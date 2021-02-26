#!/usr/bin/env python3
# coding: utf-8

import argparse
import shutil
import datetime
import re
import glob
import sys
import logging
import subprocess
import os
import os.path as osp
import markdown
import markdown.extensions.attr_list
import urllib
from urllib.parse import quote_plus

sys.path.append(osp.join(osp.dirname(__file__), ".."))
import sratic.bibliography
from sratic.metadata import YAMLDataFactory, Constructors
from sratic.schema import check_schema
from sratic.tmpl_jinja import SRAticEnvironment
from sratic.objects import ObjectStore
from sratic.remote import ObjectExporter


class Generator:
    # pylint: disable=too-many-instance-attributes
    # Eleven is reasonable in this case.
    def __init__(self,
                 template_paths=[],
                 destination_directory="../www",
                 options=None):
        self.template_paths = template_paths
        self.destination_directory = destination_directory
        self.options = options

        self.yaml_data_factory = YAMLDataFactory(None)
        schema_fn  = os.path.join(os.path.dirname(__file__), "data/schema.yml")
        self.schema = self.yaml_data_factory.load_file(schema_fn)
        self.data_dir = self.yaml_data_factory.load_file("data/root.yml")

        # Imported modules
        fns = set(filter(None,
                         [getattr(x, "__file__", None) for x in sys.modules.values()]))
        self.sources = fns
        for directory in template_paths:
            self.sources.update(glob.glob(directory + "/*"))

        # Create Jinja2 Environment
        self.env = SRAticEnvironment(template_paths)
        self.env.filters["link"] = self.__link
        self.env.filters["link_absolute"] = self.__link_absolute
        self.env.filters["markdown"] = self.markdown
        self.env.filters["quote_plus"] = lambda u: quote_plus(u)
        self.env.globals['data'] = self.data_dir.data

        self.objects = ObjectStore()
        self.exporter = ObjectExporter(self.objects)
        self.env.tests["__has_menu_children"] = self.objects.has_menu_children
        self.env.tests["__child_of"] = self.objects.is_child_of
        self.env.globals["object_list"] = self.objects.object_list
        self.env.globals["isA"] = self.objects.isA
        self.env.globals['deref'] = self.objects.deref
        self.env.globals['__get_submenu'] = self.objects.get_submenu
        self.env.globals['__id'] = self.objects.canonical_id
        self.env.globals['__get_rfc3339_timestamp'] = self.objects.get_rfc3339_timestamp
        self.env.filters['uuid'] = self.objects.uuid
        self.env.filters["sorted"] = self.objects.sorted
        self.env.globals['error'] = self.raise_error

        self.target = None

        # Register the generator as a provider for the markdown constructor
        Constructors.add("!markdown", Constructors.MARKDOWN, self.resolve_markdown_constructor)

        self.urls = set()

    # Jinja Expansions that are only possible by knowing the generator
    def __link(self, elem):
        assert isinstance(elem, str), repr(elem)
        ret = elem
        if elem.startswith("/"):
            # Relative to current destination directory
            ret = self.env.globals['page']['relative_root'] + ret
        if ret.endswith('/index.html') and self.data_dir.data['site']['baseurl'] != '.':
            ret = ret[:-len('index.html')]
        return ret

    def raise_error(self, msg, *fmt):
        loggig.error(msg, *fmt)
        raise RuntimeError()

    def __link_absolute(self, elem):
        """If elem startswith '/', we generate an absolute link according to
           site.baseurl.

           If site.baseurl is an existing directory, we generate an
           absolute file path. Otherwise, we assume baseurl is an URL.

        """
        assert isinstance(elem, str)
        if elem.startswith("/"):
            # Relative to current destination directory
            baseurl = self.data_dir.data['site']['baseurl']
            if osp.isdir(baseurl):
                baseurl = osp.abspath(osp.join(self.destination_directory, baseurl))
            elem = baseurl+elem
        return elem

    def generate_pdf(self, fn, content, url=""):
        cmd = "cd %s; pandoc --template %s -f html -V href='%s'  -o %s" % (
            osp.dirname(fn),
            self.env.find_template('pandoc-latex.template'),
            url,
            osp.basename(fn)
        )
        process = subprocess.Popen(cmd,
                                   stdin=subprocess.PIPE,
                                   shell=True)
        process.stdin.write(content.encode('utf-8'))
        process.stdin.close()
        retcode = process.wait()
        assert retcode == 0, "PDF Generation Failed for %s" % fn
        logging.info("Created PDF: %s", fn)

    def markdown(self, content, page=None):
        if page and len([1 for key in page.data.keys() if key.startswith('pandoc')]) > 0:
            extra_args = ""
            extra_args += page.data.get('pandoc.args', '')
            cmd = "pandoc --template %s -f markdown -t html5 %s" % (
                self.env.find_template('pandoc.template'), extra_args)
            process = subprocess.Popen(cmd,
                                       stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE,
                                       shell=True)
            process.stdin.write(content.encode('utf-8'))
            process.stdin.close()
            content = process.stdout.read().decode("utf-8")
        else:
            BASE_RE = r'(?<!\{)\{\:?([^%\{][^\}\n]*[^%#\}])\}(?!\{)'
            module = markdown.extensions.attr_list.AttrListTreeprocessor
            module.BASE_RE = BASE_RE
            module.HEADER_RE = re.compile(r'[ ]+%s[ ]*$' % BASE_RE)
            module.BLOCK_RE = re.compile(r'\n[ ]*%s[ ]*$' % BASE_RE)
            module.INLINE_RE = re.compile(r'^%s' % BASE_RE)
            content = markdown.markdown(content, extensions=['markdown.extensions.extra',
                                                             'markdown.extensions.toc',
                                                             'markdown.extensions.codehilite',
                                                             'sratic.markdown_tables'],
                                        safe_mode=None)
        # Posprocessing for CSS
        content = content.replace("<table>", "<table class='table'>")

        return content

    def resolve_markdown_constructor(self, fragment, parent, key):
        """This is used for the !markdown constructor, which is used to
        preprocess a string field as markdown.
        """
        text = parent[key][1][0]
        parent[key] = str(self.markdown(text))

    def do_page(self, page, pdf=False):
        # Clear the self.env
        (base, ext) = osp.splitext(page.path)
        extensions = {
            ".md": "pandoc+jinja",
            ".page": "jinja"}
        assert ext in extensions, "File extension must be " + str(list(extensions.keys()))

        # Dependency checking
        if 'formatter.target' in page.data:
            target = osp.normpath(osp.join(self.destination_directory,
                                           osp.dirname(base),
                                           page.data['formatter.target']))
            self.target = target[1:]
        elif pdf:
            target = base+'.pdf'
            self.target = base[1:] + ".pdf"
        else:
            target = osp.normpath(osp.join(self.destination_directory, base+'.html'))
            self.target = base[1:] + ".html"

        # FIXME: force build
        deps_fn = '{}/.deps.{}'.format(osp.dirname(target),
                                       osp.basename(target))
        if osp.exists(target):
            up_to_date = True
            t_time = osp.getmtime(target)
            sources = self.sources | page.sources
            if osp.exists(deps_fn):
                with open(deps_fn) as fd:
                    sources.update(fd.read().split('\0'))
            if self.data_dir.path in sources:
                sources.update(self.data_dir.sources)
            for fn in sources:
                if not osp.exists(fn):
                    continue
                time = osp.getmtime(fn)
                if time >= t_time:
                    up_to_date = False
                    break
            if not self.options.force and up_to_date:
                logging.debug("Up to date, skipping: %s (%s)" % (target, sources))
                return
            # PDF are not always regenerated
            if pdf and "ONLY" not in os.environ:
                return

        logging.info("Generating %s", target)
        # Do not change anything, if we should run dry
        if self.options.dry:
            return

        # Select the formatting pipeline
        formatter = page.data.get("formatter", extensions[ext])
        formatters = re.split("[+,|;]", formatter)

        referenced_objects = set()
        self.objects.set_referenced_objects(referenced_objects)

        page.data['pdf'] = pdf
        if '/' not in page.data['id']:
            page.data['permalink'] = self.__link_absolute('/p/' + page.data['id'].replace(':', '__'))

        # FIXME: Should be done before the generation loop. Currently
        # it is only valid for the currently processed page.
        if 'relative_root' not in page.data:
            page.data['relative_root'] = osp.relpath("/", osp.dirname(self.target))
        self.env.globals['page'].clear()
        self.env.globals['page'].update(page.data)

        content = page.data['page-body']
        for formatter in formatters:
            if formatter in ("pandoc", "markdown"):
                content = self.markdown(content, page)
            elif formatter == "jinja":
                content = self.env.expand(content)
            else:
                logging.error("Formatter %s is unknown", formatter)

        # Create Directory
        directory = osp.dirname(target)
        if not osp.exists(directory):
            os.makedirs(directory)
        # For some Pages, we generate the PDF, if it does not exist
        if pdf:
            # TODO: hard coded url
            URL = self.data_dir.data['site']['original_baseurl']
            URL += page.data['permalink.href']
            self.generate_pdf(target, content,
                              url=URL)
            return
        else:
            if set(glob.glob(base + ".*html")) - set([target]):
                logging.warning("There are other files present in the directory with a similar name: %s",
                                ", ".join(set(glob.glob(base + ".*html")) - set([target])))

            with open(target, "w+") as out:
                # don't add a specific header to txt or xml
                if not target.endswith('.html'):
                    txt = content
                # only to html
                else:
                    tmpl =  self.env.get_template("page.jinja")
                    txt = tmpl.render(page=self.env.globals['page'], body=content)
                out.write(txt)

        # create permalink symlinks
        if page.data.get('permalink.href'):
            self.create_permalink(page.data['permalink.href'], page)

        if page.data.get('permalink.alias.href'):
            self.create_permalink(page.data['permalink.alias.href'], page)


        # Save the referenced objects
        files = set()
        for id in referenced_objects:
            fn = self.objects.deref(id).get('__file__')
            if not osp.exists(fn):
                print(id, fn)
            if fn:
                files.add(fn)
        with open(deps_fn, "w+") as fd:
            fd.write("\0".join(sorted(files)))

        # Find all hrefs in html:
        # TODO: mode to detect all internal urls and search for dead urls
	#for m in re.finditer('<a[^>]*href=[\'"]([^\'"]*)[\'"]', txt):
	#    url = m.group(1)
	#    if not url.startswith("http"):
	#        self.urls.add(url)

    def create_permalink(self, href, page):
        assert href.startswith("/p/")
        perma_file = osp.join(self.destination_directory, href[1:])
        if not osp.exists(osp.dirname(perma_file)):
            os.makedirs(osp.dirname(perma_file))
        if osp.exists(perma_file):
            os.unlink(perma_file)
        logging.debug("Permalink %s -> [id:%s]", perma_file, page.data['id'])
        with open(perma_file, 'w+') as perma:
            perma.write("""<!DOCTYPE html><html lang="en"><head><meta http-equiv="refresh" content="0;url=%s"></head></html>""" %
                        self.__link_absolute(urllib.parse.quote(page.data['href'])))



def read_git(pages):
    """Retrieve author and timestamp with git.

    If the directory is in a git repository the last author and last
    modification date are extracted from git and written into the
    page.data dict, otherwise some dummy values are set.

    Arguments:
    pages -- a list of pages that are checked
    """
    try:
        # convert this to the following once python 3.5 is common used
        # subprocess.run(['git', 'rev-parse', '--show-toplevel'], check=True)
        subprocess.check_output(['git', 'rev-parse', '--show-toplevel'])
    except:
        logging.warning("Git toplevel directory not found. Disabling git support.")
        return

    for page in pages:
        # convert this to the following once python 3.5 is common used
        # subprocess.run(..., check=True, stdout=PIPE).stdout
        git_info = subprocess.check_output(['git', 'log', '-1',
                                            '--format=%at %an',
                                            '--', page.path])
        if git_info:
            time, author = git_info.decode('utf-8').split(' ', maxsplit=1)
            author = author.strip()
            time = datetime.datetime.fromtimestamp(int(time.strip()))
            page.data['last-author'] = author
            page.data['last-modification'] = time
        else:
            # Dummy value for new pages
            page.data['last-author'] = ""
            page.data['last-modification'] = datetime.datetime.now()


def main():
    parser = argparse.ArgumentParser(add_help=True,
                                     description="Website builder.")
    parser.add_argument("-d", "--destination",
                        help="destination directory", metavar="DIR",
                        default=None)
    parser.add_argument("-b", "--baseurl",
                        help="relative baseurl of all links", metavar="DIR",
                        default=None)
    parser.add_argument("-t", "--templates",
                        help="path to templates", metavar="DIR",
                        action='append',
                        default=[])
    parser.add_argument("-f", "--force",
                        help="force rebuild of whole site",
                        action="store_true", default=False)
    parser.add_argument("-j", "--jobs", type=int,
                        help="use this many build jobs", default=1)
    parser.add_argument("--assets", help="Additional asset suffixes")
    parser.add_argument("-v", "--verbose",
                        help="verbosity", default=False, action='store_true')
    parser.add_argument("--dump-objects",
                        help="Should the object export be executed?", default=False,
                        action='store_true')
    parser.add_argument("--dry",
                        help="Do not produce any output files", default=False,
                        action='store_true')

    args = parser.parse_args()
    if args.verbose or 'VERBOSE' in os.environ:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    logging.getLogger("bibtexparser.bparser").setLevel(logging.WARNING)
    logging.getLogger("MARKDOWN").setLevel(logging.WARNING)

    gen = Generator(destination_directory=args.destination,
                    template_paths=args.templates,
                    options=args)

    if args.assets:
        asset_suffixes = {x.strip() for x in args.assets.split(",")}
    else:
        asset_suffixes = set()
    # We check a few site config variables, that are required to be present
    assert 'site' in gen.data_dir.data, "root.yml does not include a 'site' configuration"
    for x in ('baseurl', 'title', 'short_title'):
        assert x in gen.data_dir.data['site'], '`site.%s\' configuration does not exist' % x
        logging.debug("Site config: %s = %s", x,
                      gen.data_dir.data['site'][x])

    gen.data_dir.data['site']['original_baseurl'] = gen.data_dir.data['site']['baseurl']
    if args.baseurl:
        gen.data_dir.data['site']['baseurl'] = args.baseurl

    pages = []
    assets = []
    for (root, dirs, files) in os.walk("."):
        for fn in files:
            if fn.startswith('.#') or fn.endswith('.swp'):
                continue
            fn = osp.join(root, fn)
            dst = osp.join(args.destination, fn)
            base, ext = osp.splitext(fn)
            ext = ext.lower()

            if os.path.islink(fn) and not os.path.relpath(os.path.realpath(fn), ".").startswith("../"):
                assert not os.path.lexists(dst) or os.path.islink(dst),\
                    "Would override non-symlink with symlink:" + dst
                symlink = os.readlink(fn)
                logging.info("Symlink: %s -> %s", dst, symlink)
                if os.path.lexists(dst):
                    os.unlink(dst)
                os.symlink(symlink, dst)
            elif ext in [".md", ".page"]:
                page = gen.yaml_data_factory.load_file(fn)
                pages.append(page)
            elif ext in asset_suffixes | {'.jpg', '.jpeg', '.png', '.pdf', '.svg', '.otf', '.gif',
                         '.xml', '.css', ".js", '.ico', '.ttf', '.woff',
                         '.woff2', '.eot', '.html', '.xls', '.xlsx' } or 'htaccess' in fn:
                assets.append(fn.lstrip("."))
                if not osp.exists(osp.dirname(dst)):
                    os.makedirs(osp.dirname(dst))
                if not osp.exists(dst) or \
                   osp.getmtime(dst) < osp.getmtime(fn):
                    shutil.copyfile(fn, dst)
                    logging.info("Copying: %s", fn)
            elif ext in {'.yml', '.bib', '.el', '.map', '.py', '.dia', ".pickle"}:
                pass
            elif 'data/bib/' in base:
                pass
            elif ext not in {'.dia'}:
                logging.warning("Ignoring: %s", fn)

    read_git(pages)

    gen.objects.crawl_pages(gen.schema, gen.data_dir, pages)
    gen.env.assets = assets

    work_packages = [list() for _ in range(0, args.jobs)]
    i = 0
    for page in sorted(pages, key=lambda x: x.path):
        if "ONLY" in os.environ:
            if not (os.environ['ONLY'] in page.path or
                    os.environ['ONLY'] in page.data['id']):
                continue
        work_packages[i].append(page)
        if len(work_packages[i]) > 3:
            i = (i + 1) % args.jobs
    # Filter out empty work packages
    work_packages = list(filter(None, work_packages))
    for work in work_packages:
        if len(work_packages) > 1:
            child = os.fork()
            if child != 0:
                continue
        else:
            child = "NOFORK"
        for page in work:
            gen.do_page(page)
            # For thesis we generate PDFs
            if gen.objects.isA(page.data, 'thesis'):
                gen.do_page(page, pdf=True)
        if child == 0:
            sys.exit(0)

    # Wait for all children to terminate
    return_code = 0
    while True:
        try:
            (pid, status) = os.wait()
            if status != 0:
                return_code = 1
        except ChildProcessError:
            break

    if args.dump_objects:
        gen.exporter.dump(os.path.join(gen.destination_directory, ".objects"))

    if gen.urls:
        print("\n".join(sorted(gen.urls)))
    sys.exit(return_code)



if __name__ == '__main__':
    main()

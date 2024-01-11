#!/usr/bin/env python3
# coding: utf-8

import unicodedata
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
from copy import deepcopy
from urllib.parse import quote_plus
from pathlib import Path

__src_dir__ = Path(__file__).parent

sys.path.append(__src_dir__.parent)
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
                 source_directory,
                 template_paths=[],
                 destination_directory="../www",
                 options=None):
        self.destination_directory = destination_directory
        self.source_directory = source_directory
        self.template_paths = template_paths
        org_cwd = os.getcwd()
        try:
            os.chdir(self.source_directory)
            self.template_paths += glob.glob("*/__templates", recursive=True)
        finally:
            os.chdir(org_cwd)
        self.options = options

        self.yaml_data_factory = YAMLDataFactory(None)
        schema_fn  = Path.cwd() / 'data' / 'schema.yml'
        if not schema_fn.exists():
            schema_fn  = __src_dir__ / 'data' / 'schema.yml'
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
        self.env.globals["markdown"] = self.call_markdown
        self.env.filters["quote_plus"] = lambda u: quote_plus(u)
        self.env.globals['data'] = self.data_dir.data
        self.env.globals["datetime"] = datetime.datetime
        self.env.globals["timedelta"] = datetime.timedelta


        self.objects = ObjectStore()
        # Transfer object constructor from schema to object store
        for _type, _schema in self.schema.data.items():
            if '__init__' in _schema:
                module, name = _schema['__init__'].rsplit(".", 1)
                module = __import__(module, fromlist=[name])
                constructor = getattr(module, name)
                del _schema['__init__']
                self.objects.object_constructors[_type] = constructor

        self.exporter = ObjectExporter(self.objects)
        self.env.tests["__has_menu_children"] = self.objects.has_menu_children
        self.env.tests["__child_of"] = self.objects.is_child_of
        self.env.tests["__teaching_sose"] = self.objects.teaching_sose
        self.env.tests["__teaching_wise"] = self.objects.teaching_wise
        self.env.globals["object_list"] = self.objects.object_list
        self.env.filters["object_unique"] = self.objects.object_unique
        self.env.globals["isA"] = self.objects.isA
        self.env.globals['deref'] = self.objects.deref
        self.env.globals['__get_submenu'] = self.objects.get_submenu
        self.env.globals['__id'] = self.objects.canonical_id
        self.env.globals['__get_rfc3339_timestamp'] = self.objects.get_rfc3339_timestamp
        self.env.filters['uuid'] = self.objects.uuid
        self.env.filters["sorted"] = self.objects.sorted
        self.env.globals['error'] = self.raise_error

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
        logging.error(msg, *fmt)
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

    def call_markdown(self, caller):
        content = caller()
        # Autogobble
        content = "\n" + content.lstrip("\n") 
        prefix  = len(content) - len(content.lstrip('\n\t '))
        content = content.replace(content[:prefix], "\n")
        content = content.lstrip("\n")
        return self.markdown(content)

    def markdown(self, content, page=None):
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

    def check_dependencies(self, page, target):
        """Check if the target file `target` has to be rebuild.

           @returns: True if target is up to date
        """
        deps_fn = '{}/.deps.{}'.format(osp.dirname(target),
                                       osp.basename(target))
        if not osp.exists(target):
            return False

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
        return up_to_date

    def dump_dependencies(self, referenced_objects, target):
        deps_fn = '{}/.deps.{}'.format(osp.dirname(target),
                                       osp.basename(target))
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



    def do_page_format(self, page, formatters):
        referenced_objects = set()
        self.objects.set_referenced_objects(referenced_objects)

        self.env.globals['page'].clear()
        self.env.globals['page'].update(page.data)

        content = page.data['page-body']
        for formatter in formatters:
            if formatter == "markdown":
                content = self.markdown(content, page)
            elif formatter == "jinja":
                content = content.replace("<markdown>", "{%+ call markdown() +%}")
                content = content.replace("</markdown>", "{%+ endcall +%}")
                content = self.env.expand(content)
            else:
                logging.error("Formatter %s is unknown", formatter)
        return content, referenced_objects


    def output_jinja(self, page, formatted, page_template, target):
        # Create Directory
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w+") as out:
            tmpl =  self.env.get_template(page_template)
            txt = tmpl.render(page=self.env.globals['page'], body=formatted)
            out.write(txt)

    def output_raw(self, page, formatted, page_template, target):
        # Create Directory
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w+") as out:
            out.write(formatted)

    def do_page(self, page):
        # Clear the self.env
        (base, ext) = osp.splitext(page.path)
        extensions = {
            ".md":   "markdown+jinja",
            ".page": "jinja",
            ".xml": "jinja",
        }
        if ext not in extensions:
            raise RuntimeError(f"Invalid File Extension: {page.path}; options: {list(extensions.keys())}")

        # Destination path in the filesystem
        dest_directory = osp.normpath(osp.join(self.destination_directory,
                                               osp.dirname(base)))
        # Destination URL (relative to site.baseurl)
        url_directory = osp.dirname(base)[1:]
        if not url_directory:
            url_directory = '/'

        # Stem of the destination file
        dest_stem = osp.basename(base)

        if 'relative_root' not in page.data:
            page.data['relative_root'] = osp.relpath("/", url_directory)

        # Stores the formatted page body
        formatted = None

        # For each output template, we will create one file.
        for page_template in page.data.get('formatter.output_templates', ['page.jinja']):
            # Create the output filename
            X = page_template.split(".")
            if len(X) == 2:
                _, output_mode = X
                dest_ext = "html"
            else:
                _, dest_ext, output_mode = X

            if 'formatter.target' in page.data:
                dest_filename = page.data['formatter.target']
            else:
                dest_filename = f"{dest_stem}.{dest_ext}"

            dest_path = osp.join(dest_directory, dest_filename)
            dest_url  = osp.join(url_directory, dest_filename)

            similar = set(glob.glob(f'{dest_directory}*{dest_ext}')) - set([dest_path])
            if similar:
                logging.warning("There are other files present in the directory with a similar name: %s",
                                ", ".join(similar))

            up_to_date = self.check_dependencies(page, dest_path)

            if not self.options.force and up_to_date:
                logging.debug("Up to date, skipping: %s" % (dest_path))
                continue

            logging.info("Generating %s", dest_url)
            # Do not change anything, if we should run dry
            if self.options.dry:
                continue

            # We format the core page exactly once
            if formatted is None:
                # Select the formatting pipeline
                formatters = page.data.get("formatter", extensions[ext])
                formatters = re.split("[+,|;]", formatters)

                # Invoke the formatter pipeline for the page body
                formatted, ref_objs = self.do_page_format(page, formatters)

            # Write the file to disk
            output_routine = getattr(self, f'output_{output_mode}')
            output_routine(page, formatted, page_template, dest_path)

        if formatted:
            self.dump_dependencies(ref_objs, dest_path)

        # create permalink symlinks
        if page.data.get('permalink.href'):
            self.create_permalink(page.data['permalink.href'], page)

        if page.data.get('permalink.alias.href'):
            self.create_permalink(page.data['permalink.alias.href'], page)

        # Find all hrefs in html:
        # TODO: mode to detect all internal urls and search for dead urls
	#for m in re.finditer('<a[^>]*href=[\'"]([^\'"]*)[\'"]', txt):
	#    url = m.group(1)
	#    if not url.startswith("http"):
	#        self.urls.add(url)

    def create_permalink(self, href, page):
        perma_file = Path(self.destination_directory, href[1:], 'index.html')
        logging.debug("Prepare Permalink: %s", perma_file.parent)
        if perma_file.parent.exists() and perma_file.parent.is_file():
                perma_file.parent.unlink()
        perma_file.parent.mkdir(parents=True, exist_ok=True)
        logging.debug("Permalink %s -> [id:%s]", perma_file, page.data['id'])
        with open(perma_file, 'w') as perma:
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

    gen = Generator(source_directory=os.path.abspath(os.curdir),
                    destination_directory=args.destination,
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

            with open(fn, 'rb') as fd:
                has_prematter = (fd.read(3) == b'---')

            if os.path.islink(fn) and not os.path.relpath(os.path.realpath(fn), ".").startswith("../"):
                assert not os.path.lexists(dst) or os.path.islink(dst),\
                    "Would override non-symlink with symlink:" + dst
                symlink = os.readlink(fn)
                logging.info("Symlink: %s -> %s", dst, symlink)
                if os.path.lexists(dst):
                    os.unlink(dst)
                if not osp.exists(osp.dirname(dst)):
                    os.makedirs(osp.dirname(dst))
                os.symlink(symlink, dst)
            elif ext in [".md", ".page"] or (has_prematter and ext in [".xml"]):
                page = gen.yaml_data_factory.load_file(fn)
                for name, value in gen.env.globals['data']['site'].get('default_page', {}).items():
                    if name not in page.data:
                        page.data[name] = deepcopy(value)
                pages.append(page)
            elif ext in asset_suffixes | {'.jpg', '.jpeg', '.png', '.pdf', '.svg', '.otf', '.gif',
                         '.xml', '.css', ".js", '.ico', '.ttf', '.woff',
                         '.woff2', '.eot', '.html', '.xls', '.xlsx' } or 'htaccess' in fn:
                assets.append(unicodedata.normalize("NFC", fn.lstrip(".")))
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
            elif ext not in {'.dia'} and '/.git/' not in fn:
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

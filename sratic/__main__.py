#!/usr/bin/env python3

import argparse
import datetime
import glob
import logging
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib
import urllib.parse
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import NoReturn
from urllib.parse import quote_plus

import markdown
import markdown.extensions.attr_list

__src_dir__ = Path(__file__).parent

sys.path.append(str(__src_dir__.parent))
import sratic.bibliography  # noqa: F401
from sratic.metadata import Constructor, Replace, YAMLDataFactory, YAMLFragment
from sratic.objects import ObjectStore
from sratic.remote import ObjectExporter
from sratic.schedule_table import ScheduleExtension, schedule_table
from sratic.tmpl_jinja import SRAticEnvironment


class Generator:
    # pylint: disable=too-many-instance-attributes
    # Eleven is reasonable in this case.
    def __init__(
        self,
        source_directory: str,
        template_paths: list[str] | None = None,
        destination_directory: str = "../www",
        options: argparse.Namespace | None = None,
    ) -> None:
        self.destination_directory: str = destination_directory
        self.source_directory: str = source_directory
        self.template_paths: list[str] = (
            template_paths if template_paths is not None else []
        )
        org_cwd = os.getcwd()
        try:
            os.chdir(self.source_directory)
            self.template_paths += glob.glob("*/__templates", recursive=True)
        finally:
            os.chdir(org_cwd)
        self.options = options

        self.yaml_data_factory = YAMLDataFactory(None)
        # Register before loading data, which may contain !markdown tags.
        Constructor.add("!markdown", self.resolve_markdown_constructor)
        schema_fn = Path.cwd() / "data" / "schema.yml"
        if not schema_fn.exists():
            schema_fn = __src_dir__ / "data" / "schema.yml"
        self.schema = self.yaml_data_factory.load_file(schema_fn)
        self.data_dir = self.yaml_data_factory.load_file(Path("data/root.yml"))

        # Imported modules
        fns = set(
            filter(None, [getattr(x, "__file__", None) for x in sys.modules.values()])
        )
        self.sources = fns
        for directory in self.template_paths:
            self.sources.update(glob.glob(directory + "/*"))

        # Create Jinja2 Environment
        self.env = SRAticEnvironment([Path(p) for p in self.template_paths])
        self.env.filters["link"] = self.__link
        self.env.filters["link_absolute"] = self.__link_absolute
        self.env.filters["markdown"] = self.markdown
        env_globals: dict = self.env.globals
        env_globals["markdown"] = self.call_markdown
        self.env.filters["quote_plus"] = lambda u: quote_plus(u)
        env_globals["data"] = self.data_dir.data
        env_globals["datetime"] = datetime.datetime
        env_globals["timedelta"] = datetime.timedelta

        env_globals["schedule_table"] = schedule_table

        self.objects = ObjectStore()
        # Transfer object constructor from schema to object store
        for _type, _schema in self.schema.data.items():
            if "__init__" in _schema:
                module, name = _schema["__init__"].rsplit(".", 1)
                module = __import__(module, fromlist=[name])
                constructor = getattr(module, name)
                del _schema["__init__"]
                self.objects.object_constructors[_type] = constructor

        self.exporter = ObjectExporter(self.objects)
        env_tests: dict = self.env.tests
        env_tests["__has_menu_children"] = self.objects.has_menu_children
        env_tests["__child_of"] = self.objects.is_child_of
        env_tests["__teaching_sose"] = self.objects.teaching_sose
        env_tests["__teaching_wise"] = self.objects.teaching_wise
        env_globals["object_list"] = self.objects.object_list
        self.env.filters["object_unique"] = self.objects.object_unique
        env_globals["isA"] = self.objects.isA
        env_globals["deref"] = self.objects.deref
        env_globals["__get_submenu"] = self.objects.get_submenu
        env_globals["__id"] = self.objects.canonical_id
        env_globals["__get_rfc3339_timestamp"] = self.objects.get_rfc3339_timestamp
        self.env.filters["uuid"] = self.objects.uuid
        self.env.filters["sorted"] = self.objects.sorted
        env_globals["error"] = self.raise_error

        self.urls = set()

    # Jinja Expansions that are only possible by knowing the generator
    def __link(self, elem: str) -> str:
        assert isinstance(elem, str), repr(elem)
        ret = elem
        if elem.startswith("/"):
            # Relative to current destination directory
            globals: dict = self.env.globals
            ret = globals["page"]["relative_root"] + ret
        if ret.endswith("/index.html") and self.data_dir.data["site"]["baseurl"] != ".":
            ret = ret[: -len("index.html")]
        return ret

    def raise_error(self, msg: str, *fmt: object) -> NoReturn:
        logging.error(msg, *fmt)
        raise RuntimeError()

    def __link_absolute(self, elem: str) -> str:
        """If elem startswith '/', we generate an absolute link according to
        site.baseurl.

        If site.baseurl is an existing directory, we generate an
        absolute file path. Otherwise, we assume baseurl is an URL.

        """
        assert isinstance(elem, str)
        if elem.startswith("/"):
            # Relative to current destination directory
            baseurl = self.data_dir.data["site"]["baseurl"]
            if Path(baseurl).is_dir():
                baseurl = str((Path(self.destination_directory) / baseurl).resolve())
            elem = baseurl + elem
        return elem

    def call_markdown(self, caller: Callable[[], str]) -> str:
        content = caller()
        # Autogobble
        content = "\n" + content.lstrip("\n")
        prefix = len(content) - len(content.lstrip("\n\t "))
        content = content.replace(content[:prefix], "\n")
        content = content.lstrip("\n")
        return self.markdown(content)

    def markdown(self, content: str, page: YAMLFragment | None = None) -> str:
        BASE_RE = r"(?<!\{)\{\:?([^%\{][^\}\n]*[^%#\}])\}(?!\{)"
        module = markdown.extensions.attr_list.AttrListTreeprocessor
        module.BASE_RE = BASE_RE
        module.HEADER_RE = re.compile(f"[ ]+{BASE_RE}[ ]*$")
        module.BLOCK_RE = re.compile(f"\n[ ]*{BASE_RE}[ ]*$")
        module.INLINE_RE = re.compile(f"^{BASE_RE}")
        content = markdown.markdown(
            content,
            extensions=[
                "markdown.extensions.extra",
                "markdown.extensions.toc",
                "markdown.extensions.codehilite",
                "sratic.markdown_tables",
                ScheduleExtension(),
            ],
            safe_mode=None,
        )
        # Posprocessing for CSS
        content = content.replace("<table>", "<table class='table'>")

        return content

    def resolve_markdown_constructor(
        self,
        fragment: YAMLFragment,
        ctx: Constructor,
    ) -> Replace:
        """This is used for the !markdown constructor, which is used to
        preprocess a string field as markdown.
        """
        assert type(ctx.value) is str
        return Replace(self.markdown(ctx.value))

    def check_dependencies(self, page: YAMLFragment, target: Path) -> bool:
        """Check if the target file `target` has to be rebuild.

        @returns: True if target is up to date
        """
        deps_fn = target.parent / f".deps.{target.name}"
        if not target.exists():
            return False

        up_to_date = True
        t_time = target.stat().st_mtime
        sources = self.sources | page.sources
        if deps_fn.exists():
            with deps_fn.open() as fd:
                sources.update(fd.read().split("\0"))
        if self.data_dir.path in sources:
            sources.update(self.data_dir.sources)
        for fn in sources:
            source_path = Path(fn)
            if not source_path.exists():
                continue
            time = source_path.stat().st_mtime
            if time >= t_time:
                up_to_date = False
                break
        return up_to_date

    def dump_dependencies(self, referenced_objects: set[str], target: Path) -> None:
        deps_fn = target.parent / f".deps.{target.name}"
        # Save the referenced objects
        files = set()
        for id in referenced_objects:
            obj = self.objects.deref(id)
            assert obj is not None
            fn = obj.get("__file__")
            assert isinstance(fn, Path)
            if not fn.exists():
                print(id, fn)
            if fn:
                files.add(fn)
        with deps_fn.open("w+") as fd:
            fd.write("\0".join(sorted(f"./{f}" for f in files)))

    def do_page_format(
        self, page: YAMLFragment, formatters: list[str]
    ) -> tuple[str, set[str]]:
        referenced_objects = set()
        self.objects.set_referenced_objects(referenced_objects)

        globals: dict = self.env.globals
        globals["page"].clear()
        globals["page"].update(page.data)

        content = page.data["page-body"]
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

    def output_jinja(
        self, page: YAMLFragment, formatted: str, page_template: str, target: str
    ) -> None:
        # Create Directory
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        with Path(target).open("w+") as out:
            tmpl = self.env.get_template(page_template)
            txt = tmpl.render(page=self.env.globals["page"], body=formatted)
            out.write(txt)

    def output_raw(
        self, page: YAMLFragment, formatted: str, page_template: str, target: str
    ) -> None:
        # Create Directory
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        with Path(target).open("w+") as out:
            out.write(formatted)

    def do_page(self, page: YAMLFragment) -> None:
        # Clear the self.env
        assert page.path is not None
        assert self.options is not None
        extensions = {
            ".md": "markdown+jinja",
            ".page": "jinja",
            ".xml": "jinja",
        }
        if page.path.suffix not in extensions:
            raise RuntimeError(
                f"Invalid File Extension: {page.path}; options: {list(extensions.keys())}"
            )

        # Destination path in the filesystem
        dest_directory = self.destination_directory / page.path.parent

        # Destination URL (relative to site.baseurl)
        url_directory = Path("/") / page.path.parent

        # Stem of the destination file
        dest_stem = page.path.stem

        if "relative_root" not in page.data:
            page.data["relative_root"] = os.path.relpath("/", url_directory)

        # Stores the formatted page body
        formatted = None

        # For each output template, we will create one file.
        for page_template in page.data.get(
            "formatter.output_templates", ["page.jinja"]
        ):
            # Create the output filename
            X = page_template.split(".")
            if len(X) == 2:
                _, output_mode = X
                dest_ext = "html"
            else:
                _, dest_ext, output_mode = X

            if "formatter.target" in page.data:
                dest_filename = page.data["formatter.target"]
            else:
                dest_filename = f"{dest_stem}.{dest_ext}"

            dest_path = dest_directory / dest_filename
            dest_url = url_directory / dest_filename

            similar = set(glob.glob(f"{dest_directory}*{dest_ext}")) - {dest_path}
            if similar:
                logging.warning(
                    "There are other files present in the directory with a similar name: %s",
                    ", ".join(similar),
                )

            up_to_date = self.check_dependencies(page, dest_path)

            if not self.options.force and up_to_date:
                logging.debug("Up to date, skipping: %s", dest_path)
                continue

            logging.info("Generating %s", dest_url)
            # Do not change anything, if we should run dry
            if self.options.dry:
                continue

            # We format the core page exactly once
            if formatted is None:
                # Select the formatting pipeline
                formatters = page.data.get("formatter", extensions[page.path.suffix])
                formatters = re.split("[+,|;]", formatters)

                # Invoke the formatter pipeline for the page body
                formatted, ref_objs = self.do_page_format(page, formatters)

            # Write the file to disk
            output_routine = getattr(self, f"output_{output_mode}")
            output_routine(page, formatted, page_template, dest_path)

        if formatted:
            self.dump_dependencies(ref_objs, dest_path)

        # create permalink symlinks
        if page.data.get("permalink.href"):
            self.create_permalink(page.data["permalink.href"], page)

        if page.data.get("permalink.alias.href"):
            self.create_permalink(page.data["permalink.alias.href"], page)

    def create_permalink(self, href: str, page: YAMLFragment) -> None:
        perma_file = Path(self.destination_directory, href[1:], "index.html")
        logging.debug("Prepare Permalink: %s", perma_file.parent)
        if perma_file.parent.exists() and perma_file.parent.is_file():
            perma_file.parent.unlink()
        perma_file.parent.mkdir(parents=True, exist_ok=True)
        logging.debug("Permalink %s -> [id:%s]", perma_file, page.data["id"])
        with perma_file.open("w") as perma:
            perma.write(
                f'<!DOCTYPE html><html lang="en"><head><meta '
                f'http-equiv="refresh" content="0;url='
                f'{self.__link_absolute(urllib.parse.quote(page.data["href"]))}"></head></html>'
            )


def read_git(pages: list[YAMLFragment]) -> None:
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
        subprocess.check_output(["git", "rev-parse", "--show-toplevel"])
    except:
        logging.warning("Git toplevel directory not found. Disabling git support.")
        return

    for page in pages:
        assert page.path is not None
        # convert this to the following once python 3.5 is common used
        # subprocess.run(..., check=True, stdout=PIPE).stdout
        git_info = subprocess.check_output(
            ["git", "log", "-1", "--format=%at %an", "--", page.path]
        )
        if git_info:
            time, author = git_info.decode("utf-8").split(" ", maxsplit=1)
            author = author.strip()
            time = datetime.datetime.fromtimestamp(int(time.strip()))
            page.data["last-author"] = author
            page.data["last-modification"] = time
        else:
            # Dummy value for new pages
            page.data["last-author"] = ""
            page.data["last-modification"] = datetime.datetime.now()


def main() -> NoReturn:
    parser = argparse.ArgumentParser(add_help=True, description="Website builder.")
    parser.add_argument(
        "-d", "--destination", help="destination directory", metavar="DIR", default=None
    )
    parser.add_argument(
        "-b",
        "--baseurl",
        help="relative baseurl of all links",
        metavar="DIR",
        default=None,
    )
    parser.add_argument(
        "-t",
        "--templates",
        help="path to templates",
        metavar="DIR",
        action="append",
        default=[],
    )
    parser.add_argument(
        "-f",
        "--force",
        help="force rebuild of whole site",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-j", "--jobs", type=int, help="use this many build jobs", default=1
    )
    parser.add_argument("--assets", help="Additional asset suffixes")
    parser.add_argument(
        "-v", "--verbose", help="verbosity", default=False, action="store_true"
    )
    parser.add_argument(
        "--dump-objects",
        help="Should the object export be executed?",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--dry",
        help="Do not produce any output files",
        default=False,
        action="store_true",
    )

    args = parser.parse_args()
    if args.verbose or "VERBOSE" in os.environ:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    logging.getLogger("bibtexparser.bparser").setLevel(logging.WARNING)
    logging.getLogger("MARKDOWN").setLevel(logging.WARNING)

    gen = Generator(
        source_directory=os.path.abspath(os.curdir),
        destination_directory=args.destination or "../www",
        template_paths=args.templates,
        options=args,
    )

    if args.assets:
        asset_suffixes = {x.strip() for x in args.assets.split(",")}
    else:
        asset_suffixes = set()
    # We check a few site config variables, that are required to be present
    assert "site" in gen.data_dir.data, (
        "root.yml does not include a 'site' configuration"
    )
    for x in ("baseurl", "title", "short_title"):
        assert x in gen.data_dir.data["site"], (
            f"`site.{x}' configuration does not exist"
        )
        logging.debug("Site config: %s = %s", x, gen.data_dir.data["site"][x])

    gen.data_dir.data["site"]["original_baseurl"] = gen.data_dir.data["site"]["baseurl"]
    if args.baseurl:
        gen.data_dir.data["site"]["baseurl"] = args.baseurl

    pages: list[YAMLFragment] = []
    assets: list[str] = []
    env_globals: dict = gen.env.globals
    for root, dirs, files in os.walk("."):
        for filename in files:
            if filename.startswith(".#") or filename.endswith(".swp"):
                continue
            fn = Path(root) / filename
            if fn.is_dir():
                continue
            dst = Path(args.destination or "../www") / fn
            ext = fn.suffix.lower()

            if fn.is_symlink() and fn.resolve().is_relative_to(Path.cwd()):
                assert not dst.exists() or dst.is_symlink(), (
                    f"Would override non-symlink with symlink: {dst}"
                )
                symlink = fn.readlink()
                logging.info("Symlink: %s -> %s", dst, symlink)
                dst.unlink(missing_ok=True)
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.symlink_to(symlink)
                continue

            with fn.open("rb") as fd:
                has_prematter = fd.read(3) == b"---"

            if ext in [".md", ".page"] or (has_prematter and ext in [".xml"]):
                page = gen.yaml_data_factory.load_file(fn)
                for name, value in (
                    env_globals["data"]["site"].get("default_page", {}).items()
                ):
                    if name not in page.data:
                        page.data[name] = deepcopy(value)
                pages.append(page)
            elif (
                ext
                in asset_suffixes
                | {
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".pdf",
                    ".svg",
                    ".otf",
                    ".gif",
                    ".webp",
                    ".xml",
                    ".css",
                    ".js",
                    ".ico",
                    ".ttf",
                    ".woff",
                    ".webm",
                    ".mp4",
                    ".mkv",
                    ".ogv",
                    ".avi",
                    ".mpg",
                    ".woff2",
                    ".eot",
                    ".html",
                    ".xls",
                    ".xlsx",
                }
                or "htaccess" in fn.name
            ):
                assets.append(unicodedata.normalize("NFC", "/" + fn.as_posix()))
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not dst.exists() or dst.stat().st_mtime < fn.stat().st_mtime:
                    shutil.copyfile(fn, dst)
                    logging.info("Copying: %s", fn)
            elif (
                ext in {".yml", ".bib", ".el", ".map", ".py", ".dia", ".pickle"}
                or "data/bib/" in fn.as_posix()
            ):
                pass
            elif ext not in {".dia"} and ".git" not in fn.parts:
                logging.warning("Ignoring: %s", fn)

    read_git(pages)

    gen.objects.crawl_pages(gen.schema, gen.data_dir, pages)
    gen.env.assets = assets

    work_packages = [[] for _ in range(args.jobs)]
    i = 0
    for page in sorted(pages, key=lambda x: x.path or ""):
        assert page.path is not None
        if "ONLY" in os.environ and not (
            os.environ["ONLY"] in page.path.as_posix()
            or os.environ["ONLY"] in page.data["id"]
        ):
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
        gen.exporter.dump(Path(gen.destination_directory) / ".objects")

    if gen.urls:
        print("\n".join(sorted(gen.urls)))
    sys.exit(return_code)


if __name__ == "__main__":
    main()

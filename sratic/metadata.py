# Metadata in SRAtic is stored as YAML. It can be contained directly
# in .yml files, or as a header within a page.

import glob
import io
import logging
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import yaml


class Constructors:
    INCLUDE = 1
    SPLICE = 2
    LOAD_BIBTEX = 3
    PATH = 4
    MARKDOWN = 5
    LOAD_CSV = 6

    handlers: dict[int, Callable[["YAMLFragment", Any, Any], Any]] = {}

    @staticmethod
    def add(
        key: str,
        tag: int,
        fn: Callable[["YAMLFragment", Any, Any], Any],
    ) -> None:
        if tag in Constructors.handlers:
            return
        yaml.add_constructor(key, lambda loader, node: (tag, [node.value]))
        Constructors.handlers[tag] = fn


class YAMLFragment:
    def __init__(self, config: Any) -> None:
        self.config = config
        self.sources: set[Path] = set()
        self.data: Any = None
        self.path: Path | None = None  # Relative path to source file

    def __repr__(self) -> str:
        return f"YAMLFragment('{self.path}')"

    def __include_filename(self, data: Any, fn: Path) -> None:
        if type(data) is list:
            for elem in data:
                self.__include_filename(elem, fn)
        elif type(data) is dict:
            for elem in data:
                self.__include_filename(data[elem], fn)
        elif type(data) is tuple and data and data[0] in Constructors.handlers:
            data[1].append(fn)

    def load_from_file(self, filename: Path) -> None:
        """Loads the data from the given source file into this YAML Fragment"""
        if not filename.exists():
            # Fallback to SRAtic provided files
            filename = Path(__file__).parent / "data" / filename.name
        self.path = filename
        with Path(filename).open() as stream:
            try:
                if filename.suffix == ".myml":
                    self.data = list(yaml.load_all(stream, Loader=yaml.Loader))
                else:
                    self.data = yaml.load(stream, Loader=yaml.Loader)
            except Exception as x:
                logging.error("Error in %s", filename)
                raise x

        self.__include_filename(self.data, filename)
        self.sources.add(filename)

    def load_from_string(self, text: str, origin_filename: Path | None = None) -> None:
        self.path = origin_filename
        try:
            self.data = yaml.load(io.StringIO(text), Loader=yaml.Loader)
        except Exception as x:
            logging.error("Error in %s", origin_filename)
            raise x

        if origin_filename:
            self.__include_filename(self.data, origin_filename)
            self.sources.add(origin_filename)

    def load_nothing(self, origin_filename: Path | None = None) -> None:
        self.path = origin_filename
        self.data = {}
        if origin_filename:
            self.__include_filename(self.data, origin_filename)
            self.sources.add(origin_filename)

    def objects(self) -> Iterator[dict[str, Any]]:
        """Iterator over all objects"""
        visited: set[int] = set()
        for prefix, k in self.__objects(self.data, visited):
            yield k

    def __objects(
        self, x: Any, visited: set[int], prefix: list[Any] = []
    ) -> Iterator[tuple[list[Any], dict[str, Any]]]:
        """A depth-first search through to reveal all objects in the object space."""
        if id(x) in visited:
            return
        visited.add(id(x))

        if type(x) is list:
            for idx, elem in enumerate(x):
                if type(elem) not in (list, dict):
                    continue
                for k in self.__objects(elem, visited, prefix + [idx]):
                    yield k

        elif type(x) is dict:
            if "id" in x or "type" in x:
                if not "id" in x:
                    assert self.path is not None
                    x["id"] = f"{self.path}-{id(x)}"
                yield prefix, x

            for key, elem in x.items():
                if type(elem) not in (list, dict):
                    continue
                for k in self.__objects(elem, visited, prefix + [key]):
                    yield k


class YAMLDataFactory:
    def __init__(self, config: Any) -> None:
        # Absolute filenames -> YAMLFragment
        self.__config = config
        self.__cache: dict[Path, YAMLFragment] = {}

        # The !include constructor does insert the whole referenced
        # document instead of the field
        Constructors.add("!include", Constructors.INCLUDE, self.__resolve_include)

        # The !splice tag is similar to !include, but merges the
        # referenced document into the parent node.
        Constructors.add("!splice", Constructors.SPLICE, self.__resolve_splice)

        # The !path constructor
        Constructors.add("!path", Constructors.PATH, self.__resolve_path)

    def __load_fragment(self, filename: Path) -> YAMLFragment:
        """Load YAML Fragment, with caching. Fragments do not only originate
        in .yml files, but also pages can be given.

        """
        filename = filename.absolute()
        if filename in self.__cache:
            return self.__cache[filename]
        # Load data file
        fragment = YAMLFragment(self.__config)
        if filename.suffix in {".yml", ".myml"}:
            fragment.load_from_file(filename)
        else:
            # Scrape data from file preface
            with Path(filename).open() as fd:
                start = fd.read(3)
                if start == "---":
                    text = []
                    while True:
                        line = fd.readline()
                        if line is None or line.strip() == "---":
                            break
                        text.append(line)
                    fragment.load_from_string("".join(text), filename)
                else:
                    fragment.load_nothing(filename)
                ### Page Content
                fragment.data["page-body"] = fd.read()

            # Pages also read in their directory 'variables' file,
            # implicitly
            dirname = Path(filename).parent
            dir_file = dirname / "variables.yml"
            if dir_file.exists():
                if type(fragment.data) is list:
                    fragment.data.append(
                        (Constructors.SPLICE, [str(dir_file), "./IGNORE.yml"])
                    )
                elif type(fragment.data) is dict:
                    fragment.data[object()] = (
                        Constructors.SPLICE,
                        [str(dir_file), "./ignore.yml"],
                    )
                else:
                    sys.exit(
                        f"YAML Type in {filename} is wrong ({type(fragment.data)})"
                    )

        # Mark as placed in cache. Cannot be changed.
        self.__cache[filename] = fragment
        return fragment

    def load_file(self, filename: Path) -> YAMLFragment:
        """Loads file, and resolves all external references. As a result, we
        get an newly created YAML Fragment."""

        ret = YAMLFragment(self.__config)
        ret.load_nothing(filename)
        ret.data = [(Constructors.INCLUDE, [filename, "./IGNORE.yml"])]
        again = True
        while again:
            ret, again = self.__resolve(ret, ret.data)

        ret.data = ret.data[0]
        if ret.data is None:
            ret.data = {}
        return ret

    ### Resolve Constructors
    def __resolve_splice(
        self, fragment: YAMLFragment, parent: Any, key: int | str
    ) -> bool:
        fn, stmt_fn = parent[key][1]
        if "*" in fn:
            fns = [str(path) for path in glob.glob(str(Path(stmt_fn).parent / fn))]
        else:
            fns = [fn]

        splice_data: Any = None
        for fn in fns:
            fn = Path(stmt_fn).parent / fn
            other = self.__load_fragment(fn)
            fragment.sources.update(other.sources)
            assert type(other.data) == type(parent), (
                f"Splicing for {fn} failed. Type mismatch ({type(other.data)} != {type(parent)})"
            )
            if splice_data is None:
                splice_data = other.data.copy()
            elif type(other.data) is dict:
                splice_data.update(other.data)
            else:
                splice_data += other.data

        if type(parent) is list:
            assert isinstance(key, int)
            assert isinstance(splice_data, list)
            parent[key : key + 1] = splice_data
        else:
            del parent[key]
            assert isinstance(splice_data, dict)
            for k, v in splice_data.items():
                parent[k] = v
        return True

    def __resolve_include(
        self, fragment: YAMLFragment, parent: Any, key: int | str
    ) -> bool:
        fn, stmt_fn = parent[key][1]
        fn = Path(stmt_fn).parent / fn
        other = self.__load_fragment(fn)
        parent[key] = other.data
        fragment.sources.update(other.sources)
        return True

    def __resolve_path(
        self, fragment: YAMLFragment, parent: Any, key: int | str
    ) -> None:
        fn, stmt_fn = parent[key][1]
        if fn[0] == "/":
            parent[key] = fn
            return
        path = (Path(stmt_fn).parent / fn).resolve()
        fn = path.relative_to(Path.cwd()).as_posix()
        parent[key] = "/" + fn

    def __resolve(self, fragment: YAMLFragment, x: Any) -> tuple[YAMLFragment, bool]:
        """One depth-first search, to resolve constructors. Returns true, if
        this process has to be repeated.

        """
        handlers = Constructors.handlers
        again = False
        if type(x) is list:
            for idx, value in enumerate(x):
                if (
                    type(value) is tuple
                    and value
                    and isinstance(value[0], int)
                    and value[0] in handlers
                    and handlers[value[0]](fragment, x, idx)
                ):
                    again = True

                # Recursion
                if type(value) in (list, dict):
                    _, change = self.__resolve(fragment, value)
                    again = change or again
        elif type(x) is dict:
            for key, value in list(x.items()):
                if (
                    type(value) is tuple
                    and value
                    and isinstance(value[0], int)
                    and value[0] in handlers
                    and handlers[value[0]](fragment, x, key)
                ):
                    again = True
                # Recursion!
                if type(value) in (list, dict):
                    _, change = self.__resolve(fragment, value)
                    again = change or again
        return fragment, again

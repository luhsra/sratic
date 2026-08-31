# Metadata in SRAtic is stored as YAML. It can be contained directly
# in .yml files, or as a header within a page.

import io
import logging
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Replace:
    value: Any
    again: bool = False


@dataclass
class Splice:
    value: list | dict
    again: bool = False


@dataclass
class Constructor:
    """Deferred constructor for YAML tags."""

    tag: str
    value: Any
    """YAML node value"""
    resolve: Callable[["YAMLFragment", "Constructor"], Replace | Splice] = field(
        repr=False
    )
    """Handler for resolving the constructor, the result can either be replaced or spliced into the parent object"""
    origin: Path | None = None
    """Original path of the fragment"""

    def __call__(self, fragment: "YAMLFragment") -> Replace | Splice:
        logging.debug(f"Constructor: {self}")
        return self.resolve(fragment, self)

    @staticmethod
    def add(
        tag: str,
        resolve: Callable[["YAMLFragment", "Constructor"], Replace | Splice],
    ) -> None:
        """Register a deferred constructor for a YAML tag."""
        yaml.add_constructor(
            tag, lambda loader, node: Constructor(tag, node.value, resolve)
        )


class YAMLFragment:
    def __init__(self, config: Any, path: Path, data: Any) -> None:
        self.config: Any = config
        self.path: Path = path  # Relative path to source file
        self.data: Any = data
        self.sources: set[Path] = {path}

        self.__include_filename(self.data, path)

    def __repr__(self) -> str:
        return f"YAMLFragment('{self.path}')"

    def __include_filename(self, data: Any, fn: Path) -> None:
        """Recursively include the filename in any constructor data."""
        if type(data) is list:
            for elem in data:
                self.__include_filename(elem, fn)
        elif type(data) is dict:
            for elem in data:
                self.__include_filename(data[elem], fn)
        elif isinstance(data, Constructor):
            data.origin = fn

    def objects(self) -> Iterator[dict[str, Any]]:
        """Iterator over all objects"""
        visited: set[int] = set()
        for prefix, k in self.__objects(self.data, visited):
            yield k

    def __objects(
        self, x: Any, visited: set[int], prefix: list[Any] | None = None
    ) -> Iterator[tuple[list[Any], dict[str, Any]]]:
        """A depth-first search through to reveal all objects in the object space."""
        if prefix is None:
            prefix = []
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
                if "id" not in x:
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
        Constructor.add("!include", self.__resolve_include)

        # The !splice tag is similar to !include, but merges the
        # referenced document into the parent node.
        Constructor.add("!splice", self.__resolve_splice)

        # The !path constructor
        Constructor.add("!path", self.__resolve_path)

    def __load_fragment(self, filename: Path) -> YAMLFragment:
        """Load YAML Fragment, with caching. Fragments do not only originate
        in .yml files, but also pages can be given.

        """
        filename = filename.absolute()
        if filename in self.__cache:
            return self.__cache[filename]

        if filename.suffix in {".yml", ".myml"}:
            # Load data file
            if not filename.exists():
                # Fallback to SRAtic provided files
                filename = Path(__file__).parent / "data" / filename.name
            with Path(filename).open() as stream:
                try:
                    if filename.suffix == ".myml":
                        data = list(yaml.load_all(stream, Loader=yaml.Loader))
                    else:
                        data = yaml.load(stream, Loader=yaml.Loader)
                except Exception:
                    logging.error("Error in %s", filename)
                    raise

            fragment = YAMLFragment(self.__config, filename, data)
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

                    try:
                        data = yaml.load(io.StringIO("".join(text)), Loader=yaml.Loader)
                    except Exception:
                        logging.error("Error in %s", filename)
                        raise

                    fragment = YAMLFragment(self.__config, filename, data)
                else:
                    fragment = YAMLFragment(self.__config, filename, {})
                ### Page Content
                fragment.data["page-body"] = fd.read()

            # Pages also read in their directory 'variables' file, implicitly
            dirname = Path(filename).parent
            dir_file = dirname / "variables.yml"
            if dir_file.exists():
                if type(fragment.data) is list:
                    fragment.data.append(
                        Constructor("!splice", dir_file, self.__resolve_splice)
                    )
                elif type(fragment.data) is dict:
                    fragment.data[object()] = Constructor(
                        "!splice", dir_file, self.__resolve_splice
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

        ret = YAMLFragment(self.__config, filename, {})
        ret.data = [Constructor("!include", filename, self.__resolve_include)]
        again = True
        while again:
            ret, again = self.__resolve(ret, ret.data)

        ret.data = ret.data[0]
        if ret.data is None:
            ret.data = {}
        return ret

    ### Resolve Constructors
    def __resolve_splice(self, fragment: YAMLFragment, ctx: Constructor) -> Splice:
        fn = ctx.origin.parent / ctx.value if ctx.origin else Path(ctx.value)
        if "*" in fn.name:
            fns = fn.parent.glob(fn.name)
        else:
            fns = [fn]

        splice_data: dict | list | None = None
        for fn in fns:
            other = self.__load_fragment(fn)
            fragment.sources.update(other.sources)
            if splice_data is None:
                splice_data = other.data.copy()
            elif type(other.data) is dict:
                assert type(splice_data) is dict, (
                    f"Splicing {fn}: Type mismatch ({type(splice_data)} != {type(other.data)})"
                )
                splice_data.update(other.data)
            elif type(other.data) is list:
                assert type(splice_data) is list, (
                    f"Splicing {fn}: Type mismatch ({type(splice_data)} != {type(other.data)})"
                )
                splice_data += other.data
            else:
                assert False, f"Splicing {fn}: Unexpected type: {type(other.data)}"

        assert splice_data is not None, f"Splicing {fn}: No data"
        return Splice(splice_data, again=True)

    def __resolve_include(self, fragment: YAMLFragment, ctx: Constructor) -> Replace:
        fn = ctx.origin.parent / ctx.value if ctx.origin else Path(ctx.value)
        other = self.__load_fragment(fn)
        fragment.sources.update(other.sources)
        return Replace(other.data, again=True)

    def __resolve_path(self, fragment: YAMLFragment, ctx: Constructor) -> Replace:
        if Path(ctx.value).is_absolute():
            return Replace(ctx.value)
        assert ctx.origin, "Path not absolute and no origin available"
        path = (Path(ctx.origin).parent / ctx.value).resolve()
        return Replace("/" + path.relative_to(Path.cwd()).as_posix())

    def __resolve(self, fragment: YAMLFragment, x: Any) -> tuple[YAMLFragment, bool]:
        """One depth-first search, to resolve constructors. Returns true, if
        this process has to be repeated.

        """
        again = False
        if type(x) is list:
            for idx, value in enumerate(x):
                if isinstance(value, Constructor):
                    res = value(fragment)
                    if isinstance(res, Replace):
                        x[idx] = res.value
                    elif isinstance(res, Splice):
                        assert type(res.value) is list
                        x[idx : idx + 1] = res.value
                    if res.again:
                        again = True

                # Recursion
                if type(value) in (list, dict):
                    _, change = self.__resolve(fragment, value)
                    again = change or again
        elif type(x) is dict:
            for key, value in list(x.items()):
                if isinstance(value, Constructor):
                    res = value(fragment)
                    if isinstance(res, Replace):
                        x[key] = res.value
                    elif isinstance(res, Splice):
                        assert type(res.value) is dict
                        x.update(res.value)
                        del x[key]
                    if res.again:
                        again = True

                # Recursion
                if type(value) in (list, dict):
                    _, change = self.__resolve(fragment, value)
                    again = change or again
        return fragment, again

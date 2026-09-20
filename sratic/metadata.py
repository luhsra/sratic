"""A safe PyYAML parser supporting file inclusion and collection splicing."""

import copy
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

import yaml
from yaml.constructor import ConstructorError


@dataclass
class YAMLFragment:
    """Represents a parsed YAML fragment with dependencies."""

    path: Path
    data: Any
    sources: set[Path] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.sources.add(self.path)

    def merge(self, other: "YAMLFragment"):
        self.sources.update(other.sources)
        assert type(self.data) == type(other.data)
        if type(other.data) is dict:
            self.data.update(other.data)
        elif type(other.data) is list:
            self.data.extend(other.data)
        else:
            raise TypeError(f"Invalid merge: {type(self.data)} <- {type(other.data)}")

    def objects(self) -> Iterator[dict[str, Any]]:
        return self._objects(self.data, set())

    def _objects(self, x: Any, visited: set[int]) -> Iterator[dict[str, Any]]:
        if id(x) in visited:
            return
        visited.add(id(x))

        if type(x) is list:
            for v in x:
                yield from self._objects(v, visited)
        elif type(x) is dict:
            if "id" in x or "type" in x:
                if "id" not in x:
                    x["id"] = f"{self.path}-{id(x)}"
                yield x
            for v in x.values():
                yield from self._objects(v, visited)


class YAMLError(ValueError):
    """Raised when loading or resolving YAML fails."""


class FrontmatterError(YAMLError):
    """Raised when the front matter is invalid."""


class IncludeCycleError(YAMLError):
    """Raised when an include/splice chain refers back to an active file."""


class SpliceTypeError(YAMLError):
    """Raised when the spliced value does not match its parent collection."""


@dataclass(frozen=True)
class _Splice:
    value: Any
    source: Path


def _resolve_splices(value: Any, path: Path, visited: set[int]) -> Any:
    if isinstance(value, _Splice):
        raise SpliceTypeError(f"splice without parent {path}")

    if not isinstance(value, (list, dict)) or id(value) in visited:
        return value
    visited.add(id(value))

    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, _Splice):
                if not isinstance(item.value, list):
                    raise SpliceTypeError(
                        f"cannot splice {type(item.value).__name__} into {type(value).__name__} {path}: {item.source}"
                    )
                result.extend(item.value)
            else:
                result.append(_resolve_splices(item, path, visited))
        value[:] = result
        return value

    for key, item in list(value.items()):
        if isinstance(item, _Splice):
            if not isinstance(item.value, dict):
                raise SpliceTypeError(
                    f"cannot splice {type(item.value).__name__} into {type(value).__name__} {path}: {item.source}"
                )
            value.update(item.value)
            if key not in item.value:
                del value[key]
        elif value.get(key) is item:
            value[key] = _resolve_splices(item, path, visited)
    return value


class YAMLLoader(yaml.SafeLoader):
    parser: "YAMLParser"
    path: Path
    sources: set[Path]

    def construct_any(self, node: yaml.Node) -> Any:
        if isinstance(node, yaml.SequenceNode):
            return self.construct_sequence(node, deep=True)
        if isinstance(node, yaml.MappingNode):
            return self.construct_mapping(node, deep=True)
        if isinstance(node, yaml.ScalarNode):
            return self.construct_scalar(node)
        raise TypeError(f"Invalid YAML: {type(node)}")

    def construct_path(self, node: yaml.Node) -> Path:
        path = self.construct_scalar(node)
        if not isinstance(path, str) or not path:
            raise TypeError("expect a non-empty filename")
        return self.path.parent / path

    def add_source(self, *paths: Path) -> None:
        self.sources.update(paths)


def _add_constructor(
    loader: type[YAMLLoader],
    tag: str,
    constructor: Callable[[YAMLLoader, yaml.Node], Any],
) -> None:
    def wrapper(loader, node, constructor=constructor, tag=tag):
        try:
            return constructor(loader, node)
        except ConstructorError as error:
            if "unconstructable recursive node" not in str(error):
                raise
            raise IncludeCycleError(
                f"YAML include/splice cycle at {loader.path}"
            ) from error
        except Exception as error:
            raise type(error)(f"{tag}: {error}") from error

    loader.add_constructor(tag, wrapper)


def _constructor_relpath(loader: YAMLLoader, node: yaml.Node) -> str:
    value = loader.construct_scalar(node)
    path = Path(value)
    if path.is_absolute():
        return value
    path = (loader.path.parent / path).resolve()
    return "/" + path.relative_to(Path.cwd()).as_posix()


def _construct_include(loader: YAMLLoader, node: yaml.Node) -> Any:
    path = loader.construct_path(node)
    loader.add_source(path)
    fragment = loader.parser.load_file(path)
    loader.add_source(*fragment.sources)
    return fragment.data


def _construct_splice(loader: YAMLLoader, node: yaml.Node) -> _Splice:
    referenced = loader.construct_path(node)
    paths = (
        list(referenced.parent.glob(referenced.name))
        if "*" in referenced.name
        else [referenced]
    )
    if not paths:
        raise SpliceTypeError(f"Splicing {referenced}: No data")
    loader.add_source(*paths)

    result: YAMLFragment | None = None
    for path in paths:
        fragment = loader.parser.load_file(path)
        if result is None:
            result = fragment
        else:
            result.merge(fragment)
        loader.add_source(*fragment.sources)

    assert result is not None
    return _Splice(result.data, referenced)


class YAMLParser:
    """Load YAML files with an instance-local parsed-file cache.

    Create a new parser (or call :meth:`clear_cache`) when files on disk may
    have changed. Returned values are copies, so callers cannot mutate cached
    values or cause two include sites to share mutable state.
    """

    def __init__(
        self,
        constructors: dict[str, Callable[[YAMLLoader, yaml.Node], Any]] | None = None,
    ) -> None:
        # Memoize parsed YAML fragments
        self._cache: dict[Path, YAMLFragment] = {}
        # Track active paths to detect circles
        self._active: list[Path] = []

        # Constructors are bound to the class -> contain instance-local state
        class _SubLoader(YAMLLoader):
            pass

        _add_constructor(_SubLoader, "!path", _constructor_relpath)
        _add_constructor(_SubLoader, "!include", _construct_include)
        _add_constructor(_SubLoader, "!splice", _construct_splice)

        if constructors is not None:
            for tag, constructor in constructors.items():
                _add_constructor(_SubLoader, tag, constructor)
        self._loader = _SubLoader

    def load_file(self, path: Path) -> YAMLFragment:
        """Load *path*, resolving all includes and splices recursively."""
        requested_path = Path(path)
        resolved_path = requested_path.resolve()

        if resolved_path in self._cache:
            result = copy.deepcopy(self._cache[resolved_path])
            result.path = requested_path
            result.sources.add(requested_path)
            return result

        if resolved_path in self._active:
            cycle_start = self._active.index(resolved_path)
            cycle = self._active[cycle_start:] + [resolved_path]
            rendered = " -> ".join(str(item) for item in cycle)
            raise IncludeCycleError(f"YAML include/splice cycle: {rendered}")

        self._active.append(resolved_path)
        try:
            result = self._parse_file(path)
            self._cache[resolved_path] = result
            result = copy.deepcopy(result)
            result.path = requested_path
            result.sources.add(requested_path)
            return result
        except YAMLError:
            raise
        except Exception as error:
            chain = " -> ".join(str(item) for item in self._active)
            raise YAMLError(f"{error} (source chain: {chain})") from error
        finally:
            self._active.pop()

    def _parse_file(self, path: Path) -> YAMLFragment:
        resolved_path = path.resolve()

        with resolved_path.open("r") as stream:
            if resolved_path.suffix in {".yml", ".yaml"}:
                result = self._load_stream(stream, resolved_path)
            elif resolved_path.suffix == ".myml":
                result = self._load_stream(stream, resolved_path, multiple=True)
            elif stream.readline().rstrip() == "---":
                text = stream.read()
                end = re.search(r"^---\s*$", text, re.MULTILINE)
                if not end:
                    raise FrontmatterError("Unterminated YAML front matter")

                result = self._load_stream(text[: end.start()], resolved_path)
                if not isinstance(result.data, dict):
                    raise FrontmatterError("Page YAML front matter must be a mapping")
                result.data["page-body"] = text[end.end() :].lstrip()
            else:
                stream.seek(0)
                result = YAMLFragment(resolved_path, {"page-body": stream.read()})

        is_page = resolved_path.suffix not in {".yml", ".yaml", ".myml"}
        variables = resolved_path.parent / "variables.yml"
        if is_page and variables.exists():
            result.merge(self.load_file(variables))
        return result

    def _load_stream(
        self, stream: TextIO | str, path: Path, multiple: bool = False
    ) -> YAMLFragment:
        loader = self._loader(stream)
        loader.parser = self
        loader.path = path
        loader.sources = {path}
        try:
            if multiple:
                value = []
                while loader.check_data():
                    value.append(loader.get_data())
            else:
                value = loader.get_single_data()
            if value is None:
                value = {}
            result = YAMLFragment(path, value, loader.sources)
            _resolve_splices(result.data, path, set())
            return result
        finally:
            loader.dispose()

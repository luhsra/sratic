import io
import logging
import operator
import re
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, nodes
from jinja2.ext import Extension
from jinja2.parser import Parser


class YamlExtension(Extension):
    def __init__(self, environment: Environment) -> None:
        # a set of names that trigger the extension.
        self.tags = {"yaml", "box"}
        super().__init__(environment)
        self.environment.filters.update(
            {
                "yaml": self._parse_yaml,
                "box": self._parse_box,
            }
        )

    def parse(self, parser: Parser) -> list[nodes.Node]:
        tag = next(parser.stream)
        lineno = tag.lineno

        parser.stream.expect("name:as")
        target = parser.parse_assign_target()

        body = parser.parse_statements(("name:end" + str(tag),), drop_needle=True)
        macro_name = "_" + parser.free_identifier().name

        return [
            nodes.Macro(macro_name, [], [], body).set_lineno(lineno),
            nodes.Assign(
                target,
                nodes.Filter(
                    nodes.Call(
                        nodes.Name(macro_name, "load").set_lineno(lineno),
                        [],
                        [],
                        None,
                        None,
                    ).set_lineno(lineno),
                    str(tag),
                    [nodes.Const(str(target.name))],
                    [],
                    None,
                    None,
                ).set_lineno(lineno),
            ).set_lineno(lineno),
        ]

    def _parse_yaml(self, text: str, *args):
        return yaml.load(io.StringIO(text), Loader=yaml.Loader)

    def _parse_box(self, text: str, boxname: str) -> str:
        globals: dict = self.environment.globals
        globals["page"][boxname] = text
        return text


class SRAticEnvironment(Environment):
    def __init__(self, template_paths: list[Path]) -> None:
        Environment.__init__(
            self,
            trim_blocks=True,
            lstrip_blocks=True,
            loader=FileSystemLoader(
                [*template_paths, Path(__file__).parent / "templates"]
            ),
            extensions=[YamlExtension],
        )
        globals: dict = self.globals
        self.filters["expand"] = self.expand
        self.filters["warn"] = self.__warn
        self.filters["match"] = self.__match
        self.filters["search"] = self.__search

        self.filters["shorten"] = self.__shorten
        globals["str"] = repr
        globals["wrap_list"] = self.wrap_list
        globals["operator"] = operator

        # This dict must never be overriden, the reference must be
        # kept intact at all times. It can only be cleared on each new page.
        globals["page"] = {}

        # A list of all copied and known assets
        self.assets: list[str] = []
        globals["__asset"] = self.__asset

    def find_template(self, name: str) -> str | None:
        """Use the Jinja2 Searchpath to find a given template."""
        assert self.loader is not None
        assert isinstance(self.loader, FileSystemLoader)
        for searchpath in self.loader.searchpath:
            filename = Path(searchpath) / name
            if filename.exists():
                return str(filename)

    def expand(self, text: str, **kwargs) -> str:
        # Some SRAtic specific markups
        # 1. Internal links

        def internal_link(m: re.Match) -> str:
            obj = m.group(1)
            if m.group(2):
                link_attr = m.group(2)[1:]  # Strip the dot
            else:
                link_attr = None
            if m.group(3) and m.group(3)[0] == ".":
                title_attr = m.group(3)[1:]
                title = None
            else:
                title = m.group(3)
                title_attr = None
            ret = f"{{{{ nav.link({obj!r}, title={title!r}, link_attr={link_attr!r}, title_attr={title_attr!r}) }}}}"
            # logging.info(ret)

            return ret

        # [[OBJECT(.ATTR)?]([TITLE or .TITLE_ATTR])?]
        text = re.sub(
            r"\[\[([^\[\].]*?)((?:\.[^\[\]]*?)?)\](?:\[([^\[\]].*?)\])?\]",
            internal_link,
            text,
        )

        # 2. We always include a few default jinja templates modules
        prefix_text = "{% set R = page.relative_root %}\n"
        globals: dict = self.globals
        for name, jinja_filename in (
            globals["data"]["site"].get("default_templates", {}).items()
        ):
            prefix_text += f"{{% import '{jinja_filename}' as {name} %}}\n"

        template = self.from_string(prefix_text + text)
        return template.render(**kwargs)

    def wrap_list(self, elem: Any) -> list[Any]:
        if type(elem) is self.undefined:
            return []
        if type(elem) is list:
            return elem
        return [elem]

    def __warn(self, text: str, **kwargs) -> str:
        logging.warning(text, **kwargs)
        return text

    def __shorten(self, elem: str, count: int) -> str:
        assert type(elem) is str
        if len(elem) < count:
            return elem
        return elem[: count - 1] + "&hellip;"

    def __regex(
        self,
        value: str = "",
        pattern: str = "",
        ignorecase: bool = False,
        match_type: str = "search",
    ) -> bool:
        if ignorecase:
            flags = re.IGNORECASE
        else:
            flags = 0
        _re = re.compile(pattern, flags=flags)
        return bool(getattr(_re, match_type)(str(value)))

    def __match(self, value: str, pattern: str = "", ignorecase: bool = False) -> bool:
        return self.__regex(value, pattern, ignorecase, "match")

    def __search(self, value: str, pattern: str = "", ignorecase: bool = False) -> bool:
        return self.__regex(value, pattern, ignorecase, "search")

    def __asset(self, name: str) -> str:
        found = None
        for asset in self.assets:
            if Path(asset).name == name:
                assert found is None, f"Asset {name} is unambigous ({found},{asset})"
                found = asset
        assert found, f"Could not find asset: {name}"
        return found

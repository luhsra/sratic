import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from sratic.__main__ import Generator
from sratic.bibliography import resolve_load_bibtex
from sratic.metadata import (
    FrontmatterError,
    IncludeCycleError,
    YAMLError,
    YAMLLoader,
    YAMLParser,
    _Splice,
)
from sratic.objects import resolve_load_csv


class MetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(temporary_directory.cleanup)
        self.directory = Path(temporary_directory.name)
        self.factory = YAMLParser(None)

    def write(self, filename: str, content: str) -> Path:
        path = self.directory / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def application_factory(self) -> YAMLParser:
        generator = Generator.__new__(Generator)
        return YAMLParser(
            {
                "!markdown": generator.resolve_markdown_constructor,
                "!csv": resolve_load_csv,
                "!bibtex": resolve_load_bibtex,
            },
        )

    def test_local_handlers(self) -> None:
        path = self.write("root.yml", "!custom value\n")
        handlers: dict = {"!custom": lambda loader, value: "first"}
        first = YAMLParser(handlers)
        second = YAMLParser(
            {"!custom": lambda loader, value: "second"},
        )
        handlers["!custom"] = lambda loader, value: "changed"
        self.assertEqual(first.load_file(path).data, "first")
        self.assertEqual(second.load_file(path).data, "second")
        self.assertEqual(first.load_file(path).data, "first")
        with self.assertRaisesRegex(Exception, "!custom"):
            self.factory.load_file(path)
        for loader in (yaml.SafeLoader, yaml.Loader):
            self.assertNotIn("!custom", loader.yaml_constructors)
            self.assertNotIn("!include", loader.yaml_constructors)

    def test_handler_not_deepcopied(self) -> None:
        class Handler:
            def __init__(self):
                self.calls = 0

            def __deepcopy__(self, memo):
                raise AssertionError("Handler owner must not be copied")

            def resolve(self, loader, node):
                self.calls += 1
                return loader.construct_any(node)

        handler = Handler()
        factory = YAMLParser({"!custom": handler.resolve})
        root = self.write("root.yml", "[!include child.yml, !include child.yml]\n")
        self.write("child.yml", "!custom [value]\n")
        self.assertEqual(factory.load_file(root).data, [["value"], ["value"]])
        self.assertEqual(factory.load_file(root).data, [["value"], ["value"]])
        self.assertEqual(handler.calls, 1)

    def test_and_independent_includes(self) -> None:
        root = self.write("root.yml", "[!include child.yml, !include child.yml]\n")
        child = self.write("child.yml", "nested: [!splice values.yml]\n")
        values = self.write("values.yml", "[one, two]\n")
        with patch.object(
            self.factory, "_load_stream", wraps=self.factory._load_stream
        ) as parse:
            first = self.factory.load_file(root)
            first.data[0]["nested"].append("changed")
            first.sources.clear()
            self.assertEqual(first.data[1], {"nested": ["one", "two"]})
            second = self.factory.load_file(root)
            self.assertEqual(
                second.data,
                [
                    {"nested": ["one", "two"]},
                    {"nested": ["one", "two"]},
                ],
            )
            self.assertEqual(second.sources, {root, child, values})
            self.assertEqual(parse.call_count, 3)

    def test_preserve_relative_path(self) -> None:
        root = self.write("page.md", "---\ntitle: Page\n---\nBody\n")
        relative = root.relative_to(Path.cwd())
        fragment = self.factory.load_file(relative)
        self.assertEqual(fragment.path, relative)
        self.assertIn(root, fragment.sources)
        self.assertIn(relative, fragment.sources)

    def test_splice_mapping_precedence(self) -> None:
        root = self.write(
            "root.yml",
            "before: original\nmerge: !splice child.yml\n"
            "after: original\ntagged: !include tagged.yml\n",
        )
        self.write(
            "child.yml",
            "before: spliced\nafter: spliced\ntagged: spliced\nmerge: spliced\n",
        )
        self.write("tagged.yml", "included\n")
        self.assertEqual(
            self.factory.load_file(root).data,
            {
                "before": "spliced",
                "after": "spliced",
                "tagged": "spliced",
                "merge": "spliced",
            },
        )

    def test_splice_wildcard_order(self) -> None:
        root = self.write("root.yml", "values: [!splice '*.yml']\n")
        first = self.write("one.yml", "[one]\n")
        second = self.write("two.yml", "[two]\n")
        with patch.object(Path, "glob", return_value=iter([second, first])):
            fragment = self.factory.load_file(root)
        self.assertEqual(fragment.data["values"], ["two", "one"])

    def test_nested_origins(self) -> None:
        seen = []

        def identity(loader: YAMLLoader, node):
            seen.append(loader.path)
            return loader.construct_any(node)

        factory = YAMLParser({"!identity": identity})
        root = self.write("root.yml", "!include nested/child.yml\n")
        child = self.write("nested/child.yml", "!identity {value: !identity hello}\n")
        fragment = factory.load_file(root)
        self.assertEqual(fragment.data, {"value": "hello"})
        self.assertEqual(seen, [child, child])
        self.assertEqual(fragment.sources, {root, child})

    def test_custom_splice_resolved(self) -> None:
        factory = YAMLParser(
            {
                "!custom": lambda loader, value: _Splice(["hello"], Path("child.yml")),
            },
        )
        root = self.write("root.yml", "[!custom ignored, after]\n")
        self.write("child.yml", "hello\n")
        self.assertEqual(factory.load_file(root).data, ["hello", "after"])

    def test_alias_to_tag_resolves_once(self) -> None:
        calls = []

        def handler(loader, node):
            value = loader.construct_any(node)
            calls.append(value)
            return {"value": value}

        factory = YAMLParser({"!custom": handler})
        root = self.write("root.yml", "[&tag !custom hello, *tag]\n")
        result = factory.load_file(root).data
        self.assertEqual(calls, ["hello"])
        self.assertIs(result[0], result[1])
        self.assertEqual(result[0], {"value": "hello"})

    def test_alias_to_container_resolves_once(self) -> None:
        root = self.write("root.yml", "[&items [!splice child.yml], *items]\n")
        self.write("child.yml", "[one, two]\n")
        result = self.factory.load_file(root).data
        self.assertEqual(result, [["one", "two"], ["one", "two"]])
        self.assertIs(result[0], result[1])

    def test_recursive_list_alias(self) -> None:
        root = self.write("root.yml", "&items [*items, !include child.yml]\n")
        self.write("child.yml", "hello\n")
        first = self.factory.load_file(root).data
        second = self.factory.load_file(root).data
        self.assertIs(first[0], first)
        self.assertIs(second[0], second)
        self.assertIsNot(first, second)
        self.assertEqual(first[1], "hello")

    def test_recursive_mapping_alias(self) -> None:
        root = self.write(
            "root.yml", "&item {self: *item, value: !include child.yml}\n"
        )
        self.write("child.yml", "hello\n")
        fragment = self.factory.load_file(root)
        self.assertIs(fragment.data["self"], fragment.data)
        self.assertEqual(fragment.data["value"], "hello")
        self.assertEqual(list(fragment.objects()), [])

    def test_recursive_alias_rejected(self) -> None:
        for content in ("&tag !custom [*tag]\n", "&tag !custom {self: *tag}\n"):
            with self.subTest(content=content):
                root = self.write("recursive.yml", content)
                factory = YAMLParser(
                    {"!custom": lambda loader, node: loader.construct_any(node)},
                )
                with self.assertRaisesRegex(
                    IncludeCycleError, "YAML include/splice cycle"
                ):
                    factory.load_file(root)

    def test_include_cycle_chain(self) -> None:
        root = self.write("root.yml", "!include child.yml\n")
        child = self.write("child.yml", "!include ./nested/../root.yml\n")
        self.directory.joinpath("nested").mkdir()
        with self.assertRaises(IncludeCycleError) as error:
            self.factory.load_file(root)
        self.assertIn("YAML include/splice cycle", str(error.exception))
        self.assertIn(f"{root} -> {child} -> {root}", str(error.exception))
        good = self.write("good.yml", "ok\n")
        self.assertEqual(self.factory.load_file(good).data, "ok")

    def test_symlink_cycle(self) -> None:
        root = self.write("root.yml", "!include alias.yml\n")
        self.directory.joinpath("alias.yml").symlink_to(root)
        with self.assertRaisesRegex(IncludeCycleError, "YAML include/splice cycle"):
            self.factory.load_file(root)

    def test_splice_cycle(self) -> None:
        root = self.write("root.yml", "[!splice child.yml]\n")
        self.write("child.yml", "[!splice root.yml]\n")
        with self.assertRaisesRegex(IncludeCycleError, "YAML include/splice cycle"):
            self.factory.load_file(root)

    def test_parse_error_sources(self) -> None:
        root = self.write("root.yml", "!include child.yml\n")
        child = self.write("child.yml", "invalid: [\n")
        with self.assertRaises(YAMLError) as error:
            self.factory.load_file(root)
        self.assertIn(f"{root} -> {child}", str(error.exception))
        self.assertIsInstance(error.exception.__cause__, ValueError)

    def test_handler_error_sources(self) -> None:
        def fail(fragment, ctx):
            raise ValueError("handler failed")

        factory = YAMLParser({"!fail": fail})
        root = self.write("root.yml", "!include child.yml\n")
        child = self.write("child.yml", "!fail value\n")
        with self.assertRaises(YAMLError) as error:
            factory.load_file(root)
        self.assertIn("handler failed", str(error.exception))
        self.assertIn(f"{root} -> {child}", str(error.exception))

    def test_missing_include_sources(self) -> None:
        root = self.write("root.yml", "!include missing.yml\n")
        with self.assertRaises(YAMLError) as error:
            self.factory.load_file(root)
        self.assertIn(
            f"{root} -> {self.directory / 'missing.yml'}", str(error.exception)
        )

    def test_reject_python_tags(self) -> None:
        root = self.write("root.yml", "!!python/object/apply:builtins.str [unsafe]\n")
        with self.assertRaisesRegex(YAMLError, "could not determine a constructor"):
            self.factory.load_file(root)

    def test_unknown_tag(self) -> None:
        root = self.write("root.yml", "!unknown value\n")
        with self.assertRaisesRegex(YAMLError, "!unknown"):
            self.factory.load_file(root)

    def test_splice_type_errors(self) -> None:
        cases = [
            ("[!splice child.yml]\n", "{key: value}\n", "dict into list"),
            ("{merge: !splice child.yml}\n", "[value]\n", "list into dict"),
            ("[!splice child.yml]\n", "scalar\n", "str into list"),
        ]
        for index, (content, included, message) in enumerate(cases):
            with self.subTest(message=message):
                root = self.write(f"case{index}/root.yml", content)
                self.write(f"case{index}/child.yml", included)
                with self.assertRaisesRegex(YAMLError, message):
                    self.factory.load_file(root)

    def test_empty_wildcard(self) -> None:
        root = self.write("root.yml", "[!splice 'missing/*.yml']\n")
        with self.assertRaisesRegex(YAMLError, "No data"):
            self.factory.load_file(root)

    def test_wildcard_last_file_wins(self) -> None:
        root = self.write("root.yml", "merge: !splice '*.yml'\n")
        first = self.write("first.yml", "value: first\n")
        second = self.write("second.yml", "value: second\n")
        with patch.object(Path, "glob", return_value=iter([second, first])):
            self.assertEqual(self.factory.load_file(root).data, {"value": "first"})

    def test_path(self) -> None:
        root = self.write("root.yml", "value: !path assets/logo.svg\n")
        expected = "/" + (
            (self.directory / "assets" / "logo.svg").relative_to(Path.cwd()).as_posix()
        )
        self.assertEqual(self.factory.load_file(root).data["value"], expected)

    def test_markdown(self) -> None:
        root = self.write("root.yml", 'value: !markdown "**bold**"\n')
        self.assertEqual(
            self.application_factory().load_file(root).data["value"],
            "<p><strong>bold</strong></p>",
        )

    def test_csv(self) -> None:
        root = self.write("root.yml", 'value: !csv [people.csv, {delimiter: ";"}]\n')
        source = self.write("people.csv", "name;role\nAda;researcher\n")
        fragment = self.application_factory().load_file(root)
        self.assertEqual(
            fragment.data["value"], [{"name": "Ada", "role": "researcher"}]
        )
        self.assertIn(source, fragment.sources)

    def test_bibtex(self) -> None:
        output = {
            "example": {
                "entry_type": "article",
                "id": "example",
                "authors": [{"first_name": "Ada", "last_name": "Lovelace"}],
                "title": "Computing",
            }
        }
        source = self.write("references.bib", "@article{example}\n")
        root = self.write("root.yml", "value: !bibtex references.bib\n")
        with (
            patch(
                "sratic.bibliography.get_bib2json_path",
                return_value="/mock/bib2json",
            ),
            patch(
                "sratic.bibliography.subprocess.run",
                return_value=SimpleNamespace(stdout=json.dumps(output).encode()),
            ) as run,
        ):
            fragment = self.application_factory().load_file(root)

        entry = fragment.data["value"]["entries"][0]
        self.assertEqual(entry["id"], "bib:example")
        self.assertEqual(entry["authors"], ["Ada Lovelace"])
        self.assertEqual(entry["type"], "bibtex")
        self.assertIn(source, fragment.sources)
        run.assert_called_once_with(
            ["/mock/bib2json", source],
            check=True,
            capture_output=True,
        )

    def test_invalid_application_tags(self) -> None:
        for tag, value in (
            ("!csv", "{filename: people.csv}"),
            ("!bibtex", "[references.bib]"),
        ):
            with self.subTest(tag=tag):
                root = self.write("root.yml", f"value: {tag} {value}\n")
                with self.assertRaisesRegex(ValueError, f"Invalid value for {tag}"):
                    self.application_factory().load_file(root)

    def test_multidocument_yaml(self) -> None:
        root = self.write("root.myml", "!include child.yml\n---\n{value: second}\n")
        self.write("child.yml", "{value: first}\n")
        self.assertEqual(
            self.factory.load_file(root).data,
            [
                {"value": "first"},
                {"value": "second"},
            ],
        )

    def test_empty_yaml(self) -> None:
        root = self.write("root.yml", "")
        self.assertEqual(self.factory.load_file(root).data, {})

    def test_frontmatter_and_variables(self) -> None:
        root = self.write("page.md", "---\ntitle: page\n---\nPage body\n")
        variables = self.write(
            "variables.yml", "title: directory\nvalue: !include child.yml\n"
        )
        child = self.write("child.yml", "included\n")
        fragment = self.factory.load_file(root)
        self.assertEqual(
            fragment.data,
            {
                "title": "directory",
                "value": "included",
                "page-body": "Page body\n",
            },
        )
        self.assertEqual(fragment.sources, {root, variables, child})

    def test_without_frontmatter(self) -> None:
        root = self.write("page.md", "Entire page body\n")
        self.assertEqual(
            self.factory.load_file(root).data,
            {"page-body": "Entire page body\n"},
        )

    def test_empty_frontmatter(self) -> None:
        root = self.write("page.md", "---\n---\nBody\n")
        self.assertEqual(self.factory.load_file(root).data, {"page-body": "Body\n"})

    def test_unterminated_frontmatter(self) -> None:
        root = self.write("page.md", "---\ntitle: unfinished\n")
        with self.assertRaisesRegex(FrontmatterError, "Unterminated YAML front matter"):
            self.factory.load_file(root)

    def test_non_mapping_frontmatter(self) -> None:
        root = self.write("page.md", "---\n[list]\n---\nBody\n")
        with self.assertRaisesRegex(FrontmatterError, "must be a mapping"):
            self.factory.load_file(root)


if __name__ == "__main__":
    unittest.main()

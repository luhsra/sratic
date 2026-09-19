import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sratic.__main__ import Generator
from sratic.metadata import Constructor, YAMLDataFactory, YAMLFragment


class YAMLTagTests(unittest.TestCase):
    def setUp(self) -> None:
        generator = Generator.__new__(Generator)  # No constructor call
        Constructor.add("!markdown", generator.resolve_markdown_constructor)
        self.factory = YAMLDataFactory(None)
        temporary_directory = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(temporary_directory.cleanup)
        self.directory = Path(temporary_directory.name)

    def load_yaml(
        self, yaml_text: str, files: dict[str, str] | None = None
    ) -> YAMLFragment:
        for relative_path, content in (files or {}).items():
            path = self.directory / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

        root = self.directory / "root.yml"
        root.write_text(yaml_text)
        return self.factory.load_file(root)

    def test_include(self) -> None:
        fragment = self.load_yaml(
            "value: !include included.yml\n",
            {"included.yml": "name: included\n"},
        )

        self.assertEqual(fragment.data, {"value": {"name": "included"}})
        self.assertIn((self.directory / "included.yml").absolute(), fragment.sources)

    def test_splice_list(self) -> None:
        fragment = self.load_yaml(
            "values: [before, !splice values.yml, after]\n",
            {"values.yml": "[one, two]\n"},
        )

        self.assertEqual(fragment.data["values"], ["before", "one", "two", "after"])

    def test_splice_mapping(self) -> None:
        fragment = self.load_yaml(
            "values:\n  original: true\n  merge: !splice values.yml\n",
            {"values.yml": "added: true\n"},
        )

        self.assertEqual(fragment.data["values"], {"original": True, "added": True})

    def test_splice_nested(self) -> None:
        fragment = self.load_yaml(
            "values: [!splice outer.yml]\n",
            {
                "outer.yml": "[outer, !splice inner.yml]\n",
                "inner.yml": "[inner]\n",
            },
        )

        self.assertEqual(fragment.data["values"], ["outer", "inner"])

    def test_splice_wildcard(self) -> None:
        fragment = self.load_yaml(
            "values: [before, !splice 'parts/*.yml', after]\n",
            {
                "parts/one.yml": "[one]\n",
                "parts/two.yml": "[two]\n",
            },
        )

        self.assertEqual(fragment.data["values"][0], "before")
        self.assertCountEqual(fragment.data["values"][1:-1], ["one", "two"])
        self.assertEqual(fragment.data["values"][-1], "after")

    def test_path(self) -> None:
        fragment = self.load_yaml("value: !path assets/logo.svg\n")
        expected = "/" + (
            (self.directory / "assets" / "logo.svg").relative_to(Path.cwd()).as_posix()
        )

        self.assertEqual(fragment.data["value"], expected)

    def test_markdown(self) -> None:
        fragment = self.load_yaml('value: !markdown "**bold**"\n')

        self.assertEqual(fragment.data["value"], "<p><strong>bold</strong></p>")

    def test_csv(self) -> None:
        fragment = self.load_yaml(
            'value: !csv [people.csv, {delimiter: ";"}]\n',
            {"people.csv": "name;role\nAda;researcher\n"},
        )

        self.assertEqual(
            fragment.data["value"], [{"name": "Ada", "role": "researcher"}]
        )
        self.assertIn((self.directory / "people.csv").absolute(), fragment.sources)

    def test_csv_invalid(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid value for !csv"):
            self.load_yaml("value: !csv {filename: people.csv}\n")

    def test_bibtex(self) -> None:
        bib2json_output = {
            "example": {
                "entry_type": "article",
                "id": "example",
                "authors": [{"first_name": "Ada", "last_name": "Lovelace"}],
                "title": "Computing",
            }
        }
        with (
            patch(
                "sratic.bibliography.get_bib2json_path",
                return_value="/mock/bib2json",
            ),
            patch(
                "sratic.bibliography.subprocess.run",
                return_value=SimpleNamespace(
                    stdout=json.dumps(bib2json_output).encode()
                ),
            ) as run,
        ):
            fragment = self.load_yaml(
                "value: !bibtex references.bib\n",
                {"references.bib": "@article{example}\n"},
            )

        entry = fragment.data["value"]["entries"][0]
        self.assertEqual(entry["id"], "bib:example")
        self.assertEqual(entry["authors"], ["Ada Lovelace"])
        self.assertEqual(entry["type"], "bibtex")
        self.assertIn((self.directory / "references.bib").absolute(), fragment.sources)
        run.assert_called_once_with(
            ["/mock/bib2json", (self.directory / "references.bib").absolute()],
            check=True,
            capture_output=True,
        )

    def test_bibtex_invalid(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid value for !bibtex"):
            self.load_yaml("value: !bibtex [references.bib]\n")


if __name__ == "__main__":
    unittest.main()

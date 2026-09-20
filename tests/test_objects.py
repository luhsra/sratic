import unittest
from pathlib import Path

from sratic.metadata import YAMLFragment
from sratic.objects import ObjectStore


def fragment(path: str, data: dict) -> YAMLFragment:
    return YAMLFragment(Path(path), data)


class ObjectStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = fragment(
            "data/schema.yml",
            {
                "page": {},
                "thing": {},
            },
        )
        self.data = fragment(
            "data/root.yml",
            {
                "site": {"permalink_base": "/p"},
            },
        )

    def test_propagation(self) -> None:
        main = fragment(
            "index.md",
            {"id": "main", "children": ["child"], "page-body": ""},
        )
        child = fragment(
            "child.md",
            {"id": "child", "depends": "leaf", "page-body": ""},
        )
        leaf = fragment("leaf.md", {"id": "leaf", "page-body": ""})
        store = ObjectStore()

        store.crawl_pages(self.schema, self.data, [main, child, leaf])

        self.assertEqual(child.data["parent"], "main")
        self.assertEqual(main.data["children"], ["child"])
        self.assertEqual(main.data["depends"], {"child", "leaf"})
        self.assertEqual(child.data["depends"], {"leaf"})
        self.assertIn(child.path, main.sources)
        self.assertIn(leaf.path, main.sources)
        self.assertIn(leaf.path, child.sources)

    def test_duplicate_page_id(self) -> None:
        pages = [
            fragment("one.md", {"id": "duplicate", "page-body": ""}),
            fragment("two.md", {"id": "duplicate", "page-body": ""}),
        ]

        with self.assertRaisesRegex(AssertionError, "Duplicate Page ID: duplicate"):
            ObjectStore().crawl_pages(self.schema, self.data, pages)

    def test_duplicate_object_id(self) -> None:
        pages = [
            fragment(
                "one.md",
                {
                    "id": "one",
                    "items": [{"id": "duplicate", "type": "thing"}],
                    "page-body": "",
                },
            ),
            fragment(
                "two.md",
                {
                    "id": "two",
                    "items": [{"id": "duplicate", "type": "thing"}],
                    "page-body": "",
                },
            ),
        ]

        with self.assertRaisesRegex(
            AssertionError, r"Duplicate Object ID \(duplicate\)"
        ):
            ObjectStore().crawl_pages(self.schema, self.data, pages)

    def test_duplicate_permalink_alias(self) -> None:
        pages = [
            fragment(
                "one.md",
                {"id": "one", "permalink.alias": "shared", "page-body": ""},
            ),
            fragment(
                "two.md",
                {"id": "two", "permalink.alias": "shared", "page-body": ""},
            ),
        ]

        with self.assertRaisesRegex(AssertionError, "Alias shared is duplicated"):
            ObjectStore().crawl_pages(self.schema, self.data, pages)

    def test_duplicate_object_alias(self) -> None:
        data = fragment(
            "data/root.yml",
            {
                "site": {"permalink_base": "/p"},
                "items": [
                    {"id": "one", "type": "thing", "object_aliases": ["shared"]},
                    {"id": "two", "type": "thing", "object_aliases": ["shared"]},
                ],
            },
        )

        with self.assertRaisesRegex(
            AssertionError, r"Alias \(object_aliases\) shared is duplicated"
        ):
            ObjectStore().crawl_pages(self.schema, data, [])


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

from sratic.metadata import YAMLFragment
from sratic.objects import ObjectStore
from sratic.schema import check_schema


class SchemaTests(unittest.TestCase):
    def test_dereference(self) -> None:
        schema = YAMLFragment(
            None,
            Path("schema.yml"),
            {
                "team": {
                    "lead": {"type": "object.person", "deref": True},
                    "members": {"type": ["object.person"], "deref": True},
                }
            },
        )
        ada = {"id": "ada", "type": ["person"]}
        grace = {"id": "grace", "type": ["person"]}
        objects = ObjectStore()
        objects.objects = {"ada": ada, "grace": grace}
        team = {
            "id": "researchers",
            "type": ["team"],
            "lead": "ada",
            "members": ["ada", "grace"],
        }

        check_schema(schema, team, objects)

        self.assertIs(team["lead"], ada)
        self.assertEqual(team["members"], [ada, grace])


if __name__ == "__main__":
    unittest.main()

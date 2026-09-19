import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class FixtureSiteTests(unittest.TestCase):
    fixture = Path(__file__).parent / "fixtures" / "site"
    snapshot = Path(__file__).parent / "fixtures" / "snapshot"
    package_root = Path(__file__).parents[1]

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(cls.temporary_directory.name)
        cls.source = root / "site"
        cls.destination = root / "output"
        shutil.copytree(cls.fixture, cls.source)
        cls._run_generator(cls.source, cls.destination)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_directory.cleanup()

    @classmethod
    def _run_generator(cls, source: Path, destination: Path, dry: bool = False) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, [str(cls.package_root), env.get("PYTHONPATH")])
        )
        command = [
            sys.executable,
            "-msratic",
            f"-d{destination}",
            f"-t{source / 'templates'}",
            "-j1",
        ]
        if dry:
            command.append("--dry")
        result = subprocess.run(
            command,
            cwd=source,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            output = (result.stdout + result.stderr).splitlines()[-30:]
            raise AssertionError("Generator failed:\n" + "\n".join(output))

    def test_formatter_order(self) -> None:
        output = (self.destination / "index.html").read_text()

        self.assertIn('<h1 id="pageheading">Fixture Site</h1>', output)
        self.assertIn("<p>People: 1</p>", output)
        self.assertNotIn("{{", output)

    def test_links(self) -> None:
        output = (self.destination / "index.html").read_text()
        self.assertIn('Link: <a href="./child.html">Child</a>', output)

    def test_csv(self) -> None:
        output = (self.destination / "index.html").read_text()
        self.assertIn("From CSV: Ada Lovelace", output)

    def test_bibliography(self) -> None:
        output = (self.destination / "index.html").read_text()
        self.assertIn("Bibliography: Notes on Computing", output)

    def test_multi_output(self) -> None:
        self.assertEqual(
            (self.destination / "report.txt").read_text().strip(), "Ada Lovelace"
        )
        self.assertEqual(
            (self.destination / "report.csv").read_text().strip(), "Ada Lovelace"
        )

    def test_template(self) -> None:
        self.assertEqual(
            (self.destination / "child.html").read_text().strip(),
            "<title>Child</title>\n<main><p>Parent: main</p></main>",
        )

    def test_snapshot(self) -> None:
        actual_files = {
            path.relative_to(self.destination)
            for path in self.destination.rglob("*")
            if path.is_file() and not path.name.startswith(".deps.")
        }
        expected_files = {
            path.relative_to(self.snapshot)
            for path in self.snapshot.rglob("*")
            if path.is_file()
        }

        self.assertEqual(actual_files, set(expected_files))
        for relative_path in expected_files:
            self.assertEqual(
                (self.destination / relative_path).read_bytes().strip(),
                (self.snapshot / relative_path).read_bytes().strip(),
                str(relative_path),
            )

    def test_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "site"
            destination = root / "output"
            shutil.copytree(self.fixture, source)

            self._run_generator(source, destination, dry=True)

            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()

import subprocess
import unittest
from pathlib import Path


class FullSiteSmokeTests(unittest.TestCase):
    def test_make_dry(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["make", "dry"],
            cwd=repository,
            text=True,
            capture_output=True,
            check=False,
        )

        if result.returncode:
            output = (result.stdout + result.stderr).splitlines()[-40:]
            self.fail("make dry failed:\n" + "\n".join(output))


if __name__ == "__main__":
    unittest.main()

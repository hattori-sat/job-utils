import unittest
from pathlib import Path


class SetupScriptTests(unittest.TestCase):
    def test_platform_setup_scripts_are_present(self):
        root = Path(__file__).parents[1]
        posix = (root / "scripts" / "setup.sh").read_text(encoding="utf-8")
        windows = (root / "scripts" / "setup.ps1").read_text(encoding="utf-8")
        self.assertIn("venv", posix)
        self.assertIn("jobutils setup init", posix)
        self.assertIn("venv", windows)
        self.assertIn("jobutils setup init", windows)


if __name__ == "__main__":
    unittest.main()

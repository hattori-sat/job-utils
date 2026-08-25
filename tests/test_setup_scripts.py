import unittest
from pathlib import Path


class SetupScriptTests(unittest.TestCase):
    def test_platform_setup_scripts_are_present(self):
        root = Path(__file__).parents[1]
        posix = (root / "scripts" / "setup.sh").read_text(encoding="utf-8")
        windows = (root / "scripts" / "setup.ps1").read_text(encoding="utf-8")
        posix_vim = (root / "scripts" / "jobutils-vim").read_text(encoding="utf-8")
        windows_vim = (root / "scripts" / "jobutils-vim.ps1").read_text(encoding="utf-8")
        self.assertIn("venv", posix)
        self.assertIn("jobutils setup init", posix)
        self.assertIn("venv", windows)
        self.assertIn("jobutils setup init", windows)
        self.assertIn("GTD_ROOT", posix_vim)
        self.assertIn("gtd.md", posix_vim)
        self.assertIn("GTD_ROOT", windows_vim)
        self.assertIn("gtd.md", windows_vim)


if __name__ == "__main__":
    unittest.main()

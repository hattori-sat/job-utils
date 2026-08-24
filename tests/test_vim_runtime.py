import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class VimRuntimeTests(unittest.TestCase):
    def test_runtime_sources_in_classic_vim(self):
        vim = shutil.which("vim")
        if vim is None:
            self.skipTest("Vim is not installed")
        repository = Path(__file__).parents[1]
        vim_runtime = repository / "vim"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "CMakeLists.txt").write_text("project(test)\n", encoding="utf-8")
            (root / "main.c").write_text(
                "int main(void) { return 0; }\n", encoding="utf-8"
            )
            result = subprocess.run(
                [
                    vim,
                    "-Nu",
                    "NONE",
                    "-n",
                    "-es",
                    "+set rtp^=" + str(vim_runtime),
                    "+source " + str(vim_runtime / "plugin/jobutils_defaults.vim"),
                    "+edit " + str(root / "main.c"),
                    "+call jobutils#project#show_root()",
                    "+qa!",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_runtime_detects_common_editing_filetypes_and_preserves_make_tabs(self):
        vim = shutil.which("vim")
        if vim is None:
            self.skipTest("Vim is not installed")
        repository = Path(__file__).parents[1]
        vim_runtime = repository / "vim"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "README.md": ("markdown", "1", "2"),
                "data.json": ("json", "1", "2"),
                "doc.xml": ("xml", "1", "2"),
                "main.cpp": ("cpp", "1", "4"),
                "main.c": ("c", "1", "4"),
                "CMakeLists.txt": ("cmake", "1", "4"),
                "Makefile": ("make", "0", "8"),
            }
            for name in files:
                (root / name).write_text("\n", encoding="utf-8")
            checks = []
            for name, (filetype, expandtab, shiftwidth) in files.items():
                checks.append(
                    "edit {} | if &filetype !=# '{}' | cquit 10 | endif | if &expandtab != {} | cquit 11 | endif | if &shiftwidth != {} | cquit 12 | endif".format(
                        str(root / name), filetype, expandtab, shiftwidth
                    )
                )
            result = subprocess.run(
                [
                    vim,
                    "-Nu",
                    "NONE",
                    "-n",
                    "-es",
                    "+set rtp^=" + str(vim_runtime),
                    "+source " + str(vim_runtime / "plugin/jobutils_defaults.vim"),
                ]
                + ["+{}".format(check) for check in checks]
                + ["+qa!"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

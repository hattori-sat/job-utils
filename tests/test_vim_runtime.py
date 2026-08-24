import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class VimRuntimeTests(unittest.TestCase):
    def test_filetype_defaults_switch_disables_markdown_autocommands(self):
        vim = shutil.which("vim")
        if vim is None:
            self.skipTest("Vim is not installed")
        repository = Path(__file__).parents[1]
        vim_runtime = repository / "vim"
        result = subprocess.run(
            [
                vim,
                "-Nu",
                "NONE",
                "-n",
                "-es",
                "+let g:jobutils_enable_filetype_defaults=0",
                "+set rtp^=" + str(vim_runtime),
                "+source " + str(vim_runtime / "plugin/jobutils_defaults.vim"),
                "+set filetype=markdown",
                "+if &l:formatoptions =~# 'r' | cquit 50 | endif",
                "+if stridx(&l:formatlistpat, '[-*+]') >= 0 | cquit 51 | endif",
                "+qa!",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_markdown_enter_continues_native_lists_without_affecting_plain_text(self):
        vim = shutil.which("vim")
        if vim is None:
            self.skipTest("Vim is not installed")
        repository = Path(__file__).parents[1]
        vim_runtime = repository / "vim"
        cases = (
            ("minus.md", "- first item", "-", True),
            ("star.md", "* first item", "*", True),
            ("plus.md", "+ first item", "+", True),
            ("numbered.md", "1. first item", "", True),
            ("plain.txt", "- first item", "", False),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (name, first_line, expected, is_markdown) in enumerate(cases):
                path = root / name
                path.write_text(first_line + "\n", encoding="utf-8")
                expected_vim = "'{}'".format(expected.replace("'", "''"))
                checks = [
                    "+edit {}".format(path),
                    '+call feedkeys("A\\<CR>", "xt")',
                    "+if getline(2) !=# {} | cquit {} | endif".format(
                        expected_vim, 20 + index
                    ),
                ]
                if is_markdown:
                    checks.append(
                        "+if &l:filetype !=# 'markdown' | cquit {} | endif".format(
                            30 + index
                        )
                    )
                    checks.append(
                        "+if &l:formatoptions !~# 'n' | cquit {} | endif".format(
                            40 + index
                        )
                    )
                    if name == "numbered.md":
                        checks.append(
                            "+if matchstr(getline(1), &l:formatlistpat) !=# '1. ' | cquit {} | endif".format(
                                45 + index
                            )
                        )
                else:
                    checks.append(
                        "+if &l:filetype ==# 'markdown' | cquit {} | endif".format(
                            30 + index
                        )
                    )
                    checks.append(
                        "+if stridx(&l:formatlistpat, '[-*+]') >= 0 | cquit {} | endif".format(
                            35 + index
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
                    + checks
                    + ["+qa!"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    "{} failed: {}{}".format(
                        name, result.stderr, result.stdout
                    ),
                )

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
                    "-i",
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
                    "-i",
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

    def test_runtime_detects_bitbake_files_and_applies_recipe_defaults(self):
        vim = shutil.which("vim")
        if vim is None:
            self.skipTest("Vim is not installed")
        repository = Path(__file__).parents[1]
        vim_runtime = repository / "vim"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe = root / "meta-example" / "recipes-example" / "demo" / "demo.bb"
            recipe.parent.mkdir(parents=True)
            recipe.write_text("SUMMARY = \"demo\"\n", encoding="utf-8")
            checks = [
                "+edit {}".format(recipe),
                "+if &filetype !=# 'bitbake' | cquit 70 | endif",
                "+if &l:commentstring !~# '^#' | cquit 71 | endif",
                "+if &l:shiftwidth != 4 | cquit 72 | endif",
                "+if &l:suffixesadd !~# '\\.bb' | cquit 73 | endif",
                "+if &syntax !=# 'bitbake' | cquit 74 | endif",
                "+qa!",
            ]
            result = subprocess.run(
                [
                    vim,
                    "-Nu",
                    "NONE",
                    "-i",
                    "NONE",
                    "-n",
                    "-es",
                    "+set rtp^=" + str(vim_runtime),
                    "+source " + str(vim_runtime / "plugin/jobutils_defaults.vim"),
                ]
                + checks,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_project_toolchain_commands_are_available(self):
        vim = shutil.which("vim")
        if vim is None:
            self.skipTest("Vim is not installed")
        repository = Path(__file__).parents[1]
        vim_runtime = repository / "vim"
        commands = (
            "JobutilsCMakeConfigure",
            "JobutilsCMakeBuild",
            "JobutilsCMakeTest",
            "JobutilsMake",
            "JobutilsClangFormat",
            "JobutilsCompileCommands",
            "JobutilsQuickfix",
        )
        checks = [
            "+if exists(':{}') != 2 | cquit {} | endif".format(command, 80 + index)
            for index, command in enumerate(commands)
        ]
        result = subprocess.run(
            [
                vim,
                "-Nu",
                "NONE",
                "-i",
                "NONE",
                "-n",
                "-es",
                "+set rtp^=" + str(vim_runtime),
                "+source " + str(vim_runtime / "plugin/jobutils_defaults.vim"),
            ]
            + checks
            + ["+qa!"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_cmake_configure_populates_quickfix_with_command_output(self):
        vim = shutil.which("vim")
        if vim is None:
            self.skipTest("Vim is not installed")
        repository = Path(__file__).parents[1]
        vim_runtime = repository / "vim"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_cmake = fake_bin / "cmake"
            fake_cmake.write_text(
                "#!/bin/sh\nprintf 'fake cmake configure\\n'\n",
                encoding="utf-8",
            )
            fake_cmake.chmod(0o755)
            (root / "CMakeLists.txt").write_text("project(test)\n", encoding="utf-8")
            source = root / "main.c"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            result_file = root / "quickfix.txt"
            result = subprocess.run(
                [
                    vim,
                    "-Nu",
                    "NONE",
                    "-i",
                    "NONE",
                    "-n",
                    "-es",
                    "+set rtp^=" + str(vim_runtime),
                    "+source " + str(vim_runtime / "plugin/jobutils_defaults.vim"),
                    "+edit " + str(source),
                    "+lcd " + str(root),
                    "+JobutilsCMakeConfigure",
                    "+call writefile([getqflist({'title': 1}).title, getqflist()[0].text, string(haslocaldir()), getcwd(-1)], '" + str(result_file) + "')",
                    "+qa!",
                ],
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]},
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(
                result_file.read_text(encoding="utf-8").splitlines(),
                ["CMake configure", "fake cmake configure", "1", str(Path.cwd())],
            )

    def test_clang_format_replaces_buffer_without_extra_eof_line(self):
        vim = shutil.which("vim")
        if vim is None:
            self.skipTest("Vim is not installed")
        repository = Path(__file__).parents[1]
        vim_runtime = repository / "vim"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_formatter = fake_bin / "clang-format"
            fake_formatter.write_text(
                "#!/bin/sh\nprintf 'formatted output\\n'\n",
                encoding="utf-8",
            )
            fake_formatter.chmod(0o755)
            source = root / "main.c"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            result_file = root / "formatted.txt"
            result = subprocess.run(
                [
                    vim,
                    "-Nu",
                    "NONE",
                    "-i",
                    "NONE",
                    "-n",
                    "-es",
                    "+set rtp^=" + str(vim_runtime),
                    "+source " + str(vim_runtime / "plugin/jobutils_defaults.vim"),
                    "+edit " + str(source),
                    "+JobutilsClangFormat",
                    "+call writefile(getline(1, '$'), '" + str(result_file) + "')",
                    "+qa!",
                ],
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]},
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(
                result_file.read_text(encoding="utf-8").splitlines(),
                ["formatted output"],
            )

    def test_gtd_dispatch_reloads_buffer_and_keeps_current_task_usable(self):
        vim = shutil.which("vim")
        if vim is None:
            self.skipTest("Vim is not installed")
        repository = Path(__file__).parents[1]
        vim_runtime = repository / "vim"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gtd = root / "gtd.md"
            gtd.write_text(
                "# GTD\n\n## Inbox\n\n- today: Work item\n\n## Next Actions\n\n## Today\n\n## Focus\n\n## Waiting\n\n## Calendar\n\n## Someday\n\n## Projects\n\n## Done\n",
                encoding="utf-8",
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
                    "+source " + str(vim_runtime / "plugin/jobutils_gtd.vim"),
                    "+let g:jobutils_python='{}'".format(sys.executable),
                    "+edit {}".format(gtd),
                    "+call cursor(5, 1)",
                    "+Gtd",
                    "+GtdTask",
                    "+if expand('%:p') !~# '/gtd_tasks/' | cquit 14 | endif",
                    "+qall!",
                ],
                capture_output=True,
                text=True,
                check=False,
                env={**__import__("os").environ, "PYTHONPATH": str(repository / "src")},
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertNotIn("W11", result.stderr + result.stdout)

    def test_gtd_subtask_command_is_available_with_lowercase_alias(self):
        vim = shutil.which("vim")
        if vim is None:
            self.skipTest("Vim is not installed")
        repository = Path(__file__).parents[1]
        vim_runtime = repository / "vim"
        result = subprocess.run(
            [
                vim,
                "-Nu",
                "NONE",
                "-n",
                "-es",
                "+set rtp^=" + str(vim_runtime),
                "+source " + str(vim_runtime / "plugin/jobutils_gtd.vim"),
                "+if exists(':GtdSubtask') == 0 | cquit 60 | endif",
                "+let g:jobutils_abbreviations = execute('silent cabbrev')",
                "+if g:jobutils_abbreviations !~# 'gtdsubtask' || g:jobutils_abbreviations !~# 'gtdreview' | cquit 61 | endif",
                "+qa!",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_sync_commands_are_available_with_lowercase_aliases(self):
        vim = shutil.which("vim")
        if vim is None:
            self.skipTest("Vim is not installed")
        repository = Path(__file__).parents[1]
        vim_runtime = repository / "vim"
        commands = (
            "GtdSyncPlan",
            "GtdSyncApply",
            "GtdSyncPull",
            "GtdSyncStatus",
            "GtdSyncHelp",
        )
        command_check = " || ".join(
            "exists(':{}') != 2".format(command) for command in commands
        )
        alias_check = " || ".join(
            "g:jobutils_abbreviations !~# '{}'".format(alias)
            for alias in (
                "gtdsyncplan",
                "gtdsyncapply",
                "gtdsyncpull",
                "gtdsyncstatus",
                "gtdsynchelp",
            )
        )
        checks = [
            "+if {} | cquit 90 | endif".format(command_check),
            "+let g:jobutils_abbreviations = execute('silent cabbrev')",
            "+if {} | cquit 91 | endif".format(alias_check),
        ]
        result = subprocess.run(
            [
                vim,
                "-Nu",
                "NONE",
                "-i",
                "NONE",
                "-n",
                "-es",
                "+set rtp^=" + str(vim_runtime),
                "+source " + str(vim_runtime / "plugin/jobutils_gtd.vim"),
            ]
            + checks
            + ["+qa!"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_sync_apply_cancellation_does_not_run_external_command(self):
        vim = shutil.which("vim")
        if vim is None:
            self.skipTest("Vim is not installed")
        repository = Path(__file__).parents[1]
        vim_runtime = repository / "vim"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "gtd.md").write_text("# GTD\n", encoding="utf-8")
            plans = root / ".jobutils" / "sync" / "plans"
            plans.mkdir(parents=True)
            (plans / "plan.json").write_text(
                '{"plan_id": "plan-1", "actions": []}\n', encoding="utf-8"
            )
            messages = root / "messages.txt"
            result = subprocess.run(
                [
                    vim,
                    "-Nu",
                    "NONE",
                    "-i",
                    "NONE",
                    "-n",
                    "-es",
                    "+set rtp^=" + str(vim_runtime),
                    "+source " + str(vim_runtime / "plugin/jobutils_gtd.vim"),
                    "+let g:jobutils_sync_confirm='C'",
                    "+edit " + str(root / "gtd.md"),
                    "+GtdSyncApply",
                    "+call writefile([execute('messages')], '" + str(messages) + "')",
                    "+qa!",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("cancel", messages.read_text(encoding="utf-8").lower())

    def test_sync_plan_command_creates_reviewable_plan(self):
        vim = shutil.which("vim")
        if vim is None:
            self.skipTest("Vim is not installed")
        repository = Path(__file__).parents[1]
        vim_runtime = repository / "vim"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "gtd.md").write_text("# GTD\n", encoding="utf-8")
            documents = root / "documents"
            documents.mkdir()
            (documents / "guide.md").write_text(
                "---\nkind: document\ntitle: Guide\npublish_confluence: true\n---\n\n# Guide\n",
                encoding="utf-8",
            )
            result_file = root / "plans.txt"
            result = subprocess.run(
                [
                    vim,
                    "-Nu",
                    "NONE",
                    "-i",
                    "NONE",
                    "-n",
                    "-es",
                    "+set rtp^=" + str(vim_runtime),
                    "+source " + str(vim_runtime / "plugin/jobutils_gtd.vim"),
                    "+let g:jobutils_python='{}'".format(sys.executable),
                    "+edit " + str(root / "gtd.md"),
                    "+GtdSyncPlan",
                    "+call writefile(glob('" + str(root / ".jobutils/sync/plans/*.json") + "', 0, 1), '" + str(result_file) + "')",
                    "+qa!",
                ],
                capture_output=True,
                text=True,
                check=False,
                env={**__import__("os").environ, "PYTHONPATH": str(repository / "src")},
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(len(result_file.read_text(encoding="utf-8").splitlines()), 1)

    def test_gtd_subtask_uses_current_task_as_parent(self):
        vim = shutil.which("vim")
        if vim is None:
            self.skipTest("Vim is not installed")
        repository = Path(__file__).parents[1]
        vim_runtime = repository / "vim"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "gtd.md").write_text("# GTD\n", encoding="utf-8")
            parent = root / "gtd_tasks" / "parent.md"
            parent.parent.mkdir()
            parent.write_text(
                """---
gtd_id: 'parent-1'
jira_key: 'DEMO-1'
jira_project: 'DEMO'
publish_jira: true
---

# Parent

# Subtasks

- next: Child from Vim

# Implementation Note

private
""",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    vim,
                    "-Nu",
                    "NONE",
                    "-n",
                    "-es",
                    "+set rtp^=" + str(vim_runtime),
                    "+source " + str(vim_runtime / "plugin/jobutils_gtd.vim"),
                    "+let g:jobutils_python='{}'".format(sys.executable),
                    "+edit {}".format(parent),
                    "+call cursor(12, 1)",
                    "+GtdSubtask",
                    "+qall!",
                ],
                capture_output=True,
                text=True,
                check=False,
                    env={**__import__("os").environ, "PYTHONPATH": str(repository / "src")},
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            children = list((root / "gtd_tasks" / "parent").glob("*.md"))
            self.assertEqual(len(children), 1)
            self.assertIn(
                "jira_parent_key: 'DEMO-1'",
                children[0].read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()

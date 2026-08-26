import tempfile
import unittest
from pathlib import Path
import subprocess

import sys
import os

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.setup_workflow import (
    SetupError,
    ensure_env_file,
    ensure_shell_profile,
    ensure_vimrc_registration,
    install_user_wrappers,
)
from jobutils.env import load_local_env


class SetupProfileTests(unittest.TestCase):
    def test_env_file_is_created_with_interactive_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.example").write_text(
                "JIRA_API_TOKEN=\nCONFLUENCE_API_TOKEN=\n", encoding="utf-8"
            )

            def answer(prompt):
                return "example-value"

            def secret_answer(prompt):
                return "test-token"

            env_path = ensure_env_file(
                root, input_fn=answer, secret_input_fn=secret_answer
            )
            content = env_path.read_text(encoding="utf-8")
            self.assertIn("JIRA_API_TOKEN=test-token", content)
            self.assertIn("CONFLUENCE_API_TOKEN=test-token", content)

    def test_vimrc_registration_and_shell_profile_are_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vimrc = root / ".vimrc"
            snippet = root / "vim-config.vim"
            profile = root / ".zshrc"
            ensure_vimrc_registration(
                vimrc, snippet, "/opt/job-utils/.venv/bin/python"
            )
            ensure_shell_profile(profile, root / ".local" / "bin", "posix")
            first_vimrc = vimrc.read_text(encoding="utf-8")
            first_profile = profile.read_text(encoding="utf-8")
            self.assertIn('" >>> job-utils setup >>>', first_vimrc)
            self.assertNotIn("# >>> job-utils setup >>>", first_vimrc)
            ensure_vimrc_registration(
                vimrc, snippet, "/opt/job-utils/.venv/bin/python"
            )
            ensure_shell_profile(profile, root / ".local" / "bin", "posix")
            self.assertEqual(vimrc.read_text(encoding="utf-8"), first_vimrc)
            self.assertEqual(profile.read_text(encoding="utf-8"), first_profile)

    def test_vimrc_registration_repairs_legacy_shell_markers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vimrc = root / ".vimrc"
            vimrc.write_text(
                "# >>> job-utils setup >>>\n"
                "execute 'source ' . fnameescape('/old/snippet.vim')\n"
                "# <<< job-utils setup <<<\n",
                encoding="utf-8",
            )
            snippet = root / "vim-config.vim"

            ensure_vimrc_registration(vimrc, snippet, "/opt/job-utils/.venv/bin/python")

            content = vimrc.read_text(encoding="utf-8")
            self.assertNotIn("# >>> job-utils setup >>>", content)
            self.assertNotIn("# <<< job-utils setup <<<", content)
            self.assertIn('" >>> job-utils setup >>>', content)

    def test_vimrc_registration_repairs_malformed_legacy_markers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vimrc = root / ".vimrc"
            vimrc.write_text(
                ">>> job-utils setup >>>: # >>> job-utils setup >>>\n"
                "execute 'source ' . fnameescape('/old/snippet.vim')\n"
                "<<< job-utils setup <<<: # <<< job-utils setup <<<\n",
                encoding="utf-8",
            )

            ensure_vimrc_registration(
                vimrc, root / "vim-config.vim", "/opt/job-utils/.venv/bin/python"
            )

            content = vimrc.read_text(encoding="utf-8")
            self.assertNotIn(">>> job-utils setup >>>:", content)
            self.assertNotIn("<<< job-utils setup <<<:", content)
            self.assertIn('" >>> job-utils setup >>>', content)

    def test_user_wrappers_use_the_job_utils_virtual_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            paths = install_user_wrappers(root, bin_dir, "posix")
            self.assertEqual(
                set(paths), {"jobutils", "jobutils-python", "jobutils-vim"}
            )
            self.assertIn(str(root / ".venv"), paths["jobutils"].read_text())
            self.assertIn(str(root / ".venv" / "bin" / "python"), paths["jobutils"].read_text())
            vim_wrapper = paths["jobutils-vim"].read_text()
            self.assertIn('GTD_ROOT', vim_wrapper)
            self.assertIn('gtd.md', vim_wrapper)
            self.assertIn('if [ "$#" -eq 0 ]', vim_wrapper)
            self.assertTrue(paths["jobutils"].stat().st_mode & 0o111)
            configured_repo = root / "gtd"
            paths = install_user_wrappers(root, bin_dir, "posix", configured_repo)
            self.assertIn(
                "JOBUTILS_CONFIGURED_GTD_ROOT='{}'".format(configured_repo.resolve()),
                paths["jobutils-vim"].read_text(),
            )

    def test_generated_vim_wrapper_opens_configured_gtd_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gtd_repo = root / "gtd"
            gtd_repo.mkdir()
            (gtd_repo / "gtd.md").write_text("# GTD\n", encoding="utf-8")
            fake_bin = root / "fake-bin"
            fake_bin.mkdir()
            capture = root / "vim-args"
            fake_vim = fake_bin / "vim"
            fake_vim.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$JOBUTILS_CAPTURE\"\n",
                encoding="utf-8",
            )
            fake_vim.chmod(0o755)
            fake_python = root / ".venv" / "bin" / "python"
            fake_python.parent.mkdir(parents=True)
            fake_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_python.chmod(0o755)
            wrapper = install_user_wrappers(
                root, root / "bin", "posix", gtd_repo
            )["jobutils-vim"]
            environment = dict(os.environ)
            environment["PATH"] = str(fake_bin)
            environment["JOBUTILS_CAPTURE"] = str(capture)
            result = subprocess.run(
                [str(wrapper)], env=environment, check=False
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                capture.read_text(encoding="utf-8").strip(),
                str((gtd_repo / "gtd.md").resolve()),
            )

    def test_existing_unmanaged_wrapper_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            wrapper = bin_dir / "jobutils"
            wrapper.write_text("#!/bin/sh\necho user-owned\n", encoding="utf-8")
            with self.assertRaises(SetupError):
                install_user_wrappers(root, bin_dir, "posix")
            self.assertEqual(wrapper.read_text(encoding="utf-8"), "#!/bin/sh\necho user-owned\n")

    def test_windows_activation_uses_job_utils_virtual_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "profile.ps1"
            ensure_shell_profile(profile, root / "bin", "windows", root)
            content = profile.read_text(encoding="utf-8")
            expected = str(root / ".venv" / "Scripts" / "Activate.ps1").replace(
                "/", "\\"
            )
            self.assertIn(expected, content)
            self.assertNotIn(
                str(root / "Scripts" / "Activate.ps1").replace("/", "\\"), content
            )

    def test_windows_vim_wrapper_opens_gtd_root_when_no_file_is_given(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = install_user_wrappers(root, root / "bin", "windows")
            content = paths["jobutils-vim"].read_text()
            self.assertIn("GTD_ROOT", content)
            self.assertIn("gtd.md", content)
            self.assertIn('if "%~1"==""', content)

    def test_local_env_loader_does_not_override_process_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "JOBUTILS_TEST_LOCAL=from-file\nJOBUTILS_TEST_EXISTING=from-file\n",
                encoding="utf-8",
            )
            old_local = os.environ.get("JOBUTILS_TEST_LOCAL")
            old_existing = os.environ.get("JOBUTILS_TEST_EXISTING")
            try:
                os.environ.pop("JOBUTILS_TEST_LOCAL", None)
                os.environ["JOBUTILS_TEST_EXISTING"] = "from-process"
                added = load_local_env(root)
                self.assertEqual(added["JOBUTILS_TEST_LOCAL"], "from-file")
                self.assertEqual(os.environ["JOBUTILS_TEST_EXISTING"], "from-process")
            finally:
                if old_local is None:
                    os.environ.pop("JOBUTILS_TEST_LOCAL", None)
                else:
                    os.environ["JOBUTILS_TEST_LOCAL"] = old_local
                if old_existing is None:
                    os.environ.pop("JOBUTILS_TEST_EXISTING", None)
                else:
                    os.environ["JOBUTILS_TEST_EXISTING"] = old_existing


if __name__ == "__main__":
    unittest.main()

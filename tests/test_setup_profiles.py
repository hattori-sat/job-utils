import tempfile
import unittest
from pathlib import Path

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
            ensure_vimrc_registration(
                vimrc, snippet, "/opt/job-utils/.venv/bin/python"
            )
            ensure_shell_profile(profile, root / ".local" / "bin", "posix")
            self.assertEqual(vimrc.read_text(encoding="utf-8"), first_vimrc)
            self.assertEqual(profile.read_text(encoding="utf-8"), first_profile)

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
            self.assertTrue(paths["jobutils"].stat().st_mode & 0o111)

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

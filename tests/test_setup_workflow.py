import tempfile
import unittest
import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.setup_workflow import (
    SetupError,
    bootstrap_gtd_repository,
    detect_platform,
    run_setup,
    validate_gtd_repository,
)


class SetupWorkflowTests(unittest.TestCase):
    def test_detect_platform_accepts_supported_systems(self):
        self.assertEqual(detect_platform("Darwin"), "macos")
        self.assertEqual(detect_platform("Linux", distribution="Ubuntu"), "ubuntu")
        self.assertEqual(detect_platform("Windows"), "windows")

    def test_unsupported_platform_is_rejected(self):
        with self.assertRaises(SetupError):
            detect_platform("FreeBSD")

    def test_missing_or_non_git_repository_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(SetupError):
                validate_gtd_repository(root / "missing")
            with self.assertRaises(SetupError):
                validate_gtd_repository(root)

    def test_bootstrap_preserves_existing_files_and_creates_missing_items(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / ".git").mkdir()
            (repo / "gtd.md").write_text("# My GTD\n", encoding="utf-8")
            bootstrap_gtd_repository(repo)
            self.assertEqual(
                (repo / "gtd.md").read_text(encoding="utf-8"), "# My GTD\n"
            )
            self.assertTrue((repo / "docs.md").is_file())
            self.assertTrue((repo / "gtd_tasks").is_dir())
            self.assertTrue((repo / "documents").is_dir())
            self.assertTrue((repo / ".jobutils").is_dir())

    def test_setup_records_state_and_redacted_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "job-utils"
            root.mkdir()
            (root / ".env.example").write_text(
                "JIRA_API_TOKEN=\n", encoding="utf-8"
            )
            repo = Path(directory) / "gtd"
            (repo / ".git").mkdir(parents=True)
            result = run_setup(
                root,
                repo,
                platform_name="macos",
                skip_env_prompt=True,
                home=Path(directory) / "home",
            )
            state = Path(result["state"])
            log = state.with_name("setup.log")
            self.assertTrue(state.is_file())
            self.assertTrue(log.is_file())
            self.assertIn('"status": "completed"', state.read_text())
            self.assertNotIn("API_TOKEN", log.read_text())

    def test_setup_records_failed_step_for_resumable_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "job-utils"
            root.mkdir()
            repo = Path(directory) / "gtd"
            (repo / ".git").mkdir(parents=True)
            with self.assertRaises(SetupError):
                run_setup(
                    root,
                    repo,
                    platform_name="macos",
                    home=Path(directory) / "home",
                )
            state = root / ".jobutils" / "setup" / "state.json"
            data = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(data["steps"]["env"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()

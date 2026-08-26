import tempfile
import unittest
import json
import subprocess
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
    def _init_git(self, path):
        subprocess.run(
            ["git", "init", str(path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

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
            fake = root / "fake"
            (fake / ".git").mkdir(parents=True)
            with self.assertRaises(SetupError):
                validate_gtd_repository(fake)

    def test_bootstrap_preserves_existing_files_and_creates_missing_items(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._init_git(repo)
            (repo / "gtd.md").write_text("# My GTD\n", encoding="utf-8")
            bootstrap_gtd_repository(repo)
            gtd = (repo / "gtd.md").read_text(encoding="utf-8")
            self.assertIn("# My GTD\n", gtd)
            self.assertIn("[Documents](docs.md)", gtd)
            self.assertTrue((repo / "docs.md").is_file())
            self.assertTrue((repo / "gtd_tasks").is_dir())
            self.assertTrue((repo / "documents").is_dir())
            self.assertTrue((repo / ".jobutils").is_dir())
            ignored = subprocess.run(
                ["git", "-C", str(repo), "check-ignore", ".jobutils/output/report.html"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(ignored.returncode, 0, ignored.stderr)
            ignored_plan = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "check-ignore",
                    ".jobutils/sync/plans/plan.json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(ignored_plan.returncode, 0, ignored_plan.stderr)

    def test_bootstrap_adds_reciprocal_index_links_without_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._init_git(repo)
            (repo / "gtd.md").write_text("# GTD\n", encoding="utf-8")
            (repo / "docs.md").write_text("# Documents\n", encoding="utf-8")

            bootstrap_gtd_repository(repo)
            bootstrap_gtd_repository(repo)

            gtd = (repo / "gtd.md").read_text(encoding="utf-8")
            docs = (repo / "docs.md").read_text(encoding="utf-8")
            self.assertIn("[Documents](docs.md)", gtd)
            self.assertIn("[GTD](gtd.md)", docs)
            self.assertEqual(gtd.count("[Documents](docs.md)"), 1)
            self.assertEqual(docs.count("[GTD](gtd.md)"), 1)

    def test_setup_records_state_and_redacted_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "job-utils"
            root.mkdir()
            (root / ".env.example").write_text(
                "JIRA_API_TOKEN=\n", encoding="utf-8"
            )
            repo = Path(directory) / "gtd"
            self._init_git(repo)
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

    def test_setup_creates_initial_gtd_commit_for_uncommitted_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "job-utils"
            root.mkdir()
            repo = Path(directory) / "gtd"
            self._init_git(repo)
            (repo / ".gtd.md.swp").write_text("vim recovery data\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "Test User"],
                check=True,
                stdout=subprocess.PIPE,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
                check=True,
                stdout=subprocess.PIPE,
            )

            run_setup(
                root,
                repo,
                platform_name="macos",
                skip_env_prompt=True,
                home=Path(directory) / "home",
            )

            revision = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            status = subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(revision.returncode, 0, revision.stderr)
            self.assertEqual(status.stdout, "")

    def test_setup_does_not_commit_changes_in_an_existing_gtd_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "job-utils"
            root.mkdir()
            repo = Path(directory) / "gtd"
            self._init_git(repo)
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "Test User"],
                check=True,
                stdout=subprocess.PIPE,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
                check=True,
                stdout=subprocess.PIPE,
            )
            (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo), "add", "seed.txt"],
                check=True,
                stdout=subprocess.PIPE,
            )
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            (repo / "local.md").write_text("local\n", encoding="utf-8")

            run_setup(
                root,
                repo,
                platform_name="macos",
                skip_env_prompt=True,
                home=Path(directory) / "home",
            )

            status = subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertIn("?? local.md", status.stdout)

    def test_setup_commits_bootstrap_changes_when_existing_repository_is_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "job-utils"
            root.mkdir()
            repo = Path(directory) / "gtd"
            self._init_git(repo)
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "Test User"],
                check=True,
                stdout=subprocess.PIPE,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
                check=True,
                stdout=subprocess.PIPE,
            )
            (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo), "add", "seed.txt"],
                check=True,
                stdout=subprocess.PIPE,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "commit",
                    "-m",
                    "seed",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            run_setup(
                root,
                repo,
                platform_name="macos",
                skip_env_prompt=True,
                home=Path(directory) / "home",
            )

            commits = subprocess.run(
                ["git", "-C", str(repo), "log", "--format=%s", "-2"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            status = subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(commits.returncode, 0, commits.stderr)
            self.assertEqual(commits.stdout.splitlines()[0], "chore: initialize GTD repository")
            self.assertEqual(status.stdout, "")

    def test_setup_records_failed_step_for_resumable_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "job-utils"
            root.mkdir()
            repo = Path(directory) / "gtd"
            self._init_git(repo)
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

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.gitops import GitOperationError, commit, push_mock, status
from jobutils.cli import main


class GitOpsTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "local-test"],
            cwd=self.repo,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Job Utils Test"],
            cwd=self.repo,
            check=True,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_commit_records_local_change_without_push(self):
        (self.repo / "note.md").write_text("local\n", encoding="utf-8")

        result = commit(self.repo, "test: save local note")

        self.assertEqual(len(result["revision"]), 40)
        self.assertEqual(status(self.repo), "")
        self.assertTrue((self.repo / ".jobutils/metrics/events").exists())

    def test_credential_shaped_file_is_rejected_before_commit(self):
        (self.repo / ".env").write_text("TOKEN=secret\n", encoding="utf-8")

        with self.assertRaises(GitOperationError):
            commit(self.repo, "test: reject secret")

        self.assertEqual(status(self.repo), "?? .env\n")

    def test_push_mock_never_requires_a_remote_or_performs_push(self):
        (self.repo / "note.md").write_text("local\n", encoding="utf-8")
        committed = commit(self.repo, "test: prepare mock push")

        result = push_mock(self.repo, remote_url="mock://github/test")

        self.assertFalse(result["performed"])
        self.assertEqual(result["remote_url"], "mock://github/test")
        self.assertEqual(result["revision"], committed["revision"])
        self.assertEqual(result["command"][:2], ["git", "push"])
        self.assertEqual(status(self.repo), "")

    def test_cli_exposes_local_commit_and_push_simulation(self):
        (self.repo / "note.md").write_text("local\n", encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(
                main(
                    [
                        "git",
                        "commit",
                        "--repo",
                        str(self.repo),
                        "--message",
                        "test: cli commit",
                    ]
                ),
                0,
            )
        revision = json.loads(output.getvalue())["revision"]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(
                main(
                    [
                        "git",
                        "push-mock",
                        "--repo",
                        str(self.repo),
                        "--remote-url",
                        "mock://github/test",
                    ]
                ),
                0,
            )
        pushed = json.loads(output.getvalue())
        self.assertEqual(pushed["revision"], revision)
        self.assertFalse(pushed["performed"])


if __name__ == "__main__":
    unittest.main()
import contextlib
import io
import json

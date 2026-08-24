import subprocess
import sys
import tempfile
import unittest
import os
from pathlib import Path


class SetupCliTests(unittest.TestCase):
    def test_setup_init_bootstraps_an_existing_local_git_repository(self):
        root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            job_utils = temp / "job-utils"
            job_utils.mkdir()
            gtd_repo = temp / "GTDMD"
            subprocess.run(["git", "init", str(gtd_repo)], check=True, stdout=subprocess.PIPE)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(root / "src")
            environment["HOME"] = str(temp / "home")
            environment["SHELL"] = "/bin/zsh"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "jobutils",
                    "setup",
                    "init",
                    "--job-utils-root",
                    str(root),
                    "--gtd-repo",
                    str(gtd_repo),
                    "--skip-env-prompt",
                ],
                cwd=str(root),
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue((gtd_repo / "gtd.md").is_file())
            self.assertTrue((gtd_repo / "docs.md").is_file())

    def test_setup_init_rejects_missing_repository(self):
        root = Path(__file__).parents[1]
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(root / "src")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "jobutils",
                "setup",
                "init",
                "--job-utils-root",
                str(root),
                "--gtd-repo",
                "/private/tmp/jobutils-setup-path-that-does-not-exist",
                "--skip-env-prompt",
            ],
            cwd=str(root),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Git Repository", result.stdout)


if __name__ == "__main__":
    unittest.main()

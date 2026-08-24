import os
import subprocess
import tempfile
import unittest
import venv
from pathlib import Path


class InstallTests(unittest.TestCase):
    def test_editable_install_works_with_bundled_python_tooling(self):
        """A fresh host can install the checkout without downloading build tools."""

        root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as directory:
            environment = Path(directory) / "venv"
            venv.EnvBuilder(with_pip=True).create(environment)
            executable = (
                environment / "Scripts" / "python.exe"
                if os.name == "nt"
                else environment / "bin" / "python"
            )
            install = subprocess.run(
                [
                    str(executable),
                    "-m",
                    "pip",
                    "install",
                    "--no-deps",
                    "--editable",
                    str(root),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            result = subprocess.run(
                [str(executable), "-m", "jobutils", "--help"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertIn("usage:", result.stdout)
            profile = Path(directory) / "config.yaml"
            profile.write_text(
                """version: 1

jira:
  base_url: https://example.invalid
  project: LIG
  issue_type: Task
  email_env: JIRA_EMAIL
  token_env: JIRA_API_TOKEN

confluence:
  base_url: https://example.invalid
  space_id: '163844'
  space_key: KB
  parent_page_id: '210632708'
  email_env: CONFLUENCE_EMAIL
  token_env: CONFLUENCE_API_TOKEN
""",
                encoding="utf-8",
            )
            config = subprocess.run(
                [
                    str(executable),
                    "-m",
                    "jobutils",
                    "config",
                    "validate",
                    "--path",
                    str(profile),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertIn("config valid:", config.stdout)

    @unittest.skipIf(os.name == "nt", "POSIX wrapper is not used on Windows")
    def test_checkout_wrapper_falls_back_to_python3(self):
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment["PATH"] = "/usr/bin:/bin"
        result = subprocess.run(
            [str(Path(__file__).parents[1] / "scripts" / "jobutils"), "--help"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=environment,
        )
        self.assertIn("usage:", result.stdout)


if __name__ == "__main__":
    unittest.main()

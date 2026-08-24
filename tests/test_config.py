import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.config import load_config, validate_config


class ConfigTests(unittest.TestCase):
    def test_loads_and_validates_destination_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                """version: 1

jira:
  base_url: https://example.invalid
  project: LIG
  issue_type: Task
  email_env: JIRA_EMAIL
  token_env: JIRA_API_TOKEN

confluence:
  base_url: https://example.invalid
  space_id: '123'
  space_key: KB
  parent_page_id: '456'
  email_env: CONFLUENCE_EMAIL
  token_env: CONFLUENCE_API_TOKEN
""",
                encoding="utf-8",
            )
            self.assertEqual(validate_config(path), [])
            self.assertEqual(load_config(path)["jira"]["project"], "LIG")

    def test_reports_missing_required_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("version: 1\njira:\n  project: LIG\n", encoding="utf-8")
            errors = validate_config(path)
            self.assertIn("missing section: confluence", errors)
            self.assertIn("missing jira.base_url", errors)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path


class SetupDocumentationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parents[1]

    def test_setup_documents_keep_data_repository_separate(self):
        setup = (self.root / "docs/setup/README.md").read_text(encoding="utf-8")
        self.assertIn("GTD Markdown Repository", setup)
        self.assertIn("existing local Git repository", setup)
        self.assertIn("jobutils-activate", setup)
        self.assertIn(".jobutils/setup/", setup)

    def test_setup_entrypoints_and_environment_reference_are_documented(self):
        setup = (self.root / "docs/setup/README.md").read_text(encoding="utf-8")
        usage = (self.root / "docs/usage/README.md").read_text(encoding="utf-8")
        variables = (self.root / "docs/setup/environment-variables.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("scripts/setup.sh", setup)
        self.assertIn("scripts\\setup.ps1", setup)
        self.assertNotIn("jobutils serve", setup)
        self.assertNotIn(":GtdStart", usage)
        self.assertNotIn(":GtdStop", usage)
        self.assertNotIn(":GtdGitPush", usage)
        self.assertIn(":GtdSyncCheck", usage)
        self.assertIn(":GtdSyncUpdate", usage)
        self.assertIn(":GtdSyncPlan", usage)
        self.assertIn(":GtdSyncApply", usage)
        self.assertNotIn("sync pull", usage)
        self.assertIn("GitHub", usage)
        self.assertIn("Jira", usage)
        self.assertIn("Confluence", usage)
        self.assertIn("JIRA_API_TOKEN", variables)
        self.assertIn("CONFLUENCE_PARENT_ID", variables)

    def test_skill_catalog_is_documentation_only(self):
        catalog = (self.root / "docs/skills/README.md").read_text(encoding="utf-8")
        self.assertIn("No skill is installed", catalog)
        self.assertNotIn("pip install", catalog)


if __name__ == "__main__":
    unittest.main()

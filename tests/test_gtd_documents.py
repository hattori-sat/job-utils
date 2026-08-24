import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.gtd import create_document


class GtdDocumentTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_create_document_from_docs_index(self):
        (self.repo / "docs.md").write_text(
            "# Documents\n\n- Delivery guide\n", encoding="utf-8"
        )
        path = create_document(self.repo, 3)
        self.assertTrue(path.is_file())
        self.assertIn("kind: 'document'", path.read_text(encoding="utf-8"))
        self.assertIn("documents/", (self.repo / "docs.md").read_text(encoding="utf-8"))

    def test_existing_document_link_is_reused(self):
        path = self.repo / "documents" / "guide.md"
        path.parent.mkdir()
        path.write_text("---\nkind: 'document'\n---\n", encoding="utf-8")
        (self.repo / "docs.md").write_text(
            "# Documents\n\n- Delivery guide <documents/guide.md>\n",
            encoding="utf-8",
        )
        self.assertEqual(create_document(self.repo, 3), path.resolve())


if __name__ == "__main__":
    unittest.main()

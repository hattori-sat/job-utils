import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.gtd.documents import create_document, create_subdocument


class GtdDocumentTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        (self.repo / "documents").mkdir()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_document_template_contains_confluence_identity_fields(self):
        (self.repo / "docs.md").write_text("# Documents\n\n- Design notes\n", encoding="utf-8")

        path = create_document(self.repo, 3)

        text = path.read_text(encoding="utf-8")
        self.assertIn("publish_confluence: false", text)
        self.assertIn("confluence_parent_id: null", text)
        self.assertIn("confluence_page_id: null", text)
        self.assertIn("# Subdocuments", text)
        self.assertIn("# Implementation Note", text)

    def test_document_template_materializes_non_secret_confluence_defaults(self):
        (self.repo / "docs.md").write_text("# Documents\n\n- Design notes\n", encoding="utf-8")

        with patch.dict(
            "os.environ",
            {
                "CONFLUENCE_SPACE_ID": "space-default",
                "CONFLUENCE_SPACE_KEY": "DOC",
                "CONFLUENCE_PARENT_ID": "page-default",
            },
            clear=False,
        ):
            path = create_document(self.repo, 3)

        text = path.read_text(encoding="utf-8")
        self.assertIn("confluence_space_id: 'space-default'", text)
        self.assertIn("confluence_space_key: 'DOC'", text)
        self.assertIn("confluence_parent_id: 'page-default'", text)

    def test_subdocument_inherits_parent_relationship_and_publication(self):
        parent = self.repo / "documents" / "parent.md"
        parent.write_text(
            """---
gtd_id: 'parent-1'
kind: 'document'
title: 'Parent'
publish_confluence: true
confluence_page_id: 'page-parent'
confluence_space_id: 'space-1'
confluence_space_key: 'DOC'
confluence_parent_id: null
---

# Parent

# Subdocuments

- Child notes

# Implementation Note

private
""",
            encoding="utf-8",
        )

        child = create_subdocument(self.repo, "documents/parent.md", 16)

        self.assertEqual(child.parent, parent.with_suffix("").resolve())
        child_text = child.read_text(encoding="utf-8")
        self.assertIn("parent_document_id: 'parent-1'", child_text)
        self.assertIn("publish_confluence: true", child_text)
        self.assertIn("confluence_parent_id: 'page-parent'", child_text)
        self.assertIn("confluence_parent_path: 'documents/parent.md'", child_text)
        self.assertIn(
            str(child.relative_to(self.repo.resolve())).replace("\\", "/"),
            parent.read_text(encoding="utf-8"),
        )

        child_text = child.read_text(encoding="utf-8").replace(
            "# Subdocuments\n\n\n\n# Implementation Note",
            "# Subdocuments\n\n- Grandchild notes\n\n# Implementation Note",
        )
        child.write_text(child_text, encoding="utf-8")
        grandchild_line = child_text.splitlines().index("- Grandchild notes") + 1
        grandchild = create_subdocument(
            self.repo,
            str(child.relative_to(self.repo.resolve())).replace("\\", "/"),
            grandchild_line,
        )
        self.assertIn(
            "parent_document_id: ", grandchild.read_text(encoding="utf-8")
        )


if __name__ == "__main__":
    unittest.main()

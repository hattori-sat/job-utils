import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.cli import main
from jobutils.markdown.normalize import markdown_to_storage, parse_document
from jobutils.sync.adapters import MemoryAdapter
from jobutils.sync.engine import SyncError, apply_plan, create_plan, pull, sync_status
from jobutils.sync.references import externalize_references


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        (self.repo / "documents").mkdir()
        (self.repo / "gtd_tasks").mkdir()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_plan_and_apply_exclude_implementation_notes(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            """---
gtd_id: 'doc-1'
kind: 'document'
title: 'Guide'
publish_confluence: 'true'
confluence_space_id: 'space-1'
confluence_space_key: 'DOC'
---

# Guide

Visible content.

# Implementation Note

Private content.
""",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        self.assertEqual(len(plan["actions"]), 1)
        self.assertNotIn(
            "Private content", plan["actions"][0]["payload"]["storage_body"]
        )
        adapter = MemoryAdapter()
        result = apply_plan(self.repo, plan, adapter)
        self.assertEqual(len(result), 1)
        updated = path.read_text(encoding="utf-8")
        self.assertIn("confluence_page_id:", updated)
        self.assertIn("confluence_url:", updated)

    def test_stale_plan_is_rejected(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            """---
gtd_id: 'doc-1'
kind: 'document'
title: 'Guide'
publish_confluence: 'true'
---

# Guide
""",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        path.write_text(
            path.read_text(encoding="utf-8") + "\nChanged.\n", encoding="utf-8"
        )
        with self.assertRaises(SyncError):
            apply_plan(self.repo, plan, MemoryAdapter())

    def test_markdown_renderer_keeps_authoring_model(self):
        rendered = markdown_to_storage(
            "# Title\n\n:::confluence-macro name=info\nBody\n:::\n"
        )
        self.assertIn("<h1>Title</h1>", rendered)
        self.assertIn("ac:structured-macro", rendered)
        document = self.repo / "documents" / "guide.md"
        document.write_text(
            "---\nkind: 'document'\ntitle: 'Guide'\n---\n\n# Guide\n", encoding="utf-8"
        )
        self.assertEqual(parse_document(str(document)).metadata["kind"], "document")

    def test_pull_marks_two_sided_change_for_vim_resolution(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            """---
gtd_id: 'doc-1'
kind: 'document'
title: 'Guide'
publish_confluence: 'true'
---

# Guide

Base content.
""",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        adapter = MemoryAdapter()
        apply_plan(self.repo, plan, adapter)
        path.write_text(
            path.read_text(encoding="utf-8").replace("Base content.", "Local content."),
            encoding="utf-8",
        )
        record = next(iter(adapter.records.values()))
        record["payload"]["storage_body"] = "<h1>Guide</h1><p>Remote content.</p>"
        result = pull(self.repo, adapter)
        self.assertTrue(result[0]["conflict"])
        merged = path.read_text(encoding="utf-8")
        self.assertIn("<<<<<<< local", merged)
        self.assertIn(">>>>>>> external", merged)

    def test_relative_reference_uses_published_external_url(self):
        target = self.repo / "documents" / "target.md"
        target.write_text(
            "---\nkind: 'document'\nconfluence_url: 'https://example.invalid/page'\n---\n\n# Target\n",
            encoding="utf-8",
        )
        source = self.repo / "gtd_tasks" / "task.md"
        source.write_text(
            "---\nkind: 'task'\n---\n\n[Target](../documents/target.md)\n",
            encoding="utf-8",
        )
        rendered = externalize_references(
            self.repo, "[Target](../documents/target.md)", source
        )
        self.assertEqual(rendered, "[Target](https://example.invalid/page)")

    def test_jira_payload_keeps_progress_comment_as_configured_text_field(self):
        path = self.repo / "gtd_tasks" / "task.md"
        path.write_text(
            """---
gtd_id: 'task-1'
kind: 'task'
title: 'Task'
publish_jira: 'true'
jira_project: 'JOB'
jira_progress_comment_field: 'customfield_12345'
---

# Summary

Summary.

# Progress Comment

2026-08-23: completed the first review.

# Objective

Objective.
""",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        payload = plan["actions"][0]["payload"]
        self.assertEqual(payload["progress_comment_field"], "customfield_12345")
        self.assertIn("2026-08-23", payload["progress_comment"])

    def test_sync_status_reports_local_state(self):
        plans = self.repo / ".jobutils" / "sync" / "plans"
        bases = self.repo / ".jobutils" / "sync" / "bases"
        plans.mkdir(parents=True)
        bases.mkdir(parents=True)
        action = {
            "action_id": "action-1",
            "action": "create",
            "kind": "confluence",
            "path": "documents/guide.md",
            "external_id": None,
            "payload": {},
        }
        (plans / "plan-1.json").write_text(
            json.dumps(
                {
                    "plan_id": "plan-1",
                    "created_at": "2026-08-25T10:00:00Z",
                    "source_hash": "0" * 64,
                    "actions": [action, dict(action, action_id="action-2")],
                }
            ),
            encoding="utf-8",
        )
        (plans / "plan-2.json").write_text(
            json.dumps(
                {
                    "plan_id": "plan-2",
                    "created_at": "2026-08-24T10:00:00Z",
                    "source_hash": "1" * 64,
                    "actions": [
                        action,
                        dict(action, action_id="action-2"),
                        dict(action, action_id="action-3"),
                    ],
                }
            ),
            encoding="utf-8",
        )
        (plans / "plan-3.json").write_text(
            '{"source_hash": "invalid", "actions": "not-a-list"}\n',
            encoding="utf-8",
        )
        os.utime(plans / "plan-1.json", (100, 100))
        os.utime(plans / "plan-2.json", (200, 200))
        os.utime(plans / "plan-3.json", (300, 300))
        (bases / "base-1.md").write_text("# Base\n", encoding="utf-8")
        (self.repo / "documents" / "guide.md").write_text(
            "---\nkind: document\n---\n\n<<<<<<< local\nLocal\n=======\nRemote\n>>>>>>> external\n",
            encoding="utf-8",
        )

        expected = {
            "base_count": 1,
            "conflict_count": 1,
            "latest_plan": ".jobutils/sync/plans/plan-2.json",
            "pending_actions": 3,
            "plan_count": 2,
        }
        self.assertEqual(sync_status(self.repo), expected)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["sync", "status", "--repo", str(self.repo)]), 0)
        self.assertEqual(json.loads(output.getvalue()), expected)


if __name__ == "__main__":
    unittest.main()

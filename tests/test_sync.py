import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.cli import main
from jobutils.markdown.normalize import markdown_to_storage, parse_document
from jobutils.sync.adapters import MemoryAdapter
from jobutils.sync.engine import (
    SyncError,
    apply_plan,
    create_plan,
    pull,
    rebind,
    sync_status,
)
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

    def test_apply_creates_unpublished_confluence_parent_before_child(self):
        parent = self.repo / "documents" / "parent.md"
        child = parent.with_suffix("") / "child.md"
        child.parent.mkdir()
        parent.write_text(
            "---\ngtd_id: parent\nkind: document\ntitle: Parent\npublish_confluence: true\nconfluence_space_id: space-1\nconfluence_space_key: DOC\n---\n\n# Parent\n",
            encoding="utf-8",
        )
        child.write_text(
            "---\ngtd_id: child\nkind: document\ntitle: Child\npublish_confluence: true\nconfluence_space_id: space-1\nconfluence_space_key: DOC\nconfluence_parent_path: documents/parent.md\n---\n\n# Child\n",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        adapter = MemoryAdapter()

        apply_plan(self.repo, plan, adapter)

        child_record = next(
            record
            for record in adapter.records.values()
            if record["payload"]["title"] == "Child"
        )
        parent_record = next(
            record
            for record in adapter.records.values()
            if record["payload"]["title"] == "Parent"
        )
        self.assertEqual(child_record["payload"]["parent_id"], parent_record["url"].rsplit("/", 1)[-1])
        self.assertIn(
            "confluence_parent_id: 'MEM-1'",
            child.read_text(encoding="utf-8"),
        )

    def test_apply_rejects_unresolved_confluence_parent_before_child_write(self):
        child = self.repo / "documents" / "child.md"
        child.write_text(
            "---\ngtd_id: child\nkind: document\ntitle: Child\npublish_confluence: true\nconfluence_space_id: space-1\nconfluence_space_key: DOC\nconfluence_parent_path: documents/missing.md\n---\n\n# Child\n",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        adapter = MemoryAdapter()

        with self.assertRaisesRegex(SyncError, "parent page is unresolved"):
            apply_plan(self.repo, plan, adapter)
        self.assertEqual(adapter.records, {})

    def test_explicit_parent_path_never_falls_back_to_default_parent(self):
        child = self.repo / "documents" / "child.md"
        child.write_text(
            "---\ngtd_id: child\nkind: document\ntitle: Child\npublish_confluence: true\nconfluence_space_id: space-1\nconfluence_space_key: DOC\nconfluence_parent_path: documents/missing.md\n---\n\n# Child\n",
            encoding="utf-8",
        )
        with patch.dict(
            os.environ, {"CONFLUENCE_PARENT_ID": "default-parent"}, clear=False
        ):
            plan = create_plan(self.repo)
        with self.assertRaisesRegex(SyncError, "parent page is unresolved"):
            apply_plan(self.repo, plan, MemoryAdapter())

    def test_explicit_parent_paths_are_applied_in_dependency_order(self):
        parent = self.repo / "documents" / "parent.md"
        child = self.repo / "documents" / "child.md"
        parent.write_text(
            "---\nkind: document\ntitle: Parent\npublish_confluence: true\n---\n\n# Parent\n",
            encoding="utf-8",
        )
        child.write_text(
            "---\nkind: document\ntitle: Child\npublish_confluence: true\nconfluence_parent_path: documents/parent.md\n---\n\n# Child\n",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        self.assertEqual(
            [action["path"] for action in plan["actions"]],
            ["documents/parent.md", "documents/child.md"],
        )

    def test_cyclic_confluence_parent_paths_are_rejected(self):
        for name, parent_path in (("a", "documents/b.md"), ("b", "documents/a.md")):
            (self.repo / "documents" / (name + ".md")).write_text(
                "---\nkind: document\ntitle: {}\npublish_confluence: true\nconfluence_parent_path: {}\n---\n\n# {}\n".format(
                    name, parent_path, name
                ),
                encoding="utf-8",
            )
        with self.assertRaisesRegex(SyncError, "cyclic Confluence"):
            create_plan(self.repo)

    def test_plan_infers_document_parent_from_recursive_path(self):
        parent = self.repo / "documents" / "parent.md"
        child = parent.with_suffix("") / "child.md"
        child.parent.mkdir()
        parent.write_text(
            "---\nkind: document\ntitle: Parent\npublish_confluence: true\n---\n\n# Parent\n",
            encoding="utf-8",
        )
        child.write_text(
            "---\nkind: document\ntitle: Child\npublish_confluence: true\n---\n\n# Child\n",
            encoding="utf-8",
        )

        plan = create_plan(self.repo)

        child_action = next(
            action for action in plan["actions"] if action["path"] == "documents/parent/child.md"
        )
        self.assertEqual(child_action["parent_path"], "documents/parent.md")

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

    def test_public_payloads_support_blocks_without_private_content(self):
        document = self.repo / "documents" / "guide.md"
        document.write_text(
            """---
gtd_id: 'doc-1'
kind: 'document'
title: 'Guide'
publish_confluence: true
confluence_space_id: space-1
confluence_space_key: DOC
---

# Guide

| Name | Value |
| --- | --- |
| A | 1 |

[Private reference](documents/secret.md)
[Public reference](https://example.com/public)

# Implementation Note

private-token
""",
            encoding="utf-8",
        )
        task = self.repo / "gtd_tasks" / "task.md"
        task.write_text(
            """---
gtd_id: 'task-1'
kind: 'task'
title: 'Task'
publish_jira: true
jira_project: DEMO
---

# Summary

- one
- two

[Public task reference](https://example.com/public)

# Implementation Note

private-task-note
""",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        by_kind = {action["kind"]: action["payload"] for action in plan["actions"]}
        confluence_body = by_kind["confluence"]["storage_body"]
        jira_body = by_kind["jira"]["description_adf"]
        serialized_jira = json.dumps(jira_body, sort_keys=True)
        for value in (confluence_body, serialized_jira):
            self.assertNotIn("private-token", value)
            self.assertNotIn("private-task-note", value)
            self.assertNotIn("documents/secret.md", value)
        self.assertIn("https://example.com/public", confluence_body)
        self.assertIn("https://example.com/public", serialized_jira)
        self.assertIn("<th>Name</th>", confluence_body)
        self.assertEqual(jira_body["content"][0]["type"], "heading")
        self.assertEqual(jira_body["content"][1]["type"], "bulletList")

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

    def test_sync_payload_uses_environment_defaults_for_missing_front_matter(self):
        jira = self.repo / "gtd_tasks" / "task.md"
        jira.write_text(
            "---\ngtd_id: task-1\nkind: task\ntitle: Task\npublish_jira: true\n---\n\n# Summary\n",
            encoding="utf-8",
        )
        document = self.repo / "documents" / "guide.md"
        document.write_text(
            "---\ngtd_id: doc-1\nkind: document\ntitle: Guide\npublish_confluence: true\n---\n\n# Guide\n",
            encoding="utf-8",
        )
        defaults = {
            "JIRA_PROJECT": "LCL",
            "JIRA_ISSUE_TYPE": "Story",
            "JIRA_PROGRESS_COMMENT_FIELD": "customfield_progress",
            "CONFLUENCE_SPACE_ID": "space-local",
            "CONFLUENCE_SPACE_KEY": "DOCS",
            "CONFLUENCE_PARENT_ID": "parent-local",
        }
        with patch.dict(os.environ, defaults, clear=False):
            plan = create_plan(self.repo)
        by_kind = {action["kind"]: action["payload"] for action in plan["actions"]}
        self.assertEqual(by_kind["jira"]["project"], "LCL")
        self.assertEqual(by_kind["jira"]["issue_type"], "Story")
        self.assertEqual(
            by_kind["jira"]["progress_comment_field"], "customfield_progress"
        )
        self.assertEqual(by_kind["confluence"]["space_id"], "space-local")
        self.assertEqual(by_kind["confluence"]["space_key"], "DOCS")
        self.assertEqual(by_kind["confluence"]["parent_id"], "parent-local")

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
            "payload": {
                "title": "Guide",
                "storage_body": "<h1>Guide</h1>",
                "space_id": "space-1",
                "space_key": "KB",
                "version": 0,
            },
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

    def test_apply_plan_rejects_paths_outside_managed_roots(self):
        document = self.repo / "documents" / "guide.md"
        document.write_text(
            "---\nkind: document\ntitle: Guide\npublish_confluence: true\n---\n\n# Guide\n",
            encoding="utf-8",
        )
        plan = create_plan(self.repo)
        plan["actions"][0]["path"] = "../outside.md"

        with self.assertRaisesRegex(SyncError, "invalid structure"):
            apply_plan(self.repo, plan, MemoryAdapter())

    def test_rebind_updates_jira_identity_without_external_write(self):
        path = self.repo / "gtd_tasks" / "task.md"
        path.write_text(
            "---\ngtd_id: task-1\nkind: task\npublish_jira: true\njira_key: null\njira_url: null\n---\n\n# Summary\n",
            encoding="utf-8",
        )

        result = rebind(
            self.repo,
            "gtd_tasks/task.md",
            "jira",
            "LIG-42",
            "https://example.invalid/browse/LIG-42",
        )

        self.assertEqual(result, path.resolve())
        text = path.read_text(encoding="utf-8")
        self.assertIn("jira_key: 'LIG-42'", text)
        self.assertIn("jira_url: 'https://example.invalid/browse/LIG-42'", text)

    def test_rebind_updates_confluence_page_and_parent_identity(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\ngtd_id: doc-1\nkind: document\npublish_confluence: true\nconfluence_page_id: null\nconfluence_url: null\nconfluence_parent_id: null\n---\n\n# Guide\n",
            encoding="utf-8",
        )

        rebind(
            self.repo,
            "documents/guide.md",
            "confluence",
            "210632708",
            "https://example.invalid/wiki/pages/210632708",
            "parent-9",
        )

        text = path.read_text(encoding="utf-8")
        self.assertIn("confluence_page_id: '210632708'", text)
        self.assertIn(
            "confluence_url: 'https://example.invalid/wiki/pages/210632708'", text
        )
        self.assertIn("confluence_parent_id: 'parent-9'", text)

    def test_rebind_rejects_invalid_target_before_mutation(self):
        path = self.repo / "documents" / "guide.md"
        original = "---\nkind: document\nconfluence_page_id: null\n---\n\n# Guide\n"
        path.write_text(original, encoding="utf-8")

        with self.assertRaisesRegex(SyncError, "unsafe external URL"):
            rebind(
                self.repo,
                "documents/guide.md",
                "confluence",
                "page-1",
                "javascript:alert(1)",
            )
        with self.assertRaisesRegex(SyncError, "unsafe external URL"):
            rebind(
                self.repo,
                "documents/guide.md",
                "confluence",
                "page-1",
                "https://user:secret@example.invalid/page-1",
            )

        self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_rebind_rejects_unmanaged_or_unsafe_paths(self):
        with self.assertRaisesRegex(SyncError, "unsafe Markdown path"):
            rebind(self.repo, "README.md", "jira", "LIG-42")
        with self.assertRaisesRegex(SyncError, "unsafe Markdown path"):
            rebind(self.repo, "../outside.md", "jira", "LIG-42")

    def test_rebind_cli_updates_the_requested_file(self):
        path = self.repo / "documents" / "guide.md"
        path.write_text(
            "---\nkind: document\nconfluence_page_id: null\n---\n\n# Guide\n",
            encoding="utf-8",
        )

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(
                main(
                    [
                        "sync",
                        "rebind",
                        "--repo",
                        str(self.repo),
                        "--path",
                        "documents/guide.md",
                        "--kind",
                        "confluence",
                        "--external-id",
                        "210632708",
                    ]
                ),
                0,
            )
        self.assertIn("documents/guide.md", output.getvalue())
        self.assertIn("confluence_page_id: '210632708'", path.read_text())

    def test_jira_parent_is_resolved_when_parent_is_created_in_same_plan(self):
        parent = self.repo / "gtd_tasks" / "parent.md"
        child = parent.with_suffix("") / "child.md"
        child.parent.mkdir()
        parent.write_text(
            "---\ngtd_id: parent\nkind: task\ntitle: Parent\npublish_jira: true\njira_project: LIG\n---\n\n# Summary\nParent\n",
            encoding="utf-8",
        )
        child.write_text(
            "---\ngtd_id: child\nkind: task\ntitle: Child\npublish_jira: true\njira_project: LIG\njira_issue_type: Sub-task\njira_parent_path: gtd_tasks/parent.md\njira_parent_key: null\n---\n\n# Summary\nChild\n",
            encoding="utf-8",
        )

        plan = create_plan(self.repo)
        self.assertEqual(
            [action["path"] for action in plan["actions"]],
            ["gtd_tasks/parent.md", "gtd_tasks/parent/child.md"],
        )
        adapter = MemoryAdapter()
        apply_plan(self.repo, plan, adapter)

        child_record = next(
            record
            for record in adapter.records.values()
            if record["payload"]["title"] == "Child"
        )
        parent_record = next(
            record
            for record in adapter.records.values()
            if record["payload"]["title"] == "Parent"
        )
        self.assertEqual(
            child_record["payload"]["parent_key"],
            parent_record["url"].rsplit("/", 1)[-1],
        )

    def test_jira_parent_path_without_parent_identity_fails_before_child_write(self):
        child = self.repo / "gtd_tasks" / "child.md"
        child.write_text(
            "---\ngtd_id: child\nkind: task\ntitle: Child\npublish_jira: true\njira_project: LIG\njira_parent_path: gtd_tasks/missing.md\njira_parent_key: null\n---\n\n# Summary\nChild\n",
            encoding="utf-8",
        )
        adapter = MemoryAdapter()

        with self.assertRaisesRegex(SyncError, "Jira parent issue is unresolved"):
            apply_plan(self.repo, create_plan(self.repo), adapter)
        self.assertEqual(adapter.records, {})

    def test_cyclic_jira_parent_paths_are_rejected(self):
        for name, parent_path in (
            ("a", "gtd_tasks/b.md"),
            ("b", "gtd_tasks/a.md"),
        ):
            (self.repo / "gtd_tasks" / (name + ".md")).write_text(
                "---\nkind: task\ntitle: {}\npublish_jira: true\njira_parent_path: {}\n---\n\n# Summary\n{}\n".format(
                    name, parent_path, name
                ),
                encoding="utf-8",
            )

        with self.assertRaisesRegex(SyncError, "cyclic Jira"):
            create_plan(self.repo)

    def test_sync_status_ignores_symlinked_plans(self):
        plans = self.repo / ".jobutils" / "sync" / "plans"
        plans.mkdir(parents=True)
        target = plans / "real.json"
        target.write_text(
            json.dumps(
                {
                    "plan_id": "real",
                    "created_at": "2026-08-25T10:00:00Z",
                    "source_hash": "0" * 64,
                    "actions": [],
                }
            ),
            encoding="utf-8",
        )
        try:
            (plans / "link.json").symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available")
        status = sync_status(self.repo)
        self.assertEqual(status["plan_count"], 1)
        self.assertEqual(status["latest_plan"], ".jobutils/sync/plans/real.json")


if __name__ == "__main__":
    unittest.main()

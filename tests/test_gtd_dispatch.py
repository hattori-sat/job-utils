import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.gtd import DispatchError, create_subtask, create_task, dispatch


class GtdDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def write_gtd(self, content):
        (self.repo / "gtd.md").write_text(content, encoding="utf-8")

    def test_dispatch_moves_items_without_creating_task_details(self):
        self.write_gtd(
            """# GTD

## Inbox

- Capture an idea

## Today

- focus: Read the design
"""
        )
        result = dispatch(self.repo)
        self.assertEqual(result.moved, 1)
        self.assertEqual(result.created, [])
        self.assertEqual(result.event_count, 0)
        gtd = (self.repo / "gtd.md").read_text(encoding="utf-8")
        self.assertIn("## Focus", gtd)
        self.assertNotIn("## Today\n\n- focus:", gtd)
        self.assertIn("- focus: Read the design", gtd)
        self.assertFalse((self.repo / "gtd_tasks").exists())

    def test_focus_overflow_is_atomic(self):
        lines = ["# GTD", "", "## Focus", ""]
        lines.extend("- focus: item {}".format(index) for index in range(1, 5))
        lines.extend(["", "## Next Actions", "", "- next: another item"])
        self.write_gtd("\n".join(lines) + "\n")
        before = (self.repo / "gtd.md").read_bytes()
        with self.assertRaises(DispatchError):
            dispatch(self.repo)
        self.assertEqual(before, (self.repo / "gtd.md").read_bytes())
        self.assertFalse((self.repo / "gtd_tasks").exists())

    def test_inbox_prefix_is_a_valid_destination(self):
        self.write_gtd("# GTD\n\n## Today\n\n- inbox: return to inbox\n")
        result = dispatch(self.repo)
        self.assertEqual(result.moved, 1)
        gtd = (self.repo / "gtd.md").read_text(encoding="utf-8")
        self.assertIn("## Inbox\n\n- inbox: return to inbox", gtd)
        self.assertFalse((self.repo / "gtd_tasks").exists())

    def test_arbitrary_transition_updates_detail_and_event(self):
        self.write_gtd("# GTD\n\n## Today\n\n- focus: Work <gtd_tasks/task.md>\n")
        detail = self.repo / "gtd_tasks" / "task.md"
        detail.parent.mkdir()
        detail.write_text(
            """---
gtd_id: 'task-1'
prefix: 'today'
status: 'in_progress'
title: 'Work'
---

# Work
""",
            encoding="utf-8",
        )
        self.write_gtd("# GTD\n\n## Today\n\n- focus: Work <gtd_tasks/task.md>\n")
        result = dispatch(self.repo, machine_id="test-machine")
        self.assertEqual(result.event_count, 1)
        detail_text = detail.read_text(encoding="utf-8")
        self.assertIn("prefix: 'focus'", detail_text)
        self.assertIn("status: 'active'", detail_text)
        event_files = list((self.repo / ".jobutils/metrics/events").glob("*.jsonl"))
        self.assertEqual(len(event_files), 1)
        event = json.loads(event_files[0].read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(event["from"]["prefix"], "today")
        self.assertEqual(event["to"]["prefix"], "focus")

    def test_state_event_keeps_estimate_and_kind_for_metrics(self):
        self.write_gtd("# GTD\n\n## Today\n\n- focus: Work <gtd_tasks/task.md>\n")
        detail = self.repo / "gtd_tasks" / "task.md"
        detail.parent.mkdir()
        detail.write_text(
            """---
gtd_id: 'task-1'
kind: 'task'
prefix: 'today'
status: 'in_progress'
title: 'Work'
estimate_minutes: 45
tags: [implementation]
impact_level: medium
---

# Work
""",
            encoding="utf-8",
        )

        dispatch(self.repo, machine_id="test-machine")

        event_file = next((self.repo / ".jobutils/metrics/events").glob("*.jsonl"))
        event = json.loads(event_file.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(event["kind"], "task")
        self.assertEqual(event["estimate_minutes"], "45")
        self.assertEqual(event["tags"], ["implementation"])

    def test_create_task_returns_existing_link(self):
        self.write_gtd("# GTD\n\n## Next Actions\n\n- next: Work\n")
        path = create_task(self.repo, 5)
        self.assertTrue(path.is_file())
        second = create_task(self.repo, 5)
        self.assertEqual(path, second)

    def test_dispatch_does_not_capture_unlinked_item(self):
        self.write_gtd("# GTD\n\n## Next Actions\n\n- next: New work\n")
        result = dispatch(self.repo)
        self.assertEqual(result.event_count, 0)
        self.assertFalse((self.repo / ".jobutils/metrics/events").exists())

    def test_create_task_is_explicit_markdown_creation_boundary(self):
        self.write_gtd("# GTD\n\n## Next Actions\n\n- next: New work\n")
        path = create_task(self.repo, 5)
        self.assertTrue(path.is_file())
        self.assertIn(
            str(path.relative_to(self.repo.resolve())).replace("\\", "/"),
            (self.repo / "gtd.md").read_text(encoding="utf-8"),
        )
        event_file = next((self.repo / ".jobutils/metrics/events").glob("*.jsonl"))
        event = json.loads(event_file.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(event["event_type"], "captured")
        self.assertEqual(event["kind"], "task")

    def test_retry_repairs_a_missing_capture_event(self):
        self.write_gtd("# GTD\n\n## Next Actions\n\n- next: Recoverable work\n")
        path = create_task(self.repo, 5)
        event_file = next((self.repo / ".jobutils/metrics/events").glob("*.jsonl"))
        event_file.unlink()

        self.assertEqual(create_task(self.repo, 5), path)
        repaired = next((self.repo / ".jobutils/metrics/events").glob("*.jsonl"))
        event = json.loads(repaired.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(event["event_type"], "captured")
        self.assertEqual(event["kind"], "task")

    def test_created_task_exposes_jira_identity_and_publish_fields(self):
        self.write_gtd("# GTD\n\n## Next Actions\n\n- next: Publish me\n")
        path = create_task(self.repo, 5)
        text = path.read_text(encoding="utf-8")
        self.assertIn("publish_jira: false", text)
        self.assertIn("jira_issue_type: 'Task'", text)
        self.assertIn("jira_summary_field: 'summary'", text)
        self.assertIn("jira_description_field: 'description'", text)
        self.assertIn("jira_parent_key: null", text)
        self.assertIn("jira_key: null", text)
        self.assertIn("jira_url: null", text)

    def test_created_task_uses_configured_default_jira_issue_type(self):
        self.write_gtd("# GTD\n\n## Next Actions\n\n- next: Configured type\n")
        with patch.dict(os.environ, {"JIRA_ISSUE_TYPE": "Story"}, clear=False):
            path = create_task(self.repo, 5)
        self.assertIn("jira_issue_type: 'Story'", path.read_text(encoding="utf-8"))

    def test_create_subtask_under_parent_directory_and_links_jira_parent(self):
        self.write_gtd("# GTD\n\n## Next Actions\n\n- next: Child work\n")
        parent = self.repo / "gtd_tasks" / "parent.md"
        parent.parent.mkdir()
        parent.write_text(
            "---\ngtd_id: 'parent-1'\njira_key: 'DEMO-1'\n---\n\n# Parent\n",
            encoding="utf-8",
        )
        child = create_task(self.repo, 5, parent_path="gtd_tasks/parent.md")
        self.assertEqual(child.parent, parent.with_suffix("").resolve())
        child_text = child.read_text(encoding="utf-8")
        self.assertIn("parent_gtd_id: 'parent-1'", child_text)
        self.assertIn("jira_parent_key: 'DEMO-1'", child_text)
        self.assertEqual(child_text.count("jira_parent_key:"), 1)
        self.assertIn(
            str(child.relative_to(self.repo.resolve())).replace("\\", "/"),
            (self.repo / "gtd.md").read_text(encoding="utf-8"),
        )

    def test_create_subtask_from_parent_markdown_section(self):
        parent = self.repo / "gtd_tasks" / "parent.md"
        parent.parent.mkdir()
        parent.write_text(
            """---
gtd_id: 'parent-1'
jira_key: 'DEMO-1'
jira_project: 'DEMO'
publish_jira: true
prefix: 'today'
---

# Parent

# Subtasks

- next: Child from parent

# Implementation Note

private
""",
            encoding="utf-8",
        )
        child = create_subtask(self.repo, "gtd_tasks/parent.md", 13)
        child_text = child.read_text(encoding="utf-8")
        parent_text = parent.read_text(encoding="utf-8")
        self.assertEqual(child.parent, parent.with_suffix("").resolve())
        self.assertIn("parent_gtd_id: 'parent-1'", child_text)
        self.assertIn("jira_parent_key: 'DEMO-1'", child_text)
        self.assertIn("jira_issue_type: 'Sub-task'", child_text)
        self.assertIn("jira_project: 'DEMO'", child_text)
        self.assertIn("publish_jira: true", child_text)
        self.assertIn(
            "- next: Child from parent <{}>".format(
                str(child.relative_to(self.repo.resolve())).replace("\\", "/")
            ),
            parent_text,
        )

    def test_create_subtask_requires_the_subtasks_section(self):
        parent = self.repo / "gtd_tasks" / "parent.md"
        parent.parent.mkdir()
        parent.write_text(
            "---\ngtd_id: 'parent-1'\n---\n\n# Parent\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(DispatchError, "Subtasks"):
            create_subtask(self.repo, "gtd_tasks/parent.md", 6)

    def test_create_subtask_inherits_jira_publication_before_parent_key_exists(self):
        parent = self.repo / "gtd_tasks" / "parent.md"
        parent.parent.mkdir()
        parent.write_text(
            """---
gtd_id: 'parent-1'
publish_jira: true
jira_project: 'DEMO'
jira_key: null
---

# Parent

# Subtasks

- next: Child before parent publish

# Implementation Note
""",
            encoding="utf-8",
        )

        child = create_subtask(self.repo, "gtd_tasks/parent.md", 12)

        child_text = child.read_text(encoding="utf-8")
        self.assertIn("publish_jira: true", child_text)
        self.assertIn("jira_parent_key: null", child_text)
        self.assertIn("jira_parent_path: 'gtd_tasks/parent.md'", child_text)


if __name__ == "__main__":
    unittest.main()

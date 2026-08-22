import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.gtd import DispatchError, create_task, dispatch


class GtdDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def write_gtd(self, content):
        (self.repo / "gtd.md").write_text(content, encoding="utf-8")

    def test_dispatch_creates_uuid_detail_and_preserves_sections(self):
        self.write_gtd("""# GTD

## Inbox

- Capture an idea

## Today

- focus: Read the design
""")
        result = dispatch(self.repo)
        self.assertEqual(result.moved, 1)
        gtd = (self.repo / "gtd.md").read_text(encoding="utf-8")
        self.assertIn("## Focus", gtd)
        self.assertNotIn("## Today\n\n- focus:", gtd)
        details = list((self.repo / "gtd_tasks").glob("*.md"))
        self.assertEqual(len(details), 1)
        detail = details[0].read_text(encoding="utf-8")
        self.assertIn("kind: 'task'", detail)
        self.assertIn("prefix: 'focus'", detail)
        self.assertIn("# Implementation Note", detail)

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

    def test_inbox_prefix_is_rejected(self):
        self.write_gtd("# GTD\n\n## Today\n\n- inbox: never move here\n")
        with self.assertRaises(DispatchError):
            dispatch(self.repo)

    def test_arbitrary_transition_updates_detail_and_event(self):
        self.write_gtd("# GTD\n\n## Today\n\n- focus: Work <gtd_tasks/task.md>\n")
        detail = self.repo / "gtd_tasks" / "task.md"
        detail.parent.mkdir()
        detail.write_text("""---
gtd_id: 'task-1'
prefix: 'today'
status: 'in_progress'
title: 'Work'
---

# Work
""", encoding="utf-8")
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

    def test_create_task_returns_existing_link(self):
        self.write_gtd("# GTD\n\n## Next Actions\n\n- next: Work\n")
        path = create_task(self.repo, 5)
        self.assertTrue(path.is_file())
        second = create_task(self.repo, 5)
        self.assertEqual(path, second)


if __name__ == "__main__":
    unittest.main()

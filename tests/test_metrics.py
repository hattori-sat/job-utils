import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.metrics.aggregate import aggregate
from jobutils.metrics.reports import (
    build_report,
    csv_text,
    html_text,
    svg_text,
    write_reports,
)


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        event_dir = self.repo / ".jobutils/metrics/events"
        event_dir.mkdir(parents=True)
        events = [
            {
                "event_id": "1",
                "event_type": "state_changed",
                "occurred_at": "2026-01-01T09:00:00+00:00",
                "gtd_id": "task-1",
                "from": {"prefix": "next"},
                "to": {"prefix": "today"},
                "tags": ["delivery"],
                "impact_level": "high",
            },
            {
                "event_id": "2",
                "event_type": "state_changed",
                "occurred_at": "2026-01-01T10:00:00+00:00",
                "gtd_id": "task-1",
                "from": {"prefix": "today"},
                "to": {"prefix": "wait"},
            },
            {
                "event_id": "3",
                "event_type": "state_changed",
                "occurred_at": "2026-01-01T12:00:00+00:00",
                "gtd_id": "task-1",
                "from": {"prefix": "wait"},
                "to": {"prefix": "focus"},
            },
            {
                "event_id": "4",
                "event_type": "state_changed",
                "occurred_at": "2026-01-01T13:30:00+00:00",
                "gtd_id": "task-1",
                "from": {"prefix": "focus"},
                "to": {"prefix": "done"},
            },
        ]
        (event_dir / "2026.jsonl").write_text(
            "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_separates_active_and_waiting_time(self):
        report = build_report(self.repo, "2026-01-01", "2026-01-01")
        self.assertEqual(report["completed_count"], 1)
        task = report["tasks"][0]
        self.assertEqual(task["active_seconds"], 9000)
        self.assertEqual(task["waiting_seconds"], 7200)
        self.assertEqual(task["scheduled_seconds"], 0)
        self.assertEqual(task["cycle_seconds"], 16200)
        self.assertEqual(task["tags"], ["delivery"])
        self.assertEqual(task["impact_level"], "high")

    def test_reports_are_generated_on_demand(self):
        target = self.repo / "output"
        paths = write_reports(
            self.repo, "2026-01-01", "2026-01-01", ["html", "csv", "svg"], target
        )
        self.assertEqual({path.suffix for path in paths}, {".html", ".csv", ".svg"})
        self.assertIn(
            "task-1", csv_text(build_report(self.repo, "2026-01-01", "2026-01-01"))
        )
        self.assertIn(
            "<html", html_text(build_report(self.repo, "2026-01-01", "2026-01-01"))
        )
        self.assertIn(
            "<svg", svg_text(build_report(self.repo, "2026-01-01", "2026-01-01"))
        )

    def test_duplicate_event_ids_are_ignored(self):
        event_path = self.repo / ".jobutils/metrics/events/2026.jsonl"
        first = event_path.read_text(encoding="utf-8").splitlines()[0]
        event_path.write_text(
            event_path.read_text(encoding="utf-8") + first + "\n", encoding="utf-8"
        )
        report = build_report(self.repo, "2026-01-01", "2026-01-01")
        self.assertEqual(report["task_count"], 1)
        self.assertEqual(report["read_errors"], [])


if __name__ == "__main__":
    unittest.main()

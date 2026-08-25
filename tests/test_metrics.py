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
    json_text,
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
            self.repo, "2026-01-01", "2026-01-01", ["html", "csv", "svg", "json"], target
        )
        self.assertEqual(
            {path.suffix for path in paths}, {".html", ".csv", ".svg", ".json"}
        )
        self.assertIn(
            "task-1", csv_text(build_report(self.repo, "2026-01-01", "2026-01-01"))
        )
        self.assertIn(
            "<html", html_text(build_report(self.repo, "2026-01-01", "2026-01-01"))
        )
        self.assertIn("throughput-start", html_text(build_report(self.repo, "2026-01-01", "2026-01-01")))
        self.assertIn(
            "<svg", svg_text(build_report(self.repo, "2026-01-01", "2026-01-01"))
        )
        self.assertIn(
            '"task_count"', json_text(build_report(self.repo, "2026-01-01", "2026-01-01"))
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

    def test_read_errors_use_repository_relative_paths(self):
        event_path = self.repo / ".jobutils/metrics/events/2026.jsonl"
        event_path.write_text("not json\n", encoding="utf-8")
        report = build_report(self.repo, "2026-01-01", "2026-01-01")
        self.assertTrue(report["read_errors"])
        self.assertNotIn(str(self.repo), report["read_errors"][0])
        self.assertTrue(
            report["read_errors"][0].startswith(".jobutils/metrics/events/")
        )

    def test_invalid_event_timestamp_is_reported_without_breaking_reports(self):
        event_path = self.repo / ".jobutils/metrics/events/2026.jsonl"
        with event_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "event_id": "invalid-time",
                        "event_type": "state_changed",
                        "occurred_at": "not-a-timestamp",
                        "gtd_id": "broken-task",
                    }
                )
                + "\n"
            )

        report = build_report(self.repo, "2026-01-01", "2026-01-01")

        self.assertEqual(report["task_count"], 1)
        self.assertEqual(len(report["read_errors"]), 1)

    def test_reports_lead_cycle_estimate_and_grouped_throughput(self):
        event_path = self.repo / ".jobutils/metrics/events/2026.jsonl"
        event_path.write_text(
            "\n".join(
                json.dumps(event)
                for event in [
                    {
                        "event_id": "capture-2",
                        "event_type": "captured",
                        "occurred_at": "2026-01-01T08:00:00+00:00",
                        "gtd_id": "task-2",
                        "kind": "task",
                        "tags": ["implementation"],
                        "impact_level": "medium",
                        "estimate_minutes": 60,
                    },
                    {
                        "event_id": "state-2a",
                        "event_type": "state_changed",
                        "occurred_at": "2026-01-01T09:00:00+00:00",
                        "gtd_id": "task-2",
                        "from": {"prefix": "next"},
                        "to": {"prefix": "today"},
                        "tags": ["implementation"],
                        "impact_level": "medium",
                        "estimate_minutes": 60,
                    },
                    {
                        "event_id": "state-2b",
                        "event_type": "state_changed",
                        "occurred_at": "2026-01-01T10:00:00+00:00",
                        "gtd_id": "task-2",
                        "from": {"prefix": "today"},
                        "to": {"prefix": "done"},
                        "tags": ["implementation"],
                        "impact_level": "medium",
                        "estimate_minutes": 60,
                    },
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        report = build_report(self.repo, "2026-01-01", "2026-01-01")
        task = next(row for row in report["tasks"] if row["gtd_id"] == "task-2")

        self.assertEqual(task["lead_seconds"], 7200)
        self.assertEqual(task["cycle_seconds"], 3600)
        self.assertEqual(task["estimate_minutes"], 60)
        self.assertEqual(task["estimate_variance_seconds"], 0)
        self.assertEqual(report["by_tag"]["implementation"]["completed_count"], 1)
        self.assertEqual(report["by_impact_level"]["medium"]["task_count"], 1)
        self.assertEqual(report["daily_throughput"], [{"date": "2026-01-01", "completed_count": 1}])

    def test_explicit_work_intervals_override_state_based_active_time(self):
        events = [
            {
                "event_id": "state-start",
                "event_type": "state_changed",
                "occurred_at": "2026-01-01T09:00:00+00:00",
                "gtd_id": "explicit-task",
                "from": {"prefix": "next"},
                "to": {"prefix": "today"},
            },
            {
                "event_id": "work-start",
                "event_type": "work_started",
                "occurred_at": "2026-01-01T09:15:00+00:00",
                "gtd_id": "explicit-task",
            },
            {
                "event_id": "work-stop",
                "event_type": "work_stopped",
                "occurred_at": "2026-01-01T09:45:00+00:00",
                "gtd_id": "explicit-task",
            },
            {
                "event_id": "state-done",
                "event_type": "state_changed",
                "occurred_at": "2026-01-01T10:00:00+00:00",
                "gtd_id": "explicit-task",
                "from": {"prefix": "today"},
                "to": {"prefix": "done"},
            },
        ]
        report = aggregate(
            events,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 23, 59, tzinfo=timezone.utc),
        )
        self.assertEqual(report["tasks"][0]["active_seconds"], 30 * 60)


if __name__ == "__main__":
    unittest.main()

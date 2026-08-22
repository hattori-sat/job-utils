"""Aggregate state-change events into task time and flow measurements."""

from datetime import datetime, timezone
from typing import Dict, Iterable, Optional


ACTIVE_PREFIXES = {"today", "focus"}


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO timestamp and default naive values to UTC."""

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _overlap_seconds(
    start: datetime, end: datetime, report_start: datetime, report_end: datetime
) -> int:
    """Return the seconds shared by an interval and the report window."""

    left = max(start, report_start)
    right = min(end, report_end)
    return max(0, int((right - left).total_seconds()))


def aggregate(
    events: Iterable[Dict], report_start: datetime, report_end: datetime
) -> Dict:
    """Build task-level metrics from an ordered stream of state changes."""

    tasks: Dict[str, Dict] = {}
    ordered = sorted(
        events, key=lambda event: (event["occurred_at"], event["event_id"])
    )
    for event in ordered:
        task_id = event["gtd_id"]
        task = tasks.setdefault(
            task_id,
            {
                "gtd_id": task_id,
                "active_seconds": 0,
                "waiting_seconds": 0,
                "scheduled_seconds": 0,
                "transitions": 0,
                "final_prefix": None,
                "first_event_at": None,
                "completed_at": None,
                "tags": [],
                "impact_level": None,
            },
        )
        occurred = parse_timestamp(event["occurred_at"])
        if task["first_event_at"] is None:
            task["first_event_at"] = occurred
        if event.get("event_type") != "state_changed":
            continue
        for tag in event.get("tags", []):
            if tag not in task["tags"]:
                task["tags"].append(tag)
        if event.get("impact_level"):
            task["impact_level"] = event["impact_level"]
        from_prefix = event.get("from", {}).get("prefix")
        to_prefix = event.get("to", {}).get("prefix")
        if not from_prefix or not to_prefix:
            continue
        previous = task.get("final_prefix") or from_prefix
        previous_at = task.get("last_state_at")
        if previous_at is not None:
            seconds = _overlap_seconds(previous_at, occurred, report_start, report_end)
            if previous in ACTIVE_PREFIXES:
                task["active_seconds"] += seconds
            elif previous == "wait":
                task["waiting_seconds"] += seconds
            elif previous == "cal":
                task["scheduled_seconds"] += seconds
        task["final_prefix"] = to_prefix
        task["last_state_at"] = occurred
        task["transitions"] += 1
        if to_prefix == "done":
            task["completed_at"] = occurred

    for task in tasks.values():
        last_state_at = task.pop("last_state_at", None)
        if last_state_at is not None and task["final_prefix"] != "done":
            seconds = _overlap_seconds(
                last_state_at, report_end, report_start, report_end
            )
            if task["final_prefix"] in ACTIVE_PREFIXES:
                task["active_seconds"] += seconds
            elif task["final_prefix"] == "wait":
                task["waiting_seconds"] += seconds
            elif task["final_prefix"] == "cal":
                task["scheduled_seconds"] += seconds
        completed = task.get("completed_at")
        first = task.get("first_event_at")
        task["cycle_seconds"] = (
            int((completed - first).total_seconds()) if completed and first else None
        )
        task["first_event_at"] = first.isoformat() if first else None
        task["completed_at"] = completed.isoformat() if completed else None

    rows = list(tasks.values())
    return {
        "period": {
            "start": report_start.isoformat(),
            "end": report_end.isoformat(),
        },
        "task_count": len(rows),
        "completed_count": sum(1 for task in rows if task["completed_at"]),
        "active_seconds": sum(task["active_seconds"] for task in rows),
        "waiting_seconds": sum(task["waiting_seconds"] for task in rows),
        "scheduled_seconds": sum(task["scheduled_seconds"] for task in rows),
        "tasks": sorted(rows, key=lambda task: task["gtd_id"]),
    }

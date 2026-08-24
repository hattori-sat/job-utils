"""Aggregate JSONL events into task time, flow, and review measurements."""

from datetime import datetime, timezone
from typing import Dict, Iterable


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


def _new_task(task_id: str) -> Dict:
    return {
        "gtd_id": task_id,
        "kind": None,
        "active_seconds": 0,
        "waiting_seconds": 0,
        "scheduled_seconds": 0,
        "transitions": 0,
        "final_prefix": None,
        "first_event_at": None,
        "first_state_at": None,
        "captured_at": None,
        "completed_at": None,
        "tags": [],
        "impact_level": None,
        "estimate_minutes": None,
    }


def _merge_metadata(task: Dict, event: Dict) -> None:
    """Merge optional classification metadata without erasing earlier values."""

    if event.get("kind"):
        task["kind"] = event["kind"]
    for tag in event.get("tags", []) or []:
        if tag not in task["tags"]:
            task["tags"].append(tag)
    if event.get("impact_level"):
        task["impact_level"] = event["impact_level"]
    if event.get("estimate_minutes") is not None:
        try:
            task["estimate_minutes"] = int(event["estimate_minutes"])
        except (TypeError, ValueError):
            pass


def _add_group(groups: Dict[str, Dict], key: str, task: Dict) -> None:
    """Accumulate fields shared by tag, impact, and prefix groups."""

    group = groups.setdefault(
        key,
        {
            "task_count": 0,
            "completed_count": 0,
            "active_seconds": 0,
            "waiting_seconds": 0,
            "scheduled_seconds": 0,
        },
    )
    group["task_count"] += 1
    group["completed_count"] += 1 if task["completed_in_period"] else 0
    for field in ("active_seconds", "waiting_seconds", "scheduled_seconds"):
        group[field] += task[field]


def aggregate(events: Iterable[Dict], report_start: datetime, report_end: datetime) -> Dict:
    """Build task-level and grouped metrics from an ordered event stream."""

    tasks: Dict[str, Dict] = {}
    ordered = sorted(
        events, key=lambda event: (event["occurred_at"], event["event_id"])
    )
    for event in ordered:
        task_id = event["gtd_id"]
        task = tasks.setdefault(task_id, _new_task(task_id))
        occurred = parse_timestamp(event["occurred_at"])
        if task["first_event_at"] is None:
            task["first_event_at"] = occurred
        _merge_metadata(task, event)
        event_type = event.get("event_type")
        if event_type == "captured" and task["captured_at"] is None:
            task["captured_at"] = occurred
        if event_type == "completed" and task["completed_at"] is None:
            task["completed_at"] = occurred
        if event_type != "state_changed":
            continue

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
        if task["first_state_at"] is None and to_prefix != "inbox":
            task["first_state_at"] = occurred
        task["final_prefix"] = to_prefix
        task["last_state_at"] = occurred
        task["transitions"] += 1
        if to_prefix == "done" and task["completed_at"] is None:
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
        completed = task["completed_at"]
        first_event = task["first_event_at"]
        first_state = task["first_state_at"]
        task["lead_seconds"] = (
            int((completed - task["captured_at"]).total_seconds())
            if completed and task["captured_at"]
            else None
        )
        task["cycle_seconds"] = (
            int((completed - first_state).total_seconds())
            if completed and first_state
            else None
        )
        task["estimate_variance_seconds"] = (
            task["active_seconds"] - task["estimate_minutes"] * 60
            if task["estimate_minutes"] is not None
            else None
        )
        task["first_event_at"] = first_event.isoformat() if first_event else None
        task["first_state_at"] = first_state.isoformat() if first_state else None
        task["captured_at"] = (
            task["captured_at"].isoformat() if task["captured_at"] else None
        )
        task["completed_at"] = completed.isoformat() if completed else None
        task["completed_in_period"] = bool(
            completed and report_start <= completed <= report_end
        )

    rows = sorted(tasks.values(), key=lambda task: task["gtd_id"])
    by_tag: Dict[str, Dict] = {}
    by_impact_level: Dict[str, Dict] = {}
    by_prefix: Dict[str, Dict] = {}
    daily = {}
    for task in rows:
        for tag in task["tags"] or ["untagged"]:
            _add_group(by_tag, tag, task)
        _add_group(by_impact_level, task["impact_level"] or "unspecified", task)
        _add_group(by_prefix, task["final_prefix"] or "unknown", task)
        if task["completed_at"]:
            completed = parse_timestamp(task["completed_at"])
            if report_start <= completed <= report_end:
                day = completed.date().isoformat()
                daily[day] = daily.get(day, 0) + 1

    return {
        "period": {
            "start": report_start.isoformat(),
            "end": report_end.isoformat(),
        },
        "task_count": len(rows),
        "completed_count": sum(1 for task in rows if task["completed_in_period"]),
        "active_seconds": sum(task["active_seconds"] for task in rows),
        "waiting_seconds": sum(task["waiting_seconds"] for task in rows),
        "scheduled_seconds": sum(task["scheduled_seconds"] for task in rows),
        "lead_seconds": sum(
            task["lead_seconds"] or 0 for task in rows if task["completed_in_period"]
        ),
        "cycle_seconds": sum(
            task["cycle_seconds"] or 0 for task in rows if task["completed_in_period"]
        ),
        "estimate_variance_seconds": sum(
            task["estimate_variance_seconds"] or 0
            for task in rows
            if task["estimate_variance_seconds"] is not None
        ),
        "by_tag": by_tag,
        "by_impact_level": by_impact_level,
        "by_prefix": by_prefix,
        "daily_throughput": [
            {"date": day, "completed_count": daily[day]} for day in sorted(daily)
        ],
        "tasks": rows,
    }

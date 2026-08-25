"""Append-only JSONL event recording for task and synchronization metrics."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def utc_timestamp() -> str:
    """Return the current UTC timestamp with second precision."""

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_event(
    repo_root: Path,
    event_type: str,
    gtd_id: str,
    occurred_at: Optional[str] = None,
    source: Optional[Dict[str, str]] = None,
    **fields: Any,
) -> Path:
    """Append one event to the JSONL file for its calendar year."""

    timestamp = occurred_at or utc_timestamp()
    event: Dict[str, Any] = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "occurred_at": timestamp,
        "gtd_id": gtd_id,
        "source": source
        or {
            "machine_id": os.environ.get("JOBUTILS_MACHINE_ID", "unknown"),
            "command": "unknown",
        },
    }
    event.update(fields)
    path = repo_root / ".jobutils" / "metrics" / "events" / (timestamp[:4] + ".jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def append_state_change(
    repo_root: Path,
    gtd_id: str,
    from_prefix: str,
    to_prefix: str,
    command: str,
    machine_id: Optional[str] = None,
    tags: Optional[list] = None,
    impact_level: Optional[str] = None,
    kind: Optional[str] = None,
    estimate_minutes: Optional[str] = None,
) -> Path:
    """Record a prefix transition with the task's current taxonomy values."""

    occurred_at = utc_timestamp()
    fields: Dict[str, Any] = {
        "from": {"prefix": from_prefix},
        "to": {"prefix": to_prefix},
    }
    if tags:
        fields["tags"] = tags
    if impact_level:
        fields["impact_level"] = impact_level
    if kind:
        fields["kind"] = kind
    if estimate_minutes is not None:
        fields["estimate_minutes"] = estimate_minutes
    return append_event(
        repo_root,
        "state_changed",
        gtd_id,
        occurred_at=occurred_at,
        source={
            "machine_id": machine_id
            or os.environ.get("JOBUTILS_MACHINE_ID", "unknown"),
            "command": command,
        },
        **fields,
    )


def append_work_started(
    repo_root: Path,
    gtd_id: str,
    command: str = "python:metrics start",
    machine_id: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> Path:
    """Record the beginning of an explicit active-work interval."""

    return append_event(
        repo_root,
        "work_started",
        gtd_id,
        occurred_at=occurred_at,
        source={
            "machine_id": machine_id
            or os.environ.get("JOBUTILS_MACHINE_ID", "unknown"),
            "command": command,
        },
    )


def append_work_stopped(
    repo_root: Path,
    gtd_id: str,
    command: str = "python:metrics stop",
    machine_id: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> Path:
    """Record the end of an explicit active-work interval."""

    return append_event(
        repo_root,
        "work_stopped",
        gtd_id,
        occurred_at=occurred_at,
        source={
            "machine_id": machine_id
            or os.environ.get("JOBUTILS_MACHINE_ID", "unknown"),
            "command": command,
        },
    )

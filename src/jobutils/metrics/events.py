import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_event(
    repo_root: Path,
    event_type: str,
    gtd_id: str,
    occurred_at: Optional[str] = None,
    source: Optional[Dict[str, str]] = None,
    **fields: Any
) -> Path:
    timestamp = occurred_at or utc_timestamp()
    event: Dict[str, Any] = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "occurred_at": timestamp,
        "gtd_id": gtd_id,
        "source": source or {
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
) -> Path:
    occurred_at = utc_timestamp()
    fields: Dict[str, Any] = {
        "from": {"prefix": from_prefix},
        "to": {"prefix": to_prefix},
    }
    if tags:
        fields["tags"] = tags
    if impact_level:
        fields["impact_level"] = impact_level
    return append_event(
        repo_root,
        "state_changed",
        gtd_id,
        occurred_at=occurred_at,
        source={
            "machine_id": machine_id or os.environ.get("JOBUTILS_MACHINE_ID", "unknown"),
            "command": command,
        },
        **fields
    )

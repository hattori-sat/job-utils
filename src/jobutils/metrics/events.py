import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_state_change(
    repo_root: Path,
    gtd_id: str,
    from_prefix: str,
    to_prefix: str,
    command: str,
    machine_id: Optional[str] = None,
) -> Path:
    occurred_at = utc_timestamp()
    event: Dict[str, Any] = {
        "event_id": str(uuid.uuid4()),
        "event_type": "state_changed",
        "occurred_at": occurred_at,
        "gtd_id": gtd_id,
        "source": {
            "machine_id": machine_id or os.environ.get("JOBUTILS_MACHINE_ID", "unknown"),
            "command": command,
        },
        "from": {"prefix": from_prefix},
        "to": {"prefix": to_prefix},
    }
    path = repo_root / ".jobutils" / "metrics" / "events" / (occurred_at[:4] + ".jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return path

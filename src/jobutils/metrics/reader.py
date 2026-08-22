import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def event_paths(repo_root: Path) -> List[Path]:
    directory = Path(repo_root) / ".jobutils" / "metrics" / "events"
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.glob("*.jsonl") if path.is_file())


def read_events(repo_root: Path) -> Tuple[List[Dict], List[str]]:
    events: List[Dict] = []
    errors: List[str] = []
    seen = set()
    for path in event_paths(repo_root):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError as error:
                errors.append("{}:{}: {}".format(path, line_number, error))
                continue
            event_id = event.get("event_id")
            if not event_id or event_id in seen:
                if event_id:
                    continue
                errors.append("{}:{}: missing event_id".format(path, line_number))
                continue
            if not event.get("gtd_id") or not event.get("occurred_at"):
                errors.append("{}:{}: missing gtd_id or occurred_at".format(path, line_number))
                continue
            seen.add(event_id)
            events.append(event)
    events.sort(key=lambda event: (event["occurred_at"], event["event_id"]))
    return events, errors

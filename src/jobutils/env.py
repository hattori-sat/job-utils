"""Small, dependency-free loader for the local ignored `.env` file."""

import os
from pathlib import Path
from typing import Dict, Iterable


def parse_env(lines: Iterable[str]) -> Dict[str, str]:
    """Parse simple KEY=value assignments without evaluating shell syntax."""

    values: Dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip().strip("'\"")
    return values


def load_local_env(root: Path) -> Dict[str, str]:
    """Load missing process variables from one local `.env` file.

    Existing process variables win. The return value contains only values that
    were added, which makes the operation easy to test without exposing
    secrets in logs or command output.
    """

    path = Path(root).expanduser().resolve() / ".env"
    if not path.is_file():
        return {}
    added: Dict[str, str] = {}
    values = parse_env(path.read_text(encoding="utf-8").splitlines())
    for key, value in values.items():
        if key not in os.environ:
            os.environ[key] = value
            added[key] = value
    return added

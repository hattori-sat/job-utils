"""Small YAML front-matter helpers for the repository's flat metadata model."""

import json
import re
from typing import List, Optional, Tuple


def bounds(lines: List[str]) -> Optional[Tuple[int, int]]:
    """Return the opening and closing delimiter indexes, if present."""

    if not lines or lines[0].strip() != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return 0, index
    return None


def value(lines: List[str], key: str) -> Optional[str]:
    """Read a scalar front-matter value without rewriting the document."""

    location = bounds(lines)
    if location is None:
        return None
    pattern = re.compile(r"^{}:\s*(.*)$".format(re.escape(key)))
    for line in lines[location[0] + 1 : location[1]]:
        match = pattern.match(line)
        if not match:
            continue
        raw = match.group(1).strip()
        if raw in ("null", "~"):
            return None
        if len(raw) >= 2 and raw[0] == raw[-1] == "'":
            return raw[1:-1].replace("''", "'")
        if len(raw) >= 2 and raw[0] == raw[-1] == '"':
            try:
                return str(json.loads(raw))
            except ValueError:
                return raw[1:-1]
        return raw
    return None


def list_value(lines: List[str], key: str) -> List[str]:
    """Read a simple inline YAML list such as ``tags: [one, two]``."""

    raw = value(lines, key)
    if not raw or not (raw.startswith("[") and raw.endswith("]")):
        return []
    result = []
    for part in raw[1:-1].split(","):
        item = part.strip().strip("'\"")
        if item:
            result.append(item)
    return result


def quote(value_to_quote: str) -> str:
    """Quote a scalar using YAML's single-quoted string form."""

    return "'{}'".format(value_to_quote.replace("'", "''"))


def set_value(lines: List[str], key: str, value_to_set: str) -> None:
    """Insert or replace a scalar front-matter value in place."""

    location = bounds(lines)
    if location is None:
        raise ValueError("managed Markdown requires YAML front matter")
    replacement = "{}: {}".format(key, quote(value_to_set))
    pattern = re.compile(r"^{}:\s*".format(re.escape(key)))
    for index in range(location[0] + 1, location[1]):
        if pattern.match(lines[index]):
            lines[index] = replacement
            return
    lines.insert(location[1], replacement)


def remove_key(lines: List[str], key: str) -> None:
    """Remove a scalar key when it exists in the front matter."""

    location = bounds(lines)
    if location is None:
        return
    pattern = re.compile(r"^{}:\s*".format(re.escape(key)))
    for index in range(location[1] - 1, location[0], -1):
        if pattern.match(lines[index]):
            del lines[index]

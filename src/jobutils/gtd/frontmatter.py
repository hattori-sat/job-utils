import json
import re
from typing import List, Optional, Tuple


def bounds(lines: List[str]) -> Optional[Tuple[int, int]]:
    if not lines or lines[0].strip() != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return 0, index
    return None


def value(lines: List[str], key: str) -> Optional[str]:
    location = bounds(lines)
    if location is None:
        return None
    pattern = re.compile(r"^{}:\s*(.*)$".format(re.escape(key)))
    for line in lines[location[0] + 1 : location[1]]:
        match = pattern.match(line)
        if not match:
            continue
        raw = match.group(1).strip()
        if len(raw) >= 2 and raw[0] == raw[-1] == "'":
            return raw[1:-1].replace("''", "'")
        if len(raw) >= 2 and raw[0] == raw[-1] == '"':
            try:
                return str(json.loads(raw))
            except ValueError:
                return raw[1:-1]
        return raw
    return None


def quote(value_to_quote: str) -> str:
    return "'{}'".format(value_to_quote.replace("'", "''"))


def set_value(lines: List[str], key: str, value_to_set: str) -> None:
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
    location = bounds(lines)
    if location is None:
        return
    pattern = re.compile(r"^{}:\s*".format(re.escape(key)))
    for index in range(location[1] - 1, location[0], -1):
        if pattern.match(lines[index]):
            del lines[index]

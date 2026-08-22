import re
from typing import Iterable, List, Optional, Tuple

from .model import PREFIXES, SECTION_TO_PREFIX, TaskItem


SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
PREFIXED_ITEM_RE = re.compile(r"^\s*-\s*([A-Za-z0-9_-]+):\s*(.*?)\s*$")
UNPREFIXED_ITEM_RE = re.compile(r"^\s*-\s*(\S.*?)\s*$")
LINK_RE = re.compile(r"^(.*?)\s+<([^<>]+\.md)>\s*$")


def split_title_link(body: str) -> Tuple[str, Optional[str]]:
    match = LINK_RE.match(body)
    if not match:
        return body.strip(), None
    return match.group(1).strip(), match.group(2).replace("\\", "/")


def scan_items(lines: Iterable[str]) -> Tuple[List[TaskItem], List[Tuple[int, str]]]:
    """Return recognized items and prefixed lines that require validation."""

    items: List[TaskItem] = []
    prefixed: List[Tuple[int, str]] = []
    current_section = ""
    for index, line in enumerate(lines):
        section_match = SECTION_RE.match(line)
        if section_match:
            current_section = section_match.group(1)
            continue

        match = PREFIXED_ITEM_RE.match(line)
        if match:
            prefix = match.group(1).lower()
            prefixed.append((index, prefix))
            if prefix not in PREFIXES:
                continue
            title, link = split_title_link(match.group(2))
            items.append(
                TaskItem(index, title, prefix, current_section, link, True)
            )
            continue

        section_prefix = SECTION_TO_PREFIX.get(current_section)
        unprefixed = UNPREFIXED_ITEM_RE.match(line)
        if section_prefix and unprefixed:
            title, link = split_title_link(unprefixed.group(1))
            items.append(
                TaskItem(index, title, section_prefix, current_section, link, False)
            )
    return items, prefixed


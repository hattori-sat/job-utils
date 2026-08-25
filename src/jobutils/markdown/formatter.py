"""Format managed Markdown without changing its authoring meaning."""

import os
import tempfile
from pathlib import Path
from typing import List

from jobutils.gtd import frontmatter


class FormatError(ValueError):
    """A Markdown file cannot be formatted safely."""


def _is_fence(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("```") or stripped.startswith("~~~")


def _is_h1(line: str) -> bool:
    return line.startswith("# ") and not line.startswith("## ")


def format_text(text: str) -> str:
    """Return canonical Markdown with three blank lines after level-one headings."""

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    location = frontmatter.bounds(lines)
    if location is None:
        raise FormatError("Markdown document requires YAML front matter")

    head = lines[: location[1] + 1]
    body = lines[location[1] + 1 :]
    formatted: List[str] = []
    in_fence = False
    pending_h1_gap = False
    blank_count = 0

    for raw_line in body:
        line = raw_line if in_fence else raw_line.rstrip()
        if _is_fence(line):
            if pending_h1_gap:
                formatted.extend([""] * 3)
                pending_h1_gap = False
            formatted.append(line)
            in_fence = not in_fence
            blank_count = 0
            continue
        if in_fence:
            formatted.append(line)
            continue
        if not line.strip():
            blank_count += 1
            continue
        if pending_h1_gap:
            formatted.extend([""] * 3)
            pending_h1_gap = False
        elif blank_count:
            formatted.append("")
        blank_count = 0
        formatted.append(line)
        if _is_h1(line):
            pending_h1_gap = True

    if pending_h1_gap:
        formatted.extend([""] * 3)
    while formatted and not formatted[0].strip():
        formatted.pop(0)
    while formatted and not formatted[-1].strip():
        formatted.pop()
    if pending_h1_gap:
        formatted.extend([""] * 3)
    return "\n".join(head + [""] + formatted).rstrip("\n") + "\n"


def format_file(path: Path, check: bool = False) -> bool:
    """Format one managed Markdown file and return whether it would change."""

    path = Path(path)
    original = path.read_text(encoding="utf-8")
    formatted = format_text(original)
    changed = original != formatted
    if check or not changed:
        return changed
    descriptor, temporary = tempfile.mkstemp(prefix=".jobutils-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(formatted)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return True

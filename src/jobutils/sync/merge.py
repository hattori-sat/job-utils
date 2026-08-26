"""Three-way merge behavior for public Markdown bodies."""

from difflib import SequenceMatcher
from typing import List, Tuple


Change = Tuple[int, int, List[str], str]


def _changes(base: List[str], variant: List[str], side: str) -> List[Change]:
    """Return changed base ranges and their replacement lines."""

    matcher = SequenceMatcher(None, base, variant, autojunk=False)
    return [
        (start, end, variant[replacement_start:replacement_end], side)
        for tag, start, end, replacement_start, replacement_end in matcher.get_opcodes()
        if tag != "equal"
    ]


def _overlaps(left: Change, right: Change) -> bool:
    """Return whether two changes compete for the same base content."""

    left_start, left_end = left[:2]
    right_start, right_end = right[:2]
    if left_start == left_end and right_start == right_end:
        return False
    if left_start == left_end:
        return right_start < left_start < right_end
    if right_start == right_end:
        return left_start < right_start < left_end
    return max(left_start, right_start) < min(left_end, right_end)


def _same_change(left: Change, right: Change) -> bool:
    """Return whether two changes produce the same replacement."""

    return left[:3] == right[:3]


def _conflict_text(local: str, remote: str) -> str:
    """Render the existing conflict-marker format for Vim resolution."""

    return "<<<<<<< local\n{}=======\n{}>>>>>>> external\n".format(
        local.rstrip("\n") + "\n", remote.rstrip("\n") + "\n"
    )


def three_way_merge(base: str, local: str, remote: str) -> Tuple[str, bool]:
    """Merge independent line changes and mark overlapping changes."""

    if local == remote:
        return local, False
    if local == base:
        return remote, False
    if remote == base:
        return local, False

    base_lines = base.splitlines(keepends=True)
    local_lines = local.splitlines(keepends=True)
    remote_lines = remote.splitlines(keepends=True)
    local_changes = _changes(base_lines, local_lines, "local")
    remote_changes = _changes(base_lines, remote_lines, "external")
    merged_changes: List[Change] = list(local_changes)

    for remote_change in remote_changes:
        matching = [
            change
            for change in merged_changes
            if change[:2] == remote_change[:2]
        ]
        if matching and _same_change(matching[0], remote_change):
            continue
        if any(_overlaps(change, remote_change) for change in merged_changes):
            return _conflict_text(local, remote), True
        merged_changes.append(remote_change)

    merged_changes.sort(
        key=lambda change: (
            change[0],
            0 if change[0] == change[1] else 1,
            0 if change[3] == "local" else 1,
        )
    )
    result: List[str] = []
    cursor = 0
    for start, end, replacement, _side in merged_changes:
        if start < cursor:
            return _conflict_text(local, remote), True
        result.extend(base_lines[cursor:start])
        result.extend(replacement)
        cursor = max(cursor, end)
    result.extend(base_lines[cursor:])
    return "".join(result), False

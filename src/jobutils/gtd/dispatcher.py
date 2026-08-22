import os
import re
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from jobutils.metrics.events import append_state_change

from . import frontmatter
from .model import PREFIXES, SECTIONS, STATUSES, TaskItem
from .parser import SECTION_RE, scan_items, split_title_link


class DispatchError(Exception):
    """A user-correctable GTD operation error."""


@dataclass
class DispatchResult:
    gtd_path: Path
    moved: int = 0
    created: List[Path] = field(default_factory=list)
    event_count: int = 0


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".jobutils-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _read_lines(path: Path) -> List[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as error:
        raise DispatchError("gtd.md was not found: {}".format(path)) from error


def _render(lines: List[str]) -> str:
    return "\n".join(lines).rstrip("\n") + "\n"


def _find_section(lines: List[str], title: str) -> Optional[int]:
    pattern = re.compile(r"^##\s+{}\s*$".format(re.escape(title)))
    for index, line in enumerate(lines):
        if pattern.match(line):
            return index
    return None


def _section_end(lines: List[str], header: int) -> int:
    for index in range(header + 1, len(lines)):
        if SECTION_RE.match(lines[index]):
            return index
    return len(lines)


def _ensure_section(lines: List[str], title: str) -> int:
    found = _find_section(lines, title)
    if found is not None:
        return found
    if lines and lines[-1].strip():
        lines.append("")
    lines.extend(["## " + title, ""])
    return len(lines) - 2


def _append_bucket(lines: List[str], title: str, items: List[str]) -> None:
    if not items:
        return
    header = _ensure_section(lines, title)
    end = _section_end(lines, header)
    existing = [line for line in lines[header + 1 : end] if line.strip()]
    content = existing + items
    replacement = [""] + content + [""]
    lines[header + 1 : end] = replacement


def _safe_link(repo_root: Path, link: str) -> Path:
    candidate = (repo_root / link).resolve()
    root = repo_root.resolve()
    if candidate != root and root not in candidate.parents:
        raise DispatchError("linked detail path escapes the GTD repository: {}".format(link))
    return candidate


def _task_template(gtd_path: Path, prefix: str, title: str, task_id: str) -> str:
    today = __import__("datetime").date.today().isoformat()
    lines = [
        "---",
        "gtd_id: {}".format(frontmatter.quote(task_id)),
        "kind: 'task'",
        "prefix: {}".format(frontmatter.quote(prefix)),
        "status: {}".format(frontmatter.quote(STATUSES[prefix])),
        "title: {}".format(frontmatter.quote(title)),
        "created_at: {}".format(frontmatter.quote(today)),
        "updated_at: {}".format(frontmatter.quote(today)),
        "gtd_file: {}".format(frontmatter.quote("../" + gtd_path.name)),
        "tags: []",
        "impact_level: null",
        "impact_area: null",
        "estimate_minutes: null",
        "publish_jira: false",
        "jira_project: null",
        "jira_issue_type: Task",
        "jira_parent_key: null",
        "jira_key: null",
        "jira_url: null",
        "publish_confluence: false",
        "confluence_space_id: null",
        "confluence_space_key: null",
        "confluence_parent_id: null",
        "confluence_page_id: null",
        "confluence_url: null",
        "confluence_version: 0",
        "references: []",
        "---",
        "",
        "# Summary",
        "",
        "",
        "",
        "# Description",
        "",
        "",
        "",
        "# Progress Comment",
        "",
        "",
        "",
        "# Background",
        "",
        "",
        "",
        "# Objective",
        "",
        "",
        "",
        "# Implementation Note",
        "",
        "",
        "",
        "# Scope",
        "",
        "",
        "",
        "## In",
        "",
        "",
        "",
        "## Out",
        "",
        "",
        "",
        "# Deliverables",
        "",
        "",
        "",
        "# Acceptance Criteria",
        "",
        "",
        "",
        "# Preconditions",
        "",
        "",
        "",
        "# Dependencies",
        "",
        "",
        "",
        "# Risks",
        "",
        "",
        "",
        "# Open Questions",
        "",
        "",
        "",
        "# References",
        "",
        "",
        "",
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


def _update_detail(path: Path, item: TaskItem, gtd_path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if frontmatter.value(lines, "gtd_id") is None:
        raise DispatchError("unmanaged detail file: {}".format(path))
    old_title = frontmatter.value(lines, "title")
    old_prefix = frontmatter.value(lines, "prefix")
    old_status = frontmatter.value(lines, "status")
    changed = old_title != item.title or old_prefix != item.prefix or old_status != STATUSES[item.prefix]
    if not changed:
        return
    frontmatter.set_value(lines, "title", item.title)
    frontmatter.set_value(lines, "prefix", item.prefix)
    frontmatter.set_value(lines, "status", STATUSES[item.prefix])
    frontmatter.set_value(lines, "updated_at", __import__("datetime").date.today().isoformat())
    if item.prefix == "done":
        frontmatter.set_value(lines, "completed_at", __import__("datetime").date.today().isoformat())
    else:
        frontmatter.remove_key(lines, "completed_at")
    closing = frontmatter.bounds(lines)
    if closing is not None and old_title:
        for index in range(closing[1] + 1, len(lines)):
            if lines[index] == "# " + old_title:
                lines[index] = "# " + item.title
                break
    _atomic_write(path, _render(lines))


def dispatch(
    repo_root: Path,
    gtd_path: Optional[Path] = None,
    machine_id: Optional[str] = None,
    command: str = "python:gtd dispatch",
) -> DispatchResult:
    repo_root = Path(repo_root).resolve()
    gtd_path = (gtd_path or repo_root / "gtd.md").resolve()
    lines = _read_lines(gtd_path)
    items, prefixed = scan_items(lines)
    if any(prefix == "inbox" for _, prefix in prefixed):
        raise DispatchError("Inbox is not a dispatch destination")

    focus_count = sum(1 for item in items if item.prefix == "focus")
    if focus_count > 3:
        raise DispatchError("GTD: dispatch failed (Focus limit is three items)")

    buckets: Dict[str, List[str]] = {prefix: [] for prefix in PREFIXES}
    delete_indices = {item.line_index for item in items}
    detail_writes: List[Tuple[Path, str]] = []
    detail_updates: List[Tuple[Path, TaskItem]] = []
    events: List[Tuple[str, str, str, List[str], Optional[str]]] = []
    created: List[Path] = []

    for item in items:
        link = item.link
        task_id_for_event = None
        task_lines: List[str] = []
        if link:
            detail_path = _safe_link(repo_root, link)
            if not detail_path.is_file():
                raise DispatchError("linked detail file is missing: {}".format(link))
            task_lines = detail_path.read_text(encoding="utf-8").splitlines()
            task_id_for_event = frontmatter.value(task_lines, "gtd_id")
            if task_id_for_event is None:
                raise DispatchError("unmanaged detail file: {}".format(link))
            detail_updates.append((detail_path, item))
        else:
            if item.prefix == "done":
                raise DispatchError("create a detail before changing the item to done")
            task_id = str(uuid.uuid4())
            task_id_for_event = task_id
            link = "gtd_tasks/{}.md".format(task_id)
            detail_path = _safe_link(repo_root, link)
            detail_writes.append((detail_path, _task_template(gtd_path, item.prefix, item.title, task_id)))
            task_lines = _task_template(gtd_path, item.prefix, item.title, task_id).splitlines()
            created.append(detail_path)

        buckets[item.prefix].append(
            "- {}: {} <{}>".format(item.prefix, item.title, link)
        )
        if item.source_prefix != item.prefix:
            if task_id_for_event:
                events.append((
                    task_id_for_event,
                    item.source_prefix,
                    item.prefix,
                    frontmatter.list_value(task_lines, "tags"),
                    frontmatter.value(task_lines, "impact_level"),
                ))

    new_lines = [line for index, line in enumerate(lines) if index not in delete_indices]
    for prefix in PREFIXES:
        _append_bucket(new_lines, SECTIONS[prefix], buckets[prefix])

    old_content = _render(lines)
    new_content = _render(new_lines)
    if new_content != old_content:
        _atomic_write(gtd_path, new_content)
    for path, content in detail_writes:
        _atomic_write(path, content)
    for path, item in detail_updates:
        _update_detail(path, item, gtd_path)
    event_count = 0
    for task_id, from_prefix, to_prefix, tags, impact_level in events:
        append_state_change(
            repo_root, task_id, from_prefix, to_prefix, command, machine_id,
            tags=tags, impact_level=impact_level,
        )
        event_count += 1
    return DispatchResult(gtd_path, len(items), created, event_count)


def create_task(repo_root: Path, line_number: int, gtd_path: Optional[Path] = None) -> Path:
    repo_root = Path(repo_root).resolve()
    gtd_path = (gtd_path or repo_root / "gtd.md").resolve()
    lines = _read_lines(gtd_path)
    if line_number < 1 or line_number > len(lines):
        raise DispatchError("line number is outside gtd.md")
    items, _ = scan_items(lines)
    item = next((candidate for candidate in items if candidate.line_index == line_number - 1), None)
    if item is None:
        raise DispatchError("place the cursor on a prefixed task item")
    if item.link:
        path = _safe_link(repo_root, item.link)
        if not path.is_file():
            raise DispatchError("linked detail file is missing: {}".format(item.link))
        return path
    if item.prefix == "done":
        raise DispatchError("create a detail before changing the item to done")
    if not item.title:
        raise DispatchError("task title cannot be empty")
    task_id = str(uuid.uuid4())
    link = "gtd_tasks/{}.md".format(task_id)
    path = _safe_link(repo_root, link)
    content = _task_template(gtd_path, item.prefix, item.title, task_id)
    new_lines = list(lines)
    new_lines[line_number - 1] = "- {}: {} <{}>".format(item.prefix, item.title, link)
    _atomic_write(path, content)
    _atomic_write(gtd_path, _render(new_lines))
    return path

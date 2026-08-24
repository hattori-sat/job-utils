"""Move GTD index items and maintain their linked task Markdown."""

import os
import json
import re
import tempfile
import uuid
from datetime import date
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from jobutils.metrics.events import append_event, append_state_change

from . import frontmatter
from .model import PREFIXES, SECTIONS, STATUSES, TaskItem
from .parser import SECTION_RE, scan_items, split_title_link


SUBTASK_ITEM_RE = re.compile(
    r"^\s*-\s*(?:(?P<prefix>[A-Za-z0-9_-]+):\s*)?(?P<body>.*?)\s*$"
)


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
        raise DispatchError(
            "linked detail path escapes the GTD repository: {}".format(link)
        )
    return candidate


def _capture_event_exists(repo_root: Path, gtd_id: str) -> bool:
    event_root = repo_root / ".jobutils" / "metrics" / "events"
    for path in sorted(event_root.glob("*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("event_type") == "captured" and event.get("gtd_id") == gtd_id:
                return True
    return False


def _ensure_capture_event(
    repo_root: Path, gtd_id: str, content: str, command: str
) -> None:
    if _capture_event_exists(repo_root, gtd_id):
        return
    lines = content.splitlines()
    append_event(
        repo_root,
        "captured",
        gtd_id,
        source={
            "machine_id": os.environ.get("JOBUTILS_MACHINE_ID", "unknown"),
            "command": command,
        },
        kind="task",
        prefix=frontmatter.value(lines, "prefix"),
        tags=frontmatter.list_value(lines, "tags"),
        impact_level=frontmatter.value(lines, "impact_level"),
        estimate_minutes=frontmatter.value(lines, "estimate_minutes"),
    )


def _task_template(
    prefix: str,
    title: str,
    task_id: str,
    parent_gtd_id: Optional[str] = None,
    jira_parent_key: Optional[str] = None,
    jira_project: Optional[str] = None,
    jira_issue_type: str = "Task",
    publish_jira: bool = False,
) -> str:
    """Build the compact task document created by the first GTD dispatch."""

    today = date.today().isoformat()
    jira_project = jira_project or os.environ.get("JIRA_PROJECT")
    jira_issue_type = jira_issue_type or os.environ.get("JIRA_ISSUE_TYPE", "Task")
    jira_progress_comment_field = os.environ.get("JIRA_PROGRESS_COMMENT_FIELD", "")
    parent_value = frontmatter.quote(parent_gtd_id) if parent_gtd_id else "null"
    jira_parent_value = frontmatter.quote(jira_parent_key) if jira_parent_key else "null"
    lines = [
        "---",
        "gtd_id: {}".format(frontmatter.quote(task_id)),
        "kind: 'task'",
        "prefix: {}".format(frontmatter.quote(prefix)),
        "status: {}".format(frontmatter.quote(STATUSES[prefix])),
        "title: {}".format(frontmatter.quote(title)),
        "created_at: {}".format(frontmatter.quote(today)),
        "updated_at: {}".format(frontmatter.quote(today)),
        "tags: []",
        "impact_level: null",
        "estimate_minutes: null",
        "parent_gtd_id: {}".format(parent_value),
        "publish_jira: {}".format("true" if publish_jira else "false"),
        "jira_project: {}".format(
            frontmatter.quote(jira_project) if jira_project else "null"
        ),
        "jira_issue_type: {}".format(frontmatter.quote(jira_issue_type)),
        "jira_parent_key: {}".format(jira_parent_value),
        "jira_progress_comment_field: {}".format(
            frontmatter.quote(jira_progress_comment_field)
            if jira_progress_comment_field
            else "null"
        ),
        "jira_key: null",
        "jira_url: null",
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
        "# Subtasks",
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


def _update_detail(path: Path, item: TaskItem) -> None:
    """Synchronize a linked task's state and title with its GTD index item."""

    lines = path.read_text(encoding="utf-8").splitlines()
    if frontmatter.value(lines, "gtd_id") is None:
        raise DispatchError("unmanaged detail file: {}".format(path))
    old_title = frontmatter.value(lines, "title")
    old_prefix = frontmatter.value(lines, "prefix")
    old_status = frontmatter.value(lines, "status")
    changed = (
        old_title != item.title
        or old_prefix != item.prefix
        or old_status != STATUSES[item.prefix]
    )
    if not changed:
        return
    frontmatter.set_value(lines, "title", item.title)
    frontmatter.set_value(lines, "prefix", item.prefix)
    frontmatter.set_value(lines, "status", STATUSES[item.prefix])
    frontmatter.set_value(lines, "updated_at", date.today().isoformat())
    if item.prefix == "done":
        frontmatter.set_value(lines, "completed_at", date.today().isoformat())
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
    """Dispatch every recognized GTD item into its prefixed section."""

    repo_root = Path(repo_root).resolve()
    gtd_path = (gtd_path or repo_root / "gtd.md").resolve()
    lines = _read_lines(gtd_path)
    items, prefixed = scan_items(lines)

    focus_count = sum(1 for item in items if item.prefix == "focus")
    if focus_count > 3:
        raise DispatchError("GTD: dispatch failed (Focus limit is three items)")

    buckets: Dict[str, List[str]] = {prefix: [] for prefix in PREFIXES}
    delete_indices = {item.line_index for item in items}
    detail_updates: List[Tuple[Path, TaskItem]] = []
    events: List[Tuple[str, str, str, List[str], Optional[str], Optional[str], Optional[str]]] = []

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

        rendered = "- {}: {}".format(item.prefix, item.title)
        if link:
            rendered += " <{}>".format(link)
        buckets[item.prefix].append(rendered)
        if item.source_prefix != item.prefix:
            if task_id_for_event:
                events.append(
                    (
                        task_id_for_event,
                        item.source_prefix,
                        item.prefix,
                        frontmatter.list_value(task_lines, "tags"),
                        frontmatter.value(task_lines, "impact_level"),
                        frontmatter.value(task_lines, "kind"),
                        frontmatter.value(task_lines, "estimate_minutes"),
                    )
                )

    new_lines = [
        line for index, line in enumerate(lines) if index not in delete_indices
    ]
    for prefix in PREFIXES:
        _append_bucket(new_lines, SECTIONS[prefix], buckets[prefix])

    old_content = _render(lines)
    new_content = _render(new_lines)
    if new_content != old_content:
        _atomic_write(gtd_path, new_content)
    for path, item in detail_updates:
        _update_detail(path, item)
    event_count = 0
    for task_id, from_prefix, to_prefix, tags, impact_level, kind, estimate_minutes in events:
        append_state_change(
            repo_root,
            task_id,
            from_prefix,
            to_prefix,
            command,
            machine_id,
            tags=tags,
            impact_level=impact_level,
            kind=kind,
            estimate_minutes=estimate_minutes,
        )
        event_count += 1
    return DispatchResult(gtd_path, len(items), [], event_count)


def create_task(
    repo_root: Path,
    line_number: int,
    gtd_path: Optional[Path] = None,
    parent_path: Optional[str] = None,
) -> Path:
    """Create or return the task document linked from a GTD line."""

    repo_root = Path(repo_root).resolve()
    gtd_path = (gtd_path or repo_root / "gtd.md").resolve()
    lines = _read_lines(gtd_path)
    if line_number < 1 or line_number > len(lines):
        raise DispatchError("line number is outside gtd.md")
    items, _ = scan_items(lines)
    item = next(
        (candidate for candidate in items if candidate.line_index == line_number - 1),
        None,
    )
    if item is None:
        raise DispatchError("place the cursor on a prefixed task item")
    if item.link:
        path = _safe_link(repo_root, item.link)
        if not path.is_file():
            raise DispatchError("linked detail file is missing: {}".format(item.link))
        content = path.read_text(encoding="utf-8")
        task_id = frontmatter.value(content.splitlines(), "gtd_id")
        if task_id is None:
            raise DispatchError("unmanaged detail file: {}".format(item.link))
        _ensure_capture_event(repo_root, task_id, content, "python:gtd task")
        return path
    if item.prefix == "done":
        raise DispatchError("create a detail before changing the item to done")
    if not item.title:
        raise DispatchError("task title cannot be empty")
    task_id = str(uuid.uuid4())
    parent_lines: List[str] = []
    parent_gtd_id = None
    jira_parent_key = None
    jira_project = None
    jira_issue_type = "Task"
    publish_jira = False
    if parent_path:
        parent = _safe_link(repo_root, parent_path)
        if not parent.is_file():
            raise DispatchError("parent task file is missing: {}".format(parent_path))
        if parent.relative_to(repo_root).parts[0] != "gtd_tasks":
            raise DispatchError(
                "parent task must be under gtd_tasks: {}".format(parent_path)
            )
        parent_lines = parent.read_text(encoding="utf-8").splitlines()
        parent_gtd_id = frontmatter.value(parent_lines, "gtd_id")
        if parent_gtd_id is None:
            raise DispatchError("parent task is missing gtd_id: {}".format(parent_path))
        jira_parent_key = frontmatter.value(parent_lines, "jira_key")
        jira_project = frontmatter.value(parent_lines, "jira_project")
        publish_jira = (
            (frontmatter.value(parent_lines, "publish_jira") or "").lower() == "true"
            and bool(jira_parent_key)
        )
        jira_issue_type = "Sub-task"
        link = str((parent.with_suffix("") / (task_id + ".md")).relative_to(repo_root)).replace(
            "\\", "/"
        )
    else:
        link = "gtd_tasks/{}.md".format(task_id)
    path = _safe_link(repo_root, link)
    content = _task_template(
        item.prefix,
        item.title,
        task_id,
        parent_gtd_id,
        jira_parent_key,
        jira_project,
        jira_issue_type,
        publish_jira,
    )
    new_lines = list(lines)
    new_lines[line_number - 1] = "- {}: {} <{}>".format(item.prefix, item.title, link)
    _atomic_write(path, content)
    _atomic_write(gtd_path, _render(new_lines))
    _ensure_capture_event(repo_root, task_id, content, "python:gtd task")
    return path


def _level_one_section_bounds(
    lines: List[str], heading: str
) -> Optional[Tuple[int, int]]:
    """Return the content bounds for one level-one Markdown section."""

    header = next(
        (
            index
            for index, line in enumerate(lines)
            if line.strip() == "# " + heading
        ),
        None,
    )
    if header is None:
        return None
    end = next(
        (
            index
            for index in range(header + 1, len(lines))
            if re.match(r"^#\s+", lines[index])
        ),
        len(lines),
    )
    return header + 1, end


def create_subtask(repo_root: Path, parent_path: str, line_number: int) -> Path:
    """Create a child task from a bullet in a parent task's Subtasks section."""

    repo_root = Path(repo_root).resolve()
    parent = _safe_link(repo_root, parent_path)
    if not parent.is_file():
        raise DispatchError("parent task file is missing: {}".format(parent_path))
    parent_relative = parent.relative_to(repo_root)
    if not parent_relative.parts or parent_relative.parts[0] != "gtd_tasks":
        raise DispatchError("parent task must be under gtd_tasks: {}".format(parent_path))

    lines = parent.read_text(encoding="utf-8").splitlines()
    parent_gtd_id = frontmatter.value(lines, "gtd_id")
    if parent_gtd_id is None:
        raise DispatchError("parent task is missing gtd_id: {}".format(parent_path))
    bounds = _level_one_section_bounds(lines, "Subtasks")
    if bounds is None:
        raise DispatchError("parent task is missing the # Subtasks section")
    if line_number < 1 or line_number > len(lines):
        raise DispatchError("line number is outside the parent task")
    start, end = bounds
    line_index = line_number - 1
    if line_index < start or line_index >= end:
        raise DispatchError("place the cursor on a bullet under # Subtasks")
    match = SUBTASK_ITEM_RE.match(lines[line_index])
    if not match:
        raise DispatchError("place the cursor on a bullet under # Subtasks")
    prefix = (match.group("prefix") or "next").lower()
    if prefix not in PREFIXES:
        raise DispatchError("unknown subtask prefix: {}".format(prefix))
    title, existing_link = split_title_link(match.group("body"))
    if not title:
        raise DispatchError("subtask title cannot be empty")
    if prefix == "done":
        raise DispatchError("create a detail before changing the subtask to done")
    if existing_link:
        path = _safe_link(repo_root, existing_link)
        if not path.is_file():
            raise DispatchError("linked subtask file is missing: {}".format(existing_link))
        content = path.read_text(encoding="utf-8")
        task_id = frontmatter.value(content.splitlines(), "gtd_id")
        if task_id is None:
            raise DispatchError("unmanaged detail file: {}".format(existing_link))
        _ensure_capture_event(repo_root, task_id, content, "python:gtd subtask")
        return path

    task_id = str(uuid.uuid4())
    link = str(
        (parent.with_suffix("") / (task_id + ".md")).relative_to(repo_root)
    ).replace("\\", "/")
    jira_parent_key = frontmatter.value(lines, "jira_key")
    jira_project = frontmatter.value(lines, "jira_project")
    publish_jira = (
        (frontmatter.value(lines, "publish_jira") or "").lower() == "true"
        and bool(jira_parent_key)
    )
    content = _task_template(
        prefix,
        title,
        task_id,
        parent_gtd_id,
        jira_parent_key,
        jira_project,
        "Sub-task",
        publish_jira,
    )
    new_lines = list(lines)
    new_lines[line_index] = "- {}: {} <{}>".format(prefix, title, link)
    path = _safe_link(repo_root, link)
    _atomic_write(path, content)
    _atomic_write(parent, _render(new_lines))
    _ensure_capture_event(repo_root, task_id, content, "python:gtd subtask")
    return path

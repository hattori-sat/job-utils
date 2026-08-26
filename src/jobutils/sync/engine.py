"""Plan, check, and apply synchronization changes for managed Markdown."""

import hashlib
import json
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from jobutils.gtd import frontmatter
from jobutils.gitops import GitOperationError, fetch as git_fetch
from jobutils.markdown.normalize import (
    markdown_to_jira_wiki,
    markdown_to_storage,
    parse_document,
)
from jobutils.metrics.events import append_event

from .adapters import SyncAdapter
from .defaults import load_sync_defaults
from .merge import three_way_merge
from .references import (
    append_reference_section,
    externalize_references,
    externalize_structured_references,
)


class SyncError(Exception):
    """A synchronization operation cannot safely continue."""

    pass


_EXTERNAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_EXTERNAL_FRONTMATTER_KEYS = {
    "jira_key",
    "jira_url",
    "jira_parent_key",
    "confluence_page_id",
    "confluence_url",
    "confluence_parent_id",
    "confluence_version",
    "sync_hash",
}


def _validate_external_identity(value: Optional[str], label: str) -> str:
    """Validate an Atlassian identity before writing it into front matter."""

    if not isinstance(value, str) or not _EXTERNAL_ID_RE.fullmatch(value):
        raise SyncError("{} must be a non-empty external identifier".format(label))
    return value


def _validate_external_url(value: Optional[str]) -> Optional[str]:
    """Allow only absolute HTTP(S) URLs for stored external references."""

    if value is None:
        return None
    if not isinstance(value, str) or any(character.isspace() for character in value):
        raise SyncError("unsafe external URL")
    parsed = urlparse(value)
    if (
        parsed.scheme.lower() not in ("http", "https")
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise SyncError("unsafe external URL")
    return value


def _atomic_frontmatter_update(path: Path, updates: Dict[str, str]) -> None:
    """Apply scalar front matter updates through a same-directory replacement."""

    with path.open("r", encoding="utf-8", newline="") as handle:
        original = handle.read()
    lines = original.splitlines()
    location = frontmatter.bounds(lines)
    if location is None:
        raise SyncError("managed Markdown requires YAML front matter")
    for line in lines[location[0] + 1 : location[1]]:
        if line.strip() and not re.match(r"^[A-Za-z_][A-Za-z0-9_-]*\s*:", line):
            raise SyncError("managed Markdown has invalid YAML front matter")
    for key, value in updates.items():
        frontmatter.set_value(lines, key, value)
    line_ending = "\r\n" if "\r\n" in original else "\n"
    trailing = original[len(original.rstrip("\r\n")) :]
    rendered = line_ending.join(lines) + trailing
    descriptor, temporary = tempfile.mkstemp(
        prefix=".jobutils-rebind-", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def rebind(
    repo_root: Path,
    relative_path: str,
    kind: str,
    external_id: str,
    url: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> Path:
    """Update stored Jira/Confluence identity fields without making API calls."""

    if kind not in ("jira", "confluence"):
        raise SyncError("kind must be jira or confluence")
    path = _managed_action_path(Path(repo_root).resolve(), relative_path)
    if not path.is_file():
        raise SyncError("managed Markdown file does not exist: {}".format(relative_path))
    identity = _validate_external_identity(external_id, "external ID")
    safe_url = _validate_external_url(url)
    safe_parent = (
        _validate_external_identity(parent_id, "parent ID")
        if parent_id is not None
        else None
    )
    if kind == "jira":
        updates = {"jira_key": identity}
        updates["jira_url"] = safe_url or ""
        if safe_parent is not None:
            updates["jira_parent_key"] = safe_parent
    else:
        old_page_id = frontmatter.value(
            path.read_text(encoding="utf-8").splitlines(), "confluence_page_id"
        )
        updates = {"confluence_page_id": identity}
        updates["confluence_url"] = safe_url or ""
        if safe_parent is not None:
            updates["confluence_parent_id"] = safe_parent
    _atomic_frontmatter_update(path, updates)
    if kind == "confluence" and old_page_id and old_page_id != identity:
        for child_path in _documents(Path(repo_root).resolve()):
            if child_path == path:
                continue
            child_lines = child_path.read_text(encoding="utf-8").splitlines()
            if frontmatter.bounds(child_lines) is None:
                continue
            if frontmatter.value(child_lines, "confluence_parent_id") == old_page_id:
                _atomic_frontmatter_update(
                    child_path, {"confluence_parent_id": identity}
                )
    return path


def _bool(value: Optional[str]) -> bool:
    """Interpret common YAML-like boolean spellings."""

    return str(value).lower() in ("1", "true", "yes", "on")


def _source_hash(repo_root: Path, paths: List[Path]) -> str:
    """Hash the relative paths and bytes used to build a sync plan."""

    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(repo_root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _source_fingerprint(lines: List[str], public_body: str) -> str:
    """Hash authoring data while excluding generated external identities."""

    location = frontmatter.bounds(lines)
    metadata = []
    if location is not None:
        for line in lines[location[0] + 1 : location[1]]:
            key = line.split(":", 1)[0].strip() if ":" in line else ""
            if key not in _EXTERNAL_FRONTMATTER_KEYS:
                metadata.append(line.rstrip())
    value = json.dumps(
        {"metadata": metadata, "public_body": public_body},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _documents(repo_root: Path) -> List[Path]:
    """Return task and document Markdown files eligible for synchronization."""

    paths = (
        list((repo_root / "gtd_tasks").rglob("*.md"))
        if (repo_root / "gtd_tasks").is_dir()
        else []
    )
    paths += (
        list((repo_root / "documents").rglob("*.md"))
        if (repo_root / "documents").is_dir()
        else []
    )
    return sorted(paths)


def _published_paths(repo_root: Path) -> List[Path]:
    """Return all managed files selected for external publication."""

    result = []
    for path in _documents(repo_root):
        lines = path.read_text(encoding="utf-8").splitlines()
        if frontmatter.bounds(lines) is None:
            continue
        document = parse_document(str(path))
        if _bool(document.metadata.get("publish_jira")) or _bool(
            document.metadata.get("publish_confluence")
        ):
            result.append(path)
    return result


def _payload(repo_root: Path, path: Path, kind: str) -> Dict:
    """Build the sanitized adapter payload for one Markdown document."""

    document = parse_document(str(path))
    defaults = load_sync_defaults()
    body = externalize_references(repo_root, document.public_body, path)
    body = append_reference_section(
        body,
        externalize_structured_references(
            repo_root, document.metadata.get("references") or []
        ),
    )
    if kind == "jira":
        return {
            "gtd_id": document.metadata.get("gtd_id"),
            "title": document.metadata.get("title") or path.stem,
            "description": markdown_to_jira_wiki(body),
            "project": document.metadata.get("jira_project") or defaults["jira_project"],
            "issue_type": document.metadata.get("jira_issue_type") or defaults["jira_issue_type"],
            "summary_field": document.metadata.get("jira_summary_field")
            or defaults["jira_summary_field"],
            "description_field": document.metadata.get("jira_description_field")
            or defaults["jira_description_field"],
            "parent_key": document.metadata.get("jira_parent_key"),
            "jira_key": document.metadata.get("jira_key"),
            "jira_url": document.metadata.get("jira_url"),
            "progress_comment": document.section("Progress Comment"),
            "progress_comment_field": document.metadata.get(
                "jira_progress_comment_field"
            )
            or defaults["jira_progress_comment_field"],
            "progress_comment_format": document.metadata.get(
                "jira_progress_comment_format"
            )
            or "text",
        }
    return {
        "gtd_id": document.metadata.get("gtd_id"),
        "title": document.metadata.get("title") or path.stem,
        "storage_body": markdown_to_storage(body),
        "space_id": document.metadata.get("confluence_space_id")
        or defaults["confluence_space_id"],
        "space_key": document.metadata.get("confluence_space_key")
        or defaults["confluence_space_key"],
        "parent_id": document.metadata.get("confluence_parent_id")
        or defaults["confluence_parent_id"]
        or None,
        "confluence_url": document.metadata.get("confluence_url"),
        "version": int(document.metadata.get("confluence_version") or "0"),
    }


def create_plan(
    repo_root: Path, observations: Optional[Dict[str, object]] = None
) -> Dict:
    """Create a reviewable plan from Markdown and the latest check result."""

    repo_root = Path(repo_root).resolve()
    observations = (
        _load_observation(repo_root) if observations is None else observations
    )
    git_state = (observations or {}).get("git", {}).get("state")
    if git_state in ("remote_ahead", "diverged"):
        raise SyncError(
            "Git repository is {}; run sync update before creating a plan".format(
                git_state
            )
        )
    observed_by_path = {
        item.get("path"): item
        for item in (observations or {}).get("items", [])
        if isinstance(item, dict) and item.get("path")
    }
    paths = _documents(repo_root)
    actions: List[Dict] = []
    published_paths: List[Path] = []
    for path in sorted(paths, key=lambda value: (len(value.relative_to(repo_root).parts), str(value))):
        if frontmatter.bounds(path.read_text(encoding="utf-8").splitlines()) is None:
            continue
        document = parse_document(str(path))
        declared_kind = str(document.metadata.get("kind") or "").lower()
        if declared_kind == "task" and _bool(
            document.metadata.get("publish_confluence")
        ):
            raise SyncError(
                "task documents can publish only to Jira; remove publish_confluence"
            )
        if declared_kind == "document" and _bool(
            document.metadata.get("publish_jira")
        ):
            raise SyncError(
                "document documents can publish only to Confluence; "
                "remove publish_jira"
            )
        kind = (
            "jira"
            if _bool(document.metadata.get("publish_jira"))
            else "confluence"
            if _bool(document.metadata.get("publish_confluence"))
            else ""
        )
        if not kind:
            continue
        published_paths.append(path)
        external_id = (
            document.metadata.get("jira_key")
            if kind == "jira"
            else document.metadata.get("confluence_page_id")
        )
        relative_path = str(path.relative_to(repo_root)).replace("\\", "/")
        operation = "update" if external_id else "create"
        blocked_reason = None
        observed = observed_by_path.get(relative_path) if external_id else None
        if external_id:
            if observed and observed.get("state") == "error":
                raise SyncError(
                    "sync check failed for {}; run sync check again".format(
                        relative_path
                    )
                )
            if observed and observed.get("state") == "conflict":
                operation = "conflict"
                blocked_reason = "local and external content both changed"
            elif observed and observed.get("state") == "external_changed":
                if document.public_body == observed.get("local_public_body"):
                    operation = "import"
                else:
                    operation = "conflict"
                    blocked_reason = "local content changed after sync check"
            elif observed and observed.get("state") in ("clean", "converged"):
                continue
            source_fingerprint = _source_fingerprint(
                path.read_text(encoding="utf-8").splitlines(), document.public_body
            )
            if (
                operation == "update"
                and document.metadata.get("sync_hash") == source_fingerprint
            ):
                continue
            base_file = _base_path(repo_root, path)
            if (
                operation == "update"
                and not document.metadata.get("sync_hash")
                and base_file.is_file()
                and base_file.read_text(encoding="utf-8") == document.public_body
            ):
                continue
        action = {
            "action_id": str(uuid.uuid4()),
            "action": operation,
            "kind": kind,
            "path": relative_path,
            "external_id": external_id,
            "payload": _payload(repo_root, path, kind)
            if operation in ("create", "update")
            else {},
        }
        if blocked_reason:
            action["blocked_reason"] = blocked_reason
        if kind == "confluence" and operation in ("create", "update"):
            parent_path = document.metadata.get("confluence_parent_path")
            parent_path = parent_path or _infer_nested_parent_path(repo_root, path)
            if parent_path:
                action["parent_path"] = parent_path.replace("\\", "/")
        elif kind == "jira" and operation in ("create", "update"):
            parent_path = document.metadata.get("jira_parent_path")
            parent_path = parent_path or _infer_nested_parent_path(repo_root, path)
            if parent_path:
                action["parent_path"] = parent_path.replace("\\", "/")
        actions.append(action)
    return {
        "plan_id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "observation_id": (observations or {}).get("observation_id"),
        "source_hash": _source_hash(
            repo_root, _source_paths_for_actions(repo_root, actions, published_paths)
        ),
        "actions": _order_actions(actions),
    }


def _order_actions(actions: List[Dict]) -> List[Dict]:
    """Order actions so Confluence parents are applied before children."""

    by_path = {action["path"]: action for action in actions}
    ordered: List[Dict] = []
    visiting = set()
    visited = set()

    def visit(path: str) -> None:
        if path in visiting:
            kind = by_path[path]["kind"].capitalize()
            raise SyncError("cyclic {} parent relationship: {}".format(kind, path))
        if path in visited:
            return
        visiting.add(path)
        action = by_path[path]
        parent_path = action.get("parent_path")
        if parent_path in by_path:
            if by_path[parent_path]["kind"] != action["kind"]:
                raise SyncError(
                    "{} parent relationship points to a different sync kind: {}".format(
                        action["kind"].capitalize(), parent_path
                    )
                )
            visit(parent_path)
        visiting.remove(path)
        visited.add(path)
        ordered.append(action)

    for action in actions:
        visit(action["path"])
    return ordered


def save_plan(repo_root: Path, plan: Dict) -> Path:
    """Persist a plan under the GTD repository's local state directory."""

    path = (
        Path(repo_root) / ".jobutils" / "sync" / "plans" / (plan["plan_id"] + ".json")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def sync_status(repo_root: Path) -> Dict[str, object]:
    """Summarize local synchronization state without contacting Atlassian."""

    repo_root = Path(repo_root).resolve()
    from jobutils.metrics.reader import read_events

    events, read_errors = read_events(repo_root)
    sync_events = [
        event for event in events if str(event.get("event_type", "")).startswith("sync_")
    ]
    plan_paths = sorted(
        (repo_root / ".jobutils" / "sync" / "plans").glob("*.json")
    )
    plan_records = []
    latest_plan = None
    for path in plan_paths:
        if path.is_symlink() or not path.is_file():
            continue
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
            if _is_valid_plan(plan):
                plan_records.append((path, plan))
        except (OSError, ValueError):
            continue
    pending_actions = 0
    if plan_records:
        path, plan = max(
            plan_records,
            key=lambda item: (int(item[0].stat().st_mtime), item[0].name),
        )
        latest_plan = str(path.relative_to(repo_root)).replace("\\", "/")
        pending_actions = len(plan.get("actions", []))
    base_paths = list(
        (repo_root / ".jobutils" / "sync" / "bases").glob("*.md")
    )
    conflict_count = 0
    for path in _documents(repo_root):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "<<<<<<< local" in text and ">>>>>>> external" in text:
            conflict_count += 1
    return {
        "base_count": len(base_paths),
        "conflict_count": conflict_count,
        "latest_plan": latest_plan,
        "pending_actions": pending_actions,
        "plan_count": len(plan_records),
        "last_sync_at": sync_events[-1]["occurred_at"] if sync_events else None,
        "error_count": sum(
            1 for event in sync_events if event.get("event_type") == "sync_error"
        ),
        "read_error_count": len(read_errors),
    }


def _is_valid_plan(plan: object) -> bool:
    """Return whether a saved plan has the structure required for apply."""

    if not isinstance(plan, dict):
        return False
    if not isinstance(plan.get("plan_id"), str) or not plan["plan_id"]:
        return False
    if not isinstance(plan.get("created_at"), str) or not plan["created_at"]:
        return False
    source_hash = plan.get("source_hash")
    if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
        return False
    if plan.get("observation_id") is not None and not isinstance(
        plan.get("observation_id"), str
    ):
        return False
    actions = plan.get("actions")
    if not isinstance(actions, list):
        return False
    for action in actions:
        if not isinstance(action, dict):
            return False
        if not isinstance(action.get("action_id"), str) or not action["action_id"]:
            return False
        if action.get("action") not in ("create", "update", "import", "conflict"):
            return False
        if action.get("kind") not in ("jira", "confluence"):
            return False
        if not _is_safe_plan_path(action.get("path")):
            return False
        if not isinstance(action.get("payload"), dict):
            return False
        if action["action"] in ("create", "update") and not _is_valid_payload(
            action["kind"], action["payload"]
        ):
            return False
        if action.get("parent_path"):
            valid_parent = (
                _is_safe_document_path(action["parent_path"])
                if action["kind"] == "confluence"
                else _is_safe_task_path(action["parent_path"])
            )
            if not valid_parent:
                return False
        if action["action"] in ("update", "import", "conflict") and not action.get(
            "external_id"
        ):
            return False
    return True


def _is_safe_plan_path(path: object) -> bool:
    """Return whether a plan path is a relative managed Markdown path."""

    if not isinstance(path, str) or not path:
        return False
    candidate = Path(path)
    return (
        not candidate.is_absolute()
        and ".." not in candidate.parts
        and candidate.parts[:1] in (("documents",), ("gtd_tasks",))
        and candidate.suffix.lower() == ".md"
    )


def _is_safe_document_path(path: object) -> bool:
    """Return whether a path can identify a Confluence parent document."""

    if not _is_safe_plan_path(path):
        return False
    return Path(path).parts[:1] == ("documents",)


def _is_safe_task_path(path: object) -> bool:
    """Return whether a path can identify a Jira parent task document."""

    if not _is_safe_plan_path(path):
        return False
    return Path(path).parts[:1] == ("gtd_tasks",)


def _infer_nested_parent_path(repo_root: Path, path: Path) -> Optional[str]:
    """Infer the conventional parent Markdown path for a nested detail file."""

    relative = path.relative_to(repo_root)
    if len(relative.parts) < 3:
        return None
    candidate = path.parent.parent / (path.parent.name + ".md")
    if not candidate.is_file():
        return None
    return str(candidate.relative_to(repo_root)).replace("\\", "/")


def _source_paths_for_actions(
    repo_root: Path, actions: List[Dict], base_paths: List[Path]
) -> List[Path]:
    """Include existing local parent files in the plan's source hash."""

    paths = list(base_paths)
    for action in actions:
        parent_path = action.get("parent_path")
        if not parent_path:
            continue
        valid_parent = (
            _is_safe_document_path(parent_path)
            if action["kind"] == "confluence"
            else _is_safe_task_path(parent_path)
        )
        if not valid_parent:
            raise SyncError("unsafe {} parent path: {}".format(action["kind"], parent_path))
        parent = _managed_action_path(repo_root, parent_path)
        if parent.is_file() and parent not in paths:
            paths.append(parent)
    return paths


def _is_valid_payload(kind: str, payload: Dict) -> bool:
    """Return whether a plan payload has the fields its adapter consumes."""

    if kind == "jira":
        return (
            isinstance(payload.get("title"), str)
            and isinstance(payload.get("description"), str)
            and isinstance(payload.get("issue_type"), str)
            and isinstance(payload.get("project"), str)
        )
    return (
        isinstance(payload.get("title"), str)
        and isinstance(payload.get("storage_body"), str)
        and isinstance(payload.get("space_id"), str)
        and isinstance(payload.get("space_key"), str)
        and isinstance(payload.get("version"), int)
        and not isinstance(payload.get("version"), bool)
    )


def _managed_action_path(repo_root: Path, relative_path: str) -> Path:
    """Resolve an action path and reject traversal or symlink escapes."""

    if not _is_safe_plan_path(relative_path):
        raise SyncError("sync plan contains an unsafe Markdown path")
    candidate = (repo_root / relative_path).resolve()
    for directory in ("documents", "gtd_tasks"):
        managed_root = (repo_root / directory).resolve()
        try:
            managed_root.relative_to(repo_root)
            candidate.relative_to(managed_root)
        except ValueError:
            continue
        return candidate
    raise SyncError("sync plan path is outside the managed Markdown roots")


def _set_external(
    path: Path, kind: str, result: Dict, payload: Optional[Dict] = None
) -> None:
    """Write returned external identities and the post-apply source hash."""

    lines = path.read_text(encoding="utf-8").splitlines()
    if kind == "jira":
        if payload:
            frontmatter.set_value(lines, "jira_project", payload.get("project") or "")
            frontmatter.set_value(
                lines, "jira_issue_type", payload.get("issue_type") or "Task"
            )
            frontmatter.set_value(
                lines,
                "jira_summary_field",
                payload.get("summary_field") or "summary",
            )
            frontmatter.set_value(
                lines,
                "jira_description_field",
                payload.get("description_field") or "description",
            )
            frontmatter.set_value(
                lines,
                "jira_progress_comment_field",
                payload.get("progress_comment_field") or "",
            )
        frontmatter.set_value(
            lines, "jira_key", result.get("key") or result.get("id") or ""
        )
        frontmatter.set_value(lines, "jira_url", result.get("url") or "")
        if payload and payload.get("parent_key"):
            frontmatter.set_value(
                lines, "jira_parent_key", str(payload["parent_key"])
            )
    else:
        if payload:
            frontmatter.set_value(
                lines, "confluence_space_id", payload.get("space_id") or ""
            )
            frontmatter.set_value(
                lines, "confluence_space_key", payload.get("space_key") or ""
            )
            if payload.get("parent_id") is not None:
                frontmatter.set_value(
                    lines, "confluence_parent_id", str(payload["parent_id"])
                )
        frontmatter.set_value(lines, "confluence_page_id", str(result.get("id") or ""))
        frontmatter.set_value(lines, "confluence_url", result.get("url") or "")
        if result.get("version") is not None:
            frontmatter.set_value(lines, "confluence_version", str(result["version"]))
        if payload and payload.get("parent_id"):
            frontmatter.set_value(
                lines, "confluence_parent_id", str(payload["parent_id"])
            )
    document = parse_document(str(path))
    frontmatter.set_value(
        lines,
        "sync_hash",
        _source_fingerprint(lines, document.public_body),
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))


def _replace_level_one_section(body: str, heading: str, content: str) -> str:
    """Replace or append one public level-one Markdown section."""

    heading_pattern = re.compile(
        r"(?m)^#\s+{}\s*$".format(re.escape(heading))
    )
    match = heading_pattern.search(body)
    replacement = "# {}\n\n{}\n".format(heading, content.strip())
    if not match:
        return body.rstrip() + "\n\n" + replacement
    next_heading = re.search(r"(?m)^#\s+.+?\s*$", body[match.end() :])
    end = match.end() + next_heading.start() if next_heading else len(body)
    return body[: match.start()] + replacement + body[end:]


def _materialize_external_reference(path: Path, kind: str, result: Dict) -> None:
    """Add or update a clickable external identity in local References."""

    url = _validate_external_url(result.get("url"))
    if not url:
        return
    if kind == "jira":
        identity = result.get("key") or result.get("id") or "issue"
        label = "Jira"
    else:
        identity = result.get("id") or "page"
        label = "Confluence"
    reference = "- {}: [{}]({})".format(label, identity, url)

    document = parse_document(str(path))
    lines = document.section("References").splitlines()
    updated = []
    replaced = False
    prefix = "- {}:".format(label)
    for line in lines:
        if line.strip().startswith(prefix):
            if not replaced:
                updated.append(reference)
                replaced = True
            continue
        updated.append(line)
    if not replaced:
        while updated and not updated[-1].strip():
            updated.pop()
        if updated:
            updated.append("")
        updated.append(reference)

    public_body = _replace_level_one_section(
        document.public_body, "References", "\n".join(updated)
    )
    body = public_body.rstrip() + "\n"
    if document.implementation_note.strip():
        body += "\n# Implementation Note\n\n{}\n".format(
            document.implementation_note.strip()
        )

    source_lines = path.read_text(encoding="utf-8").splitlines()
    location = frontmatter.bounds(source_lines)
    if location is None:
        raise SyncError("managed Markdown has no front matter: {}".format(path))
    rendered = "\n".join(source_lines[: location[1] + 1]) + "\n\n" + body.lstrip()
    descriptor, temporary = tempfile.mkstemp(
        prefix=".jobutils-reference-", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def apply_plan(repo_root: Path, plan: Dict, adapter: SyncAdapter) -> List[Dict]:
    """Apply a non-stale plan through the selected synchronization adapter."""

    repo_root = Path(repo_root).resolve()
    if not _is_valid_plan(plan):
        raise SyncError("sync plan has invalid structure")
    observed_by_path = {}
    if plan.get("observation_id"):
        observation = _load_observation(repo_root)
        if not observation or observation.get("observation_id") != plan.get(
            "observation_id"
        ):
            raise SyncError("sync check observation is stale; run sync check again")
        observed_by_path = {
            item.get("path"): item
            for item in observation.get("items", [])
            if isinstance(item, dict) and item.get("path")
        }
        git_state = observation.get("git", {}).get("state")
        if git_state in ("remote_ahead", "diverged"):
            raise SyncError(
                "Git repository is {}; run sync update before applying".format(
                    git_state
                )
            )
        for observed in observed_by_path.values():
            current_remote = adapter.fetch(
                observed["kind"],
                observed["external_id"],
                observed.get("fetch_options") or {},
            )
            previous_remote = observed.get("remote") or {}
            if current_remote.get("body_markdown") != previous_remote.get(
                "body_markdown"
            ):
                raise SyncError(
                    "external record changed since sync check for {}".format(
                        observed["path"]
                    )
                )
    conflicts = [
        action
        for action in plan["actions"]
        if action.get("action") == "conflict"
    ]
    paths = [
        _managed_action_path(repo_root, action["path"])
        for action in plan["actions"]
    ]
    hash_paths = _source_paths_for_actions(
        repo_root, plan["actions"], _published_paths(repo_root)
    )
    if _source_hash(repo_root, hash_paths) != plan.get("source_hash"):
        raise SyncError("sync plan is stale; create a new plan")
    if conflicts:
        if not observed_by_path:
            raise SyncError(
                "sync plan contains unresolved conflict; run sync check again"
            )
        for action in conflicts:
            observed = observed_by_path.get(action["path"])
            if not observed or not isinstance(observed.get("remote"), dict):
                raise SyncError(
                    "sync conflict observation is stale for {}; run sync check again".format(
                        action["path"]
                    )
                )
            conflict_path = _managed_action_path(repo_root, action["path"])
            _write_conflict_markers(
                conflict_path, observed.get("base_body"), observed["remote"]
            )
            append_event(
                repo_root,
                "sync_conflict",
                action["path"],
                source={
                    "machine_id": os.environ.get("JOBUTILS_MACHINE_ID", "unknown"),
                    "command": "sync apply",
                },
                kind=action["kind"],
                path=action["path"],
            )
        raise SyncError(
            "sync plan contains unresolved conflict; markers written: {}".format(
                ", ".join(action.get("path", "") for action in conflicts)
            )
        )
    results = []
    created_external_ids: Dict[str, str] = {}
    for action, path in zip(plan["actions"], paths):
        if action["action"] == "import":
            observed = observed_by_path.get(action["path"])
            if (
                not observed
                or observed.get("state") != "external_changed"
                or not isinstance(observed.get("remote"), dict)
            ):
                raise SyncError(
                    "sync import observation is stale for {}; run sync check again".format(
                        action["path"]
                    )
                )
            if parse_document(str(path)).public_body != observed.get(
                "local_public_body"
            ):
                raise SyncError(
                    "sync import observation is stale for {}; run sync check again".format(
                        action["path"]
                    )
                )
            _import_remote_record(repo_root, path, observed["remote"])
            document = parse_document(str(path))
            append_event(
                repo_root,
                "sync_pulled",
                document.metadata.get("gtd_id") or action["path"],
                source={
                    "machine_id": os.environ.get("JOBUTILS_MACHINE_ID", "unknown"),
                    "command": "sync apply",
                },
                kind=action["kind"],
                path=action["path"],
            )
            results.append(
                {
                    "action_id": action["action_id"],
                    "action": "import",
                    "path": action["path"],
                    "result": observed["remote"],
                }
            )
            continue
        payload = dict(action["payload"])
        if action.get("parent_path"):
            parent_path = action["parent_path"]
            parent_id = created_external_ids.get(parent_path)
            if not parent_id:
                parent = _managed_action_path(repo_root, parent_path)
                if parent.is_file():
                    parent_lines = parent.read_text(encoding="utf-8").splitlines()
                    parent_id = frontmatter.value(
                        parent_lines,
                        "confluence_page_id"
                        if action["kind"] == "confluence"
                        else "jira_key",
                    )
            if not parent_id:
                label = (
                    "Confluence parent page"
                    if action["kind"] == "confluence"
                    else "Jira parent issue"
                )
                raise SyncError("{} is unresolved: {}".format(label, parent_path))
            payload[
                "parent_id" if action["kind"] == "confluence" else "parent_key"
            ] = parent_id
        try:
            if action["action"] == "create":
                result = adapter.create(action["kind"], payload)
            else:
                result = adapter.update(action["kind"], action["external_id"], payload)
        except Exception as error:
            append_event(
                repo_root,
                "sync_error",
                payload.get("gtd_id") or action["path"],
                source={
                    "machine_id": os.environ.get("JOBUTILS_MACHINE_ID", "unknown"),
                    "command": "sync apply",
                },
                kind=action["kind"],
                action=action["action"],
                path=action["path"],
                error=error.__class__.__name__,
            )
            raise SyncError(
                "sync apply failed for {}: {}".format(action["path"], error)
            ) from error
        _materialize_external_reference(path, action["kind"], result)
        _set_external(path, action["kind"], result, payload)
        external_id = (
            result.get("id")
            if action["kind"] == "confluence"
            else result.get("key") or result.get("id")
        )
        if external_id:
            created_external_ids[action["path"]] = str(external_id)
        _write_base(repo_root, path, parse_document(str(path)).public_body)
        append_event(
            repo_root,
            "sync_applied",
            payload.get("gtd_id") or action["path"],
            source={
                "machine_id": os.environ.get("JOBUTILS_MACHINE_ID", "unknown"),
                "command": "sync apply",
            },
            kind=action["kind"],
            action=action["action"],
            path=action["path"],
        )
        results.append(
            {
                "action_id": action["action_id"],
                "action": action["action"],
                "path": action["path"],
                "result": result,
            }
        )
    return results


def classify_drift(
    base: Optional[str], local: str, remote: str
) -> str:
    """Classify local and external public bodies against the last base."""

    if base is None:
        return "unknown"
    if local == remote:
        return "clean" if local == base else "converged"
    if local == base:
        return "external_changed"
    if remote == base:
        return "local_changed"
    return "conflict"


def _observation_path(repo_root: Path) -> Path:
    """Return the ignored local path for the latest refresh observation."""

    return repo_root / ".jobutils" / "sync" / "observations" / "latest.json"


def _load_observation(repo_root: Path) -> Optional[Dict[str, object]]:
    """Load the latest check observation when one exists."""

    path = _observation_path(repo_root)
    if not path.is_file():
        return None
    try:
        observation = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SyncError("invalid sync check observation: {}".format(error)) from error
    if (
        not isinstance(observation, dict)
        or not isinstance(observation.get("observation_id"), str)
        or not isinstance(observation.get("items"), list)
    ):
        raise SyncError("invalid sync check observation structure")
    return observation


def _write_observation(repo_root: Path, observation: Dict[str, object]) -> None:
    """Persist one refresh observation without adding it to the source tree."""

    target = _observation_path(repo_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(observation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(str(temporary), str(target))


def check(
    repo_root: Path, adapter: SyncAdapter, refresh_git: bool = False
) -> Dict[str, object]:
    """Refresh and inspect Git/Atlassian drift without commit or push."""

    repo_root = Path(repo_root).resolve()
    items: List[Dict[str, object]] = []
    error_count = 0
    errors: List[str] = []
    if refresh_git:
        try:
            git_result = git_fetch(repo_root)
        except GitOperationError as error:
            git_result = {"performed": False, "error": str(error)}
    else:
        git_result = {"performed": False, "skipped": True}
    observation_id = str(uuid.uuid4())
    sync_defaults = load_sync_defaults()
    git_state = git_result.get("state")
    if git_state in ("remote_ahead", "diverged"):
        error_count += 1
        errors.append(
            "Git repository is {}; run sync update before checking external state".format(
                git_state
            )
        )
    for path in [] if errors else _documents(repo_root):
        relative_path = str(path.relative_to(repo_root)).replace("\\", "/")
        try:
            document = parse_document(str(path))
            kind = (
                "jira"
                if _bool(document.metadata.get("publish_jira"))
                else "confluence"
                if _bool(document.metadata.get("publish_confluence"))
                else ""
            )
            external_id = (
                document.metadata.get("jira_key")
                if kind == "jira"
                else document.metadata.get("confluence_page_id")
            )
            if not kind or not external_id:
                continue
            remote = adapter.fetch(
                kind,
                external_id,
                fetch_options := {
                    "progress_comment_field": document.metadata.get(
                        "jira_progress_comment_field"
                    ),
                    "summary_field": document.metadata.get("jira_summary_field")
                    or sync_defaults["jira_summary_field"],
                    "description_field": document.metadata.get(
                        "jira_description_field"
                    )
                    or sync_defaults["jira_description_field"],
                    "progress_comment_format": document.metadata.get(
                        "jira_progress_comment_format"
                    )
                    or "text",
                },
            )
            remote_body = remote.get("body_markdown")
            if not isinstance(remote_body, str):
                raise SyncError("external body is missing")
            base_file = _base_path(repo_root, path)
            base = (
                base_file.read_text(encoding="utf-8")
                if base_file.is_file()
                else None
            )
            state = classify_drift(base, document.public_body, remote_body)
            items.append(
                {
                    "path": relative_path,
                    "kind": kind,
                    "external_id": external_id,
                    "external_url": remote.get("url")
                    or document.metadata.get(
                        "jira_url" if kind == "jira" else "confluence_url"
                    ),
                    "state": state,
                }
            )
            items[-1]["_observation"] = {
                "path": relative_path,
                "kind": kind,
                "external_id": external_id,
                "state": state,
                "local_public_body": document.public_body,
                "base_body": base,
                "remote": remote,
                "fetch_options": fetch_options,
            }
        except Exception as error:
            error_count += 1
            items.append(
                {
                    "path": relative_path,
                    "state": "error",
                    "error": str(error),
                }
            )
    observations = [
        item.pop("_observation") for item in items if "_observation" in item
    ]
    observation = {
        "observation_id": observation_id,
        "checked_at": datetime.utcnow().isoformat() + "Z",
        "git": git_result,
        "items": observations,
    }
    _write_observation(repo_root, observation)
    return {
        "checked": len(items),
        "error_count": error_count,
        "errors": errors,
        "git": git_result,
        "observation_id": observation_id,
        "items": items,
    }


def _base_path(repo_root: Path, path: Path) -> Path:
    """Return the deterministic base snapshot path for a Markdown file."""

    name = hashlib.sha1(str(path.relative_to(repo_root)).encode("utf-8")).hexdigest()
    return repo_root / ".jobutils" / "sync" / "bases" / (name + ".md")


def _write_base(repo_root: Path, path: Path, body: str) -> None:
    """Store the public body used by the next three-way pull."""

    target = _base_path(repo_root, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


def _apply_remote_metadata(path: Path, remote: Dict) -> None:
    """Materialize external title, relationship metadata, and progress text."""

    document = parse_document(str(path))
    lines = path.read_text(encoding="utf-8").splitlines()
    changed = False
    for key, value in (
        ("title", remote.get("title")),
        ("jira_issue_type", remote.get("issue_type")),
        ("jira_parent_key", remote.get("parent_key")),
        ("confluence_parent_id", remote.get("parent_id")),
        ("confluence_version", remote.get("version")),
    ):
        if value is not None:
            frontmatter.set_value(lines, key, str(value))
            changed = True
    body = document.public_body
    if remote.get("progress_comment") is not None:
        body = _replace_level_one_section(
            body, "Progress Comment", str(remote["progress_comment"])
        )
        changed = True
    if changed:
        closing = frontmatter.bounds(lines)
        if closing is None:
            raise SyncError("managed Markdown has no front matter: {}".format(path))
        suffix = document.implementation_note.rstrip("\n")
        body_lines = body.rstrip("\n").splitlines()
        if suffix:
            body_lines += ["", "# Implementation Note", ""] + suffix.splitlines()
        path.write_text(
            "\n".join(lines[: closing[1] + 1] + [""] + body_lines).rstrip("\n")
            + "\n",
            encoding="utf-8",
        )


def _import_remote_record(repo_root: Path, path: Path, remote: Dict) -> None:
    """Accept an external-only change into Markdown and refresh its base."""

    remote_body = remote.get("body_markdown")
    if not isinstance(remote_body, str):
        raise SyncError("external body is missing")
    document = parse_document(str(path))
    lines = path.read_text(encoding="utf-8").splitlines()
    closing = frontmatter.bounds(lines)
    if closing is None:
        raise SyncError("managed Markdown has no front matter: {}".format(path))
    body_lines = remote_body.rstrip("\n").splitlines()
    suffix = document.implementation_note.rstrip("\n")
    if suffix:
        body_lines += ["", "# Implementation Note", ""] + suffix.splitlines()
    path.write_text(
        "\n".join(lines[: closing[1] + 1] + [""] + body_lines).rstrip("\n")
        + "\n",
        encoding="utf-8",
    )
    _apply_remote_metadata(path, remote)
    _write_base(repo_root, path, parse_document(str(path)).public_body)


def _write_conflict_markers(
    path: Path, base_body: Optional[str], remote: Dict
) -> None:
    """Write a three-way conflict into public Markdown while preserving notes."""

    remote_body = remote.get("body_markdown")
    if not isinstance(remote_body, str):
        raise SyncError("external body is missing")
    document = parse_document(str(path))
    merged, conflict = three_way_merge(
        base_body if base_body is not None else document.public_body,
        document.public_body,
        remote_body,
    )
    if not conflict:
        raise SyncError("sync conflict observation no longer contains two-sided changes")
    lines = path.read_text(encoding="utf-8").splitlines()
    closing = frontmatter.bounds(lines)
    if closing is None:
        raise SyncError("managed Markdown has no front matter: {}".format(path))
    body_lines = merged.rstrip("\n").splitlines()
    suffix = document.implementation_note.rstrip("\n")
    if suffix:
        body_lines += ["", "# Implementation Note", ""] + suffix.splitlines()
    path.write_text(
        "\n".join(lines[: closing[1] + 1] + [""] + body_lines).rstrip("\n")
        + "\n",
        encoding="utf-8",
    )

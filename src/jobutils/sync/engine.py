"""Plan, apply, and pull synchronization changes for managed Markdown."""

import hashlib
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from jobutils.gtd import frontmatter
from jobutils.markdown.normalize import markdown_to_adf, markdown_to_storage, parse_document

from .adapters import SyncAdapter
from .defaults import load_sync_defaults
from .references import externalize_references
from .merge import three_way_merge


class SyncError(Exception):
    """A synchronization operation cannot safely continue."""

    pass


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


def _payload(repo_root: Path, path: Path, kind: str) -> Dict:
    """Build the sanitized adapter payload for one Markdown document."""

    document = parse_document(str(path))
    defaults = load_sync_defaults()
    body = externalize_references(repo_root, document.public_body, path)
    if kind == "jira":
        return {
            "title": document.metadata.get("title") or path.stem,
            "description_adf": markdown_to_adf(body),
            "project": document.metadata.get("jira_project") or defaults["jira_project"],
            "issue_type": document.metadata.get("jira_issue_type") or defaults["jira_issue_type"],
            "parent_key": document.metadata.get("jira_parent_key"),
            "jira_key": document.metadata.get("jira_key"),
            "jira_url": document.metadata.get("jira_url"),
            "progress_comment": document.section("Progress Comment"),
            "progress_comment_field": document.metadata.get(
                "jira_progress_comment_field"
            )
            or defaults["jira_progress_comment_field"],
        }
    return {
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


def create_plan(repo_root: Path) -> Dict:
    """Create a reviewable plan without calling an external write endpoint."""

    repo_root = Path(repo_root).resolve()
    paths = _documents(repo_root)
    actions: List[Dict] = []
    published_paths: List[Path] = []
    for path in sorted(paths, key=lambda value: (len(value.relative_to(repo_root).parts), str(value))):
        document = parse_document(str(path))
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
        operation = "update" if external_id else "create"
        action = {
                "action_id": str(uuid.uuid4()),
                "action": operation,
                "kind": kind,
                "path": str(path.relative_to(repo_root)).replace("\\", "/"),
                "external_id": external_id,
                "payload": _payload(repo_root, path, kind),
        }
        if kind == "confluence":
            parent_path = document.metadata.get("confluence_parent_path")
            if not parent_path:
                relative = path.relative_to(repo_root)
                if len(relative.parts) >= 3:
                    candidate = path.parent.parent / (path.parent.name + ".md")
                    if candidate.is_file():
                        parent_path = str(candidate.relative_to(repo_root)).replace(
                            "\\", "/"
                        )
            if parent_path:
                action["parent_path"] = parent_path.replace("\\", "/")
        actions.append(action)
    return {
        "plan_id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "source_hash": _source_hash(repo_root, published_paths),
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
            raise SyncError("cyclic Confluence parent relationship: {}".format(path))
        if path in visited:
            return
        visiting.add(path)
        action = by_path[path]
        parent_path = action.get("parent_path") if action["kind"] == "confluence" else None
        if parent_path in by_path:
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
    actions = plan.get("actions")
    if not isinstance(actions, list):
        return False
    for action in actions:
        if not isinstance(action, dict):
            return False
        if not isinstance(action.get("action_id"), str) or not action["action_id"]:
            return False
        if action.get("action") not in ("create", "update"):
            return False
        if action.get("kind") not in ("jira", "confluence"):
            return False
        if not _is_safe_plan_path(action.get("path")):
            return False
        if not isinstance(action.get("payload"), dict):
            return False
        if not _is_valid_payload(action["kind"], action["payload"]):
            return False
        if action["kind"] == "confluence" and action.get("parent_path"):
            if not _is_safe_document_path(action["parent_path"]):
                return False
        if action["action"] == "update" and not action.get("external_id"):
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


def _is_valid_payload(kind: str, payload: Dict) -> bool:
    """Return whether a plan payload has the fields its adapter consumes."""

    if kind == "jira":
        return (
            isinstance(payload.get("title"), str)
            and isinstance(payload.get("description_adf"), dict)
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
        frontmatter.set_value(
            lines, "jira_key", result.get("key") or result.get("id") or ""
        )
        frontmatter.set_value(lines, "jira_url", result.get("url") or "")
    else:
        frontmatter.set_value(lines, "confluence_page_id", str(result.get("id") or ""))
        frontmatter.set_value(lines, "confluence_url", result.get("url") or "")
        if payload and payload.get("parent_id"):
            frontmatter.set_value(
                lines, "confluence_parent_id", str(payload["parent_id"])
            )
    frontmatter.set_value(
        lines, "sync_hash", hashlib.sha256(path.read_bytes()).hexdigest()
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))


def apply_plan(repo_root: Path, plan: Dict, adapter: SyncAdapter) -> List[Dict]:
    """Apply a non-stale plan through the selected synchronization adapter."""

    repo_root = Path(repo_root).resolve()
    if not _is_valid_plan(plan):
        raise SyncError("sync plan has invalid structure")
    paths = [
        _managed_action_path(repo_root, action["path"])
        for action in plan["actions"]
    ]
    if _source_hash(repo_root, paths) != plan.get("source_hash"):
        raise SyncError("sync plan is stale; create a new plan")
    results = []
    created_external_ids: Dict[str, str] = {}
    for action, path in zip(plan["actions"], paths):
        payload = dict(action["payload"])
        if action["kind"] == "confluence" and action.get("parent_path"):
            parent_path = action["parent_path"]
            parent_id = created_external_ids.get(parent_path)
            if not parent_id:
                parent = _managed_action_path(repo_root, parent_path)
                if parent.is_file():
                    parent_lines = parent.read_text(encoding="utf-8").splitlines()
                    parent_id = frontmatter.value(parent_lines, "confluence_page_id")
            if not parent_id:
                raise SyncError(
                    "Confluence parent page is unresolved: {}".format(parent_path)
                )
            payload["parent_id"] = parent_id
        if action["action"] == "create":
            result = adapter.create(action["kind"], payload)
        else:
            result = adapter.update(action["kind"], action["external_id"], payload)
        _set_external(path, action["kind"], result, payload)
        if action["kind"] == "confluence" and result.get("id"):
            created_external_ids[action["path"]] = str(result["id"])
        _write_base(repo_root, path, parse_document(str(path)).public_body)
        results.append(
            {"action_id": action["action_id"], "path": action["path"], "result": result}
        )
    return results


def _base_path(repo_root: Path, path: Path) -> Path:
    """Return the deterministic base snapshot path for a Markdown file."""

    name = hashlib.sha1(str(path.relative_to(repo_root)).encode("utf-8")).hexdigest()
    return repo_root / ".jobutils" / "sync" / "bases" / (name + ".md")


def _write_base(repo_root: Path, path: Path, body: str) -> None:
    """Store the public body used by the next three-way pull."""

    target = _base_path(repo_root, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


def pull(repo_root: Path, adapter: SyncAdapter) -> List[Dict]:
    """Pull external content and preserve two-sided changes as conflicts."""

    repo_root = Path(repo_root).resolve()
    results: List[Dict] = []
    for path in _documents(repo_root):
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
        remote = adapter.fetch(kind, external_id)
        base_file = _base_path(repo_root, path)
        base = (
            base_file.read_text(encoding="utf-8")
            if base_file.is_file()
            else document.public_body
        )
        # Keep the private implementation note outside the merge input so it
        # can never be sent to Jira or Confluence.
        merged, conflict = three_way_merge(
            base, document.public_body, remote.get("body_markdown", "")
        )
        if not conflict:
            lines = path.read_text(encoding="utf-8").splitlines()
            closing = frontmatter.bounds(lines)
            if closing is None:
                raise SyncError("managed Markdown has no front matter: {}".format(path))
            suffix = document.implementation_note.rstrip("\n")
            body_lines = merged.rstrip("\n").splitlines()
            if suffix:
                body_lines += ["", "# Implementation Note", ""] + suffix.splitlines()
            new_lines = lines[: closing[1] + 1] + [""] + body_lines
            path.write_text("\n".join(new_lines).rstrip("\n") + "\n", encoding="utf-8")
            _write_base(repo_root, path, remote.get("body_markdown", ""))
        else:
            lines = path.read_text(encoding="utf-8").splitlines()
            closing = frontmatter.bounds(lines)
            suffix = document.implementation_note.rstrip("\n")
            body_lines = merged.rstrip("\n").splitlines()
            if suffix:
                body_lines += ["", "# Implementation Note", ""] + suffix.splitlines()
            path.write_text(
                "\n".join(lines[: closing[1] + 1] + [""] + body_lines).rstrip("\n")
                + "\n",
                encoding="utf-8",
            )
        results.append(
            {
                "path": str(path.relative_to(repo_root)),
                "kind": kind,
                "conflict": conflict,
            }
        )
    return results

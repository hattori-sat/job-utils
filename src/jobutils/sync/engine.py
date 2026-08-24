"""Plan, apply, and pull synchronization changes for managed Markdown."""

import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from jobutils.gtd import frontmatter
from jobutils.markdown.normalize import markdown_to_storage, parse_document

from .adapters import SyncAdapter
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
    body = externalize_references(repo_root, document.public_body, path)
    if kind == "jira":
        return {
            "title": document.metadata.get("title") or path.stem,
            "description_adf": {
                "version": 1,
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": body}]}
                ],
            },
            "project": document.metadata.get("jira_project") or "",
            "issue_type": document.metadata.get("jira_issue_type") or "Task",
            "parent_key": document.metadata.get("jira_parent_key"),
            "jira_key": document.metadata.get("jira_key"),
            "jira_url": document.metadata.get("jira_url"),
            "progress_comment": document.section("Progress Comment"),
            "progress_comment_field": document.metadata.get(
                "jira_progress_comment_field"
            ),
        }
    return {
        "title": document.metadata.get("title") or path.stem,
        "storage_body": markdown_to_storage(body),
        "space_id": document.metadata.get("confluence_space_id") or "",
        "space_key": document.metadata.get("confluence_space_key") or "",
        "parent_id": document.metadata.get("confluence_parent_id"),
        "confluence_url": document.metadata.get("confluence_url"),
        "version": int(document.metadata.get("confluence_version") or "0"),
    }


def create_plan(repo_root: Path) -> Dict:
    """Create a reviewable plan without calling an external write endpoint."""

    repo_root = Path(repo_root).resolve()
    paths = _documents(repo_root)
    actions: List[Dict] = []
    published_paths: List[Path] = []
    for path in paths:
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
        action = "update" if external_id else "create"
        actions.append(
            {
                "action_id": str(uuid.uuid4()),
                "action": action,
                "kind": kind,
                "path": str(path.relative_to(repo_root)).replace("\\", "/"),
                "external_id": external_id,
                "payload": _payload(repo_root, path, kind),
            }
        )
    return {
        "plan_id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "source_hash": _source_hash(repo_root, published_paths),
        "actions": actions,
    }


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
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(plan, dict):
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


def _set_external(path: Path, kind: str, result: Dict) -> None:
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
    frontmatter.set_value(
        lines, "sync_hash", hashlib.sha256(path.read_bytes()).hexdigest()
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))


def apply_plan(repo_root: Path, plan: Dict, adapter: SyncAdapter) -> List[Dict]:
    """Apply a non-stale plan through the selected synchronization adapter."""

    repo_root = Path(repo_root).resolve()
    paths = [repo_root / action["path"] for action in plan.get("actions", [])]
    if _source_hash(repo_root, paths) != plan.get("source_hash"):
        raise SyncError("sync plan is stale; create a new plan")
    results = []
    for action in plan.get("actions", []):
        path = repo_root / action["path"]
        payload = action["payload"]
        if action["action"] == "create":
            result = adapter.create(action["kind"], payload)
        else:
            result = adapter.update(action["kind"], action["external_id"], payload)
        _set_external(path, action["kind"], result)
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

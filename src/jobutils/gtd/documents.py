"""Create and maintain Document Markdown entries from ``docs.md``."""

import os
import re
import tempfile
import uuid
from datetime import date
from pathlib import Path
from typing import Optional, Tuple

from . import frontmatter
from .parser import split_title_link


DOCUMENT_ITEM_RE = re.compile(r"^\s*-\s*(\S.*?)\s*$")


class DocumentError(Exception):
    """A user-correctable Document Markdown operation error."""


def _atomic_write(path: Path, content: str) -> None:
    """Write a file through a same-directory replacement."""

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


def _render(lines):
    """Render index lines with one terminal newline."""

    return "\n".join(lines).rstrip("\n") + "\n"


def _read_index(path: Path):
    """Read a document index or raise a concise user-facing error."""

    try:
        return path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as error:
        raise DocumentError("docs.md was not found: {}".format(path)) from error


def _safe_link(repo_root: Path, link: str) -> Path:
    """Resolve a document link without allowing it to escape the repository."""

    candidate = (repo_root / link).resolve()
    root = repo_root.resolve()
    if candidate != root and root not in candidate.parents:
        raise DocumentError("document link escapes the GTD repository: {}".format(link))
    return candidate


def _template(title: str, document_id: str) -> str:
    """Return the compact Document Markdown authoring template."""

    today = date.today().isoformat()
    lines = [
        "---",
        "gtd_id: {}".format(frontmatter.quote(document_id)),
        "kind: 'document'",
        "title: {}".format(frontmatter.quote(title)),
        "created_at: {}".format(frontmatter.quote(today)),
        "updated_at: {}".format(frontmatter.quote(today)),
        "tags: []",
        "---",
        "",
        "# {}".format(title),
        "",
        "",
        "",
        "# Implementation Note",
        "",
        "",
        "",
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


def _document_item(lines, line_number: int) -> Optional[Tuple[int, str, Optional[str]]]:
    """Return the title and optional link for a document-index list item."""

    if line_number < 1 or line_number > len(lines):
        raise DocumentError("line number is outside docs.md")
    match = DOCUMENT_ITEM_RE.match(lines[line_number - 1])
    if not match:
        return None
    title, link = split_title_link(match.group(1))
    if not title:
        raise DocumentError("document title cannot be empty")
    return line_number - 1, title, link


def create_document(
    repo_root: Path, line_number: int, docs_path: Optional[Path] = None
) -> Path:
    """Create or return the Document Markdown linked from a ``docs.md`` line."""

    repo_root = Path(repo_root).resolve()
    docs_path = (docs_path or repo_root / "docs.md").resolve()
    lines = _read_index(docs_path)
    item = _document_item(lines, line_number)
    if item is None:
        raise DocumentError("place the cursor on a document list item")
    index, title, link = item
    if link:
        path = _safe_link(repo_root, link)
        if not path.is_file():
            raise DocumentError("linked document file is missing: {}".format(link))
        return path

    document_id = str(uuid.uuid4())
    link = "documents/{}.md".format(document_id)
    path = _safe_link(repo_root, link)
    lines[index] = "- {} <{}>".format(title, link)
    _atomic_write(path, _template(title, document_id))
    _atomic_write(docs_path, _render(lines))
    return path

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


def _is_true(value: Optional[str]) -> bool:
    """Interpret the boolean spellings accepted by front matter and config."""

    return str(value).lower() in ("1", "true", "yes", "on")


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
    space_id = os.environ.get("CONFLUENCE_SPACE_ID", "")
    space_key = os.environ.get("CONFLUENCE_SPACE_KEY", "")
    parent_id = os.environ.get("CONFLUENCE_PARENT_ID", "")
    lines = [
        "---",
        "gtd_id: {}".format(frontmatter.quote(document_id)),
        "kind: 'document'",
        "title: {}".format(frontmatter.quote(title)),
        "created_at: {}".format(frontmatter.quote(today)),
        "updated_at: {}".format(frontmatter.quote(today)),
        "tags: []",
        "references: []",
        "allow_subdocuments: false",
        "publish_confluence: false",
        "parent_document_id: null",
        "parent_gtd_id: null",
        "parent_path: null",
        "confluence_space_id: {}".format(frontmatter.quote(space_id) if space_id else "null"),
        "confluence_space_key: {}".format(frontmatter.quote(space_key) if space_key else "null"),
        "confluence_parent_id: {}".format(frontmatter.quote(parent_id) if parent_id else "null"),
        "confluence_parent_path: null",
        "confluence_page_id: null",
        "confluence_url: null",
        "confluence_version: 0",
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


def _level_one_section_bounds(lines, heading: str) -> Optional[Tuple[int, int]]:
    """Return the content bounds for a level-one document section."""

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


def _level_one_section(lines, heading: str) -> Optional[Tuple[int, int]]:
    """Return the line bounds of a level-one section."""

    start = next(
        (index for index, line in enumerate(lines) if line.strip() == "# " + heading),
        None,
    )
    if start is None:
        return None
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("# ")),
        len(lines),
    )
    return start, end


def _ensure_subdocuments_section(lines):
    """Materialize the opt-in child section before Implementation Note."""

    existing = _level_one_section(lines, "Subdocuments")
    if existing is not None:
        return existing, False
    implementation = _level_one_section(lines, "Implementation Note")
    insertion = implementation[0] if implementation is not None else len(lines)
    section = ["# Subdocuments", "", "", ""]
    lines[insertion:insertion] = section
    return (insertion, insertion + len(section)), True


def _document_child_item(lines, line_number: int) -> Tuple[int, str, Optional[str]]:
    """Read a child bullet and require it to be inside Subdocuments."""

    bounds = _level_one_section_bounds(lines, "Subdocuments")
    if bounds is None:
        raise DocumentError("parent document is missing the # Subdocuments section")
    if line_number < 1 or line_number > len(lines):
        raise DocumentError("line number is outside the parent document")
    index = line_number - 1
    if index < bounds[0] or index >= bounds[1]:
        raise DocumentError("place the cursor on a bullet under # Subdocuments")
    item = _document_item(lines, line_number)
    if item is None:
        raise DocumentError("place the cursor on a bullet under # Subdocuments")
    return item


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


def create_subdocument(repo_root: Path, parent_path: str, line_number: int) -> Path:
    """Create a recursively nested document from a parent document bullet."""

    repo_root = Path(repo_root).resolve()
    parent = _safe_link(repo_root, parent_path)
    if not parent.is_file():
        raise DocumentError("parent document is missing: {}".format(parent_path))
    relative_parent = parent.relative_to(repo_root)
    if not relative_parent.parts or relative_parent.parts[0] != "documents":
        raise DocumentError("parent document must be under documents: {}".format(parent_path))

    lines = _read_index(parent)
    bounds, inserted = _ensure_subdocuments_section(lines)
    if inserted:
        frontmatter.set_value(lines, "allow_subdocuments", "true")
        _atomic_write(parent, _render(lines))
        raise DocumentError(
            "Subdocuments section was added; place the cursor on a child bullet"
        )

    start, end = bounds[0] + 1, bounds[1]
    if line_number < 1 or line_number > len(lines):
        raise DocumentError("line number is outside the parent document")
    line_index = line_number - 1
    if line_index < start or line_index >= end:
        raise DocumentError("place the cursor on a bullet under # Subdocuments")
    item = _document_item(lines, line_number)
    if item is None:
        raise DocumentError("place the cursor on a bullet under # Subdocuments")
    _, title, existing_link = item
    if existing_link:
        path = _safe_link(repo_root, existing_link)
        if not path.is_file():
            raise DocumentError("linked subdocument is missing: {}".format(existing_link))
        return path

    parent_id = frontmatter.value(lines, "gtd_id")
    if parent_id is None:
        raise DocumentError("parent document is missing gtd_id: {}".format(parent_path))
    document_id = str(uuid.uuid4())
    link = str((parent.with_suffix("") / (document_id + ".md")).relative_to(repo_root)).replace(
        "\\", "/"
    )
    child_lines = [
        "---",
        "gtd_id: {}".format(frontmatter.quote(document_id)),
        "kind: 'document'",
        "title: {}".format(frontmatter.quote(title)),
        "created_at: {}".format(frontmatter.quote(date.today().isoformat())),
        "updated_at: {}".format(frontmatter.quote(date.today().isoformat())),
        "tags: []",
        "references: []",
        "allow_subdocuments: true",
        "publish_confluence: {}".format(
            "true" if _is_true(frontmatter.value(lines, "publish_confluence")) else "false"
        ),
        "parent_document_id: {}".format(frontmatter.quote(parent_id)),
        "parent_gtd_id: {}".format(frontmatter.quote(parent_id)),
        "parent_path: {}".format(frontmatter.quote(relative_parent.as_posix())),
        "confluence_space_id: {}".format(
            frontmatter.quote(frontmatter.value(lines, "confluence_space_id"))
            if frontmatter.value(lines, "confluence_space_id")
            else "null"
        ),
        "confluence_space_key: {}".format(
            frontmatter.quote(frontmatter.value(lines, "confluence_space_key"))
            if frontmatter.value(lines, "confluence_space_key")
            else "null"
        ),
        "confluence_parent_id: {}".format(
            frontmatter.quote(frontmatter.value(lines, "confluence_page_id"))
            if frontmatter.value(lines, "confluence_page_id")
            else "null"
        ),
        "confluence_parent_path: {}".format(frontmatter.quote(relative_parent.as_posix())),
        "confluence_page_id: null",
        "confluence_url: null",
        "confluence_version: 0",
        "---",
        "",
        "# {}".format(title),
        "",
        "",
        "",
        "# Subdocuments",
        "",
        "",
        "",
        "# Implementation Note",
        "",
        "",
        "",
    ]
    new_lines = list(lines)
    new_lines[line_number - 1] = "- {} <{}>".format(title, link)
    path = _safe_link(repo_root, link)
    _atomic_write(path, _render(child_lines))
    _atomic_write(parent, _render(new_lines))
    return path

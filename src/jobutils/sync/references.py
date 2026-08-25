"""Resolve local Markdown references to published external URLs."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from jobutils.markdown.normalize import public_markdown_links


def externalize_structured_references(
    repo_root: Path, references: List[str]
) -> List[Tuple[str, str]]:
    """Resolve structured local references to published external URLs."""

    published = published_reference_map(repo_root)
    result: List[Tuple[str, str]] = []
    for reference in references:
        normalized = str(reference).replace("\\", "/")
        url = published.get(normalized)
        if url:
            result.append((Path(normalized).stem, url))
    return result


def append_reference_section(body: str, references: List[Tuple[str, str]]) -> str:
    """Append a public References section without exposing local paths."""

    if not references:
        return body
    lines = [body.rstrip("\n"), "", "# References", ""]
    lines.extend("- [{}]({})".format(label, url) for label, url in references)
    return "\n".join(lines) + "\n"


def published_reference_map(repo_root: Path) -> Dict[str, str]:
    """Index published Markdown files by their repository-relative paths."""

    result: Dict[str, str] = {}
    for path in Path(repo_root).rglob("*.md"):
        if ".jobutils" in path.parts:
            continue
        text = path.read_text(encoding="utf-8").splitlines()
        from jobutils.gtd import frontmatter

        url = frontmatter.value(text, "confluence_url") or frontmatter.value(
            text, "jira_url"
        )
        if url:
            result[str(path.relative_to(repo_root)).replace("\\", "/")] = url
    return result


def externalize_references(
    repo_root: Path, body: str, source_path: Optional[Path] = None
) -> str:
    """Replace resolvable local links without exposing private paths."""

    published = published_reference_map(repo_root)
    if source_path is None:
        return public_markdown_links(body, published)
    import os

    source_dir = Path(source_path).parent.resolve()
    root = Path(repo_root).resolve()
    relative_targets = {}
    for key, value in published.items():
        absolute = root / key
        target = os.path.relpath(str(absolute), str(source_dir)).replace("\\", "/")
        relative_targets[target] = value
        relative_targets[key] = value
    return public_markdown_links(body, relative_targets)

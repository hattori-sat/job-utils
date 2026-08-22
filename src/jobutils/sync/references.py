from pathlib import Path
from typing import Dict

from jobutils.markdown.normalize import public_markdown_links


def published_reference_map(repo_root: Path) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for path in Path(repo_root).rglob("*.md"):
        if ".jobutils" in path.parts:
            continue
        text = path.read_text(encoding="utf-8").splitlines()
        from jobutils.gtd import frontmatter
        url = frontmatter.value(text, "confluence_url") or frontmatter.value(text, "jira_url")
        if url:
            result[str(path.relative_to(repo_root)).replace("\\", "/")] = url
    return result


def externalize_references(repo_root: Path, body: str) -> str:
    return public_markdown_links(body, published_reference_map(repo_root))

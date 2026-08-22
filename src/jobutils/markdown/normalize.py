import html
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from jobutils.gtd import frontmatter


@dataclass
class MarkdownDocument:
    path: str
    metadata: Dict[str, Optional[str]]
    body: str
    public_body: str
    implementation_note: str


def split_implementation_note(body: str) -> Tuple[str, str]:
    match = re.search(r"(?m)^#\s+Implementation Note\s*$", body)
    if not match:
        return body.rstrip() + "\n", ""
    public = body[: match.start()].rstrip() + "\n"
    private = body[match.end() :].lstrip("\n").rstrip() + "\n"
    return public, private


def canonical_body(body: str) -> str:
    lines = [line.rstrip() for line in body.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines) + "\n"


def parse_document(path: str) -> MarkdownDocument:
    from pathlib import Path

    file_path = Path(path)
    lines = file_path.read_text(encoding="utf-8").splitlines()
    location = frontmatter.bounds(lines)
    if location is None:
        raise ValueError("Markdown document requires YAML front matter: {}".format(path))
    body = canonical_body("\n".join(lines[location[1] + 1 :]))
    public_body, implementation_note = split_implementation_note(body)
    metadata = {
        key: frontmatter.value(lines, key)
        for key in (
            "gtd_id", "kind", "title", "prefix", "status", "publish_jira",
            "publish_confluence", "jira_key", "jira_url", "confluence_page_id",
            "confluence_url", "confluence_parent_id", "jira_project",
            "jira_issue_type", "jira_parent_key", "confluence_space_id",
            "confluence_space_key", "confluence_version", "sync_hash",
        )
    }
    return MarkdownDocument(str(path), metadata, body, public_body, implementation_note)


def public_markdown_links(body: str, published: Dict[str, str]) -> str:
    """Replace local Markdown links with published URLs when available."""

    pattern = re.compile(r"(!?\[[^\]]*\])\(([^)]+)\)")

    def replace(match: re.Match) -> str:
        target = match.group(2)
        external = published.get(target)
        if external:
            return "{}({})".format(match.group(1), external)
        if match.group(1).startswith("!"):
            return match.group(1)
        return match.group(1)

    return pattern.sub(replace, body)


def markdown_to_storage(body: str) -> str:
    """Render common Markdown to Confluence storage content.

    The authoring model remains Markdown. This small renderer produces storage
    content for the API and leaves complex Confluence macros to explicit
    `:::confluence-macro` directives.
    """

    output: List[str] = []
    paragraph: List[str] = []
    in_code = False
    code_lines: List[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            output.append("<p>{}</p>".format(html.escape(" ".join(paragraph))))
            paragraph[:] = []

    for line in body.splitlines():
        if line.startswith("```"):
            flush_paragraph()
            if in_code:
                output.append("<pre><code>{}</code></pre>".format(html.escape("\n".join(code_lines))))
                code_lines[:] = []
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue
        directive = re.match(r"^:::confluence-macro\s+name=\"([^\"]+)\"\s*$", line)
        if directive:
            flush_paragraph()
            output.append('<ac:structured-macro ac:name="{}"><ac:rich-text-body>'.format(html.escape(directive.group(1))))
            continue
        if line.strip() == ":::" and output and output[-1].endswith("</ac:rich-text-body>") is False:
            flush_paragraph()
            output.append("</ac:rich-text-body></ac:structured-macro>")
            continue
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            output.append("<h{0}>{1}</h{0}>".format(level, html.escape(heading.group(2))))
            continue
        bullet = re.match(r"^\s*[-*]\s+(.+)$", line)
        if bullet:
            flush_paragraph()
            output.append("<ul><li>{}</li></ul>".format(html.escape(bullet.group(1))))
            continue
        if line.strip():
            paragraph.append(line.strip())
        else:
            flush_paragraph()
    flush_paragraph()
    if in_code:
        output.append("<pre><code>{}</code></pre>".format(html.escape("\n".join(code_lines))))
    return "\n".join(output)

"""Normalize Markdown and translate public bodies for external systems."""

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

from jobutils.gtd import frontmatter


@dataclass
class MarkdownDocument:
    """Parsed Markdown with public and local-only body partitions."""

    path: str
    metadata: Dict[str, Optional[str]]
    body: str
    public_body: str
    implementation_note: str

    def section(self, heading: str) -> str:
        """Return the content under a level-one heading."""

        pattern = re.compile(r"(?m)^#\s+{}\s*$".format(re.escape(heading)))
        match = pattern.search(self.public_body)
        if not match:
            return ""
        next_heading = re.search(r"(?m)^#\s+.+?\s*$", self.public_body[match.end() :])
        end = (
            match.end() + next_heading.start()
            if next_heading
            else len(self.public_body)
        )
        return self.public_body[match.end() : end].strip()


def split_implementation_note(body: str) -> Tuple[str, str]:
    """Separate the final local-only Implementation Note section."""

    match = re.search(r"(?m)^#\s+Implementation Note\s*$", body)
    if not match:
        return body.rstrip() + "\n", ""
    public = body[: match.start()].rstrip() + "\n"
    private = body[match.end() :].lstrip("\n").rstrip() + "\n"
    return public, private


def canonical_body(body: str) -> str:
    """Normalize line endings, trailing whitespace, and final newlines."""

    lines = [line.rstrip() for line in body.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines) + "\n"


def parse_document(path: str) -> MarkdownDocument:
    """Parse a managed Markdown file and expose its public body."""

    from pathlib import Path

    file_path = Path(path)
    lines = file_path.read_text(encoding="utf-8").splitlines()
    location = frontmatter.bounds(lines)
    if location is None:
        raise ValueError(
            "Markdown document requires YAML front matter: {}".format(path)
        )
    body = canonical_body("\n".join(lines[location[1] + 1 :]))
    public_body, implementation_note = split_implementation_note(body)
    metadata = {
        key: frontmatter.value(lines, key)
        for key in (
            "gtd_id",
            "kind",
            "title",
            "prefix",
            "status",
            "publish_jira",
            "publish_confluence",
            "parent_document_id",
            "jira_key",
            "jira_url",
            "confluence_page_id",
            "confluence_url",
            "confluence_parent_id",
            "confluence_parent_path",
            "jira_project",
            "jira_issue_type",
            "jira_parent_key",
            "confluence_space_id",
            "confluence_space_key",
            "confluence_version",
            "jira_progress_comment_field",
            "sync_hash",
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


_INLINE_LINK = re.compile(
    r"(!?)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)"
)
_MACRO = re.compile(
    r"^:::confluence-macro\s+name=(?:\"([^\"]+)\"|'([^']+)'|(\S+))\s*$"
)
_BULLET = re.compile(r"^\s*[-*+]\s+(.+)$")
_ORDERED = re.compile(r"^\s*\d+[.)]\s+(.+)$")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _table_cells(line: str) -> List[str]:
    """Split a simple pipe table row into trimmed cells."""

    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|") and not value.endswith("\\|"):
        value = value[:-1]
    return [cell.strip().replace("\\|", "|") for cell in value.split("|")]


def _is_table_separator(line: str) -> bool:
    """Return whether a line is a Markdown table separator row."""

    cells = _table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _is_table_start(lines: List[str], index: int) -> bool:
    """Return whether two adjacent lines begin a supported table."""

    return (
        index + 1 < len(lines)
        and "|" in lines[index]
        and _is_table_separator(lines[index + 1])
    )


def _block_start(lines: List[str], index: int) -> bool:
    """Return whether a line starts a block that ends the current paragraph."""

    line = lines[index]
    return bool(
        line.startswith("```")
        or _MACRO.match(line)
        or _HEADING.match(line)
        or _BULLET.match(line)
        or _ORDERED.match(line)
        or _is_table_start(lines, index)
    )


def _markdown_blocks(body: str) -> List[Tuple[str, object]]:
    """Parse the supported Markdown subset into deterministic block tuples."""

    lines = body.replace("\r\n", "\n").split("\n")
    blocks: List[Tuple[str, object]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("```"):
            language = line[3:].strip()
            index += 1
            code: List[str] = []
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            blocks.append(("code", (language, "\n".join(code))))
            continue
        macro = _MACRO.match(line)
        if macro:
            name = next(value for value in macro.groups() if value is not None)
            index += 1
            macro_body: List[str] = []
            while index < len(lines) and lines[index].strip() != ":::":
                macro_body.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            blocks.append(("macro", (name, "\n".join(macro_body))))
            continue
        heading = _HEADING.match(line)
        if heading:
            blocks.append(("heading", (len(heading.group(1)), heading.group(2))))
            index += 1
            continue
        if _is_table_start(lines, index):
            headers = _table_cells(line)
            index += 2
            rows: List[List[str]] = []
            while index < len(lines) and lines[index].strip() and "|" in lines[index]:
                rows.append(_table_cells(lines[index]))
                index += 1
            blocks.append(("table", (headers, rows)))
            continue
        list_match = _BULLET.match(line) or _ORDERED.match(line)
        if list_match:
            kind = "unordered" if _BULLET.match(line) else "ordered"
            items = [list_match.group(1)]
            index += 1
            while index < len(lines):
                match = _BULLET.match(lines[index]) if kind == "unordered" else _ORDERED.match(lines[index])
                if not match:
                    break
                items.append(match.group(1))
                index += 1
            blocks.append((kind, items))
            continue
        paragraph = [line.strip()]
        index += 1
        while index < len(lines) and lines[index].strip() and not _block_start(lines, index):
            paragraph.append(lines[index].strip())
            index += 1
        blocks.append(("paragraph", " ".join(paragraph)))
    return blocks


def _render_storage_inline(text: str) -> str:
    """Escape Markdown inline text while retaining safe links and images."""

    output: List[str] = []
    last = 0
    for match in _INLINE_LINK.finditer(text):
        output.append(html.escape(text[last : match.start()]))
        image, label, target = match.group(1), match.group(2), match.group(3)
        safe_label = html.escape(label, quote=True)
        safe_target = html.escape(target, quote=True)
        if image:
            output.append(
                '<ac:image ac:alt="{0}"><ri:url ri:value="{1}" /></ac:image>'.format(
                    safe_label, safe_target
                )
            )
        else:
            output.append('<a href="{0}">{1}</a>'.format(safe_target, safe_label))
        last = match.end()
    output.append(html.escape(text[last:]))
    return "".join(output)


def _render_storage_table(headers: List[str], rows: List[List[str]]) -> str:
    """Render a Markdown table as Confluence storage table markup."""

    head = "<tr>{}</tr>".format(
        "".join("<th>{}</th>".format(_render_storage_inline(cell)) for cell in headers)
    )
    body = "".join(
        "<tr>{}</tr>".format(
            "".join("<td>{}</td>".format(_render_storage_inline(cell)) for cell in row)
        )
        for row in rows
    )
    return "<table><thead>{}</thead><tbody>{}</tbody></table>".format(head, body)


def markdown_to_storage(body: str) -> str:
    """Render the supported Markdown subset as Confluence storage markup."""

    output: List[str] = []
    for kind, value in _markdown_blocks(body):
        if kind == "heading":
            level, text = value
            output.append("<h{0}>{1}</h{0}>".format(level, _render_storage_inline(text)))
        elif kind == "paragraph":
            output.append("<p>{}</p>".format(_render_storage_inline(value)))
        elif kind in ("unordered", "ordered"):
            tag = "ul" if kind == "unordered" else "ol"
            output.append(
                "<{0}>{1}</{0}>".format(
                    tag,
                    "".join("<li>{}</li>".format(_render_storage_inline(item)) for item in value),
                )
            )
        elif kind == "table":
            output.append(_render_storage_table(value[0], value[1]))
        elif kind == "code":
            output.append("<pre><code>{}</code></pre>".format(html.escape(value[1])))
        elif kind == "macro":
            name, macro_body = value
            output.append(
                '<ac:structured-macro ac:name="{}"><ac:rich-text-body>{}</ac:rich-text-body></ac:structured-macro>'.format(
                    html.escape(name, quote=True), markdown_to_storage(macro_body)
                )
            )
    return "\n".join(output)


class _StorageNode:
    """Small parsed storage tree node used by the safe Markdown reader."""

    def __init__(self, tag: str = "", attrs: Optional[Dict[str, str]] = None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children: List[object] = []


class _StorageParser(HTMLParser):
    """Parse the supported storage subset without executing or preserving HTML."""

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.root = _StorageNode("root")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        node = _StorageNode(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in ("br", "hr", "img", "ri:url", "ri:attachment"):
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str):
        self.stack[-1].children.append(data)


def _node_text(node: _StorageNode) -> str:
    """Return decoded text content from a storage node."""

    return "".join(
        child if isinstance(child, str) else _node_text(child) for child in node.children
    )


def _find_nodes(node: _StorageNode, tag: str) -> List[_StorageNode]:
    """Return descendant nodes with a given tag."""

    result: List[_StorageNode] = []
    for child in node.children:
        if isinstance(child, _StorageNode):
            if child.tag == tag:
                result.append(child)
            result.extend(_find_nodes(child, tag))
    return result


def _storage_inline(node: object) -> str:
    """Convert inline storage nodes to Markdown inline syntax."""

    if isinstance(node, str):
        return node
    if node.tag == "br":
        return "\n"
    if node.tag == "a":
        return "[{}]({})".format(
            "".join(_storage_inline(child) for child in node.children),
            node.attrs.get("href", ""),
        )
    if node.tag == "ac:image":
        target_nodes = _find_nodes(node, "ri:url")
        target = target_nodes[0].attrs.get("ri:value", "") if target_nodes else ""
        if not target:
            attachments = _find_nodes(node, "ri:attachment")
            target = attachments[0].attrs.get("ri:filename", "") if attachments else ""
        return "![{}]({})".format(node.attrs.get("ac:alt", ""), target)
    return "".join(_storage_inline(child) for child in node.children)


def _storage_table(node: _StorageNode) -> str:
    """Convert a storage table node to a Markdown pipe table."""

    rows = _find_nodes(node, "tr")
    rendered: List[List[str]] = []
    for row in rows:
        cells = [child for child in row.children if isinstance(child, _StorageNode) and child.tag in ("th", "td")]
        rendered.append(["".join(_storage_inline(child) for child in cell.children) for cell in cells])
    if not rendered:
        return ""
    width = max(len(row) for row in rendered)
    rendered = [row + [""] * (width - len(row)) for row in rendered]
    lines = ["| " + " | ".join(rendered[0]) + " |", "| " + " | ".join("---" for _ in range(width)) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rendered[1:])
    return "\n".join(lines)


def _storage_block(node: _StorageNode) -> str:
    """Convert one supported storage block to Markdown."""

    if re.fullmatch(r"h[1-6]", node.tag):
        return "{} {}".format("#" * int(node.tag[1]), _storage_inline(node))
    if node.tag == "p":
        return "".join(_storage_inline(child) for child in node.children).strip()
    if node.tag in ("ul", "ol"):
        prefix = "-" if node.tag == "ul" else "1."
        items = []
        for child in node.children:
            if isinstance(child, _StorageNode) and child.tag == "li":
                items.append("{} {}".format(prefix, _storage_inline(child).strip()))
        if node.tag == "ol":
            items = ["{}. {}".format(index, line.split(" ", 1)[1]) for index, line in enumerate(items, 1)]
        return "\n".join(items)
    if node.tag == "table":
        return _storage_table(node)
    if node.tag == "pre":
        return "```\n{}\n```".format(_node_text(node).rstrip("\n"))
    if node.tag == "ac:structured-macro":
        name = node.attrs.get("ac:name", "unknown")
        body_nodes = _find_nodes(node, "ac:rich-text-body")
        body = _storage_blocks(body_nodes[0].children) if body_nodes else ""
        return ":::confluence-macro name={}\n{}\n:::".format(name, body.rstrip("\n"))
    if node.tag == "ac:image":
        return _storage_inline(node)
    return _storage_inline(node).strip()


def _storage_blocks(nodes: List[object]) -> str:
    """Render parsed storage block nodes with canonical spacing."""

    blocks = []
    for node in nodes:
        if isinstance(node, _StorageNode):
            rendered = _storage_block(node)
            if rendered:
                blocks.append(rendered)
    return "\n\n".join(blocks)


def storage_to_markdown(storage: str) -> str:
    """Convert the supported Confluence storage subset back to Markdown."""

    parser = _StorageParser()
    parser.feed(storage)
    parser.close()
    return canonical_body(_storage_blocks(parser.root.children))


def _adf_inline(text: str) -> List[Dict]:
    """Build ADF text and link nodes from Markdown inline syntax."""

    nodes: List[Dict] = []
    last = 0
    for match in _INLINE_LINK.finditer(text):
        if match.start() > last:
            nodes.append({"type": "text", "text": text[last : match.start()]})
        label = match.group(2)
        if match.group(1):
            nodes.append({"type": "text", "text": label})
        else:
            nodes.append(
                {
                    "type": "text",
                    "text": label,
                    "marks": [{"type": "link", "attrs": {"href": match.group(3)}}],
                }
            )
        last = match.end()
    if last < len(text) or not nodes:
        nodes.append({"type": "text", "text": text[last:]})
    return nodes


def _adf_paragraph(text: str) -> Dict:
    """Build a non-empty ADF paragraph node."""

    return {"type": "paragraph", "content": _adf_inline(text)}


def markdown_to_adf(body: str) -> Dict:
    """Convert the supported Markdown subset into Jira ADF."""

    content: List[Dict] = []
    for kind, value in _markdown_blocks(body):
        if kind == "heading":
            level, text = value
            content.append(
                {"type": "heading", "attrs": {"level": level}, "content": _adf_inline(text)}
            )
        elif kind == "paragraph":
            content.append(_adf_paragraph(value))
        elif kind in ("unordered", "ordered"):
            item_nodes = [
                {"type": "listItem", "content": [_adf_paragraph(item)]} for item in value
            ]
            block = {"type": "bulletList" if kind == "unordered" else "orderedList", "content": item_nodes}
            if kind == "ordered":
                block["attrs"] = {"order": 1}
            content.append(block)
        elif kind == "table":
            headers, rows = value
            table_rows = []
            for row_index, row in enumerate([headers] + rows):
                cell_type = "tableHeader" if row_index == 0 else "tableCell"
                table_rows.append(
                    {
                        "type": "tableRow",
                        "content": [
                            {"type": cell_type, "content": [_adf_paragraph(cell)]}
                            for cell in row
                        ],
                    }
                )
            content.append({"type": "table", "content": table_rows})
        elif kind == "code":
            language, code = value
            block = {"type": "codeBlock", "content": [{"type": "text", "text": code}]}
            if language:
                block["attrs"] = {"language": language}
            content.append(block)
        elif kind == "macro":
            name, macro_body = value
            content.append(_adf_paragraph(":::confluence-macro name={} {} :::".format(name, macro_body).strip()))
    return {"version": 1, "type": "doc", "content": content}


def _adf_inline_to_markdown(items: List[Dict]) -> str:
    """Convert ADF inline nodes to Markdown text."""

    output: List[str] = []
    for item in items or []:
        item_type = item.get("type")
        if item_type == "hardBreak":
            output.append("\n")
            continue
        if item_type == "image":
            attrs = item.get("attrs", {})
            output.append("![{}]({})".format(attrs.get("alt", ""), attrs.get("url", "")))
            continue
        text = item.get("text", "")
        marks = item.get("marks", []) or []
        link = next((mark.get("attrs", {}).get("href") for mark in marks if mark.get("type") == "link"), None)
        output.append("[{}]({})".format(text, link) if link else text)
    return "".join(output)


def _adf_list(block: Dict, ordered: bool) -> str:
    """Convert an ADF list block to Markdown list lines."""

    lines = []
    for index, item in enumerate(block.get("content", []), 1):
        text = " ".join(
            _adf_inline_to_markdown(paragraph.get("content", []))
            for paragraph in item.get("content", [])
            if paragraph.get("type") == "paragraph"
        )
        lines.append("{}. {}".format(index, text) if ordered else "- {}".format(text))
    return "\n".join(lines)


def _adf_table(block: Dict) -> str:
    """Convert an ADF table block to a Markdown pipe table."""

    rows = []
    for row in block.get("content", []):
        cells = []
        for cell in row.get("content", []):
            paragraphs = [child for child in cell.get("content", []) if child.get("type") == "paragraph"]
            cells.append(" ".join(_adf_inline_to_markdown(paragraph.get("content", [])) for paragraph in paragraphs))
        rows.append(cells)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join("---" for _ in range(width)) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows[1:])
    return "\n".join(lines)


def adf_to_markdown(document: Dict) -> str:
    """Convert supported Jira ADF blocks to canonical Markdown."""

    lines: List[str] = []
    for block in document.get("content", []):
        block_type = block.get("type")
        if block_type == "paragraph":
            lines.extend([_adf_inline_to_markdown(block.get("content", [])), ""])
        elif block_type == "heading":
            level = int(block.get("attrs", {}).get("level", 1))
            lines.extend(["{} {}".format("#" * level, _adf_inline_to_markdown(block.get("content", []))), ""])
        elif block_type == "bulletList":
            lines.extend([_adf_list(block, False), ""])
        elif block_type == "orderedList":
            lines.extend([_adf_list(block, True), ""])
        elif block_type == "table":
            lines.extend([_adf_table(block), ""])
        elif block_type == "codeBlock":
            language = block.get("attrs", {}).get("language", "")
            lines.extend(["```{}".format(language), "".join(item.get("text", "") for item in block.get("content", [])), "```", ""])
    return canonical_body("\n".join(lines))

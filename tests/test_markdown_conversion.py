import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.markdown.normalize import (
    adf_to_markdown,
    markdown_to_adf,
    markdown_to_storage,
    storage_to_markdown,
)


class MarkdownConversionTests(unittest.TestCase):
    def test_markdown_to_storage_renders_supported_blocks_and_inline_content(self):
        rendered = markdown_to_storage(
            """# Guide

See [the docs](https://example.com/docs) and ![diagram](https://example.com/a.png).

- one
- two

1. first
2. second

| Name | Value |
| --- | --- |
| A | 1 |

:::confluence-macro name=info
Useful **context**.
:::
"""
        )
        self.assertIn('<h1>Guide</h1>', rendered)
        self.assertIn('<a href="https://example.com/docs">the docs</a>', rendered)
        self.assertIn(
            '<ac:image ac:alt="diagram"><ri:url ri:value="https://example.com/a.png" /></ac:image>',
            rendered,
        )
        self.assertIn("<ul><li>one</li><li>two</li></ul>", rendered)
        self.assertIn("<ol><li>first</li><li>second</li></ol>", rendered)
        self.assertIn("<th>Name</th><th>Value</th>", rendered)
        self.assertIn('<ac:structured-macro ac:name="info">', rendered)
        self.assertIn("Useful **context**.", rendered)

    def test_storage_to_markdown_reads_supported_blocks_and_macro_body(self):
        markdown = storage_to_markdown(
            """<h1>Guide</h1>
<p>See <a href="https://example.com/docs">the docs</a>.</p>
<ul><li>one</li><li>two</li></ul>
<table><thead><tr><th>Name</th><th>Value</th></tr></thead><tbody><tr><td>A</td><td>1</td></tr></tbody></table>
<ac:image ac:alt="diagram"><ri:url ri:value="https://example.com/a.png" /></ac:image>
<ac:structured-macro ac:name="info"><ac:rich-text-body><p>Useful context.</p></ac:rich-text-body></ac:structured-macro>
"""
        )
        self.assertIn("# Guide", markdown)
        self.assertIn("[the docs](https://example.com/docs)", markdown)
        self.assertIn("- one\n- two", markdown)
        self.assertIn("| Name | Value |", markdown)
        self.assertIn("| --- | --- |", markdown)
        self.assertIn("![diagram](https://example.com/a.png)", markdown)
        self.assertIn(":::confluence-macro name=info", markdown)
        self.assertIn("Useful context.", markdown)

    def test_markdown_to_adf_uses_structured_blocks_and_links(self):
        document = markdown_to_adf(
            """# Guide

See [the docs](https://example.com/docs).

- one
- two

| Name | Value |
| --- | --- |
| A | 1 |

```python
print('ok')
```
"""
        )
        self.assertEqual(document["type"], "doc")
        self.assertEqual(document["content"][0]["type"], "heading")
        self.assertEqual(document["content"][1]["type"], "paragraph")
        self.assertEqual(
            document["content"][1]["content"][1]["marks"][0]["type"], "link"
        )
        self.assertEqual(document["content"][2]["type"], "bulletList")
        self.assertEqual(document["content"][3]["type"], "table")
        self.assertEqual(document["content"][4]["type"], "codeBlock")

    def test_adf_to_markdown_reads_lists_links_and_code(self):
        markdown = adf_to_markdown(
            {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "See "},
                            {
                                "type": "text",
                                "text": "the docs",
                                "marks": [
                                    {
                                        "type": "link",
                                        "attrs": {"href": "https://example.com/docs"},
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "type": "bulletList",
                        "content": [
                            {
                                "type": "listItem",
                                "content": [
                                    {"type": "paragraph", "content": [{"type": "text", "text": "one"}]}
                                ],
                            },
                            {
                                "type": "listItem",
                                "content": [
                                    {"type": "paragraph", "content": [{"type": "text", "text": "two"}]}
                                ],
                            },
                        ],
                    },
                    {
                        "type": "codeBlock",
                        "attrs": {"language": "python"},
                        "content": [{"type": "text", "text": "print('ok')"}],
                    },
                    {
                        "type": "table",
                        "content": [
                            {
                                "type": "tableRow",
                                "content": [
                                    {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Name"}]}]},
                                    {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Value"}]}]},
                                ],
                            },
                            {
                                "type": "tableRow",
                                "content": [
                                    {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "A"}]}]},
                                    {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "1"}]}]},
                                ],
                            },
                        ],
                    },
                ],
            }
        )
        self.assertIn("[the docs](https://example.com/docs)", markdown)
        self.assertIn("- one\n- two", markdown)
        self.assertIn("```python\nprint('ok')\n```", markdown)
        self.assertIn("| Name | Value |", markdown)
        self.assertIn("| A | 1 |", markdown)


if __name__ == "__main__":
    unittest.main()

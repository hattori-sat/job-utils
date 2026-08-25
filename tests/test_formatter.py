import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.cli import main
from jobutils.markdown.formatter import format_file, format_text


class MarkdownFormatterTests(unittest.TestCase):
    def test_format_is_idempotent_and_preserves_code(self):
        source = (
            "---\nkind: 'document'\ntitle: 'Guide'\n---\n"
            "\n# Guide\n\nBody  \n\n\n# Implementation Note\n\n"
            "```python\nvalue = '  keep  '\n```\n"
        )
        formatted = format_text(source)
        self.assertEqual(formatted, format_text(formatted))
        self.assertIn("# Guide\n\n\n\nBody\n", formatted)
        self.assertIn("value = '  keep  '", formatted)

    def test_check_does_not_write_and_file_format_is_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text("---\nkind: 'document'\n---\n\n# Guide\n\nBody\n", encoding="utf-8")
            self.assertTrue(format_file(path, check=True))
            self.assertTrue(path.read_text(encoding="utf-8").endswith("# Guide\n\nBody\n"))
            self.assertTrue(format_file(path))
            self.assertFalse(format_file(path, check=True))

    def test_cli_check_reports_a_machine_readable_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text("---\nkind: document\n---\n\n# Guide\n\nBody\n", encoding="utf-8")
            format_file(path)
            output = StringIO()
            with redirect_stdout(output):
                result = main(["markdown", "format", "--path", str(path), "--check"])
            self.assertEqual(result, 0)
            self.assertIn("ok:", output.getvalue())


if __name__ == "__main__":
    unittest.main()

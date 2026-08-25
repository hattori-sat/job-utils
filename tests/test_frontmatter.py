import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.gtd.frontmatter import list_value


class FrontMatterTests(unittest.TestCase):
    def test_reads_standard_yaml_block_lists(self):
        lines = [
            "---",
            "tags:",
            "  - delivery",
            "  - review",
            "references:",
            "  - documents/guide.md",
            "---",
        ]

        self.assertEqual(list_value(lines, "tags"), ["delivery", "review"])
        self.assertEqual(list_value(lines, "references"), ["documents/guide.md"])


if __name__ == "__main__":
    unittest.main()

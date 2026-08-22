import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.gtd.model import SECTION_TO_PREFIX
from jobutils.gtd.parser import scan_items, split_title_link


class GtdParserTests(unittest.TestCase):
    def test_split_title_and_link(self):
        self.assertEqual(split_title_link("A task <gtd_tasks/a.md>"), ("A task", "gtd_tasks/a.md"))
        self.assertEqual(split_title_link("A task"), ("A task", None))

    def test_unprefixed_item_uses_section_prefix(self):
        items, _ = scan_items(["## Next Actions", "", "- Fix the build"])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].prefix, "next")
        self.assertFalse(items[0].explicitly_prefixed)

    def test_unknown_prefix_is_not_reclassified(self):
        items, prefixed = scan_items(["## Today", "", "- custom: Keep this"])
        self.assertEqual(items, [])
        self.assertEqual(prefixed, [(2, "custom")])

    def test_focus_section_is_known(self):
        self.assertEqual(SECTION_TO_PREFIX["Focus"], "focus")


if __name__ == "__main__":
    unittest.main()

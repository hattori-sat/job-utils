import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from jobutils.sync.merge import three_way_merge


class MergeTests(unittest.TestCase):
    def test_one_sided_change_is_accepted(self):
        merged, conflict = three_way_merge("base\n", "local\n", "base\n")
        self.assertFalse(conflict)
        self.assertEqual(merged, "local\n")

    def test_both_sides_are_visible_as_conflict_markers(self):
        merged, conflict = three_way_merge("base\n", "local\n", "remote\n")
        self.assertTrue(conflict)
        self.assertIn("<<<<<<< local", merged)
        self.assertIn(">>>>>>> external", merged)


if __name__ == "__main__":
    unittest.main()

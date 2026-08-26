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

    def test_non_overlapping_changes_are_merged(self):
        base = "first\nsecond\nthird\n"
        local = "local first\nsecond\nthird\n"
        remote = "first\nsecond\nremote third\n"

        merged, conflict = three_way_merge(base, local, remote)

        self.assertFalse(conflict)
        self.assertEqual(merged, "local first\nsecond\nremote third\n")

    def test_independent_appends_are_merged(self):
        base = "first\n"
        local = "first\nlocal addition\n"
        remote = "first\nexternal addition\n"

        merged, conflict = three_way_merge(base, local, remote)

        self.assertFalse(conflict)
        self.assertEqual(merged, "first\nlocal addition\nexternal addition\n")

    def test_identical_changes_to_the_same_range_are_merged_once(self):
        base = "first\nsecond\n"
        local = "first\nupdated\n"
        remote = "first\nupdated\n"

        merged, conflict = three_way_merge(base, local, remote)

        self.assertFalse(conflict)
        self.assertEqual(merged, "first\nupdated\n")

    def test_both_sides_are_visible_as_conflict_markers(self):
        merged, conflict = three_way_merge("base\n", "local\n", "remote\n")
        self.assertTrue(conflict)
        self.assertIn("<<<<<<< local", merged)
        self.assertIn(">>>>>>> external", merged)


if __name__ == "__main__":
    unittest.main()

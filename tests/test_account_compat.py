import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import unittest
from account_compat import merge_account


class AccountCompatTest(unittest.TestCase):
    def test_unchanged_retains_original_order_null_and_types(self):
        source = [[2, [8, 1.0, None]], None, [1, [3, 10]]]
        baseline = [[1, [3, 10]], [2, [8, 1, 999]]]
        merged = merge_account(source, baseline, baseline)
        self.assertEqual(source, merged)
        self.assertIsInstance(merged[0][1][1], float)

    def test_progress_new_rows_and_deletions(self):
        source = [[2, [8, 1.0, None]], [1, [3, 10]]]
        baseline = [[1, [3, 10]], [2, [8, 1, 999]]]
        current = [[2, [8, 2, 999]], [3, [4, 30]]]
        self.assertEqual(merge_account(source, baseline, current),
                         [[2, [8, 2.0, None]], [3, [4, 30]]])

    def test_duplicate_ids_remain_distinct(self):
        source = [[1, [7, 10]], [1, [7, 20]]]
        self.assertEqual(merge_account(source, source, [[1, [7, 11]], [1, [7, 20]]]),
                         [[1, [7, 11]], [1, [7, 20]]])


if __name__ == '__main__':
    unittest.main()

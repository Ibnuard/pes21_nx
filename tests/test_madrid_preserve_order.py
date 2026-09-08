"""Regression guard for the user-confirmed Madrid integration contract."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_madrid_preserve_order import restore_order
from build_inter_miami_release_experiment import cpk_index


class PreserveOrderTests(unittest.TestCase):
    def test_original_order_ids_and_offsets_are_not_sorted_away(self):
        source = ROOT / 'local-debug/native-license-v7-madrid-preserve-order/base-dt200.cpk'
        if not source.is_file():
            self.skipTest('local PES21 fixture not available')
        header, rows, _ = cpk_index(source)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'candidate.cpk'
            report = restore_order(source, output, list(rows))
            actual_header, actual_rows, _ = cpk_index(output)
            self.assertEqual(actual_header, dict(header, Sorted=0))
            self.assertEqual(list(actual_rows.items()), list(rows.items()))
            self.assertEqual(report['changed_members'], [])
            with self.assertRaises(FileExistsError):
                restore_order(source, output, list(rows))


if __name__ == '__main__':
    unittest.main()

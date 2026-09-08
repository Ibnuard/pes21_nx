import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from package_native_club_license import enable_real_kits
from build_barca_real_madrid_mobile_kit_canary import decode_wesys_payload


class NativeLicenseMergeTests(unittest.TestCase):
    def test_changes_only_selected_flags(self):
        rows = []
        for team in (108, 109, 18961):
            row = bytearray(b'X' * 1532)
            struct.pack_into('<I', row, 8, team)
            row[84] = 4
            rows.append(row)
        raw = b''.join(rows)
        encoded, report = enable_real_kits(raw, {108, 109})
        result, _ = decode_wesys_payload(encoded, 'test')
        changed = [i for i, (a, b) in enumerate(zip(raw, result)) if a != b]
        self.assertEqual(changed, [84, 1532 + 84])
        self.assertEqual(len(report), 2)

    def test_missing_team_rejected(self):
        with self.assertRaises(ValueError):
            enable_real_kits(bytes(1532), {109})


if __name__ == '__main__':
    unittest.main()

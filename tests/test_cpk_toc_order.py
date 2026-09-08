import sys
import unittest
from bisect import bisect_left
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from repair_cpk_toc_order import sorted_rows
from add_cpk_members_canary import build_toc_packet, packet_payload, parse_toc_rows
from prepare_runtime import read_cpk_packet


class TocOrderTests(unittest.TestCase):
    def test_appended_madrid_breaks_existing_binary_lookup(self):
        original = ['common/etc/uniform/team/108/a.bin',
                    'common/etc/uniform/team/referee/a.bin',
                    'common/etc/uniform/team/RefereeColor.bin',
                    'common/etc/uniform/team/UniColor.bin']
        appended = original + ['common/etc/uniform/team/109/a.bin']
        target = original[-1].lower()
        keys = [x.lower() for x in appended]
        self.assertEqual(bisect_left(keys, target), len(keys))
        rows = [dict(DirName=x.rsplit('/', 1)[0], FileName=x.rsplit('/', 1)[1], ID=i)
                for i, x in enumerate(appended)]
        ordered = sorted_rows(rows)
        repaired = [(r['DirName']+'/'+r['FileName']).lower() for r in ordered]
        self.assertEqual(repaired[bisect_left(repaired, target)], target)
        self.assertEqual({r['ID'] for r in ordered}, set(range(5)))

    def test_real_rebuilder_keeps_additions_sorted(self):
        path = Path(__file__).resolve().parents[1]/'local-debug/native-license-kits-v2/base-dt200.cpk'
        if not path.is_file():
            self.skipTest('local CPK fixture unavailable')
        with path.open('rb') as stream:
            header = read_cpk_packet(stream, 0, b'CPK ')[0]
            _, packet, _ = packet_payload(stream, header['TocOffset'], b'TOC ')
        rows = parse_toc_rows(packet)
        addition = dict(DirName='common/etc/uniform/team/109',
                        FileName='109_DEF_1st_realUni.bin', FileSize=120,
                        ExtractSize=120, FileOffset=12000000, ID=9999)
        rebuilt = parse_toc_rows(build_toc_packet(packet, rows, [addition]))
        keys = [(r['DirName']+'/'+r['FileName']).lower() for r in rebuilt]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(len(rebuilt), len(rows)+1)
        self.assertEqual({r['ID']: r['FileOffset'] for r in rows},
                         {r['ID']: r['FileOffset'] for r in rebuilt if r['ID'] != 9999})


if __name__ == '__main__':
    unittest.main()

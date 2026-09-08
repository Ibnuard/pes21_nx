import sys
import unittest
import json
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from build_eng_spa_mobile_kits import mobile_descriptor, safe_reference
from build_barca_real_madrid_mobile_kit_canary import descriptor_texture_names
from build_barca_real_madrid_mobile_kit_canary import cpk_inventory, decode_wesys_payload
from build_pesdb_famous_teams_candidate import member_payload
from build_real_madrid_mobile_kit_canary import sha256_bytes
from PIL import Image

FIXTURE = Path(__file__).resolve().parents[1]/'local-debug/eng-spa-all-kits-v3'


class KitDescriptorTests(unittest.TestCase):
    def test_shared_fonts_get_unique_names_without_changing_parameters(self):
        pc = bytearray(range(120))
        offsets = (40, 56, 88, 104)
        for offset, name in zip(offsets, ('u0101p1', 'epl_whi_back', 'epl_nav_leg', 'epl_whi_name')):
            pc[offset:offset+16] = name.encode().ljust(16, b'\0')
        result = mobile_descriptor(bytes(pc), 'u0101p1')
        self.assertEqual(descriptor_texture_names(result),
                         ['u0101p1', 'u0101p1_back', 'u0101p1_leg', 'u0101p1_name'])
        allowed = {i for o in offsets for i in range(o, o+16)}
        self.assertTrue(all(a == b or i in allowed for i, (a,b) in enumerate(zip(pc, result))))
        self.assertEqual(len(result), 120)

    def test_reject_wrong_descriptor_length(self):
        with self.assertRaises(ValueError):
            mobile_descriptor(bytes(96), 'u0101p1')

    def test_reject_reference_overflow(self):
        with self.assertRaises(ValueError):
            mobile_descriptor(bytes(120), 'u1234567890123456')

    def test_no_path_traversal(self):
        for bad in ('', '../font', 'a/b', 'a\\b', 'x.ftex'):
            with self.assertRaises(ValueError):
                safe_reference(bad)
        self.assertEqual(safe_reference('epl_whi_back'), 'epl_whi_back')


@unittest.skipUnless((FIXTURE/'validation-report.json').is_file(), 'local proprietary candidate not available')
class PackagedLeagueKitsTests(unittest.TestCase):
    def test_original_order_and_ids(self):
        for label in ('dt120', 'dt200', 'dt240'):
            before = cpk_inventory(FIXTURE/f'base-{label}.cpk')
            after = cpk_inventory(FIXTURE/f'{label}-original-order.cpk')
            self.assertEqual(list(after)[:len(before)], list(before))
            for name, row in before.items():
                self.assertEqual(after[name]['ID'], row['ID'], name)

    def test_stable_barca_madrid_assets_unchanged(self):
        for label in ('dt120', 'dt200'):
            base = FIXTURE/f'base-{label}.cpk'
            candidate = FIXTURE/f'{label}-original-order.cpk'
            names = [n for n in cpk_inventory(base)
                     if any(x in n for x in ('u0108', 'u0109', '/team/108/', '/team/109/'))]
            self.assertGreater(len(names), 0)
            for name in names:
                self.assertEqual(member_payload(base, name), member_payload(candidate, name), name)

    def test_all_converted_active_kit_textures_present(self):
        report = json.loads((FIXTURE/'asset-report.json').read_text())
        converted = [t for t in report['teams'] if t['status'] == 'converted']
        self.assertEqual(len(converted), 37)
        self.assertEqual(report['pending_native_slots'], [396])
        for team in converted:
            self.assertEqual(len(team['kits']), 3)
            for kit in team['kits']:
                for role, output in kit['outputs'].items():
                    payload = member_payload(FIXTURE/'dt120-original-order.cpk', output['member'])
                    self.assertEqual(sha256_bytes(payload), output['sha256'])
                    with Image.open(io.BytesIO(payload)) as image:
                        self.assertEqual(image.size, (256,384) if role == 'body' else (320,40))
                        self.assertEqual(image.mode, 'P' if role == 'body' else 'RGBA')

    def test_team_data_only_changes_kit_flags(self):
        name = 'common/etc/pesdb/Team.bin'
        before = decode_wesys_payload(member_payload(FIXTURE/'base-dt200.cpk', name), name)[0]
        after = decode_wesys_payload(member_payload(FIXTURE/'dt200-original-order.cpk', name), name)[0]
        self.assertEqual(len(before), len(after))
        self.assertTrue(all(a == b or i % 1532 == 84 for i,(a,b) in enumerate(zip(before,after))))


if __name__ == '__main__':
    unittest.main()

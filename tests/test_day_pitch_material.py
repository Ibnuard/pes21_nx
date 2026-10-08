import struct
import sys
from pathlib import Path
import unittest
from tools.tune_day_pitch_material import patch_color

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_pitch_shadow_control import green_shadow, OLD_SHADOW

class DayMaterialTests(unittest.TestCase):
    def test_only_color_bytes_change(self):
        old = (.03125,.023696,0,1)
        new = (.015,.025,.007,1)
        data = b'header'+struct.pack('<4f',*old)+b'tail'
        result, offset = patch_color(data,old,new)
        self.assertEqual(offset,6)
        self.assertEqual(result,b'header'+struct.pack('<4f',*new)+b'tail')
        self.assertEqual(len(data),len(result))
    def test_refuse_missing_or_ambiguous(self):
        old = (.03125,.023696,0,1)
        for data in (b'',struct.pack('<4f',*old)*2):
            with self.assertRaises(ValueError):
                patch_color(data,old,old)

    def test_historical_green_control_is_exactly_reversible(self):
        original = b'native-prefix' + struct.pack('<4f', *OLD_SHADOW) + b'native-suffix'
        green, offset = patch_color(original, OLD_SHADOW, green_shadow())
        restored, restored_offset = patch_color(green, green_shadow(), OLD_SHADOW)
        self.assertEqual(offset, restored_offset)
        self.assertEqual(original, restored)

    def test_owned_control_keeps_every_other_patch_member(self):
        root = Path(__file__).resolve().parents[1] / 'local-debug/night-tint-control'
        if not (root / 'original').is_dir() or not (root / 'verify').is_dir():
            self.skipTest('optional owned PAK control fixtures unavailable')
        original = {p.relative_to(root / 'original'): p.read_bytes()
                    for p in (root / 'original').rglob('*') if p.is_file()}
        restored = {p.relative_to(root / 'verify'): p.read_bytes()
                    for p in (root / 'verify').rglob('*') if p.is_file()}
        self.assertEqual(len(original), 31)
        self.assertEqual(original.keys(), restored.keys())
        changed = {p.name for p in original if original[p] != restored[p]}
        self.assertEqual(changed, {'MI_Pitch_L.uexp', 'MI_Pitch_R.uexp'})
        for p in original:
            if p.name in changed:
                expected, _ = patch_color(original[p], green_shadow(), OLD_SHADOW)
                self.assertEqual(expected, restored[p])

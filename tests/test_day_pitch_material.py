import struct
import unittest
from tools.tune_day_pitch_material import patch_color

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

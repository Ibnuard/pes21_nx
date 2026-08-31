"""Synthetic binary layout tests. No game assets in the test fixtures."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from afp_score_layout import placements, swap_fields
from afp_texture_patch import lzss_decode,lzss_encode
from scoreboard_geometry import BOXES, LOGO_ICON, SCORE_DIVIDER, timeline_targets, validate_geometry


class ScoreLayoutTests(unittest.TestCase):
    def test_balanced_context_geometry(self):
        rects=validate_geometry()
        self.assertEqual(rects['home_team'],[0,0,78,48])
        self.assertEqual(rects['away_team'],[154,0,232,48])
        self.assertEqual(rects['pes_logo'],[336,0,384,48])
        self.assertEqual(LOGO_ICON,(348,12,372,36))
        targets=timeline_targets()
        self.assertEqual(targets[61],(160,10.65))
        self.assertEqual(targets[63],(6,10.65))
        self.assertEqual(targets[65],(122,8))
        self.assertEqual(targets[67],(84,8))
        self.assertEqual(SCORE_DIVIDER[0]-BOXES['home_score'][0],37)
        self.assertEqual(BOXES['away_score'][1]-SCORE_DIVIDER[1],37)
        self.assertEqual(targets[69],(244,2))
        self.assertEqual(targets[14],(236.65,8))
        self.assertEqual(targets[14],targets[33])
        self.assertEqual(targets[69][0]-6,6+BOXES['away_team'][1])
        self.assertEqual(targets[69][0]+2,6+BOXES['timer'][0])
        # Native content spans for 1-, 2-, and 3-digit minute states stay
        # inside the 96 px clock context, without shrinking its glyphs.
        for lo,hi in ((32,82.65),(24.65,89.3),(18,96)):
            self.assertGreater(targets[14][0]+lo,6+BOXES['timer'][0])
            self.assertLess(targets[14][0]+hi,6+BOXES['timer'][1])

    def test_endian_descriptor_roundtrip(self):
        data=bytes(range(64))
        # skip two bytes, swap 2 bytes twice; then 4 bytes once, 8 bytes once.
        info=struct.pack('<4H',0x2081,0x4000,0x6000,0)
        swapped=swap_fields(data,info)
        self.assertEqual(swapped[2:6],b'\x03\x02\x05\x04')
        self.assertEqual(swap_fields(swapped,info),data)
        with self.assertRaises(ValueError):
            swap_fields(b'a',struct.pack('<H',0x6000))

    def test_placement_positions_and_color_offsets(self):
        names=b'\0time_set\0'
        payload=struct.pack('<IHHHHiiI',0x242e,14,55,18,1,2000,400,0xffffff80)
        tag=struct.pack('<I',(0x7f<<22)|len(payload))+payload
        section=struct.pack('<HHIIIII',0,0,1,1,0,24,28)+struct.pack('<I',1<<20)+tag
        data=bytearray(68)
        data[:4]=b'\x0b\xb2\xd0\xc1'
        struct.pack_into('<I',data,36,68)
        start=len(data)+len(section)
        struct.pack_into('<II',data,48,start,len(names))
        data+=section+bytes((b+128+i)&255 for i,b in enumerate(names))
        struct.pack_into('<I',data,4,len(data))
        records=placements(bytes(data))
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['name'],'time_set')
        self.assertEqual(records[0]['translate'],(100,20))
        self.assertEqual(records[0]['mult8'],(0xffffff80,))
        self.assertEqual(records[0]['frame'],0)

    def test_compression_modes_are_lossless(self):
        data=(bytes(range(251))+b'ABABABAB'*30+b'\0'*200)*20
        for candidates,minimum in ((8,3),(16,6),(48,3),(128,18)):
            compressed=lzss_encode(data,candidates,minimum)
            self.assertEqual(lzss_decode(compressed,len(data)),data)


if __name__=='__main__':
    unittest.main()

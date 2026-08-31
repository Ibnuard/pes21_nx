"""Low pitch reference-binding helpers; synthetic fixtures only."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from build_low_pitch_phase_patch import name_entries, renamed_value


class LowPitchTests(unittest.TestCase):
    def test_same_length_names_keep_offsets(self):
        header=bytearray(80)
        header[:4]=b'\xc1\x83\x2a\x9e'
        struct.pack_into('<i',header,28,1)
        struct.pack_into('<ii',header,37,2,80)
        names=['pitch_l_bsm_alp','None']
        blob=bytes(header)
        for name in names:
            blob+=struct.pack('<i',len(name)+1)+name.encode()+b'\0'+bytes(4)
        entries=name_entries(blob)
        self.assertEqual([e[0] for e in entries],names)
        self.assertEqual(entries[0][1],80)
        changed=blob.replace(b'pitch_l_bsm_alp',b'pitch_n_bsm_alp')
        self.assertEqual(name_entries(changed)[0],('pitch_n_bsm_alp',*entries[0][1:]))
        with self.assertRaises(ValueError):
            name_entries(blob[:86])

    def test_renames_do_not_touch_opaque_shader_bytes(self):
        original={'NameMap':['left','Keep'], 'Imports':[{'ObjectName':'left'}],
                  'Exports':[{'Extras':'bGVmdA==','Data':[{'Value':'left'}]}]}
        result=renamed_value(original,{'left':'next'})
        self.assertEqual(result['NameMap'],['next','Keep'])
        self.assertEqual(result['Imports'][0]['ObjectName'],'next')
        self.assertEqual(result['Exports'][0]['Extras'],'bGVmdA==')
        self.assertEqual(original['NameMap'][0],'left')


if __name__=='__main__':
    unittest.main()

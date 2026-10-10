"""Cook success alone is insufficient: both runtime GL routes need materials."""
from pathlib import Path
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from pack_stadium_shell import material_shader_versions


class StadiumShellPackageTests(unittest.TestCase):
    def test_detects_es2_only_and_complete_inline_material_maps(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'M_shell.uexp'
            es2 = zlib.compress(b'LSLGSP\x00#version 100 \nvoid main() {}\x00')
            es31 = zlib.compress(b'LSLGSP\x00#version 310 es\nvoid main() {}\x00')
            unrelated = zlib.compress(b'not-shader#version 310 es\x00')
            path.write_bytes(b'header' + es2 + unrelated)
            self.assertEqual(material_shader_versions(path), {'100'})
            path.write_bytes(b'header' + es2 + es31)
            self.assertEqual(material_shader_versions(path), {'100', '310 es'})
            path.write_bytes(es31[:-8])
            self.assertEqual(material_shader_versions(path), set())

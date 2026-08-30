"""Synthetic format tests; no proprietary game assets are needed."""
from pathlib import Path
import random
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from afp_texture_patch import lzss_decode, lzss_encode
from cooked_texture import Texture


class CompressionTests(unittest.TestCase):
    def test_lzss_roundtrip(self):
        randomizer = random.Random(17)
        for size in (0, 1, 2, 3, 7, 18, 4095, 4096, 4100, 18000):
            for data in (bytes(size), randomizer.randbytes(size),
                         (b'ABCDEF' * (size // 6 + 1))[:size]):
                with self.subTest(size=size, prefix=data[:3]):
                    self.assertEqual(lzss_decode(lzss_encode(data), size), data)

    def test_truncated_streams(self):
        for data in (b'', b'\x01', b'\0', b'\0\0'):
            with self.assertRaises(ValueError):
                lzss_decode(data, 10)


class TextureTests(unittest.TestCase):
    def test_mips_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.uexp'
            fmt = b'PF_B8G8R8A8\0'
            data = b'HDR!' + struct.pack('<4I', 4, 4, 1, len(fmt)) + fmt
            data += struct.pack('<2I', 0, 3)
            originals = []
            for size in (4, 2, 1):
                pixels = bytes([size, 50, 80, 255]) * size * size
                originals.append(pixels)
                data += struct.pack('<4Iq', 1, 0x40, len(pixels), len(pixels), 0)
                data += pixels + struct.pack('<3I', size, size, 1)
            data += b'TAIL'
            path.write_bytes(data)
            texture = Texture(path)
            self.assertEqual(len(texture.mips), 3)
            self.assertEqual(texture.replace(originals)['uexp'], data)
            changed = texture.replace([bytes(len(p)) for p in originals])['uexp']
            allowed = set()
            for i, mip in enumerate(texture.mips):
                self.assertEqual(texture.decode(i).size, (mip.width, mip.height))
                allowed.update(range(mip.offset, mip.offset + mip.size))
            self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(data, changed))))
            with self.assertRaises(ValueError):
                texture.replace(originals[:1])
            with self.assertRaises(ValueError):
                texture.replace([b'wrong'] + originals[1:])

    def test_separate_bulk_offsets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bulk.uexp'
            path.with_suffix('.uasset').write_bytes(bytes(100))
            path.with_suffix('.ubulk').write_bytes(bytes(64))
            fmt = b'PF_B8G8R8A8\0'
            prefix = b'HDR!' + struct.pack('<4I', 4, 4, 1, len(fmt)) + fmt + struct.pack('<2I', 0, 1)
            for flags in (0x100, 0x10100):
                total = len(prefix) + 24 + 12 + 4
                offset = 0 if flags & 0x10000 else -(100 + total - 4)
                path.write_bytes(prefix + struct.pack('<4Iq', 1, flags, 64, 64, offset)
                                 + struct.pack('<3I', 4, 4, 1) + b'TAIL')
                texture = Texture(path)
                self.assertEqual(texture.mips[0].offset, 0)
                self.assertEqual(texture.payload(), bytes(64))


if __name__ == '__main__':
    unittest.main()

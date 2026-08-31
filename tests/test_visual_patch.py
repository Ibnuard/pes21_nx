"""Synthetic format tests; no proprietary game assets are needed."""
from pathlib import Path
import random
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from afp_texture_patch import lzss_decode, lzss_encode
from build_efootball10_visual_patch import mowing_blend, pitch_colors
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
    def test_broad_v10_is_near_v8_width_and_aligns_penalty_front(self):
        import numpy as np
        for name in ('pitch_l_bsm_alp', 'pitch_l_bsm_exLow_alp'):
            left, band = mowing_blend(name, 1024, 'clean-v10')
            _, baseline_band = mowing_blend(name, 1024, 'clean-v7')
            self.assertAlmostEqual(band, 530/3)
            self.assertAlmostEqual(band/baseline_band, 1.03515625)
            self.assertEqual(int(left[0,493,0]), 0)
            self.assertEqual(int(left[0,494,0]), 1)
            # Exactly one constant spacing from the penalty front to center.
            self.assertEqual(494+3*band, 1024)
            transitions = np.flatnonzero(np.diff(left[0,:,0]))+1
            self.assertTrue(set(np.diff(transitions)).issubset({176,177}))
            # The Low_R stock shader mirrors the complement of this L map.
            playable = left[0,254:1024,0]
            joined = np.r_[playable, 1-playable[::-1]]
            edges = np.flatnonzero(np.diff(joined))+1
            self.assertIn(770, edges)
            self.assertEqual(len(edges), 9)  # five visible broad bands/half
            self.assertTrue(set(np.diff(edges)).issubset({176,177}))
        self.assertEqual(pitch_colors('clean-v10'), pitch_colors('clean-v7'))

    def test_broad_v10_phase_and_scale_for_all_diffuse_variants(self):
        import numpy as np
        for width in (1024,512,256,128):
            left, band = mowing_blend('pitch_l_bsm_alp', width, 'clean-v10')
            right, right_band = mowing_blend('pitch_r_bsm_alp', width, 'clean-v10')
            combined, full_band = mowing_blend('pitch_lr_bsm_exLow_alp', width, 'clean-v10')
            self.assertEqual(right_band, band)
            self.assertEqual(full_band, band/2)
            self.assertEqual(int(left[0,-1,0]), 1)
            self.assertEqual(int((1-left)[0,-1,0]), 0)
            self.assertEqual(int(right[0,0,0]), 0)
            self.assertEqual(int(combined[0,width//2-1,0]), 1)
            self.assertEqual(int(combined[0,width//2,0]), 0)
            # LR is the same world pattern, at half the texel density.
            self.assertTrue(np.array_equal(left[0,::2,0], combined[0,:width//2,0]))
            self.assertTrue(np.array_equal(right[0,::2,0], combined[0,width//2:,0]))
        combined, _ = mowing_blend('pitch_lr_bsm_exLow_alp', 1024, 'clean-v10')
        self.assertNotEqual(int(combined[0,246,0]), int(combined[0,247,0]))
        self.assertNotEqual(int(combined[0,776,0]), int(combined[0,777,0]))

    def test_broad_v11_slightly_narrower_and_aligns_keeper_box(self):
        import numpy as np
        left, band = mowing_blend('pitch_l_bsm_alp', 1024, 'clean-v11')
        _, v10_band = mowing_blend('pitch_l_bsm_alp', 1024, 'clean-v10')
        self.assertAlmostEqual(band, 693/4)
        self.assertAlmostEqual(band/v10_band, 0.9806603773584906)
        self.assertEqual(int(left[0,330,0]), 1)
        self.assertEqual(int(left[0,331,0]), 0)
        self.assertEqual(331+4*band, 1024)
        transitions = np.flatnonzero(np.diff(left[0,:,0]))+1
        self.assertTrue(set(np.diff(transitions)).issubset({173,174}))
        playable = left[0,254:1024,0]
        joined = np.r_[playable, 1-playable[::-1]]
        edges = np.flatnonzero(np.diff(joined))+1
        self.assertIn(770, edges)
        self.assertTrue(set(np.diff(edges)).issubset({173,174}))
        self.assertEqual(pitch_colors('clean-v11'), pitch_colors('clean-v10'))

    def test_broad_v11_l_r_and_lr_share_world_phase(self):
        import numpy as np
        for width in (1024,512,256,128):
            left, band = mowing_blend('pitch_l_bsm_alp', width, 'clean-v11')
            right, right_band = mowing_blend('pitch_r_bsm_alp', width, 'clean-v11')
            combined, full_band = mowing_blend('pitch_lr_bsm_exLow_alp', width, 'clean-v11')
            self.assertEqual(right_band, band)
            self.assertEqual(full_band, band/2)
            self.assertEqual(int(left[0,-1,0]), 1)
            self.assertEqual(int((1-left)[0,-1,0]), 0)
            self.assertEqual(int(right[0,0,0]), 0)
            self.assertEqual(int(combined[0,width//2-1,0]), 1)
            self.assertEqual(int(combined[0,width//2,0]), 0)
            self.assertTrue(np.array_equal(left[0,::2,0], combined[0,:width//2,0]))
            self.assertTrue(np.array_equal(right[0,::2,0], combined[0,width//2:,0]))

    def test_broad_v12_is_one_small_uniform_step_below_v11(self):
        import numpy as np
        left, band = mowing_blend('pitch_l_bsm_alp', 1024, 'clean-v12')
        _, v11_band = mowing_blend('pitch_l_bsm_alp', 1024, 'clean-v11')
        self.assertEqual(band, 171)
        self.assertAlmostEqual(band/v11_band, 171/(693/4))
        transitions = np.flatnonzero(np.diff(left[0,:,0]))+1
        self.assertEqual(transitions.tolist(), [152, 323, 494, 665, 836, 1007])
        self.assertEqual(int(left[0,493,0]), 0)
        self.assertEqual(int(left[0,494,0]), 1)
        self.assertEqual(int(left[0,-1,0]), 0)
        self.assertEqual(pitch_colors('clean-v12'), pitch_colors('clean-v11'))

    def test_broad_v12_l_r_and_lr_share_world_phase(self):
        import numpy as np
        for width in (1024,512,256,128):
            left, band = mowing_blend('pitch_l_bsm_alp', width, 'clean-v12')
            right, right_band = mowing_blend('pitch_r_bsm_alp', width, 'clean-v12')
            combined, full_band = mowing_blend('pitch_lr_bsm_exLow_alp', width, 'clean-v12')
            self.assertEqual(right_band, band)
            self.assertEqual(full_band, band/2)
            self.assertEqual(int(left[0,-1,0]), 0)
            self.assertEqual(int((1-left)[0,-1,0]), 1)
            self.assertEqual(int(right[0,0,0]), 1)
            self.assertEqual(int(combined[0,width//2-1,0]), 0)
            self.assertEqual(int(combined[0,width//2,0]), 1)
            # LR uses the same world spacing independently on each half. Its
            # left half is the L phase locked to x494; its right half starts
            # at a fresh R phase at midfield.
            self.assertTrue(np.array_equal(left[0,::2,0], combined[0,:width//2,0]))
            self.assertTrue(np.array_equal(right[0,::2,0], combined[0,width//2:,0]))

    def test_broad_v13_uses_subtle_dark_light_width_ratio(self):
        import numpy as np
        left, band = mowing_blend('pitch_l_bsm_alp', 1024, 'clean-v13')
        right, _ = mowing_blend('pitch_r_bsm_alp', 1024, 'clean-v13')
        self.assertEqual(band, 171)
        self.assertEqual(np.flatnonzero(np.diff(left[0,:,0])).tolist(),
                         [151, 325, 493, 667, 835, 1009])
        self.assertEqual(np.flatnonzero(np.diff(right[0,:,0])).tolist(),
                         [151, 325, 493, 667, 835, 1009])
        self.assertEqual(int(left[0,493,0]), 0)
        self.assertEqual(int(left[0,494,0]), 1)
        self.assertEqual(int(left[0,-1,0]), 0)
        self.assertEqual(int(right[0,0,0]), 1)
        self.assertEqual(pitch_colors('clean-v13'), pitch_colors('clean-v11'))

    def test_broad_v13_lr_preserves_world_phase_at_half_density(self):
        import numpy as np
        for width in (1024, 512, 256, 128):
            left, band = mowing_blend('pitch_l_bsm_alp', width, 'clean-v13')
            right, right_band = mowing_blend('pitch_r_bsm_alp', width, 'clean-v13')
            combined, full_band = mowing_blend('pitch_lr_bsm_exLow_alp', width, 'clean-v13')
            self.assertEqual(right_band, band)
            self.assertEqual(full_band, band/2)
            self.assertTrue(np.array_equal(left[0,::2,0], combined[0,:width//2,0]))
            self.assertTrue(np.array_equal(right[0,::2,0], combined[0,width//2:,0]))
            self.assertEqual(int(combined[0,width//2-1,0]), int(left[0,-2,0]))
            self.assertEqual(int(combined[0,width//2,0]), int(right[0,0,0]))

    def test_broad_v14_corrects_only_symmetric_goal_area_band(self):
        import numpy as np
        left, band = mowing_blend('pitch_l_bsm_alp', 1024, 'clean-v14')
        right, right_band = mowing_blend('pitch_r_bsm_alp', 1024, 'clean-v14')
        self.assertAlmostEqual(band, 530/3)
        self.assertEqual(right_band, band)
        self.assertEqual((np.flatnonzero(np.diff(left[0,:,0]))+1).tolist(),
                         [155,331,494,671,848])
        self.assertEqual((np.flatnonzero(np.diff(right[0,:,0]))+1).tolist(),
                         [177,354,530,693,870])
        self.assertEqual(int(left[0,330,0]), 1)
        self.assertEqual(int(left[0,331,0]), 0)
        self.assertEqual(int(left[0,493,0]), 0)
        self.assertEqual(int(left[0,494,0]), 1)
        self.assertEqual(494-331, 163)
        self.assertEqual(693-530, 163)
        self.assertEqual(pitch_colors('clean-v14'), pitch_colors('clean-v10'))

    def test_broad_v14_lr_is_symmetric_and_alternates_at_midfield(self):
        import numpy as np
        for width in (1024,512,256,128):
            left, band = mowing_blend('pitch_l_bsm_alp', width, 'clean-v14')
            right, right_band = mowing_blend('pitch_r_bsm_alp', width, 'clean-v14')
            combined, full_band = mowing_blend('pitch_lr_bsm_exLow_alp', width, 'clean-v14')
            self.assertEqual(right_band, band)
            self.assertEqual(full_band, band/2)
            self.assertTrue(np.array_equal(left[0,::2,0], combined[0,:width//2,0]))
            self.assertTrue(np.array_equal(right[0,::2,0], combined[0,width//2:,0]))
            self.assertEqual(int(combined[0,width//2-1,0]), 1)
            self.assertEqual(int(combined[0,width//2,0]), 0)

    def test_uniform_v9_all_bands_and_complemented_low_right(self):
        import numpy as np
        left, band = mowing_blend('pitch_l_bsm_alp', 1024, 'clean-v9')
        right, other_band = mowing_blend('pitch_r_bsm_alp', 1024, 'clean-v9')
        combined, combined_band = mowing_blend('pitch_lr_bsm_exLow_alp', 1024, 'clean-v9')
        self.assertEqual(band, 77)
        self.assertEqual(other_band, band)
        self.assertEqual(combined_band, band/2)
        values = left[0, 254:1024, 0]
        self.assertEqual(values.reshape(10, 77).sum(1).tolist(), [0,77]*5)
        # Low_R mirrors the SAME L geometry, now in its own v8 alias.
        inverse = 1-left
        self.assertEqual(int(left[0,-1,0]), 1)
        self.assertEqual(int(inverse[0,-1,0]), 0)
        self.assertEqual(int(right[0,0,0]), 0)
        self.assertEqual(int(combined[0,511,0]), 1)
        self.assertEqual(int(combined[0,512,0]), 0)
        # Pixel rounding <=1 px in the half-resolution distant full-pitch map.
        edges = np.flatnonzero(np.diff(combined[0,127:897,0]))+1
        lengths = np.diff(np.r_[0,edges,770])
        self.assertEqual(len(lengths),20)
        self.assertLessEqual(int(lengths.max()-lengths.min()),1)

    def test_legacy_v6_active_rectangle_recipe(self):
        left, _ = mowing_blend('pitch_l_bsm_alp', 1024, 'clean-v6')
        right, _ = mowing_blend('pitch_r_bsm_alp', 1024, 'clean-v6')
        combined, _ = mowing_blend('pitch_lr_bsm_exLow_alp', 1024, 'clean-v6')
        # Historical authored sample positions only. The v6 Switch test did
        # not confirm these as the shader's actual midpoint sampling points.
        self.assertEqual(int(left[0, 254, 0]), 0)
        self.assertEqual(int(left[0, 1023, 0]), 1)
        self.assertEqual(int(right[0, 0, 0]), 0)
        self.assertEqual(int(right[0, 769, 0]), 1)
        self.assertEqual(int(combined[0, 511, 0]), 1)
        self.assertEqual(int(combined[0, 512, 0]), 0)

    def test_global_phase_opposes_shared_texture_edges(self):
        left, band = mowing_blend('pitch_l_bsm_alp', 1024, 'clean-v7')
        right, _ = mowing_blend('pitch_r_bsm_alp', 1024, 'clean-v7')
        combined, combined_band = mowing_blend('pitch_lr_bsm_exLow_alp', 1024, 'clean-v7')
        self.assertAlmostEqual(band, 1024 / 6)
        self.assertAlmostEqual(combined_band, 1024 / 12)
        # Exported mesh UV0 before shader transforms: L u=1 and R u~=0.
        # The runtime material's final sampling still needs a device test.
        self.assertEqual(int(left[0, 0, 0]), 0)
        self.assertEqual(int(left[0, 1023, 0]), 1)
        self.assertEqual(int(right[0, 0, 0]), 0)
        self.assertEqual(int(right[0, 1023, 0]), 1)
        self.assertEqual(int(combined[0, 511, 0]), 1)
        self.assertEqual(int(combined[0, 512, 0]), 0)

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

import io
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_kit_preview_canary import render_jersey, thumbnail_members
from kit_preview_mesh import build_mesh, render_mesh, Mesh


class KitPreviewCanaryTests(unittest.TestCase):
    def test_renderer_is_deterministic_and_uses_mesh_silhouette(self):
        atlas = Image.new("RGBA", (256, 384), (18, 80, 170, 255))
        draw = ImageDraw.Draw(atlas)
        draw.rectangle((106, 205, 150, 235), fill=(245, 210, 20, 255))
        template = Image.new("RGBA", (128, 128), (255, 255, 255, 0))
        mask = Image.new("L", (128, 128), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.polygon(
            [(44, 24), (25, 31), (15, 61), (40, 70), (43, 120),
             (85, 120), (88, 70), (113, 61), (103, 31), (84, 24)],
            fill=255,
        )
        template.putalpha(mask)
        buffer = io.BytesIO()
        template.save(buffer, format="PNG")
        first = render_jersey(atlas, buffer.getvalue())
        second = render_jersey(atlas, buffer.getvalue())
        self.assertEqual(first.size, (128, 128))
        self.assertEqual(first.tobytes(), second.tobytes())
        self.assertNotEqual(first.getchannel("A").tobytes(), mask.tobytes())
        self.assertEqual(first.getpixel((64, 12))[3], 0)  # actual neck opening
        self.assertGreater(first.getpixel((64, 60))[3], 240)
        self.assertEqual(first.getpixel((4, 60))[3], 0)
        self.assertGreater(np.asarray(first)[..., :3].std(), 5)

    def test_mesh_has_depth_and_valid_atlas_uvs(self):
        mesh = build_mesh()
        self.assertGreater(np.ptp(mesh.vertices[:, 2]), 5)
        self.assertTrue(np.isfinite(mesh.normals).all())
        self.assertTrue((mesh.uv >= 0).all())
        self.assertTrue((mesh.uv < (256, 384)).all())
        self.assertIn('collar', mesh.parts)
        self.assertIn('sleeve_left', mesh.parts)
        self.assertIn('sleeve_right', mesh.parts)
        self.assertFalse(any(part.startswith('shoulder_') for part in mesh.parts))
        for part in ('sleeve_left', 'sleeve_right'):
            triangles = mesh.triangles[np.array(mesh.parts) == part]
            self.assertEqual(len(np.unique(triangles)), 41 * 25)

    def test_depth_test_is_independent_of_triangle_draw_order(self):
        atlas = Image.new('RGBA', (256, 384), (255, 0, 0, 255))
        ImageDraw.Draw(atlas).rectangle((128, 0, 255, 383), fill=(0, 0, 255, 255))
        xyz = np.array([(20,20,1),(100,20,1),(64,100,1),
                        (20,20,9),(100,20,9),(64,100,9)], dtype=float)
        uv = np.array([(30,40)]*3+[(180,40)]*3,dtype=float)
        normals = np.array([(0,0,1)]*6,dtype=float)
        triangles = np.array([(0,1,2),(3,4,5)])
        mesh = Mesh(xyz, uv, normals, triangles, ['back', 'front'])
        first = render_mesh(atlas, mesh)
        mesh.triangles = triangles[::-1]
        second = render_mesh(atlas, mesh)
        self.assertEqual(first.tobytes(), second.tobytes())
        self.assertGreater(first.getpixel((64,50))[2], 200)
        self.assertEqual(first.getpixel((64,50))[0], 0)

    def test_thumbnail_member_mapping_uses_physical_team_and_kind(self):
        def entry(name):
            return {"name": name, "row": {}}

        team = 108
        p1 = team << 14
        p2 = p1 | 1
        regulated_p1 = p1 | (3 << 9)
        index = {
            "rows": {
                "a": entry(f"common/render/thumbnail/uniform/uni{p1}.png"),
                "b": entry(f"common/render/thumbnail/uniform/uni{p2}.png"),
                "c": entry(f"common/render/thumbnail/uniform/uni{regulated_p1}.png"),
                "d": entry(f"common/render/thumbnail/uniform/uni{p1}_full.png"),
            }
        }
        self.assertEqual(
            thumbnail_members(index, team, 0),
            [
                f"common/render/thumbnail/uniform/uni{p1}.png",
                f"common/render/thumbnail/uniform/uni{regulated_p1}.png",
            ],
        )
        self.assertEqual(
            thumbnail_members(index, team, 1),
            [f"common/render/thumbnail/uniform/uni{p2}.png"],
        )


if __name__ == "__main__":
    unittest.main()

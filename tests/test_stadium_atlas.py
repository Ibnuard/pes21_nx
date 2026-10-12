"""Atlas conversion preserves repeated UVs, cutouts and native crowd pixels."""
import hashlib
import json
from pathlib import Path
import sys
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from stadium_atlas import prepare, atlas_uv, PAGE, CELL, INNER, GUTTER


def test_repeat_uvs_stay_in_their_tile_including_negative_and_large_values():
    for tile in range(16):
        for u in (-32.4, -1, -.2, 0, .2, .999, 1, 123.2):
            x, y = atlas_uv(u, u + .1, tile)
            assert tile % 4 * CELL + GUTTER <= x * PAGE < (tile % 4 + 1) * CELL - GUTTER
            assert tile // 4 * CELL + GUTTER <= y * PAGE < (tile // 4 + 1) * CELL - GUTTER
            assert atlas_uv(u + 2, u + 2.1, tile) == pytest.approx((x, y))


def test_rgb_and_masks_are_independently_compressible_and_inputs_remain_read_only(tmp_path):
    # Asymmetric source exposes an accidental V flip, wrong tile or alpha loss.
    im = Image.new('RGBA', (INNER, INNER), (100, 150, 200, 255))
    im.paste((220, 70, 40, 0), (0, 0, INNER // 2, INNER // 2))
    source = tmp_path / 'source.png'
    im.save(source)
    crowd = Image.new('RGBA', (1024, 1024))
    for frame in range(16):
        crowd.paste((frame * 15, 99, 137, frame * 16), (0, frame * 64, 1024, (frame + 1) * 64))
    crowd_path = tmp_path / 'crowd.png'
    crowd.save(crowd_path)
    profile = tmp_path / 'fbx.local.json'
    profile.write_text(json.dumps(dict(material_slots=['M_shell', 'M_crowd_seated'], crowd_flipbook=True,
        texture_files={'M_shell': str(source), 'M_crowd_seated': str(crowd_path)})))
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (source, crowd_path, profile)]
    result = prepare(profile, tmp_path / 'result')
    page = result['pages'][0]
    rgb, mask = Image.open(page['color']), Image.open(page['mask'])
    assert rgb.mode == mask.mode == 'RGB'
    for x, y in ((0, 0), (100, 70), (220, 220)):
        expected = im.getpixel((x, y))
        assert rgb.getpixel((x + GUTTER, y + GUTTER)) == expected[:3]
        assert mask.getpixel((x + GUTTER, y + GUTTER)) == (expected[3],) * 3
    # Wrap gutter copies the opposing edge, not the next atlas tile.
    assert rgb.getpixel((0, 20)) == im.getpixel((INNER - GUTTER, 20 - GUTTER))[:3]
    animated = result['pages'][-1]
    assert Image.open(animated['color']).tobytes() == crowd.convert('RGB').tobytes()
    assert Image.open(animated['mask']).getchannel('R').tobytes() == crowd.getchannel('A').tobytes()
    assert before == [hashlib.sha256(p.read_bytes()).hexdigest() for p in (source, crowd_path, profile)]


def test_atlas_pages_bound_draw_sections_and_keep_opaque_separate(tmp_path):
    im = tmp_path / 'solid.png'
    Image.new('RGB', (16, 16), (40, 50, 60)).save(im)
    names = ['M_s%d' % i for i in range(33)]
    profile = tmp_path / 'fbx.local.json'
    profile.write_text(json.dumps(dict(material_slots=names, texture_files={n: str(im) for n in names})))
    result = prepare(profile, tmp_path / 'out')
    assert result['new_materials'] == 3
    assert all('mask' not in p for p in result['pages'])
    assert len(result['mapping']) == 33
    assert result['mapping']['M_s32']['tile'] == 0


def test_glass_authored_at_cutout_threshold_is_resolved_before_lossy_compression(tmp_path):
    # Tottenham has broad panes at 102/255 alpha: ETC1's rounding used to
    # change >5% of its mask coverage, despite a correct mesh and UV channel.
    im = Image.new('RGBA', (INNER, INNER), (130, 140, 150, 101))
    im.paste((130, 140, 150, 102), (INNER // 2, 0, INNER, INNER))
    path = tmp_path / 'glass.png'
    im.save(path)
    profile = tmp_path / 'fbx.local.json'
    profile.write_text(json.dumps(dict(material_slots=['M_glass'], texture_files={'M_glass': str(path)})))
    result = prepare(profile, tmp_path / 'out')
    coverage = Image.open(result['pages'][0]['mask'])
    assert coverage.getpixel((GUTTER + 40, GUTTER + 40)) == (0, 0, 0)
    assert coverage.getpixel((GUTTER + 180, GUTTER + 40)) == (255, 255, 255)

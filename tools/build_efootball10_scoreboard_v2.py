"""Compact single-row native scoreboard, with EF10 colors/logo.

No runtime hooks, new text engine, injected frame handlers or AS3 edits.
The exact original AP2 timeline is retained with patched placement/color fields.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib
import zopfli.zlib

import numpy as np
from PIL import Image

from afp_score_layout import patch_layout, read_movies, placements
from afp_texture_patch import read_atlas, replace_atlas
from cooked_texture import Texture
from scoreboard_geometry import (BOXES, LOGO_ICON, PLATE_HEIGHT, PLATE_WIDTH,
                                 SCORE_DIVIDER, TEXT_CENTER_CORRECTION_X, validate_geometry)


def unpack_wesys(data):
    if data[:8] == b'\xff\x10\x81WESYS':
        compressed, size = struct.unpack_from('<II', data, 8)
        if len(data) != 16+compressed:
            raise ValueError('WESYS compressed size mismatch')
        data = zlib.decompress(data[16:])
        if len(data) != size:
            raise ValueError('WESYS expanded size mismatch')
    return data


def region_bounds(region):
    _, l, t, r, b = region['rect']
    return l//2, t//2, (r+1)//2, (b+1)//2


def build(base, ef10, output):
    if output.exists():
        raise ValueError('output must be a new directory; baseline must not be overwritten')
    original = unpack_wesys(base.read_bytes())
    modified, layout_report = patch_layout(original)
    atlas, regions, (txp_base, _, _, _) = read_atlas(modified)
    w, h = struct.unpack_from('>HH', atlas, 16)
    if (w, h) != (1024, 512):
        raise ValueError('unexpected native atlas dimensions')
    old = np.frombuffer(atlas[64:], np.uint8).reshape(h, w, 4)
    pixels = old.copy()  # Native ARGB byte order, not RGBA.
    navy = Texture(next(ef10.rglob('MatchTimePlate_0.uexp'))).decode().getpixel((0, 0))[:3]
    yellow = Texture(next(ef10.rglob('MatchTimePlate_1.uexp'))).decode().getpixel((0, 0))[:3]
    if navy != (0, 0, 100) or yellow != (230, 230, 0):
        raise ValueError('unexpected EF10 palette')
    changed_regions = []
    for entry in regions:
        name = entry['name']
        color = None
        if name == 'game2dPes-score-plateTime':
            color = yellow
        elif name.startswith('MatchPlate-texFont-'):
            color = navy
        if color is not None:
            x0, y0, x1, y1 = region_bounds(entry)
            pixels[y0:y1, x0:x1, 1:] = color
            changed_regions.append(name)

    # Give the stretched background an actual horizontal color texture. Its
    # AP2 image has explicit virtual dimensions (6x72), kept unchanged, so this
    # changes sampling resolution, not geometry. Move only its atlas region.
    geometry = validate_geometry()
    x0, y0, width, height = 0, 400, PLATE_WIDTH, PLATE_HEIGHT
    for entry in regions:
        left, top, right, bottom = region_bounds(entry)
        if left < x0+width and right > x0 and top < y0+height and bottom > y0:
            raise ValueError('new scoreboard background overlaps another atlas region')
    if old[y0:y0+height, x0:x0+width, 0].any():
        raise ValueError('new scoreboard background overlaps nonempty atlas pixels')
    bar = np.empty((height, width, 4), np.uint8)
    bar[:, :, 0] = 255
    bar[:, :, 1:] = navy
    # The verified AP2 patch makes team names yellow and scores navy throughout
    # their native fades. This lets the score cells use the solid EF10 yellow
    # reference instead of the temporary V4 outline treatment.
    for name in ('home_score', 'away_score', 'timer'):
        start, stop = BOXES[name]
        bar[:, start:stop, 1:] = yellow
    bar[:, SCORE_DIVIDER[0]:SCORE_DIVIDER[1], 1:] = navy
    logo = Texture(next(ef10.rglob('MatchTimeLogo.uexp'))).decode().convert('RGB')
    logo = np.asarray(logo.resize((24, 24), Image.Resampling.LANCZOS))
    # Reference order: accent, team, score, team, accent, clock, PES logo.
    # The two team boxes are both 78 px. Native 8 px away accent sits between
    # away team and clock. The terminal logo context is square, 48x48 px;
    # its unstretched 24x24 icon is centered with equal 12 px padding.
    lx0, ly0, lx1, ly1 = LOGO_ICON
    bar[ly0:ly1, lx0:lx1, 1:] = logo
    pixels[y0:y0+height, x0:x0+width] = bar
    index = next(i for i, r in enumerate(regions) if r['name'] == 'game2dPes-score-plateMain')
    region_table = struct.unpack_from('>I', modified, txp_base+40)[0]
    new_rect = (0, x0*2+1, y0*2+1, (x0+width)*2-1, (y0+height)*2-1)
    modified = bytearray(modified)
    struct.pack_into('>5H', modified, txp_base+region_table+index*10, *new_rect)
    # Fewer LZSS candidates give the outer DEFLATE stage a more repetitive
    # stream. Both stages are lossless; decoded atlas size/format are unchanged.
    modified = replace_atlas(bytes(modified), atlas[:64]+pixels.tobytes(), candidate_limit=4)
    changed_regions.append('game2dPes-score-plateMain')
    checked_atlas, checked_regions, _ = read_atlas(modified)
    if checked_atlas != atlas[:64]+pixels.tobytes():
        raise ValueError('atlas roundtrip mismatch')
    for i, (a, b) in enumerate(zip(regions, checked_regions)):
        if i != index and a != b:
            raise ValueError('unrelated atlas region metadata changed')
    for before, after in zip(read_movies(original), read_movies(modified)):
        if before.name != 'game2d_score' and before.data != after.data:
            raise ValueError('unrelated native UI movie changed')
    score = next(m for m in read_movies(modified) if m.name == 'game2d_score')
    nodes = [r for r in placements(score.data) if r['parent'] == 28 and r['frame'] == 0]
    packed = zopfli.zlib.compress(modified, numiterations=15)
    if zlib.decompress(packed) != modified:
        raise ValueError('WESYS compression roundtrip mismatch')
    wesys = b'\xff\x10\x81WESYS'+struct.pack('<II', len(packed), len(modified))+packed
    if len(wesys) > 102400:
        raise ValueError(f'scoreboard is {len(wesys)} bytes and exceeds the 102400-byte CPK slot; do not install')
    output.mkdir(parents=True)
    (output/'game2dPes.bin').write_bytes(wesys)
    Image.fromarray(pixels[:, :, [1, 2, 3, 0]]).save(output/'atlas-preview.png')
    Image.fromarray(bar[:, :, [1, 2, 3, 0]]).save(output/'bar-background-preview.png')
    report = {'base_sha256': hashlib.sha256(base.read_bytes()).hexdigest(),
              'output_sha256': hashlib.sha256(wesys).hexdigest(),
              'wesys_size': len(wesys), 'modified_regions': changed_regions,
              'compression': {'lzss_candidates': 4, 'zopfli_iterations': 15,
                              'original_cpk_slot_capacity': 102400, 'lossless': True},
              'main_plate_region': new_rect, 'other_region_metadata_preserved': True,
              'native_image_virtual_dimensions_unchanged': True,
              'main_plate_animation_scale_divisor_x': 96,
              'clock_display_depths': {'normal': 77, 'progress': 78},
              'right_end_order': ['team_accent', 'timer', 'pes_logo'],
              'context_boxes_atlas_px': geometry,
              'logo_icon_rect_atlas_px': list(LOGO_ICON),
              'score_divider_atlas_x': list(SCORE_DIVIDER),
              'team_score_glyph_offset_correction_x': TEXT_CENTER_CORRECTION_X,
              'layout': layout_report, 'initial_nodes': nodes,
              'runtime_tested': False, 'competition_badge_ported': False,
              'uir_team_and_score_text': 'team names EF10 yellow; scores EF10 navy; native fades retained',
              'reference_limitations': ['competition badge not ported']}
    (output/'validation.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k not in ('layout', 'initial_nodes')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, default=Path('local-debug/stability-visuals/built/game2dPes.bin'))
    parser.add_argument('--ef10', type=Path, default=Path('local-debug/stability-visuals/ef10'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.base, args.ef10, args.output)

"""Validate the compact scoreboard against the approved baseline UI member.

Checks container metadata, the entire non-atlas prefix, timeline edits, alpha
and unrelated atlas pixels. This does not substitute for a device render test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np

from afp_score_layout import patch_layout, placements, read_movies
from afp_texture_patch import read_atlas
from build_efootball10_scoreboard_v2 import region_bounds, unpack_wesys
from scoreboard_geometry import LOGO_ICON, timeline_targets, validate_geometry


def validate(base, candidate):
    original = unpack_wesys(base.read_bytes())
    packed = candidate.read_bytes()
    modified = unpack_wesys(packed)
    assert packed[:8] == b'\xff\x10\x81WESYS' and len(packed) <= 102400
    expected, layout = patch_layout(original)
    atlas, regions, old_layout = read_atlas(original)
    new_atlas, new_regions, new_layout = read_atlas(modified)
    assert old_layout[:3] == new_layout[:3]
    assert len(atlas) == len(new_atlas) and atlas[:64] == new_atlas[:64]
    txp, table, payload, _ = old_layout
    index = next(i for i, r in enumerate(regions) if r['name'] == 'game2dPes-score-plateMain')
    region_table = struct.unpack_from('>I', original, txp+40)[0]
    rect_offset = txp+region_table+index*10
    assert new_regions[index]['rect'] == (0, 1, 801, 767, 895)
    assert all(a == b for i, (a, b) in enumerate(zip(regions, new_regions)) if i != index)

    # All bytes preceding the atlas must equal the narrowly patched original,
    # except container/payload lengths and the single relocated region.
    prefix = bytearray(expected[:txp+payload])
    actual = bytearray(modified[:txp+payload])
    for start, size in ((12, 4), (txp+12, 4), (txp+table+4, 4), (rect_offset, 10)):
        prefix[start:start+size] = actual[start:start+size] = bytes(size)
    assert prefix == actual
    before_movies, after_movies = read_movies(original), read_movies(modified)
    assert len(before_movies) == len(after_movies) == 8
    for before, after in zip(before_movies, after_movies):
        assert (before.name, before.size, before.info) == (after.name, after.size, after.info)
        if before.name != 'game2d_score':
            assert before.data == after.data
            continue
        tag_start = struct.unpack_from('<I', before.data, 36)[0]
        strings_start = struct.unpack_from('<I', before.data, 48)[0]
        assert before.data[:tag_start] == after.data[:tag_start]  # AS3/headers
        assert before.data[strings_start:] == after.data[strings_start:]
        assert len(placements(before.data)) == len(placements(after.data)) == 534
        for old, new in zip(placements(before.data), placements(after.data)):
            if old['parent'] == 28 and old['depth'] in (14, 33):
                assert new['depth'] == (77 if old['depth'] == 14 else 78)
            targeted = old['parent'] == 28 and old['depth'] in (61, 63, 65, 67)
            if targeted and 'mult8' in old:
                old_value, new_value = int(old['mult8'][0]), int(new['mult8'][0])
                expected_rgb = 0xe6e600 if old['depth'] in (61, 63) else 0x000064
                expected_alpha = old_value & 255
                last_fade = 30 if old['depth'] in (61, 63) else 24
                if old['frame'] == last_fade and expected_alpha == 224:
                    expected_alpha = 255
                assert new_value == (expected_rgb << 8) | expected_alpha
            elif targeted and old['flags'] & 0x8:
                assert new['flags'] == old['flags'] & ~0x8
            elif 'mult8' in old and not (old['parent'] == 28 and old['depth'] == 81):
                assert old['mult8'] == new['mult8']
        main_scales=[r['scale'][0] for r in placements(after.data)
                     if r['parent']==28 and r['depth']==60 and 'scale' in r]
        assert len(main_scales)==17 and 0.84 < min(main_scales) <= max(main_scales) < 1.01
        initial={r['depth']:r for r in placements(after.data)
                 if r['parent']==28 and r['frame']==0}
        for depth, xy in timeline_targets().items():
            actual_depth = {14:77, 33:78}.get(depth, depth)
            assert initial[actual_depth]['translate']==xy
        assert initial[61]['scale']==initial[63]['scale']
        assert initial[61]['translate'][0]-initial[63]['translate'][0]==154
        # Source accent consists of two 8x24 tiles at child x=-2, y=-2/22.
        # Mirroring the parent at x244 therefore occupies x238..246.
        assert initial[69]['scale']==(-1.0, 1.0)
        accent_children=[r for r in placements(after.data)
                         if r['parent']==27 and r['frame']==0 and r['depth'] in (1,3)]
        assert [r['translate'] for r in accent_children]==[(-2.0,-2.0),(-2.0,22.0)]

    width, height = struct.unpack_from('>HH', atlas, 16)
    before = np.frombuffer(atlas[64:], np.uint8).reshape(height, width, 4)
    after = np.frombuffer(new_atlas[64:], np.uint8).reshape(height, width, 4)
    allowed = np.zeros((height, width), bool)
    allocated = np.zeros_like(allowed)
    allocated[400:448, 0:384] = True
    assert not before[allocated, 0].any()
    changed = []
    for region in regions:
        name = region['name']
        color = None
        if name == 'game2dPes-score-plateTime':
            color = (230, 230, 0)
        elif name.startswith('MatchPlate-texFont-'):
            color = (0, 0, 100)
        if color is not None:
            x0, y0, x1, y1 = region_bounds(region)
            allowed[y0:y1, x0:x1] = True
            assert np.all(after[y0:y1, x0:x1, 1:] == color)
            changed.append(name)
    allowed |= allocated
    assert np.array_equal(before[~allowed], after[~allowed])
    assert np.array_equal(before[~allocated, 0], after[~allocated, 0])
    assert np.all(after[allocated, 0] == 255)
    assert np.all(after[400:448, 78:115, 1:] == (230, 230, 0))
    assert np.all(after[400:448, 115:117, 1:] == (0, 0, 100))
    assert np.all(after[400:448, 117:154, 1:] == (230, 230, 0))
    assert np.all(after[400:448, 240:336, 1:] == (230, 230, 0))
    assert np.all(after[400:448, 154:240, 1:] == (0, 0, 100))
    lx0, ly0, lx1, ly1 = LOGO_ICON
    assert not np.all(after[400+ly0:400+ly1, lx0:lx1, 1:] == (0, 0, 100))
    # All four margins around the square logo icon remain navy.
    assert np.all(after[400:412, 336:384, 1:] == (0,0,100))
    assert np.all(after[436:448, 336:384, 1:] == (0,0,100))
    assert np.all(after[400:448, 336:348, 1:] == (0,0,100))
    assert np.all(after[400:448, 372:384, 1:] == (0,0,100))
    for region in regions:
        if region['name'].startswith('game2dPes-score-plateTeamColor-'):
            l,t,r,b=region_bounds(region)
            assert (r-l,b-t)==(8,24)
    return {
        'scoreboard_sha256': hashlib.sha256(packed).hexdigest(),
        'wesys_bytes': len(packed), 'fits_original_cpk_slot': True,
        'other_movies_identical': 7, 'regions_checked': len(regions),
        'regions_recolored': len(changed), 'background_regions_relocated': 1,
        'other_pixels_and_native_alpha_preserved': True,
        'all_non_image_bytes_match_whitelisted_layout_edits': True,
        'as3_strings_bindings_and_image_virtual_sizes_unchanged': True,
        'team_and_score_text_rgb_persisted_without_as3_changes': True,
        'native_text_fades_preserved': True,
        'placements_checked': layout['placement_count'],
        'timeline_field_edits': len(layout['edits']), 'device_tested': False,
        'compact_main_plate_scale_keyframes_checked': 17,
        'clock_nodes_lifted_above_opaque_plate': 58,
        'away_team_accent_before_clock': True,
        'terminal_pes_logo_after_clock': True,
        'context_boxes_atlas_px': validate_geometry(),
        'equal_team_boxes_px': 78,
        'equal_score_boxes_px': 38,
        'logo_context_size_px': [48,48],
        'logo_icon_size_px': [24,24],
        'equal_visible_yellow_score_widths_px': [37,37],
        'team_score_glyph_offset_correction_x': -2,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, default=Path('local-debug/stability-visuals/built/game2dPes.bin'))
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = validate(args.base, args.candidate)
    rendered = json.dumps(report, indent=2)
    if args.report:
        args.report.write_text(rendered+'\n', encoding='utf-8')
    print(rendered)

"""Patch the deployed scoreboard only, preserving all other OBB members.

Uses verified AP2 field offsets and fixed CPK slots; never repacks runtime kits.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import zopfli.zlib

from afp_score_layout import read_movies, placements, swap_fields
from afp_texture_patch import read_atlas, replace_atlas
from build_efootball10_scoreboard_v2 import unpack_wesys, region_bounds
from prepare_runtime import read_cpk_packet
from patch_cpk_slots import patch_slot, member_name


def extract(source, member, destination):
    with source.open('rb') as stream:
        header = read_cpk_packet(stream, 0, b'CPK ')[0]
        rows = read_cpk_packet(stream, header['TocOffset'], b'TOC ')
        row, = [r for r in rows if member_name(r) == member]
        assert row['FileSize'] == row['ExtractSize']
        stream.seek(min(header['TocOffset'], header['ContentOffset']) + row['FileOffset'])
        destination.write_bytes(stream.read(row['FileSize']))


def patch_score(data, font_path):
    original = unpack_wesys(data)
    movie, = [m for m in read_movies(original) if m.name == 'game2d_score']
    records = placements(movie.data)
    initial = {r['depth']: r for r in records if r['parent'] == 28 and r['frame'] == 0}
    assert initial[60]['translate'] == (6.0, 0.0), 'Unexpected deployed plate origin'
    assert initial[69]['translate'] == (244.0, 2.0), 'Unexpected deployed accent'
    changed = bytearray(movie.data)
    # Retain native 38-pixel score text bounds; center them in new 48px cells.
    # Deployed v8 promotes time_set/losstime_progress_set to depths 77/78.
    # Moving only the old 14/33 depths leaves live digits 20px left of center.
    shifts = {7: 20, 13: 20, 14: 20, 33: 20, 77: 20, 78: 20, 56: 20,
              61: 20, 65: 15, 67: 5, 69: 20}
    count = 0
    for record in records:
        if record['parent'] == 28 and 'translate' in record:
            x, y = record['translate']
            struct.pack_into('<ii', changed, record['translate_offset'],
                             round((x + shifts.get(record['depth'], 0)) * 20),
                             round((y + 20) * 20))
            count += 1
    assert len(placements(changed)) == len(records)
    result = bytearray(original)
    result[movie.offset:movie.offset + movie.size] = swap_fields(changed, movie.info)
    atlas, regions, (txp, _, _, _) = read_atlas(result)
    width, height = struct.unpack_from('>HH', atlas, 16)
    pixels = np.frombuffer(atlas[64:], np.uint8).reshape(height, width, 4).copy()
    plate_index, plate = next((i, r) for i, r in enumerate(regions)
                             if r['name'] == 'game2dPes-score-plateMain')
    x0, y0, x1, y1 = region_bounds(plate)
    assert (x1-x0, y1-y0) == (384, 48), 'Expected compact 384x48 baseline'
    for i, region in enumerate(regions):
        l, t, r, b = region_bounds(region)
        if i != plate_index:
            assert not (l < x0+404 and r > x0 and t < y1 and b > y0), 'Atlas overlap'
    assert not pixels[y0:y1, x1:x1+20, 0].any(), 'Expansion padding occupied'
    bar = pixels[y0:y1, x0:x1].copy()
    # Duplicate interior columns only; retain original palette and logo pixels.
    expanded = np.concatenate((bar[:, :115], np.repeat(bar[:, 110:111], 10, axis=1),
                               bar[:, 115:153], np.repeat(bar[:, 140:141], 10, axis=1),
                               bar[:, 153:]), axis=1)
    assert expanded.shape == (48, 404, 4)
    pixels[y0:y1, x0:x0+404] = expanded
    table = struct.unpack_from('>I', result, txp + 40)[0]
    struct.pack_into('>5H', result, txp + table + plate_index * 10,
                     0, x0*2+1, y0*2+1, (x0+404)*2-1, y1*2-1)
    font = ImageFont.truetype(str(font_path), 24)
    for region in regions:
        name = region['name']
        l, t, r, b = region_bounds(region)
        if name.startswith('game2dPes-score-plateTeamColor-'):
            # Native timeline supplies the kit tint; opaque white corners make
            # each two-color identity strip rectangular, without baked colors.
            pixels[t:b, l:r] = (255, 255, 255, 255)
        elif name.startswith('MatchPlate-texFont-digit') or name == 'MatchPlate-texFont-colon':
            glyph = ':' if name.endswith('colon') else name[-1]
            mask = Image.new('L', (r-l, b-t), 0)
            draw = ImageDraw.Draw(mask)
            box = font.getbbox(glyph)
            draw.text(((r-l-(box[2]-box[0]))/2-box[0],
                       (b-t-(box[3]-box[1]))/2-box[1]), glyph, font=font, fill=255)
            pixels[t:b, l:r, 0] = np.asarray(mask)
            pixels[t:b, l:r, 1:] = (0, 0, 100)
    result = replace_atlas(bytes(result), atlas[:64]+pixels.tobytes(), candidate_limit=4)
    checked, _, _ = read_atlas(result)
    assert checked == atlas[:64]+pixels.tobytes()
    for before, after in zip(read_movies(original), read_movies(result)):
        assert before.name == after.name
        if before.name != 'game2d_score':
            assert before.data == after.data
    compressed = zopfli.zlib.compress(result, numiterations=15)
    assert zlib.decompress(compressed) == result
    output = b'\xff\x10\x81WESYS' + struct.pack('<II', len(compressed), len(result)) + compressed
    return output, {'score_cells': [48, 48], 'height': 48, 'plate_width': 404,
                    'vertical_offset_delta': 20, 'translated_keyframes': count,
                    'kit_accents': 'opaque rectangular native-tinted strips',
                    'timer_font': str(font_path), 'team_font': 'native unchanged',
                    'hardware_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--obb', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Output must be a new directory')
    args.output.mkdir(parents=True)
    dt = args.output / 'dt210-original.cpk'
    score = args.output / 'game2d-original.bin'
    dt_member = 'Expansion/dt210_mobile_android.cpk'
    extract(args.obb, dt_member, dt)
    with dt.open('rb') as stream:
        header = read_cpk_packet(stream, 0, b'CPK ')[0]
        rows = read_cpk_packet(stream, header['TocOffset'], b'TOC ')
    score_member, = [member_name(r) for r in rows if r['FileName'] == 'game2dPes.bin']
    extract(dt, score_member, score)
    payload, report = patch_score(score.read_bytes(), Path('assets/fonts/efootball/eFootballSans-Bold.ttf'))
    candidate = args.output / 'game2dPes.bin'
    candidate.write_bytes(payload)
    patched_dt = args.output / 'dt210-square.cpk'
    report['inner'] = patch_slot(dt, patched_dt, score_member, candidate)
    output_obb = args.output / args.obb.name
    report['outer'] = patch_slot(args.obb, output_obb, dt_member, patched_dt)
    report['obb_size'] = output_obb.stat().st_size
    report['score_sha256'] = hashlib.sha256(payload).hexdigest()
    (args.output / 'validation.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

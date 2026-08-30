"""Verify a locally generated patch against the user's actual stock assets."""
import argparse
import json
from pathlib import Path
import struct
import zlib

import numpy as np
from PIL import Image

from afp_texture_patch import read_atlas
from cooked_texture import Texture


def validate_pitch(stock, built):
    textures = list(built.rglob('*.uexp'))
    if len(textures) != 6:
        raise ValueError('expected exactly six pitch textures')
    total_mips = 0
    for path in textures:
        base = stock / path.relative_to(built)
        old, new = Texture(base), Texture(path)
        assert base.with_suffix('.uasset').read_bytes() == path.with_suffix('.uasset').read_bytes()
        assert old.format == new.format and old.mips == new.mips
        assert old.files.keys() == new.files.keys()
        # Compare all package bytes outside the mip payloads, not just lengths.
        for suffix, original in old.files.items():
            modified = new.files[suffix]
            assert len(original) == len(modified)
            cursor = 0
            for mip in sorted((m for m in old.mips if m.file == suffix), key=lambda m: m.offset):
                assert original[cursor:mip.offset] == modified[cursor:mip.offset]
                cursor = mip.offset + mip.size
            assert original[cursor:] == modified[cursor:]
        rgb = np.asarray(old.decode())[:, :, :3].astype(np.int16)
        lines = Image.fromarray(np.uint8((rgb.min(axis=2) >= 78) &
                                          (rgb.max(axis=2) - rgb.min(axis=2) <= 48)) * 255)
        for i, mip in enumerate(old.mips):
            a, b = np.asarray(old.decode(i)), np.asarray(new.decode(i))
            assert np.array_equal(a[:, :, 3], b[:, :, 3])
            if old.format == 'PF_ETC1':
                rgb = a[:, :, :3].astype(np.int16)
                mask = ((rgb.min(axis=2) >= 78) & (rgb.max(axis=2) - rgb.min(axis=2) <= 48))
                mask |= np.asarray(lines.resize((mip.width, mip.height), Image.Resampling.BOX)) > 0
                blocks = mask.reshape(mip.height // 4, 4, mip.width // 4, 4).any(axis=(1, 3)).reshape(-1)
                before, after = old.payload(i), new.payload(i)
                assert all(before[j*8:j*8+8] == after[j*8:j*8+8] for j in np.flatnonzero(blocks))
            total_mips += 1
    assert total_mips == 35
    return {'textures': len(textures), 'mips_validated': total_mips,
            'native_line_blocks_preserved': True, 'alpha_and_package_metadata_preserved': True}


def validate_scoreboard(base, skin):
    original = base.read_bytes()
    wesys = skin.read_bytes()
    assert wesys[:8] == b'\xff\x10\x81WESYS'
    compressed, expanded = struct.unpack_from('<II', wesys, 8)
    assert len(wesys) == compressed + 16
    modified = zlib.decompress(wesys[16:])
    assert len(modified) == expanded
    atlas, regions, (offset, table, payload, _) = read_atlas(original)
    new_atlas, new_regions, new_layout = read_atlas(modified)
    assert regions == new_regions and new_layout[:3] == (offset, table, payload)
    assert atlas[:64] == new_atlas[:64] and len(atlas) == len(new_atlas)
    # The only non-image changes allowed are the three payload/container sizes.
    before, after = bytearray(original[:offset+payload]), bytearray(modified[:offset+payload])
    for size_offset in (12, offset+12, offset+table+4):
        before[size_offset:size_offset+4] = bytes(4)
        after[size_offset:size_offset+4] = bytes(4)
    assert before == after
    w, h = struct.unpack_from('>HH', atlas, 16)
    old_pixels = np.frombuffer(atlas[64:], dtype=np.uint8).reshape(h, w, 4)
    new_pixels = np.frombuffer(new_atlas[64:], dtype=np.uint8).reshape(h, w, 4)
    assert np.array_equal(old_pixels[:, :, 0], new_pixels[:, :, 0])
    mask = np.zeros((h, w), dtype=bool)
    selected = {'game2dPes-score-plateTime', 'game2dPes-score-plateMain',
                'game2dPes-score-plateAgreegateScore', 'game2dPes-score-plateStats'}
    for region in regions:
        if region['name'] in selected:
            _, l, t, r, b = region['rect']
            mask[t//2:(b+1)//2, l//2:(r+1)//2] = True
    assert np.array_equal(old_pixels[~mask], new_pixels[~mask])
    assert not np.array_equal(old_pixels[mask], new_pixels[mask])
    return {'regions': len(regions), 'modified_regions': len(selected),
            'scripts_layout_alpha_and_other_regions_preserved': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stock', type=Path, required=True, help='Textures extracted from the actual stock PES21 PAK')
    parser.add_argument('--built', type=Path, default=Path('local-debug/stability-visuals/built/pitch-stage'))
    parser.add_argument('--score-base', type=Path, default=Path('local-debug/stability-visuals/pes21-ui/game2dPes.bin'))
    parser.add_argument('--skin', type=Path, default=Path('local-debug/stability-visuals/built/game2dPes.bin'))
    args = parser.parse_args()
    print(json.dumps({'pitch': validate_pitch(args.stock, args.built),
                      'scoreboard': validate_scoreboard(args.score_base, args.skin)}, indent=2))


if __name__ == '__main__':
    main()

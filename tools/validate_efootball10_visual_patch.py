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


def validate_pitch(stock, built, style='baseline', baseline=None):
    textures = list(built.rglob('*.uexp'))
    expected_count=6 if style=='baseline' else 8
    if len(textures) != expected_count:
        raise ValueError(f'expected exactly {expected_count} pitch textures')
    total_mips = 0
    grain_checks = 0
    phase_checks = 0
    for path in textures:
        base = stock / path.relative_to(built)
        old, new = Texture(base), Texture(path)
        if baseline is not None and (style=='mask-only' and not path.stem.startswith('pitch_specular_mask_') or path.stem=='pitch2_bsm_alp_copied'):
            before=baseline/path.relative_to(built)
            for suffix in new.files:
                assert before.with_suffix('.'+suffix).read_bytes()==new.files[suffix]
        if style in ('clean-v3','clean-v4','clean-v5','clean-v6','clean-v7') and baseline is not None and not path.stem.startswith('pitch_specular_mask_') and path.stem!='pitch2_bsm_alp_copied':
            prior=Texture(baseline/path.relative_to(built))
            old_green=np.asarray(prior.decode())[:,:,1].astype(np.float32)
            new_green=np.asarray(new.decode())[:,:,1].astype(np.float32)
            # Color/pattern mean remains v2 while fine adjacent-pixel variation
            # is measurably restored in the once-mapped diffuse.
            if style in ('clean-v5','clean-v6'):
                # Edge pixels outside the native field rectangle do not enter
                # gameplay. Compare the authored/playable geometry only.
                if '_lr_' in path.stem:
                    active=slice(127,897)
                else:
                    active=slice(254,1024) if path.stem.startswith('pitch_l_') else slice(0,770)
                assert abs(float(old_green[:,active].mean()-new_green[:,active].mean())) < 0.5
            else:
                assert abs(float(old_green.mean()-new_green.mean())) < 0.5
            old_variation=(np.abs(np.diff(old_green,axis=0)).mean()+np.abs(np.diff(old_green,axis=1)).mean())/2
            new_variation=(np.abs(np.diff(new_green,axis=0)).mean()+np.abs(np.diff(new_green,axis=1)).mean())/2
            assert new_variation > old_variation + 2.0
            grain_checks += 1
            old_bands=np.array([old_green[:,x:x+128].mean() for x in range(0,1024,128)])
            new_bands=np.array([new_green[:,x:x+128].mean() for x in range(0,1024,128)])
            if style=='clean-v3' and path.stem.startswith('pitch_r_'):
                assert np.corrcoef(old_bands,new_bands)[0,1] < -0.98
                phase_checks += 1
            elif style=='clean-v3':
                assert np.corrcoef(old_bands,new_bands)[0,1] > 0.98
            elif style=='clean-v4':
                band_width=64 if '_lr_' in path.stem else 128
                old_columns=old_green.mean(axis=0)
                new_columns=new_green.mean(axis=0)
                # New diffuse is the accepted v2 mowing pattern shifted left
                # by exactly half a band. Painted-line blocks remain fixed, so
                # the independent decoded correlation is intentionally <1.
                assert np.corrcoef(np.roll(old_columns,-band_width//2),new_columns)[0,1] > 0.60
                phase_checks += 1
            elif style=='clean-v5':
                columns=new_green.mean(axis=0)
                band_width=64 if '_lr_' in path.stem else 128
                if '_lr_' in path.stem:
                    center=columns.size//2
                    assert columns[center-band_width:center].mean() > 60
                    assert columns[center:center+band_width].mean() < 60
                elif path.stem.startswith('pitch_l_'):
                    assert columns[:band_width].mean() > 60
                    assert columns[-band_width:].mean() > 60
                else:
                    assert columns[:band_width].mean() < 60
                    assert columns[-band_width:].mean() < 60
                phase_checks += 1
            elif style=='clean-v6':
                columns=new_green.mean(axis=0)
                if '_lr_' in path.stem:
                    assert columns[448:511].mean() > 60
                    assert columns[512:576].mean() < 60
                elif path.stem.startswith('pitch_l_'):
                    assert columns[254:382].mean() < 60
                    assert columns[896:1024].mean() > 60
                else:
                    assert columns[0:128].mean() < 60
                    assert columns[642:770].mean() > 60
                phase_checks += 1
            elif style=='clean-v7':
                columns=new_green.mean(axis=0)
                if '_lr_' in path.stem:
                    # Twelve global bands: the two samples adjacent to the
                    # combined texture midpoint must be light/dark.
                    assert columns[426:510].mean() > 60
                    assert columns[514:598].mean() < 60
                else:
                    # Six global bands force opposite phases at u=0 and u=1,
                    # including Low_R which shares the left diffuse texture.
                    assert columns[8:160].mean() < 60
                    assert columns[864:1016].mean() > 60
                phase_checks += 1
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
            if path.stem.startswith('pitch_specular_mask_'):
                assert np.all(b[:,:,:2]==128)
                assert np.array_equal(a[:,:,2:],b[:,:,2:])
            if old.format == 'PF_ETC1':
                rgb = a[:, :, :3].astype(np.int16)
                mask = ((rgb.min(axis=2) >= 78) & (rgb.max(axis=2) - rgb.min(axis=2) <= 48))
                mask |= np.asarray(lines.resize((mip.width, mip.height), Image.Resampling.BOX)) > 0
                blocks = mask.reshape(mip.height // 4, 4, mip.width // 4, 4).any(axis=(1, 3)).reshape(-1)
                before, after = old.payload(i), new.payload(i)
                assert all(before[j*8:j*8+8] == after[j*8:j*8+8] for j in np.flatnonzero(blocks))
            total_mips += 1
    assert total_mips == (35 if style=='baseline' else 37)
    return {'textures': len(textures), 'mips_validated': total_mips,
            'native_line_blocks_preserved': True, 'alpha_and_package_metadata_preserved': True,
            'diffuse_grain_restoration_checks':grain_checks,
            'stripe_phase_checks':phase_checks}


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
    parser.add_argument('--pitch-style',choices=('baseline','mask-only','clean-v2','clean-v3','clean-v4','clean-v5','clean-v6','clean-v7'),default='baseline')
    parser.add_argument('--baseline-pitch',type=Path)
    parser.add_argument('--pitch-only',action='store_true')
    args = parser.parse_args()
    report={'pitch':validate_pitch(args.stock,args.built,args.pitch_style,args.baseline_pitch)}
    if not args.pitch_only:
        report['scoreboard']=validate_scoreboard(args.score_base,args.skin)
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()

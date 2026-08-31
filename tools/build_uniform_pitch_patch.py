"""Uniform pitch recipes, keeping v8's proven Low_R binding (v9 or broad v10)."""
import argparse
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import numpy as np

from build_efootball10_visual_patch import mowing_blend, pitch
from build_low_pitch_phase_patch import CONTENT, TEXTURE, NEW_TEXTURE
from cooked_texture import Texture

DIFFUSES = ('pitch_l_bsm_alp', 'pitch_r_bsm_alp', 'pitch_lr_bsm_exLow_alp',
            'pitch_l_bsm_exLow_alp', 'pitch_r_bsm_exLow_alp')


def validate(baseline, built, stock, style='clean-v9'):
    files = {p.relative_to(baseline) for p in baseline.rglob('*') if p.is_file()}
    assert files == {p.relative_to(built) for p in built.rglob('*') if p.is_file()}
    assert len(files) == 27
    changed = set()
    textures = []
    for name in (*DIFFUSES, NEW_TEXTURE):
        relative = CONTENT/'Textures'/(name+'.uexp')
        native_name = TEXTURE if name == NEW_TEXTURE else name
        source = Texture(stock/CONTENT/'Textures'/(native_name+'.uexp'))
        prior, candidate = Texture(baseline/relative), Texture(built/relative)
        assert source.format == candidate.format == 'PF_ETC1'
        assert source.mips == candidate.mips
        # Permit changed pixels only, not size/metadata/trailer changes.
        rebuilt = prior.replace([candidate.payload(i) for i in range(len(candidate.mips))])
        for suffix, data in rebuilt.items():
            assert data == (built/relative).with_suffix('.'+suffix).read_bytes()
            changed.add(relative.with_suffix('.'+suffix))
        top = np.array(source.decode())[:, :, :3].astype(np.int16)
        mask = (top.min(2) >= 78) & (top.max(2)-top.min(2) <= 48)
        from PIL import Image
        line_image = Image.fromarray(mask.astype('uint8')*255)
        line_counts = []
        for i, mip in enumerate(source.mips):
            rgb = np.array(source.decode(i))[:, :, :3].astype(np.int16)
            paint = (rgb.min(2) >= 78) & (rgb.max(2)-rgb.min(2) <= 48)
            paint |= np.array(line_image.resize((mip.width, mip.height), Image.Resampling.BOX)) > 0
            blocks = paint.reshape(mip.height//4, 4, mip.width//4, 4).any(axis=(1, 3)).reshape(-1)
            a, b = source.payload(i), candidate.payload(i)
            assert all(a[k*8:k*8+8] == b[k*8:k*8+8] for k in np.flatnonzero(blocks))
            line_counts.append(int(blocks.sum()))
        # Check encoded top-mip phase on every Low/standard/exLow variant,
        # not only the two textures selected by the known Low material path.
        shade, _ = mowing_blend(native_name, top.shape[1], style)
        shade = shade[0,:,0]
        if name == NEW_TEXTURE:
            shade = 1-shade
        start, end = ((127,897) if '_lr_' in name else
                      (0,770) if name.startswith('pitch_r_') else (254,1024))
        phase_edges = np.r_[start, np.flatnonzero(np.diff(shade[start:end]))+start+1, end]
        phase_centers = ((phase_edges[:-1]+phase_edges[1:])/2).astype(int)
        encoded = np.array(candidate.decode())
        # A phase-locked outer-box candidate can leave a short clipped band
        # immediately before the LR midpoint. Keep the sample window inside
        # its own band so the neighboring shade at the seam is not averaged
        # into the assertion.
        greens = []
        for index, x in enumerate(phase_centers):
            previous_edge, next_edge = phase_edges[index:index+2]
            radius = min(10, (x-previous_edge-1)//2,
                         (next_edge-x-1)//2)
            radius = max(0, int(radius))
            greens.append(float(np.median(encoded[110:180,
                                                 x-radius:x+radius+1, 1])))
        assert np.array_equal(np.array(greens) > 61.5, shade[phase_centers]), name
        textures.append({'name': name, 'mips': len(candidate.mips),
                         'encoded_phase_verified': True, 'band_green_samples': greens,
                         'line_blocks_preserved': line_counts})
    for relative in files-changed:
        assert (baseline/relative).read_bytes() == (built/relative).read_bytes(), relative
    left = np.array(Texture(built/CONTENT/'Textures'/(TEXTURE+'.uexp')).decode())
    right = np.array(Texture(built/CONTENT/'Textures'/(NEW_TEXTURE+'.uexp')).decode())
    blend, band_width = mowing_blend(TEXTURE, 1024, style)
    active = blend[0,254:1024,0]
    edges = np.r_[254, np.flatnonzero(np.diff(active))+255, 1024]
    # Sample EVERY visible band away from paint, including the edge-clipped
    # outer band in v10. It continues at unchanged width outside the goal.
    centers = ((edges[:-1]+edges[1:])/2).astype(int)
    a_samples = []
    b_samples = []
    for index, x in enumerate(centers):
        previous_edge, next_edge = edges[index:index+2]
        radius = min(10, (x-previous_edge-1)//2,
                     (next_edge-x-1)//2)
        radius = max(0, int(radius))
        a_samples.append(left[110:180,x-radius:x+radius+1,1].mean())
        b_samples.append(right[110:180,x-radius:x+radius+1,1].mean())
    a = np.array(a_samples)
    b = np.array(b_samples)
    expected = blend[0,centers,0]
    assert np.array_equal(a > 61.5, expected)
    assert np.array_equal(b > 61.5, 1-expected)
    assert np.max(np.abs(a+b-123)) < 4
    if style in ('clean-v12', 'clean-v13'):
        # v12 locks the penalty-box transition at x494; its final clipped
        # outer stripe therefore ends in the opposite phase to v10/v11.
        assert a[-1] < 61.5 and b[-1] > 61.5
    else:
        assert a[-1] > 61.5 and b[-1] < 61.5  # actual mirrored Low seam
    # At v10 the entire field is one constant pitch, not ten narrow bands
    # per half. Ignore only the two outer portions clipped by the goal lines.
    if style in ('clean-v10', 'clean-v11', 'clean-v12', 'clean-v13', 'clean-v14'):
        full = np.r_[active, 1-active[::-1]]
        transitions = np.flatnonzero(np.diff(full))+1
        lengths = np.diff(transitions)
        expected_width = ({176,177} if style == 'clean-v10' else
                          {173,174} if style == 'clean-v11' else
                          {17,69,171} if style == 'clean-v12' else
                          {14,168,174} if style == 'clean-v13' else
                          {163,176,177})
        assert set(lengths).issubset(expected_width)
        assert 770 in transitions
        if style == 'clean-v10':
            assert 494 in edges
        elif style == 'clean-v11':
            assert 331 in edges
        elif style == 'clean-v13':
            assert 494 in edges
        elif style == 'clean-v14':
            assert 331 in edges and 494 in edges
        assert len(centers) == (6 if style in ('clean-v12','clean-v13') else 5)
    return {'recipe': style, 'pak_files': len(files), 'unchanged_files': len(files-changed),
            'all_materials_shaders_headers_identical_to_v8': True,
            'visible_bands_per_half': len(centers), 'full_pitch_visible_bands': 2*len(centers),
            'band_width_texture_px': band_width,
            'all_band_widths_uniform': style not in ('clean-v13','clean-v14'),
            'dark_band_width_texture_px': 168.0 if style == 'clean-v13' else None,
            'light_band_width_texture_px': 174.0 if style == 'clean-v13' else None,
            'light_to_dark_width_ratio': (174.0/168.0 if style == 'clean-v13' else None),
            'goal_area_corrected_band_width_texture_px': 163.0 if style == 'clean-v14' else None,
            'symmetric_goal_area_correction': style == 'clean-v14',
            'outer_band_continues_beyond_goal_line': style in ('clean-v10','clean-v11','clean-v12','clean-v13','clean-v14'),
            'left_band_boundaries_in_playable_area_px': edges.tolist(),
            'left_green_samples': a.tolist(), 'right_green_samples': b.tolist(),
            'native_lines': textures, 'device_tested': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--baseline', type=Path, default=Path('local-debug/visual-v8-20260831/pitch-build/pitch-stage'))
    p.add_argument('--stock', type=Path, default=Path('local-debug/pitch-audit-20260826/base'))
    p.add_argument('--ef10', type=Path, default=Path('local-debug/stability-visuals/ef10'))
    p.add_argument('--etc1tool', type=Path, default=Path.home()/'AppData/Local/Android/Sdk/platform-tools/etc1tool.exe')
    p.add_argument('--verify-only', action='store_true')
    p.add_argument('--style', choices=('clean-v9', 'clean-v10', 'clean-v11', 'clean-v12', 'clean-v13', 'clean-v14'), default='clean-v9')
    args = p.parse_args()
    stage = args.output/'pitch-stage'
    if not args.verify_only:
        if args.output.exists():
            raise ValueError('output must be a new directory')
        shutil.copytree(args.baseline, stage)
        settings = SimpleNamespace(pes21=args.stock, ef10=args.ef10,
                                   etc1tool=args.etc1tool, pitch_style=args.style)
        for inverse in (False, True):
            work = args.output/('right-phase' if inverse else 'uniform-source')
            previews = work/'previews'
            previews.mkdir(parents=True)
            pitch(settings, work, previews, selected_names=(TEXTURE,) if inverse else DIFFUSES,
                  complement_diffuse=inverse)
            for name in ((TEXTURE,) if inverse else DIFFUSES):
                src = work/'pitch-stage'/CONTENT/'Textures'/(name+'.uexp')
                dst = stage/CONTENT/'Textures'/((NEW_TEXTURE if inverse else name)+'.uexp')
                # Reuse v8's headers/name hashes. Only replace texture payloads.
                for suffix in ('.uexp', '.ubulk'):
                    if src.with_suffix(suffix).exists():
                        shutil.copy2(src.with_suffix(suffix), dst.with_suffix(suffix))
    result = validate(args.baseline, stage, args.stock, args.style)
    (args.output/'validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

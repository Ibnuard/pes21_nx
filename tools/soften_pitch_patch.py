"""Soften an existing cooked pitch patch without changing its package layout."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageFilter

from cooked_texture import Texture
from build_efootball10_visual_patch import etc1, mowing_blend, pitch_colors


def soften(rgb, name=None):
    pixels = np.asarray(rgb, dtype=np.float32)
    grass = ((pixels[:, :, 1] > pixels[:, :, 0]) &
             (pixels[:, :, 1] > pixels[:, :, 2]) & (pixels[:, :, 1] > 10))
    if grass.sum() < pixels.shape[0] * pixels.shape[1] / 2:
        raise ValueError('Not a predominantly green pitch diffuse')
    base = pixels[grass].mean(axis=0)
    broad = np.asarray(rgb.filter(ImageFilter.GaussianBlur(1.1)), dtype=np.float32)
    # Reduce broad mowing contrast; retain only gentle bright blade detail.
    result = base + (broad - base) / 3 + np.maximum(pixels - broad, 0) * 0.4
    if name is not None:
        # Rebuild from our authored recipe when the surviving local patch is
        # older than v16. Do not carry its obsolete near-black palette forward.
        blend, _ = mowing_blend(name, rgb.width, 'clean-v17')
        dark, light = map(np.asarray, pitch_colors('clean-v17'))
        rng = np.random.default_rng(1701)
        grain = np.maximum(rng.normal(0, 1, (rgb.height, rgb.width, 1)), 0)
        result = dark + blend * (light - dark) + grain * np.array([1.2, 2.4, 0.9])
    return Image.fromarray(np.clip(np.rint(result), 0, 255).astype('uint8'))


def build(baseline, output, encoder):
    if output.exists():
        raise ValueError('Output must be a new directory')
    stage = output / 'stage'
    shutil.copytree(baseline, stage)
    previews = output / 'previews'
    previews.mkdir()
    records = []
    changed = set()
    for path in sorted(baseline.rglob('pitch_*bsm*alp.uexp')):
        texture = Texture(path)
        if texture.format != 'PF_ETC1':
            raise ValueError(f'Unexpected pitch format: {path}')
        top = texture.decode().convert('RGB')
        top_pixels = np.asarray(top, dtype=np.int16)
        paint = (top_pixels.min(2) >= 78) & (np.ptp(top_pixels, axis=2) <= 48)
        paint_image = Image.fromarray(paint.astype('uint8') * 255)
        payloads, counts = [], []
        for index, mip in enumerate(texture.mips):
            original = texture.decode(index).convert('RGB')
            rgb = np.asarray(original, dtype=np.int16)
            mask = (rgb.min(2) >= 78) & (np.ptp(rgb, axis=2) <= 48)
            mask |= np.asarray(paint_image.resize(original.size, Image.Resampling.BOX)) > 0
            blocks = mask.reshape(mip.height//4, 4, mip.width//4, 4).any(axis=(1, 3)).reshape(-1)
            softened = soften(original, path.stem)
            encoded = bytearray(etc1(softened, previews / f'{path.stem}-{index}.etc1', encoder))
            source = texture.payload(index)
            for block in np.flatnonzero(blocks):
                encoded[block*8:block*8+8] = source[block*8:block*8+8]
            assert all(encoded[b*8:b*8+8] == source[b*8:b*8+8] for b in np.flatnonzero(blocks))
            payloads.append(bytes(encoded))
            counts.append(int(blocks.sum()))
        target = stage / path.relative_to(baseline)
        for suffix, data in texture.replace(payloads).items():
            destination = target.with_suffix('.' + suffix)
            destination.write_bytes(data)
            changed.add(destination.relative_to(stage))
        verified = Texture(target)
        assert all(verified.payload(i) == value for i, value in enumerate(payloads))
        top.save(previews / f'{path.stem}-before.png')
        verified.decode().save(previews / f'{path.stem}-after.png')
        records.append({'texture': str(path.relative_to(baseline)), 'mips': len(payloads),
                        'protected_paint_blocks': counts,
                        'baseline_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    if not records:
        raise ValueError('No pitch diffuse textures found')
    for path in baseline.rglob('*'):
        if path.is_file() and path.relative_to(baseline) not in changed:
            assert path.read_bytes() == (stage / path.relative_to(baseline)).read_bytes()
    report = {'textures': records, 'material_and_other_files_unchanged': True,
              'recipe': 'clean-v17', 'grain': 'deterministic positive fine grain',
              'palette': pitch_colors('clean-v17')}
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--encoder', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.baseline, args.output, args.encoder), indent=2))

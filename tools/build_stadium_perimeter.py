"""Make a local warm-neutral stadium apron patch from the owned native texture.

Only st029_field_bsm is replaced. The native st029_pitch_2 StaticMaterials
array assigns it to M_field_ed (outer apron); the playable left/right pitch
uses MI_Pitch_L/R. Camera crew use an unrelated atlas. No mesh, material,
shader, pitch texture, lightmap, or package metadata is rewritten.
Generated PAKs and decoded previews are proprietary local data, never public.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
from PIL import Image

from cooked_texture import Texture

MEMBER = Path('PesMobile/Content/Assets/bg_lighting_AM1/Textures/st029_field_bsm')
WEIGHTS = np.array([.2126, .7152, .0722])


def linear(rgb):
    rgb = np.asarray(rgb, dtype=np.float64) / 255
    return np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)


def warm_apron(image):
    """Retain grain luminance, attenuate 20%, replace green with restrained ochre."""
    rgba = np.asarray(image.convert('RGBA'))
    luminance = linear(rgba[:, :, :3]) @ WEIGHTS
    tint = np.array([1.26, 1., .66])
    tint /= tint @ WEIGHTS
    rgb = np.clip(luminance[:, :, None] * .8 * tint, 0, 1)
    srgb = np.where(rgb <= .0031308, rgb * 12.92, 1.055 * rgb ** (1 / 2.4) - .055)
    result = rgba.copy()
    result[:, :, :3] = np.clip(np.rint(srgb * 255), 0, 255).astype(np.uint8)
    return Image.fromarray(result)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(native, output, encoder, repak):
    source = native / MEMBER.with_suffix('.uexp')
    texture = Texture(source)
    if texture.format != 'PF_ETC1' or (texture.width, texture.height) != (128, 128):
        raise ValueError('Expected the owned 128x128 ETC1 stadium apron texture')
    if output.exists():
        raise ValueError('Use a new output directory; existing packages are preserved')
    output.mkdir(parents=True)
    stage = output / 'stage'
    dest = stage / MEMBER
    dest.parent.mkdir(parents=True)
    work = output / 'mips'
    work.mkdir()
    inputs = {suffix: source.with_suffix('.' + suffix).read_bytes()
              for suffix in ('uasset', *texture.files)}
    payloads = []
    stats = []
    for i, mip in enumerate(texture.mips):
        original = texture.decode(i)
        candidate = warm_apron(original)
        png, encoded = work / f'{i}.png', work / f'{i}.etc1'
        candidate.convert('RGB').save(png)
        subprocess.run([str(encoder), str(png), '--encodeNoHeader', '-o', str(encoded)],
                       check=True, capture_output=True)
        payloads.append(encoded.read_bytes())
        stats.append(dict(mip=i, width=mip.width, height=mip.height, bytes=mip.size))
    changed = texture.replace(payloads)
    for suffix, raw in changed.items():
        dest.with_suffix('.' + suffix).write_bytes(raw)
        # Outside the known mip ranges every byte must remain identical.
        undone = bytearray(raw)
        for mip in texture.mips:
            if mip.file == suffix:
                undone[mip.offset:mip.offset+mip.size] = inputs[suffix][mip.offset:mip.offset+mip.size]
        if bytes(undone) != inputs[suffix]:
            raise ValueError('Texture metadata changed')
    shutil.copyfile(source.with_suffix('.uasset'), dest.with_suffix('.uasset'))
    decoded = Texture(dest.with_suffix('.uexp'))
    for i, mip in enumerate(texture.mips):
        before = np.asarray(texture.decode(i))[:, :, :3]
        after = np.asarray(decoded.decode(i))[:, :, :3]
        avg = linear(after).mean(axis=(0, 1))
        ratio = float((linear(after) @ WEIGHTS).mean() / (linear(before) @ WEIGHTS).mean())
        # ETC1 can quantize R/G to the same level in the smallest solid mips.
        # Warm yellow is acceptable; green dominance or brightening is not.
        if not (avg[0] >= avg[1] > avg[2] and .65 < ratio < .95):
            raise ValueError(f'Mip {i}: ETC1 output lost the warm palette or luminance bound')
        stats[i].update(linear_rgb_mean=avg.tolist(), luminance_ratio=ratio)
    texture.decode().save(output / 'apron-native.png')
    decoded.decode().save(output / 'apron-warm.png')
    target = output / 'PesMobile-StadiumPerimeter-Android_ETC1_P.pak'
    subprocess.run([str(repak), 'pack', '--version', 'V8A', '--compression', 'Zlib',
                    str(stage), str(target)], check=True)
    members = {p.relative_to(stage).as_posix(): sha(p.read_bytes())
               for p in stage.rglob('*') if p.is_file()}
    actual = subprocess.check_output([str(repak), 'list', str(target)], text=True).splitlines()
    if set(actual) != set(members):
        raise ValueError('Unexpected PAK members')
    for member, expected in members.items():
        if sha(subprocess.check_output([str(repak), 'get', str(target), member])) != expected:
            raise ValueError('PAK roundtrip mismatch')
    if any(source.with_suffix('.'+suffix).read_bytes() != raw for suffix, raw in inputs.items()):
        raise ValueError('Original texture changed')
    report = dict(input_hashes={suffix: sha(raw) for suffix, raw in inputs.items()},
                  members=members, output_sha256=sha(target.read_bytes()), mips=stats,
                  metadata_preserved=True, native_untouched=True, roundtrip_verified=True,
                  hardware_tested=False)
    (output / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('native', 'output', 'encoder', 'repak'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    print(build(*(getattr(args, name).resolve() for name in ('native', 'output', 'encoder', 'repak'))))

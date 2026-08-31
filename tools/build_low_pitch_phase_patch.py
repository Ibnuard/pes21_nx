"""Separate Low_R's diffuse binding; preserve cooked shaders and line UVs.

Uses UAssetGUI only to obtain valid name-table hashes for same-length renames.
All export payloads (including opaque cooked shader maps) are copied verbatim,
not reserialized. A tightly checked name-table diff is the only header edit.
The new diffuse is the L texture with opposite mowing phase and original lines.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
from types import SimpleNamespace
import zlib

import numpy as np

from build_efootball10_visual_patch import pitch
from cooked_texture import Texture

CONTENT = Path('PesMobile/Content/Assets/bg_lighting_AM1')
PARENT = 'M_Pitch_Default_night_Low'
NEW_PARENT = 'M_Pitch_Default_night_NXR'
TEXTURE = 'pitch_l_bsm_alp'
NEW_TEXTURE = 'pitch_n_bsm_alp'
RIGHT_MATERIALS = ('MI_Pitch_Low_R', 'MI_Pitch_Default_night_Low_R')
RIGHT_SHADER_SHA = '902e2ab6768804d805fd477a9083780c48214f16a454ccf1ca74924b9aa4da41'
LEFT_SHADER_SHA = '47dc245c64bc15603593c22cd3bca9df6ece5e4ba6c27ea5390b45142281738a'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def name_entries(data):
    # Verified UE4.22 package summary with zero custom-version entries.
    if data[:4] != b'\xc1\x83\x2a\x9e' or struct.unpack_from('<i', data, 20)[0] != 0:
        raise ValueError('unsupported package summary')
    folder_length = struct.unpack_from('<i', data, 28)[0]
    if folder_length <= 0:
        raise ValueError('unsupported folder string')
    count, offset = struct.unpack_from('<ii', data, 36 + folder_length)
    entries = []
    for _ in range(count):
        start = offset
        length = struct.unpack_from('<i', data, start)[0]
        if not 0 < length < 4096:
            raise ValueError('unsupported name string')
        offset = start + 4 + length + 4
        raw = data[start+4:start+4+length]
        if raw[-1:] != b'\0' or offset > len(data):
            raise ValueError('truncated name entry')
        entries.append((raw[:-1].decode('ascii'), start, offset))
    return entries


def renamed_value(value, replacements):
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [renamed_value(v, replacements) for v in value]
    if isinstance(value, dict):
        return {k: renamed_value(v, replacements) for k, v in value.items()}
    return value


def rename_package(source, target, replacements, work, gui):
    if any(len(a) != len(b) for a, b in replacements.items()):
        raise ValueError('only same-length name changes are allowed')
    work.mkdir(parents=True)
    stock_json = work/'stock.json'
    edited_json = work/'renamed.json'
    temporary = work/target.name
    subprocess.run([str(gui), 'tojson', str(source), str(stock_json), 'VER_UE4_22'], check=True)
    document = json.loads(stock_json.read_text(encoding='utf-8-sig'))
    old_names = document['NameMap']
    if not set(replacements).issubset(old_names):
        raise ValueError('expected renamed names missing from package')
    modified = renamed_value(document, replacements)
    edited_json.write_text(json.dumps(modified), encoding='utf-8')
    subprocess.run([str(gui), 'fromjson', str(edited_json), str(temporary)], check=True)
    before, generated = source.read_bytes(), temporary.read_bytes()
    if len(before) != len(generated):
        raise ValueError('renamed package header size changed')
    old_entries, new_entries = name_entries(before), name_entries(generated)
    if len(old_entries) != len(new_entries):
        raise ValueError('name table count changed')
    patched = bytearray(before)
    changes = []
    for (old, start, end), (new, ns, ne) in zip(old_entries, new_entries):
        if (start, end) != (ns, ne) or new != replacements.get(old, old):
            raise ValueError('unexpected name table edit')
        if old in replacements:
            patched[start:end] = generated[start:end]
            changes.append({'from': old, 'to': new, 'start': start, 'end': end})
    # GUI may roundtrip opaque export data imperfectly. Its .uexp is never
    # used. We also reject any generated header change outside approved names.
    if bytes(patched) != generated:
        raise ValueError('header changed outside the renamed name entries')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(patched)
    for suffix in ('.uexp', '.ubulk'):
        original = source.with_suffix(suffix)
        if original.exists():
            shutil.copy2(original, target.with_suffix(suffix))
            assert original.read_bytes() == target.with_suffix(suffix).read_bytes()
    return {'source': str(source), 'target': str(target), 'header_bytes': len(before),
            'name_changes': changes, 'exports_and_shader_bytecode_identical': True}


def audit_shaders(path, mirrored):
    data = path.read_bytes()
    expected = RIGHT_SHADER_SHA if mirrored else LEFT_SHADER_SHA
    if sha(data) != expected:
        raise ValueError('not the audited PES21 Low material shader revision')
    pixels, vertices, mirrors = 0, 0, 0
    example = None
    for match in re.finditer(b'\x78[\x01\x5e\x9c\xda]', data):
        try:
            raw = zlib.decompress(data[match.start():])
        except zlib.error:
            continue
        if raw.startswith(b'LSLGSP'):
            pixels += 1
            mirrors += b'vec2(-1.000000e+00,1.000000e+00)' in raw
            if example is None:
                source = raw[raw.index(b'#version'):].split(b'\0', 1)[0]
                lines = source.decode('ascii').splitlines()
                example = [line for line in lines if 'var_TEXCOORD0.xy' in line
                           or 'vec2(-1.000000e+00,1.000000e+00)' in line]
        elif raw.startswith(b'LSLGSV'):
            vertices += 1
    assert (pixels, vertices, mirrors) == (80, 40, 80 if mirrored else 0)
    return {'sha256': sha(data), 'pixel_shaders': pixels, 'vertex_shaders': vertices,
            'negative_u_pixel_shaders': mirrors, 'uv_excerpt': example}


def validate_inverse(original, prior, new):
    stock, left, right = Texture(original), Texture(prior), Texture(new)
    assert len(stock.mips) == len(left.mips) == len(right.mips) == 1
    assert stock.format == left.format == right.format == 'PF_ETC1'
    a, l, r = (np.asarray(t.decode()) for t in (stock, left, right))
    rgb = a[:, :, :3].astype(np.int16)
    mask = (rgb.min(2) >= 78) & ((rgb.max(2) - rgb.min(2)) <= 48)
    blocks = mask.reshape(256, 4, 256, 4).any(axis=(1, 3)).reshape(-1)
    stock_payload, left_payload, right_payload = stock.payload(), left.payload(), right.payload()
    for index in np.flatnonzero(blocks):
        sl = slice(index*8, index*8+8)
        assert stock_payload[sl] == right_payload[sl] == left_payload[sl]
    assert np.array_equal(l[:, :, 3], r[:, :, 3])
    # Avoid paint and stripe boundaries. Equal shades/grass amplitude, opposite
    # phase. Both halves still sample x~1023 at midfield under the Low shader.
    samples = [40, 230, 420, 590, 760, 960]
    lm = np.array([l[100:190, x:x+24, 1].mean() for x in samples])
    rm = np.array([r[100:190, x:x+24, 1].mean() for x in samples])
    assert np.corrcoef(lm, rm)[0, 1] < -0.99
    assert np.max(np.abs(lm + rm - 123)) < 4
    assert lm[-1] > 70 and rm[-1] < 55
    return {'native_line_blocks_identical': int(blocks.sum()), 'left_samples_green': lm.tolist(),
            'right_samples_green': rm.tolist(), 'opposite_phase_correlation': float(np.corrcoef(lm, rm)[0, 1]),
            'low_mirrored_midfield_left_light_right_dark': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, default=Path('local-debug/visual-v7-20260831/pitch-build/pitch-stage'))
    parser.add_argument('--stock', type=Path, default=Path('local-debug/pitch-audit-20260826/base'))
    parser.add_argument('--materials', type=Path, default=Path('local-debug/pitch-material-audit-20260831'))
    parser.add_argument('--ef10', type=Path, default=Path('local-debug/stability-visuals/ef10'))
    parser.add_argument('--uassetgui', type=Path, default=Path('local-debug/pitch-audit-20260826/UAssetGUI.exe'))
    parser.add_argument('--etc1tool', type=Path, default=Path.home()/'AppData/Local/Android/Sdk/platform-tools/etc1tool.exe')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('output must be a new directory')
    args.output.mkdir(parents=True)
    stage = args.output/'pitch-stage'
    shutil.copytree(args.baseline, stage)
    material_root = args.materials/CONTENT/'Materials'
    shader_report = {PARENT: audit_shaders(material_root/(PARENT+'.uexp'), False)}
    for name in RIGHT_MATERIALS:
        shader_report[name] = audit_shaders(material_root/(name+'.uexp'), True)
    inverse = args.output/'inverse-source'
    previews = inverse/'previews'
    previews.mkdir(parents=True)
    settings = SimpleNamespace(pes21=args.stock, ef10=args.ef10, etc1tool=args.etc1tool,
                               pitch_style='clean-v7')
    pitch(settings, inverse, previews, selected_names=(TEXTURE,), complement_diffuse=True)
    renamed = []
    old_parent_path = '/Game/Assets/bg_lighting_AM1/Materials/'+PARENT
    new_parent_path = '/Game/Assets/bg_lighting_AM1/Materials/'+NEW_PARENT
    old_texture_path = '/Game/Assets/bg_lighting_AM1/Textures/'+TEXTURE
    new_texture_path = '/Game/Assets/bg_lighting_AM1/Textures/'+NEW_TEXTURE
    gui = args.uassetgui.resolve()
    renamed.append(rename_package(
        material_root/(PARENT+'.uasset'), stage/CONTENT/'Materials'/(NEW_PARENT+'.uasset'),
        {PARENT: NEW_PARENT, old_parent_path: new_parent_path,
         TEXTURE: NEW_TEXTURE, old_texture_path: new_texture_path}, args.output/'rename-parent', gui))
    for name in RIGHT_MATERIALS:
        renamed.append(rename_package(
            material_root/(name+'.uasset'), stage/CONTENT/'Materials'/(name+'.uasset'),
            {PARENT: NEW_PARENT, old_parent_path: new_parent_path, TEXTURE: NEW_TEXTURE},
            args.output/('rename-'+name), gui))
    inverted_texture = inverse/'pitch-stage'/CONTENT/'Textures'/(TEXTURE+'.uasset')
    renamed.append(rename_package(inverted_texture, stage/CONTENT/'Textures'/(NEW_TEXTURE+'.uasset'),
                                  {TEXTURE: NEW_TEXTURE}, args.output/'rename-texture', gui))
    validation = validate_inverse(args.stock/CONTENT/'Textures'/(TEXTURE+'.uexp'),
                                  args.baseline/CONTENT/'Textures'/(TEXTURE+'.uexp'),
                                  stage/CONTENT/'Textures'/(NEW_TEXTURE+'.uexp'))
    preserved = 0
    for path in args.baseline.rglob('*'):
        if path.is_file():
            assert path.read_bytes() == (stage/path.relative_to(args.baseline)).read_bytes()
            preserved += 1
    assert preserved == 19
    report = {'shaders': shader_report, 'renamed_packages': renamed, 'phase_validation': validation,
              'baseline_files_byte_identical': preserved, 'pak_files': len(list(stage.rglob('*.*'))),
              'nro_modified': False, 'shader_bytecode_modified': False,
              'high_materials_modified': False, 'device_tested': False}
    (args.output/'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

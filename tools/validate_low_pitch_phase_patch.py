"""Validate a built or unpacked Low-phase patch against owned source assets."""
import argparse
import json
from pathlib import Path

from build_low_pitch_phase_patch import (CONTENT, PARENT, NEW_PARENT, TEXTURE,
                                        NEW_TEXTURE, RIGHT_MATERIALS, name_entries,
                                        audit_shaders, validate_inverse)


def check_header(source, target, changes):
    a, b = source.read_bytes(), target.read_bytes()
    assert len(a) == len(b)
    ae, be = name_entries(a), name_entries(b)
    assert len(ae) == len(be)
    scratch = bytearray(a)
    edited = set()
    for (an, start, end), (bn, bs, bend) in zip(ae, be):
        assert (start, end) == (bs, bend)
        assert bn == changes.get(an, an)
        if an in changes:
            scratch[start:end] = b[start:end]
            edited.add(an)
    assert edited == set(changes)
    assert bytes(scratch) == b


def validate(stock, materials, baseline, built):
    names = {p.relative_to(baseline) for p in baseline.rglob('*') if p.is_file()}
    assert len(names) == 19
    for name in names:
        assert (baseline/name).read_bytes() == (built/name).read_bytes()
    mp = '/Game/Assets/bg_lighting_AM1/Materials/'
    tp = '/Game/Assets/bg_lighting_AM1/Textures/'
    pairs = [(PARENT, NEW_PARENT, {PARENT:NEW_PARENT, mp+PARENT:mp+NEW_PARENT,
                                  TEXTURE:NEW_TEXTURE, tp+TEXTURE:tp+NEW_TEXTURE})]
    for name in RIGHT_MATERIALS:
        pairs.append((name, name, {PARENT:NEW_PARENT, mp+PARENT:mp+NEW_PARENT,
                                  TEXTURE:NEW_TEXTURE}))
    for old_name, new_name, changes in pairs:
        source = materials/CONTENT/'Materials'/old_name
        target = built/CONTENT/'Materials'/new_name
        check_header(source.with_suffix('.uasset'), target.with_suffix('.uasset'), changes)
        assert source.with_suffix('.uexp').read_bytes() == target.with_suffix('.uexp').read_bytes()
        audit_shaders(target.with_suffix('.uexp'), old_name in RIGHT_MATERIALS)
        names.update((target.with_suffix(s).relative_to(built) for s in ('.uasset','.uexp')))
    texture = built/CONTENT/'Textures'/NEW_TEXTURE
    check_header((baseline/CONTENT/'Textures'/TEXTURE).with_suffix('.uasset'),
                 texture.with_suffix('.uasset'), {TEXTURE:NEW_TEXTURE})
    names.update((texture.with_suffix(s).relative_to(built) for s in ('.uasset','.uexp')))
    assert names == {p.relative_to(built) for p in built.rglob('*') if p.is_file()}
    assert len(names) == 27
    phase = validate_inverse(stock/CONTENT/'Textures'/(TEXTURE+'.uexp'),
                             baseline/CONTENT/'Textures'/(TEXTURE+'.uexp'),
                             texture.with_suffix('.uexp'))
    return {'pak_files':27, 'baseline_files_byte_identical':19,
            'material_exports_and_shaders_byte_identical':3,
            'header_changes_limited_to_checked_name_table_entries':True,
            'unexpected_files':0, 'inverse_diffuse':phase, 'device_tested':False}


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--built',type=Path,required=True)
    p.add_argument('--stock',type=Path,default=Path('local-debug/pitch-audit-20260826/base'))
    p.add_argument('--materials',type=Path,default=Path('local-debug/pitch-material-audit-20260831'))
    p.add_argument('--baseline',type=Path,default=Path('local-debug/visual-v7-20260831/pitch-build/pitch-stage'))
    p.add_argument('--report',type=Path)
    a=p.parse_args()
    result=validate(a.stock,a.materials,a.baseline,a.built)
    rendered=json.dumps(result,indent=2)
    if a.report:
        a.report.write_text(rendered+'\n',encoding='utf-8')
    print(rendered)

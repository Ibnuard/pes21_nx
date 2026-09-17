"""Recreate the full custom Low/standard pitch package from owned native assets."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from build_efootball10_visual_patch import pitch
from build_low_pitch_phase_patch import (
    CONTENT, PARENT, NEW_PARENT, TEXTURE, NEW_TEXTURE, RIGHT_MATERIALS,
    audit_shaders, rename_package,
)
from build_uniform_pitch_patch import validate as validate_geometry


def build(native, output, encoder, gui):
    if output.exists():
        raise ValueError('Use a fresh output directory')
    output.mkdir(parents=True)
    previews = output / 'previews'
    previews.mkdir()
    settings = SimpleNamespace(pes21=native, ef10=None, etc1tool=encoder,
                               pitch_style='clean-v17', procedural_grain=True)
    textures = pitch(settings, output, previews)
    stage = output / 'pitch-stage'
    assert len(list(stage.rglob('*.*'))) == 19
    materials = native / CONTENT / 'Materials'
    audits = {PARENT: audit_shaders(materials / (PARENT+'.uexp'), False)}
    for name in RIGHT_MATERIALS:
        audits[name] = audit_shaders(materials / (name+'.uexp'), True)
    inverse = output / 'inverse'
    inverse_previews = inverse / 'previews'
    inverse_previews.mkdir(parents=True)
    pitch(settings, inverse, inverse_previews, selected_names=(TEXTURE,),
          complement_diffuse=True)
    old_parent = '/Game/Assets/bg_lighting_AM1/Materials/' + PARENT
    new_parent = '/Game/Assets/bg_lighting_AM1/Materials/' + NEW_PARENT
    old_texture = '/Game/Assets/bg_lighting_AM1/Textures/' + TEXTURE
    new_texture = '/Game/Assets/bg_lighting_AM1/Textures/' + NEW_TEXTURE
    renames = [rename_package(materials/(PARENT+'.uasset'),
        stage/CONTENT/'Materials'/(NEW_PARENT+'.uasset'),
        {PARENT:NEW_PARENT, old_parent:new_parent, TEXTURE:NEW_TEXTURE,
         old_texture:new_texture}, output/'rename-parent', gui)]
    for name in RIGHT_MATERIALS:
        renames.append(rename_package(materials/(name+'.uasset'),
            stage/CONTENT/'Materials'/(name+'.uasset'),
            {PARENT:NEW_PARENT, old_parent:new_parent, TEXTURE:NEW_TEXTURE},
            output/('rename-'+name), gui))
    renames.append(rename_package(
        inverse/'pitch-stage'/CONTENT/'Textures'/(TEXTURE+'.uasset'),
        stage/CONTENT/'Textures'/(NEW_TEXTURE+'.uasset'),
        {TEXTURE:NEW_TEXTURE}, output/'rename-texture', gui))
    assert len(list(stage.rglob('*.*'))) == 27
    geometry = validate_geometry(stage, stage, native, 'clean-v17')
    report = {'files':27, 'recipe':'clean-v17', 'grain':'seeded procedural, not EF10',
              'textures':textures, 'shader_audits':audits, 'renames':renames,
              'encoded_geometry': {key: value for key, value in geometry.items()
                                   if 'identical' not in key and key != 'unchanged_files'},
              'hardware_validated':False}
    (output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('native', 'output', 'encoder', 'gui'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    build(args.native, args.output, args.encoder.resolve(), args.gui.resolve())
    print('Recreated and validated 27-member custom pitch stage')

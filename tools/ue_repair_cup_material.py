"""Repair ONLY the Cup material in a caller-owned isolated UE4.22 project.

Run from an ignored copy of the audited prop Content, never an active project.
PESNX_CUP_MATERIAL_TOOLS and PESNX_CUP_MATERIAL_REPORT are required.
"""
import json
import os
import sys
sys.path.insert(0, os.environ['PESNX_CUP_MATERIAL_TOOLS'])
from cinematic_cup_material import (CUP_METAL_CODE, MATERIAL_PATH,
                                    TEXTURE_PATH, material_contract,
                                    require_isolated_project)
import unreal


def main():
    if not unreal.SystemLibrary.get_engine_version().startswith('4.22.'):
        raise RuntimeError('Only the audited UE4.22 project is supported')
    require_isolated_project(unreal.Paths.project_dir(),
                             os.environ['PESNX_CUP_MATERIAL_PROJECT'],
                             os.environ['PESNX_CUP_MATERIAL_REPOSITORY'])
    material = unreal.load_asset(MATERIAL_PATH)
    texture = unreal.load_asset(TEXTURE_PATH)
    if material is None or texture is None:
        raise RuntimeError('The two audited Cup assets must already exist')
    lib = unreal.MaterialEditingLibrary
    lib.delete_all_material_expressions(material)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
    material.set_editor_property('two_sided', False)
    colour = lib.create_material_expression(material, unreal.MaterialExpressionTextureSample)
    colour.set_editor_property('texture', texture)
    colour.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    normal = lib.create_material_expression(material, unreal.MaterialExpressionPixelNormalWS)
    view = lib.create_material_expression(material, unreal.MaterialExpressionCameraVectorWS)
    metal = lib.create_material_expression(material, unreal.MaterialExpressionCustom)
    metal.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    inputs = []
    for name in ('Base', 'Normal', 'View'):
        item = unreal.CustomInput()
        item.set_editor_property('input_name', name)
        inputs.append(item)
    metal.set_editor_property('inputs', inputs)
    metal.set_editor_property('code', CUP_METAL_CODE)
    for node, pin, target in ((colour, 'RGB', 'Base'), (normal, '', 'Normal'),
                              (view, '', 'View')):
        if not lib.connect_material_expressions(node, pin, metal, target):
            raise RuntimeError('Missing Cup material input: ' + target)
    if not lib.connect_material_property(metal, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR):
        raise RuntimeError('Missing Cup material output')
    lib.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_asset(MATERIAL_PATH):
        raise RuntimeError('Cup material save failed')
    report = material_contract()
    report.update(status='material_saved', material=MATERIAL_PATH,
                  scene_playback_verified=False, hardware_tested=False)
    with open(os.environ['PESNX_CUP_MATERIAL_REPORT'], 'w') as stream:
        json.dump(report, stream, indent=2)
    unreal.log('PESNX_CUP_MATERIAL_V88_OK')


if __name__ == '__main__':
    main()

"""Prepare a new per-player face/hair candidate in an isolated UE4.22 project.

PESNX_REALFACE_IMPORT_PROFILE specifies explicit mesh/texture inputs and slot
policies. Shared skeleton/materials are pre-existing cook dependencies only.
The native face material must resolve from the original runtime PAK; its
editor placeholder is deliberately excluded from the package allowlist.
Compatible with the editor's bundled Python.
"""
import json
import os
import unreal

with open(os.environ['PESNX_REALFACE_IMPORT_PROFILE'],'r') as stream:
    profile=json.load(stream)
player=str(int(profile['native_player_id']))
destination='/Game/Assets/character/RealFace'
base='/Game/Assets/character/BaseAssets'
skeleton=unreal.load_asset(base+'/test_body_Skeleton')
parent=unreal.load_asset(base+'/M_RealFaceBase')
hair_material=unreal.load_asset(base+'/hair_parts_tablet_ss')
if skeleton is None or parent is None or hair_material is None:
    raise RuntimeError('Audited native skeleton/material dependencies are missing')
assets=unreal.AssetToolsHelpers.get_asset_tools()


def absent(path):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        raise RuntimeError('Refusing existing player asset: '+path)


def texture(source,name,alpha):
    path=destination+'/'+name
    absent(path)
    task=unreal.AssetImportTask()
    for key,value in {'filename':source,'destination_path':destination,'destination_name':name,
                      'automated':True,'save':True,'replace_existing':False}.items():
        task.set_editor_property(key,value)
    assets.import_asset_tasks([task])
    result=unreal.load_asset(path)
    if result is None:raise RuntimeError('Texture import failed: '+path)
    result.set_editor_property('max_texture_size',128)
    result.set_editor_property('lod_bias',0)
    result.set_editor_property('srgb',True)
    result.set_editor_property('compression_no_alpha',not alpha)
    if alpha:
        result.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
    unreal.EditorAssetLibrary.save_asset(path)
    return result


face_texture=texture(profile['face_texture'],player+'_face_tablet',False)
texture(profile['hair_texture'],player+'_hair_parts_color_tablet',True)
eye_texture=texture(profile['native_eye_texture'],player+'_eyes_tablet',False)


def instance(name,source):
    absent(destination+'/'+name)
    result=assets.create_asset(name,destination,unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
    if result is None:raise RuntimeError('Material creation failed: '+name)
    result.set_editor_property('parent',parent)
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(result,'Base Texture',source)
    unreal.EditorAssetLibrary.save_asset(result.get_path_name())
    return result


skin=instance('face_'+player,face_texture)
eye=instance('eye_native_'+player,eye_texture)
report={'player':int(player),'parts':{},'native_face_material_packaged':False}
for part in ('face','hair'):
    name=player+'_'+part
    path=destination+'/'+name
    absent(path)
    options=unreal.FbxImportUI()
    for key,value in {'import_as_skeletal':True,'import_mesh':True,'import_animations':False,
                      'create_physics_asset':False,'import_materials':False,'import_textures':False,
                      'skeleton':skeleton}.items():
        options.set_editor_property(key,value)
    options.get_editor_property('skeletal_mesh_import_data').set_editor_property(
        'normal_import_method',unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    task=unreal.AssetImportTask()
    for key,value in {'filename':profile[part+'_fbx'],'destination_path':destination,
                      'destination_name':name,'automated':True,'save':True,
                      'replace_existing':False,'options':options}.items():
        task.set_editor_property(key,value)
    assets.import_asset_tasks([task])
    mesh=unreal.load_asset(path)
    if mesh is None:raise RuntimeError('Mesh import failed: '+part)
    slots=list(mesh.get_editor_property('materials'))
    assigned={}
    for slot in slots:
        original=str(slot.get_editor_property('imported_material_slot_name'))
        if part=='hair' and original in profile['hair_materials']:
            material=hair_material
        elif part=='face' and original==profile['eye_material']:
            material=eye
        elif part=='face' and original in profile['skin_materials']:
            material=skin
        else:
            raise RuntimeError('Unclassified material slot: '+part+'/'+original)
        assigned[original]=material.get_path_name()
        slot.set_editor_property('material_interface',material)
    if part=='face' and sum(str(s.get_editor_property('imported_material_slot_name'))==profile['eye_material'] for s in slots)!=1:
        raise RuntimeError('Expected one dedicated native eye slot')
    mesh.set_editor_property('materials',slots)
    unreal.EditorAssetLibrary.save_asset(path)
    report['parts'][part]=assigned
report['status']='imported'
with open(profile['report'],'w') as stream:
    json.dump(report,stream,indent=2)
unreal.log('PESNX_REALFACE_PREPARE_OK '+player)

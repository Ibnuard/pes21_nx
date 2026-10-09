"""UE4.22 editor-side face import, configured by PESNX_REALFACE_IMPORT_PROFILE.

Run only in the disposable conversion project. Its shared skeleton/materials
are import dependencies and must never be included in the detached output PAK.
Keep this file compatible with the editor's bundled Python version.
"""
import json
import os
import unreal

with open(os.environ['PESNX_REALFACE_IMPORT_PROFILE'], 'r') as stream:
    profile = json.load(stream)
destination = '/Game/Assets/character/RealFace'
player_id = str(int(profile['native_player_id']))
skeleton = unreal.load_asset('/Game/Assets/character/BaseAssets/test_body_Skeleton')
skin = unreal.load_asset(destination + '/face_' + player_id)
eye = unreal.load_asset(destination + '/eye_native_' + player_id)
if skeleton is None or skin is None or eye is None:
    raise RuntimeError('Missing audited native skeleton/skin/eye import dependency')
asset_path = destination + '/' + player_id + '_face'
if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
    if not unreal.EditorAssetLibrary.delete_asset(asset_path):
        raise RuntimeError('Could not replace face in the disposable cook project')
options = unreal.FbxImportUI()
for key, value in {'import_as_skeletal': True, 'import_mesh': True,
                   'import_animations': False, 'create_physics_asset': False,
                   'import_materials': False, 'import_textures': False,
                   'skeleton': skeleton}.items():
    options.set_editor_property(key, value)
options.get_editor_property('skeletal_mesh_import_data').set_editor_property(
    'normal_import_method', unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
task = unreal.AssetImportTask()
for key, value in {'filename': profile['fbx'], 'destination_path': destination,
                   'destination_name': player_id + '_face', 'automated': True,
                   'save': True, 'replace_existing': True, 'options': options}.items():
    task.set_editor_property(key, value)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
mesh = unreal.load_asset(asset_path)
if mesh is None:
    raise RuntimeError('Imported face asset is missing')
slots = list(mesh.get_editor_property('materials'))
eye_count = 0
for slot in slots:
    name = str(slot.get_editor_property('imported_material_slot_name'))
    is_eye = name == profile['eye_material']
    eye_count += int(is_eye)
    slot.set_editor_property('material_interface', eye if is_eye else skin)
if eye_count != 1:
    raise RuntimeError('Expected one eye material slot')
mesh.set_editor_property('materials', slots)
unreal.EditorAssetLibrary.save_asset(asset_path)
unreal.log('PESNX_REALFACE_IMPORT_OK ' + player_id)

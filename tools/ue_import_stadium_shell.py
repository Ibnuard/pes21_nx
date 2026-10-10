"""UE4.22 editor stage for the optional, locally converted Anfield shell.

PESNX_STADIUM_PROFILE points to fbx.local.json from stadium_shell_fbx.py.
Only /Game/FootballNX/Stadiums/Anfield is packaged; no engine assets replaced.
"""
import json
import os
import unreal

profile_path = os.environ['PESNX_STADIUM_PROFILE']
with open(profile_path, 'r') as stream:
    profile = json.load(stream)
work = os.path.dirname(profile_path)
destination = '/Game/FootballNX/Stadiums/Anfield'
assets = unreal.AssetToolsHelpers.get_asset_tools()
lib = unreal.MaterialEditingLibrary
materials = {}
resume = os.environ.get('PESNX_STADIUM_RESUME') == '1'


def expression(material, kind):
    return lib.create_material_expression(material, kind)


def connect(a, output, b, input_name):
    if not lib.connect_material_expressions(a, output, b, input_name):
        raise RuntimeError('Material connection failed: ' + input_name)


for name in profile['material_slots']:
    material = unreal.load_asset(destination + '/' + name) if resume else None
    if material is not None:
        lib.delete_all_material_expressions(material)
    else:
        material = assets.create_asset(name, destination, unreal.Material, unreal.MaterialFactoryNew())
    if material is None:
        raise RuntimeError('Use a fresh conversion project: ' + name)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property('two_sided', True)
    texture_path = os.path.join(profile.get('texture_root', os.path.join(work, 'textures')), name[2:] + '.png')
    if os.path.isfile(texture_path):
        task = unreal.AssetImportTask()
        for k, v in {'filename': texture_path, 'destination_path': destination,
                      'destination_name': 'T_' + name[2:], 'automated': True,
                      'save': True, 'replace_existing': False}.items():
            task.set_editor_property(k, v)
        texture = unreal.load_asset(destination + '/T_' + name[2:]) if resume else None
        if texture is None:
            assets.import_asset_tasks([task])
            texture = unreal.load_asset(destination + '/T_' + name[2:])
        texture.set_editor_property('max_texture_size',
            profile.get('textures', {}).get(name[2:], {}).get('max_texture_size', 512))
        texture.set_editor_property('srgb', True)
        alpha = profile.get('textures', {}).get(name[2:], {}).get('alpha_range', [255, 255])[0] < 128
        texture.set_editor_property('compression_no_alpha', not alpha)
        if alpha:
            texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
            material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
            material.set_editor_property('opacity_mask_clip_value', 0.4)
        color = expression(material, unreal.MaterialExpressionTextureSample)
        color.set_editor_property('texture', texture)
        if name == 'M_crowd_seated':
            # Animate the existing atlas without extra geometry, textures or
            # draw calls. Different seated people sway/bob out of phase; UV.y=1
            # is the feet after FBX's V flip, so the bottom edge stays pinned.
            uv = expression(material, unreal.MaterialExpressionTextureCoordinate)
            time = expression(material, unreal.MaterialExpressionTime)
            # Keep mobile mediump time precise in long sessions. Both rates
            # complete an integer number of cycles across this ten-second wrap.
            time.set_editor_property('override_period', True)
            time.set_editor_property('period', 10.0)
            motion = expression(material, unreal.MaterialExpressionCustom)
            motion.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT2)
            motion.set_editor_property('description', 'FootballNX seated crowd motion')
            inputs = []
            for input_name in ('UV', 'Clock'):
                item = unreal.CustomInput()
                item.set_editor_property('input_name', input_name)
                inputs.append(item)
            motion.set_editor_property('inputs', inputs)
            motion.set_editor_property('code', '''
float upper = 1.0 - saturate(UV.y);
float phase = floor(UV.x * 32.0) * 2.399963;
float sway = sin(Clock * 3.7699111843 + phase) * 0.0025 * upper * upper;
float bob = sin(Clock * 4.3982297150 + phase * 1.3) * 0.009 * upper;
return float2(UV.x + sway, saturate(UV.y + bob));
''')
            connect(uv, '', motion, 'UV')
            connect(time, '', motion, 'Clock')
            connect(motion, '', color, '')  # Texture sample's first input: UVs.
        if alpha:
            if not lib.connect_material_property(color, 'A', unreal.MaterialProperty.MP_OPACITY_MASK):
                raise RuntimeError('Opacity output connection failed: ' + name)
        unreal.EditorAssetLibrary.save_asset(texture.get_path_name())
        color_pin = 'RGB'
    else:
        color = expression(material, unreal.MaterialExpressionConstant3Vector)
        color.set_editor_property('constant', unreal.LinearColor(0.32, 0.32, 0.30, 1))
        color_pin = ''
    # Authored constant hemisphere shading: keeps PC shell readable with no
    # additional shadow map, reflection capture, or dynamic light count.
    normal = expression(material, unreal.MaterialExpressionVertexNormalWS)
    sun = expression(material, unreal.MaterialExpressionConstant3Vector)
    sun.set_editor_property('constant', unreal.LinearColor(0.25, 0.35, 0.90, 1))
    dot = expression(material, unreal.MaterialExpressionDotProduct)
    connect(normal, '', dot, 'A')
    connect(sun, '', dot, 'B')
    clamp = expression(material, unreal.MaterialExpressionClamp)
    connect(dot, '', clamp, '')
    shade = expression(material, unreal.MaterialExpressionMultiply)
    shade.set_editor_property('const_b', 0.30)
    connect(clamp, '', shade, 'A')
    ambient = expression(material, unreal.MaterialExpressionAdd)
    ambient.set_editor_property('const_b', 0.65)
    connect(shade, '', ambient, 'A')
    result = expression(material, unreal.MaterialExpressionMultiply)
    connect(color, color_pin, result, 'A')
    connect(ambient, '', result, 'B')
    if not lib.connect_material_property(result, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR):
        raise RuntimeError('Color output connection failed: ' + name)
    lib.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(material.get_path_name())
    materials[name] = material

options = unreal.FbxImportUI()
for k, v in {'import_as_skeletal': False, 'import_mesh': True,
              'import_materials': False, 'import_textures': False,
              'import_animations': False}.items():
    options.set_editor_property(k, v)
mesh_options = options.get_editor_property('static_mesh_import_data')
mesh_options.set_editor_property('combine_meshes', True)
mesh_options.set_editor_property('auto_generate_collision', False)
mesh_options.set_editor_property('generate_lightmap_u_vs', False)
mesh_options.set_editor_property('normal_import_method', unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
task = unreal.AssetImportTask()
for k, v in {'filename': profile['fbx'], 'destination_path': destination,
              'destination_name': 'AnfieldShell', 'automated': True,
              'save': True, 'replace_existing': resume, 'options': options}.items():
    task.set_editor_property(k, v)
mesh = unreal.load_asset(destination + '/AnfieldShell') if resume else None
if mesh is None or os.environ.get('PESNX_STADIUM_REIMPORT') == '1':
    assets.import_asset_tasks([task])
    mesh = unreal.load_asset(destination + '/AnfieldShell')
if mesh is None:
    raise RuntimeError('Stadium mesh import failed')
slots = {}
for name in profile['material_slots']:
    index = mesh.get_material_index(name)
    if index < 0:
        raise RuntimeError('Missing imported slot: ' + name)
    mesh.set_material(index, materials[name])
    slots[name] = index
if len(set(slots.values())) != len(materials):
    raise RuntimeError('Duplicate FBX material indices')
unreal.EditorAssetLibrary.save_asset(mesh.get_path_name())
bounds = mesh.get_bounds()
extent = bounds.box_extent
origin = bounds.origin
report = {'mesh': mesh.get_path_name(), 'materials': len(slots),
          'crowd_animation': 'GPU atlas sway/bob, feet pinned, no additional draws',
          'extent_cm': [extent.x, extent.y, extent.z],
          'origin_cm': [origin.x, origin.y, origin.z]}
if not (10000 < extent.x < 20000 and 7000 < extent.y < 11000 and 1700 < extent.z < 2500):
    raise RuntimeError('Unexpected imported centimetre scale or axes: ' + str(report))
with open(os.path.join(work, 'ue-import.local.json'), 'w') as stream:
    json.dump(report, stream, indent=2)
unreal.log('PESNX_ANFIELD_IMPORT_OK ' + str(report))

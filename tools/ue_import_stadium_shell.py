"""UE4.22 editor stage for optional, locally converted stadium shells.

PESNX_STADIUM_PROFILE points to fbx.local.json from stadium_shell_fbx.py.
Each profile has its own /Game/FootballNX/Stadiums/<key> namespace.
"""
import json
import hashlib
import os
import unreal
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stadium_material_policy import CROWD_UV, CROWD_PERIOD, CAMERA_MASK, CAMERA_CULL, ATLAS_UV
from stadium_assets import asset_key

profile_path = os.environ['PESNX_STADIUM_PROFILE']
with open(profile_path, 'r') as stream:
    profile = json.load(stream)
work = os.path.dirname(profile_path)
key = asset_key(profile.get('key', 'Anfield'))
mesh_name = key + 'Shell'
destination = '/Game/FootballNX/Stadiums/' + key
assets = unreal.AssetToolsHelpers.get_asset_tools()
lib = unreal.MaterialEditingLibrary
materials = {}
resume = os.environ.get('PESNX_STADIUM_RESUME') == '1'
reuse_materials = os.environ.get('PESNX_STADIUM_REUSE_MATERIALS') == '1'
if reuse_materials and (not resume or not profile.get('apron_repair')):
    raise RuntimeError('Material reuse is only for an existing, verified apron-repair project')


def expression(material, kind):
    return lib.create_material_expression(material, kind)


def connect(a, output, b, input_name):
    if not lib.connect_material_expressions(a, output, b, input_name):
        raise RuntimeError('Material connection failed: ' + input_name)


def custom(material, code, description, inputs, output_type):
    node = expression(material, unreal.MaterialExpressionCustom)
    node.set_editor_property('output_type', output_type)
    node.set_editor_property('description', description)
    fields = []
    for name, source in inputs:
        field = unreal.CustomInput()
        field.set_editor_property('input_name', name)
        fields.append(field)
    node.set_editor_property('inputs', fields)
    node.set_editor_property('code', code)
    for name, source in inputs:
        connect(source, '', node, name)
    return node


def vertex_camera_cull(material, world, camera):
    xy = expression(material, unreal.MaterialExpressionTextureCoordinate)
    xy.set_editor_property('coordinate_index', 2)
    ze = expression(material, unreal.MaterialExpressionTextureCoordinate)
    ze.set_editor_property('coordinate_index', 3)
    yz = expression(material, unreal.MaterialExpressionTextureCoordinate)
    yz.set_editor_property('coordinate_index', 4)
    position = custom(material, 'return float3(XY, ZE.x) * 32768.0;', 'Local cluster centre',
                      [('XY', xy), ('ZE', ze)], unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    half_size = custom(material, 'return float3(ZE.y, YZ) * 32768.0;', 'Local cluster half extent',
                       [('ZE', ze), ('YZ', yz)], unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    transform = expression(material, unreal.MaterialExpressionTransformPosition)
    transform.set_editor_property('transform_source_type', unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
    transform.set_editor_property('transform_type', unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD)
    connect(position, '', transform, '')
    # Transform the three local axes separately. Sum their absolute vectors
    # to enclose arbitrary component rotation and nonuniform scale in a world
    # AABB, rather than assuming the imported actor has an identity transform.
    axes = []
    for axis in ('x', 'y', 'z'):
        code = 'return float3(%s);' % ','.join('Size.'+axis if a == axis else '0.0' for a in ('x', 'y', 'z'))
        local_axis = custom(material, code, 'Local extent '+axis, [('Size', half_size)], unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        vector = expression(material, unreal.MaterialExpressionTransform)
        vector.set_editor_property('transform_source_type', unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL)
        vector.set_editor_property('transform_type', unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
        connect(local_axis, '', vector, '')
        axes.append(vector)
    world_size = custom(material, 'return abs(X) + abs(Y) + abs(Z);', 'Conservative world half extent',
                        list(zip(('X', 'Y', 'Z'), axes)), unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    cull = custom(material, CAMERA_CULL, 'Conservative camera rejection before rasterization',
                  [('HalfSize', world_size), ('Centre', transform), ('Camera', camera), ('World', world)],
                  unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    # ES2 allows only three UV sets. Compile out bounds and WPO there; the
    # existing pixel cutaway remains fully functional on the legacy path.
    zero = expression(material, unreal.MaterialExpressionConstant3Vector)
    zero.set_editor_property('constant', unreal.LinearColor(0, 0, 0, 0))
    selected = expression(material, unreal.MaterialExpressionFeatureLevelSwitch)
    connect(zero, '', selected, 'Default')
    connect(cull, '', selected, 'ES3_1')
    connect(cull, '', selected, 'SM5')
    # UE4.22 hides the WPO enum and protects its Python struct. The editor's
    # built-in SET command uses the reflected property importer instead. Target
    # this exact asset (never a class default). Cooked vertex maps are audited
    # for the bound decoding/culling code, so a failed connection cannot ship.
    command = "SET %s WorldPositionOffset (Expression=MaterialExpressionFeatureLevelSwitch'%s',OutputIndex=0)" % (material.get_path_name(), selected.get_path_name())
    unreal.SystemLibrary.execute_console_command(unreal.EditorLevelLibrary.get_editor_world(), command)


def texture_asset(path, name, maximum, linear=False, alpha=False):
    asset_path = destination + '/' + name
    texture = unreal.load_asset(asset_path) if resume and unreal.EditorAssetLibrary.does_asset_exist(asset_path) else None
    with open(path, 'rb') as source:
        source_hash = hashlib.sha256(source.read()).hexdigest()
    imported_hash = unreal.EditorAssetLibrary.get_metadata_tag(texture, 'PESNX.SourceSHA256') if texture else ''
    # A mesh/shader rebuild must not invalidate unchanged texture compression.
    # A changed or untracked source still imports, even in a reused project.
    if texture is None or imported_hash != source_hash:
        task = unreal.AssetImportTask()
        for k, v in {'filename': path, 'destination_path': destination,
                     'destination_name': name, 'automated': True, 'save': True,
                     'replace_existing': True}.items():
            task.set_editor_property(k, v)
        assets.import_asset_tasks([task])
        texture = unreal.load_asset(destination + '/' + name)
    if texture is None:
        raise RuntimeError('Texture import failed: ' + path)
    texture.set_editor_property('max_texture_size', maximum)
    texture.set_editor_property('srgb', not linear)
    texture.set_editor_property('compression_no_alpha', not alpha)
    texture.set_editor_property('compression_settings',
        unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP if alpha else
        unreal.TextureCompressionSettings.TC_DEFAULT)
    unreal.EditorAssetLibrary.set_metadata_tag(texture, 'PESNX.SourceSHA256', source_hash)
    unreal.EditorAssetLibrary.save_asset(texture.get_path_name())
    return texture


def atlas_gradients(material, uv):
    # Derive from continuous source UVs, before frac(). Otherwise a repeated
    # seam selects the coarsest mip and can flash the neighbouring atlas tile.
    scale = expression(material, unreal.MaterialExpressionMultiply)
    scale.set_editor_property('const_b', 240.0 / 1024.0)
    connect(uv, '', scale, 'A')
    dx = expression(material, unreal.MaterialExpressionDDX)
    dy = expression(material, unreal.MaterialExpressionDDY)
    connect(scale, '', dx, '')
    connect(scale, '', dy, '')
    return dx, dy


def sample_gradients(material, sample, uv, gradients, mask=False):
    sample.set_editor_property('mip_value_mode', unreal.TextureMipValueMode.TMVM_DERIVATIVE)
    connect(gradients[0], '', sample, 'DDX(UVs)')
    connect(gradients[1], '', sample, 'DDY(UVs)')
    # Explicit gradients are supported by the native ES3.1 path. UE4.22's
    # ES2 backend emits an unsupported texture2DGrad symbol; give that legacy
    # path a normal sampled material, selected at compile time (one sample).
    automatic = expression(material, unreal.MaterialExpressionTextureSample)
    automatic.set_editor_property('texture', sample.get_editor_property('texture'))
    automatic.set_editor_property('sampler_type', sample.get_editor_property('sampler_type'))
    connect(uv, '', automatic, '')
    selected = expression(material, unreal.MaterialExpressionFeatureLevelSwitch)
    connect(automatic, 'RGB', selected, 'Default')
    connect(sample, 'RGB', selected, 'ES3_1')
    connect(sample, 'RGB', selected, 'SM5')
    channels = expression(material, unreal.MaterialExpressionComponentMask)
    for channel, value in (('r', True), ('g', not mask), ('b', not mask), ('a', False)):
        channels.set_editor_property(channel, value)
    connect(selected, '', channels, '')
    return channels


for name in profile['material_slots']:
    asset_path = destination + '/' + name
    material = unreal.load_asset(asset_path) if resume and unreal.EditorAssetLibrary.does_asset_exist(asset_path) else None
    if reuse_materials:
        if material is None:
            raise RuntimeError('Previously verified material missing: '+asset_path)
        materials[name] = material
        continue
    if material is not None:
        lib.delete_all_material_expressions(material)
    else:
        material = assets.create_asset(name, destination, unreal.Material, unreal.MaterialFactoryNew())
    if material is None:
        raise RuntimeError('Use a fresh conversion project: ' + name)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property('two_sided', profile.get('material_policies', {}).get(name, {}).get('two_sided', True))
    alpha_node, alpha_pin = None, ''
    texture_path = profile.get('texture_files', {}).get(name) or os.path.join(profile.get('texture_root', os.path.join(work, 'textures')), name[2:] + '.png')
    if os.path.isfile(texture_path):
        animated_crowd = name == 'M_crowd_seated' and profile.get('crowd_flipbook', False)
        texture_name = 'T_crowd_flipbook_v16' if animated_crowd else 'T_' + name[2:]
        maximum = profile.get('textures', {}).get(name[2:], {}).get('max_texture_size', 512)
        alpha = profile.get('textures', {}).get(name[2:], {}).get('alpha_range', [255, 255])[0] < 128
        texture = texture_asset(texture_path, texture_name, maximum, alpha=alpha)
        if alpha:
            material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
            material.set_editor_property('opacity_mask_clip_value', 0.4)
        color = expression(material, unreal.MaterialExpressionTextureSample)
        color.set_editor_property('texture', texture)
        color_pin = 'RGB'
        uv_result = None
        gradients = None
        if animated_crowd:
            uv = expression(material, unreal.MaterialExpressionTextureCoordinate)
            time = expression(material, unreal.MaterialExpressionTime)
            time.set_editor_property('override_period', True)
            time.set_editor_property('period', CROWD_PERIOD)
            motion = expression(material, unreal.MaterialExpressionCustom)
            motion.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT2)
            motion.set_editor_property('description', 'Native sixteen-frame crowd atlas')
            inputs = []
            for input_name in ('UV', 'Clock'):
                item = unreal.CustomInput()
                item.set_editor_property('input_name', input_name)
                inputs.append(item)
            motion.set_editor_property('inputs', inputs)
            motion.set_editor_property('code', CROWD_UV)
            connect(uv, '', motion, 'UV')
            connect(time, '', motion, 'Clock')
            connect(motion, '', color, '')
            uv_result = motion
        elif name in profile.get('atlas', {}).get('materials', []):
            uv = expression(material, unreal.MaterialExpressionTextureCoordinate)
            tile = expression(material, unreal.MaterialExpressionTextureCoordinate)
            tile.set_editor_property('coordinate_index', 1)
            mapped = expression(material, unreal.MaterialExpressionCustom)
            mapped.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT2)
            mapped.set_editor_property('description', 'Repeated source UV into bounded atlas tile')
            inputs = []
            for input_name in ('UV', 'Tile'):
                item = unreal.CustomInput()
                item.set_editor_property('input_name', input_name)
                inputs.append(item)
            mapped.set_editor_property('inputs', inputs)
            mapped.set_editor_property('code', ATLAS_UV)
            connect(uv, '', mapped, 'UV')
            connect(tile, '', mapped, 'Tile')
            connect(mapped, '', color, '')
            uv_result = mapped
            gradients = atlas_gradients(material, uv)
            color = sample_gradients(material, color, mapped, gradients)
            color_pin = ''
        if alpha:
            alpha_node, alpha_pin = color, 'A'
        mask_file = profile.get('mask_files', {}).get(name)
        if mask_file:
            mask_texture = texture_asset(mask_file, 'T_' + name[2:] + '_mask', maximum, linear=True)
            alpha_node = expression(material, unreal.MaterialExpressionTextureSample)
            alpha_node.set_editor_property('texture', mask_texture)
            alpha_node.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
            if uv_result is not None:
                connect(uv_result, '', alpha_node, '')
            alpha_pin = 'R'
            if gradients is not None:
                alpha_node = sample_gradients(material, alpha_node, uv_result, gradients, mask=True)
                alpha_pin = ''
            material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
            material.set_editor_property('opacity_mask_clip_value', 0.4)
        if alpha_node is not None:
            if not lib.connect_material_property(alpha_node, alpha_pin, unreal.MaterialProperty.MP_OPACITY_MASK):
                raise RuntimeError('Opacity output connection failed: ' + name)
        unreal.EditorAssetLibrary.save_asset(texture.get_path_name())
    else:
        color = expression(material, unreal.MaterialExpressionConstant3Vector)
        color.set_editor_property('constant', unreal.LinearColor(0.32, 0.32, 0.30, 1))
        color_pin = ''
    if profile.get('close_camera_cutaway', False):
        material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
        material.set_editor_property('opacity_mask_clip_value', 0.4)
        camera = expression(material, unreal.MaterialExpressionCameraPositionWS)
        world = expression(material, unreal.MaterialExpressionWorldPosition)
        if profile.get('vertex_camera_cull'):
            vertex_camera_cull(material, world, camera)
        mask = expression(material, unreal.MaterialExpressionCustom)
        mask.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        mask.set_editor_property('description', 'Close camera shell cutaway')
        inputs=[]
        for input_name in ('World', 'Camera'):
            item=unreal.CustomInput();item.set_editor_property('input_name', input_name);inputs.append(item)
        mask.set_editor_property('inputs', inputs)
        mask.set_editor_property('code', CAMERA_MASK)
        connect(world, '', mask, 'World');connect(camera, '', mask, 'Camera')
        if alpha_node is not None:
            combined=expression(material, unreal.MaterialExpressionMultiply)
            connect(mask, '', combined, 'A');connect(alpha_node, alpha_pin, combined, 'B')
            mask=combined
        if not lib.connect_material_property(mask, '', unreal.MaterialProperty.MP_OPACITY_MASK):
            raise RuntimeError('Camera mask connection failed: ' + name)
    # Authored constant hemisphere shading: keeps PC shell readable with no
    # additional shadow map, reflection capture, or dynamic light count.
    ambient_pin = ''
    if profile.get('baked_hemisphere'):
        ambient = expression(material, unreal.MaterialExpressionVertexColor)
        ambient_pin = 'R'
    else:
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
    connect(ambient, ambient_pin, result, 'B')
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
if profile.get('baked_hemisphere'):
    mesh_options.set_editor_property('vertex_color_import_option', unreal.VertexColorImportOption.REPLACE)
task = unreal.AssetImportTask()
for k, v in {'filename': profile['fbx'], 'destination_path': destination,
              'destination_name': mesh_name, 'automated': True,
              'save': True, 'replace_existing': resume, 'options': options}.items():
    task.set_editor_property(k, v)
asset_path = destination + '/' + mesh_name
mesh = unreal.load_asset(asset_path) if resume and unreal.EditorAssetLibrary.does_asset_exist(asset_path) else None
if mesh is None or os.environ.get('PESNX_STADIUM_REIMPORT') == '1':
    if mesh is not None and profile.get('baked_hemisphere'):
        # UE's reimport route can reuse the asset's saved settings instead of
        # FbxImportUI. Ignore would remap old colours by position, losing
        # distinct corner lighting when topology/UV seams change.
        saved_import = mesh.get_editor_property('asset_import_data')
        saved_import.set_editor_property('vertex_color_import_option', unreal.VertexColorImportOption.REPLACE)
        saved_import.set_editor_property('normal_import_method', unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    assets.import_asset_tasks([task])
    mesh = unreal.load_asset(destination + '/' + mesh_name)
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
          'crowd_animation': 'native 16-frame sheet at 8 fps, no vertex motion' if profile.get('crowd_flipbook') else 'static',
          'close_camera_cutaway': profile.get('close_camera_cutaway', False),
          'extent_cm': [extent.x, extent.y, extent.z],
          'origin_cm': [origin.x, origin.y, origin.z]}
# Verify the measured source bounds through the actual Blender -> UE basis.
blender_bounds = profile['blender_bounds']
expected_extent = [(blender_bounds[1][i]-blender_bounds[0][i])*50 for i in range(3)]
expected_origin = [(blender_bounds[1][i]+blender_bounds[0][i])*50 for i in range(3)]
expected_origin[1] *= -1
if (not (5500 < extent.x < 35000 and 3600 < extent.y < 35000 and 500 < extent.z < 12000)
        or any(abs(a-b)>max(5.,abs(b)*.002) for a,b in zip(report['extent_cm'],expected_extent))
        or any(abs(a-b)>5. for a,b in zip(report['origin_cm'],expected_origin))):
    raise RuntimeError('Unexpected imported centimetre scale or axes: ' + str(report))
with open(os.path.join(work, 'ue-import.local.json'), 'w') as stream:
    json.dump(report, stream, indent=2)
unreal.log('PESNX_STADIUM_IMPORT_OK ' + str(report))
if key == 'Anfield':
    unreal.log('PESNX_ANFIELD_IMPORT_OK ' + str(report))

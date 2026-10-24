"""UE4.22: import authored rain/snow fields and compile mobile mesh materials."""
import json
import ctypes as C
import os
import sys
import unreal
sys.path.insert(0, os.environ['PESNX_WEATHER_TOOLS'])
from ue_editor_properties import object_ptr, ref, set_value, bind, P

extend_bounds = bind(C.CDLL('UE4Editor-Engine.dll'), '?CalculateExtendedBounds@UStaticMesh@@QEAAXXZ', None, [P])

light=os.environ.get('NX_WEATHER_LIGHT')=='1'
light_snow=os.environ.get('NX_WEATHER_LIGHT_SNOW')=='1'
world_field=os.environ.get('NX_WEATHER_WORLD')=='1'
if light_snow and not light:raise ValueError('Light snow requires explicit light policy')
if world_field and (not light or light_snow):raise ValueError('World field requires both bounded seasonal assets')
destination = '/Game/FootballNX/WeatherWorld' if world_field else '/Game/FootballNX/WeatherLight' if light else '/Game/FootballNX/Weather'
assets = unreal.AssetToolsHelpers.get_asset_tools()
lib = unreal.MaterialEditingLibrary


def connect(a, output, b, input_name):
    if not lib.connect_material_expressions(a, output, b, input_name):
        raise RuntimeError('Failed material connection: ' + input_name)


def custom(mat, code, output, inputs):
    node = lib.create_material_expression(mat, unreal.MaterialExpressionCustom)
    node.set_editor_property('code', code)
    node.set_editor_property('output_type', output)
    fields = []
    for name, source in inputs:
        value = unreal.CustomInput()
        value.set_editor_property('input_name', name)
        fields.append(value)
    node.set_editor_property('inputs', fields)
    for name, source in inputs:
        connect(source, '', node, name)
    return node


def material(name, snow):
    mat = unreal.load_asset(destination + '/' + name) if unreal.EditorAssetLibrary.does_asset_exist(destination + '/' + name) else None
    if mat is None:
        mat = assets.create_asset(name, destination, unreal.Material, unreal.MaterialFactoryNew())
    lib.delete_all_material_expressions(mat)
    for key, value in [('shading_model', unreal.MaterialShadingModel.MSM_UNLIT),
                       ('blend_mode', unreal.BlendMode.BLEND_MASKED),
                       ('two_sided', True), ('use_full_precision', True),
                       ('opacity_mask_clip_value', .4)]:
        mat.set_editor_property(key, value)
    uv = lib.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate)
    # A per-component scalar is advanced by the match world, including pause.
    # It is bounded to 24 s to keep ES2 arithmetic precise in long sessions.
    clock = lib.create_material_expression(mat, unreal.MaterialExpressionScalarParameter)
    clock.set_editor_property('parameter_name', 'WeatherClock')
    clock.set_editor_property('default_value', 0.0)
    period = (12.0 if light else 6.0) if snow else 1.0
    wpo = custom(mat, '''
float phase=(floor(UV.x)+0.5)/128.0;
float fall=(frac(phase-Clock/%.1f)-phase)*1800.0;
float sway=sin(Clock*6.2831853/%.1f+phase*6.2831853)*%.1f;
return %s;
''' % (period, 8.0 if light and snow else 6.0, 18.0 if light and snow else 24.0 if snow else 6.0,
       'float3(sway,sway*0.3,fall)' if light and snow else
       'float3(fall*0.10,fall*0.025,fall)' if light else 'float3(sway,0.0,fall)'), unreal.CustomMaterialOutputType.CMOT_FLOAT3,
                 [('UV', uv), ('Clock', clock)])
    world = lib.create_material_expression(mat, unreal.MaterialExpressionWorldPosition)
    shape = custom(mat, '''
float2 q=float2(frac(UV.x),UV.y)*2.0-1.0;
float shape=%s;
float pitch=step(abs(World.x),5350.0)*step(abs(World.y),3450.0);
return shape*pitch*step(5.0,World.z);
''' % ('step(dot(q,q),0.55)' if snow else
       'step(abs(q.x),0.60*(1.0-abs(q.y)*0.70))' if light else 'step(abs(q.x),0.66)'),
                   unreal.CustomMaterialOutputType.CMOT_FLOAT1, [('UV', uv), ('World', world)])
    color = lib.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector)
    color.set_editor_property('constant', unreal.LinearColor(.52,.57,.62,1) if light and snow else
                              unreal.LinearColor(.30,.34,.37,1) if light else unreal.LinearColor(.72,.78,.84,1))
    # UE4.22 marks WPO's enum entry Hidden, so Python cannot use the enum.
    # Set the same reflected input that ConnectMaterialProperty would set.
    set_value(object_ptr(mat), 'Material', 'WorldPositionOffset',
              '(Expression=' + ref(object_ptr(wpo)) + ')')
    for node, prop in [(shape, unreal.MaterialProperty.MP_OPACITY_MASK),
                       (color, unreal.MaterialProperty.MP_EMISSIVE_COLOR)]:
        if not lib.connect_material_property(node, '', prop):
            raise RuntimeError('Failed output connection')
    lib.recompile_material(mat)
    unreal.EditorAssetLibrary.save_asset(mat.get_path_name())
    return mat


report = {}
for name in (('Rain','Snow') if world_field else ('Snow',) if light_snow else ('Rain',) if light else ('Rain','Snow')):
    mat = material('M_' + name + 'Field', name == 'Snow')
    options = unreal.FbxImportUI()
    for key, value in [('import_as_skeletal', False), ('import_mesh', True),
                       ('import_materials', False), ('import_textures', False),
                       ('import_animations', False)]:
        options.set_editor_property(key, value)
    mesh_options = options.get_editor_property('static_mesh_import_data')
    for key, value in [('combine_meshes', True), ('auto_generate_collision', False),
                       ('generate_lightmap_u_vs', False)]:
        mesh_options.set_editor_property(key, value)
    mesh_options.set_editor_property('normal_import_method', unreal.FBXNormalImportMethod.FBXNIM_COMPUTE_NORMALS)
    task = unreal.AssetImportTask()
    for key, value in [('filename', os.path.join(os.environ['NX_WEATHER_MESH'], name + 'Field.obj')),
                       ('destination_path', destination), ('destination_name', name + 'Field'),
                       ('automated', True), ('save', True), ('replace_existing', True), ('options', options)]:
        task.set_editor_property(key, value)
    assets.import_asset_tasks([task])
    mesh = unreal.load_asset(destination + '/' + name + 'Field')
    if mesh is None:
        raise RuntimeError('Weather mesh not imported')
    mesh.set_material(0, mat)
    # UV's integer phase and fractional mask must both survive the import.
    # Bounds include the entire authored 18 m column; extend for sway/wrap ends.
    for field in ('PositiveBoundsExtension', 'NegativeBoundsExtension'):
        set_value(object_ptr(mesh), 'StaticMesh', field, '(X=200,Y=80,Z=80)' if light and name=='Rain' else '(X=32,Y=32,Z=80)')
    extend_bounds(object_ptr(mesh))
    bounds = mesh.get_bounds()
    extent = bounds.box_extent
    valid=(5000 < extent.x < 5600 and 3200 < extent.y < 3650) if world_field else (2700 < extent.x < (3200 if light else 2900) and 2000 < extent.y < (2400 if light else 2200))
    if not (valid and 850 < extent.z < 1050):
        raise RuntimeError('Weather OBJ scale/axis mismatch: ' + str(bounds))
    unreal.EditorAssetLibrary.save_asset(mesh.get_path_name())
    report[name] = {'mesh': mesh.get_path_name(), 'extent_cm': [extent.x, extent.y, extent.z]}
with open(os.path.join(os.environ['NX_WEATHER_MESH'], 'ue-import.local.json'), 'w') as stream:
    json.dump(report, stream, indent=2)
unreal.log('NX_WEATHER_FIELD_OK ' + str(report))

"""UE4.22 commandlet: author the optional, bounded podium spark mesh material."""
import ctypes as C
import json
import os
import sys
import unreal

sys.path.insert(0, os.environ['PESNX_SPARK_TOOLS'])
from ue_editor_properties import object_ptr, ref, set_value, bind, P

if not unreal.SystemLibrary.get_engine_version().startswith('4.22.'):
    raise RuntimeError('Podium sparks require the supported UE4.22 authoring runtime')
DESTINATION='/Game/FootballNX/TrophySparks'
assets=unreal.AssetToolsHelpers.get_asset_tools()
lib=unreal.MaterialEditingLibrary
extend_bounds=bind(C.CDLL('UE4Editor-Engine.dll'),
                  '?CalculateExtendedBounds@UStaticMesh@@QEAAXXZ',None,[P])


def connect(a,output,b,input_name):
    if not lib.connect_material_expressions(a,output,b,input_name):
        raise RuntimeError('Failed material connection: '+input_name)


def custom(mat,code,output,inputs):
    node=lib.create_material_expression(mat,unreal.MaterialExpressionCustom)
    node.set_editor_property('code',code)
    node.set_editor_property('output_type',output)
    values=[]
    for name,source in inputs:
        item=unreal.CustomInput()
        item.set_editor_property('input_name',name)
        values.append(item)
    node.set_editor_property('inputs',values)
    for name,source in inputs:connect(source,'',node,name)
    return node


mat=unreal.load_asset(DESTINATION+'/M_PodiumSparks')
if mat is None:
    mat=assets.create_asset('M_PodiumSparks',DESTINATION,unreal.Material,unreal.MaterialFactoryNew())
lib.delete_all_material_expressions(mat)
for key,value in [('shading_model',unreal.MaterialShadingModel.MSM_UNLIT),
                  ('blend_mode',unreal.BlendMode.BLEND_MASKED),('two_sided',True),
                  ('use_full_precision',True),('opacity_mask_clip_value',.4),
                  ('disable_depth_test',False)]:
    mat.set_editor_property(key,value)
uv=lib.create_material_expression(mat,unreal.MaterialExpressionTextureCoordinate)
clock=lib.create_material_expression(mat,unreal.MaterialExpressionScalarParameter)
clock.set_editor_property('parameter_name','SparkClock')
clock.set_editor_property('default_value',0.)
motion=custom(mat,'''
float id=floor(UV.x);
float t=frac(Clock/2.0+(id+0.5)/128.0);
float sx=(frac(id*0.61803398875)-0.5)*160.0*t;
float sy=(frac(id*0.38196601125)-0.5)*120.0*t;
return float3(sx,sy,1680.0*t*(1.0-t));
''',unreal.CustomMaterialOutputType.CMOT_FLOAT3,[('UV',uv),('Clock',clock)])
# WorldPositionOffset expects a world vector. Rotate the local trajectory using
# the captured actor pose, so it remains behind a rotated podium as well.
world_motion=lib.create_material_expression(mat,unreal.MaterialExpressionTransform)
world_motion.set_editor_property('transform_source_type',unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL)
world_motion.set_editor_property('transform_type',unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
connect(motion,'',world_motion,'')
mask=custom(mat,'''
float2 q=float2(frac(UV.x),UV.y)*2.0-1.0;
float t=frac(Clock/2.0+(floor(UV.x)+0.5)/128.0);
float taper=1.0-abs(q.y)*0.65;
return step(abs(q.x),0.7*taper)*step(0.025,t)*step(t,0.965);
''',unreal.CustomMaterialOutputType.CMOT_FLOAT1,[('UV',uv),('Clock',clock)])
colour=custom(mat,'''
float t=frac(Clock/2.0+(floor(UV.x)+0.5)/128.0);
return float3(1.0,0.62,0.10)*(0.72+0.28*(1.0-t));
''',unreal.CustomMaterialOutputType.CMOT_FLOAT3,[('UV',uv),('Clock',clock)])
set_value(object_ptr(mat),'Material','WorldPositionOffset','(Expression='+ref(object_ptr(world_motion))+')')
for node,prop in ((mask,unreal.MaterialProperty.MP_OPACITY_MASK),
                  (colour,unreal.MaterialProperty.MP_EMISSIVE_COLOR)):
    if not lib.connect_material_property(node,'',prop):
        raise RuntimeError('Failed material output')
lib.recompile_material(mat)
unreal.EditorAssetLibrary.save_asset(mat.get_path_name())

options=unreal.FbxImportUI()
for key,value in [('import_as_skeletal',False),('import_mesh',True),
                  ('import_materials',False),('import_textures',False),('import_animations',False)]:
    options.set_editor_property(key,value)
mesh_options=options.get_editor_property('static_mesh_import_data')
for key,value in [('combine_meshes',True),('auto_generate_collision',False),
                  ('generate_lightmap_u_vs',False)]:mesh_options.set_editor_property(key,value)
mesh_options.set_editor_property('normal_import_method',unreal.FBXNormalImportMethod.FBXNIM_COMPUTE_NORMALS)
task=unreal.AssetImportTask()
for key,value in [('filename',os.environ['PESNX_SPARK_OBJ']),('destination_path',DESTINATION),
                  ('destination_name','PodiumSparks'),('automated',True),('save',True),
                  ('replace_existing',True),('options',options)]:task.set_editor_property(key,value)
assets.import_asset_tasks([task])
mesh=unreal.load_asset(DESTINATION+'/PodiumSparks')
if mesh is None:raise RuntimeError('Podium sparks were not imported')
mesh.set_material(0,mat)
# The static mesh lies at fountain bases. Explicit culling extensions include
# the complete rising/falling trajectories without an oversized stadium bound.
set_value(object_ptr(mesh),'StaticMesh','PositiveBoundsExtension','(X=82,Y=62,Z=422)')
set_value(object_ptr(mesh),'StaticMesh','NegativeBoundsExtension','(X=82,Y=62,Z=2)')
extend_bounds(object_ptr(mesh))
bounds=mesh.get_bounds()
extent=bounds.box_extent
if not (500<extent.x<520 and 60<extent.y<70 and 215<extent.z<225):
    raise RuntimeError('Podium spark OBJ scale/bounds mismatch: '+str(bounds))
unreal.EditorAssetLibrary.save_asset(mesh.get_path_name())
report={'mesh':mesh.get_path_name(),'material':mat.get_path_name(),
        'extent_cm':[extent.x,extent.y,extent.z], 'sparks':128,'triangles':512,
        'one_primitive':True,'masked_depth_test':True,'fragment_texture_fetches':0,
        'new_lights':0,'shadow_map':False,'authored_approximation':True,
        'device_appearance_tested':False}
with open(os.environ['PESNX_SPARK_REPORT'],'w') as report_file:
    json.dump(report,report_file,indent=2)
    report_file.write('\n')
unreal.log('NX_TROPHY_SPARKS_OK '+str(report))

"""Represent a genuinely empty source hair slot with an invisible native mesh.

UE refuses a zero-sized skeletal mesh. This exception is limited to hair-only
geometry whose entire extent is at most one millionth of a centimetre; it
cannot replace a visible scalp, a thin hair card, or missing source data.
"""
import json
import math
from pathlib import Path
import bpy
from mathutils import Vector
from blender_export_ue_fbx import rig_globals, rebuild_smooth_normals
from blender_fit_realface import runtime_matrix


def ensure_hair_slot(profile, output):
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    if not meshes:
        raise ValueError('Missing hair geometry is not an empty-slot proof')
    points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
    if not points or not all(math.isfinite(x) for p in points for x in p):
        raise ValueError('Nonfinite/absent hair geometry')
    spans=[max(p[k] for p in points)-min(p[k] for p in points) for k in range(3)]
    if max(spans)>1e-6:
        return None
    if any(not m.name.startswith(('rf_hair','rf_skin')) for o in meshes for m in o.data.materials):
        raise ValueError('Unexpected material in collapsed hair slot')
    arms=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    native=rig_globals(json.loads(Path(profile['native_rig']).read_text()))
    cooked=rig_globals(json.loads(Path(profile['cooked_rig']).read_text()))
    if len(arms)!=1 or set(b.name for b in arms[0].data.bones)!=set(native):
        raise ValueError('Empty hair slot requires the verified native rig')
    audit=dict(policy='authored_invisible_empty_hair_slot_v1',source_vertices=len(points),
               source_extent_cm=spans,output_vertices=3,output_triangles=1)
    material=bpy.data.materials.get('rf_hair_empty') or bpy.data.materials.new('rf_hair_empty')
    audit['material']=material.name
    for obj in meshes:
        bpy.data.objects.remove(obj,do_unlink=True)
    desired=[Vector((0,4,174)),Vector((.05,4,174)),Vector((0,4.05,174))]
    mesh=bpy.data.meshes.new('empty_hair_slot')
    mesh.from_pydata(desired,[],[(0,1,2)]);mesh.update()
    obj=bpy.data.objects.new('empty_hair_slot',mesh);bpy.context.scene.collection.objects.link(obj)
    obj.vertex_groups.new(name='sk_head').add([0,1,2],1.,'REPLACE')
    modifier=obj.modifiers.new('Armature','ARMATURE');modifier.object=arms[0]
    matrix=runtime_matrix(obj,{'sk_head':1.},native,cooked)
    for vertex,point in zip(mesh.vertices,desired):vertex.co=matrix.inverted()@point
    if matrix.determinant()<0:mesh.flip_normals()
    uv=mesh.uv_layers.new(name='UVMap')
    for loop in uv.data:loop.uv=(.5,.5)
    mesh.materials.append(material)
    rebuild_smooth_normals(obj)
    armature=arms[0];armature.name='Armature';armature.data.name='Armature'
    for other in bpy.context.scene.objects:other.select_set(other in (armature,obj))
    bpy.context.view_layer.objects.active=armature
    bpy.ops.export_scene.fbx(filepath=str(output),use_selection=True,global_scale=1.,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',use_space_transform=True,bake_space_transform=False,
        object_types={'ARMATURE','MESH'},mesh_smooth_type='FACE',use_tspace=True,add_leaf_bones=False,
        primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=False,
        armature_nodetype='NULL',bake_anim=False,path_mode='COPY',embed_textures=True,axis_forward='-Y',axis_up='Z')
    Path(output).with_suffix('.empty-hair.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    return audit

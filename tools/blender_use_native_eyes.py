"""Replace explicitly selected converted eyes with an audited native eye region.

Run in Blender with -- --profile local.json. The native face is the player's
own verified PES21 face. Geometry, UVs, normals and weights come from that
reference. An optional, explicitly reviewed yaw can rotate one eye around an
audited native pivot without moving the accepted eye or rescaling either eye.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from realface_reference import load_reference
from blender_export_ue_fbx import rig_globals
from blender_fit_realface import vertex_weights,runtime_matrix


def replace(profile):
    output=Path(profile['output']).resolve()
    if output.exists():
        raise ValueError('Refusing to overwrite native-eye output')
    reference=load_reference(Path(profile['native_face']))
    native=rig_globals(json.loads(Path(profile['native_rig']).read_text()))
    cooked=rig_globals(json.loads(Path(profile['cooked_rig']).read_text()))
    region=profile['native_eye_region']
    u0,v0,u1,v1=region['uv_bounds']
    z0,z1=region['z_bounds_cm'];x0,x1=region['abs_x_bounds_cm']
    indices={i for i,(p,uv) in enumerate(zip(reference['vertices'],reference['uv']))
             if u0<=uv[0]<=u1 and v0<=uv[1]<=v1 and z0<=p[2]<=z1 and x0<=abs(p[0])<=x1}
    faces=[f for f in reference['faces'] if all(i in indices for i in f)]
    used=sorted({i for f in faces for i in f})
    if len(used)!=region['expected_vertices'] or len(faces)!=region['expected_triangles']:
        raise ValueError('Native eye selection differs from the audited profile')
    if not used or {n for i in used for n in reference['weights'][i]}!={'sk_head'}:
        raise ValueError('Native eye region must be head-bound')
    if not any(reference['vertices'][i][0]<0 for i in used) or not any(reference['vertices'][i][0]>0 for i in used):
        raise ValueError('Native eye region must contain both eyes')
    remap={old:new for new,old in enumerate(used)}
    expected=[Vector(reference['vertices'][i]) for i in used]
    source_normals=[Vector(reference['normals'][i]) for i in used]
    gaze=profile.get('gaze')
    rotated=set()
    if gaze:
        side=gaze['side']
        if side not in ('negative_x','positive_x'):
            raise ValueError('Native eye gaze side must be explicit')
        yaw=float(gaze['yaw_degrees'])
        pivot=Vector(gaze['native_pivot_cm'])
        if len(pivot)!=3 or not all(math.isfinite(v) for v in pivot) or not math.isfinite(yaw) or abs(yaw)>12:
            raise ValueError('Native eye gaze requires a finite audited pivot and yaw within 12 degrees')
        sign=-1 if side=='negative_x' else 1
        rotated={j for j,p in enumerate(expected) if p.x*sign>0}
        if len(rotated)!=gaze['expected_vertices'] or not rotated or len(rotated)==len(used):
            raise ValueError('Native eye gaze selection differs from the audited profile')
        # The globe centre lies behind the visible hemisphere. Require its
        # lateral/vertical coordinates inside that eye and its depth nearby.
        if any(not min(expected[j][k] for j in rotated)<=pivot[k]<=max(expected[j][k] for j in rotated) for k in (0,2)):
            raise ValueError('Native eye pivot is outside the selected eye')
        if not min(expected[j].y for j in rotated)-3<=pivot.y<=max(expected[j].y for j in rotated):
            raise ValueError('Native eye pivot depth differs from the native globe')
        rotation=Matrix.Rotation(math.radians(yaw),3,'Z')
        for j in rotated:
            expected[j]=pivot+rotation@(expected[j]-pivot)
            source_normals[j]=rotation@source_normals[j]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system='METRIC'
    bpy.context.scene.unit_settings.scale_length=.01
    bpy.ops.import_scene.fbx(filepath=str(Path(profile['face_fbx']).resolve()),use_anim=False)
    arms=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    if len(arms)!=1 or set(b.name for b in arms[0].data.bones)!=set(native):
        raise ValueError('Unexpected converted skeleton')
    removed=[o for o in bpy.context.scene.objects if o.type=='MESH' and profile['replace_material'] in [m.name for m in o.data.materials]]
    if len(removed)!=1 or len(removed[0].data.materials)!=1:
        raise ValueError('Eye replacement requires exactly one dedicated eye mesh')
    removed_count=len(removed[0].data.vertices)
    bpy.data.objects.remove(removed[0],do_unlink=True)
    mesh=bpy.data.meshes.new('native_eyes_geometry')
    mesh.from_pydata(expected,[],[tuple(remap[i] for i in f) for f in faces])
    mesh.update()
    obj=bpy.data.objects.new('player_native_eyes',mesh)
    bpy.context.scene.collection.objects.link(obj)
    modifier=obj.modifiers.new('Armature','ARMATURE');modifier.object=arms[0]
    group=obj.vertex_groups.new(name='sk_head');group.add(list(range(len(used))),1.,'REPLACE')
    transform=runtime_matrix(obj,{'sk_head':1.},native,cooked)
    for v,p in zip(mesh.vertices,expected):v.co=transform.inverted()@p
    if transform.determinant()<0:mesh.flip_normals()
    uv=mesh.uv_layers.new(name='UVMap')
    for loop in mesh.loops:
        u,v=reference['uv'][used[loop.vertex_index]]
        uv.data[loop.index].uv=(u,1-v)
    for p in mesh.polygons:p.use_smooth=True
    normals=[(transform.to_3x3().transposed()@source_normals[l.vertex_index]).normalized() for l in mesh.loops]
    mesh.normals_split_custom_set(normals)
    material=bpy.data.materials.get(profile['native_eye_material']) or bpy.data.materials.new(profile['native_eye_material'])
    obj.data.materials.append(material)
    # Read expectations from the source; adding custom-normal/material layers
    # can invalidate Blender's earlier RNA view of the UV layer.
    uv_expected=[(reference['uv'][used[l.vertex_index]][0],1-reference['uv'][used[l.vertex_index]][1]) for l in mesh.loops]
    triangles_expected=[tuple(p.vertices) for p in mesh.polygons]
    armature=arms[0];armature.name='Armature';armature.data.name='Armature'
    for o in bpy.context.scene.objects:o.select_set(o.type in ('MESH','ARMATURE'))
    bpy.context.view_layer.objects.active=armature
    output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=str(output),use_selection=True,global_scale=1.,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',use_space_transform=True,bake_space_transform=False,
        object_types={'ARMATURE','MESH'},mesh_smooth_type='FACE',use_tspace=True,add_leaf_bones=False,
        primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=False,
        armature_nodetype='NULL',bake_anim=False,path_mode='COPY',embed_textures=True,axis_forward='-Y',axis_up='Z')
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=.01
    bpy.ops.import_scene.fbx(filepath=str(output),use_anim=False)
    obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and profile['native_eye_material'] in [m.name for m in o.data.materials])
    points=[runtime_matrix(obj,vertex_weights(obj,v),native,cooked)@v.co for v in obj.data.vertices]
    if len(points)!=len(expected):raise ValueError('Native eye vertex count changed')
    drift=max((a-b).length for a,b in zip(points,expected))
    uv_actual=[tuple(v.uv) for v in obj.data.uv_layers[0].data]
    if len(uv_actual)!=len(uv_expected) or [tuple(p.vertices) for p in obj.data.polygons]!=triangles_expected:
        raise ValueError('Native eye topology changed during FBX round-trip')
    uv_drift=max(abs(a-b) for old,new in zip(uv_expected,uv_actual) for a,b in zip(old,new))
    if drift>.001 or uv_drift>1e-6:
        raise ValueError('Native eye position or UV changed during FBX round-trip')
    preserved=[j for j in range(len(used)) if j not in rotated]
    native_drift=max((points[j]-Vector(reference['vertices'][used[j]])).length for j in preserved)
    report=dict(native_eye_source=profile['native_face'],native_eye_vertices=len(used),native_eye_triangles=len(faces),
                replaced_eye_vertices=removed_count,max_export_position_drift_cm=drift,
                native_uv_preserved=True,max_uv_drift=uv_drift,pupil_rotation_applied=bool(gaze),
                gaze=gaze,preserved_native_vertices=len(preserved),max_preserved_native_drift_cm=native_drift,
                max_target_rotation_move_cm=max(((expected[j]-Vector(reference['vertices'][used[j]])).length for j in rotated),default=0.),
                reference_eye_indices=used)
    output.with_suffix('.native-eyes.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='reference_eye_indices'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    replace(json.loads(args.profile.read_text(encoding='utf-8-sig')))

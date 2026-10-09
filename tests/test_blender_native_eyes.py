"""Native-eye transfer regression using authored synthetic geometry only."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

import pytest


def test_native_eye_geometry_uv_and_other_mesh_survive_fbx(tmp_path):
    blender=os.environ.get('PESNX_TEST_BLENDER') or shutil.which('blender')
    if not blender or not Path(blender).is_file():
        pytest.skip('Set PESNX_TEST_BLENDER for the synthetic native-eye transfer check')
    root=Path(__file__).resolve().parents[1]
    # Two eye quads and one unrelated triangle, in native centimetres.
    points=[(-3,10,9),(-1,10,9),(-1,10,11),(-3,10,11),
            (1,10,9),(3,10,9),(3,10,11),(1,10,11),(0,0,0),(1,0,0),(0,1,0)]
    faces=[(0,1,2),(0,2,3),(4,5,6),(4,6,7),(8,9,10)]
    uv=[(.81,.91),(.91,.91),(.91,.81),(.81,.81)]*2+[(0,0)]*3
    raw=bytearray();views=[];accessors=[]
    def add(rows,fmt,component,kind):
        start=len(raw)
        for row in rows:raw.extend(struct.pack('<'+fmt*len(row),*row))
        views.append(dict(buffer=0,byteOffset=start,byteLength=len(raw)-start))
        accessors.append(dict(bufferView=len(views)-1,componentType=component,count=len(rows),type=kind))
        return len(accessors)-1
    attrs=dict(POSITION=add([(x/100,z/100,y/100) for x,y,z in points],'f',5126,'VEC3'),
               NORMAL=add([(0,0,1)]*len(points),'f',5126,'VEC3'),
               TEXCOORD_0=add(uv,'f',5126,'VEC2'),
               JOINTS_0=add([(0,0,0,0)]*len(points),'B',5121,'VEC4'),
               WEIGHTS_0=add([(1,0,0,0)]*len(points),'f',5126,'VEC4'))
    indices=add([(i,) for tri in faces for i in reversed(tri)],'H',5123,'SCALAR')
    doc=dict(nodes=[dict(mesh=0,skin=0),dict(name='sk_head')],skins=[dict(joints=[1])],
             meshes=[dict(primitives=[dict(attributes=attrs,indices=indices)])],
             buffers=[dict(uri='mesh.bin',byteLength=len(raw))],bufferViews=views,accessors=accessors)
    (tmp_path/'mesh.bin').write_bytes(raw);(tmp_path/'native.gltf').write_text(json.dumps(doc))
    (tmp_path/'rig.json').write_text(json.dumps([dict(name='sk_head',parent=-1,trs=[0,0,0,1,0,0,0,1,1,1])]))
    profile=dict(native_face=str(tmp_path/'native.gltf'),native_rig=str(tmp_path/'rig.json'),
                 cooked_rig=str(tmp_path/'rig.json'),face_fbx=str(tmp_path/'source.fbx'),
                 output=str(tmp_path/'result.fbx'),replace_material='generic_eye',native_eye_material='native_eye',
                 native_eye_region=dict(uv_bounds=[.8,.8,1,1],z_bounds_cm=[8,12],abs_x_bounds_cm=[.5,4],
                                        expected_vertices=8,expected_triangles=4))
    (tmp_path/'profile.json').write_text(json.dumps(profile))
    script=tmp_path/'check.py'
    script.write_text('import sys\nfrom pathlib import Path\nroot=Path('+repr(str(root))+')\nw=Path('+repr(str(tmp_path))+')\nsys.path.insert(0,str(root/"tools"))\n'+r'''
import bpy,json,math
from mathutils import Matrix,Vector
from blender_use_native_eyes import replace
from blender_export_ue_fbx import rig_globals
from blender_fit_realface import runtime_matrix,vertex_weights
from realface_reference import load_reference
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=.01
rig=bpy.data.armatures.new('Armature');arm=bpy.data.objects.new('Armature',rig);bpy.context.collection.objects.link(arm)
bpy.context.view_layer.objects.active=arm;arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT');bone=rig.edit_bones.new('sk_head');bone.head=(0,0,0);bone.tail=(0,0,1);bpy.ops.object.mode_set(mode='OBJECT')
for name,material,points in [('skin','skin',[(0,0,0),(1,0,0),(0,0,1)]),('old_eyes','generic_eye',[(0,-1,8),(1,-1,8),(0,-1,9)])]:
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(points,[],[(0,1,2)]);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    obj.data.materials.append(bpy.data.materials.new(material))
    obj.vertex_groups.new(name='sk_head').add([0,1,2],1,'REPLACE')
    mod=obj.modifiers.new('Armature','ARMATURE');mod.object=arm
    obj.data.uv_layers.new(name='UVMap');obj.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(w/'source.fbx'),use_selection=True,object_types={'ARMATURE','MESH'},
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',add_leaf_bones=False,bake_anim=False,axis_forward='-Y',axis_up='Z')
profile=json.loads((w/'profile.json').read_text());replace(profile)
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
assert {o.name for o in meshes}=={'skin','player_native_eyes'}
skin=next(o for o in meshes if o.name=='skin')
for v,p in zip(skin.data.vertices,[(0,0,0),(1,0,0),(0,0,1)]):
    assert (skin.matrix_world@v.co-Vector(p)).length<.001
eye=next(o for o in meshes if o.name=='player_native_eyes')
assert len(eye.data.vertices)==8 and len(eye.data.polygons)==4
profile['native_eye_region']['expected_vertices']=9;profile['output']=str(w/'bad.fbx')
try:replace(profile)
except ValueError as error:assert 'selection' in str(error)
else:raise AssertionError('An ambiguous eye selection must fail closed')
assert not (w/'bad.fbx').exists()
profile['native_eye_region']['expected_vertices']=8
profile.update(face_fbx=str(w/'result.fbx'),replace_material='native_eye',output=str(w/'gazed.fbx'),
               gaze=dict(side='negative_x',yaw_degrees=-5,native_pivot_cm=[-2,9,10],expected_vertices=4))
replace(profile)
rig=rig_globals(json.loads((w/'rig.json').read_text()))
source=load_reference(w/'native.gltf')['vertices'][:8]
eye=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.name=='player_native_eyes')
pivot=Vector((-2,9,10));rotation=Matrix.Rotation(math.radians(-5),3,'Z')
for vertex,original in zip(eye.data.vertices,source):
    actual=runtime_matrix(eye,vertex_weights(eye,vertex),rig,rig)@vertex.co
    original=Vector(original)
    expected=pivot+rotation@(original-pivot) if original.x<0 else original
    assert (actual-expected).length<.001
    assert abs(actual.z-original.z)<.001
    if original.x<0:assert actual.x>original.x
assert eye.data.materials[0].name=='native_eye'
report=json.loads((w/'gazed.native-eyes.json').read_text())
assert report['preserved_native_vertices']==4 and report['max_preserved_native_drift_cm']<.001
assert report['max_uv_drift']<1e-6 and report['pupil_rotation_applied']
skin=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.name=='skin')
for v,p in zip(skin.data.vertices,[(0,0,0),(1,0,0),(0,0,1)]):
    assert (skin.matrix_world@v.co-Vector(p)).length<.001
profile['gaze']['yaw_degrees']=13;profile['output']=str(w/'excessive.fbx')
try:replace(profile)
except ValueError as error:assert '12 degrees' in str(error)
else:raise AssertionError('Excessive gaze rotation must fail closed')
assert not (w/'excessive.fbx').exists()
print('NATIVE_EYE_TRANSFER_OK')
''',encoding='utf-8')
    result=subprocess.run([str(blender),'--background','--python-exit-code','1','--python',str(script)],capture_output=True,text=True,timeout=120)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'NATIVE_EYE_TRANSFER_OK' in result.stdout

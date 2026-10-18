"""A zero smooth fan must not become importer-dependent FBX shading."""
import os
from pathlib import Path
import subprocess

import pytest


def test_folded_eye_fan_exports_finite_normals_without_more_triangles(tmp_path):
    root=Path(__file__).resolve().parents[1]
    bundled=root/'local-debug/lamine-yamal-face-canary/third-party/blender-4.5.13/blender-4.5.13-windows-x64/blender.exe'
    blender=Path(os.environ.get('PESNX_TEST_BLENDER',str(bundled)))
    if not blender.is_file():pytest.skip('Optional local Blender fixture required; set PESNX_TEST_BLENDER')
    script=tmp_path/'normal_regression.py'
    script.write_text('''import bpy,sys,json
from pathlib import Path
from io_scene_fbx import parse_fbx
sys.path.insert(0,sys.argv[sys.argv.index('--')+1])
from blender_realface_normal_export import repair
bpy.ops.wm.read_factory_settings(use_empty=True)
mesh=bpy.data.meshes.new('folded_eye_rim')
mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0),(0,1,0)],[],[(0,1,2),(1,0,3)])
mesh.update();uv=mesh.uv_layers.new(name='UVMap')
for f in mesh.polygons:
 f.use_smooth=True
 for li,st in zip(f.loop_indices,[(0,0),(1,0),(0,1)]):uv.data[li].uv=st
obj=bpy.data.objects.new('eye',mesh);bpy.context.collection.objects.link(obj)
obj.vertex_groups.new(name='sk_head').add(list(range(4)),1.,'REPLACE')
assert any(n.vector.length<.99 for n in mesh.corner_normals), 'Fixture did not reproduce the zero normal'
report=repair(obj)
assert report['undefined_corners']>0 and len(obj.data.polygons)==2
assert all(n.vector.length>.999 for n in obj.data.corner_normals)
assert {tuple(v.co) for v in obj.data.vertices}=={(0.,0.,0.),(1.,0.,0.),(0.,1.,0.)}
obj.select_set(True);bpy.context.view_layer.objects.active=obj
output=Path(__file__).with_suffix('.fbx')
bpy.ops.export_scene.fbx(filepath=str(output),use_selection=True,object_types={'MESH'},
 axis_forward='-Y',axis_up='Z',mesh_smooth_type='FACE',use_tspace=True,bake_anim=False)
fbx,_=parse_fbx.parse(str(output))
objects=next(n for n in fbx.elems if n.id==b'Objects')
geometry=next(n for n in objects.elems if n.id==b'Geometry')
layer=next(n for n in geometry.elems if n.id==b'LayerElementNormal')
values=next(n for n in layer.elems if n.id==b'Normals').props[0]
assert all(sum(v*v for v in values[i:i+3])>.998 for i in range(0,len(values),3))
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.fbx(filepath=str(output),use_anim=False)
mesh=next(o.data for o in bpy.context.scene.objects if o.type=='MESH')
assert len(mesh.polygons)==2 and all(n.vector.length>.999 for n in mesh.corner_normals)
print('FINITE_NORMAL_EXPORT_OK')
''',encoding='utf-8')
    result=subprocess.run([str(blender),'-b','-t','1','--python-exit-code','1','--python',str(script),'--',str(root/'tools')],
                          capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'FINITE_NORMAL_EXPORT_OK' in result.stdout

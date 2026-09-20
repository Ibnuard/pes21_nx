"""Optional Blender regression; generated geometry only, no game fixtures."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


def test_lower_chest_preserves_width_upper_neck_and_skinning(tmp_path):
    blender = os.environ.get("PESNX_TEST_BLENDER") or shutil.which("blender")
    if not blender or not Path(blender).is_file():
        pytest.skip("Set PESNX_TEST_BLENDER to run the Blender integration check")
    root = Path(__file__).resolve().parents[1]
    script = tmp_path / "check_chest.py"
    script.write_text("import sys\nsys.path.insert(0, " + repr(str(root)) + ")\n" + r'''
import bpy
from tools.blender_export_ue_fbx import lower_chest_attachment
bpy.ops.wm.read_factory_settings(use_empty=True)
mesh = bpy.data.meshes.new('chest')
mesh.from_pydata([(-4,2,153),(4,2,153),(-3,2,157.5),(3,2,157.5),
                 (-2,2,161),(2,2,161)], [], [(0,1,3,2),(2,3,5,4)])
obj = bpy.data.objects.new('chest',mesh)
bpy.context.collection.objects.link(obj)
group = obj.vertex_groups.new(name='neck')
group.add(list(range(6)),1.0,'REPLACE')
uv = mesh.uv_layers.new(name='UV0')
for i, loop in enumerate(uv.data): loop.uv = (i / 10, i / 20)
before = [tuple(v.co) for v in mesh.vertices]
weights = [[(g.group,g.weight) for g in v.groups] for v in mesh.vertices]
uvs = [tuple(loop.uv) for loop in uv.data]
result = lower_chest_attachment(obj,1.2)
assert result['vertices'] == 4
for i, v in enumerate(mesh.vertices):
    assert tuple(v.co)[:2] == before[i][:2], 'Neck circumference must not shrink'
assert abs(mesh.vertices[0].co.z - 151.8) < 0.0001
assert abs(mesh.vertices[2].co.z - 156.9) < 0.0001
assert tuple(mesh.vertices[4].co) == before[4]
assert tuple(mesh.vertices[5].co) == before[5]
assert weights == [[(g.group,g.weight) for g in v.groups] for v in mesh.vertices]
assert uvs == [tuple(loop.uv) for loop in uv.data]
for invalid in (-1, float('nan'), 4):
    try: lower_chest_attachment(obj,invalid)
    except ValueError: pass
    else: raise AssertionError('Invalid displacement accepted')
print('PESNX_CHEST_CHECK_OK')
''', encoding="utf-8")
    result = subprocess.run([str(blender), "--background", "--python-exit-code", "1",
                             "--python", str(script)], text=True, capture_output=True,
                            timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PESNX_CHEST_CHECK_OK" in result.stdout


def test_recomputed_normals_preserve_uvs_and_skinning(tmp_path):
    blender = os.environ.get("PESNX_TEST_BLENDER") or shutil.which("blender")
    if not blender or not Path(blender).is_file():
        pytest.skip("Set PESNX_TEST_BLENDER to run the Blender integration check")
    root = Path(__file__).resolve().parents[1]
    script = tmp_path / "check_normals.py"
    script.write_text(
        "import sys\nsys.path.insert(0, " + repr(str(root)) + ")\n" + r'''
import bpy
from tools.blender_export_ue_fbx import rebuild_smooth_normals
bpy.ops.wm.read_factory_settings(use_empty=True)
mesh = bpy.data.meshes.new("test")
mesh.from_pydata([(0,0,0), (1,0,0), (0,1,0), (-1,0,0)], [], [(0,1,2), (0,2,3)])
obj = bpy.data.objects.new("test", mesh)
bpy.context.collection.objects.link(obj)
for name in ("head", "unused", "neck"):
    obj.vertex_groups.new(name=name)
obj.vertex_groups[0].add([0,1], 0.75, 'REPLACE')
obj.vertex_groups[2].add([0,1], 0.25, 'REPLACE')
obj.vertex_groups[2].add([2,3], 1.0, 'REPLACE')
for name in ("skin", "eyes"):
    mesh.materials.append(bpy.data.materials.new(name))
mesh.polygons[1].material_index = 1
for name in ("UV0", "UV1"):
    layer = mesh.uv_layers.new(name=name)
    for i, loop in enumerate(layer.data):
        loop.uv = (i / 8, (7-i) / 8)
mesh.uv_layers.active_index = 1
mesh.normals_split_custom_set([(0,0,-1)] * len(mesh.loops))
assert mesh.corner_normals[0].vector.z < 0
def snapshot():
    data = obj.data
    return (
        [tuple(v.co) for v in data.vertices],
        [tuple(p.vertices) for p in data.polygons],
        [[tuple(v.uv) for v in layer.data] for layer in data.uv_layers],
        [layer.name for layer in data.uv_layers],
        data.uv_layers.active_index,
        [g.name for g in obj.vertex_groups],
        [[(g.group, g.weight) for g in v.groups] for v in data.vertices],
        [m.name for m in data.materials],
        [p.material_index for p in data.polygons],
    )
before = snapshot()
rebuild_smooth_normals(obj)
assert snapshot() == before, "Geometry/UV/material/weight loss while rebuilding"
assert not obj.data.has_custom_normals
assert all(n.vector.z > 0.99 for n in obj.data.corner_normals)
assert all(p.use_smooth for p in obj.data.polygons)
obj.shape_key_add(name="Basis")
try:
    rebuild_smooth_normals(obj)
except ValueError:
    pass
else:
    raise AssertionError("Must not silently drop shape keys")
print("PESNX_NORMALS_CHECK_OK")
''', encoding="utf-8")
    result = subprocess.run(
        [str(blender), "--background", "--python-exit-code", "1", "--python", str(script)],
        text=True, capture_output=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PESNX_NORMALS_CHECK_OK" in result.stdout


def test_island_fit_is_scoped_and_preserves_attributes(tmp_path):
    blender = os.environ.get("PESNX_TEST_BLENDER") or shutil.which("blender")
    if not blender or not Path(blender).is_file():
        pytest.skip("Set PESNX_TEST_BLENDER to run the Blender integration check")
    root = Path(__file__).resolve().parents[1]
    script = tmp_path / "check_islands.py"
    script.write_text(
        "import sys\nsys.path.insert(0, " + repr(str(root)) + ")\n" + r'''
import bpy
from mathutils import Matrix, Vector
from tools.blender_export_ue_fbx import fit_mesh_island
from tools.blender_export_ue_fbx import tuck_lower_neck
bpy.ops.wm.read_factory_settings(use_empty=True)
mesh = bpy.data.meshes.new("eyes")
mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0),(0,4,0),(1,4,0),(0,5,0)], [], [(0,1,2),(3,4,5)])
obj = bpy.data.objects.new("eyes", mesh)
bpy.context.collection.objects.link(obj)
obj.matrix_world = Matrix.Translation((8,2,169)) @ Matrix.Scale(2,4)
obj.vertex_groups.new(name="head").add(list(range(6)), 1.0, 'REPLACE')
uv = mesh.uv_layers.new(name="UVMap")
for i, loop in enumerate(uv.data):
    loop.uv = (i/6, i/7)
before = [obj.matrix_world @ v.co for v in mesh.vertices]
attributes = ([tuple(p.vertices) for p in mesh.polygons], [tuple(l.uv) for l in uv.data],
              [[(g.group,g.weight) for g in v.groups] for v in mesh.vertices])
for args in [('Y',1,1,(0,0,0),3), ('Y',2,1,(0,0,0),2), ('Q',1,1,(0,0,0),2),
             ('Y',1,0,(0,0,0),2), ('Y',1,1,(float('nan'),0,0),2)]:
    try:
        fit_mesh_island(obj,*args)
    except ValueError:
        pass
    else:
        raise AssertionError("Bad island fit must fail closed")
assert [obj.matrix_world @ v.co for v in mesh.vertices] == before
report = fit_mesh_island(obj,'Y',1,.96,(-.25,0,.25),2)
assert report['vertices'] == 3
pivot = Vector(report['center_cm'])
for i, v in enumerate(mesh.vertices):
    expected = before[i] if i < 3 else pivot+(before[i]-pivot)*.96+Vector((-.25,0,.25))
    assert (obj.matrix_world @ v.co - expected).length < .0001
assert attributes == ([tuple(p.vertices) for p in mesh.polygons], [tuple(l.uv) for l in uv.data],
              [[(g.group,g.weight) for g in v.groups] for v in mesh.vertices])
neck = bpy.data.meshes.new('neck')
neck.from_pydata([(8,10,153),(6,8,158),(4,6,162)], [], [(0,1,2)])
neck_obj=bpy.data.objects.new('neck',neck)
bpy.context.collection.objects.link(neck_obj)
neck_obj.vertex_groups.new(name='sk_neck').add([0,1,2],1.,'REPLACE')
neck_uv=neck.uv_layers.new(name='UVMap')
for i,loop in enumerate(neck_uv.data): loop.uv=(i/3,i/4)
saved=[tuple(loop.uv) for loop in neck_uv.data]
report=tuck_lower_neck(neck_obj)
assert report['vertices']==2
assert abs(neck.vertices[0].co.x-8*.52)<.0001
assert abs(neck.vertices[0].co.y-(5.43+(10-5.43)*.52))<.0001
assert tuple(neck.vertices[2].co)==(4,6,162)
assert [tuple(loop.uv) for loop in neck_uv.data]==saved
assert all(v.groups[0].weight==1 for v in neck.vertices)
print("PESNX_ISLAND_FIT_OK")
''', encoding="utf-8")
    result = subprocess.run(
        [str(blender), "--background", "--python-exit-code", "1", "--python", str(script)],
        text=True, capture_output=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PESNX_ISLAND_FIT_OK" in result.stdout


def test_runtime_bind_compensation_reconstructs_weighted_rest_pose(tmp_path):
    blender = os.environ.get("PESNX_TEST_BLENDER") or shutil.which("blender")
    if not blender or not Path(blender).is_file():
        pytest.skip("Set PESNX_TEST_BLENDER to run the Blender integration check")
    root = Path(__file__).resolve().parents[1]
    script = tmp_path / "check_bind.py"
    script.write_text("import sys\nsys.path.insert(0, " + repr(str(root)) + ")\n" + r'''
import bpy
from mathutils import Matrix, Vector
from tools.blender_export_ue_fbx import compensate_runtime_bind, rig_globals
bpy.ops.wm.read_factory_settings(use_empty=True)
mesh = bpy.data.meshes.new('neck')
mesh.from_pydata([(1,2,3),(2,3,4),(4,2,1)], [], [(0,1,2)])
obj = bpy.data.objects.new('neck', mesh)
bpy.context.collection.objects.link(obj)
obj.matrix_world = Matrix.Translation((2,1,5))
obj.vertex_groups.new(name='head').add([0,1], .7, 'REPLACE')
obj.vertex_groups.new(name='neck').add([0,1], .3, 'REPLACE')
obj.vertex_groups[1].add([2], 1., 'REPLACE')
native = {'head': Matrix.Translation((0,0,8)), 'neck': Matrix.Translation((0,0,5))}
cooked = {'head': native['head'] @ Matrix.Rotation(.6,4,'X'),
          'neck': native['neck'] @ Matrix.Rotation(-.4,4,'Y')}
desired = [obj.matrix_world @ v.co for v in mesh.vertices]
weights = [[(g.group,g.weight) for g in v.groups] for v in mesh.vertices]
report = compensate_runtime_bind(obj,native,cooked)
assert report['max_reconstructed_error_cm'] < .0001
reflect = Matrix.Diagonal((1.,-1.,1.,1.))
for v, expected in zip(mesh.vertices,desired):
    result = Vector((0,0,0))
    total = sum(g.weight for g in v.groups)
    for g in v.groups:
        name = obj.vertex_groups[g.group].name
        result += (native[name] @ cooked[name].inverted() @ reflect @ (obj.matrix_world @ v.co))*(g.weight/total)
    assert (result-expected).length < .0001
assert weights == [[(g.group,g.weight) for g in v.groups] for v in mesh.vertices]
for v,p in zip(mesh.vertices,desired):
    v.co=obj.matrix_world.inverted()@p
compensate_runtime_bind(obj,native,cooked,mirror_x=True)
for v,p in zip(mesh.vertices,desired):
    expected=Vector((-p.x,p.y,p.z))
    total=sum(g.weight for g in v.groups)
    result=sum(((native[obj.vertex_groups[g.group].name] @ cooked[obj.vertex_groups[g.group].name].inverted() @ reflect @ (obj.matrix_world@v.co))*(g.weight/total) for g in v.groups),Vector((0,0,0)))
    assert (result-expected).length < .0001
assert rig_globals([dict(name='root',parent=-1,trs=[0,0,0,1,1,2,3,1,1,1])])['root'].translation == Vector((1,2,3))
print('PESNX_BIND_CHECK_OK')
''', encoding="utf-8")
    result = subprocess.run([str(blender), "--background", "--python-exit-code", "1", "--python", str(script)],
                            text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PESNX_BIND_CHECK_OK" in result.stdout

"""Run in Blender: folded-card shading repair must preserve all mesh data."""
import sys
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from blender_export_ue_fbx import repair_fold_normals, rebuild_smooth_normals, opposed_triangle_count

bpy.ops.wm.read_factory_settings(use_empty=True)
mesh = bpy.data.meshes.new('fold')
mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0),(0,-1,.01)], [], [(0,1,2),(0,1,3)])
mesh.update()
obj = bpy.data.objects.new('fold',mesh)
bpy.context.scene.collection.objects.link(obj)
obj.vertex_groups.new(name='sk_head').add([0,1,2,3],1.,'REPLACE')
layer = mesh.uv_layers.new()
for i, loop in enumerate(layer.data): loop.uv = (i/6, i/7)
for polygon in mesh.polygons: polygon.use_smooth = True
mesh.normals_split_custom_set([Vector((0,0,1)) for _ in mesh.loops])
def geometry():
    m=obj.data
    return ([(tuple(v.co),[(g.group,g.weight) for g in v.groups]) for v in m.vertices],
            [tuple(p.vertices) for p in m.polygons],
            [[tuple(v.uv) for v in l.data] for l in m.uv_layers])
before=geometry();valid=[n.vector.copy() for n in mesh.corner_normals][:3]
result=repair_fold_normals(mesh)
assert result['repaired_corners']==3
assert before==geometry()
assert max((n.vector-v).length for n,v in zip(mesh.corner_normals,valid))<.001
for p in mesh.polygons:
    assert all(mesh.corner_normals[i].vector.dot(p.normal)>=0 for i in p.loop_indices)
rebuild_smooth_normals(obj)
assert before==geometry()
tiny=bpy.data.meshes.new('tiny')
tiny.from_pydata([(0,0,0),(1,0,0),(0,1,0),(0,1e-11,0)],[],[(0,1,2),(0,1,3)])
tiny.update()
for polygon in tiny.polygons:polygon.use_smooth=True
tiny.normals_split_custom_set([Vector((0,0,-1)) for _ in tiny.loops])
assert opposed_triangle_count(tiny)==1  # The real inverted surface still fails.
repair_fold_normals(tiny)
assert opposed_triangle_count(tiny)==0
print('Fold normal repair: geometry, UVs, weights, and valid normals preserved')

"""Volume-aware collapse for short opaque hairstyles that reject a scalp bake."""
import bpy
import bmesh
from blender_fit_realface import runtime_matrix, vertex_weights


def from_native_surface(mesh, inverse):
    """Keep outward winding while a native-space surface crosses handedness."""
    if inverse.determinant() < 0:
        mesh.flip_normals()
    for vertex in mesh.vertices:
        vertex.co = inverse @ vertex.co


def reduce(obj, positions, target, native, cooked):
    # Operate in native centimetres. Applying a modifier after the armature
    # could bake its deformation into this temporary coordinate space.
    for vertex, position in zip(obj.data.vertices, positions):
        vertex.co = position
    by_weight = {}
    for vertex in obj.data.vertices:
        key = tuple(sorted(vertex_weights(obj, vertex).items()))
        by_weight.setdefault(key, []).append(vertex.index)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    groups = [[bm.verts[i] for i in indices] for indices in by_weight.values()]
    for vertices in groups:
        bmesh.ops.remove_doubles(bm, verts=vertices, dist=.0001)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.calc_loop_triangles()
    modifier = obj.modifiers.new('Offline hair volume budget', 'DECIMATE')
    modifier.ratio = min(1., target / max(len(obj.data.loop_triangles), 1))
    modifier.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = obj
    while obj.modifiers.find(modifier.name) > 0:
        bpy.ops.object.modifier_move_up(modifier=modifier.name)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    transforms = {}
    for vertex in obj.data.vertices:
        key = tuple(sorted(vertex_weights(obj, vertex).items()))
        if key not in transforms:
            transforms[key] = runtime_matrix(obj, dict(key), native, cooked).inverted()
        vertex.co = transforms[key] @ vertex.co
    for polygon in obj.data.polygons:
        polygon.use_smooth = True

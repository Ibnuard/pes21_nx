"""Recover solid FL shell concourse floors without importing its playing surface.

The centre part also contains high-detail benches, pitch decals and equipment.
Only shallow concrete faces wholly outside a protected field rectangle qualify.
Inputs and converted geometry are owned local fixtures, never public assets.
"""
from copy import copy


def outside_field(points, half_length=53.5, half_width=35.0):
    """A separating half-plane ensures the entire triangle misses the field."""
    return any(all(sign * p[axis] >= bound for p in points)
               for axis, bound in ((0, half_length), (2, half_width))
               for sign in (-1, 1))


def perimeter_meshes(model):
    result = []
    for mesh in model.meshes:
        textures = [t.filename.lower() for role, t in mesh.materialInstance.textures
                    if role.startswith('Base_')]
        if not any('_cncr' in name for name in textures):
            continue
        faces = []
        for face in mesh.faces:
            points = [(v.position.x, v.position.y, v.position.z) for v in face.vertices]
            if (all(-0.3 <= p[1] <= 0.5 for p in points) and
                    max(p[1] for p in points)-min(p[1] for p in points) < 0.35 and
                    outside_field(points)):
                faces.append(face)
        if faces:
            selected = copy(mesh)
            selected.faces = faces
            used = {id(v) for face in faces for v in face.vertices}
            selected.vertices = [v for v in mesh.vertices if id(v) in used]
            result.append(selected)
    return result

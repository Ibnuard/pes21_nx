"""Exclude zero-sized filler meshes only when a real surface remains.

Some source heads include a separate, fully collapsed skin quad. It cannot
render and must not be fitted as a lower neck. Visible or differently weighted
surfaces are preserved. A wholly empty part stays available for its explicit
native-slot policy, rather than silently becoming missing geometry.
"""
import math
from types import SimpleNamespace


def collapsed(mesh, bone_mapper=None):
    if not mesh.vertices:
        return False
    points = [tuple(getattr(v.position, axis) for axis in ('x', 'y', 'z')) for v in mesh.vertices]
    if not all(math.isfinite(x) for p in points for x in p):
        return False
    if any(max(p[k] for p in points) - min(p[k] for p in points) > 1e-8 for k in range(3)):
        return False
    weights = mesh.vertices[0].boneMapping
    if bool(weights) and all(v.boneMapping == weights for v in mesh.vertices):
        return True
    if bone_mapper is not None:
        # Coincident points blended between at most two transformed bone
        # positions remain collinear in every pose: they cannot form a
        # visible triangle even when their individual weights differ.
        bones=set()
        for vertex in mesh.vertices:
            mapping=vertex.boneMapping or {}
            if not mapping or any(not math.isfinite(w) or w<0 for w in mapping.values()):return False
            if sum(mapping.values())<=0:return False
            bones.update(bone_mapper(b) for b,w in mapping.items() if w>0)
        return len(bones)<=2
    return False


def prune_collapsed_fillers(model, bone_mapper=None):
    empty = [mesh for mesh in model.meshes if collapsed(mesh,bone_mapper)]
    if len(empty) == len(model.meshes):
        return []
    excluded = {id(mesh) for mesh in empty}
    model.meshes = [mesh for mesh in model.meshes if id(mesh) not in excluded]
    return [dict(material=mesh.materialInstance.name, vertices=len(mesh.vertices),
                 policy='coincident_vertices_and_identical_weights' if collapsed(mesh) else
                        'coincident_vertices_at_most_two_mobile_bones') for mesh in empty]


def prune_disabled_nan_meshes(model):
    """A wholly NaN mesh is nonrendering; never repair mixed damaged geometry."""
    disabled=[m for m in model.meshes if m.vertices and
              all(math.isnan(getattr(v.position,k)) for v in m.vertices for k in ('x','y','z'))]
    visible=[m for m in model.meshes if m.vertices and not collapsed(m) and
             all(math.isfinite(getattr(v.position,k)) for v in m.vertices for k in ('x','y','z'))]
    if not visible:return []
    excluded={id(m) for m in disabled}
    model.meshes=[m for m in model.meshes if id(m) not in excluded]
    return [dict(material=m.materialInstance.name,vertices=len(m.vertices),policy='all_xyz_nan_nonrendering_mesh')
            for m in disabled]


def prune_collapsed_triangles(model,bone_mapper=None):
    """Remove only triangles that have zero area under every supported pose.

    Large coincident filler islands inside an otherwise visible hair mesh can
    make UE's overlap table quadratic. Visible corners and UVs stay untouched.
    """
    proposals=[]
    def empty(face):
        vs=face.vertices
        if collapsed(SimpleNamespace(vertices=vs),bone_mapper):return True
        for i in range(len(vs)):
            for j in range(i):
                a,b=vs[i],vs[j]
                if (a.boneMapping and a.boneMapping==b.boneMapping and
                        all(math.isfinite(getattr(a.position,k)) and
                            abs(getattr(a.position,k)-getattr(b.position,k))<=1e-8 for k in ('x','y','z'))):
                    return True
        return False
    for mesh in model.meshes:
        faces=[f for f in mesh.faces if not empty(f)]
        proposals.append((mesh,faces))
    if not any(faces for _,faces in proposals):return []
    audit=[];retained=[]
    for mesh,faces in proposals:
        removed=len(mesh.faces)-len(faces)
        if removed:
            used={id(v) for f in faces for v in f.vertices}
            vertices=[v for v in mesh.vertices if id(v) in used]
            audit.append(dict(material=mesh.materialInstance.name,triangles=removed,
                              vertices=len(mesh.vertices)-len(vertices),policy='zero_area_in_all_supported_poses'))
            mesh.faces=faces;mesh.vertices=vertices
        if faces:retained.append(mesh)
    model.meshes=retained
    return audit

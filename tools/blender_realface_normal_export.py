"""Replace undefined corner normals before FBX can delegate them to an importer.

Folded eye rims can have a zero smooth-fan average. Preserve every valid
direction, split only conflicting fans, and use the actual adjacent face
direction for undefined corners. Positions, UVs, triangles and weights stay.
"""
import json
from pathlib import Path
import bpy

from blender_meshopt import split_invalid_normal_fans
from blender_fit_realface import vertex_weights


def repair(obj):
    mesh=obj.data;expected=[n.vector.copy() for n in mesh.corner_normals]
    undefined={i for i,n in enumerate(expected) if n.length<.99}
    if not undefined:return dict(undefined_corners=0,split_fan_vertices=0,triangles_unchanged=True)
    weights=[list(vertex_weights(obj,v).items()) for v in mesh.vertices]
    names=[g.name for g in obj.vertex_groups]
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            if li in undefined:
                if poly.normal.length<.99:raise ValueError('Undefined normal also has a collapsed supporting face')
                expected[li]=poly.normal.copy().normalized()
    mesh.normals_split_custom_set(expected)
    replacement,weights,split=split_invalid_normal_fans(mesh,expected,weights)
    minimum=min(n.dot(actual.vector) for n,actual in zip(expected,replacement.corner_normals))
    if minimum<.999:raise ValueError('Explicit FBX normal repair failed')
    obj.data=replacement;obj.vertex_groups.clear()
    groups={name:obj.vertex_groups.new(name=name) for name in names}
    for vi,row in enumerate(weights):
        for name,value in row:groups[name].add([vi],value,'REPLACE')
    return dict(undefined_corners=len(undefined),split_fan_vertices=split,minimum_dot=minimum,
                triangles_unchanged=True,valid_source_normals_preserved=True)


def prepare(job):
    import blender_realface_mobile as mobile
    from blender_realface_league_worker import prepare as base_prepare
    original=mobile.merge_atlas
    def atlas(job):
        original(job)
        result=repair(bpy.context.view_layer.objects.active)
        (Path(job['folder'])/'normal-export-repair.json').write_text(json.dumps(result,indent=2))
    mobile.merge_atlas=atlas
    try:base_prepare(job)
    finally:mobile.merge_atlas=original

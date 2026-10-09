"""Fit a converted face against native reference surfaces, inside Blender.

Run Blender --background --python-exit-code 1 --python this_file -- --profile
profile.json. Profiles and reference meshes are explicit inputs; no player,
donor, skin colour or source-mesh count is selected implicitly.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import rig_globals, rebuild_smooth_normals
from realface_reference import barycentric, load_reference, mix_weights, socket_target_x, socket_target_z


def smooth(value):
    value = min(1., max(0., value))
    return value * value * (3 - 2 * value)


def vertex_weights(obj, vertex):
    weights = {obj.vertex_groups[g.group].name: g.weight for g in vertex.groups if g.weight > 0}
    total = sum(weights.values())
    if not total or abs(total-1) > .01:
        raise ValueError("Invalid converted vertex weights")
    return {n: w/total for n, w in weights.items()}


def runtime_matrix(obj, weights, native, cooked):
    blend = Matrix([[sum((native[n] @ cooked[n].inverted())[r][c] * w
                         for n, w in weights.items()) for c in range(4)] for r in range(4)])
    result = blend @ Matrix.Diagonal((1., -1., 1., 1.)) @ obj.matrix_world
    if abs(result.determinant()) < 1e-8:
        raise ValueError("Singular weighted bind transform")
    return result


def components(mesh):
    adjacent = {v.index: set() for v in mesh.vertices}
    for edge in mesh.edges:
        a, b = edge.vertices
        adjacent[a].add(b)
        adjacent[b].add(a)
    unseen, result = set(adjacent), []
    while unseen:
        queue, group = [unseen.pop()], []
        while queue:
            a = queue.pop()
            group.append(a)
            for b in adjacent[a]:
                if b in unseen:
                    unseen.remove(b)
                    queue.append(b)
        result.append(group)
    return result


def align_eye_gaze(obj, points, transforms, reference_side, skin_tree):
    """Centre the other pupil relative to its own visible eyelid opening.

    The accepted pupil's relative offset is mirrored between the asymmetric
    sockets in both horizontal and vertical coordinates. Only the other
    eyeball rotates; its UVs, socket position and the accepted eye are kept.
    """
    groups = components(obj.data)
    if len(groups) != 2:
        raise ValueError("Expected exactly two separate eyeballs")
    groups.sort(key=lambda g: sum(points[i].x for i in g)/len(g))
    if reference_side not in ("negative_x", "positive_x"):
        raise ValueError("Eye reference side must be explicit")
    accepted = groups[0 if reference_side == "negative_x" else 1]
    target = groups[1 if reference_side == "negative_x" else 0]
    uv = {v.index: [] for v in obj.data.vertices}
    for loop in obj.data.loops:
        uv[loop.vertex_index].append(obj.data.uv_layers[0].data[loop.index].uv.copy())

    def eye(group):
        center = Vector([(min(points[i][k] for i in group) + max(points[i][k] for i in group))/2 for k in range(3)])
        pupil = min(group, key=lambda i: min((st-Vector((.5, .5))).length_squared for st in uv[i]))
        if min((st-Vector((.5, .5))).length for st in uv[pupil]) > .02:
            raise ValueError("Eye texture has no validated central pupil landmark")
        return center, pupil

    eye_tree = BVHTree.FromPolygons(points, [tuple(p.vertices) for p in obj.data.polygons])
    ray_y = max(p.y for p in points) + 30

    def opening(group, pupil, axis, cross_coordinate=None):
        low, high = min(points[i][axis] for i in group), max(points[i][axis] for i in group)
        cross_axis = 2 if axis == 0 else 0
        cross_coordinate = points[pupil][cross_axis] if cross_coordinate is None else cross_coordinate
        visible = []
        for row in range(5):
            for column in range(200):
                coordinate = low + (high-low)*column/199
                origin = Vector((0, ray_y, 0))
                origin[axis] = coordinate
                origin[cross_axis] = cross_coordinate+(row-2)*.035
                direction = Vector((0, -1, 0))
                hit, _, _, distance = eye_tree.ray_cast(origin, direction)
                skin_hit, _, _, skin_distance = skin_tree.ray_cast(origin, direction)
                if hit is not None and (skin_hit is None or distance < skin_distance-.005):
                    visible.append(coordinate)
        if len(visible) < 50:
            raise ValueError("Eye opening is occluded or too small to fit automatically")
        return [min(visible), max(visible), sum(visible)/len(visible)]

    _, good_pupil = eye(accepted)
    center, bad_pupil = eye(target)
    good_opening, bad_opening = opening(accepted, good_pupil, 0), opening(target, bad_pupil, 0)
    desired_x = socket_target_x(points[good_pupil].x, good_opening, bad_opening)
    good_vertical = opening(accepted, good_pupil, 2)
    bad_vertical = opening(target, bad_pupil, 2, desired_x)
    desired_z = socket_target_z(points[good_pupil].z, good_vertical, bad_vertical)
    original = points[bad_pupil]-center
    radius_squared = original.length_squared
    dx, dz = desired_x-center.x, desired_z-center.z
    if radius_squared <= dx**2+dz**2 or original.y <= 0:
        raise ValueError("Pupil cannot reach the measured opening centre by a front-facing rotation")
    desired = Vector((dx, math.sqrt(radius_squared-dx**2-dz**2), dz))
    angle = original.angle(desired)
    if abs(math.degrees(angle)) > 12:
        raise ValueError("Eye needs manual review: socket correction exceeds 12 degrees")
    rotation = original.rotation_difference(desired).to_matrix().to_4x4()
    before_normals = [n.vector.copy() for n in obj.data.corner_normals]
    changed = set(target)
    for i in target:
        obj.data.vertices[i].co = transforms[i].inverted() @ (center + rotation.to_3x3() @ (points[i]-center))
    for loop in obj.data.loops:
        i = loop.vertex_index
        if i in changed:
            local = transforms[i].inverted() @ rotation @ transforms[i]
            before_normals[loop.index] = (local.to_3x3().inverted().transposed() @ before_normals[loop.index]).normalized()
    obj.data.normals_split_custom_set(before_normals)
    return dict(method='eyelid_aperture_xz', rotation_degrees=math.degrees(angle), reference_side=reference_side,
                accepted_opening_native_x=good_opening, adjusted_opening_native_x=bad_opening,
                accepted_opening_native_z=good_vertical, adjusted_opening_native_z=bad_vertical,
                accepted_vertices=len(accepted), adjusted_vertices=len(target),
                accepted_pupil_native=list(points[good_pupil]),
                adjusted_pupil_before=list(points[bad_pupil]),
                adjusted_pupil_after=list(transforms[bad_pupil] @ obj.data.vertices[bad_pupil].co),
                accepted_eye_max_drift_cm=max((transforms[i] @ obj.data.vertices[i].co-points[i]).length for i in accepted))


def add_reference(name, reference, collection):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(reference["vertices"], [], reference["faces"])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.hide_render = True
    obj.display_type = 'WIRE'
    obj["reference_only"] = True
    return obj


def fit(profile):
    output = Path(profile["output"]).resolve()
    if output.exists():
        raise ValueError("Refusing to overwrite a candidate directory")
    native = rig_globals(json.loads(Path(profile["native_rig"]).read_text()))
    cooked = rig_globals(json.loads(Path(profile["cooked_rig"]).read_text()))
    if set(native) != set(cooked):
        raise ValueError("Native and cooked rig bones differ")
    surface = load_reference(Path(profile["native_face"]))
    body = load_reference(Path(profile["native_body"]))
    if set(surface["bone_names"]) != set(native) or set(body["bone_names"]) != set(native):
        raise ValueError("Reference meshes use a different rig")
    settings = profile["fit"]
    lower, full, stop = (float(settings[k]) for k in ("min_z_cm", "full_until_z_cm", "stop_z_cm"))
    cap = float(settings["max_move_cm"])
    if not lower < full < stop or not 0 < cap <= 2:
        raise ValueError("Invalid fitting limits")
    ref_vertices = [Vector(p) for p in surface["vertices"]]
    faces = [f for f in surface["faces"] if min(ref_vertices[i].z for i in f) < stop]
    tree = BVHTree.FromPolygons(ref_vertices, faces, all_triangles=True)
    body_tree = BVHTree.FromPolygons([Vector(p) for p in body["vertices"]], body["faces"], all_triangles=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = .01
    # Reference geometry is present before the candidate is imported.
    refs = bpy.data.collections.new('NATIVE_REFERENCE_DO_NOT_EXPORT')
    bpy.context.scene.collection.children.link(refs)
    add_reference('native_face_reference', surface, refs)
    add_reference('native_body_reference', body, refs)
    prior = set(bpy.context.scene.objects)
    bpy.ops.import_scene.fbx(filepath=str(Path(profile["face_fbx"]).resolve()), use_anim=False)
    imported = list(set(bpy.context.scene.objects)-prior)
    meshes = [o for o in imported if o.type == 'MESH']
    arms = [o for o in imported if o.type == 'ARMATURE']
    if len(arms) != 1 or set(b.name for b in arms[0].data.bones) != set(native):
        raise ValueError("Unexpected candidate armature")
    report = dict(schema_version=1, base_id=profile["base_id"],
                  native_reference_loaded_first=True, reference_geometry_exported=False,
                  body_reference=profile["native_body"], eye=None, meshes=[])
    motion_samples = []
    # Measure occlusion in the converted face, not the native donor's sockets.
    skin_points, skin_faces = [], []
    for obj in meshes:
        if profile['skin_material'] not in [m.name.split('.')[0] for m in obj.data.materials]:
            continue
        offset = len(skin_points)
        skin_points.extend(runtime_matrix(obj, vertex_weights(obj, v), native, cooked) @ v.co for v in obj.data.vertices)
        skin_faces.extend(tuple(offset+i for i in p.vertices) for p in obj.data.polygons)
    skin_tree = BVHTree.FromPolygons(skin_points, skin_faces)
    for obj in meshes:
        original_weights = [vertex_weights(obj, v) for v in obj.data.vertices]
        transforms = [runtime_matrix(obj, w, native, cooked) for w in original_weights]
        points = [m @ v.co for v, m in zip(obj.data.vertices, transforms)]
        uvs = [[tuple(v.uv) for v in layer.data] for layer in obj.data.uv_layers]
        topology = [tuple(p.vertices) for p in obj.data.polygons]
        before_normals = [n.vector.copy() for n in obj.data.corner_normals]
        materials = [m.name.split('.')[0] for m in obj.data.materials]
        changed, weight_changes, distances = set(), 0, []
        if profile.get("eye") and profile["eye"]["material"] in materials:
            if report["eye"] is not None:
                raise ValueError("More than one eye mesh")
            report["eye"] = align_eye_gaze(obj, points, transforms, profile["eye"]["reference_side"], skin_tree)
        elif profile["skin_material"] in materials:
            for v, p, old_w, old_m in zip(obj.data.vertices, points, original_weights, transforms):
                if not lower < p.z < stop:
                    continue
                amount = smooth((stop-p.z)/(stop-full)) * smooth((p.z-lower)/2)
                target, normal, face_index, distance = tree.find_nearest(p)
                if distance > settings["max_reference_distance_cm"]:
                    raise ValueError(f"{obj.name}: lower neck is too far from the native reference")
                triangle = faces[face_index]
                coefficients = barycentric(target, [ref_vertices[i] for i in triangle])
                target_weights = {}
                for i, coefficient in zip(triangle, coefficients):
                    for name, weight in surface["weights"][i].items():
                        target_weights[name] = target_weights.get(name, 0) + weight*coefficient
                weights = mix_weights(old_w, target_weights, amount*settings["weight_blend"])
                delta = target-p
                if delta.length > cap:
                    delta *= cap/delta.length
                target = p+delta*amount
                # Small clearance is applied only where a shirt surface covers
                # the original and target skin. Open collar skin stays intact.
                q, n, _, d = body_tree.find_nearest(target)
                clearance = settings["cloth_clearance_cm"]
                signed = (target-q).dot(n)
                if d < .8 and signed > -clearance and q.z < full:
                    target -= n*min(clearance+signed, cap/2)*amount
                if (target-p).length > cap+clearance+1e-5:
                    raise ValueError(f"{obj.name} vertex {v.index}: fitting move {(target-p).length:.6f} cm exceeds {cap+clearance:.6f} cm budget")
                new_m = runtime_matrix(obj, weights, native, cooked)
                v.co = new_m.inverted() @ target
                if weights != old_w:
                    for group in obj.vertex_groups:
                        group.remove([v.index])
                    for name, weight in weights.items():
                        obj.vertex_groups[name].add([v.index], weight, 'REPLACE')
                    weight_changes += 1
                changed.add(v.index)
                distances.append((target-p).length)
                motion_samples.append(dict(mesh=obj.name, index=v.index, before=list(p), after=list(target),
                                           before_weights=old_w, after_weights=weights,
                                           native_surface=list(tree.find_nearest(p)[0]), target_weights=target_weights))
            if changed:
                rebuild_smooth_normals(obj)
                normals = [n.vector.copy() for n in obj.data.corner_normals]
                for loop in obj.data.loops:
                    if loop.vertex_index not in changed:
                        normals[loop.index] = before_normals[loop.index]
                obj.data.normals_split_custom_set(normals)
        if uvs != [[tuple(v.uv) for v in layer.data] for layer in obj.data.uv_layers] or topology != [tuple(p.vertices) for p in obj.data.polygons]:
            raise ValueError("UV/topology changed during fitting")
        if not all(math.isfinite(c) for v in obj.data.vertices for c in v.co):
            raise ValueError("Non-finite fitted coordinates")
        upper = [i for i,p in enumerate(points) if p.z >= stop]
        drift = max(((runtime_matrix(obj, vertex_weights(obj, obj.data.vertices[i]), native, cooked) @ obj.data.vertices[i].co-points[i]).length for i in upper), default=0)
        is_eye = profile.get('eye') and profile['eye']['material'] in materials
        if not is_eye and drift > .001:
            raise ValueError("Fitting moved protected upper face")
        report["meshes"].append(dict(name=obj.name, vertices=len(points),
                                     adjusted_neck_vertices=len(changed), weight_changes=weight_changes,
                                     max_neck_move_cm=max(distances, default=0), upper_drift_cm=drift,
                                     uv_topology_preserved=True))
    if profile.get("eye") and report["eye"] is None:
        raise ValueError("Configured eye mesh is missing")
    if report["eye"] and report["eye"]["accepted_eye_max_drift_cm"] > .001:
        raise ValueError("Accepted eye changed")
    output.mkdir(parents=True)
    armature = arms[0]
    armature.name = 'Armature'
    armature.data.name = 'Armature'
    for obj in bpy.context.scene.objects:
        obj.select_set(obj in imported and obj.type in ('MESH', 'ARMATURE'))
    bpy.context.view_layer.objects.active = armature
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'reference-fit.blend'))
    bpy.ops.export_scene.fbx(filepath=str(output/'face.fbx'), use_selection=True,
        global_scale=1., apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        use_space_transform=True, bake_space_transform=False, object_types={'ARMATURE','MESH'},
        mesh_smooth_type='FACE', use_tspace=True, use_custom_props=True,
        add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
        use_armature_deform_only=False, armature_nodetype='NULL', bake_anim=False,
        path_mode='COPY', embed_textures=True, axis_forward='-Y', axis_up='Z')
    (output/'fit-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    (output/'motion-samples.json').write_text(json.dumps(motion_samples), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    fit(json.loads(args.profile.read_text(encoding='utf-8')))

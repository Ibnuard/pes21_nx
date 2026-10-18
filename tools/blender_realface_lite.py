"""Reduce fitted FBX heads offline, retaining the native rig and material roles.

Invoked by realface_lite.py in Blender. Original FBXs remain immutable. Eyes
keep their separate atlas; same-atlas skin/hair slots merge. Every result
records surface error in centimetres and is held if it exceeds its contract.
"""
import json
from pathlib import Path
import shutil
import sys
import math

import bpy
import bmesh
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import rig_globals
from blender_fit_realface import runtime_matrix, vertex_weights


def normalized(name):
    return name.replace('_00', '.00')


def count(obj):
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def points(obj, native, cooked):
    transforms = {}
    result = []
    for v in obj.data.vertices:
        weights = vertex_weights(obj, v)
        key = tuple(sorted(weights.items()))
        if key not in transforms:
            transforms[key] = runtime_matrix(obj, weights, native, cooked)
        result.append(transforms[key] @ v.co)
    return result


def surface(obj, native, cooked):
    pos = points(obj, native, cooked)
    obj.data.calc_loop_triangles()
    faces = []
    for triangle in obj.data.loop_triangles:
        a,b,c=(pos[i] for i in triangle.vertices)
        area2=(b-a).cross(c-a).length
        # Some sources contain point-size, disconnected hair markers. Native
        # bind-matrix roundoff can make them cross a degenerate-area threshold
        # and spuriously expand bounds by centimetres. Exclude only triangles
        # smaller than 0.3 mm in every direction AND 0.0001 cm2; long thin hair
        # cards are still measured. Geometry itself is not removed by this test.
        microscopic = area2 <= 2e-4 and max((b-a).length,(c-a).length,(c-b).length) < .03
        if area2 > 2e-6 and not microscopic:
            faces.append(tuple(triangle.vertices))
    return pos, faces


def quality(old_points, old_faces, obj, native, cooked):
    new, faces = surface(obj, native, cooked)
    if not old_faces and not faces:
        return dict(max_cm=0.,p95_cm=0.,reverse_max_cm=0.,lower_neck_max_cm=0.,bounds_max_cm=0.)
    if not faces or any(not math.isfinite(c) for v in new for c in v):
        raise ValueError('Empty/nonfinite reduced surface')
    tree = BVHTree.FromPolygons(new, faces, all_triangles=True)
    old_tree = BVHTree.FromPolygons(old_points, old_faces, all_triangles=True)
    # Include face centres: vertex-only sampling misses collapsed card holes.
    old_live = [old_points[i] for i in sorted({i for f in old_faces for i in f})]
    new_live = [new[i] for i in sorted({i for f in faces for i in f})]
    samples = old_live + [sum((old_points[i] for i in f), old_points[f[0]]*0)/3 for f in old_faces]
    distances = sorted(tree.find_nearest(p)[3] for p in samples)
    reverse = max(old_tree.find_nearest(p)[3] for p in new_live)
    neck = max((tree.find_nearest(p)[3] for p in old_live if p.z < 155), default=0.)
    bounds = max(abs(fn(p[i] for p in new_live)-fn(p[i] for p in old_live))
                 for i in range(3) for fn in (min, max))
    return dict(max_cm=distances[-1], p95_cm=distances[int((len(distances)-1)*.95)],
                reverse_max_cm=reverse, lower_neck_max_cm=neck, bounds_max_cm=bounds)


def export(path, arm):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type in ('ARMATURE', 'MESH'): obj.select_set(True)
    bpy.context.view_layer.objects.active = arm
    arm.name = 'Armature'; arm.data.name = 'Armature'
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True,
        global_scale=1., apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        use_space_transform=True, bake_space_transform=False,
        object_types={'ARMATURE', 'MESH'}, mesh_smooth_type='FACE', use_tspace=True,
        add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
        use_armature_deform_only=False, armature_nodetype='NULL', bake_anim=False,
        path_mode='ABSOLUTE', embed_textures=False, axis_forward='-Y', axis_up='Z')


def reduce_part(job, part, native, cooked):
    profile, folder = job['source_profile'], Path(job['folder'])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.scale_length = .01
    # Blender extracts embedded textures beside an FBX; never import in cache.
    copied = folder / ('input-' + part + '.fbx')
    if not copied.exists(): shutil.copy2(profile[part+'_fbx'], copied)
    bpy.ops.import_scene.fbx(filepath=str(copied), use_anim=False)
    arms = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    if len(arms) != 1 or set(b.name for b in arms[0].data.bones) != set(native):
        raise ValueError('Fitted input rig differs from the native skeleton')
    bones = [b.name for b in arms[0].data.bones]
    skin = set(map(normalized, profile['skin_materials'] if part == 'face' else profile.get('hair_skin_materials', [])))
    hair = set(map(normalized, profile.get('hair_materials', [])))
    groups = {}
    for obj in list(bpy.context.scene.objects):
        if obj.type != 'MESH': continue
        names = set(normalized(m.name) for m in obj.data.materials)
        if len(names) != 1: raise ValueError('Expected separately classified source slots: '+str(names))
        name = next(iter(names))
        role = 'skin' if name in skin else 'eye' if name == normalized(profile['eye_material']) else 'hair' if name in hair else None
        if role is None: raise ValueError('Unclassified input material '+name)
        groups.setdefault(role, []).append(obj)
    if job.get('mobile_v35') and part == 'face':
        from blender_realface_eye_cleanup import clean
        clean(groups, job, native, cooked)
    result = {}
    for role, objects in groups.items():
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects: obj.select_set(True)
        bpy.context.view_layer.objects.active = objects[0]
        if len(objects) > 1: bpy.ops.object.join()
        obj = bpy.context.object
        obj.name = 'lite_' + role
        obj.data.materials.clear()
        obj.data.materials.append(bpy.data.materials.new('lite_'+role))
        for poly in obj.data.polygons: poly.material_index = 0
        if not job.get('mobile_v35'):
            bm = bmesh.new(); bm.from_mesh(obj.data)
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
            bm.to_mesh(obj.data); bm.free()
        # Mobile's indexed reducer discards unused vertices itself. A BMesh
        # round trip here would discard the source's custom corner normals.
        if job.get('mobile_v35') and role=='skin':
            from blender_realface_skin_visibility import exterior
            exterior(obj,points(obj,native,cooked),folder)
        before = count(obj)
        old_points, old_faces = surface(obj, native, cooked)
        mobile_audit = None
        if job.get('mobile_v35') and role == 'hair':
            from blender_realface_mobile import prepare_hair
            mobile_audit = prepare_hair(obj, job, native, cooked)
        target = job['budgets']['face_skin' if part == 'face' and role == 'skin' else 'eye' if role == 'eye' else 'hair']
        if job.get('mobile_v35') and role=='hair' and job['budgets'].get('hair_mode')=='closed':
            from blender_realface_hair_reduce import reduce
            reduce(obj,points(obj,native,cooked),target,native,cooked)
        elif before > target and job.get('meshoptimizer'):
            from blender_meshopt import reduce
            reduce(obj, points(obj, native, cooked), target, role, job)
        elif before > target:
            # The fitted FBX compensates for native bind matrices. Simplifying
            # in that distorted import space can move weighted hair tips by
            # centimetres. Run QEM in actual native rest space, then invert the
            # new interpolated bind transform for each surviving vertex.
            for v, p in zip(obj.data.vertices, old_points): v.co = p
            # Some source hair exports duplicate every triangle corner. Weld
            # exact positions only within identical weight groups; loop UVs
            # retain their seams. This avoids a thousands-of-islands floor.
            if role == 'hair':
                groups_by_weight = {}
                for v in obj.data.vertices:
                    weights = tuple(sorted(vertex_weights(obj, v).items()))
                    groups_by_weight.setdefault(weights, []).append(v.index)
                bm = bmesh.new(); bm.from_mesh(obj.data); bm.verts.ensure_lookup_table()
                vertex_groups = [[bm.verts[i] for i in ids] for ids in groups_by_weight.values()]
                for vertices in vertex_groups:
                    bmesh.ops.remove_doubles(bm, verts=vertices, dist=.005)
                bm.to_mesh(obj.data); bm.free()
            mod = obj.modifiers.new('Offline mobile budget', 'DECIMATE')
            mod.ratio = target / before
            mod.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bm = bmesh.new(); bm.from_mesh(obj.data)
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
            bm.to_mesh(obj.data); bm.free()
            transforms = {}
            for v in obj.data.vertices:
                weights = vertex_weights(obj, v)
                key = tuple(sorted(weights.items()))
                if key not in transforms:
                    transforms[key] = runtime_matrix(obj, weights, native, cooked).inverted()
                v.co = transforms[key] @ v.co
        after = count(obj)
        error = quality(old_points, old_faces, obj, native, cooked)
        result[role] = dict(before=before, after=after, vertices=len(obj.data.vertices), error=error)
        if mobile_audit is not None:
            from blender_realface_mobile import finish_hair
            result[role]['exterior'] = finish_hair(obj, job, native, cooked, mobile_audit)
        (folder/(part+'-'+role+'-metrics.json')).write_text(json.dumps(result[role], indent=2))
        limits = job['limits'][role]
        if any(error[k] > limit for k, limit in limits.items()):
            raise ValueError('Surface quality held '+part+'/'+role+': '+json.dumps(error))
        for vertex in obj.data.vertices:
            weights = vertex_weights(obj, vertex)
            if not weights or abs(sum(weights.values())-1) > .01:
                raise ValueError('Invalid reduced bone weights')
    if job.get('mobile_v35') and part == 'face':
        from blender_realface_mobile import merge_atlas
        merge_atlas(job)
    output = folder / (part+'.fbx')
    export(output, arms[0])
    return dict(roles=result, bones=bones, total=sum(r['after'] for r in result.values()),
                sections=1 if job.get('mobile_v35') else len(result), fbx=str(output))


def run(job):
    folder = Path(job['folder']); folder.mkdir(parents=True, exist_ok=True)
    native = rig_globals(json.loads(Path(job['native_rig']).read_text()))
    cooked = rig_globals(json.loads(Path(job['cooked_rig']).read_text()))
    report = {part: reduce_part(job, part, native, cooked) for part in ('face','hair')}
    total = sum(p['total'] for p in report.values())
    if total > job['budgets']['head_cap']:
        raise ValueError('Head exceeds cooked candidate budget: '+str(total))
    report.update(base_id=job['base_id'], native_player_id=job['native_player_id'],
                  total_triangles=total, hardware_accepted=False)
    (folder/'simplification.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PESNX_REALFACE_LITE_PREPARED', job['base_id'], total, flush=True)


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8')))

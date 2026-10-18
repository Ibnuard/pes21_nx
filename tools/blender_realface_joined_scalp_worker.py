"""Use the entire remaining head budget for a joined, source-derived scalp.

Facial hair is projected onto the unchanged opaque face. The scalp occupies
one existing hair section instead of spending triangles on sparse loose cards.
All projection, clump shading and silhouette comparisons happen offline.
"""
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import rig_globals
from blender_fit_realface import runtime_matrix, vertex_weights
from blender_realface_joined_recovery import import_mesh
from blender_realface_lite import count
from blender_realface_mobile import geometry, pixels
from blender_realface_native_hair_worker import (subset, paint_undercoat, clean_generated_base,
    export_only, roundtrip, triangle_records)
from blender_realface_native_hair_detail import detail
from blender_realface_source_quality import capture_normals, transfer_normals
from realface_native_hair_cards import scalp_triangles, composite_ok
from realface_mobile_geometry import audit, compare


def run(job):
    folder = Path(job['folder']); base = Path(job['face_folder'])
    native, cooked = (rig_globals(json.loads(Path(job[k]).read_text()))
                      for k in ('native_rig', 'cooked_rig'))
    if job.get('fast_raster'):
        from realface_fast_raster import load
        import realface_mobile_geometry
        realface_mobile_geometry.raster = load(job['fast_raster'])
    obj = import_mesh(folder / 'input-hair.fbx')
    source = geometry(obj, native, cooked)
    original = pixels(job['source_profile']['hair_texture'])
    undercoat = paint_undercoat(source, original, base, folder / 'opaque-atlas.png')
    selected = np.flatnonzero(scalp_triangles(source[0], source[1]))
    if not len(selected):
        raise ValueError('No verified source scalp; use the independently screened short-hair route')
    local = [v.co[:] for v in obj.data.vertices]
    normals = np.asarray([[obj.data.corner_normals[i].vector[:] for i in tri.loops]
                          for tri in obj.data.loop_triangles])
    weights = [vertex_weights(obj, v) for v in obj.data.vertices]
    subset(obj, selected, source, local, normals, weights)
    scalp = geometry(obj, native, cooked)
    source_normals = capture_normals(obj, native, cooked)[2]
    request = json.loads((base / 'lite_skin-meshopt.json').read_text())
    skin = np.asarray(request['positions']).reshape(-1, 3)
    faces = np.asarray(json.loads((base / 'lite_skin-meshopt-result.json').read_text())['indices']).reshape(-1, 3)
    before, _ = audit(*scalp, original[:, :, 3], skin=(skin, faces))
    budget = int(job['hair_budget'])
    if budget < 32:
        raise ValueError('Insufficient remaining head budget for a joined scalp')
    import blender_realface_hair_volume as volume
    original_neighbours = volume.neighbours
    calls = {True: 0, False: 0}
    closing = int(job.get('closing_steps', 2))
    def bounded_closing(array, dilate):
        calls[dilate] += 1
        limit = closing + 1 if dilate else closing
        return original_neighbours(array, dilate) if calls[dilate] <= limit else array
    volume.neighbours = bounded_closing
    try:
        _, _, _, volume_proof = volume.prepare(obj, dict(job,
            budgets=dict(hair=budget, volume_closing_steps=3)), native, cooked)
    finally:
        volume.neighbours = original_neighbours
    volume_proof['closing_steps'] = closing
    # Compensate sampling dilation using the final scalp on its own. No loose
    # source cards are allowed to hide gaps in this route's silhouette proof.
    points, triangles, uv = geometry(obj, native, cooked)
    radial = points - [0., 4., 173.]
    length = np.linalg.norm(radial, axis=1, keepdims=True)
    trials = []; best = None
    for distance in (0., .1, .2, .3):
        fitted = points - radial / np.maximum(length, 1.) * distance
        frames, _ = audit(fitted, triangles, uv, np.ones((128, 128)), reference=before)
        comparison = compare(before, frames)
        score = (composite_ok(comparison), comparison['silhouette_iou_min'],
                 comparison['silhouette_iou_mean'], -distance)
        trials.append(dict(inset_cm=distance, projection=comparison))
        if best is None or score > best[0]:
            best = (score, fitted, distance, comparison)
        if composite_ok(comparison):
            break
    for vertex, point in zip(obj.data.vertices, best[1]):
        vertex.co = runtime_matrix(obj, vertex_weights(obj, vertex), native, cooked).inverted() @ Vector(point)
    shading = transfer_normals(obj, native, cooked, volume.LAST_SURFACE)
    cleanup = clean_generated_base(obj, native, cooked)
    colour = detail(obj, scalp, original, source_normals, native, cooked, folder)
    geometry_before_export = geometry(obj, native, cooked)
    reference = triangle_records(geometry_before_export, [vertex_weights(obj, v) for v in obj.data.vertices])
    allocated = count(obj)
    export_only(folder / 'hair.fbx', next(m.object for m in obj.modifiers if m.type == 'ARMATURE'), [obj])
    reimport = roundtrip(folder / 'hair.fbx', native, cooked, allocated, 'lite_hair', reference)
    face_count = int(job['face_triangles'])
    total = face_count + reimport['triangles']
    if total > 2000:
        raise ValueError('Joined scalp exceeds the complete-head limit')
    # Export can remove exact zero-area corners. Validate the actual exported
    # mesh as well as the pre-export surface against the original scalp.
    actual = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
    after, _ = audit(*geometry(actual, native, cooked), pixels(folder / 'hair-shell.png')[:, :, 3], reference=before)
    projection = compare(before, after)
    (folder / 'joined-scalp-proof.json').write_text(json.dumps(dict(
        face_triangles=face_count, hair_triangles=reimport['triangles'], total_triangles=total,
        sections=2, original_face_fbx_unchanged=True, undercoat=undercoat, volume=volume_proof,
        silhouette_fit=trials, selected_inset_cm=best[2], cleanup=cleanup, shading=shading,
        source_clump_colour=colour, exported_fbx_reimport=reimport,
        composite_scalp_projection=projection, visual_approved=False, hardware_profiled=False), indent=2) + '\n')


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text()))

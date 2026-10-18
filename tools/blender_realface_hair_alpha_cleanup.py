"""Prune only alpha-invisible, unsupported bindings in an isolated hair copy."""
import json
from pathlib import Path
import shutil
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import rig_globals
from blender_fit_realface import vertex_weights
from blender_realface_mobile import geometry, pixels
from blender_realface_native_hair_worker import subset, export_only, triangle_records
from realface_hair_alpha_cleanup import invisible_bindings
from realface_triangle_audit import surviving_triangles


def run(job):
    folder = Path(job['folder'])
    native, cooked = (rig_globals(json.loads(Path(job[k]).read_text()))
                      for k in ('native_rig', 'cooked_rig'))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.scale_length = .01
    copied = folder / 'source.fbx'
    shutil.copy2(job['hair_fbx'], copied)
    bpy.ops.import_scene.fbx(filepath=str(copied), use_anim=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    arms = {m.object for o in meshes for m in o.modifiers if m.type == 'ARMATURE'}
    if not meshes or len(arms) != 1:
        raise ValueError('Cleanup requires one verified source hair rig')
    arm = next(iter(arms))
    if {b.name for b in arm.data.bones} != set(native):
        raise ValueError('Source hair rig differs from the native contract')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes: obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1: bpy.ops.object.join()
    obj = bpy.context.object
    source = geometry(obj, native, cooked)
    weights = [vertex_weights(obj, v) for v in obj.data.vertices]
    alphas = [pixels(job['hair_texture'])[:, :, 3], pixels(str(folder / 'runtime-hair.png'))[:, :, 3]]
    removed, proof = invisible_bindings(source[1], source[2], weights, alphas)
    if proof['potentially_visible_triangles']:
        raise ValueError('Unsupported source bindings include potentially visible triangles')
    if not len(removed): raise ValueError('No alpha-invisible source binding repair needed')
    keep = np.setdiff1d(np.arange(len(source[1])), removed)
    if not len(keep): raise ValueError('Cleanup cannot turn a source head into an empty hair slot')
    local = [v.co[:] for v in obj.data.vertices]
    normals = np.asarray([[obj.data.corner_normals[i].vector[:] for i in tri.loops]
                          for tri in obj.data.loop_triangles])
    subset(obj, keep, source, local, normals, weights)
    clean = geometry(obj, native, cooked)
    clean_weights = [vertex_weights(obj, v) for v in obj.data.vertices]
    if any(set(w) - {'sk_head', 'sk_neck', 'sk_chest'} for w in clean_weights):
        raise ValueError('An unsupported binding survived alpha cleanup')
    reference = triangle_records((source[0], source[1][keep], source[2][keep]), weights)
    proof['retained_triangles'] = len(keep)
    proof['retained_surface'] = surviving_triangles(reference, triangle_records(clean, clean_weights), position_limit=.0002)
    output = folder / 'hair.fbx'
    export_only(output, arm, [obj])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.scale_length = .01
    bpy.ops.import_scene.fbx(filepath=str(output), use_anim=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if len(meshes) != 1: raise ValueError('Source cleanup FBX has duplicated sections')
    obj = meshes[0]
    actual = geometry(obj, native, cooked)
    actual_weights = [vertex_weights(obj, v) for v in obj.data.vertices]
    if len(actual[1]) != len(keep): raise ValueError('Source cleanup export lost a retained triangle')
    proof['exported_surface'] = surviving_triangles(reference, triangle_records(actual, actual_weights), position_limit=.002)
    proof.update(face_edited=False, original_source_edited=False, empty_hair_created=False)
    (folder / 'cleanup-proof.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
    print(json.dumps(proof), flush=True)


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8')))

"""Recover joined hair detail offline without changing a verified face/mesh.

The input is an identity-pinned, previously validated mobile head. Its original
source supplies colour relief, never a different player's scalp or geometry.
Appearance approval remains separate from this conversion.
"""
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import rig_globals
from blender_realface_mobile import geometry
from blender_realface_native_hair_bake import relief
from blender_realface_native_hair_detail import fresh_pixels
from blender_realface_source_quality import capture_normals


def import_mesh(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.scale_length = .01
    bpy.ops.import_scene.fbx(filepath=str(path), use_anim=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not meshes:
        raise ValueError('No source hair mesh')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    return bpy.context.object


def run(job):
    folder = Path(job['folder'])
    native, cooked = (rig_globals(json.loads(Path(job[k]).read_text()))
                      for k in ('native_rig', 'cooked_rig'))
    source_obj = import_mesh(folder / 'input-hair.fbx')
    source = geometry(source_obj, native, cooked)
    _, _, normals = capture_normals(source_obj, native, cooked)
    obj = import_mesh(folder / 'hair.fbx')
    before = geometry(obj, native, cooked)
    alpha = fresh_pixels(folder / 'hair-shell.png')[:, :, 3].copy()
    proof = relief(obj, source, job['source_profile']['hair_texture'], normals,
                   native, cooked, folder)
    # Radial surfaces can contain the beard and intentional hairline masks.
    # The opaque-scalp baker must never fill these cuts as solid polygons.
    pixels = fresh_pixels(folder / 'hair-shell.png')
    pixels[:, :, 3] = alpha
    texture = bpy.data.images.new('recovered_hair_preserved_coverage', 128, 128, alpha=True)
    texture.alpha_mode = 'CHANNEL_PACKED'
    texture.pixels.foreach_set(pixels.ravel())
    texture.filepath_raw = str(folder / 'hair-shell.png')
    texture.file_format = 'PNG'
    texture.save()
    after = geometry(obj, native, cooked)
    if not all((a == b).all() for a, b in zip(before, after)):
        raise ValueError('Offline relief unexpectedly changed geometry or UVs')
    proof.update(mesh_unchanged=True, face_edited=False, source_alpha_preserved=True,
                 visual_approved=False)
    (folder / 'relief-proof.json').write_text(json.dumps(proof, indent=2) + '\n')


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text()))

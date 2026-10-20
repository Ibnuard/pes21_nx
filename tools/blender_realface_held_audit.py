"""Read-only native-space audit of held source hair; inputs remain immutable."""
import json
from pathlib import Path
import shutil
import sys
from collections import Counter

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import rig_globals
from blender_fit_realface import vertex_weights
from blender_realface_mobile import geometry, pixels, source_views


def audit(job):
    folder = Path(job['folder']); folder.mkdir(parents=True, exist_ok=True)
    profile = job['source_profile']
    native, cooked = (rig_globals(json.loads(Path(job[k]).read_text()))
                      for k in ('native_rig', 'cooked_rig'))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.scale_length = .01
    copied = folder/'source-hair.fbx'
    shutil.copy2(profile['hair_fbx'], copied)
    bpy.ops.import_scene.fbx(filepath=str(copied), use_anim=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.object
    p, t, uv = geometry(obj, native, cooked)
    alpha = pixels(profile['hair_texture'])[:, :, 3]
    frames, visible = source_views((p, t, uv), alpha, job)
    area = np.linalg.norm(np.cross(p[t[:, 1]]-p[t[:, 0]], p[t[:, 2]]-p[t[:, 0]]), axis=1)
    bindings = [vertex_weights(obj, v) for v in obj.data.vertices]
    groups = Counter(tuple(sorted(b.items())) for b in bindings)
    np.savez_compressed(folder/'source-geometry.npz', positions=p, triangles=t, uv=uv, alpha=alpha)
    (folder/'source-bindings.json').write_text(json.dumps(bindings)+'\n')
    lower = (p[:, 2] < 170) & (p[:, 1] > 5) & (np.abs(p[:, 0]) < 9)
    result = dict(base_id=job['base_id'], name=job['name'], vertices=len(p), triangles=len(t),
                  materials=profile.get('hair_materials'),
                  bounds=[p.min(axis=0).tolist(), p.max(axis=0).tolist()],
                  max_extent_cm=float(np.ptp(p, axis=0).max()),
                  max_area2_cm2=float(area.max()), alpha_max=float(alpha.max()),
                  alpha_visible_pixels=int((alpha > .333).sum()),
                  uv_bounds=[uv.min(axis=(0, 1)).tolist(), uv.max(axis=(0, 1)).tolist()],
                  visible_triangles=len(visible),
                  locked_vertices=int(lower.sum()),
                  locked_triangles=int(lower[t].any(axis=1).sum()),
                  binding_groups=[dict(weights=dict(k), vertices=v) for k, v in groups.most_common(8)],
                  binding_group_count=len(groups),
                  bindings=[vertex_weights(obj, v) for v in obj.data.vertices] if len(p) < 20 else None,
                  positions=p.tolist() if len(p) < 20 else None,
                  uv=uv.tolist() if len(p) < 20 else None,
                  source_unchanged=True)
    (folder/'audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=True), flush=True)
    return result


if __name__ == '__main__':
    request = json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8'))
    results = [audit(job) for job in request['jobs']]
    Path(request['output']).write_text(json.dumps(results, indent=2)+'\n')

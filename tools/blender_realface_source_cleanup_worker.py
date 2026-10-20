"""Remove only exact zero-area source sentinels that pollute hair audit bounds."""
import json
from pathlib import Path
import runpy
import sys

import bpy
import bmesh
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
import blender_realface_mobile as mobile
from blender_fit_realface import vertex_weights
from realface_zero_area_policy import zero_area_in_every_pose

original=mobile.prepare_hair


def prepare(obj,job,native,cooked):
    if not job['budgets'].get('cleanup_exact_zero_area_outliers'):
        return original(obj,job,native,cooked)
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
    p,t,uv=mobile.geometry(obj,native,cooked)
    outside=(np.abs(p)>1000).any(axis=1)
    candidates=np.flatnonzero(outside[t].any(axis=1))
    if not len(candidates):raise ValueError('No exact far-away source sentinels to repair')
    for index in candidates:
        ids=t[index]
        if not zero_area_in_every_pose([obj.data.vertices[i].co[:] for i in ids],
                [vertex_weights(obj,obj.data.vertices[i]) for i in ids]):
            raise ValueError('Far-away source triangle is not proven zero-area in every pose')
    polys={obj.data.loop_triangles[i].polygon_index for i in candidates}
    bm=bmesh.new();bm.from_mesh(obj.data);bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index in polys],context='FACES')
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bm.to_mesh(obj.data);bm.free()
    after,_,_=mobile.geometry(obj,native,cooked)
    if not len(after) or (np.abs(after)>1000).any():raise ValueError('Unrepaired source outliers remain')
    proof=dict(policy='exact_zero_area_weighted_source_sentinel_v1',triangles_removed=len(candidates),
               source_max_coordinate_cm=float(np.abs(p).max()),
               remaining_max_coordinate_cm=float(np.abs(after).max()),
               visible_source_removed=False,zero_area_in_every_pose=True,source_skin_changed=False)
    (Path(job['folder'])/'source-cleanup-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return original(obj,job,native,cooked)


mobile.prepare_hair=prepare
runpy.run_path(str(Path(__file__).with_name('blender_realface_budget_worker.py')),run_name='__main__')

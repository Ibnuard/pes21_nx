"""Use the standard budget worker with a strictly verified existing empty slot."""
from pathlib import Path
import json
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import blender_realface_mobile as mobile
from blender_fit_realface import vertex_weights
from realface_empty_slot_policy import verified_empty_slot

original_prepare, original_finish = mobile.prepare_hair, mobile.finish_hair


def prepare(obj, job, native, cooked):
    if not job['budgets'].get('verified_empty_hair_slot'):
        return original_prepare(obj, job, native, cooked)
    profile = job['source_profile']
    if profile.get('hair_skin_materials'):
        raise ValueError('A skin surface cannot be treated as an empty hair slot')
    p, t, uv = mobile.geometry(obj, native, cooked)
    alpha = mobile.pixels(profile['hair_texture'])[:, :, 3]
    proof = verified_empty_slot(p.tolist(), t.tolist(), float(np.max(alpha)),
                                profile.get('hair_materials'),
                                [vertex_weights(obj, v) for v in obj.data.vertices])
    before, visible = mobile.source_views((p, t, uv), alpha, job)
    if visible:
        raise ValueError('A verified empty slot cannot contain visible source triangles')
    Path(job['folder'], 'empty-slot-proof.json').write_text(json.dumps(proof, indent=2))
    return before, alpha, 0, dict(mode='verified_empty_slot', source_positions=p.tolist(),
                                 source_uv=uv.tolist(), proof=proof)


def finish(obj, job, native, cooked, reference):
    method = reference[3]
    if method.get('mode') != 'verified_empty_slot':
        return original_finish(obj, job, native, cooked, reference)
    p, t, uv = mobile.geometry(obj, native, cooked)
    profile = job['source_profile']
    verified_empty_slot(p.tolist(), t.tolist(), float(np.max(reference[1])),
                        profile.get('hair_materials'), [vertex_weights(obj, v) for v in obj.data.vertices])
    source = np.asarray(method['source_positions'])
    distance = np.linalg.norm(p[:, None, :]-source[None, :, :], axis=2)
    if max(np.max(np.min(distance, axis=0)), np.max(np.min(distance, axis=1))) > .0002:
        raise ValueError('Empty-slot source positions changed')
    if not np.allclose(uv, np.asarray(method['source_uv']), atol=1e-6, rtol=0):
        raise ValueError('Empty-slot source UV changed')
    after, visible = mobile.source_views((p, t, uv), reference[1], job)
    if visible or any(np.any(frame['mask']) for frame in after):
        raise ValueError('Empty-slot reduction introduced visible hair')
    result = dict(silhouette_iou_min=1.0, silhouette_iou_mean=1.0, missing_coverage_max=0.0,
                  card_fragments_before=0, card_fragments_after=0,
                  alpha_fragments_before=0, alpha_fragments_after=0,
                  views=13, method=dict(mode='verified_empty_slot', proof=method['proof']),
                  invisible_triangles_removed=0, hardware_profiled=False)
    Path(job['folder'], 'hair-projection.json').write_text(json.dumps(result, indent=2))
    return result


mobile.prepare_hair, mobile.finish_hair = prepare, finish
runpy.run_path(str(Path(__file__).with_name('blender_realface_budget_worker.py')), run_name='__main__')

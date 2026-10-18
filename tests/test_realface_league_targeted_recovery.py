import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from realface_league_targeted_recovery import candidates


def test_near_hair_failure_uses_few_bounded_reallocations():
    proof = dict(silhouette_iou_min=.83, silhouette_iou_mean=.87, missing_coverage_max=.155)
    row = dict(attempts=[dict(level=57, reason='Hair silhouette held: '+json.dumps(proof))])
    result = candidates(row)
    assert 1 < len(result) <= 5
    assert all(r['head_cap'] == 2000 and r['face_skin'] >= 1200 for r in result)
    assert all(sum(r[k] for k in ('face_skin','eye','hair')) <= 2000 for r in result)
    assert all(r['native_seam_alias'] and r['normal_export_recovery'] for r in result)


def test_bad_aperture_uses_original_globes_without_relaxing_eye_distance():
    rows = candidates(dict(attempts=[dict(reason='Pupil lies outside a usable eyelid aperture')]))
    assert all(r['source_eye_policy'] == 'original_lod' and r['eye_error_cm'] == .06 for r in rows)

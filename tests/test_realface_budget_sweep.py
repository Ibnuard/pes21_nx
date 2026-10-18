"""Bounded geometry allocation keeps accepted hair policies and quality gates."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_budget_sweep import distribution,retryable
from realface_budget_experiment import effective_allocation,allocation


@pytest.mark.parametrize('cap',[4500,5000])
@pytest.mark.parametrize('skin',[3000,2800,2600])
@pytest.mark.parametrize('locked',[False,True])
def test_redistribution_preserves_eye_neck_uv_policy_and_explicit_hair_lock(cap,skin,locked):
    override=distribution(cap,skin,locked)
    config=dict(experimental_head_cap=cap,experimental_allocations={'162114':override})
    budget=effective_allocation(config,162114)
    assert budget['face_skin']+budget['eye']+budget['hair']+20==cap
    assert budget['hair_face_lock'] is locked
    for key in ('eye','skin_error_cm','eye_error_cm','skin_uv_weight','skin_normal_weight',
                'skin_feature_policy','native_seam_alias','source_eye_policy'):
        assert budget[key]==allocation(cap)[key]
    if locked:assert budget['hair_error_cm']==.45 and budget['hair_uv_weight']==.5
    assert 'hair_face_lock' not in effective_allocation(config,119835)


def test_face_quality_failures_do_not_retry_by_lowering_detail():
    assert retryable(dict(status='held_geometry',reason='Experimental complete head cap exceeded: 5091'))
    assert retryable(dict(status='held_geometry',reason='Hair silhouette held'))
    assert not retryable(dict(status='held_geometry',reason='Visible face UV distortion held'))
    assert not retryable(dict(status='held_geometry',reason='Surface quality held face/skin'))
    assert not retryable(dict(status='prepared',reason='Hair silhouette held'))


@pytest.mark.parametrize('changes',[dict(face_skin=2000),dict(hair=99999),dict(hair_face_lock=1),dict(skin_error_cm=99)])
def test_caller_cannot_relax_thresholds_or_restore_2k_policy(changes):
    override=dict(distribution(5000,3000,False),**changes)
    with pytest.raises(ValueError,match='bounded experimental'):
        effective_allocation(dict(experimental_head_cap=5000,experimental_allocations={'1':override}),1)

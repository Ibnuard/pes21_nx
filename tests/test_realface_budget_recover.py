from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from realface_budget_experiment import allocation
from realface_budget_recover import hair_hold, reallocate


def test_reallocation_preserves_cap_and_quality_thresholds():
    original = allocation(6000)
    for skin in (3000,2600):
        result = reallocate(original, skin)
        assert result['head_cap'] == 6000
        assert result['face_skin']+result['hair']+result['eye']+20 == 6000
        assert {k:v for k,v in result.items() if k not in ('face_skin','hair')} == {
            k:v for k,v in original.items() if k not in ('face_skin','hair')}
    assert original['face_skin'] == 3900
    with pytest.raises(ValueError): reallocate(allocation(4500),3000)


def test_only_coverage_holds_are_retried():
    assert hair_hold(dict(status='held_geometry',reason='Hair silhouette held: {}'))
    assert hair_hold(dict(status='held_geometry',reason='Card gaps require a separate joined-hair experiment'))
    assert not hair_hold(dict(status='held_geometry',reason='Face anatomy error'))
    assert not hair_hold(dict(status='prepared',reason='Hair silhouette held'))

"""Budget trials must not silently relax quality or production scope."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from realface_budget_experiment import allocation, isolated_config, validate_preparation, ROOT


def projection(**changes):
    return dict(silhouette_iou_min=.9, silhouette_iou_mean=.95, missing_coverage_max=.05,
                card_fragments_before=100, card_fragments_after=70,
                method=dict(mode='visible_cards'), **changes)


def test_only_skin_and_hair_allowance_change_with_cap():
    rows = [allocation(cap) for cap in (3000,4500,6000)]
    constant = [{k:v for k,v in row.items() if k not in ('head_cap','face_skin','hair')} for row in rows]
    assert constant[0] == constant[1] == constant[2]
    for row in rows:
        assert row['face_skin']+row['eye']+row['hair'] <= row['head_cap']
        assert row['native_seam_alias'] and row['source_eye']
    assert rows[0]['face_skin'] < rows[1]['face_skin'] < rows[2]['face_skin']
    assert rows[0]['hair'] < rows[1]['hair'] < rows[2]['hair']


@pytest.mark.parametrize('cap', [2000,3001,4501,10000])
def test_unplanned_budget_rejected(cap):
    with pytest.raises(ValueError, match='Experimental cap'):
        allocation(cap)


def test_experimental_ceiling_is_checked_not_legacy_2k():
    assert validate_preparation(dict(total_triangles=4499),projection(),4500) == 4499
    with pytest.raises(ValueError, match='explicit experimental ceiling'):
        validate_preparation(dict(total_triangles=4501),projection(),4500)


def test_explicit_7k_exception_keeps_the_same_face_allowance():
    ordinary,exception=allocation(6000),allocation(7000)
    assert ordinary['face_skin']==exception['face_skin']==3900
    assert exception['hair']-ordinary['hair']==1000
    assert validate_preparation(dict(total_triangles=6932),projection(),7000)==6932
    with pytest.raises(ValueError,match='ceiling'):
        validate_preparation(dict(total_triangles=7001),projection(),7000)


def test_5k_keeps_45k_face_and_uses_extra_allowance_for_hair():
    low, candidate = allocation(4500), allocation(5000)
    assert low['face_skin'] == candidate['face_skin'] == 3000
    assert candidate['hair']-low['hair'] == 500
    assert {k:v for k,v in low.items() if k not in ('head_cap','hair')} == {
        k:v for k,v in candidate.items() if k not in ('head_cap','hair')}
    assert validate_preparation(dict(total_triangles=4999),projection(),5000)==4999
    with pytest.raises(ValueError,match='ceiling'):
        validate_preparation(dict(total_triangles=5001),projection(),5000)


@pytest.mark.parametrize('field,value,message', [
    ('silhouette_iou_min',.79,'silhouette'),
    ('silhouette_iou_mean',.84,'silhouette'),
    ('missing_coverage_max',.13,'Card gaps'),
    ('missing_coverage_max',.16,'silhouette'),
    ('card_fragments_after',106,'workload'),
])
def test_existing_hair_quality_gates_remain(field,value,message):
    proof=projection();proof[field]=value
    with pytest.raises(ValueError, match=message):
        validate_preparation(dict(total_triangles=2800),proof,3000)


def test_output_keeps_production_config_unchanged():
    source=dict(work_dir='production-work',cache_dir='production-cache')
    candidate=isolated_config(source,ROOT/'local-debug'/'budget-test',3000)
    assert source == dict(work_dir='production-work',cache_dir='production-cache')
    assert Path(candidate['work_dir']).name == '3000'
    assert Path(candidate['cache_dir']).name == 'cache'
    with pytest.raises(ValueError, match='dedicated ignored'):
        isolated_config(source,ROOT/'dist',3000)

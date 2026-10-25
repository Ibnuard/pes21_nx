"""Source receipts cannot turn arbitrary geometry into roof-end backing."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stadium_backing import select_upright_panel, select_source_surface, backing_budget_allowed


def receipt(**changes):
    args=dict(positions=[[65,19,44],[75,19,44],[75,31,44],[65,27,44]],
              indices=[[0,1,2],[0,2,3]],panel_indices=[0,1],
              expected_bounds=[[65,19,44],[75,31,44]],plane_axis=2,plane_m=44.)
    args.update(changes)
    return args


def test_irregular_source_end_panel_faces_inward():
    rows=select_upright_panel(**receipt())
    assert len(rows)==2 and all(r['normal'][2]<0 for r in rows)
    assert {r['source_triangle'] for r in rows}=={0,1}


@pytest.mark.parametrize('changes',[
    dict(panel_indices=[0,0]),dict(panel_indices=[2]),dict(plane_m=45.),
    dict(expected_bounds=[[65,19,44],[76,31,44]]),dict(plane_axis=1),
    dict(positions=[[0,19,0],[10,19,0],[10,31,0],[0,27,0]],
         expected_bounds=[[0,19,0],[10,31,0]],plane_m=0.),
    dict(positions=[[65,19,44],[75,19,44],[75,31,45],[65,27,44]]),
])
def test_changed_or_unreviewed_panel_rejected(changes):
    with pytest.raises(ValueError):select_upright_panel(**receipt(**changes))


def test_source_roof_sheet_keeps_positions_and_faces_interior():
    args=dict(positions=[[60,20,44],[70,20,44],[70,22,54]],indices=[[0,2,1]],
              surface_indices=[0],expected_bounds=[[60,20,44],[70,22,54]],orientation='roof_underside')
    rows=select_source_surface(**args)
    assert rows[0]['normal'][1]<0
    assert sorted(rows[0]['positions'])==sorted(args['positions'])
    with pytest.raises(ValueError):select_source_surface(**dict(args,surface_indices=[0,0]))
    with pytest.raises(ValueError):select_source_surface(**dict(args,orientation='outer_wall'))
    with pytest.raises(ValueError):select_source_surface(**dict(args,expected_bounds=[[60,20,44],[71,22,54]]))


def test_source_roof_cannot_cover_playing_surface():
    with pytest.raises(ValueError):select_source_surface(
        [[0,20,0],[10,20,0],[10,20,10]],[[0,1,2]],surface_indices=[0],
        expected_bounds=[[0,20,0],[10,20,10]],orientation='roof_underside')


def test_fox_clockwise_source_repair_preserves_source_plane():
    rows=select_source_surface([[65,1,44],[75,1,44],[75,5,44]],[[0,1,2]],surface_indices=[0],
        expected_bounds=[[65,1,44],[75,5,44]],orientation='source_clockwise')
    assert rows[0]['positions']==[[65.,1.,44.],[75.,5.,44.],[75.,1.,44.]]
    assert rows[0]['winding_flipped']


def test_roof_budget_exception_is_explicit_and_bounded():
    r=dict(key='OldTrafford',maximum_total_triangles=25320,
           source_roof_completion=dict(native_reference=24560,maximum_extra_triangles=760))
    assert backing_budget_allowed(r,24522,781)
    assert not backing_budget_allowed(dict(r,key='CampNou'),24522,595)
    assert not backing_budget_allowed(dict(r,maximum_total_triangles=25321),24522,595)
    assert not backing_budget_allowed(dict(r,source_roof_completion={}),24522,595)
    assert not backing_budget_allowed(r,24521,595)
    assert not backing_budget_allowed(r,24522,799)
    assert backing_budget_allowed(dict(key='CampNou',maximum_total_triangles=24560),24328,130)

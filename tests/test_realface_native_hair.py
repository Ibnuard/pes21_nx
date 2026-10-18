import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from audit_realface_native_hair import topology
from realface_native_hair_cards import card_groups,select_cards,composite_ok,scalp_triangles,opaque_atlas_slot,inset_bulk


def test_scalp_inset_is_bounded_and_does_not_mutate_source_coordinates():
    source = np.array([[0.,4.,183.], [10.,4.,173.], [0.,14.,173.]])
    original = source.copy()
    result = inset_bulk(source,.30)
    assert np.allclose(np.linalg.norm(result-source,axis=1),.30)
    assert np.array_equal(source,original)
    assert np.array_equal(inset_bulk(source,0),original)
    for value in (-.1,.46):
        with pytest.raises(ValueError,match='0..0.45'):inset_bulk(source,value)


def test_native_bulk_uses_real_atlas_resolution_without_touching_skin_or_eyes():
    for size in (128, 256):
        factor = size / 256
        tiles = {key: dict(destination_bounds=(np.asarray(bounds) * factor).tolist()) for key, bounds in
                 dict(skin=[[4,4],[188,252]], eye=[[196,196],[252,252]]).items()}
        slot = opaque_atlas_slot(size, tiles)
        assert np.array_equal(slot, np.asarray([[196,4],[252,188]]) * size // 256)
        assert (slot >= 0).all() and (slot <= size).all()
        with pytest.raises(ValueError, match='overlaps'):
            opaque_atlas_slot(size, dict(tiles, conflict=dict(destination_bounds=slot.tolist())))
    with pytest.raises(ValueError, match='128 or 256'):
        opaque_atlas_slot(64, {})


def test_native_strip_audit_distinguishes_disconnected_cards_from_closed_head():
    points=[[0,0,0],[1,0,0],[1,1,0],[0,1,0],
            [0,0,1],[1,0,1],[1,1,1],[0,1,1]]
    faces=[[0,1,2],[0,2,3],[4,5,6],[4,6,7]]
    proof=topology(points,faces)
    assert proof['triangles']==4
    assert proof['connected_components']==2
    assert proof['largest_component_triangles']==2
    assert proof['component_triangle_histogram']=={2:2}


def test_card_selection_preserves_whole_adjacent_pair_and_strict_remainder():
    tri=np.array([[0,1,2],[0,2,3],[4,5,6],[4,6,7]])
    original=tri.copy()
    frame=dict(front=np.array([[2,2,2],[2,3,3],[2,3,3]]))
    selected,proof=select_cards(tri,[frame],2)
    assert selected.tolist()==[2,3]
    assert np.array_equal(tri,original)
    assert proof['selected_triangles']<=2
    assert proof['selected_front_pixels']==9
    assert card_groups(tri)==[(0,1),(2,3)]
    assert not proof['visual_approval']


def test_no_unseen_cards_or_budget_overflow_and_stable_order():
    tri=np.arange(18).reshape(-1,3)
    frame=dict(front=np.array([[0,1,2],[-1,-1,-1]]))
    a,_=select_cards(tri,[frame],2);b,_=select_cards(tri,[frame],2)
    assert a.tolist()==b.tolist()
    assert len(a)==2 and set(a)<=set((0,1,2))
    empty,_=select_cards(tri,[dict(front=np.full((2,2),-1))],2)
    assert not len(empty)
    for budget in (0,2001,-1):
        with pytest.raises(ValueError,match='ceiling'):select_cards(tri,[frame],budget)


def test_facial_hair_neighbor_cannot_return_with_a_visible_scalp_card():
    tri=np.array([[0,1,2],[0,2,3],[4,5,6],[4,6,7]])
    frame=dict(front=np.array([[0,0,0],[0,0,2],[2,3,3]]))
    selected,_=select_cards(tri,[frame],4,eligible=[True,False,True,True])
    assert selected.tolist()==[2,3]


def test_composite_gate_does_not_accept_missing_coverage_or_partial_views():
    passing=dict(views=13,silhouette_iou_min=.80,silhouette_iou_mean=.85,missing_coverage_max=.15)
    assert composite_ok(passing)
    assert not composite_ok(None)
    for key,value in (('views',8),('silhouette_iou_min',.799),('silhouette_iou_mean',.849),('missing_coverage_max',.151)):
        assert not composite_ok(dict(passing,**{key:value}))


def test_long_scalp_lock_is_not_removed_as_beard_at_neck_height():
    # One lock runs continuously from crown to below the neck. A detached
    # short front-jaw triangle and eyebrow belong in the opaque face texture.
    p=np.array([[8,3,183],[9,3,178],[8,4,165],[9,4,154],
                [1,10,163],[2,11,164],[1,11,165],
                [2,13,172],[4,13,172],[3,13,173]],float)
    tri=np.array([[0,1,2],[1,2,3],[4,5,6],[7,8,9]])
    assert scalp_triangles(p,tri).tolist()==[True,True,False,False]

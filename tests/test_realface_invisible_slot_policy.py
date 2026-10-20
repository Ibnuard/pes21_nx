from pathlib import Path
import sys
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_invisible_slot_policy import verified_invisible_cards,rigid_pose_diameters


def source():
    return dict(positions=[(0,4,174),(1,4,174),(0,5,174)],triangles=[[0,1,2]],
                uv=[[(.2,.2),(.3,.2),(.2,.3)]],alpha=np.zeros((16,16)),
                bindings=[{'sk_head':1.0}]*3,materials=['rf_hair'],hair_skin_materials=[],visible_triangles=0)


def test_alpha_proof_is_independent_of_pose_or_vertex_binding():
    s=source();s['bindings']=[{'sk_neck':1.0}]*3
    p=verified_invisible_cards(**s)
    assert p['alpha_hidden']==1 and not p['visible_source_removed']


def test_identical_rigid_microscopic_marker_is_distinct_from_visible_hair():
    s=source();s.update(positions=[(0,4,174),(.001,4,174),(0,4.001,174)],alpha=np.ones((16,16)))
    assert verified_invisible_cards(**s)['rigid_microscopic']==1
    s['bindings']=[{'sk_neck':1.0}]*3
    with pytest.raises(ValueError):verified_invisible_cards(**s)


@pytest.mark.parametrize('changes',[
    {'alpha':np.ones((16,16))},{'visible_triangles':1},{'hair_skin_materials':['rf_skin']},
    {'materials':['rf_skin']},{'positions':[(0,4,174),(float('nan'),4,174),(0,5,174)]}])
def test_raster_silence_alone_cannot_remove_visible_or_unproven_source(changes):
    with pytest.raises(ValueError):verified_invisible_cards(**dict(source(),**changes))


def test_alpha_proof_covers_neighboring_texels_and_uv_wrap():
    s=source();s['uv']=[[(-.001,.2),(.001,.2),(0,.21)]]
    s['alpha'][3,-1]=1
    with pytest.raises(ValueError):verified_invisible_cards(**s)


def test_equal_weight_marker_bound_is_valid_for_other_native_bones():
    s=source();local=np.asarray([(0,0,0),(.0001,0,0),(0,.0001,0)])
    weights=[{'sk_neck':.5,'sk_head':.5}]*3
    frames={n:np.eye(4) for n in weights[0]}
    bound=rigid_pose_diameters(local,s['triangles'],weights,frames,frames)
    assert bound[0]<.003
    s.update(positions=[(0,4,174)]*3,bindings=weights,alpha=np.ones((16,16)),pose_diameters=bound)
    assert verified_invisible_cards(**s)['rigid_microscopic']==1
    weights[2]={'sk_head':1.0}
    assert np.isinf(rigid_pose_diameters(local,s['triangles'],weights,frames,frames)[0])


def test_rigid_marker_bound_accounts_for_import_scale():
    local=[(0,0,0),(.001,0,0),(0,.001,0)]; weights=[{'sk_head':1.0}]*3
    transforms={'sk_head':np.diag((100,100,100,1))}
    assert rigid_pose_diameters(local,[[0,1,2]],weights,transforms,{'sk_head':np.eye(4)})[0]>.003


def test_pc_point_source_proof_cannot_call_visible_source_a_marker():
    from realface_source_empty_part import validate_source_part
    p=dict(policy='same_player_authored_empty_masked_part_v1',meshes=[
        dict(classification='authored_point',vertices=30,triangles=20,max_extent_cm=.000001)])
    assert validate_source_part(p)==p
    p['meshes'][0]['max_extent_cm']=.1
    with pytest.raises(ValueError):validate_source_part(p)


def test_buried_micro_source_requires_own_closed_skin_and_clearance():
    from realface_source_empty_part import buried_micro_source_mesh
    corners=np.asarray([(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                        (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)])
    faces=[[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],
           [1,5,6],[1,6,2],[2,6,7],[2,7,3],[3,7,4],[3,4,0]]
    assert buried_micro_source_mesh([(0,0,0),(.01,.01,0)],corners,faces)['inside_source_skin_rays']==5
    assert buried_micro_source_mesh([(2,0,0),(2.01,0,0)],corners,faces) is None
    assert buried_micro_source_mesh([(.95,0,0),(.96,0,0)],corners,faces) is None
    assert buried_micro_source_mesh([(0,0,0),(.2,0,0)],corners,faces) is None


def test_native_conversion_ghost_needs_complete_original_pc_empty_part_proof():
    s=source();s['visible_triangles']=5
    proof=dict(policy='same_player_authored_empty_masked_part_v1',meshes=[
        dict(classification='authored_point',vertices=30,triangles=20,max_extent_cm=.000001)])
    result=verified_invisible_cards(**s,source_part_proof=proof)
    assert result['rejected_native_conversion_visible_triangles']==5
    assert result['projection_reference']=='verified_empty_PC_source_part'
    proof['meshes'][0]['max_extent_cm']=1
    with pytest.raises(ValueError):verified_invisible_cards(**s,source_part_proof=proof)


def test_exact_degenerate_sentinel_cannot_include_different_skinning_or_thin_card():
    from realface_zero_area_policy import zero_area_in_every_pose
    p=[(0,0,-92966)]*3;b=[{'sk_head':1.0}]*3
    assert zero_area_in_every_pose(p,b)
    assert not zero_area_in_every_pose([(0,0,0),(1e-8,0,0),(0,1e-8,0)],b)
    assert not zero_area_in_every_pose([(0,0,0),(0,0,0),(1,1,1)],
                                      [{'sk_head':1.0},{'sk_neck':1.0},{'sk_head':1.0}])

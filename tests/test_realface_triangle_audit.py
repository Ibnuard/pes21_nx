from pathlib import Path
import sys
import copy
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_triangle_audit import surviving_triangles


def face(offset=0):
    return dict(points=[(offset,0,0),(offset+1,0,0),(offset,1,0)],
                uv=[(0,0),(1,0),(0,1)],weights=[{'head':1.}]*3)


def test_partial_collapsed_drop_still_proves_every_visible_triangle():
    collapsed=face();collapsed['points']=[(0,0,0)]*3
    source=[face(),face(3),collapsed,copy.deepcopy(collapsed)]
    result=surviving_triangles(source,[face(3),collapsed,face()])
    assert result['noncollapsed_source_triangles']==2
    assert result['connectivity_uv_weights_match']


def test_unchanged_vertex_pool_cannot_hide_changed_connectivity_or_duplicate_faces():
    source=[face(),face(3)]
    with pytest.raises(ValueError,match='cover every'):
        surviving_triangles(source,[face(),face()])
    bad=face();bad['points'][2]=(3,0,0)
    with pytest.raises(ValueError,match='connectivity'):
        surviving_triangles(source,[bad,face(3)])
    with pytest.raises(ValueError,match='count changed'):
        surviving_triangles(source,[face()])


@pytest.mark.parametrize('attribute',['uv','weights'])
def test_surface_proof_requires_uv_and_weights_on_the_same_triangle(attribute):
    bad=face()
    bad[attribute][0]=(0.3,0.5) if attribute=='uv' else {'chest':1.}
    with pytest.raises(ValueError,match='connectivity'):
        surviving_triangles([face()],[bad])


def test_signature_bin_boundary_does_not_hide_an_alternative_surface_match():
    source=[face(.000499),face(.000501)]
    cooked=[face(.0004992),face(.0004994)]
    assert surviving_triangles(source,cooked)['noncollapsed_source_triangles']==2

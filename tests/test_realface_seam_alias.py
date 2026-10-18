import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_seam_alias import canonical_positions


def test_seams_across_grid_boundary_share_simplifier_position_but_input_is_unchanged():
    original=[(0.00019,0.,170.),(.00021,0.,170.),(2.,0.,170.)]
    result,proof=canonical_positions(original,[(('head',1.),)]*3)
    assert result[0]==result[1] and result[2]==original[2]
    assert original[1][0]==.00021 and proof['aliased_vertices']==1
    assert proof['maximum_alias_cm']<=.0002


def test_aliases_preserve_skinning_and_cannot_chain_across_anatomical_points():
    points=[(0.,0.,170.),(.00015,0.,170.),(.00030,0.,170.),(.00007,0.,170.)]
    weights=[(('head',1.),)]*3+[(('neck',1.),)]
    result,proof=canonical_positions(points,weights)
    assert result[0]==result[1] and result[2]!=result[0]
    assert result[3]==points[3] and result[3]!=result[0]
    assert proof['aliased_vertices']==1
    with pytest.raises(ValueError):canonical_positions([(float('nan'),0,0)],[()])
    with pytest.raises(ValueError):canonical_positions(points,weights,tolerance=.01)

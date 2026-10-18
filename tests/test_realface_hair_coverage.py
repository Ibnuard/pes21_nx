import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_hair_coverage import compare_visibility


def test_exposed_scalp_inside_hairstyle_is_distinct_from_trimmed_edge():
    source=np.zeros((24,24),bool);source[3:21,3:21]=True
    skin=np.ones_like(source)
    edge=source.copy();edge[3,:]=False
    hole=source.copy();hole[10:14,10:14]=False
    assert compare_visibility(source,edge,skin)['interior_bald_pixels']==0
    assert compare_visibility(source,hole,skin)['interior_bald_pixels']==16
    # A removed hair tip over the background is not exposed scalp.
    assert compare_visibility(source,hole,np.zeros_like(source))['interior_bald_pixels']==0


def test_empty_source_scalp_is_not_a_missing_hairstyle():
    empty=np.zeros((12,12),bool)
    assert compare_visibility(empty,empty,np.ones_like(empty))['interior_bald_ratio']==0

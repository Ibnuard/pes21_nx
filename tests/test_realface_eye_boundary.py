from pathlib import Path
import sys
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_eye_boundary import opening_from_depth,rim_variants


def grid():
    xs=np.linspace(.8,5.6,81);zs=np.linspace(166,174,135)
    x,z=np.meshgrid(xs,zs)
    recess=2*np.exp(-((x-3)/1.3)**8-((z-170)/.48)**6)
    return xs,zs,16+.1*x+.05*(z-170)-recess


def test_skin_recess_finds_each_eye_without_guessing_or_changing_geometry():
    xs,zs,depth=grid();before=depth.copy()
    a=np.asarray(opening_from_depth(xs,zs,depth))
    b=np.asarray(opening_from_depth(-xs,zs,depth))
    assert (a.min(0)[0]+a.max(0)[0])/2==pytest.approx(3,abs=.08)
    assert (a.min(0)[2]+a.max(0)[2])/2==pytest.approx(170,abs=.08)
    assert b==pytest.approx(a*[-1,1,1])
    assert np.array_equal(before,depth)


def test_skin_scan_rejects_flat_nonfinite_ambiguous_or_open_recesses():
    xs,zs,depth=grid()
    for bad in (np.full_like(depth,16),depth*np.nan,
                np.minimum(depth,np.roll(depth,40,axis=0)),np.roll(depth,39,axis=1)):
        with pytest.raises(ValueError):opening_from_depth(xs,zs,bad)


def test_alternative_rims_keep_complete_optical_bounds_and_reject_flat_skin():
    xs,zs,depth=grid();variants=rim_variants(xs,zs,depth)
    original=np.asarray(variants[0]['bounds'])
    trimmed=next(v for v in variants if v['name']=='strict_central_rim')
    assert np.asarray(trimmed['bounds'])==pytest.approx(original)
    assert np.ptp(np.asarray(trimmed['rim'])[:,0])==pytest.approx(np.ptp(original[:,0])-.36)
    shallow=16+.1*np.meshgrid(xs,zs)[0]+(depth-16-.1*np.meshgrid(xs,zs)[0])*.4
    assert not any(v['name'].startswith('strict') for v in rim_variants(xs,zs,shallow))
    assert any(v['name'].startswith('shallow') for v in rim_variants(xs,zs,shallow))
    assert rim_variants(xs,zs,np.full_like(depth,16))==[]

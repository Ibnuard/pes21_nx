import sys
from pathlib import Path

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from realface_mobile_geometry import raster
from realface_fast_raster import load


def test_native_raster_matches_reference_for_alpha_wrap_occlusion_and_degenerates():
    dll=ROOT/'local-inputs/realface-raster-v1/realface_raster.dll'
    if not dll.exists():pytest.skip('Build optional local native raster fixture with tools/build_realface_raster.py')
    fast=load(dll);rng=np.random.default_rng(27)
    for i in range(12):
        p=rng.normal(size=(93,3));p[-3:]=0
        t=np.arange(93).reshape(-1,3);uv=rng.uniform(-2,3,(31,3,2));alpha=rng.random((8,16))
        basis=rng.normal(size=(3,3));skin=None if i%2 else rng.random((32,32))
        old=raster(p,t,uv,alpha,basis,size=32,skin_depth=skin)
        new=fast(p,t,uv,alpha,basis,size=32,skin_depth=skin)
        for name in ('front','mask','cards','opaque'):np.testing.assert_array_equal(old[name],new[name])
        np.testing.assert_allclose(old['depth'],new['depth'],atol=1e-12)

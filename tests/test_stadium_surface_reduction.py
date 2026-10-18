"""Exercise open-border coverage with synthetic UV-mapped floor geometry."""
import json
from pathlib import Path
import shutil
import subprocess
import pytest
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))


def test_stair_open_outline_survives_aggressive_target(tmp_path):
    module=ROOT/'local-inputs/meshoptimizer-tools-v1/node_modules/meshoptimizer/meshopt_simplifier.js'
    node=shutil.which('node')
    if not node or not module.is_file():pytest.skip('Optional local Node/meshoptimizer unavailable')
    positions=[];uv=[];indices=[]
    for y in range(5):
        for x in range(5):positions.extend((x,y,0));uv.extend((x/4,y/4))
    for y in range(4):
        for x in range(4):
            a=y*5+x;indices.extend((a,a+1,a+5,a+1,a+6,a+5))
    source=tmp_path/'in.json';output=tmp_path/'out.json'
    source.write_text(json.dumps(dict(materials=[dict(name='M_test_stairs',positions=positions,
        uv=uv,indices=indices)],ratio=.01,error=10)))
    subprocess.run([node,str(ROOT/'tools/meshopt_stadium_reduce.mjs'),str(module),str(source),str(output)],check=True)
    reduced=json.loads(output.read_text())[0]['indices']
    def boundary(values):
        from collections import Counter
        edges=Counter(tuple(sorted((values[i+j],values[i+(j+1)%3])))
                      for i in range(0,len(values),3) for j in range(3))
        return {e for e,n in edges.items() if n==1}
    assert boundary(indices)==boundary(reduced)
    area=0.
    for i in range(0,len(reduced),3):
        a,b,c=[positions[v*3:v*3+3] for v in reduced[i:i+3]]
        area+=abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2
    assert area==16


def test_stair_backing_preserves_source_hole_and_clearance():
    pytest.importorskip('shapely')
    from stadium_floor_underlay import build
    import numpy as np
    from shapely import Polygon,union_all
    # Four textured strips around a real opening; height follows a ramp.
    points=[];uv=[];indices=[]
    for x0,y0,x1,y1 in ((0,0,3,1),(0,2,3,3),(0,1,1,2),(2,1,3,2)):
        start=len(points)//3
        for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)):
            points.extend((x,y,2+y*.5));uv.extend((x,y))
        indices.extend(start+i for i in (0,1,2,0,2,3))
    result=build(dict(name='Synthetic stairs',positions=points,uv=uv,indices=indices),cell=1)
    p=np.array(result['positions']).reshape(-1,3);ix=np.array(result['indices']).reshape(-1,3)
    shape=union_all([Polygon(tri) for tri in p[ix,:2]])
    assert shape.area==pytest.approx(8)
    assert len(shape.interiors)==1
    assert np.allclose(p[:,2],2+p[:,1]*.5-.35)
    assert np.allclose(result['uv'],p[:,:2].reshape(-1))

"""Exercise open-border coverage with synthetic UV-mapped floor geometry."""
import json
from pathlib import Path
import shutil
import subprocess
import pytest
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))


def test_reviewed_venue_concrete_uses_fixed_border_scope_only():
    from stadium_surface_policy import protected_surface
    reviewed=('M_st051_cncr001_bsm_solid_one','M_st051_flor101_bsm_solid_one')
    assert all(protected_surface(name, reviewed) for name in reviewed)
    assert not protected_surface(reviewed[0])
    assert not protected_surface('M_unreviewed_cncr001_bsm_solid_one', reviewed)
    assert not protected_surface('M_unreviewed_flor101_bsm_solid_one', reviewed)
    assert protected_surface('M_original_star002_bsm_solid_one', reviewed)


def test_original_panels_are_source_bound_without_filling_openings():
    import numpy as np
    from stadium_surface_policy import preserved_source_faces
    p=np.array([[-40,-70,16],[40,-70,16],[40,-70,16.4],
                [0,-72,16.8],[1,-72,16.8],[1,-72,17],
                [0,-20,1],[1,-20,1],[1,-20,1.2]])
    ids=np.arange(9).reshape(-1,3)
    rules=[dict(kind='wide_panel',minimum_edge_m=30,minimum_area_m2=4,expected_source_triangles=1),
           dict(kind='upper_stair_band',minimum_height_m=16.7,maximum_height_m=17.1,
                minimum_source_z_m=71.9,maximum_source_z_m=72.1,expected_source_triangles=1)]
    assert preserved_source_faces(p,ids,rules)==[0,1]
    rules[0]['expected_source_triangles']=2
    with pytest.raises(ValueError,match='count changed'):
        preserved_source_faces(p,ids,rules)


def test_selected_riser_survives_clustering_with_exact_source_uvs(tmp_path):
    import numpy as np
    module=ROOT/'local-inputs/meshoptimizer-tools-v1/node_modules/meshoptimizer/meshopt_simplifier.js'
    node=shutil.which('node')
    if not node or not module.is_file():pytest.skip('Optional local Node/meshoptimizer unavailable')
    # A very wide, thin original riser behind disconnected small stair boxes.
    # Clustering may remove stair detail but must retain its structural cover.
    p=[[-40,0,0],[40,0,0],[40,0,.4],[-40,0,.4]]
    uv=[[0,0],[80,0],[80,.4],[0,.4]];ids=[0,1,2,0,2,3]
    for i in range(4100):
        x=(i%100)*.01;y=(i//100)*.01;offset=len(p)
        p.extend([[x,1+y,0],[x+.005,1+y,0],[x,1+y,.005]])
        uv.extend([[x,y],[x+.005,y],[x,y+.005]]);ids.extend([offset,offset+1,offset+2])
    source=tmp_path/'in.json';output=tmp_path/'out.json'
    row=dict(name='reviewed_riser',positions=np.array(p).reshape(-1).tolist(),
             uv=np.array(uv).reshape(-1).tolist(),indices=ids,preserve_triangles=[0,1])
    source.write_text(json.dumps(dict(materials=[row],ratio=.01,error=.5,cluster_relative_error=.008)))
    subprocess.run([node,str(ROOT/'tools/meshopt_stadium_reduce.mjs'),str(module),str(source),str(output)],check=True)
    result=json.loads(output.read_text())[0];tri=np.array(p)[np.array(result['indices']).reshape(-1,3)]
    # Both original triangles retain their actual source coordinates and UVs;
    # no replacement slab is invented across a neighbouring source opening.
    panel=tri[np.all(tri[:,:,1]==0,axis=1)]
    assert sum(np.linalg.norm(np.cross(t[1]-t[0],t[2]-t[0]))*.5 for t in panel)==pytest.approx(32)
    assert np.array(uv)[np.array(result['indices'][-6:])].tolist()==np.array(uv)[ids[:6]].tolist()
    assert result['preserved_source_triangles']==2
    row['preserve_triangles']=[999999]
    source.write_text(json.dumps(dict(materials=[row],ratio=.01,error=.5)))
    rejected=subprocess.run([node,str(ROOT/'tools/meshopt_stadium_reduce.mjs'),str(module),str(source),str(output)],capture_output=True)
    assert rejected.returncode!=0 and b'Invalid preserved source panels' in rejected.stderr


def test_central_access_keeps_both_source_stairways_with_bounded_selection():
    import numpy as np
    from stadium_surface_policy import preserved_source_faces
    # Blender basis: source lateral X, negated source Z, source height.
    # Two real access treads, adjacent seating, and a face crossing the edge.
    p=np.array([[-1,-45,1],[1,-45,1],[1,-45.2,1],
                [-1,45,2],[1,45,2],[1,45.2,2],
                [3,-45,1],[4,-45,1],[4,-45.2,1],
                [-1,-45,1],[1,-45,1],[1,-45.2,9]],dtype=float)
    ids=np.arange(12).reshape(-1,3)
    rule=dict(kind='central_stair_access',maximum_abs_source_x_m=1.51,
              minimum_height_m=-.01,maximum_height_m=4.7,
              minimum_abs_source_z_m=39.99,maximum_abs_source_z_m=51.01,
              expected_source_triangles=2)
    assert preserved_source_faces(p,ids,[rule])==[0,1]
    rule['expected_source_triangles']=3
    with pytest.raises(ValueError,match='count changed'):
        preserved_source_faces(p,ids,[rule])
    rule['maximum_abs_source_x_m']=10
    with pytest.raises(ValueError,match='access bounds'):
        preserved_source_faces(p,ids,[rule])


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

import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stadium_backing import select_triangles,load_selection,clip_floor_triangles


def wall(x=80.):
    return np.array([[x,0.,-2.],[x,10.,-2.],[x,10.,2.],[x,0.,2.]])


def test_only_matching_vertical_backing_and_inward_winding():
    p=np.concatenate((wall(),np.array([[80.,0.,4.],[84.,0.,4.],[84.,0.,8.]]),wall(82.)[:3]+[0,2,0]))
    rows=select_triangles(p,np.array([[0,1,2],[0,2,3],[4,5,6],[7,8,9]]),bottom_m=0,top_m=10,expected_triangles=2)
    assert [r['source_triangle'] for r in rows]==[0,1]
    assert all(np.dot(r['normal'],np.mean(r['positions'],axis=0))<0 for r in rows)


def test_field_intersection_fails_instead_of_filling_playable_space():
    with pytest.raises(ValueError,match='protected field'):
        select_triangles(wall(20.),np.array([[0,1,2],[0,2,3]]),bottom_m=0,top_m=10,expected_triangles=2)


def test_changed_source_selection_count_is_refused():
    with pytest.raises(ValueError,match='selection changed'):
        select_triangles(wall(),np.array([[0,1,2]]),bottom_m=0,top_m=10,expected_triangles=2)


@pytest.mark.parametrize('kind',['nan','index','fractional','oversized'])
def test_malformed_or_unbounded_input_is_refused(kind):
    p=wall();ids=np.array([[0,1,2],[0,2,3]]);expected=2
    if kind=='nan':p[0,0]=float('nan')
    if kind=='index':ids[0,0]=20
    if kind=='fractional':ids=ids.astype(float)+.1
    if kind=='oversized':expected=233
    with pytest.raises(ValueError):select_triangles(p,ids,bottom_m=0,top_m=10,expected_triangles=expected)


def test_source_and_buffer_binding_and_uv_winding(tmp_path):
    import json,hashlib
    positions=wall().astype('<f4');uv=np.array([[0,0],[0,1],[1,1],[1,0]],dtype='<f4')
    indices=np.array([0,1,2,0,2,3],dtype='<u2')
    raw=positions.tobytes()+uv.tobytes()+indices.tobytes()
    (tmp_path/'pane.bin').write_bytes(raw)
    doc=dict(asset=dict(generator='PES 2021 NX FMDL intermediate exporter'),nodes=[dict(mesh=0)],
        buffers=[dict(uri='pane.bin',byteLength=len(raw))],
        bufferViews=[dict(byteOffset=0),dict(byteOffset=positions.nbytes),dict(byteOffset=positions.nbytes+uv.nbytes)],
        accessors=[dict(bufferView=0,count=4,type='VEC3',componentType=5126),
                   dict(bufferView=1,count=4,type='VEC2',componentType=5126),
                   dict(bufferView=2,count=6,type='SCALAR',componentType=5123)],
        materials=[dict(name='own_glass')],meshes=[dict(primitives=[dict(material=0,indices=2,attributes=dict(POSITION=0,TEXCOORD_0=1))])])
    path=tmp_path/'pane.gltf';path.write_text(json.dumps(doc))
    options=dict(expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),expected_buffer_sha256=hashlib.sha256(raw).hexdigest(),
                 material='own_glass',bottom_m=0,top_m=10,expected_triangles=2)
    rows,proof=load_selection(path,**options)
    assert len(rows)==2 and rows[0]['uv'][0]==(0.,1.)
    assert proof['buffer_sha256']==options['expected_buffer_sha256']
    doc['meshes'][0]['primitives'] *= 2
    path.write_text(json.dumps(doc))
    options['expected_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='one reviewed'):
        load_selection(path,**options)
    _,proof=load_selection(path,primitive_ordinal=1,**options)
    assert proof['primitive_ordinal']==1
    for ordinal in (-1,2,True,1.0):
        with pytest.raises(ValueError,match='ordinal'):
            load_selection(path,primitive_ordinal=ordinal,**options)
    options['primitive_ordinal']=0
    (tmp_path/'pane.bin').write_bytes(raw[:-1]+bytes([raw[-1]^1]))
    with pytest.raises(ValueError,match='fingerprint/length'):
        load_selection(path,**options)
    path.write_text(path.read_text()+' ')
    with pytest.raises(ValueError,match='source fingerprint'):
        load_selection(path,**options)


def test_owned_floor_keeps_protected_field_as_real_hole():
    pytest.importorskip('shapely')
    p=np.array([[-100,-5,-80],[100,-5,-80],[100,-5,80],[-100,-5,80],[0,-5,0]])
    rows,proof=clip_floor_triangles(p,np.array([[0,1,4],[1,2,4],[2,3,4],[3,0,4]]),plane_m=-5,expected_source_triangles=4)
    assert len(rows)==8 and proof['protected_overlap_m2']==0
    assert proof['retained_area_m2']==pytest.approx(32000-116*80)
    assert all(p[1]==-5 for r in rows for p in r['positions'])
    with pytest.raises(ValueError,match='selection changed'):
        clip_floor_triangles(p,np.array([[0,1,4]]),plane_m=-5,expected_source_triangles=4)

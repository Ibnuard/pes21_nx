"""Conservative camera rejection must never erase a formerly visible surface."""
from pathlib import Path
import random
import sys
from types import SimpleNamespace as O
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from stadium_material_policy import camera_visible, camera_box_hidden
from stadium_geometry import subtract_pitch
from stadium_surface_policy import apply_surface_policies
from extract_fl26_stadium import Window
import pytest


def test_cluster_boxes_only_remove_existing_hidden_volume():
    rng=random.Random(27)
    removed=0
    for sample in range(30000):
        camera=[rng.uniform(-14000,14000),rng.uniform(-12000,12000),rng.uniform(150,8000)]
        centre=[rng.uniform(-13000,13000),rng.uniform(-10000,10000),rng.uniform(0,7000)]
        half_size=[rng.uniform(5,1000) for _ in range(3)]
        if not camera_box_hidden(centre,half_size,camera):continue
        removed+=1
        # Both rejection volumes are convex. Check all eight extreme corners
        # as well as random interior points, not only the box centre.
        assert not camera_visible(centre,camera)
        for i in range(40):
            direction=[(1 if i & (1 << k) else -1) if i<8 else rng.uniform(-1,1) for k in range(3)]
            assert not camera_visible([c+h*d for c,h,d in zip(centre,half_size,direction)],camera)
    assert removed>500


def test_near_wall_rejected_far_stand_and_boundary_box_retained():
    camera=(0,-9000,2000)
    assert camera_box_hidden((0,-8000,1700),(200,200,200),camera)
    assert not camera_box_hidden((0,8000,1700),(200,200,200),camera)
    assert not camera_box_hidden((0,-6500,1000),(6000,6000,6000),camera)
    for point in ((0,8000,2000),(8000,0,500),(0,5000,6000)):
        assert not camera_box_hidden(point,(100,100,100),(0,0,180))


def test_pitch_subtraction_retains_area_and_interpolated_uv():
    def vertex(x,z):return O(position=O(x=x,y=0,z=z),uv=[O(u=x/100,v=z/100)])
    face=O(vertices=[vertex(-100,-100),vertex(100,-100),vertex(0,100)])
    pieces=subtract_pitch(face)
    area=0
    for piece in pieces:
        a,b,c=piece.vertices
        area+=abs((b.position.x-a.position.x)*(c.position.z-a.position.z)-(b.position.z-a.position.z)*(c.position.x-a.position.x))*.5
        for v in piece.vertices:
            assert v.uv[0].u==pytest.approx(v.position.x/100)
            assert v.uv[0].v==pytest.approx(v.position.z/100)
    # All rectangle corners lie within this triangle except the two upper
    # corners: compare by an independent dense integration below instead.
    step=.5;reference=0
    for j in range(400):
        z=-100+(j+.5)*step
        for i in range(400):
            x=-100+(i+.5)*step
            if abs(x)<(100-z)*.5 and (abs(x)>53.5 or abs(z)>35):reference+=step*step
    assert abs(area-reference)<105
    assert face.vertices[0].position.x==-100


def test_same_texture_keeps_opaque_and_cutout_source_surfaces_separate():
    doc=dict(materials=[dict(name='paint',extras={})],meshes=[dict(primitives=[dict(material=0)]) for _ in range(3)])
    mat=O(shader='fox_3ddf_ggx',technique='fox3DDF_GGX')
    model=O(meshes=[O(alphaFlags=f,materialInstance=mat) for f in (0,128,160)])
    apply_surface_policies(doc,model)
    assert [(m['alphaMode'],m['doubleSided']) for m in doc['materials']]==[('OPAQUE',False),('MASK',False),('MASK',True)]


def test_nested_cpk_window_cannot_cross_archive_member():
    from io import BytesIO
    window=Window(BytesIO(b'private'+b'fixture'+b'other'),7,7)
    assert window.read(7)==b'fixture'
    with pytest.raises(ValueError):window.read(1)
    with pytest.raises(ValueError):window.seek(-1)
    with pytest.raises(ValueError):window.seek(8)
    window.seek(-3,2)
    assert window.read()==b'ure'

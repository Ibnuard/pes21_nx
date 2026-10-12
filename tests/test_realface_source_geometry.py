from pathlib import Path
import sys
from types import SimpleNamespace as Obj
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_source_geometry import prune_collapsed_fillers,prune_disabled_nan_meshes,prune_collapsed_triangles


def mesh(points, weights=None):
    return Obj(materialInstance=Obj(name='skin'), vertices=[
        Obj(position=Obj(x=p[0], y=p[1], z=p[2]), boneMapping=w)
        for p, w in zip(points, weights or [{'head': 1}] * len(points))])


def test_only_collapsed_identically_weighted_filler_is_excluded():
    visible = mesh([(0, 0, 0), (.001, 0, 0), (0, .001, 0)])
    zero = mesh([(0, 0, 0)] * 4)
    weighted = mesh([(0, 0, 0)] * 3, [{'head': 1}, {'neck': 1}, {'head': 1}])
    model = Obj(meshes=[visible, zero, weighted])
    audit = prune_collapsed_fillers(model)
    assert model.meshes == [visible, weighted]
    assert audit == [dict(material='skin', vertices=4, policy='coincident_vertices_and_identical_weights')]


def test_whole_empty_slot_and_nonfinite_input_are_not_hidden():
    zero = mesh([(0, 0, 0)] * 3)
    model = Obj(meshes=[zero])
    assert prune_collapsed_fillers(model) == [] and model.meshes == [zero]
    nonfinite = mesh([(float('nan'), 0, 0)] * 3)
    model = Obj(meshes=[zero, nonfinite])
    prune_collapsed_fillers(model)
    assert model.meshes == [nonfinite]


def test_two_bone_coincident_fillers_are_always_collinear_but_three_bones_are_not():
    import numpy as np
    weights=[{'head':1.},{'head':.9,'neck':.1},{'neck':1.}]
    filler=mesh([(0,0,0)]*3,weights)
    visible=mesh([(0,0,0),(1,0,0),(0,1,0)])
    third=mesh([(0,0,0)]*3,[{'head':1.},{'neck':1.},{'chest':1.}])
    model=Obj(meshes=[visible,filler,third])
    report=prune_collapsed_fillers(model,lambda b:b)
    assert model.meshes==[visible,third]
    assert report[0]['policy']=='coincident_vertices_at_most_two_mobile_bones'
    for seed in range(12):
        posed=dict(zip(('head','neck'),np.random.default_rng(seed).normal(size=(2,3))))
        points=[sum((posed[b]*w for b,w in row.items()),np.zeros(3)) for row in weights]
        assert np.linalg.norm(np.cross(points[1]-points[0],points[2]-points[0]))<1e-12


def test_disabled_nan_mesh_requires_a_remaining_finite_surface():
    disabled=mesh([(float('nan'),)*3]*3)
    visible=mesh([(0,0,0),(1,0,0),(0,1,0)])
    mixed=mesh([(float('nan'),0,0),(1,0,0),(0,1,0)])
    infinite=mesh([(float('inf'),)*3]*3)
    model=Obj(meshes=[disabled,visible,mixed,infinite])
    assert prune_disabled_nan_meshes(model)[0]['vertices']==3
    assert model.meshes==[visible,mixed,infinite]
    model=Obj(meshes=[disabled,mixed,infinite])
    assert prune_disabled_nan_meshes(model)==[]


def test_collapsed_islands_inside_visible_mesh_do_not_reach_overlap_builder():
    visible=mesh([(0,0,0),(1,0,0),(0,1,0)])
    filler=mesh([(0,0,0)]*3,[{'head':1},{'head':.5,'neck':.5},{'neck':1}])
    visible.faces=[Obj(vertices=list(visible.vertices)),Obj(vertices=filler.vertices)]
    visible.vertices+=filler.vertices
    original=list(visible.vertices[:3]);model=Obj(meshes=[visible])
    report=prune_collapsed_triangles(model,lambda b:b)
    assert report[0]['triangles']==1 and report[0]['vertices']==3
    assert visible.vertices==original and visible.faces[0].vertices==original


def test_posed_visible_collapsed_triangle_and_empty_part_are_preserved():
    unstable=mesh([(0,0,0)]*3,[{'head':1},{'neck':1},{'chest':1}])
    unstable.faces=[Obj(vertices=unstable.vertices)]
    model=Obj(meshes=[unstable]);assert prune_collapsed_triangles(model,lambda b:b)==[]
    visible=mesh([(0,0,0),(1,0,0),(0,1,0)]);visible.faces=[Obj(vertices=visible.vertices)]
    model.meshes.append(visible);assert prune_collapsed_triangles(model,lambda b:b)==[]

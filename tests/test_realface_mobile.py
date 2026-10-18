import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_mobile_geometry import raster,atlas_uv,compare
from realface_mobile import cooked_counts
from realface_eye_enclosure import choose_depth
from realface_mobile import package
from test_realface_lite import fixture
from realface_vertex_audit import match_normals
from realface_mobile_geometry import compact_hair_mask
from realface_mobile import status,CODE,HERE
from realface_mobile import ordered_levels,LEVELS
from realface_pipeline import sha


def test_occluded_layers_reduce_work_without_losing_coverage():
    p=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1],[1,0,1],[0,1,1]])
    t=np.array([[0,1,2],[3,4,5]]);uv=np.array([[[0,0],[1,0],[0,1]]]*2)
    old=raster(p,t,uv,np.ones((8,8)),np.eye(3))
    assert set(np.unique(old['front']))=={-1,1}
    new=raster(p,t[1:],uv[1:],np.ones((8,8)),np.eye(3),bounds=old['bounds'])
    proof=compare([old],[new])
    assert proof['silhouette_iou_min']==1
    assert proof['card_fragments_after']*2==proof['card_fragments_before']


def test_compact_hair_closes_strand_gaps_without_filling_large_openings():
    alpha=np.zeros((32,32));alpha[4:27,4:27]=1
    alpha[12:14,12:14]=0;alpha[17:25,17:25]=0
    result=compact_hair_mask(alpha)
    assert result[12:14,12:14].all()
    assert not result[19:23,19:23].any()
    assert not result[:3].any()


def test_transparent_front_does_not_occlude_solid_layer():
    p=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1],[1,0,1],[0,1,1]])
    uv=np.array([[[.1,.1]]*3,[[.8,.8]]*3]);alpha=np.zeros((8,8));alpha[:4,:4]=1
    frame=raster(p,np.array([[0,1,2],[3,4,5]]),uv,alpha,np.eye(3))
    assert set(np.unique(frame['front']))=={-1,0}


def test_skin_occlusion_changes_visibility_without_hiding_card_work():
    p=np.array([[0,0,0],[1,0,0],[0,1,0]])
    t=np.array([[0,1,2]]);uv=np.zeros((1,3,2));alpha=np.ones((1,1))
    visible=raster(p,t,uv,alpha,np.eye(3))
    behind=raster(p,t,uv,alpha,np.eye(3),bounds=visible['bounds'],skin_depth=np.ones((72,72)))
    assert visible['mask'].any() and not behind['mask'].any()
    assert behind['cards'].sum()==visible['cards'].sum()>0
    assert behind['opaque'].sum()==visible['opaque'].sum()>0


def test_eye_uv_crop_preserves_the_actual_native_eye_region():
    uv=np.array([[.25,.7],[.375,.825],[.3,.8]])
    mapped=atlas_uv(uv,((.25,.7),(.375,.825)),((98,98),(126,126)))
    assert mapped[0]==pytest.approx([98/128]*2)
    assert mapped[1]==pytest.approx([126/128]*2)
    with pytest.raises(ValueError):atlas_uv([[2,0]],((0,0),(1,1)),((2,2),(94,126)))


def test_cooked_material_and_triangle_ceiling_are_enforced():
    part=lambda n:dict(triangles=n,cooked_vertices=n)
    proof=dict(parts=dict(face=dict(components=dict(skin=part(1500))),hair=dict(components=dict(hair=part(400)))))
    assert cooked_counts(proof)['sections']==2
    proof['parts']['face']['components']['eye']=part(80)
    with pytest.raises(ValueError):cooked_counts(proof)
    del proof['parts']['face']['components']['eye']
    proof['parts']['hair']['components']['hair']['triangles']=501
    with pytest.raises(ValueError):cooked_counts(proof)


def test_eye_depth_removes_cheek_protrusion_without_hiding_pupil():
    opening=np.zeros((20,30),bool);opening[5:15,5:25]=True
    pupil=np.zeros_like(opening);pupil[9:12,14:17]=True
    skin=np.ones(opening.shape)*10;skin[opening]=9
    eye=np.full(opening.shape,10.3)
    choice,proof=choose_depth(eye,skin,opening,pupil)
    assert .29<choice['depth_shift_cm']<.32
    assert proof['after']['spill_pixels']==0
    assert proof['after']['pupil_visible_fraction']==1


def test_eye_depth_rejects_fix_that_occludes_the_pupil():
    opening=np.zeros((20,30),bool);opening[5:15,5:25]=True
    pupil=np.zeros_like(opening);pupil[9:12,14:17]=True
    skin=np.ones(opening.shape)*10;eye=np.ones(opening.shape)*10.3
    with pytest.raises(ValueError,match='keeping the pupil'):
        choose_depth(eye,skin,opening,pupil)


def test_mobile_package_refuses_incomplete_or_stale_identity(tmp_path):
    import json
    config,row=fixture(tmp_path);config['mobile_base_ids']=[7]
    for rows in ([],[dict(row,status='held_geometry')],
                 [dict(row,status='validated',fingerprint='different-player')]):
        (tmp_path/'verify-report.json').write_text(json.dumps(rows))
        with pytest.raises(ValueError):package(config)
        assert not (tmp_path/'package-stage').exists()


def test_status_does_not_count_a_stale_prepared_recipe_as_complete(tmp_path):
    import json
    config,row=fixture(tmp_path);config['mobile_base_ids']=[7]
    path=tmp_path/'prepare-report.json'
    path.write_text(json.dumps([dict(row,status='prepared',recipe_source_sha256={})]))
    assert status(config)['counts']=={'pending':1}
    path.write_text(json.dumps([dict(row,status='held_geometry',recipe_source_sha256={name:sha(HERE/name) for name in CODE},
                                   attempts=[dict(reason='ValueError: Hair silhouette held: {details}')])]))
    result=status(config)
    assert result['counts']=={'held_geometry':1}
    assert result['players'][0]['reason']=='ValueError: Hair silhouette held'


def test_resume_prioritizes_prior_allocation_without_skipping_validation_options():
    identity=dict(base_id=7,native_player_id=17,fingerprint='same-player')
    previous=dict(identity,status='prepared',budgets=LEVELS[-1])
    order=ordered_levels(identity,previous)
    assert order[0][0]==len(LEVELS)-1
    assert sorted(i for i,_ in order)==list(range(len(LEVELS)))
    previous['fingerprint']='another-owner'
    assert ordered_levels(identity,previous)[0][0]==0


def test_cooked_normals_allow_quantization_but_reject_changed_shading():
    corners=[((1,2,3),(.5,.5),(0,0,1))]
    proof=match_normals([(1,2,3)],[(.5,.5)],[(.002,0,.999)],corners,.03)
    assert proof['max_angle_degrees']<.2
    for normal in [(0,0,-1),(0,.1,.99)]:
        with pytest.raises(ValueError,match='normal changed'):
            match_normals([(1,2,3)],[(.5,.5)],[normal],corners,.03)


def test_reduced_skin_retains_smooth_source_normals(tmp_path):
    """Actual Blender + reducer regression using a synthetic authored sphere."""
    import json
    import shutil
    import subprocess
    root=Path(__file__).resolve().parents[1]
    blender=root/'local-debug/lamine-yamal-face-canary/third-party/blender-4.5.13/blender-4.5.13-windows-x64/blender.exe'
    module=root/'local-inputs/meshoptimizer-tools-v1/node_modules/meshoptimizer/meshopt_simplifier.js'
    node=shutil.which('node')
    if not blender.is_file() or not module.is_file() or not node:
        pytest.skip('Optional local Blender, meshoptimizer and Node runtimes unavailable')
    script=tmp_path/'normals.py'
    job=dict(mobile_v35=True,folder=str(tmp_path),node=node,meshoptimizer=str(module),
             budgets=dict(skin_error_cm=1.))
    script.write_text('''import sys,json
sys.path.insert(0, TOOLS)
import bpy
from mathutils import Vector
from blender_meshopt import reduce
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=5)
obj=bpy.context.object
for v in obj.data.vertices:v.co.z+=170
for p in obj.data.polygons:p.use_smooth=True
obj.data.normals_split_custom_set([(obj.data.vertices[l.vertex_index].co-Vector((0,0,170))).normalized() for l in obj.data.loops])
obj.vertex_groups.new(name='sk_head').add(list(range(len(obj.data.vertices))),1.,'REPLACE')
count=reduce(obj,[v.co.copy() for v in obj.data.vertices],160,'skin',JOB)
assert count<250,count
assert obj.data.has_custom_normals
for loop,normal in zip(obj.data.loops,obj.data.corner_normals):
    expected=(obj.data.vertices[loop.vertex_index].co-Vector((0,0,170))).normalized()
    assert expected.dot(normal.vector)>.999,(expected,normal.vector)
'''.replace('TOOLS',repr(str(root/'tools'))).replace('JOB',repr(job)))
    result=subprocess.run([str(blender),'--background','--threads','1','--python-exit-code','1',
                           '--python',str(script)],capture_output=True)
    assert result.returncode==0,(result.stdout+result.stderr).decode(errors='replace')


def test_skin_visibility_removes_enclosed_rigid_geometry_only(tmp_path):
    import subprocess
    root=Path(__file__).resolve().parents[1]
    blender=root/'local-debug/lamine-yamal-face-canary/third-party/blender-4.5.13/blender-4.5.13-windows-x64/blender.exe'
    if not blender.is_file():pytest.skip('Optional local Blender runtime unavailable')
    script=tmp_path/'exterior.py'
    script.write_text('''import sys
sys.path.insert(0, TOOLS)
import bpy
from blender_realface_skin_visibility import exterior
bpy.ops.wm.read_factory_settings(use_empty=True)
mesh=bpy.data.meshes.new('synthetic')
p=[(-2,-2,168),(2,-2,168),(2,2,168),(-2,2,168),(-2,-2,172),(2,-2,172),(2,2,172),(-2,2,172),
   (-.2,0,170),(.2,0,170),(0,.2,170),(-.2,0,169),(.2,0,169),(0,.2,169)]
faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(8,9,10),(11,12,13)]
mesh.from_pydata(p,[],faces);mesh.uv_layers.new(name='UVMap')
obj=bpy.data.objects.new('head',mesh);bpy.context.collection.objects.link(obj)
obj.vertex_groups.new(name='sk_head').add(list(range(11)),1.,'REPLACE')
obj.vertex_groups.new(name='sk_neck').add([11,12,13],1.,'REPLACE')
proof=exterior(obj,[v.co.copy() for v in mesh.vertices],OUTPUT)
assert proof['before']==14 and proof['after']==13,proof
assert obj.data.has_custom_normals
assert any(set(p.vertices)=={11,12,13} for p in obj.data.polygons)
assert not any(set(p.vertices)=={8,9,10} for p in obj.data.polygons)
'''.replace('TOOLS',repr(str(root/'tools'))).replace('OUTPUT',repr(str(tmp_path))))
    result=subprocess.run([str(blender),'--background','--threads','1','--python-exit-code','1',
                           '--python',str(script)],capture_output=True)
    assert result.returncode==0,(result.stdout+result.stderr).decode(errors='replace')


def test_anterior_eye_patch_faces_the_light_and_retains_iris_depth(tmp_path):
    import subprocess
    root=Path(__file__).resolve().parents[1]
    blender=root/'local-debug/lamine-yamal-face-canary/third-party/blender-4.5.13/blender-4.5.13-windows-x64/blender.exe'
    if not blender.is_file():pytest.skip('Optional local Blender runtime unavailable')
    script=tmp_path/'eye-front.py'
    script.write_text('''import sys
sys.path.insert(0, TOOLS)
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from blender_realface_eye_cleanup import aperture_cap
from blender_realface_hair_reduce import from_native_surface
from mathutils import Matrix
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=1.3,location=(0,8,170))
obj=bpy.context.object;mesh=obj.data;mesh.calc_loop_triangles()
p=np.array([obj.matrix_world@v.co for v in mesh.vertices]);f=[t.vertices[:] for t in mesh.loop_triangles]
uv=np.array([[mesh.uv_layers[0].data[i].uv[:] for i in t.loops] for t in mesh.loop_triangles])
eye=BVHTree.FromPolygons([Vector(v) for v in p],f,all_triangles=True)
skin=BVHTree.FromPolygons([Vector(v) for v in [(-3,9.15,167),(3,9.15,167),(3,9.15,173),(-3,9.15,173)]],[(0,1,2),(0,2,3)],all_triangles=True)
xs=np.linspace(-2.2,2.2,147);zs=np.linspace(168,172,135)
opening=(xs[None,:]/1.1)**2+((zs[:,None]-170)/.5)**2<=1
points,faces,st=aperture_cap((0,8,170),xs,zs,opening,skin,eye,p,f,uv)
assert abs(points[0][1]-9.27)<.002,points[0]
for face in faces:
    a,b,c=[Vector(points[i]) for i in face]
    assert (b-a).cross(c-a).y>0,face
assert np.isfinite(st).all()
patch=bpy.data.meshes.new('eye-patch');patch.from_pydata(points,[],faces);patch.update()
layer=patch.uv_layers.new(name='UVMap')
for loop,coord in zip(patch.loops,layer.data):coord.uv=st[loop.vertex_index]
for polygon in patch.polygons:polygon.use_smooth=True
inverse=Matrix.Diagonal((1.,-1.,1.,1.))
from_native_surface(patch,inverse)
normal_matrix=inverse.transposed().to_3x3()
front=[normal_matrix@normal.vector for loop,normal in zip(patch.loops,patch.corner_normals) if loop.vertex_index==0]
assert front and all(n.y>.9 for n in front),front
assert all(np.max(np.abs(np.array(coord.uv)-st[loop.vertex_index]))<.00001 for loop,coord in zip(patch.loops,patch.uv_layers[0].data))
'''.replace('TOOLS',repr(str(root/'tools'))))
    result=subprocess.run([str(blender),'--background','--threads','1','--python-exit-code','1','--python',str(script)],capture_output=True)
    assert result.returncode==0,(result.stdout+result.stderr).decode(errors='replace')

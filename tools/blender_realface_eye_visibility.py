"""Keep source eye surfaces visible around the head, with a protected neighbour ring.

Offline only. The original visible coordinates, UVs, normals and weights are
retained. This is an optional source-detail policy, never a relaxed eye gate.
"""
import bpy
import numpy as np
from pathlib import Path
import shutil

from blender_fit_realface import vertex_weights
from blender_realface_mobile import geometry, pixels
from realface_mobile_geometry import views


def hair_occluders(job,native,cooked):
    before=set(bpy.context.scene.objects)
    path=Path(job['folder'])/'eye-occluder-hair.fbx'
    shutil.copy2(job['source_profile']['hair_fbx'],path)
    try:
        bpy.ops.import_scene.fbx(filepath=str(path),use_anim=False)
        meshes=[geometry(obj,native,cooked) for obj in set(bpy.context.scene.objects)-before if obj.type=='MESH']
        alpha=pixels(job['source_profile']['hair_texture'])[:,:,3].copy()
        return [(p,t,uv,alpha) for p,t,uv in meshes]
    finally:
        for obj in set(bpy.context.scene.objects)-before:bpy.data.objects.remove(obj,do_unlink=True)


def trim(obj, skin, skin_tri, native, cooked, budget, occluders=()):
    import realface_mobile_geometry as geometry_checks
    p,tri,uv=geometry(obj,native,cooked)
    selected=set();references=[]
    for basis in views():
        projected=p@basis.T
        bounds=(projected[:,:2].min(axis=0)-.2,projected[:,:2].max(axis=0)+.2)
        body=geometry_checks.raster(skin,skin_tri,np.zeros((len(skin_tri),3,2)),
            np.ones((1,1)),basis,bounds,size=192)
        # FL source faces may intentionally omit the back of the skull where
        # their own scalp covers it. Ignoring that scalp falsely classifies
        # the buried rear halves of the eyeballs as visible from behind.
        for hp,ht,hu,alpha in occluders:
            hair=geometry_checks.raster(hp,ht,hu,alpha,basis,bounds,size=192)
            body['depth']=np.maximum(body['depth'],hair['depth'])
        eye=geometry_checks.raster(p,tri,uv,np.ones((1,1)),basis,bounds,size=192,skin_depth=body['depth'])
        selected.update(int(i) for i in np.unique(eye['front']) if i>=0)
        references.append((basis,bounds,body['depth'],eye['mask']))
    if not selected:raise ValueError('No visible original eye surface')
    # Weld positions only for adjacency detection, never for exported geometry.
    # Padding covers a small reveal after reduction of the surrounding eyelid.
    _,alias=np.unique(np.round(p,5),axis=0,return_inverse=True)
    visible_vertices=set(alias[tri[sorted(selected)]].ravel())
    retained=np.array([i for i,face in enumerate(tri) if any(alias[v] in visible_vertices for v in face)],dtype=int)
    if len(retained)>budget:
        raise ValueError('Visible source eye exceeds reserved budget: '+str(len(retained)))
    for basis,bounds,body,mask in references:
        after=geometry_checks.raster(p,tri[retained],uv[retained],np.ones((1,1)),basis,bounds,size=192,skin_depth=body)
        if np.any(mask & ~after['mask']):raise ValueError('Visible original eye coverage was lost')
    old=obj.data;used=sorted(set(tri[retained].ravel()));remap={int(v):i for i,v in enumerate(used)}
    weights=[vertex_weights(obj,old.vertices[i]) for i in used]
    corners=[[old.corner_normals[li].vector.copy() for li in old.loop_triangles[i].loops] for i in retained]
    mesh=bpy.data.meshes.new(old.name+'_visible_source')
    mesh.from_pydata([old.vertices[i].co[:] for i in used],[],
                    [[remap[int(v)] for v in face] for face in tri[retained]])
    mesh.update();layer=mesh.uv_layers.new(name='UVMap')
    for poly,st in zip(mesh.polygons,uv[retained]):
        poly.use_smooth=True
        for li,coord in zip(poly.loop_indices,st):layer.data[li].uv=coord
    mesh.normals_split_custom_set([normal for face in corners for normal in face])
    for material in old.materials:mesh.materials.append(material)
    obj.data=mesh;obj.vertex_groups.clear()
    groups={name:obj.vertex_groups.new(name=name) for name in sorted({n for w in weights for n in w})}
    for i,row in enumerate(weights):
        for name,value in row.items():groups[name].add([i],value,'REPLACE')
    return dict(source_triangles=len(tri),visible_triangles=len(selected),retained_triangles=len(retained),
                occluded_triangles_removed=len(tri)-len(retained),adjacency_padding_rings=1,
                checked_views=len(references),sample_resolution=192,visible_coverage_lost=0,
                source_positions_uv_weights_preserved=True,source_hair_occlusion_included=bool(occluders))

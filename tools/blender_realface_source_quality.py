"""Experimental source-detail canaries; not an approved league release recipe.

This optional investigation keeps the original eye surface and bakes a sharper
opaque atlas at the same normalized UVs. Hair keeps source textures, UVs and
bone weights in the collapse branch. The trial must still pass visual review:
neither a small surface error nor a silhouette pass proves hairstyle fidelity.
"""
import json
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from blender_fit_realface import runtime_matrix,vertex_weights
from blender_realface_mobile import geometry,pixels,sample_tile


def facial_detail_locks(original,positions,triangles,uv,locks,texture):
    """Protect eyebrow/eyelid texture boundaries as well as the mouth crease."""
    result,proof=original(positions,triangles,uv,locks,texture)
    p=np.asarray(positions).reshape(-1,3);tri=np.asarray(triangles).reshape(-1,3);st=np.asarray(uv).reshape(-1,2)
    from realface_surface_quality import raster
    frame=raster(p,tri,st[tri],np.ones((1,1)),np.array([[1,0,0],[0,0,1],[0,1,0]]),((-9.5,155),(9.5,182)),size=192)
    visible=np.zeros(len(p),bool);visible[np.unique(tri[np.unique(frame['front'][frame['front']>=0])])]=True
    nose=p[(np.abs(p[:,0])<1.5)&(p[:,2]>160)&(p[:,2]<176)]
    nose_z=nose[np.argmax(nose[:,1]),2]
    brow=visible&(np.abs(p[:,0])<7)&(p[:,2]>nose_z+2)&(p[:,2]<nose_z+8)
    x=np.clip((st[:,0]*texture.shape[1]).astype(int),0,texture.shape[1]-1)
    y=np.clip((st[:,1]*texture.shape[0]).astype(int),0,texture.shape[0]-1)
    luma=texture[y,x,:3]@np.array([.2126,.7152,.0722])
    candidates=np.flatnonzero(brow&(luma<np.median(luma[brow])*.7)) if brow.any() else np.array([],dtype=int)
    # Keep both ends of a narrow brow triangle. Protecting its dark centre
    # alone still lets a collapse stretch that centre into the forehead.
    marked=np.flatnonzero(np.isin(tri,candidates).any(axis=1))
    candidates=np.unique(tri[marked]);candidates=candidates[brow[candidates]]
    if len(candidates)>160:
        selected=[int(candidates[np.argmin(luma[candidates])])];distance=np.full(len(candidates),np.inf)
        for _ in range(159):
            distance=np.minimum(distance,np.linalg.norm(p[candidates]-p[selected[-1]],axis=1));selected.append(int(candidates[np.argmax(distance)]))
        candidates=np.asarray(selected)
    for i in candidates:result[i]=1
    proof.update(eyebrow_anchors=len(candidates),maximum_eyebrow_anchors=160)
    return result,proof


def capture_normals(obj,native,cooked):
    p,t,uv=geometry(obj,native,cooked)
    matrices=[runtime_matrix(obj,vertex_weights(obj,v),native,cooked).to_3x3().inverted().transposed()
              for v in obj.data.vertices]
    normals=np.asarray([[tuple((matrices[vi]@obj.data.corner_normals[li].vector).normalized())
        for vi,li in zip(tri.vertices,tri.loops)] for tri in obj.data.loop_triangles])
    return p,t,normals


def transfer_normals(obj,native,cooked,source):
    p,t,n=source
    # Never interpolate through a zero-area marker or a hidden duplicate.
    area=np.linalg.norm(np.cross(p[t[:,1]]-p[t[:,0]],p[t[:,2]]-p[t[:,0]]),axis=1)
    live=np.flatnonzero(area>1e-6);faces=t[live]
    tree=BVHTree.FromPolygons([Vector(v) for v in p],faces.tolist(),all_triangles=True)
    after,_,_=geometry(obj,native,cooked);normals=[];distances=[]
    for loop in obj.data.loops:
        vi=loop.vertex_index;hit,normal,index,distance=tree.find_nearest(Vector(after[vi]))
        if index is None:raise ValueError('Original hair has no shading surface')
        a,b,c=p[faces[index]];e0=b-a;e1=c-a;d=np.asarray(hit)-a
        aa=e0@e0;ab=e0@e1;bb=e1@e1;den=aa*bb-ab*ab
        v=(bb*(d@e0)-ab*(d@e1))/den;w=(aa*(d@e1)-ab*(d@e0))/den
        weights=np.maximum(np.array([1-v-w,v,w]),0.);weights/=weights.sum()
        native_normal=Vector(weights@n[live[index]])
        if native_normal.length<.1:native_normal=normal
        matrix=runtime_matrix(obj,vertex_weights(obj,obj.data.vertices[vi]),native,cooked)
        local=(matrix.to_3x3().transposed()@native_normal).normalized()
        normals.append(local);distances.append(distance)
    obj.data.normals_split_custom_set(normals)
    return dict(corners=len(normals),max_projection_cm=max(distances),source_shading_projected=True)


def atlas256(job):
    folder=Path(job['folder']);proof=json.loads((folder/'atlas-proof.json').read_text())
    profile=job['source_profile'];atlas=np.zeros((256,256,4),np.float32)
    for role,tile in proof['tiles'].items():
        sample_tile(pixels(profile['face_texture' if role=='skin' else 'native_eye_texture']),
                    tile['source_bounds'],np.asarray(tile['destination_bounds'])*2,atlas)
    # Original face diffuse alpha is a separate source mask. The merged mobile
    # face is intentionally opaque; do not premultiply away its skin colours.
    atlas[:,:,3]=1
    image=bpy.data.images.new('source_detail_atlas',width=256,height=256,alpha=False)
    image.pixels.foreach_set(atlas.ravel());image.filepath_raw=str(folder/'opaque-atlas.png')
    image.file_format='PNG';image.save()
    proof.update(size=256,normalized_uvs_unchanged=True,source_detail_rebaked=True)
    for tile in proof['tiles'].values():tile['destination_bounds']=(np.asarray(tile['destination_bounds'])*2).tolist()
    (folder/'atlas-proof.json').write_text(json.dumps(proof,indent=2))


def prepare(job):
    import blender_realface_eye_cleanup as eyes
    import blender_realface_mobile as mobile
    import realface_surface_quality as surface
    from blender_realface_league_worker import prepare as base_prepare
    old_eye,old_prepare,old_finish,old_atlas=eyes.clean,mobile.prepare_hair,mobile.finish_hair,mobile.merge_atlas
    old_locks=surface.feature_locks
    captured={}
    def keep_eye(groups,job,native,cooked):
        if len(groups.get('eye',[]))!=1:raise ValueError('Source eye requires one classified original surface')
        from blender_realface_lite import count
        original_count=count(groups['eye'][0])
        from blender_realface_lite import points
        from realface_eye_fit import sphere
        from realface_eye_boundary import rim_variants
        eye=np.asarray(points(groups['eye'][0],native,cooked))
        skin,faces=[],[]
        for obj in groups.get('skin',[]):
            p,t,_=geometry(obj,native,cooked);faces.extend(t+len(skin));skin.extend(p)
        visibility=None
        if original_count>job['budgets']['eye']:
            from blender_realface_eye_visibility import trim,hair_occluders
            visibility=trim(groups['eye'][0],np.asarray(skin),np.asarray(faces),native,cooked,job['budgets']['eye'],
                            hair_occluders(job,native,cooked))
        tree=BVHTree.FromPolygons([Vector(v) for v in skin],faces,all_triangles=True)
        rims=[]
        for sign in (-1,1):
            center,_,_=sphere(eye[eye[:,0]*sign>0])
            xs=np.linspace(center[0]-2.2,center[0]+2.2,147)
            zs=np.linspace(center[2]-2.,center[2]+2.,135)
            depth=np.full((len(zs),len(xs)),-100.)
            for zi,z in enumerate(zs):
                for xi,x in enumerate(xs):
                    hit,_,_,_=tree.ray_cast(Vector((x,40,z)),Vector((0,-1,0)))
                    if hit is not None:depth[zi,xi]=hit.y
            variants=rim_variants(xs,zs,depth)
            if variants:rims.extend(variants[0]['bounds'])
        job['eyelid_rim_points']=rims
        (Path(job['folder'])/'eye-enclosure.json').write_text(json.dumps(dict(
            mode='original_source_eye',positions_unchanged=True,uv_unchanged=True,skin_geometry_changed=False,
            original_triangles=original_count,retained_triangles=count(groups['eye'][0]),
            visibility=visibility,eyelid_rim_anchors=len(rims))))
    def hair(obj,job,native,cooked):
        captured['normals']=capture_normals(obj,native,cooked)
        captured['geometry']=geometry(obj,native,cooked)
        mode=job['budgets']['hair_mode']
        if job['budgets'].get('visible_volume'):job['budgets']['hair_mode']='cards'
        try:result=old_prepare(obj,job,native,cooked)
        finally:job['budgets']['hair_mode']=mode
        if mode=='closed':result[3]['mode']='source_volume_collapse'
        return result
    def finish(obj,job,native,cooked,reference):
        if job['budgets'].get('detail_shell'):
            from blender_realface_hair_clearance import clearance,rebake_radial
            folder=Path(job['folder']);request=json.loads((folder/'lite_skin-meshopt.json').read_text())
            skin=np.asarray(request['positions']).reshape(-1,3)
            faces=np.asarray(json.loads((folder/'lite_skin-meshopt-result.json').read_text())['indices']).reshape(-1,3)
            p,t,uv=geometry(obj,native,cooked)
            moved,clearance_proof=clearance(p,t,skin,faces,max_move=.35)
            for vertex,point in zip(obj.data.vertices,moved):
                vertex.co=runtime_matrix(obj,vertex_weights(obj,vertex),native,cooked).inverted()@Vector(point)
            atlas=rebake_radial(captured['geometry'],pixels(job['source_profile']['hair_texture']),
                               (moved,t,uv),reference[3],captured['normals'][2])
            size=len(atlas);image=bpy.data.images.new('final_detail_hair',width=size,height=size,alpha=True)
            image.alpha_mode='CHANNEL_PACKED';image.pixels.foreach_set(atlas.ravel())
            image.filepath_raw=str(folder/'hair-shell.png');image.file_format='PNG';image.save()
            reference=(reference[0],atlas[:,:,3],reference[2],reference[3])
            (folder/'hair-clearance.json').write_text(json.dumps(clearance_proof,indent=2))
        result=old_finish(obj,job,native,cooked,reference)
        if not job['budgets'].get('detail_shell'):
            proof=transfer_normals(obj,native,cooked,captured['normals'])
            (Path(job['folder'])/'hair-normal-transfer.json').write_text(json.dumps(proof,indent=2))
        return result
    def atlas(job):
        old_atlas(job);atlas256(job)
        if job['budgets'].get('normal_export_recovery'):
            from blender_realface_normal_export import repair
            proof=repair(bpy.context.view_layer.objects.active)
            (Path(job['folder'])/'normal-export-repair.json').write_text(json.dumps(proof,indent=2))
    eyes.clean=keep_eye if job['budgets'].get('source_eye') else old_eye
    if job['budgets'].get('source_eye_policy')=='measured_aperture':
        from blender_realface_eye_aperture_recovery import clean as aperture_recovery
        eyes.clean=aperture_recovery
    mobile.prepare_hair=hair;mobile.finish_hair=finish;mobile.merge_atlas=atlas
    if job['budgets'].get('extra_brow_anchors'):
        surface.feature_locks=lambda *args:facial_detail_locks(old_locks,*args)
    try:base_prepare(job)
    finally:
        eyes.clean=old_eye;mobile.prepare_hair=old_prepare;mobile.finish_hair=old_finish;mobile.merge_atlas=old_atlas
        surface.feature_locks=old_locks

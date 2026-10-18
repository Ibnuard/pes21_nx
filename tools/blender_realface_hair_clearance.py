"""Offline scalp clearance against the actual face, preserving topology and UVs.

A coarse radial shell can have vertices outside the head but triangle interiors
inside it. Constrain sampled interiors, not just vertices. This is an optional
derived-mesh repair: original face geometry and source assets are immutable.
"""
import json
from pathlib import Path
import shutil
import sys
import math

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import rig_globals
from blender_fit_realface import runtime_matrix, vertex_weights
from blender_realface_lite import export
from blender_realface_mobile import geometry, pixels, source_views
from realface_mobile_geometry import audit as silhouette_audit, compare
from realface_fast_raster import load


def import_mesh(path, copy):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.scale_length=.01
    shutil.copy2(path,copy)
    bpy.ops.import_scene.fbx(filepath=str(copy),use_anim=False)
    return [o for o in bpy.context.scene.objects if o.type=='MESH']


def merged_data(objects,native,cooked):
    points=[];tri=[];uv=[]
    for obj in objects:
        p,t,u=geometry(obj,native,cooked)
        tri.extend(t+len(points));points.extend(p);uv.extend(u)
    return np.asarray(points),np.asarray(tri,dtype=int),np.asarray(uv)


def visible_metrics(before,after,alpha,beta,skin,skin_tri,raster):
    bounds=((-12,152),(12,194));size=192
    z=152+(np.arange(size)+.5)/size*42
    forehead=(z[:,None]>172)&(z[:,None]<179)
    records=[]
    for yaw in (0,-25,25):
        a=np.radians(yaw)
        basis=np.asarray([[np.cos(a),-np.sin(a),0],[0,0,1],[np.sin(a),np.cos(a),0]])
        body=raster(skin,skin_tri,np.zeros((len(skin_tri),3,2)),np.ones((1,1)),basis,bounds,size)
        old=raster(*before,alpha,basis,bounds,size,skin_depth=body['depth'])
        new=raster(*after,beta,basis,bounds,size,skin_depth=body['depth'])
        pad=np.pad(old['mask'],1)
        expanded=np.logical_or.reduce([pad[y:y+size,x:x+size] for y in range(3) for x in range(3)])
        records.append(dict(yaw=yaw,visible_missing=float(np.count_nonzero(old['mask']&~new['mask'])/max(old['mask'].sum(),1)),
                            new_forehead_pixels=int(np.count_nonzero(new['mask']&~expanded&body['mask']&forehead))))
    return dict(views=records,visible_missing_max=max(r['visible_missing'] for r in records),
                new_forehead_pixels_max=max(r['new_forehead_pixels'] for r in records))


def clearance(points,tri,skin,skin_tri,margin=.06,max_move=1.2):
    """Push scalp triangle interiors outside skin; keep facial hair stationary."""
    tree=BVHTree.FromPolygons([Vector(v) for v in skin],skin_tri.tolist(),all_triangles=True)
    center=np.array([0.,0.,173.]);start=points.copy();current=points.copy()
    # Never displace beard/jaw or long side hair below the eye line.
    movable=points[:,2]>168.
    samples=np.asarray([(1.,0.,0.),(0.,1.,0.),(0.,0.,1.),(.5,.5,0.),(.5,0.,.5),(0.,.5,.5),(1/3,1/3,1/3)])
    deficits=[]
    for iteration in range(8):
        demand=np.zeros(len(points));hits=0;worst=0.
        for face in tri:
            if not movable[face].all():continue
            for weights in samples:
                point=weights@current[face];delta=point-center;radius=np.linalg.norm(delta)
                if radius<1.:continue
                direction=delta/radius
                hit,normal,index,distance=tree.ray_cast(Vector(center+direction*40),Vector(-direction),39.)
                if index is None:continue
                skin_radius=float(np.dot(np.asarray(hit)-center,direction))
                deficit=skin_radius+margin-radius
                if deficit>.015:
                    hits+=1;worst=max(worst,deficit)
                    # All supporting vertices move enough to lift the interior.
                    demand[face]=np.maximum(demand[face],min(deficit*.8,.25))
        deficits.append(dict(iteration=iteration,samples_inside=hits,maximum_cm=worst))
        if not hits:break
        delta=current-center;directions=delta/np.maximum(np.linalg.norm(delta,axis=1)[:,None],1e-6)
        proposed=current+directions*demand[:,None]
        displacement=proposed-start;length=np.linalg.norm(displacement,axis=1)
        current=start+displacement*np.minimum(1.,max_move/np.maximum(length,1e-6))[:,None]
    return current,dict(iterations=deficits,max_vertex_displacement_cm=float(np.linalg.norm(current-start,axis=1).max()))


def rebake_radial(original,texture,after,method,source_normals=None):
    """Bake onto the final sparse surface, avoiding angular UV interpolation drift."""
    p,t,u=original;h,w=texture.shape[:2]
    tree=BVHTree.FromPolygons([Vector(v) for v in p],t.tolist(),all_triangles=True)
    size=method.get('texture_size',128)
    pos,faces,uv=after;atlas=np.zeros((size,size,4),np.float32)
    regions=method['regions'];split=.75 if len(regions)>1 else 1.
    for face,st in zip(faces,uv):
        xy=st*size-.5;lo=np.maximum(np.ceil(xy.min(axis=0)).astype(int),0);hi=np.minimum(np.floor(xy.max(axis=0)).astype(int),size-1)
        a,b,c=xy;den=np.cross(b-a,c-a)
        if abs(den)<1e-8:continue
        for y in range(lo[1],hi[1]+1):
            for x in range(lo[0],hi[0]+1):
                q=np.array([x,y]);v=np.cross(q-a,c-a)/den;z=np.cross(b-a,q-a)/den
                if min(1-v-z,v,z)<-1e-6:continue
                point=np.array([1-v-z,v,z])@pos[face]
                region=regions[0 if (y+.5)/size<split else 1]
                center=Vector(region['center']);delta=Vector(point)-center;ray=delta.normalized();origin=center+ray*42
                for _ in range(64):
                    remain=(origin-center).dot(ray)
                    if remain<=.25:break
                    hit,_,index,_=tree.ray_cast(origin,-ray,remain-.25)
                    if index is None:break
                    a0,b0,c0=[Vector(v) for v in p[t[index]]];e0=b0-a0;e1=c0-a0;e2=hit-a0
                    aa=e0.dot(e0);ab=e0.dot(e1);bb=e1.dot(e1);div=aa*bb-ab*ab
                    if abs(div)>1e-12:
                        v0=(bb*e2.dot(e0)-ab*e2.dot(e1))/div;v1=(aa*e2.dot(e1)-ab*e2.dot(e0))/div
                        texel=np.array([1-v0-v1,v0,v1])@u[index];xx=texel[0]*w-.5;yy=texel[1]*h-.5
                        ix=math.floor(xx);iy=math.floor(yy);fx=xx-ix;fy=yy-iy
                        color=(texture[iy%h,ix%w]*(1-fx)*(1-fy)+texture[iy%h,(ix+1)%w]*fx*(1-fy)+
                               texture[(iy+1)%h,ix%w]*(1-fx)*fy+texture[(iy+1)%h,(ix+1)%w]*fx*fy)
                        if color[3]>=.333:
                            if source_normals is not None:
                                normal=Vector(np.array([1-v0-v1,v0,v1])@source_normals[index]).normalized()
                                if normal.dot(ray)<0:normal=-normal
                                lights=[Vector((.6,.8,1)).normalized(),Vector((-.6,.6,.8)).normalized()]
                                shading=lambda n:.55+sum(max(0.,n.dot(light)) for light in lights)*.225
                                color=color.copy();color[:3]*=min(1.25,max(.65,shading(normal)/shading(ray)))
                            atlas[y,x]=color;break
                    origin=hit-ray*.002
    # Only close small interior gaps. A final-surface bake must not extend its
    # sampled lower hairline again, which caused the original forehead islands.
    from realface_mobile_geometry import compact_hair_mask
    atlas[:,:,3]=compact_hair_mask(atlas[:,:,3],radius=1)
    known=atlas[:,:,3]>=.333;rgb=atlas[:,:,:3]
    for _ in range(4):
        sums=np.zeros_like(rgb);counts=np.zeros((size,size))
        for dy,dx in ((-1,0),(1,0),(0,-1),(0,1)):
            mask=np.roll(known,(dy,dx),(0,1));sums+=np.roll(rgb,(dy,dx),(0,1))*mask[:,:,None];counts+=mask
        fill=~known&(counts>0);rgb[fill]=sums[fill]/counts[fill,None];known|=fill
    return atlas


def run(job):
    folder=Path(job['output']);folder.mkdir(parents=True,exist_ok=True)
    old=Path(job['row']['folder']);source=json.loads((old/'job.json').read_text(encoding='utf-8'))
    profile=json.loads((old/'ue-profile.json').read_text(encoding='utf-8'))
    config=job['config'];raster=load(config['fast_raster'])
    import realface_mobile_geometry
    realface_mobile_geometry.raster=raster
    native,cooked=(rig_globals(json.loads(Path(config[k]).read_text())) for k in ('native_rig','cooked_rig'))
    original=merged_data(import_mesh(source['source_profile']['hair_fbx'],folder/'input-original.fbx'),native,cooked)
    original_texture=pixels(source['source_profile']['hair_texture']).copy()
    alpha=original_texture[:,:,3]
    # The source contains skin-only positions before atlas merging.
    request=json.loads((old/'lite_skin-meshopt.json').read_text())
    skin=np.asarray(request['positions']).reshape(-1,3)
    skin_tri=np.asarray(json.loads((old/'lite_skin-meshopt-result.json').read_text())['indices']).reshape(-1,3)
    objects=import_mesh(profile['hair_fbx'],folder/'input-hair.fbx')
    if len(objects)!=1:raise ValueError('Clearance requires the single prepared hair section')
    obj=objects[0];before=geometry(obj,native,cooked)
    beta=pixels(profile['hair_texture'])[:,:,3].copy()
    base=visible_metrics(original,before,alpha,beta,skin,skin_tri,raster)
    reference,_=source_views(original,alpha,dict(source,folder=str(folder)))
    selected=None;candidates=[];method=read_projection(old)
    for maximum in (0.,.3,.6,1.0):
        pos,proof=clearance(before[0],before[1],skin,skin_tri,max_move=maximum)
        after=(pos,before[1],before[2])
        atlas=rebake_radial(original,original_texture,after,method) if method['mode']=='split_radial_surface' else None
        candidate_alpha=atlas[:,:,3] if atlas is not None else beta
        visibility=visible_metrics(original,after,alpha,candidate_alpha,skin,skin_tri,raster)
        frames,_=silhouette_audit(*after,candidate_alpha,reference=reference);outline=compare(reference,frames)
        result=dict(maximum_cm=maximum,clearance=proof,visibility=visibility,outline=outline)
        candidates.append(result)
        allowed=(outline['silhouette_iou_min']>=.80 and outline['silhouette_iou_mean']>=.85 and
                 outline['missing_coverage_max']<=.15 and outline['card_fragments_after']<=outline['card_fragments_before']*1.05)
        # Removing intersections must not introduce additional forehead coverage.
        if allowed and visibility['new_forehead_pixels_max']<=max(40,base['new_forehead_pixels_max']+8):
            score=visibility['visible_missing_max']+.001*visibility['new_forehead_pixels_max']
            if selected is None or score<selected[0]:selected=(score,pos.copy(),result,atlas)
        if selected and selected[2]['visibility']['visible_missing_max']<.12:break
    report=dict(base_id=job['row']['base_id'],before=base,candidates=candidates,
                selected=selected[2] if selected else None)
    (folder/'clearance.json').write_text(json.dumps(report,indent=2))
    if selected is None:raise ValueError('No scalp clearance candidate preserves its original outline')
    if selected[3] is not None:
        image=bpy.data.images.new('final_hair_atlas',width=128,height=128,alpha=True)
        image.alpha_mode='CHANNEL_PACKED';image.pixels.foreach_set(selected[3].ravel())
        image.filepath_raw=str(folder/'hair-shell.png');image.file_format='PNG';image.save()
    for vertex,point in zip(obj.data.vertices,selected[1]):
        vertex.co=runtime_matrix(obj,vertex_weights(obj,vertex),native,cooked).inverted()@Vector(point)
    # A loose vertex is not a renderable surface. Remove only unused vertices;
    # no triangle, UV or influence of the surviving surface may disappear.
    import bmesh
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bm.to_mesh(obj.data);bm.free()
    export(folder/'hair.fbx',next(o for o in bpy.context.scene.objects if o.type=='ARMATURE'))
    (folder/'hair-projection.json').write_text(json.dumps(dict(selected[2]['outline'],method=dict(mode='skin_clearance',parent=read_projection(old))),indent=2))


def read_projection(folder):
    return json.loads((folder/'hair-projection.json').read_text())['method']


if __name__=='__main__':run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8')))

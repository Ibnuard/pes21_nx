"""Reproject source hair onto a unique atlas after reducing its volume.

Collapsing overlapping source cards can interpolate their UVs across the face
mask and reveal dark triangles on the forehead. Reprojection uses the original
surface at each final texel instead, with no additional runtime material.
"""
import math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from blender_realface_mobile import geometry,pixels


def bake(obj,source,texture,native,cooked,output,size=256,opaque=False,micro_shading=False,visible_source=False,
         normal_output=None,source_normals=None,coverage_source=None):
    points,tri,uv=source
    area=np.linalg.norm(np.cross(points[tri[:,1]]-points[tri[:,0]],points[tri[:,2]]-points[tri[:,0]]),axis=1)
    live=np.flatnonzero(area>1e-6);tri=tri[live];uv=uv[live]
    if source_normals is not None:source_normals=np.asarray(source_normals)[live]
    tree=BVHTree.FromPolygons([Vector(v) for v in points],tri.tolist(),all_triangles=True)
    coverage_tree=None
    if coverage_source is not None:
        coverage_points,coverage_tri,coverage_uv=coverage_source
        coverage_tree=BVHTree.FromPolygons([Vector(v) for v in coverage_points],coverage_tri.tolist(),all_triangles=True)
    saved=[v.co.copy() for v in obj.data.vertices]
    native_points=geometry(obj,native,cooked)[0]
    for v,p in zip(obj.data.vertices,native_points):v.co=p
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    # The source image can be rectangular. This new atlas is square: inheriting
    # its aspect ratio can waste more than half the atlas before chart margins.
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.012,
                             correct_aspect=False,scale_to_bounds=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    for v,p in zip(obj.data.vertices,saved):v.co=p
    current,faces,st=geometry(obj,native,cooked);image=np.zeros((size,size,4),np.float32);filled=np.zeros((size,size),bool)
    normal_image=np.zeros_like(image)
    h,w=texture.shape[:2];maximum=0.;count=0;opaque_fallbacks=0
    from blender_realface_face_rebake import sample
    opaque_colors=texture[texture[:,:,3]>=.5,:3]
    fallback=np.median(opaque_colors,axis=0) if len(opaque_colors) else np.zeros(3)
    def projected_color(hit,index):
        aa,bb,cc=points[tri[index]];e0=bb-aa;e1=cc-aa;e2=np.asarray(hit)-aa
        d00=e0@e0;d01=e0@e1;d11=e1@e1;det=d00*d11-d01*d01
        v0=(d11*(e2@e0)-d01*(e2@e1))/det;v1=(d00*(e2@e1)-d01*(e2@e0))/det
        coord=np.array([1-v0-v1,v0,v1])@uv[index]
        return sample(texture,coord)
    def projected_normal(hit,index):
        aa,bb,cc=points[tri[index]];e0=bb-aa;e1=cc-aa;e2=np.asarray(hit)-aa
        if source_normals is None:normal=np.cross(e0,e1)
        else:
            a=e0@e0;b=e0@e1;c=e1@e1;det=a*c-b*b
            v=(c*(e2@e0)-b*(e2@e1))/det;w=(a*(e2@e1)-b*(e2@e0))/det
            normal=np.array([1-v-w,v,w])@source_normals[index]
        normal/=max(np.linalg.norm(normal),1e-8)
        if normal@(np.asarray(hit)-[0,4,173])<0:normal=-normal
        return normal
    def detail_shading(hit,index,color):
        a,b,c=(Vector(p) for p in points[tri[index]])
        normal=(b-a).cross(c-a).normalized()
        if normal.dot(hit-Vector((0,4,173)))<0:normal=-normal
        tangent=normal.cross(Vector((0,0,1)))
        if tangent.length<.01:tangent=normal.cross(Vector((1,0,0)))
        tangent.normalize();bitangent=normal.cross(tangent).normalized();blocked=0
        directions=[(normal+tangent*x+bitangent*y).normalized() for x,y in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1))]
        for direction in directions:
            start=hit+normal*.025;travel=0.
            for _ in range(12):
                point,_,other,distance=tree.ray_cast(start,direction,2.-travel)
                if other is None:break
                if projected_color(point,other)[3]>=.4:blocked+=1;break
                travel+=distance+.01
                if travel>=2.:break
                start=point+direction*.01
        visibility=1-blocked/len(directions)
        half=Vector((.1,.7,1)).normalized();highlight=max(0.,normal.dot(half))**6
        result=color.copy()
        result[:3]=color[:3]*(.45+.55*visibility)+.02*highlight*visibility
        return result
    for face,coords in zip(faces,st):
        q=coords*size-.5;start=np.maximum(np.ceil(q.min(axis=0)).astype(int),0);end=np.minimum(np.floor(q.max(axis=0)).astype(int),size-1)
        a,b,c=q;den=np.cross(b-a,c-a)
        if abs(den)<1e-8:continue
        for y in range(start[1],end[1]+1):
            for x in range(start[0],end[0]+1):
                d=np.array([x,y])-a;v=np.cross(d,c-a)/den;z=np.cross(b-a,d)/den
                if min(1-v-z,v,z)<-1e-6:continue
                position=np.array([1-v-z,v,z])@current[face]
                hit,_,index,distance=tree.find_nearest(Vector(position))
                if index is None:continue
                if visible_source:
                    center=Vector((0,4,173));ray=(Vector(position)-center).normalized();origin=center+ray*40
                    for _ in range(64):
                        remaining=(origin-center).dot(ray)
                        if remaining<.2:break
                        projected,_,outer,_=tree.ray_cast(origin,-ray,remaining-.2)
                        if outer is None:break
                        if projected_color(projected,outer)[3]>=.4:
                            if (projected-Vector(position)).length<=2.:
                                hit,index,distance=projected,outer,(projected-Vector(position)).length
                            break
                        origin=projected-ray*.005
                color=projected_color(hit,index)
                if opaque and color[3]<.4:
                    # Transparent source texels can contain arbitrary RGB.
                    # Never turn those hidden blue/skin pixels opaque when
                    # the strand geometry has been joined into a solid clump.
                    choices=sorted(tree.find_nearest_range(Vector(position),max(.8,distance+.1)),key=lambda h:h[3])
                    for point,_,other,near_distance in choices:
                        candidate=projected_color(point,other)
                        if candidate[3]>=.4:
                            color=candidate;hit=point;index=other;distance=near_distance;break
                    else:color=np.r_[fallback,1.];opaque_fallbacks+=1
                if micro_shading:color=detail_shading(hit,index,color)
                image[y,x]=color
                if opaque:image[y,x,3]=1.
                if coverage_tree is not None:
                    # A joined scalp still has a source hairline and exposed
                    # ear/temple cutouts. Filling colour is not permission to
                    # make those intentionally transparent areas opaque.
                    point,_,other,_=coverage_tree.find_nearest(Vector(position))
                    if other is None:raise ValueError('No original scalp coverage surface')
                    aa,bb,cc=coverage_points[coverage_tri[other]]
                    e0=bb-aa;e1=cc-aa;d=np.asarray(point)-aa
                    ca=e0@e0;cb=e0@e1;cc=e1@e1;coverage_den=ca*cc-cb*cb
                    if abs(coverage_den)<1e-12:raise ValueError('Collapsed source scalp coverage triangle')
                    cv=(cc*(d@e0)-cb*(d@e1))/coverage_den;cw=(ca*(d@e1)-cb*(d@e0))/coverage_den
                    mask_uv=np.array([1-cv-cw,cv,cw])@coverage_uv[other]
                    image[y,x,3]=float(sample(texture,mask_uv)[3]>=.333)
                if normal_output is not None:normal_image[y,x]=np.r_[projected_normal(hit,index)*.5+.5,1.]
                filled[y,x]=True;maximum=max(maximum,distance);count+=1
    # Extrude chart borders for linear sampling. Never close an interior
    # transparent texel, including the source's forehead and eyelid masks.
    for _ in range(3):
        total=np.zeros_like(image);normal_total=np.zeros_like(image);number=np.zeros_like(filled,dtype=np.int32)
        for dy,dx in ((-1,0),(1,0),(0,-1),(0,1)):
            valid=np.roll(filled,(dy,dx),(0,1));total+=np.roll(image,(dy,dx),(0,1))*valid[:,:,None]
            normal_total+=np.roll(normal_image,(dy,dx),(0,1))*valid[:,:,None];number+=valid
        mask=~filled&(number>0);image[mask]=total[mask]/number[mask,None]
        normal_image[mask]=normal_total[mask]/number[mask,None];filled|=mask
    result=bpy.data.images.new('source_projected_hair',width=size,height=size,alpha=True)
    result.alpha_mode='CHANNEL_PACKED';result.pixels.foreach_set(image.ravel());result.filepath_raw=str(Path(output).resolve());result.file_format='PNG';result.save()
    if normal_output is not None:
        result=bpy.data.images.new('diagnostic_world_normal',width=size,height=size,alpha=False)
        result.colorspace_settings.name='Non-Color';result.pixels.foreach_set(normal_image.ravel())
        result.filepath_raw=str(Path(normal_output).resolve());result.file_format='PNG';result.save()
    return image[:,:,3],dict(size=size,projected_texels=count,max_projection_cm=maximum,unique_uv_atlas=True,
                            opaque=opaque,opaque_colour_fallbacks=opaque_fallbacks,micro_shading=micro_shading,
                            visible_source=visible_source,source_scalp_mask_preserved=coverage_tree is not None)

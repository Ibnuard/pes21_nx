"""Reproject original skin colour onto the final sparse face's existing UVs."""
import json,math
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def sample(texture,coord):
    h,w=texture.shape[:2];x=coord[0]*w-.5;y=coord[1]*h-.5
    ix=math.floor(x);iy=math.floor(y);fx=x-ix;fy=y-iy
    return (texture[iy%h,ix%w]*(1-fx)*(1-fy)+texture[iy%h,(ix+1)%w]*fx*(1-fy)+
            texture[(iy+1)%h,ix%w]*(1-fx)*fy+texture[(iy+1)%h,(ix+1)%w]*fx*fy)


def bake(folder,texture,atlas,destination,frontal=True):
    folder=Path(folder)
    request=json.loads((folder/'lite_skin-meshopt.json').read_text())
    p=np.asarray(request['positions']).reshape(-1,3);uv=np.asarray(request['uv']).reshape(-1,2)
    source=np.asarray(request['indices']).reshape(-1,3)
    after=np.asarray(json.loads((folder/'lite_skin-meshopt-result.json').read_text())['indices']).reshape(-1,3)
    area=np.linalg.norm(np.cross(p[source[:,1]]-p[source[:,0]],p[source[:,2]]-p[source[:,0]]),axis=1)
    source=source[area>1e-6]
    tree=BVHTree.FromPolygons([Vector(v) for v in p],source.tolist(),all_triangles=True)
    start,end=np.asarray(destination);count=0;maximum=0.;depth=np.full(atlas.shape[:2],-np.inf)
    for tri in after:
        coords=start+uv[tri]*(end-start)-.5
        lo=np.maximum(np.ceil(coords.min(axis=0)).astype(int),start);hi=np.minimum(np.floor(coords.max(axis=0)).astype(int),end-1)
        a,b,c=coords;den=np.cross(b-a,c-a)
        if abs(den)<1e-8:continue
        for y in range(lo[1],hi[1]+1):
            for x in range(lo[0],hi[0]+1):
                d=np.asarray([x,y])-a;v=np.cross(d,c-a)/den;w=np.cross(b-a,d)/den
                if min(1-v-w,v,w)<-1e-6:continue
                position=np.asarray([1-v-w,v,w])@p[tri]
                # In the facial features, match the original visible surface
                # at the same frontal coordinates; nearest 3D can select the
                # inner wall of the mouth instead of its visible lip.
                if frontal and abs(position[0])<7.5 and position[1]>5 and 158<position[2]<178:
                    hit,_,index,distance=tree.ray_cast(Vector((position[0],40,position[2])),Vector((0,-1,0)))
                    if index is not None and abs(hit.y-position[1])>1.:index=None
                else:index=None
                if index is None:hit,_,index,distance=tree.find_nearest(Vector(position))
                if index is None:continue
                aa,bb,cc=p[source[index]];e0=bb-aa;e1=cc-aa;e2=np.asarray(hit)-aa
                d00=e0@e0;d01=e0@e1;d11=e1@e1;det=d00*d11-d01*d01
                v0=(d11*(e2@e0)-d01*(e2@e1))/det;v1=(d00*(e2@e1)-d01*(e2@e0))/det
                coord=np.asarray([1-v0-v1,v0,v1])@uv[source[index]]
                if position[1]>=depth[y,x]:
                    atlas[y,x]=sample(texture,coord);depth[y,x]=position[1]
                maximum=max(maximum,float(np.linalg.norm(np.asarray(hit)-position)));count+=1
    return dict(projected_skin_texels=count,max_projection_cm=maximum,frontal_feature_projection=frontal)

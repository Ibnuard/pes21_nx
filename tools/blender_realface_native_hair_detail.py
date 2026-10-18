"""Bake source clump relief into colour, as native mobile hair atlases do.

The shipped material has no sampled hair normal map. A diagnostic world-normal
bake is used offline only; it never becomes another game sampler or section.
"""
from pathlib import Path
import bpy
import numpy as np

from blender_realface_mobile import geometry
from blender_realface_hair_rebake import bake
from blender_realface_source_quality import capture_normals


def fresh_pixels(path):
    # A trial writes several derived images to the same output path. Blender
    # check_existing=True can return a previous generated in-memory image.
    image=bpy.data.images.load(str(path),check_existing=False);image.alpha_mode='CHANNEL_PACKED'
    raw=np.empty(len(image.pixels),np.float32);image.pixels.foreach_get(raw)
    return raw.reshape((image.size[1],image.size[0],4))


def detail(obj,source,texture,source_normals,native,cooked,folder):
    folder=Path(folder);normal_path=folder/'source-clump-normals-diagnostic.png'
    _,proof=bake(obj,source,texture,native,cooked,folder/'hair-shell.png',size=128,opaque=True,
        visible_source=True,normal_output=normal_path,source_normals=source_normals)
    color=fresh_pixels(folder/'hair-shell.png')
    image=bpy.data.images.load(str(normal_path),check_existing=False)
    image.colorspace_settings.name='Non-Color'
    raw=np.empty(len(image.pixels),np.float32);image.pixels.foreach_get(raw)
    source_n=raw.reshape((128,128,4))[:,:,:3]*2-1
    source_n/=np.maximum(np.linalg.norm(source_n,axis=2,keepdims=True),1e-6)
    p,t,uv=geometry(obj,native,cooked);_,_,normals=capture_normals(obj,native,cooked)
    low=np.zeros((128,128,3),np.float32);occupied=np.zeros((128,128),bool)
    for face,coords,ns in zip(t,uv,normals):
        xy=coords*128-.5;a,b,c=xy
        den=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        if abs(den)<1e-8:continue
        lo=np.maximum(np.ceil(xy.min(axis=0)).astype(int),0);hi=np.minimum(np.floor(xy.max(axis=0)).astype(int),127)
        x,y=np.meshgrid(np.arange(lo[0],hi[0]+1),np.arange(lo[1],hi[1]+1))
        dx=x-a[0];dy=y-a[1]
        v=(dx*(c[1]-a[1])-dy*(c[0]-a[0]))/den
        w=((b[0]-a[0])*dy-(b[1]-a[1])*dx)/den
        weights=np.stack([1-v-w,v,w],axis=-1);inside=np.min(weights,axis=2)>=-1e-6
        values=weights@ns;values/=np.maximum(np.linalg.norm(values,axis=2,keepdims=True),1e-6)
        low[y[inside],x[inside]]=values[inside];occupied[y[inside],x[inside]]=True
    light=np.array([[.6,.8,1.],[-.6,.6,.8]])
    light/=np.linalg.norm(light,axis=1,keepdims=True)
    def shade(n):return .32+.34*np.maximum(n@light.T,0).sum(axis=2)
    ratio=np.clip(shade(source_n)/np.maximum(shade(low),.1),.45,1.6)
    # Apply the relative clump response, leaving broad directional lighting to
    # the existing shader. This adds no silhouette or source-colour filling.
    color[occupied,:3]*=ratio[occupied,None]
    color[:,:,3]=1.
    result=bpy.data.images.new('opaque_hair_source_relief',128,128,alpha=False)
    result.pixels.foreach_set(color.ravel());result.filepath_raw=str(folder/'hair-shell.png')
    result.file_format='PNG';result.save()
    return dict(projection=proof,relative_source_normal_colour_bake=True,normal_texture_runtime=False,
        contrast_range=[.45,1.6],baked_texels=int(occupied.sum()),visual_approval=False)

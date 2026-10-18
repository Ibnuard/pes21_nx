"""Experimental source-alpha hair masses under the complete-head ceiling.

Sample the source's visible alpha rather than closing whole card rectangles.
This is an offline alternative for difficult layered hair, not an appearance
approval. Silhouette/workload, face, rig and cooked-buffer gates still apply.
"""
from pathlib import Path
import bpy
import bmesh
import numpy as np

from blender_fit_realface import runtime_matrix, vertex_weights
from blender_realface_lite import count
from blender_realface_mobile import geometry, pixels, source_views
from blender_realface_hair_reduce import from_native_surface
from blender_realface_hair_rebake import bake


LAST_SURFACE = None


def neighbours(array, dilate):
    result=array.copy()
    for axis in range(3):
        for offset in (-1,1):
            shifted=np.roll(array,offset,axis)
            edge=[slice(None)]*3;edge[axis]=0 if offset>0 else -1
            shifted[tuple(edge)]=False
            if dilate:result|=shifted
            else:result&=shifted
    return result


def prepare(obj,job,native,cooked):
    global LAST_SURFACE
    LAST_SURFACE=None
    bindings=[vertex_weights(obj,v) for v in obj.data.vertices]
    if any(set(weights)-{'sk_head','sk_neck','sk_chest'} for weights in bindings):
        raise ValueError('Joined hair contains a binding outside the audited head/neck chain')
    mixed=sum(weights!={'sk_head':1.} for weights in bindings)
    source=geometry(obj,native,cooked);p,t,st=source
    texture=pixels(job['source_profile']['hair_texture'])
    before,_=source_views(source,texture[:,:,3],job)
    voxel=.22
    lo=np.floor(p.min(axis=0)/voxel)*voxel-voxel*7
    hi=p.max(axis=0)+voxel*7
    shape=np.ceil((hi-lo)/voxel).astype(int)
    if np.any(shape<1) or np.prod(shape)>8000000:
        raise ValueError('Source hair exceeds the bounded offline volume grid')
    occupied=np.zeros(shape,bool)
    for indices,uv in zip(t,st):
        q=p[indices]
        n=max(1,int(np.ceil(np.linalg.norm(q-np.roll(q,1,axis=0),axis=1).max()/(voxel*.6))))
        if n>600:raise ValueError('Source hair contains an unbounded card')
        a,b=np.meshgrid(np.arange(n+1)/n,np.arange(n+1)/n)
        keep=a+b<=1.
        weights=np.stack([1-a[keep]-b[keep],a[keep],b[keep]],1)
        xyz=weights@q;coord=(weights@uv)%1
        sx=coord[:,0]*texture.shape[1]-.5;sy=coord[:,1]*texture.shape[0]-.5
        ix=np.floor(sx).astype(int);iy=np.floor(sy).astype(int);fx=sx-ix;fy=sy-iy
        h,w=texture.shape[:2]
        alpha=(texture[iy%h,ix%w,3]*(1-fx)*(1-fy)+texture[iy%h,(ix+1)%w,3]*fx*(1-fy)+
               texture[(iy+1)%h,ix%w,3]*(1-fx)*fy+texture[(iy+1)%h,(ix+1)%w,3]*fx*fy)
        cells=np.floor((xyz[alpha>=.333]-lo)/voxel).astype(int)
        if len(cells):occupied[tuple(cells.T)]=True
    samples=int(occupied.sum())
    if samples<8:raise ValueError('Source alpha has insufficient visible hair volume')
    occupied=neighbours(occupied,True)
    closing=int(job['budgets'].get('volume_closing_steps',5))
    if closing not in (3,4,5):raise ValueError('Unsupported bounded hair closing radius')
    for _ in range(closing):occupied=neighbours(occupied,True)
    for _ in range(closing):occupied=neighbours(occupied,False)
    vertices=[];faces=[];lookup={}
    for axis in range(3):
        for sign in (-1,1):
            adjacent=np.roll(occupied,-sign,axis)
            edge=[slice(None)]*3;edge[axis]=-1 if sign>0 else 0
            adjacent[tuple(edge)]=False
            other=[i for i in range(3) if i!=axis]
            for cell in np.argwhere(occupied&~adjacent):
                quad=[]
                for a,b in ((0,0),(1,0),(1,1),(0,1)):
                    corner=cell.copy();corner[axis]+=int(sign>0)
                    corner[other[0]]+=a;corner[other[1]]+=b;key=tuple(corner)
                    if key not in lookup:
                        lookup[key]=len(vertices);vertices.append(lo+corner*voxel)
                    quad.append(lookup[key])
                if (axis==1)==(sign>0):quad.reverse()
                faces.append(quad)
    inverse=runtime_matrix(obj,{'sk_head':1.},native,cooked).inverted()
    arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    materials=list(obj.data.materials)
    mesh=bpy.data.meshes.new('source_alpha_hair_masses')
    mesh.from_pydata(vertices,[],faces);mesh.update();obj.data=mesh
    obj.modifiers.clear();parent=obj.parent;matrix=obj.matrix_world.copy()
    obj.parent=None;obj.matrix_world.identity();bpy.context.view_layer.objects.active=obj;obj.select_set(True)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    obj.data.remesh_voxel_size=.25;obj.data.use_remesh_preserve_volume=True
    bpy.ops.object.voxel_remesh()
    smooth=obj.modifiers.new('join source clumps','SMOOTH');smooth.factor=.55;smooth.iterations=4
    bpy.ops.object.modifier_apply(modifier=smooth.name)
    for polygon in obj.data.polygons:polygon.use_smooth=True
    obj.data.calc_loop_triangles()
    high=(np.asarray([v.co[:] for v in obj.data.vertices]),
          np.asarray([tri.vertices[:] for tri in obj.data.loop_triangles]),
          np.asarray([[obj.data.corner_normals[i].vector[:] for i in tri.loops] for tri in obj.data.loop_triangles]))
    budget=int(job['budgets']['hair'])
    if budget<32:raise ValueError('Insufficient complete-head remainder for joined hair')
    modifier=obj.modifiers.new('bounded hair budget','DECIMATE')
    modifier.ratio=min(1.,(budget-6)/max(count(obj),1));modifier.use_collapse_triangulate=True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    for _ in range(3):
        for factor in (.45,-.46):
            smooth=obj.modifiers.new('soften clump corners','SMOOTH');smooth.factor=factor;smooth.iterations=1
            bpy.ops.object.modifier_apply(modifier=smooth.name)
    if count(obj)>budget:raise ValueError('Joined hair exceeds the complete-head remainder')
    obj.parent=parent;obj.matrix_world=matrix
    obj.vertex_groups.clear();obj.vertex_groups.new(name='sk_head').add(list(range(len(obj.data.vertices))),1.,'REPLACE')
    from_native_surface(obj.data,inverse)
    modifier=obj.modifiers.new('native head binding','ARMATURE');modifier.object=arm
    for polygon in obj.data.polygons:polygon.use_smooth=True
    obj.data.uv_layers.new(name='UVMap')
    alpha,proof=bake(obj,source,texture,native,cooked,Path(job['folder'])/'hair-shell.png',
                     size=128,opaque=True,micro_shading=True,visible_source=True)
    obj.data.materials.clear()
    for material in materials:obj.data.materials.append(material)
    for polygon in obj.data.polygons:polygon.material_index=0
    LAST_SURFACE=high
    return before,alpha,0,dict(mode='joined_source_alpha_volume',sampled_cells=samples,
        voxel_cm=voxel,closing_steps=closing,source_triangles=len(t),hair_budget=budget,
        texture_size=128,source_colour_bake=proof,visual_approval=False,
        binding_policy='rigid_native_head_like_joined_scalp_shell',source_mixed_neck_vertices=mixed)

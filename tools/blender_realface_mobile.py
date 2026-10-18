"""Mobile head preparation: visible hair envelope and one opaque face atlas."""
import json
import hashlib
from pathlib import Path
import bpy
import bmesh
import numpy as np
from realface_mobile_geometry import audit, compare, atlas_uv


def geometry(obj,native,cooked):
    from blender_realface_lite import points
    obj.data.calc_loop_triangles()
    triangles=np.array([t.vertices[:] for t in obj.data.loop_triangles],dtype=int)
    uv=np.array([[obj.data.uv_layers[0].data[i].uv[:] for i in t.loops] for t in obj.data.loop_triangles])
    return np.array(points(obj,native,cooked)),triangles,uv


def pixels(path):
    image=bpy.data.images.load(str(path),check_existing=True)
    image.alpha_mode='CHANNEL_PACKED'
    values=np.empty(len(image.pixels),np.float32);image.pixels.foreach_get(values)
    return values.reshape((image.size[1],image.size[0],4))


def source_views(data,alpha,job):
    """Reuse the expensive unchanged source raster across allocation retries."""
    digest=hashlib.sha256(Path(__file__).with_name('realface_mobile_geometry.py').read_bytes())
    for array in (*data,alpha):digest.update(array.tobytes())
    cache=Path(job['folder']).parent/'source-views'/ (digest.hexdigest()+'.npz')
    if cache.exists():
        with np.load(cache,allow_pickle=False) as stored:
            frames=[{name:stored[str(i)+'_'+name] for name in ('front','mask','opaque','cards','bounds','depth')} for i in range(13)]
        return frames,{int(v) for frame in frames for v in np.unique(frame['front']) if v>=0}
    frames,visible=audit(*data,alpha)
    cache.parent.mkdir(parents=True,exist_ok=True)
    temporary=cache.with_name(cache.stem+'-'+str(job['base_id'])+'.tmp.npz')
    np.savez_compressed(temporary,**{str(i)+'_'+name:value for i,frame in enumerate(frames) for name,value in frame.items()})
    temporary.replace(cache)
    return frames,visible


def prepare_hair(obj,job,native,cooked):
    alpha=pixels(job['source_profile']['hair_texture'])[:,:,3]
    obj.data.calc_loop_triangles()
    # Remove complete triangles invisible in all 13 alpha-tested views.
    # Triangulate first so visibility indices match faces exactly.
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
    # Blender's triangulation can reorder triangles; audit that actual order.
    before,visible=source_views(geometry(obj,native,cooked),alpha,job)
    if job['budgets'].get('hair_mode')=='closed':
        return before,alpha,0,dict(mode='closed_source_collapse')
    if job['budgets'].get('hair_mode')=='shell':
        from blender_realface_hair_shell import build
        new_alpha,proof=build(obj,job,native,cooked)
        return before,new_alpha,0,proof
    polys={obj.data.loop_triangles[i].polygon_index for i in visible}
    if not polys:
        raise ValueError('No visible hair pixels; requires a separate bald-head recipe')
    original=len(obj.data.polygons)
    bm=bmesh.new();bm.from_mesh(obj.data);bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index not in polys],context='FACES')
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bm.to_mesh(obj.data);bm.free()
    return before,alpha,original-len(obj.data.polygons),dict(mode='visible_cards')


def finish_hair(obj,job,native,cooked,reference):
    before,alpha,removed,method=reference
    after,_=audit(*geometry(obj,native,cooked),alpha,reference=before)
    result=compare(before,after)
    if method['mode']=='split_radial_surface':
        # Fit the final reduced surface, not a denser intermediate. Do not
        # inflate facial hair; its separate shell follows the jaw directly.
        from blender_fit_realface import runtime_matrix
        from mathutils import Vector
        center=Vector(method['regions'][0]['center'])
        source=[Vector(p) for p in geometry(obj,native,cooked)[0]]
        scalp=set(range(len(source)))
        if len(method['regions'])>1:
            scalp={loop.vertex_index for loop,uv in zip(obj.data.loops,obj.data.uv_layers[0].data) if uv.uv.y<.75}
        inverse=runtime_matrix(obj,{'sk_head':1.},native,cooked).inverted()
        def score(q):return min(q['silhouette_iou_min']/.80,q['silhouette_iou_mean']/.85,(1-q['missing_coverage_max'])/.85)
        best=(score(result),0.,[v.co.copy() for v in obj.data.vertices],result)
        if best[0]<1:
            for offset in (.125,.25,.5,.75,1.):
                for i,(vertex,position) in enumerate(zip(obj.data.vertices,source)):
                    vertex.co=inverse @ (position+(position-center).normalized()*offset if i in scalp else position)
                frames,_=audit(*geometry(obj,native,cooked),alpha,reference=before);candidate=compare(before,frames)
                if score(candidate)>best[0]:best=(score(candidate),offset,[v.co.copy() for v in obj.data.vertices],candidate)
                if best[0]>=1:break
        for vertex,position in zip(obj.data.vertices,best[2]):vertex.co=position
        result=best[3];method['envelope_fit_offset_cm']=best[1]
    result['invisible_triangles_removed']=removed
    result['method']=method
    Path(job['folder'],'hair-projection.json').write_text(json.dumps(result,indent=2))
    # Visible fringe/outline coverage replaces interior-layer distance as the
    # hair quality gate. Face/eyes/neck still use the original surface limits.
    # Hair is deliberately simplified more than facial anatomy. Allow the
    # loss of isolated strand detail after inspecting the compact shell, but
    # still require an 85% mean envelope and bounded missing coverage.
    if (result['silhouette_iou_min']<.80 or result['silhouette_iou_mean']<.85 or
            result['missing_coverage_max']>.15):
        raise ValueError('Hair silhouette held: '+json.dumps(result))
    if result['card_fragments_after']>result['card_fragments_before']*1.05:
        raise ValueError('Hair card workload increased')
    return result


def sample_tile(source,source_bounds,dest_bounds,atlas):
    (x0,y0),(x1,y1)=dest_bounds
    (u0,v0),(u1,v1)=source_bounds
    # Two pixels of edge extrusion guard the tile from bilinear/mip bleed.
    x=np.arange(x0-2,x1+2);y=np.arange(y0-2,y1+2)
    u=u0+np.clip((x+.5-x0)/(x1-x0),0,1)*(u1-u0)
    v=v0+np.clip((y+.5-y0)/(y1-y0),0,1)*(v1-v0)
    # Bake native repeat sampling into the tile, including tiny eye UV
    # overscan outside 0..1. Modulo applies to texels, never to mesh UVs.
    sx=u*source.shape[1]-.5;sy=v*source.shape[0]-.5
    ix=np.floor(sx).astype(int);iy=np.floor(sy).astype(int);fx=sx-ix;fy=sy-iy
    jx=(ix+1)%source.shape[1];jy=(iy+1)%source.shape[0]
    ix=ix%source.shape[1];iy=iy%source.shape[0]
    row0=source[iy[:,None],ix]*(1-fx[None,:,None])+source[iy[:,None],jx]*fx[None,:,None]
    row1=source[jy[:,None],ix]*(1-fx[None,:,None])+source[jy[:,None],jx]*fx[None,:,None]
    atlas[y[:,None],x]=row0*(1-fy[:,None,None])+row1*fy[:,None,None]


def merge_atlas(job):
    objects={o.name:o for o in bpy.context.scene.objects if o.type=='MESH'}
    if set(objects)!={'lite_skin','lite_eye'}:
        raise ValueError('Opaque atlas requires one classified skin and eye surface')
    atlas=np.zeros((128,128,4),np.float32);atlas[:,:,3]=1
    tiles={};profile=job['source_profile']
    for role,destination in [('skin',((2,2),(94,126))),('eye',((98,98),(126,126)))]:
        obj=objects['lite_'+role];layer=obj.data.uv_layers[0]
        uv=np.array([item.uv[:] for item in layer.data])
        bounds=np.array([[0.,0.],[1.,1.]]) if role=='skin' else np.array([uv.min(axis=0),uv.max(axis=0)])
        if np.any(np.abs(bounds)>4) or np.any(bounds[1]-bounds[0]>4):
            raise ValueError('Atlas UV repetition exceeds the explicit four-tile guard')
        source=pixels(profile['face_texture' if role=='skin' else 'native_eye_texture'])
        sample_tile(source,bounds,destination,atlas)
        mapped=atlas_uv(uv,bounds,destination)
        for item,value in zip(layer.data,mapped):item.uv=value
        tiles[role]=dict(source_bounds=bounds.tolist(),destination_bounds=destination,
                         loops=len(uv),max_uv_roundtrip_error=float(np.max(np.abs(
                             ((mapped*128-destination[0])/(np.array(destination[1])-destination[0]))*
                             (bounds[1]-bounds[0])+bounds[0]-uv))))
    atlas[:,:,3]=1
    image=bpy.data.images.new('mobile_opaque_atlas',width=128,height=128,alpha=False)
    image.pixels.foreach_set(atlas.ravel());image.filepath_raw=str(Path(job['folder'],'opaque-atlas.png'))
    image.file_format='PNG';image.save()
    material=bpy.data.materials.new('mobile_opaque')
    for obj in objects.values():
        obj.data.materials.clear();obj.data.materials.append(material)
        for poly in obj.data.polygons:poly.material_index=0
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects.values():obj.select_set(True)
    bpy.context.view_layer.objects.active=objects['lite_skin'];bpy.ops.object.join()
    Path(job['folder'],'atlas-proof.json').write_text(json.dumps(dict(size=128,tiles=tiles),indent=2))

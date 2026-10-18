"""Offline alpha-aware exterior/silhouette audit; no game-frame work.

The raster counts card fragments and alpha-tested fragments separately. It
is a geometry workload proxy, not a GPU measurement. Pixels use fixed head
bounds across the before/after comparison, including the same sample grid.
"""
import math
import numpy as np


def views():
    result=[]
    for elevation, count in ((0,8),(40,4),(85,1)):
        for i in range(count):
            angle=2*math.pi*i/count; tilt=math.radians(elevation)
            forward=np.array([math.cos(angle)*math.cos(tilt),math.sin(angle)*math.cos(tilt),math.sin(tilt)])
            right=np.array([-math.sin(angle),math.cos(angle),0.])
            result.append(np.array([right,np.cross(forward,right),forward]))
    return result


def raster(positions, triangles, uv, alpha, basis, bounds=None, size=72, skin_depth=None):
    p=np.asarray(positions) @ basis.T
    if bounds is None:
        lo=p[:,:2].min(axis=0)-.15; hi=p[:,:2].max(axis=0)+.15
        bounds=(lo,hi)
    lo,hi=map(np.asarray,bounds)
    screen=(p[:,:2]-lo)/(hi-lo)*size
    depth=np.full((size,size),-np.inf); front=np.full((size,size),-1,dtype=int)
    opaque=np.zeros((size,size),np.uint16); cards=np.zeros_like(opaque)
    ah,aw=alpha.shape
    for index, face in enumerate(triangles):
        points=screen[face]; low=np.maximum(np.floor(points.min(axis=0)).astype(int),0)
        high=np.minimum(np.ceil(points.max(axis=0)).astype(int),size-1)
        if np.any(high<low):continue
        a,b,c=points; denominator=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(denominator)<1e-10:continue
        x,y=np.meshgrid(np.arange(low[0],high[0]+1)+.5,np.arange(low[1],high[1]+1)+.5)
        w0=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/denominator
        w1=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/denominator
        w2=1-w0-w1
        inside=(w0>=-1e-7)&(w1>=-1e-7)&(w2>=-1e-7)
        weights=np.stack([w0,w1,w2],axis=-1)
        mapped=weights @ uv[index]
        # Native hair uses wrapping UVs. Exact upper edge samples the last
        # texel; out-of-range UVs wrap rather than silently clamp the atlas.
        mapped=np.where((mapped>=0)&(mapped<=1),mapped,np.mod(mapped,1))
        tx=np.clip((mapped[:,:,0]*aw).astype(int),0,aw-1)
        ty=np.clip((mapped[:,:,1]*ah).astype(int),0,ah-1)
        solid=inside & (alpha[ty,tx]>=.333)
        sl=(slice(low[1],high[1]+1),slice(low[0],high[0]+1))
        cards[sl]+=inside;opaque[sl]+=solid
        z=weights @ p[face,2]; visible=solid & (z>depth[sl])
        if skin_depth is not None:visible &= z>skin_depth[sl]+.005
        depth[sl][visible]=z[visible];front[sl][visible]=index
    return dict(front=front,mask=front>=0,opaque=opaque,cards=cards,bounds=bounds,depth=depth,
                **({} if skin_depth is None else {'skin_depth':skin_depth}))


def audit(positions, triangles, uv, alpha, reference=None, skin=None):
    frames=[]
    for i,basis in enumerate(views()):
        bounds=None if reference is None else reference[i]['bounds']
        if bounds is None:
            projected=np.asarray(positions)@basis.T
            bounds=(projected[:,:2].min(axis=0)-.15,projected[:,:2].max(axis=0)+.15)
        depth=None if reference is None else reference[i].get('skin_depth')
        if skin is not None:
            sp,st=skin
            depth=raster(sp,st,np.zeros((len(st),3,2)),np.ones((1,1)),basis,bounds)['depth']
        frames.append(raster(positions,triangles,uv,alpha,basis,bounds,skin_depth=depth))
    ids=set(int(v) for frame in frames for v in np.unique(frame['front']) if v>=0)
    return frames,ids


def envelope(mask):
    # Close one-pixel gaps between alpha strands. This measures the visible
    # hairstyle envelope separately from strand-pattern pixel agreement.
    padded=np.pad(mask,1)
    expanded=np.logical_or.reduce([padded[y:y+mask.shape[0],x:x+mask.shape[1]] for y in range(3) for x in range(3)])
    padded=np.pad(expanded,1)
    return np.logical_and.reduce([padded[y:y+mask.shape[0],x:x+mask.shape[1]] for y in range(3) for x in range(3)])


def compact_hair_mask(alpha,radius=2):
    """Merge small strand gaps on a periodic radial atlas, retaining its outline."""
    mask=np.asarray(alpha)>=.333
    def shifts(values):
        padded=np.pad(values,((radius,radius),(0,0)),mode='edge')
        return [np.roll(padded[dy:dy+len(values)],dx,axis=1)
                for dy in range(2*radius+1) for dx in range(-radius,radius+1)]
    return np.logical_and.reduce(shifts(np.logical_or.reduce(shifts(mask)))).astype(np.float32)


def compare(old,new):
    ious=[]; missing=[];raw=[]
    for a,b in zip(old,new):
        union=np.count_nonzero(a['mask']|b['mask'])
        raw.append(np.count_nonzero(a['mask']&b['mask'])/union if union else 1.)
        left,right=envelope(a['mask']),envelope(b['mask'])
        union=np.count_nonzero(left|right)
        ious.append(np.count_nonzero(left&right)/union if union else 1.)
        missing.append(np.count_nonzero(left&~right)/max(np.count_nonzero(left),1))
    def fragments(frames,key):return int(sum(f[key].sum() for f in frames))
    return dict(silhouette_iou_min=min(ious),silhouette_iou_mean=float(np.mean(ious)),
                missing_coverage_max=max(missing),raw_alpha_iou_mean=float(np.mean(raw)),envelope_gap_close_pixels=1,
                card_fragments_before=fragments(old,'cards'),card_fragments_after=fragments(new,'cards'),
                alpha_fragments_before=fragments(old,'opaque'),alpha_fragments_after=fragments(new,'opaque'),
                views=len(old),sample_resolution=72,hardware_profiled=False)


def atlas_uv(uv,source_bounds,destination_bounds,size=128):
    uv=np.asarray(uv);lo,hi=np.asarray(source_bounds)
    start,end=np.asarray(destination_bounds)
    if np.any(hi<=lo):raise ValueError('Atlas source has empty UV extent')
    if np.any(uv<lo-1e-5) or np.any(uv>hi+1e-5):raise ValueError('UV outside the declared atlas tile')
    return (start+(uv-lo)/(hi-lo)*(end-start))/size

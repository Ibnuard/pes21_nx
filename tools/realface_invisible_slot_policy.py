"""Prove a masked source slot has no renderable hair before replacing it.

A raster returning no pixels is insufficient. Every triangle must additionally
have an entirely transparent conservative UV footprint, or be a rigid head
marker at most 0.003 cm across. Skin and nonfinite source data are rejected.
"""
import math
import numpy as np

CUTOFF = .333


def rigid_pose_diameters(local_positions, triangles, bindings, bone_from_local, native_rotations):
    """Conservative edge bound for equal-weight corners under any rigid pose.

    Translations cancel for identical skin weights; the triangle edge cannot
    exceed the weighted sum of its lengths in each influencing bone frame.
    """
    local=np.asarray(local_positions,dtype=float); result=[]
    for face in triangles:
        weights=bindings[face[0]]
        if any(bindings[i]!=weights for i in face):
            result.append(float('inf'));continue
        edges=[local[face[i]]-local[face[j]] for i,j in ((0,1),(1,2),(2,0))]
        bounds=[]
        for edge in edges:
            bound=0.
            for bone,weight in weights.items():
                transform=np.asarray(bone_from_local[bone],dtype=float)[:3,:3]
                rotation=np.asarray(native_rotations[bone],dtype=float)[:3,:3]
                if not np.isfinite(transform).all() or np.linalg.svd(rotation,compute_uv=False).max()>1.001:
                    raise ValueError('Source marker requires verified rigid native bone frames')
                bound+=weight*float(np.linalg.norm(transform@edge))*1.001
            bounds.append(bound)
        result.append(max(bounds))
    return np.asarray(result)


def alpha_footprint_hidden(coords,alpha,lo,hi):
    """Conservative triangle/texel support test, including repeat and filtering."""
    height,width=alpha.shape
    if (hi[0]-lo[0]+1)*(hi[1]-lo[1]+1)>2_000_000:
        return False
    xs=np.arange(lo[0],hi[0]+1);ys=np.arange(lo[1],hi[1]+1)
    yy,xx=np.nonzero(alpha[np.ix_(ys%height,xs%width)]>CUTOFF)
    if not len(xx):return True
    centers=np.column_stack((xs[xx]+.5,ys[yy]+.5))
    triangle=coords*[width,height]
    # Expanded texel squares contain the complete bilinear sample support.
    half=1.5; intersects=np.ones(len(centers),dtype=bool)
    for i in range(3):
        edge=triangle[(i+1)%3]-triangle[i];normal=np.asarray((-edge[1],edge[0]))
        projection=triangle@normal;middle=centers@normal
        radius=half*np.abs(normal).sum()
        intersects&=(middle+radius>=projection.min()-1e-8)&(middle-radius<=projection.max()+1e-8)
    # Include x/y separating axes for degenerate point/line UV triangles.
    intersects&=((centers+half>=triangle.min(axis=0)-1e-8)&
                 (centers-half<=triangle.max(axis=0)+1e-8)).all(axis=1)
    return not intersects.any()


def classify_triangles(positions, triangles, uv, alpha, bindings, pose_diameters=None):
    p = np.asarray(positions, dtype=float); t = np.asarray(triangles, dtype=int)
    st = np.asarray(uv, dtype=float); a = np.asarray(alpha, dtype=float)
    if (p.ndim != 2 or p.shape[1:] != (3,) or not len(p) or
            t.ndim != 2 or t.shape[1:] != (3,) or not len(t) or
            st.shape != (len(t), 3, 2) or a.ndim != 2 or min(a.shape) < 1 or
            len(bindings) != len(p) or t.min() < 0 or t.max() >= len(p) or
            not all(np.isfinite(x).all() for x in (p, st, a)) or
            a.min() < 0 or a.max() > 1 or np.abs(st).max() > 16):
        raise ValueError('Finite complete source geometry, UVs, alpha and bindings required')
    for weights in bindings:
        if (not weights or any(not math.isfinite(v) or v < 0 for v in weights.values()) or
                abs(sum(weights.values())-1) > 1e-5):
            raise ValueError('Invalid source marker binding')
    height, width = a.shape
    if pose_diameters is not None and len(pose_diameters)!=len(t):
        raise ValueError('A rigid pose bound is required for each source triangle')
    result = dict(alpha_hidden=0, rigid_microscopic=0, unproven=0)
    for number,(face, coords) in enumerate(zip(t, st)):
        # Include neighboring texels to cover bilinear filtering and wrap.
        lo = np.floor(coords.min(axis=0)*[width, height]-1).astype(int)
        hi = np.ceil(coords.max(axis=0)*[width, height]+1).astype(int)
        xs = np.arange(width) if hi[0]-lo[0]+1 >= width else np.arange(lo[0],hi[0]+1) % width
        ys = np.arange(height) if hi[1]-lo[1]+1 >= height else np.arange(lo[1],hi[1]+1) % height
        if (a[np.ix_(ys,xs)].max() <= CUTOFF or
                alpha_footprint_hidden(coords,a,lo,hi)):
            result['alpha_hidden'] += 1
            continue
        q = p[face]
        edges = [np.linalg.norm(q[i]-q[j]) for i,j in ((0,1),(1,2),(2,0))]
        rigid = (max(edges)<=.003 and all(bindings[i]=={'sk_head':1.0} for i in face))
        if pose_diameters is not None:
            rigid=rigid or (math.isfinite(pose_diameters[number]) and 0<=pose_diameters[number]<=.003)
        if (rigid and
                np.abs(q[:,0]).max() < 15 and q[:,1].min() > -20 and q[:,1].max() < 25 and
                q[:,2].min() > 150 and q[:,2].max() < 195):
            result['rigid_microscopic'] += 1
        else:
            result['unproven'] += 1
    return result


def verified_invisible_cards(positions, triangles, uv, alpha, bindings, materials,
                             hair_skin_materials, visible_triangles, pose_diameters=None, source_part_proof=None):
    if (not materials or any(not m.startswith('rf_hair') for m in materials) or
            hair_skin_materials or (visible_triangles != 0 and source_part_proof is None)):
        raise ValueError('Only classified hair with zero source-view coverage is eligible')
    result = classify_triangles(positions,triangles,uv,alpha,bindings,pose_diameters)
    if source_part_proof is not None:
        from realface_source_empty_part import validate_source_part
        validate_source_part(source_part_proof)
        result.update(unproven=0,authored_pc_source_part=source_part_proof,
                      rejected_native_conversion_visible_triangles=visible_triangles,
                      projection_reference='verified_empty_PC_source_part')
    if result['unproven']:
        raise ValueError('Source slot contains unproven triangles: '+str(result))
    return dict(policy='proven_alpha_hidden_or_rigid_microscopic_source_slot_v1',
                **result, source_triangles=len(triangles), source_views=13,
                visible_source_removed=False, source_skin_changed=False,
                replacement_triangles=1, hair_alpha_cutoff=CUTOFF)

"""Interpolate isolated collar seam tips from already fitted mesh neighbours."""
import numpy as np


def supported_seam_moves(points, fitted, faces, changed, unresolved, max_move):
    points=np.asarray(points,dtype=float);fitted=np.asarray(fitted,dtype=float)
    if (points.ndim!=2 or points.shape[1]!=3 or fitted.shape!=points.shape or
            not np.isfinite(points).all() or not np.isfinite(fitted).all() or
            not np.isfinite(max_move) or max_move<=0):
        raise ValueError('Collar support requires finite matching geometry and movement budget')
    changed=set(changed);unresolved=set(unresolved);all_unresolved=set(unresolved);result=[]
    while unresolved:
        first=min(unresolved)
        group={i for i in unresolved if np.linalg.norm(points[i]-points[first])<1e-4}
        cluster=set(group)
        while True:
            linked={i for f in faces if cluster.intersection(f) for i in f}&all_unresolved
            linked|={i for i in all_unresolved if any(np.linalg.norm(points[i]-points[j])<1e-4 for j in cluster)}
            if linked<=cluster:break
            cluster|=linked
        physical={tuple(np.round(points[i],4)) for i in cluster}
        if len(physical)>4 or max(np.linalg.norm(points[i]-points[first]) for i in cluster)>2:
            raise ValueError('Unresolved collar patch is too large for local support')
        incident=[f for f in faces if cluster.intersection(f)]
        adjacent={i for f in incident for i in f}-all_unresolved
        # UV-seam aliases must move together. All their neighbours must have
        # passed the ordinary measured-reference fit, without chaining repairs.
        if not adjacent<=changed:raise ValueError('Unresolved collar tip lacks fully fitted neighbours')
        unique={}
        for i in sorted(adjacent):
            distance=float(np.linalg.norm(points[i]-points[first]))
            if not .1<distance<=3 or any(np.linalg.norm(points[i]-points[j])>3 for j in cluster):
                raise ValueError('Collar support is outside the local one-ring')
            unique.setdefault(tuple(np.round(points[i],4)),i)
        ids=list(unique.values())
        if len(ids)<4:raise ValueError('Collar tip needs four distinct physical neighbours')
        deltas=fitted[ids]-points[ids]
        weight=1/np.linalg.norm(points[ids]-points[first],axis=1)
        delta=np.average(deltas,axis=0,weights=weight)
        spread=float(np.max(np.linalg.norm(deltas-delta,axis=1)))
        if spread>.5 or np.linalg.norm(delta)>max_move+1e-5:
            raise ValueError('Collar neighbours do not support a coherent bounded move: '+str(dict(spread=spread,move=float(np.linalg.norm(delta)),points=points[ids].tolist(),deltas=deltas.tolist())))
        proposed=fitted.copy()
        for i in cluster:proposed[i]=points[i]+delta
        minimum_cosine=1.
        for face in incident:
            a,b,c=points[list(face)];x,y,z=proposed[list(face)]
            old=np.cross(b-a,c-a);new=np.cross(y-x,z-x)
            old_area=np.linalg.norm(old);new_area=np.linalg.norm(new)
            if old_area<1e-10:continue
            cosine=float(old@new/max(old_area*new_area,1e-20));minimum_cosine=min(minimum_cosine,cosine)
            if cosine<.5 or not .25<new_area/old_area<4:
                raise ValueError('Supported collar move would fold or collapse a triangle')
        result.append(dict(indices=sorted(cluster),delta_cm=delta.tolist(),support_indices=ids,
                           support_spread_cm=spread,minimum_triangle_normal_cosine=minimum_cosine))
        unresolved-=cluster
    return result

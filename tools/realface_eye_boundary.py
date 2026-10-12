"""Measure a closed orbital recess from frontal skin depths.

The eyelid surface can be topologically closed by an inner socket wall, so
mesh boundary edges alone are insufficient. A bounded vertical closing finds
a recess enclosed by upper/lower skin. Only one interior anatomical opening
per side is accepted. This is a fitting reference, never replacement geometry.
"""
import numpy as np


def opening_from_depth(xs, zs, depth, *, shallow=False):
    xs=np.asarray(xs,dtype=float);zs=np.asarray(zs,dtype=float);depth=np.asarray(depth,dtype=float)
    if (depth.shape!=(len(zs),len(xs)) or min(depth.shape)<30 or
            not np.isfinite(depth).all() or not np.isfinite(xs).all() or not np.isfinite(zs).all()):
        raise ValueError('Orbital scan requires a finite depth grid')
    step=float(np.mean(np.diff(zs)))
    if not .025<=step<=.08 or not np.allclose(np.diff(zs),step):
        raise ValueError('Orbital scan spacing differs from contract')
    radius=round(.72/step)
    def vertical(values, operation):
        padded=np.pad(values,((radius,radius),(0,0)),mode='edge')
        return operation([padded[i:i+len(values)] for i in range(radius*2+1)],axis=0)
    recess=vertical(vertical(depth,np.max),np.min)-depth
    unseen=set(map(tuple,np.argwhere(recess>(.4 if shallow else .65))));candidates=[]
    while unseen:
        start=unseen.pop();component={start};todo=[start]
        while todo:
            z,x=todo.pop()
            for neighbor in ((z-1,x),(z+1,x),(z,x-1),(z,x+1)):
                if neighbor in unseen:
                    unseen.remove(neighbor);component.add(neighbor);todo.append(neighbor)
        indices=np.asarray(sorted(component));low,high=indices.min(0),indices.max(0)
        if 0 in low or high[0]==len(zs)-1 or high[1]==len(xs)-1:continue
        width=abs(xs[high[1]]-xs[low[1]]);height=zs[high[0]]-zs[low[0]]
        if not (1.4<width<3.5 and .25<height<1.65 and len(component)>=50
                and max(recess[z,x] for z,x in component)>(.65 if shallow else .9)):continue
        # Sample the actual upper/lower lid surface just outside the inner
        # recess wall, at three scan steps (about 0.18 cm). The vertical wall
        # itself is not a sphere surface and biases globe depth backwards.
        if low[0]<3 or high[0]>=len(zs)-3:continue
        boundary=[]
        for x in range(low[1],high[1]+1):
            column=[z for z,q in component if q==x]
            if column:
                boundary.extend(((min(column)-3,x),(max(column)+3,x)))
        rim=np.asarray([(xs[x],depth[z,x],zs[z]) for z,x in boundary])
        if not (8<rim[:,1].min() and rim[:,1].max()<20):continue
        candidates.append(rim)
    if len(candidates)!=1:
        raise ValueError('Orbital scan needs one enclosed unambiguous recess per eye')
    return candidates[0].tolist()


def rim_variants(xs, zs, depth):
    """Bounded alternative measurements, not altered head/eye geometry.

    Tear-duct corners need not lie on the spherical eyeball. A second fit may
    exclude at most 0.18 cm at each end, while optical validation still scans
    the complete aperture. Shallow recesses retain all anatomical/uniqueness
    requirements; the sphere fitter's scale/depth/translation limits stay fixed.
    """
    result=[]
    for shallow in (False, True):
        try:
            bounds=np.asarray(opening_from_depth(xs,zs,depth,shallow=shallow))
        except ValueError:
            continue
        for trim in (False, True):
            rim=bounds
            if trim:
                low,high=bounds[:,0].min(),bounds[:,0].max()
                rim=bounds[(bounds[:,0]>=low+.179)&(bounds[:,0]<=high-.179)]
                if len(rim)<24 or np.ptp(rim[:,0])<1.4:continue
            name=('shallow' if shallow else 'strict')+('_central_rim' if trim else '')
            result.append(dict(name=name,rim=rim.tolist(),bounds=bounds.tolist()))
    return result

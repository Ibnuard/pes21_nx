"""Recognize bind-roundoff seam aliases without moving exported vertices."""
from itertools import product
import math


def canonical_positions(positions, weights, tolerance=.0002):
    """Return simplifier-only positions; join only equal skinning within 2 um.

    Search neighbouring spatial cells instead of rounding to a grid: two seam
    copies can straddle a grid boundary. Every member stays within tolerance
    of its representative; long chains cannot join distant anatomical points.
    The caller must still export the original positions, UVs and weights.
    """
    if len(positions)!=len(weights) or not 0<tolerance<=.0002:
        raise ValueError('Invalid native seam alias contract')
    buckets={};result=[];joined=0;maximum=0.
    for index,(position,weight) in enumerate(zip(positions,weights)):
        p=tuple(map(float,position));weight=tuple(weight)
        if len(p)!=3 or not all(map(math.isfinite,p)):
            raise ValueError('Non-finite native seam position')
        cell=tuple(math.floor(v/tolerance) for v in p);matches=[]
        if weight:
            for delta in product((-1,0,1),repeat=3):
                key=(weight,*(a+b for a,b in zip(cell,delta)))
                for previous in buckets.get(key,()):
                    distance=sum((a-b)**2 for a,b in zip(p,result[previous]))
                    if distance<=tolerance*tolerance:matches.append((distance,previous))
        if matches:
            distance,previous=min(matches);result.append(result[previous])
            joined+=int(p!=result[previous]);maximum=max(maximum,math.sqrt(distance))
        else:
            result.append(p);buckets.setdefault((weight,*cell),[]).append(index)
    return result,dict(policy='bind_roundoff_seam_alias',tolerance_cm=tolerance,
        aliased_vertices=joined,maximum_alias_cm=maximum,
        simplifier_positions_only=True,exported_positions_unchanged=True)

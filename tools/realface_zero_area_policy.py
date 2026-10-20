"""Exact duplicate weighted corners cannot form a triangle in any pose."""
import math


def zero_area_in_every_pose(positions,bindings):
    if len(positions)!=3 or len(bindings)!=3:
        raise ValueError('Three complete weighted corners required')
    if any(len(p)!=3 or any(not math.isfinite(float(v)) for v in p) for p in positions):
        raise ValueError('Nonfinite source corners cannot be repaired by deletion')
    if any(not b or any(not math.isfinite(w) or w<0 for w in b.values()) or
           abs(sum(b.values())-1)>1e-5 for b in bindings):
        raise ValueError('Invalid source weights')
    return any(tuple(positions[i])==tuple(positions[j]) and bindings[i]==bindings[j]
               for i in range(3) for j in range(i))

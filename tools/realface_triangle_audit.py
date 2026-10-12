"""Prove surviving triangle connectivity when UE drops some zero-area faces."""
from collections import defaultdict
from itertools import permutations, product
import math
from realface_cook_policy import collapsed_triangle


def surviving_triangles(source,cooked,position_limit=.03,*,_broad=False):
    source=[t for t in source if not collapsed_triangle(t['points'])]
    cooked=[t for t in cooked if not collapsed_triangle(t['points'])]
    if len(source)!=len(cooked):
        raise ValueError('Noncollapsed triangle count changed: '+str((len(source),len(cooked))))
    def cell(t):
        return tuple(math.floor(sum(p[k] for p in t['points'])/3/position_limit) for k in range(3))
    cells=defaultdict(list)
    for i,t in enumerate(source):cells[cell(t)].append(i)
    def signature(t):
        # A fast candidate index only; exact tolerance checks still follow.
        return tuple(sorted(tuple(round(v,3) for v in (*p,*uv)) for p,uv in zip(t['points'],t['uv'])))
    signatures=defaultdict(list)
    for i,t in enumerate(source):signatures[signature(t)].append(i)
    source_uv_centers=[tuple(sum(uv[k] for uv in t['uv'])/3 for k in range(2)) for t in source]
    orders=list(permutations(range(3)));offsets=list(product((-1,0,1),repeat=3))
    edges=[]
    for t in cooked:
        center=cell(t);matches=[]
        uv_center=tuple(sum(uv[k] for uv in t['uv'])/3 for k in range(2))
        broad=[i for offset in offsets for i in cells.get(tuple(a+b for a,b in zip(center,offset)),())]
        for candidates in ((broad,) if _broad else (signatures.get(signature(t),()),broad)):
            for index in candidates:
                if any(abs(a-b)>=.001 for a,b in zip(uv_center,source_uv_centers[index])):continue
                s=source[index]
                for order in orders:
                    if any(math.dist(t['points'][k],s['points'][j])>=position_limit for k,j in enumerate(order)):continue
                    if any(max(abs(a-b) for a,b in zip(t['uv'][k],s['uv'][j]))>=.001 for k,j in enumerate(order)):continue
                    if any(sum(abs(t['weights'][k].get(b,0)-s['weights'][j].get(b,0))
                               for b in t['weights'][k].keys()|s['weights'][j].keys())>=.025 for k,j in enumerate(order)):continue
                    matches.append(index);break
            if matches:break
        if not matches:raise ValueError('Cooked triangle has no matching source position/UV/weight connectivity')
        edges.append(matches)
    # One-to-one coverage: a duplicate cooked triangle cannot substitute for
    # another source triangle, even when all vertices still exist elsewhere.
    assigned={}
    def assign(index,seen):
        for candidate in edges[index]:
            if candidate not in assigned and candidate not in seen:
                assigned[candidate]=index;return True
        for candidate in edges[index]:
            if candidate in seen:continue
            seen.add(candidate)
            if candidate not in assigned or assign(assigned[candidate],seen):
                assigned[candidate]=index;return True
        return False
    for index in sorted(range(len(edges)),key=lambda i:len(edges[i])):
        if not assign(index,set()):
            # Rounded signatures only accelerate candidate discovery. A bin
            # boundary must never exclude a valid augmenting-path match.
            if not _broad:return surviving_triangles(source,cooked,position_limit,_broad=True)
            raise ValueError('Cooked triangles do not cover every source surface once')
    return dict(noncollapsed_source_triangles=len(source),noncollapsed_cooked_triangles=len(cooked),
                connectivity_uv_weights_match=True)

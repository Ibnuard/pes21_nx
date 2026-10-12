"""Match complete position/UV/weight tuples without quadratic seam scans."""
from collections import defaultdict
from itertools import product
import math


def match_vertices(points,uvs,weights,source_points,source_uvs,source_weights,limit):
    if not math.isfinite(limit) or limit<=0:raise ValueError('Invalid vertex distance tolerance')
    for point,options,weight in zip(source_points,source_uvs,source_weights):
        if not all(math.isfinite(v) for v in point) or not all(math.isfinite(v) for uv in options for v in uv) or not all(math.isfinite(v) for v in weight.values()):
            raise ValueError('Non-finite source vertex tuple')
    records=[];seen=set();cells=defaultdict(list)
    for point,options,weight in zip(source_points,source_uvs,source_weights):
        for uv in options:
            key=(tuple(point),tuple(uv),tuple(sorted(weight.items())))
            if key in seen:continue
            seen.add(key);index=len(records);records.append((point,uv,weight))
            cells[tuple(math.floor(x/.001) for x in uv)].append(index)
    offsets=list(product((-1,0,1),repeat=2));errors=[];uv_errors=[];weight_errors=[];cache={}
    for point,uv,weight in zip(points,uvs,weights):
        if not all(math.isfinite(v) for v in (*point,*uv,*weight.values())):
            raise ValueError('Non-finite cooked vertex tuple')
        key=(tuple(point),tuple(uv),tuple(sorted(weight.items())))
        best=cache.get(key)
        if best is None:
            cell=tuple(math.floor(x/.001) for x in uv);best=None
            for offset in offsets:
                for index in cells.get(tuple(a+b for a,b in zip(cell,offset)),()):
                    old,st,bones=records[index]
                    u=max(abs(a-b) for a,b in zip(uv,st))
                    if u>=.001:continue
                    d=math.dist(point,old)
                    if d>=limit:continue
                    w=sum(abs(weight.get(b,0)-bones.get(b,0)) for b in weight.keys()|bones.keys())
                    if w>=.025:continue
                    # One complete supporting tuple is sufficient. Ranking
                    # thousands of coincident seams cannot strengthen this
                    # existence check and used to dominate validation time.
                    best=(d,u,w);break
                if best is not None:break
            if best is None:raise ValueError('Cooked vertex has no matching source position/UV/weight tuple')
            cache[key]=best
        d,u,w=best;errors.append(d);uv_errors.append(u);weight_errors.append(w)
    return errors,uv_errors,weight_errors

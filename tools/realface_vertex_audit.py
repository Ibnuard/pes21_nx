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


def match_normals(points,uvs,normals,source_corners,position_limit,angle_limit=2.):
    """Check imported shading at the same position/UV, including split seams."""
    def unit(n):
        if not all(math.isfinite(v) for v in n):raise ValueError('Non-finite shading normal')
        length=math.sqrt(sum(v*v for v in n))
        if length<.5:raise ValueError('Invalid shading normal')
        return tuple(v/length for v in n)
    cells=defaultdict(list)
    for point,uv,normal in source_corners:
        cells[tuple(math.floor(v/.001) for v in uv)].append((point,uv,unit(normal)))
    errors=[]
    for point,uv,normal in zip(points,uvs,normals):
        normal=unit(normal);cell=tuple(math.floor(v/.001) for v in uv);dots=[]
        for offset in product((-1,0,1),repeat=2):
            for old,st,expected in cells.get(tuple(a+b for a,b in zip(cell,offset)),()):
                if max(abs(a-b) for a,b in zip(uv,st))<.001 and math.dist(point,old)<position_limit:
                    dots.append(sum(a*b for a,b in zip(normal,expected)))
        if not dots:raise ValueError('Cooked normal has no matching source corner')
        angle=math.degrees(math.acos(max(-1.,min(1.,max(dots)))))
        if angle>angle_limit:raise ValueError('Cooked shading normal changed: %.3f degrees'%angle)
        errors.append(angle)
    return dict(corners_checked=len(errors),max_angle_degrees=max(errors),limit_degrees=angle_limit)

"""Build a cheap continuous backing under reviewed disconnected stair meshes.

Runs outside Blender with the optional local Shapely installation. The XY
footprint is the union of original upward faces, including its holes. Source
heights/UVs are sampled locally; the backing sits 35 cm below the steps. It is
not collision geometry and must be counted in the final stadium budget.
"""
import argparse
import json
import math
from pathlib import Path
import sys


def build(row,cell=8.):
    import numpy as np
    from shapely import polygons,union_all,box,Point,constrained_delaunay_triangles
    from shapely.strtree import STRtree
    p=np.asarray(row['positions']).reshape(-1,3)
    uv=np.asarray(row['uv']).reshape(-1,2)
    ids=np.asarray(row['indices']).reshape(-1,3)
    tri=p[ids];norm=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    ids=ids[norm[:,2]>np.linalg.norm(norm,axis=1)*.2]
    tri=p[ids];regions=polygons(tri[:,:,:2]);tree=STRtree(regions)
    footprint=union_all(regions,grid_size=.002).simplify(.002,preserve_topology=True)
    shapes=list(footprint.geoms) if hasattr(footprint,'geoms') else [footprint]
    cache={};positions=[];texcoords=[];indices=[]
    def sample(x,y):
        key=(round(x,6),round(y,6))
        if key in cache:return cache[key]
        point=Point(x,y);candidates=tree.query(point.buffer(.005))
        if not len(candidates):candidates=[tree.nearest(point)]
        candidates=sorted(candidates,key=lambda i:regions[i].distance(point))
        nearest=regions[candidates[0]].distance(point)
        choices=[]
        for i in candidates:
            if regions[i].distance(point)>nearest+.0001:continue
            a,b,c=tri[i];matrix=np.column_stack((b[:2]-a[:2],c[:2]-a[:2]))
            weights=np.linalg.solve(matrix,np.array([x,y])-a[:2])
            w=np.clip([1-weights.sum(),*weights],0,1);w/=w.sum()
            choices.append((float(w@tri[i,:,2]),w@uv[ids[i]]))
        z,t=max(choices,key=lambda value:value[0])
        index=len(positions)//3;positions.extend((x,y,z-.35));texcoords.extend(t.tolist());cache[key]=index
        return index
    for shape in shapes:
        if shape.geom_type!='Polygon' or shape.area<1e-6:continue
        lo_x,lo_y,hi_x,hi_y=shape.bounds
        for gx in range(math.floor(lo_x/cell),math.ceil(hi_x/cell)):
            for gy in range(math.floor(lo_y/cell),math.ceil(hi_y/cell)):
                patch=shape.intersection(box(gx*cell,gy*cell,(gx+1)*cell,(gy+1)*cell))
                if patch.is_empty or patch.area<1e-6:continue
                for polygon in constrained_delaunay_triangles(patch).geoms:
                    xy=list(polygon.exterior.coords)[:3]
                    signed=(xy[1][0]-xy[0][0])*(xy[2][1]-xy[0][1])-(xy[1][1]-xy[0][1])*(xy[2][0]-xy[0][0])
                    if abs(signed)<1e-9:continue
                    if signed<0:xy[1],xy[2]=xy[2],xy[1]
                    indices.extend(sample(*v) for v in xy)
    return dict(name=row['name'],positions=positions,uv=texcoords,indices=indices,
                footprint_area_m2=footprint.area,cell_m=cell,clearance_m=.35,
                footprint_tolerance_m=.002,method='source_footprint_backing')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--modules',type=Path,required=True)
    args=parser.parse_args();sys.path.insert(0,str(args.modules))
    result=[build(row) for row in json.loads(args.input.read_text())['materials']]
    args.output.write_text(json.dumps(result))

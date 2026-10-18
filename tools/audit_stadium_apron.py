"""Sample actual cooked shell/native-floor overlap without saving game geometry.

Requires owned UModel glTF exports. Samples the apron at 0.75 m spacing and
reports near-height intersections separately from near-parallel floor layers.
This is a geometric regression check, not a raster/flicker or GPU benchmark.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from audit_stadium_optimization import accessor


def ground_triangles(path):
    doc=json.loads(path.read_text());blob=(path.parent/doc['buffers'][0]['uri']).read_bytes()
    result=[]
    for primitive in doc['meshes'][0]['primitives']:
        name=doc['materials'][primitive['material']]['name']
        positions=accessor(doc,blob,primitive['attributes']['POSITION'])
        indices=accessor(doc,blob,primitive['indices']).reshape(-1,3)
        tris=positions[indices].astype(float)
        tris=tris[(np.abs(tris[:,:,1]).max(1)<1.5)&(np.ptp(tris[:,:,1],axis=1)<.3)]
        for triangle in tris:
            normal=np.cross(triangle[1]-triangle[0],triangle[2]-triangle[0])
            length=np.linalg.norm(normal)
            if length>1e-10:result.append((triangle,name,normal/length))
    return result


def layers(triangles,points):
    result=[[] for _ in points]
    for triangle,name,normal in triangles:
        a,b,c=triangle[:,[0,2]];u=b-a;v=c-a
        det=u[0]*v[1]-u[1]*v[0]
        if abs(det)<1e-9:continue
        rel=points-a
        w=(rel[:,0]*v[1]-rel[:,1]*v[0])/det
        q=(u[0]*rel[:,1]-u[1]*rel[:,0])/det
        for i in np.nonzero((w>1e-6)&(q>1e-6)&(w+q<1-1e-6))[0]:
            height=float(triangle[0,1]+w[i]*(triangle[1,1]-triangle[0,1])+q[i]*(triangle[2,1]-triangle[0,1]))
            result[i].append((height,name,normal))
    return result


def compare(native,shell,points):
    out=dict(samples=len(points),native_close_samples=0,native_parallel_close_samples=0,
        self_close_height_samples=0,self_parallel_close_samples=0,parallel_cosine_min=.9995,
        height_tolerance_m=.01,native_examples=[],self_examples=[])
    for i,(a,b) in enumerate(zip(native,shell)):
        for za,ma,na in a:
            for zb,mb,nb in b:
                if abs(za-zb)>=.01:continue
                out['native_close_samples']+=1
                if abs(float(np.dot(na,nb)))>=.9995:
                    out['native_parallel_close_samples']+=1
                    if len(out['native_examples'])<12:out['native_examples'].append(dict(point=points[i].tolist(),materials=[ma,mb],height=[za,zb]))
        for j,(za,ma,na) in enumerate(b):
            for zb,mb,nb in b[j+1:]:
                if abs(za-zb)>=.01:continue
                out['self_close_height_samples']+=1
                if abs(float(np.dot(na,nb)))>=.9995:
                    out['self_parallel_close_samples']+=1
                    if len(out['self_examples'])<12:out['self_examples'].append(dict(point=points[i].tolist(),materials=[ma,mb],height=[za,zb]))
    out['self_nonparallel_close_samples']=out['self_close_height_samples']-out['self_parallel_close_samples']
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-pitch',type=Path,required=True)
    p.add_argument('--meshes',type=Path,required=True,help='Folder containing <key>/<key>Shell.gltf')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--strict',action='store_true',help='Fail sampled near-parallel floor overlaps')
    a=p.parse_args()
    points=np.array([(x,z) for x in np.arange(-72.123,72,.75) for z in np.arange(-43.234,43,.75) if abs(x)>53.5 or abs(z)>35])
    native=layers(ground_triangles(a.native_pitch),points);rows=[]
    for folder in sorted(a.meshes.iterdir()):
        mesh=folder/(folder.name+'Shell.gltf')
        if not mesh.is_file():continue
        row=compare(native,layers(ground_triangles(mesh),points),points)
        row['key']=folder.name;rows.append(row)
    if not rows:raise ValueError('No owned cooked shell glTF exports found')
    a.output.write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps([dict(key=r['key'],native=r['native_parallel_close_samples'],parallel_self=r['self_parallel_close_samples'],angled_self=r['self_nonparallel_close_samples']) for r in rows]))
    if a.strict and any(r['native_parallel_close_samples'] or r['self_parallel_close_samples'] for r in rows):
        raise ValueError('Sampled near-parallel floor overlap remains; inspect local report')


if __name__=='__main__':main()

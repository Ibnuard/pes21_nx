"""Audit existing cooked verification exports in the native reference pose.

No editor/Blender process, asset mutation or geometry reduction. Bind-space
bounds alone are misleading when the importer compensates different rest rigs.
This is offline reference-pose evidence, never a device visibility/FPS pass.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from audit_realface_rig import audit_rig
from realface_reference import load_reference

ROOT=Path(__file__).resolve().parents[1]


def rig_globals(rows):
    matrices=[]
    result={}
    for index,bone in enumerate(rows):
        values=np.asarray(bone['trs'],dtype=float)
        parent=bone['parent']
        if (values.shape!=(10,) or not np.isfinite(values).all() or
                not -1<=parent<index or bone['name'] in result):
            raise ValueError('Invalid reference rig')
        q=values[:4]
        length=float(np.linalg.norm(q))
        if length<1e-8 or any(abs(v)<1e-8 for v in values[7:]):
            raise ValueError('Singular reference rig')
        x,y,z,w=q/length
        rotation=np.array([
            [1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
            [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
            [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
        matrix=np.eye(4)
        matrix[:3,:3]=rotation@np.diag(values[7:])
        matrix[:3,3]=values[4:7]
        if parent>=0: matrix=matrices[parent]@matrix
        matrices.append(matrix)
        result[bone['name']]=matrix
    return result


def pose_points(mesh,native,cooked):
    if set(native)!=set(cooked): raise ValueError('Rig bone ownership differs')
    transforms={n:native[n]@np.linalg.inv(cooked[n]) for n in native}
    points=[]
    for point,weights in zip(mesh['vertices'],mesh['weights'],strict=True):
        if (not weights or any(n not in transforms or not np.isfinite(w) or w<0
                               for n,w in weights.items()) or abs(sum(weights.values())-1)>.01):
            raise ValueError('Invalid skin weights')
        matrix=sum((transforms[n]*w for n,w in weights.items()))
        points.append((matrix@np.array([*point,1]))[:3])
    result=np.asarray(points)
    if result.shape!=(len(mesh['vertices']),3) or not len(result) or not np.isfinite(result).all():
        raise ValueError('Invalid native reference-pose geometry')
    return result


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def audit_profile(path):
    path=Path(path).resolve()
    profile=json.loads(path.read_text(encoding='utf-8-sig'))
    native_path,contract_path=map(Path,(profile['native_rig'],profile['cooked_rig']))
    native=rig_globals(json.loads(native_path.read_text(encoding='utf-8-sig')))
    contract=json.loads(contract_path.read_text(encoding='utf-8-sig'))
    hashes={str(p):sha(p) for p in (path,native_path,contract_path)}
    records={}
    for kind in ('face','hair'):
        spec=profile['parts'][kind]
        asset_path,gltf_path=map(Path,(spec['cooked_mesh_json'],spec['gltf']))
        asset=json.loads(asset_path.read_text(encoding='utf-8-sig'))
        bones=audit_rig(asset,contract,True)['embedded_rig']
        mesh=load_reference(gltf_path)
        points=pose_points(mesh,native,rig_globals(bones))
        records[kind]=dict(vertices=len(points),triangles=len(mesh['faces']),
                           runtime_bbox_cm=[points.min(axis=0).tolist(),points.max(axis=0).tolist()],
                           max_influences=max(map(len,mesh['weights'])),finite=True)
        for p in (asset_path,gltf_path): hashes[str(p)]=sha(p)
        for buf in json.loads(gltf_path.read_text())['buffers']:
            p=(gltf_path.parent/buf['uri']).resolve()
            if not p.is_relative_to(gltf_path.parent):raise ValueError('Escaping glTF buffer')
            hashes[str(p)]=sha(p)
    return dict(base_id=profile['base_id'],native_player_id=profile['native_player_id'],
                parts=records,input_sha256=hashes)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'local-debug'):
        raise ValueError('Audit output must remain under ignored local-debug')
    players=[audit_profile(p) for p in args.profile]
    if len({p['base_id'] for p in players})!=len(players):raise ValueError('Duplicate BaseId')
    report=dict(scope='Native reference pose; not device animation, culling, texture binding or performance',
                hardware_accepted=False,players=players)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),players=len(players),hardware_accepted=False)))


if __name__=='__main__': main()

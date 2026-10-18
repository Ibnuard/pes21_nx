"""Bounded, reproducible topology/texture audit of locally owned native heads.

Exported game assets stay in an ignored directory. Native IDs select examples
of construction only; they are never identity evidence for a converted player.
"""
import argparse
from collections import Counter
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image

from realface_batch import PREFIX, command, key_of, output_hashes, valid_cache
from realface_batch_inventory import read, write
from realface_pipeline import sha
from realface_reference import load_reference


def topology(vertices, faces):
    p=np.asarray(vertices);tri=np.asarray(faces,dtype=int)
    parent=np.arange(len(p))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return int(i)
    for a,b,c in tri:
        a,b,c=root(a),root(b),root(c);parent[b]=a;parent[c]=a
    sizes=Counter(root(t[0]) for t in tri)
    return dict(triangles=len(tri),vertices=len(p),unique_positions_4dp=len(np.unique(p.round(4),axis=0)),
        connected_components=len(sizes),largest_component_triangles=max(sizes.values(),default=0),
        component_triangle_histogram=dict(sorted(Counter(sizes.values()).items())),
        bounds_cm=[p.min(axis=0).tolist(),p.max(axis=0).tolist()])


def audit(config,players,work):
    work=Path(work).resolve();root=Path(__file__).resolve().parents[1]
    if not work.is_relative_to(root/'local-debug') or work==root/'local-debug':
        raise ValueError('Native payload audit requires a separate ignored local-debug directory')
    expected=config['main_pak_sha256']
    if sha(config['main_pak'])!=expected:raise ValueError('Native main PAK differs from pinned input')
    names=set(subprocess.check_output([config['repak'],'list',config['main_pak']],text=True).splitlines())
    records=[]
    for base in sorted(set(players)):
        stems=[str(base)+suffix for suffix in ('_face','_hair','_face_tablet','_hair_parts_color_tablet')]
        wanted=sorted(n for n in names if any(n.startswith(PREFIX+s+'.') for s in stems))
        if any(PREFIX+s+'.uasset' not in names for s in stems):
            records.append(dict(native_id=base,status='unavailable_native_example'));continue
        key=key_of(dict(pak=expected,umodel=sha(config['umodel']),members=wanted))
        folder=work/str(base)
        if not valid_cache(folder,key):
            if folder.exists():raise ValueError('Changed/incomplete native export; choose a fresh audit directory')
            args=[config['repak'],'unpack',config['main_pak'],'-o',folder/'assets','-q']
            for name in wanted:args+=['-i',name]
            command(args,folder/'extract.log')
            for stem in stems:
                command([config['umodel'],'-export','-gltf','-png','-game=ue4.22',
                    '-path='+str(folder/'assets/PesMobile/Content'),'-out='+str(folder/'gltf'),stem],folder/(stem+'.log'))
            write(folder/'complete.json',dict(cache_key=key,outputs=output_hashes(folder)))
        data=folder/'gltf/Assets/character/RealFace';parts={}
        for part,texture in (('face','_face_tablet'),('hair','_hair_parts_color_tablet')):
            path=data/(str(base)+'_'+part+'.gltf');mesh=load_reference(path)
            image_path=data/(str(base)+texture+'.png');im=Image.open(image_path);rgba=np.asarray(im.convert('RGBA'))
            parts[part]=dict(topology(mesh['vertices'],mesh['faces']),texture=dict(size=list(im.size),mode=im.mode,
                opaque_fraction=float(np.mean(rgba[:,:,3]>=85)),alpha_range=[int(rgba[:,:,3].min()),int(rgba[:,:,3].max())]),
                rigid_head_vertices=sum(w=={'sk_head':1.} for w in mesh['weights']),
                gltf_sha256=sha(path),texture_sha256=sha(image_path),
                original_asset_hashes={n:sha(folder/'assets'/n) for n in wanted if n.startswith(PREFIX+str(base)+'_'+part+'.')})
        records.append(dict(native_id=base,status='audited',parts=parts,
                            complete_head_triangles=sum(p['triangles'] for p in parts.values())))
        print(dict(native_id=base,head=records[-1]['complete_head_triangles'],hair=parts['hair']['triangles'],
                   largest_hair_component=parts['hair']['largest_component_triangles']),flush=True)
    if sha(config['main_pak'])!=expected:raise ValueError('Native source changed during audit')
    write(work/'audit.json',dict(main_pak_sha256=expected,examples=records,hardware_profiled=False,
        identity_assets_reused=False,scope='selected construction examples; not all native hairstyles'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--player',action='append',type=int,required=True)
    parser.add_argument('--work-dir',required=True);args=parser.parse_args()
    audit(read(args.config),args.player,args.work_dir)

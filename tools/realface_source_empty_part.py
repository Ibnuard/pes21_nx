"""Identify authored PC point fillers using the same player's pinned FMDLs.

This is a source repair policy, distinct from assuming that an empty raster
means bald hair. An entire masked part must comprise point-size primitives
or provably transparent UV footprints. Visible meshes remain ineligible.
"""
from pathlib import Path
import math
import numpy as np

from realface_pipeline import sha


def buried_micro_source_mesh(points,skin_points,skin_faces):
    p=np.asarray(points,dtype=float);v=np.asarray(skin_points,dtype=float);t=np.asarray(skin_faces,dtype=int)
    if (not len(p) or not len(t) or not np.isfinite(p).all() or not np.isfinite(v).all() or
            np.ptp(p,axis=0).max()>.15):return None
    center=(p.min(axis=0)+p.max(axis=0))*.5;radius=float(np.linalg.norm(np.ptp(p,axis=0))*.5)
    triangles=v[t];lo=triangles.min(axis=1);hi=triangles.max(axis=1)
    lower=np.linalg.norm(np.maximum(0,np.maximum(lo-center,center-hi)),axis=1)
    clearance=float(lower.min()-radius)
    if clearance<.3:return None
    e1=triangles[:,1]-triangles[:,0];e2=triangles[:,2]-triangles[:,0]
    # Five independent rays avoid relying on the open lower-neck boundary.
    directions=((1,.017,.031),(-1,.023,.041),(.019,.029,1),(.037,.013,-1),(.011,1,.027))
    for raw in directions:
        direction=np.asarray(raw);direction=direction/np.linalg.norm(direction)
        h=np.cross(np.broadcast_to(direction,e2.shape),e2);det=(e1*h).sum(axis=1)
        live=np.abs(det)>1e-10;inv=np.zeros_like(det);inv[live]=1/det[live]
        s=center-triangles[:,0];u=(s*h).sum(axis=1)*inv;q=np.cross(s,e1)
        vv=(q*direction).sum(axis=1)*inv;distance=(e2*q).sum(axis=1)*inv
        hits=distance[live&(u>=-1e-8)&(vv>=-1e-8)&(u+vv<=1+1e-8)&(distance>1e-8)]
        if len(np.unique(np.round(hits,7)))%2!=1:return None
    return dict(source_skin_clearance_lower_bound_cm=clearance,inside_source_skin_rays=5)


def validate_source_part(proof):
    if proof.get('policy')!='same_player_authored_empty_masked_part_v1' or not proof.get('meshes'):
        raise ValueError('Complete same-player source-part proof required')
    for mesh in proof['meshes']:
        if mesh['triangles']<=0 or mesh['vertices']<=0:
            raise ValueError('Missing geometry cannot establish an empty source part')
        if mesh['classification']=='authored_point':
            span=mesh['max_extent_cm']
            if not math.isfinite(span) or not 0<=span<=1e-5:
                raise ValueError('Source primitive is not an authored point filler')
        elif mesh['classification']=='alpha_hidden':
            if mesh['alpha_hidden_triangles']!=mesh['triangles']:
                raise ValueError('Source alpha proof is incomplete')
        elif mesh['classification']=='buried_microscopic_source':
            if (not 0<=mesh['max_extent_cm']<=.15 or
                    mesh.get('source_skin_clearance_lower_bound_cm',-1)<.3 or
                    mesh.get('inside_source_skin_rays')!=5):
                raise ValueError('Small source mesh lacks a complete own-skin enclosure proof')
        else:
            raise ValueError('Visible/unclassified source mesh cannot be replaced')
    return proof


def source_part_proof(config,row):
    from realface_batch_inventory import read,write
    from export_pes_fmdl_gltf import load_fmdl
    from realface_material_policy import classify
    from realface_material_atlas import build_atlas
    from realface_invisible_slot_policy import classify_triangles
    from PIL import Image
    source_root=config.get('source_input_root')
    root=(Path(source_root) if source_root else
          Path(__file__).resolve().parents[1]/'local-inputs/realface-cache-v1/inputs-v2')/str(row['base_id'])
    manifest=root/'extraction.json'
    if not manifest.is_file():return None
    extraction=read(manifest)
    if any(extraction.get(k)!=row[k] for k in ('base_id','native_player_id','fingerprint')):
        raise ValueError('Raw PC source belongs to a different identity')
    expected={r['member']:r['sha256'] for r in extraction['files']}
    models={};inputs={str(manifest):sha(manifest)};skin_points=[];skin_faces=[]
    for part in ('face','hair'):
        path=next((root/'source').rglob(part+'_high.fmdl'))
        if sha(path)!=expected.get(path.name):raise ValueError('Pinned extracted FMDL changed')
        inputs[str(path)]=sha(path)
        model=load_fmdl(path,Path(config['fmdl_parser']))
        def role(mat):
            return classify(dict(name=mat.name,extras=dict(fmdlTechnique=mat.technique,
                fmdlTextures=[dict(role=k,filename=t.filename) for k,t in mat.textures])))['role']
        for mesh in model.meshes:
            if role(mesh.materialInstance)!='skin':continue
            lookup={id(v):i+len(skin_points) for i,v in enumerate(mesh.vertices)}
            skin_faces.extend([[lookup[id(v)] for v in f.vertices] for f in mesh.faces])
            skin_points.extend([(v.position.x*100,v.position.y*100,v.position.z*100) for v in mesh.vertices])
        model.meshes=[m for m in model.meshes if role(m.materialInstance)=='hair']
        models[part]=model
    png=next((root/'source').rglob('face_bsm_alp.png')).parent
    inputs.update({str(p):sha(p) for p in png.glob('*.png')})
    folder=Path(config['work_dir'])/'remaining-hold-audit'/str(row['base_id'])/'pc-source-proof'
    atlas,audit=build_atlas(models,png,folder/'native-source-alpha.png')
    if atlas is None:return None
    alpha=np.asarray(Image.open(atlas).convert('RGBA'))[:,:,3]/255.
    meshes=[]
    for part,model in models.items():
        for m in model.meshes:
            p=np.asarray([(v.position.x,v.position.y,v.position.z) for v in m.vertices],dtype=float)*100
            if not len(p) or not len(m.faces) or not np.isfinite(p).all():return None
            extent=float(np.ptp(p,axis=0).max())
            entry=dict(part=part,material=m.materialInstance.name,vertices=len(p),
                       triangles=len(m.faces),max_extent_cm=extent)
            if extent<=1e-5:
                entry['classification']='authored_point'
            else:
                lookup={id(v):i for i,v in enumerate(m.vertices)}
                t=np.asarray([[lookup[id(v)] for v in f.vertices] for f in m.faces])
                uv=np.asarray([[(v.uv[0].u,v.uv[0].v) for v in f.vertices] for f in m.faces])
                measured=classify_triangles(p,t,uv,alpha,[{'sk_head':1.0}]*len(p))
                if measured['alpha_hidden']==len(t):
                    entry.update(classification='alpha_hidden',alpha_hidden_triangles=len(t))
                else:
                    enclosure=buried_micro_source_mesh(p,skin_points,skin_faces)
                    if enclosure is None:return None
                    entry.update(classification='buried_microscopic_source',**enclosure)
            meshes.append(entry)
    proof=dict(policy='same_player_authored_empty_masked_part_v1',
        **{k:row[k] for k in ('base_id','native_player_id','fingerprint')},
        meshes=meshes,inputs=inputs,atlas_policy=audit,source_skin_changed=False,
        native_weighted_filler_repaired=True)
    validate_source_part(proof);write(folder/'proof.json',proof)
    return proof

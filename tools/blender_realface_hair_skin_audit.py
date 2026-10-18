"""Compare actual visible hair against skin, including lower fringe intrusion."""
import json
from pathlib import Path
import shutil
import sys

import bpy
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import rig_globals
from blender_realface_mobile import geometry,pixels
from realface_fast_raster import load


def data(path,copy,native,cooked):
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=.01
    shutil.copy2(path,copy);bpy.ops.import_scene.fbx(filepath=str(copy),use_anim=False)
    points=[];tri=[];uv=[]
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH':continue
        p,t,u=geometry(obj,native,cooked);tri.extend(t+len(points));points.extend(p);uv.extend(u)
    return np.asarray(points),np.asarray(tri),np.asarray(uv)


def audit(row,config,work):
    folder=Path(row['folder']);job=json.loads((folder/'job.json').read_text(encoding='utf-8'))
    ue=json.loads((folder/'ue-profile.json').read_text(encoding='utf-8'))
    native,cooked=(rig_globals(json.loads(Path(config[n]).read_text())) for n in ('native_rig','cooked_rig'))
    before=data(job['source_profile']['hair_fbx'],work/'source.fbx',native,cooked)
    alpha=pixels(job['source_profile']['hair_texture'])[:,:,3].copy()
    after=data(ue['hair_fbx'],work/'after.fbx',native,cooked)
    beta=pixels(ue['hair_texture'])[:,:,3].copy()
    request=json.loads((folder/'lite_skin-meshopt.json').read_text())
    indices=json.loads((folder/'lite_skin-meshopt-result.json').read_text())['indices']
    skin=np.asarray(request['positions']).reshape(-1,3);skin_tri=np.asarray(indices).reshape(-1,3)
    raster=load(config['fast_raster']);bounds=((-12,152),(12,194));size=192
    z=152+(np.arange(size)+.5)/size*42
    forehead=(z[:,None]>172)&(z[:,None]<179)
    views=[]
    for yaw in (0,-25,25):
        a=np.radians(yaw);basis=np.asarray([[np.cos(a),-np.sin(a),0],[0,0,1],[np.sin(a),np.cos(a),0]])
        body=raster(skin,skin_tri,np.zeros((len(skin_tri),3,2)),np.ones((1,1)),basis,bounds,size)
        b=raster(*before,alpha,basis,bounds,size,skin_depth=body['depth'])
        c=raster(*after,beta,basis,bounds,size,skin_depth=body['depth'])
        # One-pixel expansion tolerates different triangle coverage at edges.
        pad=np.pad(b['mask'],1)
        expanded=np.logical_or.reduce([pad[y:y+size,x:x+size] for y in range(3) for x in range(3)])
        missing=np.count_nonzero(b['mask']&~c['mask'])/max(np.count_nonzero(b['mask']),1)
        spill=np.count_nonzero(c['mask']&~expanded&body['mask']&forehead)
        views.append(dict(yaw=yaw,visible_missing_fraction=float(missing),new_forehead_pixels=int(spill),
            original_hair_pixels=int(b['mask'].sum()),candidate_hair_pixels=int(c['mask'].sum())))
    return dict(base_id=row['base_id'],name=row['name'],views=views,
        visible_missing_max=max(v['visible_missing_fraction'] for v in views),
        new_forehead_pixels_max=max(v['new_forehead_pixels'] for v in views),
        solid_scalp=row['budgets'].get('solid_scalp'),mode=row['budgets'].get('hair_mode'))


def run(manifest):
    work=Path(manifest['work']);work.mkdir(parents=True,exist_ok=True);rows=[]
    for row in manifest['players']:
        try:result=audit(row,manifest['config'],work)
        except Exception as error:result=dict(base_id=row['base_id'],name=row['name'],error=str(error))
        rows.append(result);Path(manifest['output']).write_text(json.dumps(rows,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)


if __name__=='__main__':run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8')))

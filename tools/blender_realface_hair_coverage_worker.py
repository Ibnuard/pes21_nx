"""Check scalp exposure using separate source and reduced face depth buffers."""
import json
from pathlib import Path
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from blender_export_ue_fbx import rig_globals
from blender_realface_hair_clearance import import_mesh,merged_data
from blender_realface_mobile import pixels
from blender_realface_league_worker import PREFIX
from realface_fast_raster import load
from realface_hair_coverage import compare_visibility


def audit(request):
    folder=Path(request['folder']);folder.mkdir(parents=True,exist_ok=True)
    old=Path(request['row']['folder'])
    job=json.loads((old/'job.json').read_text(encoding='utf-8'))
    prepared=json.loads((old/'ue-profile.json').read_text(encoding='utf-8'))
    native,cooked=(rig_globals(json.loads(Path(job[k]).read_text())) for k in ('native_rig','cooked_rig'))
    raster=load(job['fast_raster'])
    source=merged_data(import_mesh(job['source_profile']['hair_fbx'],folder/'source.fbx'),native,cooked)
    after=merged_data(import_mesh(prepared['hair_fbx'],folder/'prepared.fbx'),native,cooked)
    alpha=pixels(job['source_profile']['hair_texture'])[:,:,3].copy()
    beta=pixels(prepared['hair_texture'])[:,:,3].copy()
    skin=json.loads((old/'lite_skin-meshopt.json').read_text())
    p=np.asarray(skin['positions']).reshape(-1,3)
    original_skin=np.asarray(skin['indices']).reshape(-1,3)
    reduced_skin=np.asarray(json.loads((old/'lite_skin-meshopt-result.json').read_text())['indices']).reshape(-1,3)
    bounds=((-13,162),(13,194));size=160;records=[]
    for yaw in (0,-45,45,-90,90,-135,135,180):
        a=np.radians(yaw)
        basis=np.asarray([[np.cos(a),-np.sin(a),0],[0,0,1],[np.sin(a),np.cos(a),0]])
        depths=[]
        for triangles in (original_skin,reduced_skin):
            depths.append(raster(p,triangles,np.zeros((len(triangles),3,2)),np.ones((1,1)),basis,bounds,size))
        visible=[]
        for data,texture,depth in zip((source,after),(alpha,beta),depths):
            frame=raster(*data,texture,basis,bounds,size,skin_depth=depth['depth'])
            # The audit concerns scalp hair. Beard detail has a separate review.
            z=bounds[0][1]+(np.arange(size)+.5)/size*(bounds[1][1]-bounds[0][1])
            visible.append(frame['mask'] & (z[:,None]>=169))
        records.append(dict(yaw=yaw,**compare_visibility(*visible,depths[1]['mask'])))
    result=dict(base_id=request['row']['base_id'],cache_key=request['row']['cache_key'],
        diagnostic_only=True,visual_approval=False,separate_original_and_reduced_skin=True,
        views=records,interior_bald_ratio_max=max(r['interior_bald_ratio'] for r in records),
        interior_bald_pixels_max=max(r['interior_bald_pixels'] for r in records),
        visible_missing_ratio_max=max(r['visible_missing_ratio'] for r in records))
    (folder/'coverage.json').write_text(json.dumps(result,indent=2))
    # Only local inspection copies, never the source or immutable prepared FBX.
    for name in ('source.fbx','prepared.fbx'):(folder/name).unlink()


for line in sys.stdin:
    message=json.loads(line);result=dict(token=message['token'],ok=False)
    try:
        audit(json.loads(Path(message['profile']).read_text(encoding='utf-8')));result['ok']=True
    except Exception as error:
        traceback.print_exc();result['reason']=str(error)
    print(PREFIX+json.dumps(result),flush=True)

"""Persistent Blender worker for strict mobile league heads (local inputs only)."""
import json
from pathlib import Path
import shutil
import sys
import traceback

PREFIX = 'PESNX_LEAGUE_RESULT '
FACE_PARTS = {}


def remaining_hair_budget(budgets, face_triangles):
    """Use the actual retained face/eyes, never the requested triangle count."""
    remaining=min(2000,budgets.get('head_cap',2000))-face_triangles
    if remaining < 1:
        raise ValueError('Face exceeds complete head cap before hair')
    return dict(budgets,hair=min(budgets['hair'],remaining))


def prepare(job):
    if job.get('fast_raster'):
        from realface_fast_raster import load
        import realface_mobile_geometry
        import realface_surface_quality
        fast=load(job['fast_raster'])
        realface_mobile_geometry.raster=fast
        realface_surface_quality.raster=fast
    from blender_export_ue_fbx import rig_globals
    from blender_realface_lite import reduce_part
    from realface_surface_quality import audit, needs_refinement
    folder = Path(job['folder'])
    if job['budgets'].get('hair_mode') == 'braids':
        from blender_realface_braids import run
        run(job)
        proof = json.loads((folder/'simplification.json').read_text())
    else:
        native,cooked=(rig_globals(json.loads(Path(job[name]).read_text())) for name in ('native_rig','cooked_rig'))
        face_key=json.dumps(dict(owner=job['base_id'],profile=job['source_profile'],code=job['recipe_source_sha256'],
            budgets={k:v for k,v in job['budgets'].items() if k not in ('hair','hair_mode','solid_scalp')}),sort_keys=True)
        if face_key in FACE_PARTS:
            face,files=FACE_PARTS[face_key]
            for file in files: shutil.copy2(file,folder/file.name)
        else:
            face=reduce_part(job,'face',native,cooked)
            audit_face(folder,face,audit,needs_refinement)
            files=[p for p in folder.iterdir() if p.is_file() and p.suffix in ('.json','.png','.fbx') and
                   p.name not in ('job.json','input-face.fbx','held.json')]
            FACE_PARTS[face_key]=(face,files)
        hair_budget=remaining_hair_budget(job['budgets'],face['total'])
        hair=reduce_part(dict(job,budgets=hair_budget),'hair',native,cooked)
        total=face['total']+hair['total']
        if not 0<total<=2000: raise ValueError('Strict complete head cap exceeded: '+str(total))
        proof=dict(face=face,hair=hair,total_triangles=total,base_id=job['base_id'],
                   native_player_id=job['native_player_id'],hardware_accepted=False,
                   effective_hair_budget=hair_budget['hair'])
        (folder/'simplification.json').write_text(json.dumps(proof,indent=2)+'\n')
    audit_face(folder,proof['face'],audit,needs_refinement)


def audit_face(folder,face,audit,needs_refinement):
    if (folder/'surface-projection.json').exists(): return
    request=folder/'lite_skin-meshopt.json'
    if request.exists():
        projection=audit(json.loads(request.read_text()),
            json.loads((folder/'lite_skin-meshopt-result.json').read_text())['indices'])
        if needs_refinement(projection):
            raise ValueError('Visible face UV distortion held: '+json.dumps(projection))
    else:
        proof=face['roles']['skin']
        if proof['before']!=proof['after']: raise ValueError('Reduced skin has no projection audit input')
        projection=dict(mouth_uv_p95_max=0.,face_uv_p95_max=0.,unchanged_skin=True)
    (folder/'surface-projection.json').write_text(json.dumps(projection,indent=2)+'\n')


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    for line in sys.stdin:
        request = json.loads(line)
        result = dict(token=request['token'], ok=False)
        try:
            prepare(json.loads(Path(request['profile']).read_text(encoding='utf-8')))
            result['ok'] = True
        except Exception as error:
            traceback.print_exc()
            result['reason'] = str(error)
        print(PREFIX+json.dumps(result), flush=True)


if __name__ == '__main__':
    main()

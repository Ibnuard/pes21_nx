"""Explicit isolated head-budget trials; legacy recipes are unchanged."""
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mathutils import Vector
import blender_meshopt as meshopt
import blender_realface_eye_visibility as visibility
import blender_realface_league_worker as league
from blender_realface_lite import count
from realface_seam_alias import canonical_positions


def experimental_prepare(job):
    cap = job['budgets']['head_cap']
    if not job.get('experimental_only') or cap not in (3000,4500,5000,6000,7000):
        raise ValueError('Budget worker requires an explicit isolated experiment')
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
    folder=Path(job['folder'])
    native,cooked=(rig_globals(json.loads(Path(job[name]).read_text()))
                   for name in ('native_rig','cooked_rig'))
    face=reduce_part(job,'face',native,cooked)
    league.audit_face(folder,face,audit,needs_refinement)
    remaining=cap-face['total']
    if remaining<1:
        raise ValueError('Face exceeds experimental head cap before hair')
    hair_budget=dict(job['budgets'],hair=min(job['budgets']['hair'],remaining))
    hair=reduce_part(dict(job,budgets=hair_budget),'hair',native,cooked)
    total=face['total']+hair['total']
    if not 0<total<=cap:
        raise ValueError('Experimental complete head cap exceeded: '+str(total))
    proof=dict(face=face,hair=hair,total_triangles=total,base_id=job['base_id'],
               native_player_id=job['native_player_id'],hardware_accepted=False,
               effective_hair_budget=hair_budget['hair'],experimental_head_cap=cap)
    (folder/'simplification.json').write_text(json.dumps(proof,indent=2)+'\n')


def keep_globe(obj,skin,tri,native,cooked,budget,occluders=()):
    return dict(policy='whole_original_globe_for_bounded_reduction',source_triangles=count(obj),
                occluded_triangles_removed=0,visibility_trim_applied=False,reduction_target=budget)


original_reduce,original_trim,original_prepare=meshopt.reduce,visibility.trim,league.prepare


def reduce(obj,positions,target,role,job):
    if role=='skin':
        weights=[tuple(sorted((g.group,round(g.weight,7)) for g in vertex.groups))
                 for vertex in obj.data.vertices]
        positions,proof=canonical_positions(positions,weights)
        positions=[Vector(p) for p in positions]
        (Path(job['folder'])/'native-seam-alias.json').write_text(json.dumps(proof,indent=2))
    return original_reduce(obj,positions,target,role,job)


for line in sys.stdin:
    request=json.loads(line);result=dict(token=request['token'],ok=False)
    try:
        job=json.loads(Path(request['profile']).read_text(encoding='utf-8'))
        if not (job.get('experimental_only') and job['budgets'].get('native_seam_alias')
                and job['budgets'].get('source_eye_policy')=='original_lod'):
            raise ValueError('Explicit experimental seam and original-eye policy required')
        meshopt.reduce=reduce
        visibility.trim=keep_globe
        league.prepare=experimental_prepare
        from blender_realface_source_quality import prepare
        prepare(job);result['ok']=True
    except Exception as error:
        traceback.print_exc();result['reason']=str(error)
    finally:
        meshopt.reduce,visibility.trim,league.prepare=original_reduce,original_trim,original_prepare
    print(league.PREFIX+json.dumps(result),flush=True)

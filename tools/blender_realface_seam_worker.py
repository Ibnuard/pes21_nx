"""Keep near-coincident native skin seams together during index reduction."""
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent))
from mathutils import Vector
import blender_meshopt as meshopt
import blender_realface_eye_visibility as visibility
import blender_realface_eye_cleanup as eyes
from blender_realface_league_worker import PREFIX
from blender_realface_lite import count
from realface_seam_alias import canonical_positions


def keep_globe(obj,skin,tri,native,cooked,budget,occluders=()):
    return dict(policy='whole_original_globe_for_bounded_reduction',source_triangles=count(obj),
                occluded_triangles_removed=0,visibility_trim_applied=False,reduction_target=budget)


original_reduce,original_trim,original_cap=meshopt.reduce,visibility.trim,eyes.aperture_cap


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
        if not job['budgets'].get('native_seam_alias'):
            raise ValueError('Seam worker requires the explicit source-seam policy')
        meshopt.reduce=reduce
        if job['budgets'].get('source_eye_policy') in ('original_lod','scalp_original_lod'):
            visibility.trim=keep_globe
        if job['budgets'].get('eye_recovery'):
            from blender_realface_eye_recovery import aperture_cap
            eyes.aperture_cap=aperture_cap
        if job['budgets'].get('source_eye') or job['budgets'].get('face_detail'):
            from blender_realface_source_quality import prepare
        else:
            from blender_realface_normal_export import prepare
        prepare(job);result['ok']=True
    except Exception as error:
        traceback.print_exc();result['reason']=str(error)
    finally:
        meshopt.reduce,visibility.trim,eyes.aperture_cap=original_reduce,original_trim,original_cap
    print(PREFIX+json.dumps(result),flush=True)

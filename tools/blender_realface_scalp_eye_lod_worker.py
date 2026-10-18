"""Reclaim eye triangles for facial detail on verified skin-only scalp sources."""
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_realface_league_worker import PREFIX
from blender_realface_source_quality import prepare
from blender_realface_lite import count
import blender_realface_eye_visibility as visibility


def keep_globe(obj,skin,skin_tri,native,cooked,budget,occluders=()):
    return dict(policy='whole_original_globe_for_bounded_reduction',source_triangles=count(obj),
                occluded_triangles_removed=0,visibility_trim_applied=False,reduction_target=budget)


original=visibility.trim
for line in sys.stdin:
    request=json.loads(line);result=dict(token=request['token'],ok=False)
    try:
        job=json.loads(Path(request['profile']).read_text(encoding='utf-8'))
        if (job['budgets'].get('source_eye_policy')!='scalp_original_lod' or
            job['source_profile'].get('empty_hair_slot',{}).get('policy')!='all_source_skin_transferred_to_face'):
            raise ValueError('Scalp eye-LOD requires verified transferred skin and its explicit policy')
        visibility.trim=keep_globe
        prepare(job);result['ok']=True
    except Exception as error:
        traceback.print_exc();result['reason']=str(error)
    finally:visibility.trim=original
    print(PREFIX+json.dumps(result),flush=True)

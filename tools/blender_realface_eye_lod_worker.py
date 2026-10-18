"""Reduce the original eye globe in place instead of constructing an aperture cap.

Only the visibility-trim stage is bypassed. The normal reducer still checks
the complete source globe against the unchanged eye surface-distance limits.
The complete head/UV/native rig gates also remain in place.
"""
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_realface_league_worker import PREFIX
from blender_realface_source_quality import prepare
import blender_realface_eye_visibility as visibility
from blender_realface_lite import count

def keep_globe(obj,skin,skin_tri,native,cooked,budget,occluders=()):
    return dict(policy='whole_original_globe_for_bounded_reduction',source_triangles=count(obj),
                occluded_triangles_removed=0,visibility_trim_applied=False,reduction_target=budget)

original=visibility.trim
for line in sys.stdin:
    request=json.loads(line);result=dict(token=request['token'],ok=False)
    try:
        job=json.loads(Path(request['profile']).read_text(encoding='utf-8'))
        if job['budgets'].get('source_eye_policy')!='original_lod':
            raise ValueError('Whole-globe worker requires its explicit source-eye policy')
        visibility.trim=keep_globe
        prepare(job);result['ok']=True
    except Exception as error:
        traceback.print_exc();result['reason']=str(error)
    finally:visibility.trim=original
    print(PREFIX+json.dumps(result),flush=True)

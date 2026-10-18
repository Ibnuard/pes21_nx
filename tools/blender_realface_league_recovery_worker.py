"""Scoped exceptional-input worker; leaves the normal league recipe unchanged."""
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_realface_league_worker import prepare, PREFIX
import blender_realface_eye_cleanup as eyes
from blender_realface_eye_recovery import aperture_cap

original=eyes.aperture_cap
for line in sys.stdin:
    request=json.loads(line);result=dict(token=request['token'],ok=False)
    try:
        job=json.loads(Path(request['profile']).read_text(encoding='utf-8'))
        eyes.aperture_cap=aperture_cap if job['budgets'].get('eye_recovery') else original
        if job['budgets'].get('normal_export_recovery'):
            from blender_realface_normal_export import prepare as export_safe_prepare
            export_safe_prepare(job)
        else:prepare(job)
        result['ok']=True
    except Exception as error:
        traceback.print_exc();result['reason']=str(error)
    finally:eyes.aperture_cap=original
    print(PREFIX+json.dumps(result),flush=True)

"""Scoped persistent worker for the undefined-normal export repair."""
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_realface_league_worker import PREFIX
from blender_realface_normal_export import prepare

for line in sys.stdin:
    request=json.loads(line);result=dict(token=request['token'],ok=False)
    try:
        job=json.loads(Path(request['profile']).read_text(encoding='utf-8'))
        if not job['budgets'].get('normal_export_recovery'):raise ValueError('Explicit normal recovery policy required')
        prepare(job);result['ok']=True
    except Exception as error:
        traceback.print_exc();result['reason']=str(error)
    print(PREFIX+json.dumps(result),flush=True)

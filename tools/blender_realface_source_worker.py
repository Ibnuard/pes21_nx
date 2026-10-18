"""Explicit source-eye/detail recovery worker; every result still needs visual review."""
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_realface_league_worker import PREFIX
from blender_realface_source_quality import prepare

for line in sys.stdin:
    request=json.loads(line);result=dict(token=request['token'],ok=False)
    try:
        job=json.loads(Path(request['profile']).read_text(encoding='utf-8'))
        if not job['budgets'].get('source_eye'):raise ValueError('Source-detail worker requires explicit source-eye policy')
        prepare(job);result['ok']=True
    except Exception as error:
        traceback.print_exc();result['reason']=str(error)
    print(PREFIX+json.dumps(result),flush=True)

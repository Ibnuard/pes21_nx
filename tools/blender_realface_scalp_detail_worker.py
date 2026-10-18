"""Spend the complete head budget on skin when the source hair is baked into it."""
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
        policy=job['source_profile'].get('empty_hair_slot',{}).get('policy')
        if policy!='all_source_skin_transferred_to_face':
            raise ValueError('Scalp-detail allocation requires verified transferred source skin')
        prepare(job);result['ok']=True
    except Exception as error:
        traceback.print_exc();result['reason']=str(error)
    print(PREFIX+json.dumps(result),flush=True)

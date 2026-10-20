"""Render the unchanged offline preview recipe in a bounded persistent worker."""
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_preview_realface import render
from realface_pipeline import sha
from realface_preview_process import PREFIX

for line in sys.stdin:
    request=json.loads(line);receipt=dict(token=request['token'],ok=False)
    try:
        if sha(Path(__file__).with_name('blender_preview_realface.py'))!=request['renderer_sha256']:
            raise ValueError('Preview renderer source differs')
        targets=json.loads(Path(request['targets']).read_text(encoding='utf-8'))
        if not isinstance(targets,list) or not 1<=len(targets)<=48:
            raise ValueError('Preview requests must contain 1 to 48 views')
        for target in targets:
            render(target['recipe'],target['output'])
        receipt['ok']=True
    except Exception as error:
        traceback.print_exc();receipt['reason']=str(error)
    print(PREFIX+json.dumps(receipt),flush=True)

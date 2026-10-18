"""Recheck retained cook outputs after a validator fix, without rerunning UE."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
import threading

from realface_batch import key_of
from realface_batch_inventory import read,write
from realface_batch_release import verify_one
from realface_pipeline import sha
from realface_validation_process import ValidationProcess


def run(config,workers=2):
    work=Path(config['work_dir']);path=work/'verify-report.json'
    saved={r['base_id']:r for r in read(path)};pending=[]
    script=Path(__file__).with_name('validate_realface_cooked.py')
    for row in saved.values():
        if row['status']!='held_cook_validation':continue
        key=key_of(dict(original_cook_key=row['cooked_cache_key'],validator=sha(script)))
        folder=Path(config['cache_dir'])/'cooked'/(str(row['base_id'])+'-'+key[:16])
        pending.append(dict(row,status='cooked_pending_verification',original_cook_key=row['cooked_cache_key'],
                            cooked_cache_key=key,cooked_folder=str(folder)))
    local=threading.local();processes=[]
    def one(row):
        if not hasattr(local,'validator'):
            local.validator=ValidationProcess(config['blender']);processes.append(local.validator)
        return verify_one(dict(config,work_dir=str(work/'revalidated')),row,local.validator)
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for i,future in enumerate(as_completed([pool.submit(one,r) for r in pending]),1):
                row=future.result()
                if row['status'] in ('validated', 'validated_cached'):
                    row.pop('reason', None)
                saved[row['base_id']]=row
                write(path,sorted(saved.values(),key=lambda r:r['base_id']))
                print(json.dumps(dict(done=i,total=len(pending),base_id=row['base_id'],status=row['status'],reason=row.get('reason'))),flush=True)
    finally:
        for process in processes:process.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True)
    parser.add_argument('--workers',type=int,default=2,choices=range(1,5));args=parser.parse_args()
    run(read(args.config),args.workers)

"""Cook completed league heads in bounded batches while preparation continues."""
import argparse
import json
from pathlib import Path
import time

from realface_batch import key_of
from realface_batch_inventory import read, write
from realface_batch_release import verify
from realface_league_cook import cook
from realface_league_mobile import recipe_code


def preparation_finished(work):
    complete=work/'prepare-complete.json';running=work/'prepare-running.json'
    if not complete.exists():return False
    if not running.exists():return True  # Legacy explicit completion marker.
    try:return read(complete).get('run_id')==read(running).get('run_id')
    except (OSError,json.JSONDecodeError):return False


def queue(config,follow=False):
    work=Path(config['work_dir']);target=work/'verify-report.json'
    saved={r['base_id']:r for r in read(target)} if target.exists() else {}
    while True:
        try: prepared=read(work/'prepare-report.json')
        except (OSError,json.JSONDecodeError):
            if not follow:raise
            time.sleep(2);continue
        ready=[r for r in prepared if r['status'] in ('prepared','prepared_cached') and
               (r.get('reuse_cooked') or r.get('recipe_source_sha256')==recipe_code(r['budgets']))]
        ready.sort(key=lambda r:r['base_id'])
        pending=[r for r in ready if saved.get(r['base_id'],{}).get('cache_key')!=r['cache_key']]
        finished=preparation_finished(work)
        if not pending or (follow and not finished and len(pending)<64):
            if not follow or finished:break
            time.sleep(10);continue
        selected=pending[:256]
        key=key_of([r['cache_key'] for r in selected])
        batch=work/'cook-queue'/key[:16]
        local=dict(config,work_dir=str(batch))
        write(batch/'prepare-report.json',selected)
        print(json.dumps(dict(queue_batch=len(selected),verified=len(saved),key=key[:16])),flush=True)
        cook(local)
        verify(local,workers=2)
        for row in read(batch/'verify-report.json'):saved[row['base_id']]=row
        # The latest prepare key wins; never mix a superseded mesh into release.
        latest={r['base_id']:r for r in read(work/'prepare-report.json')}
        saved={base:r for base,r in saved.items() if latest.get(base,{}).get('cache_key')==r['cache_key']}
        write(target,sorted(saved.values(),key=lambda r:r['base_id']))
        print(json.dumps(dict(queue_verified=sum(r['status'] in ('validated','validated_cached') for r in saved.values()),
            held=[dict(base_id=r['base_id'],reason=r.get('reason')) for r in saved.values() if r['status'].startswith('held')])),flush=True)
    return saved


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--follow',action='store_true')
    args=parser.parse_args();queue(read(args.config),args.follow)

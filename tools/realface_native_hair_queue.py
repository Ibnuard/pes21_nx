"""Independently cook/verify native-style league candidates in bounded chunks."""
import argparse
from pathlib import Path
import time

from realface_batch import key_of
from realface_batch_inventory import read, write
from realface_native_hair_validate import validate
from realface_native_hair_trial import HERE


def pending(rows, verified):
    return [row for row in rows if row.get('status') == 'candidate_visual_hold' and
            verified.get(row['base_id'], {}).get('cache_key') != row['cache_key']]


def batch_paths(work, keys):
    # UModel uses legacy Windows file opening for dependencies. A deeply
    # nested league/cook/verification path put shared assets beyond 260 chars,
    # yielding dummy_material_0 despite those assets being present and correct.
    key = key_of(dict(league_work=str(Path(work).resolve()), prepared=keys))
    base = HERE.parent / 'local-debug' / 'nh39c' / key[:16]
    return base / 'trial', base / 'v'


def queue(config, work, follow=False, chunk=64, workers=1):
    work = Path(work).resolve()
    saved = {r['base_id']: r for r in read(work / 'verify-report.json')} if (work / 'verify-report.json').exists() else {}
    while True:
        if not (work / 'trial-report.json').exists():
            if not follow: raise ValueError('No league trial report')
            time.sleep(5); continue
        rows = read(work / 'trial-report.json')
        faces = read(work / 'chosen-faces.json')
        expected = sum(not r.get('reuse_cooked') and r.get('status') in ('prepared', 'prepared_cached') for r in faces)
        latest = {r['base_id']: r for r in rows}
        saved = {base: r for base, r in saved.items() if latest.get(base, {}).get('cache_key') == r['cache_key']}
        waiting = pending(rows, saved); finished = len(rows) == expected
        if not waiting or (follow and not finished and len(waiting) < chunk):
            if not follow or finished: break
            time.sleep(10); continue
        selected = sorted(waiting, key=lambda r: r['base_id'])[:chunk]
        trial, batch = batch_paths(work, [r['cache_key'] for r in selected])
        write(trial / 'trial-report.json', selected)
        validate(config, [trial], batch, workers)
        for row in read(batch / 'verify-report.json'): saved[row['base_id']] = row
        write(work / 'verify-report.json', sorted(saved.values(), key=lambda r: r['base_id']))
        print(dict(verified=sum(r['status'].startswith('validated') for r in saved.values()),
                   held=sum(r['status'].startswith('held') for r in saved.values()), attempted=len(rows), target=expected), flush=True)
    write(work / 'verify-report.json', sorted(saved.values(), key=lambda r: r['base_id']))
    return saved


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True); p.add_argument('--work-dir', required=True)
    p.add_argument('--follow', action='store_true'); p.add_argument('--chunk', type=int, choices=(32, 64, 128), default=64)
    p.add_argument('--workers', type=int, choices=(1, 2), default=1)
    a = p.parse_args(); queue(read(a.config), a.work_dir, a.follow, a.chunk, a.workers)

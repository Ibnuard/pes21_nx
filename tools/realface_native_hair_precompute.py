"""Warm recovery caches with one worker while the primary league run proceeds.

Only completed primary holds are considered. This never edits primary reports
or chooses the final package contents. The finisher waits for the current job
to end before combining the recovery pass, whose normal validators still run.
"""
import argparse
import json
import os
from pathlib import Path
import time

from realface_batch_inventory import read, write
from realface_league_progress import indexed
from realface_native_hair_leagues import convert
from realface_native_hair_recover import clean_source, eligible, recover_shape
from realface_native_hair_trial import HERE


def next_job(rows, faces, completed):
    candidates = [r for r in rows if r['base_id'] in faces and not faces[r['base_id']].get('reuse_cooked') and
                  (eligible(r, faces[r['base_id']]) or r.get('status') == 'held_composite_geometry') and
                  completed.get(r['base_id'], {}).get('original_key') != r.get('cache_key')]
    return min(candidates, key=lambda r: (not eligible(r, faces[r['base_id']]), r['base_id'])) if candidates else None


def run(config, primary):
    primary = Path(primary).resolve()
    if not primary.is_relative_to(HERE.parent / 'local-debug') or primary == HERE.parent / 'local-debug':
        raise ValueError('Recovery precomputation requires a dedicated ignored league directory')
    work = primary / 'binding-recovery'; work.mkdir(parents=True, exist_ok=True)
    faces = indexed(read(primary / 'chosen-faces.json'), 'faces')
    owners = indexed(read(config['source_profiles']), 'sources')
    expected = sum(not r.get('reuse_cooked') and r.get('status') in ('prepared', 'prepared_cached') for r in faces.values())
    records = {}; state = primary / 'PRECOMPUTE-STATUS.json'
    if (primary / 'PRECOMPUTE-REPORT.json').exists():
        records = indexed(read(primary / 'PRECOMPUTE-REPORT.json'), 'precomputed holds')
    def status(phase, **details):
        write(state, dict(phase=phase, pid=os.getpid(), completed=len(records),
              recovered=sum(r.get('status') == 'candidate_visual_hold' for r in records.values()),
              approved=False, **details))
    try:
        while True:
            rows = read(primary / 'trial-report.json')
            if len(rows) >= expected: break
            row = next_job(rows, faces, records)
            if not row:
                status('running', waiting_for_primary=True); time.sleep(10); continue
            base = row['base_id']; face = faces[base]
            status('running', active_base_id=base)
            if eligible(row, face):
                owner, reason = clean_source(config, owners[base], face, work / 'clean-sources')
                if owner:
                    source = work / 'early-sources' / (str(base) + '.json'); write(source, [owner])
                    cfg = dict(config, source_profiles=str(source))
                    result = convert(cfg, primary / 'chosen-faces.json', base, work)
                else:
                    result = dict(base_id=base, status='held_source_cleanup', reason=reason)
            else:
                result = recover_shape(config, primary / 'chosen-faces.json', base, face, work)
            records[base] = dict(result, original_key=row['cache_key'])
            write(primary / 'PRECOMPUTE-REPORT.json', sorted(records.values(), key=lambda r: r['base_id']))
            print(json.dumps(dict(base_id=base, status=result['status'], completed=len(records))), flush=True)
        status('complete')
    except Exception as error:
        status('failed', reason=str(error)); raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True); p.add_argument('--work-dir', required=True)
    a = p.parse_args(); run(read(a.config), a.work_dir)

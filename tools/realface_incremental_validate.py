"""Cook screened recovery heads with immutable identity and geometry evidence.

Reports are explicit snapshots: rejected/unscreened heads cannot enter the
batch. A successful cook still needs appearance and device review.
"""
import argparse
from pathlib import Path

from realface_batch import valid_prepared_cache
from realface_batch_inventory import read, write
from realface_batch_release import cook, verify
from realface_joined_recovery import CODE, HERE
from realface_league_progress import owner_matches
from realface_mobile import cooked_counts
from realface_native_hair_screen_gate import require_screened
from realface_pipeline import sha


def candidates(config, reports, reviews, baseline_path):
    baseline = read(baseline_path)
    existing = {r['base_id'] for r in baseline['players_in_package']}
    occupied = {r['native_player_id'] for r in baseline['players_in_package']}
    owners = {r['base_id']: r for r in read(config['identity_state'])['identities'].values()
              if r.get('status') == 'active'}
    code = {name: sha(HERE / name) for name in CODE}
    selected = {}
    for report in reports:
        for row in read(report):
            base = row['base_id']
            if base in selected or base in existing or row['native_player_id'] in occupied:
                raise ValueError('Duplicate or inherited recovery head')
            if not owner_matches(row, owners.get(base, {})):
                raise ValueError('Recovery identity changed')
            if (row.get('status') != 'candidate_visual_hold' or
                    row.get('composite_geometry_pass') is not True or
                    row.get('recipe_source_sha256') != code):
                raise ValueError('Recovery geometry/provenance has not passed')
            if not valid_prepared_cache(Path(row['folder']), row['cache_key']):
                raise ValueError('Recovery prepared bytes changed')
            selected[base] = row
            occupied.add(row['native_player_id'])
    rows = sorted(selected.values(), key=lambda r: r['base_id'])
    proof = require_screened(rows, reviews)
    return [dict(r, status='prepared', candidate_status=r['status']) for r in rows], proof


def validate(config, reports, reviews, baseline_path, work, workers=1):
    work = Path(work).resolve()
    if not work.is_relative_to(HERE.parent / 'local-debug') or work == HERE.parent / 'local-debug':
        raise ValueError('Validation requires a dedicated ignored folder')
    rows, proof = candidates(config, reports, reviews, baseline_path)
    if not rows:
        raise ValueError('No screened recovery heads')
    work.mkdir(parents=True, exist_ok=True)
    cfg = dict(config, work_dir=str(work), import_chunk_size=4)
    write(work / 'config.local.json', cfg)
    write(work / 'prepare-report.json', rows)
    write(work / 'SCREEN-PROOF.json', proof)
    write(work / 'QUALITY-HOLD.json', dict(approved=False, reason='Appearance/device review pending'))
    cook(cfg)
    verify(cfg, workers)
    summary = []
    for row in read(work / 'verify-report.json'):
        counts = cooked_counts(read(Path(row['cooked_folder']) / 'verification.json')) \
            if row['status'].startswith('validated') else {}
        summary.append(dict(base_id=row['base_id'], name=row['name'], status=row['status'],
                            reason=row.get('reason'), **counts, visual_approved=False, hardware_profiled=False))
    write(work / 'validation-summary.json', summary)
    print(dict(selected=len(rows), validated=sum(r['status'].startswith('validated') for r in summary)), flush=True)
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--report', action='append', required=True)
    p.add_argument('--reviews', required=True, help='JSON list of report/screen_dir specifications')
    p.add_argument('--baseline', required=True)
    p.add_argument('--work-dir', required=True)
    p.add_argument('--workers', type=int, choices=(1, 2), default=1)
    a = p.parse_args()
    validate(read(a.config), a.report, read(a.reviews), a.baseline, a.work_dir, a.workers)

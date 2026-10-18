"""Retry held league heads using their best measured attempt, not another full sweep."""
import argparse
import json
from pathlib import Path
import shutil

from realface_batch_inventory import read, write
from realface_league_progress import indexed, owner_matches
import realface_league_mobile as mobile
from realface_league_recovery import allocations as recovery_allocations
from realface_league_eye_lod import allocations as eye_allocations


def candidates(row):
    previous = recovery_allocations()
    scored = []
    reasons = [a.get('reason', '') for a in row.get('attempts', [])]
    for attempt in row.get('attempts', []):
        reason = attempt.get('reason', '')
        if not reason.startswith('Hair silhouette held: '):
            continue
        proof = json.loads(reason.split(': ', 1)[1])
        score = min(proof['silhouette_iou_min']/.80, proof['silhouette_iou_mean']/.85,
                    (1-proof['missing_coverage_max'])/.85)
        level = attempt['level']
        if not 0 <= level < len(previous):
            raise ValueError('Held allocation index is outside the known recovery policy')
        scored.append((score, level))
    rows = []
    if scored:
        # A prior attempt that reached this gate already passed face/eye checks.
        # Try a seam-safe version and bounded reallocations around two leaders.
        for _, level in sorted(scored, reverse=True)[:2]:
            budget = previous[level]
            rows.append(budget)
            rows.extend(dict(budget, face_skin=budget['face_skin']-shift,
                             hair=budget['hair']+shift) for shift in (20, 40, 80)
                        if budget['face_skin']-shift >= 1200)
            if budget['eye'] > 128:
                rows.append(dict(budget, eye=128, hair=budget['hair']+budget['eye']-128))
    elif any('Pupil lies outside' in reason or 'face/eye' in reason or
             'eye cap failed' in reason for reason in reasons):
        # Keep each player's original globe when an aperture approximation fails.
        rows.extend(eye_allocations())
    else:
        # Near-coincident source seams can make even generous face budgets fail.
        base = mobile.allocations()[0]
        for skin, eye, hair in ((1600,128,260),(1750,128,110),(1500,128,360)):
            for mode in ('shell', 'closed'):
                rows.append(dict(base, face_skin=skin, eye=eye, hair=hair, hair_mode=mode))
    result = []
    for budget in rows:
        budget = dict(budget, native_seam_alias=True, normal_export_recovery=True)
        if budget['head_cap'] != 2000 or sum(budget[k] for k in ('face_skin','eye','hair')) > 2000:
            raise ValueError('Retry allocation exceeds the complete-head budget')
        if budget not in result:
            result.append(budget)
    return result


def run(config_path, held_path, overlays, workers=2):
    config = read(config_path)
    source = Path(config['work_dir'])
    owners = indexed(read(config['source_profiles']), 'source identities')
    prepared = set()
    for folder in [source, *map(Path, overlays)]:
        for row in read(folder/'prepare-report.json'):
            if not owner_matches(row, owners.get(row['base_id'], {})):
                raise ValueError('Prepared identity differs from source')
            if row['status'] in ('prepared', 'prepared_cached'):
                prepared.add(row['base_id'])
    held = indexed(read(held_path), 'held recovery')
    selected = {base:row for base,row in held.items()
                if row['status'].startswith('held') and base not in prepared}
    for base, row in selected.items():
        if not owner_matches(row, owners.get(base, {})):
            raise ValueError('Held identity differs from source')
    work = source.parent/'targeted-recovery'
    work.mkdir(parents=True, exist_ok=True)
    hold = source/'QUALITY-HOLD.json'
    if not hold.exists() or read(hold).get('approved'):
        raise ValueError('Recovery requires an unreleased visual hold')
    shutil.copy2(hold, work/hold.name)
    overrides = {str(base):candidates(row) for base,row in selected.items()}
    local = dict(config, work_dir=str(work), allocation_overrides=overrides)
    write(work/'config.local.json', local)
    write(work/'retry-plan.json', dict(players=[dict(base_id=base,name=selected[base]['name'],
        attempts=len(overrides[str(base)])) for base in sorted(selected)], head_cap=2000))
    if not selected:
        print('No uncovered held heads to retry', flush=True)
        return
    process = mobile.PreparationProcess
    mobile.PreparationProcess = lambda blender: process(blender, script=mobile.HERE/'blender_realface_seam_worker.py')
    try:
        mobile.prepare(local, set(selected), workers)
    finally:
        mobile.PreparationProcess = process


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--held-report', required=True)
    parser.add_argument('--overlay', action='append', default=[])
    parser.add_argument('--workers', type=int, choices=(1,2), default=2)
    args = parser.parse_args()
    run(args.config, args.held_report, args.overlay, args.workers)

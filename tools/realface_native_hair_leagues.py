"""Resumable, bounded native-style hair conversion for verified league heads.

One private trial report per player/recipe avoids worker report races. The
coordinator publishes atomic league reports; inherited accepted heads are never
replaced. Geometry passes remain appearance/device holds until reviewed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from pathlib import Path
import time

from realface_batch import valid_cache, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_league_progress import indexed, owner_matches
from realface_native_hair_trial import CODE, HERE, trial
from realface_pipeline import sha


def face_choices(config, alternate=()):
    """Explicit, identity-matched face choices; never spend accepted face detail."""
    canonical = indexed(read(Path(config['work_dir']) / 'prepare-report.json'), 'prepared')
    owners = indexed(read(config['source_profiles']), 'sources')
    chosen = dict(canonical)
    for base, report in alternate:
        row = indexed(read(report), 'prepared').get(base, {})
        if canonical.get(base, {}).get('reuse_cooked'):
            raise ValueError('Alternate face cannot replace an accepted inherited head')
        if not owner_matches(row, owners.get(base, {})) or row.get('status') not in ('prepared', 'prepared_cached'):
            raise ValueError('Alternate face requires a verified prepared identity')
        if not valid_prepared_cache(Path(row['folder']), row['cache_key']):
            raise ValueError('Alternate face bytes changed')
        chosen[base] = row
    return canonical, chosen, owners


def reusable(row, face, owner, code):
    if (row.get('status') != 'candidate_visual_hold' or not row.get('composite_geometry_pass') or
            not owner_matches(row, owner) or row.get('recipe_source_sha256') != code or
            row.get('source_face_key') != face.get('cache_key')):
        return False
    if not valid_prepared_cache(Path(face['folder']), face['cache_key']):
        raise ValueError('Chosen prepared face bytes changed')
    if any(sha(path) != digest for path, digest in owner['input_hashes'].items()):
        raise ValueError('Pinned player source changed')
    if not valid_cache(Path(row['folder']), row['cache_key']):
        raise ValueError('Previously selected native hair candidate bytes changed')
    return True


def convert(config, face_report, base, work):
    """Try bounded closing variants, stopping at the first unchanged gate pass."""
    attempts = []
    for closing in (3, 1, 0):
        destination = Path(work) / 'players' / str(base) / ('closing-' + str(closing))
        try:
            trial(config, face_report, [base], destination, 420, 'alpha_volume', 'cycles_relief', closing)
            row = read(destination / 'trial-report.json')[0]
        except (ValueError, OSError) as error:
            row = dict(base_id=base, status='held_preflight', reason=str(error))
        attempts.append(dict(status=row['status'], closing_steps=closing, folder=row.get('folder'),
                             reason=row.get('reason')))
        if row['status'] == 'candidate_visual_hold':
            return dict(row, attempts=attempts)
        if 'insufficient visible hair volume' in row.get('reason', '') or 'No source scalp' in row.get('reason', ''):
            # Sparse/bald styles need no opaque bulk. Keep original source cards
            # and the same 13-view composite gate; do not invent a dense cap.
            destination = Path(work) / 'players' / str(base) / 'sparse-source'
            trial(config, face_report, [base], destination, 0, 'alpha_volume', 'cycles_relief', 3)
            row = read(destination / 'trial-report.json')[0]
            attempts.append(dict(status=row['status'], mode='sparse_source', folder=row.get('folder'),
                                 reason=row.get('reason')))
            return dict(row, attempts=attempts)
        # Input/face/material failures cannot be repaired by more voxel closing.
        if row['status'] == 'held_preflight':
            break
    return dict(row, attempts=attempts)


def coverage(snapshot, canonical, native, verified=()):
    cooked = {row['base_id']: row for row in verified}
    players = []
    for source in snapshot['players']:
        base = source['base_id']; old = canonical.get(base, {}); row = native.get(base, {})
        item = {key: source.get(key) for key in ('base_id', 'native_player_id', 'fingerprint', 'name', 'team_ids')}
        if old.get('reuse_cooked'):
            item.update(status='accepted_v37_retained', triangles=old.get('triangles'), visual_approved=True)
        elif row:
            item.update(status=row['status'], triangles=row.get('triangles'), reason=row.get('reason'),
                        cache_key=row.get('cache_key'), visual_approved=False)
            cooked_row = cooked.get(base, {})
            if cooked_row and cooked_row.get('cache_key') == row.get('cache_key'):
                if cooked_row['status'].startswith('validated'):
                    item['status'] = 'native_cooked_visual_hold'
                elif cooked_row['status'].startswith('held'):
                    item.update(status=cooked_row['status'], reason=cooked_row.get('reason'))
        elif old.get('status') in ('prepared', 'prepared_cached'):
            item.update(status='native_pending', visual_approved=False)
        else:
            item.update(status=source.get('stage', source.get('status', 'source_unresolved')),
                        reason=source.get('reason'), visual_approved=False)
        players.append(item)
    counts = dict(Counter(row['status'] for row in players))
    teams = []
    for team in snapshot.get('teams', []):
        team_id = team.get('team_id')
        members = [r for r in players if team_id in (r.get('team_ids') or [])]
        teams.append(dict(team, native_counts=dict(Counter(r['status'] for r in members))))
    return dict(maximum_head_triangles=2000, roster_identities=len(players), counts=counts,
                players=players, teams=teams, device_profiled=False, visual_approved=False)


def publish(work, snapshot, canonical, records, started, verified=()):
    rows = sorted(records.values(), key=lambda row: row['base_id'])
    write(work / 'trial-report.json', rows)
    if not verified and (work / 'verify-report.json').exists():
        verified = read(work / 'verify-report.json')
    report = coverage(snapshot, canonical, records, verified)
    report.update(elapsed_seconds=round(time.monotonic() - started, 2), native_attempted=len(rows))
    write(work / 'coverage.json', report)
    fields = ('base_id', 'native_player_id', 'name', 'team_ids', 'status', 'triangles', 'visual_approved', 'reason')
    # JSON is the atomic machine-readable checkpoint. CSV is regenerated from it.
    with (work / 'PLAYER-STATUS.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for row in report['players']:
            writer.writerow({key: ';'.join(map(str, row.get(key) or [])) if key == 'team_ids' else row.get(key)
                             for key in fields})
    return report


def run(config, work, snapshot, alternate=(), seeds=(), workers=2, selected=()):
    work = Path(work).resolve()
    if (not work.is_relative_to(HERE.parent / 'local-debug') or work == HERE.parent / 'local-debug' or
            work == Path(config['work_dir']).resolve()):
        raise ValueError('League native conversion needs a separate ignored work directory')
    if workers not in (1, 2, 3):
        raise ValueError('Native hair conversion supports one to three Blender workers')
    work.mkdir(parents=True, exist_ok=True)
    canonical, chosen, owners = face_choices(config, alternate)
    code = {name: sha(HERE / name) for name in CODE}
    targets = {base: row for base, row in chosen.items() if not row.get('reuse_cooked') and
               row.get('status') in ('prepared', 'prepared_cached') and (not selected or base in selected)}
    for base, row in targets.items():
        if not owner_matches(row, owners.get(base, {})):
            raise ValueError('Canonical prepared/source identity differs: ' + str(base))
    face_report = work / 'chosen-faces.json'; write(face_report, list(chosen.values()))
    write(work / 'run-config.json', dict(config=config, alternatives=[(b, str(p)) for b, p in alternate],
          seeds=[str(p) for p in seeds], workers=workers, head_cap=2000, native_code=code))
    write(work / 'QUALITY-HOLD.json', dict(approved=False, reason='League appearance/device review pending'))
    available = []
    if (work / 'trial-report.json').exists():
        available.extend(read(work / 'trial-report.json'))
    for seed in seeds:
        available.extend(read(Path(seed) / 'trial-report.json'))
    records = {}
    for number, row in enumerate(available, 1):
        base = row['base_id']
        if base in targets and reusable(row, chosen[base], owners[base], code):
            records[base] = row
        if number % 25 == 0 or number == len(available):
            progress = dict(checked=number, total=len(available), reusable=len(records), last_base_id=base)
            write(work / 'CACHE-STATUS.json', progress)
            print(dict(cache_verification=progress), flush=True)
    started = time.monotonic()
    publish(work, snapshot, canonical, records, started)
    print(dict(target=len(targets), retained_accepted=sum(bool(r.get('reuse_cooked')) for r in canonical.values()),
               reused=len(records), workers=workers), flush=True)
    # Interleave sorted identities. Each worker owns only its player's sub-tree.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(convert, config, face_report, base, work): base
                   for base in sorted(targets) if base not in records}
        for future in as_completed(pending):
            base = pending[future]
            row = future.result()
            records[base] = dict({k: owners[base][k] for k in ('base_id', 'native_player_id', 'fingerprint', 'name')}, **row)
            report = publish(work, snapshot, canonical, records, started)
            print(dict(completed=len(records), total=len(targets), base_id=base, status=row['status'],
                       counts=report['counts']), flush=True)
    return publish(work, snapshot, canonical, records, started)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True); parser.add_argument('--work-dir', required=True)
    parser.add_argument('--coverage', required=True); parser.add_argument('--seed', action='append', default=[])
    parser.add_argument('--face-choice', action='append', default=[], metavar='BASEID=REPORT')
    parser.add_argument('--workers', type=int, choices=(1, 2, 3), default=2)
    parser.add_argument('--player', type=int, action='append', default=[])
    args = parser.parse_args()
    alternate = [(int(value.split('=', 1)[0]), Path(value.split('=', 1)[1])) for value in args.face_choice]
    run(read(args.config), args.work_dir, read(args.coverage), alternate, args.seed, args.workers, args.player)

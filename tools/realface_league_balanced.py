"""Serial, resumable league heads using the accepted 5k Barca/MU recipe.

One Blender/editor/validator at a time. A failed 5k quality gate may try the
explicit exceptional ceiling, but complete heads must stay strictly below
7,000 triangles. Original inputs and the delivered v54 package are immutable.
Generated game payloads and reports belong in ignored local-debug on D.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import time

from realface_batch import valid_cache, valid_prepared_cache
from realface_batch_inventory import read, write
import realface_budget_experiment as trial
from realface_budget_hair_repair import facial_hair_count
from realface_budget_sweep import distribution, retryable
from realface_league_mobile import PreparationProcess
from realface_lite import sources
from realface_pipeline import sha

ROOT = Path(__file__).resolve().parents[1]
POLICY = 'league-balanced-v55'
CATEGORIES = ('english_league', 'spanish_league')
READY = ('prepared', 'prepared_cached')
VERIFIED = ('validated', 'validated_cached')


def local_output(path):
    path = Path(path).resolve()
    if (not path.is_relative_to(ROOT / 'local-debug') or path == ROOT / 'local-debug' or
            path.drive.upper() != 'D:'):
        raise ValueError('Use a dedicated ignored local-debug directory on D')
    return path


def unique(rows, label):
    result = {r['base_id']: r for r in rows}
    if len(result) != len(rows) or len({r['native_player_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate identity/native owner in ' + label)
    return result


def scope_for(config, catalogue):
    catalog = read(config['catalog'])
    categories = {c['key']: c for c in catalog['categories']}
    if not set(CATEGORIES) <= categories.keys():
        raise ValueError('Both league categories are required')
    teams = sorted({t for key in CATEGORIES for t in categories[key]['team_ids']})
    owners = [r for r in read(config['source_verification'])['players']
              if set(r.get('team_ids', [])) & set(teams)]
    owners_by_id = unique(owners, 'league roster')
    state = read(config['identity_state'])['identities']
    active = {p['base_id']: p for p in state.values() if p.get('status') == 'active'}
    for row in owners:
        identity = active.get(row['base_id'])
        if not identity or any(identity.get(k) != row[k] for k in ('native_player_id', 'fingerprint')):
            raise ValueError('League roster is not the active identity: ' + str(row['base_id']))
    selected, unresolved = [], []
    for base, owner in owners_by_id.items():
        source = catalogue.get(base)
        if source is None:
            unresolved.append(owner)
        elif any(source[k] != owner[k] for k in ('native_player_id', 'fingerprint')):
            raise ValueError('League source ownership differs')
        else:
            selected.append(base)
    if set(selected) != catalogue.keys():
        raise ValueError('Source list contains identities outside the two league rosters')
    return dict(policy=POLICY, categories=list(CATEGORIES), teams=teams,
                category_team_counts={key: len(categories[key]['team_ids']) for key in CATEGORIES},
                roster_count=len(owners), source_count=len(selected),
                selected_base_ids=sorted(selected), unresolved=unresolved,
                verification_sha256=sha(config['source_verification']),
                owners=owners, missing_catalog_team_note='Sunderland is absent from the supplied native catalog')


def assert_owner(row, owner):
    if any(row.get(k) != owner.get(k) for k in ('base_id', 'native_player_id', 'fingerprint')):
        raise ValueError('Player identity changed')


def validate_head(row):
    if row['status'] not in READY + VERIFIED:
        raise ValueError('Head is not prepared or verified')
    cap = row.get('budgets', {}).get('head_cap')
    if cap not in (5000, 6000, 7000):
        raise ValueError('Unexpected head recipe ceiling')
    folder = Path(row['folder'])
    total = trial.validate_preparation(read(folder / 'simplification.json'),
                                       read(folder / 'hair-projection.json'), cap)
    if total != row['triangles'] or total >= 7000:
        raise ValueError('Head must match its proof and stay strictly below 7000')
    if total > 5000 and not row.get('league_exception'):
        raise ValueError('Above-target head requires explicit exception provenance')
    return total


def baseline_rows(config, catalogue):
    work = Path(config['accepted_work'])
    prepared = unique(read(work / 'prepare-report.json'), 'accepted preparation')
    checked = unique(read(work / 'verify-report.json'), 'accepted verification')
    result = {}
    for base, proof in checked.items():
        if proof['status'] not in VERIFIED:
            continue
        old = prepared[base]
        assert_owner(old, catalogue[base]); assert_owner(proof, old)
        if proof['cache_key'] != old['cache_key']:
            raise ValueError('Accepted prepare/cook recipe differs')
        if not valid_cache(Path(proof['cooked_folder']), proof['cooked_cache_key']):
            raise ValueError('Accepted cooked head changed')
        # The old immutable profile is sufficient when no geometry is used.
        folder = Path(old['folder']); stamp = read(folder / 'complete.json')
        if stamp['cache_key'] != old['cache_key'] or sha(folder / 'ue-profile.json') != stamp['outputs']['ue-profile.json']:
            raise ValueError('Accepted prepared identity changed')
        row = dict(old, status='prepared_cached',
                   reuse_cooked={k: proof[k] for k in ('cooked_folder', 'cooked_cache_key')},
                   accepted_cohort=dict(verify_sha256=sha(work / 'verify-report.json'),
                                        source_cache_key=old['cache_key']))
        if row['triangles'] > 5000:
            row['league_exception'] = dict(reason='Retained exact accepted Barca/MU head',
                                          triangles=row['triangles'], source_verify_sha256=sha(work / 'verify-report.json'))
        validate_head(row); result[base] = row
    if len(result) != config['accepted_head_count']:
        raise ValueError('Accepted Barca/MU head count changed')
    return result


def prepare_player(config, row, worker):
    absent = [path for path in row['input_hashes'] if not Path(path).is_file()]
    if absent:
        return dict(row, status='held_source', reason='Optional original source files unavailable', missing_files=absent)
    attempts, locked, count = [], False, 0
    result = None
    for cap in (5000, 7000):
        for skin in ((3000, 2800, 2600) if cap == 5000 else (None,)):
            candidate = dict(config, experimental_head_cap=cap,
                             experimental_hair_policy='cards', experimental_allocations={})
            while True:
                if skin is not None:
                    candidate['experimental_allocations'] = {str(row['base_id']): distribution(cap, skin, locked)}
                else:
                    candidate['experimental_hair_policy'] = 'face_locked_cards' if locked else 'cards'
                result = trial.prepare_one(candidate, row, worker)
                if any(message in result.get('reason', '').lower() for message in
                       ('blender exited', 'allocate memory', 'bad_alloc', 'paging file', 'broken pipe')):
                    held = Path(result['folder']) / 'held.json'
                    if held.resolve().is_relative_to(Path(config['cache_dir']).resolve()):
                        held.unlink(missing_ok=True)
                    raise RuntimeError('Transient worker failure; resume after releasing memory: ' + result['reason'])
                request = Path(result['folder']) / 'lite_hair-meshopt.json'
                if request.is_file():
                    count = facial_hair_count(read(request))
                attempts.append(dict(cap=cap, skin=skin, facial_hair_locked=locked,
                                     **{k: result.get(k) for k in ('status', 'triangles', 'reason', 'cache_key', 'folder')}))
                # Never select the unprotected beard result, even when its
                # silhouette passes. This is the same measured v41 region rule.
                if count >= 20 and not locked:
                    locked = True
                    continue
                break
            if result['status'] in READY:
                result['league_attempts'] = attempts
                result['facial_hair_policy'] = dict(source_region_triangles=count, locked=locked)
                if result['triangles'] > 5000:
                    result['league_exception'] = dict(reason='5000 quality/budget attempts held',
                                                      triangles=result['triangles'], attempts=attempts[:-1])
                if result['triangles'] >= 7000:
                    result = dict(result, status='held_geometry', reason='Exceptional head must be strictly below 7000')
                    continue
                validate_head(result)
                return result
            if not retryable(result):
                break  # Do not lower face detail to pass an anatomy/UV failure.
    return dict(result, league_attempts=attempts, facial_hair_policy=dict(source_region_triangles=count, locked=locked))


def initialize(baseline, output, candidate):
    output = local_output(output); output.mkdir(parents=True, exist_ok=True)
    config_path = output / 'config.local.json'
    if config_path.exists():
        raise ValueError('Config already exists; resume it instead')
    baseline = Path(baseline).resolve()
    candidate = Path(candidate).resolve()
    candidate_proof = read(candidate.parent / 'release-validation.json')
    if candidate_proof.get('executing_build_id') != '79cf4f629bf5992fc6e878d96f15f7ff29a32c19':
        raise ValueError('Use the delivered v54 candidate')
    candidate_files = {}
    for name, proof in candidate_proof['files'].items():
        candidate_path = candidate / name
        if not candidate_path.resolve().is_relative_to(candidate) or sha(candidate_path) != proof['sha256']:
            raise ValueError('Delivered v54 file changed')
        if name.startswith('switch/pes21_nx/'):
            candidate_files[name] = proof
    if len(candidate_files) != 4:
        raise ValueError('Complete v54 runtime payload required')
    config = dict(read(baseline), policy=POLICY, work_dir=str(output),
                  cache_dir=str(output / 'cache'), experimental_head_cap=5000,
                  experimental_hair_policy='cards', experimental_allocations={},
                  accepted_work=str(baseline.parent), accepted_head_count=50,
                  import_chunk_size=12, serial_texture_cook=True,
                  v54_candidate=str(candidate), v54_pinned_files=candidate_files)
    config.pop('experimental_teams', None)
    catalogue = unique(sources(config), 'sources')
    scope = scope_for(config, catalogue)
    accepted_release = Path(read(baseline.parent / 'latest-test.json')['release'])
    config['accepted_release'] = str(accepted_release)
    config['accepted_stage'] = str(accepted_release.parent / 'stage')
    inputs = [baseline, Path(config['source_profiles']), Path(config['source_verification']),
              Path(config['identity_state']), Path(config['catalog']), Path(config['selector']),
              Path(config['accepted_work']) / 'prepare-report.json', Path(config['accepted_work']) / 'verify-report.json',
              Path(config['accepted_work']) / 'latest-test.json', accepted_release / 'VERIFICATION.json']
    config['pinned_inputs'] = {str(p.resolve()): sha(p) for p in inputs}
    write(config_path, config); write(output / 'league-scope.json', scope)
    write(output / 'RUN-STATUS.json', dict(phase='ready', state='initialized',
          total_sources=len(catalogue), roster_count=scope['roster_count'],
          teams=len(scope['teams']), installed=False, hardware_accepted=False))
    print(json.dumps(read(output / 'RUN-STATUS.json')), flush=True)


@contextmanager
def exclusive(work):
    import msvcrt
    path = work / 'runner.lock'
    with path.open('a+b') as stream:
        stream.seek(0); stream.write(b'0'); stream.flush(); stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError('This league runner is already active')
        try:
            yield
        finally:
            stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def run(config_path, limit=None):
    config = read(config_path); work = local_output(config['work_dir'])
    if config.get('policy') != POLICY:
        raise ValueError('Explicit league balanced policy required')
    with exclusive(work):
        for path, expected in config['pinned_inputs'].items():
            if sha(path) != expected:
                raise ValueError('Pinned league input changed: ' + path)
        catalogue = unique(sources(config), 'sources')
        scope = read(work / 'league-scope.json')
        if scope != scope_for(config, catalogue):
            raise ValueError('Active league scope changed')
        report = work / 'prepare-report.json'
        saved = unique(read(report), 'saved preparations') if report.exists() else {}
        accepted = baseline_rows(config, catalogue)
        for base, row in accepted.items():
            if base in saved and saved[base]['cache_key'] != row['cache_key']:
                raise ValueError('Accepted cohort was replaced')
            saved[base] = row
        write(report, sorted(saved.values(), key=lambda r: r['base_id']))
        verify_path = work / 'verify-report.json'
        verified = unique(read(verify_path), 'saved verification') if verify_path.exists() else {}
        pending = [base for base in sorted(catalogue) if base not in saved]
        if limit is not None:
            pending = pending[:limit]
        def status(phase, **extra):
            write(work / 'RUN-STATUS.json', dict(policy=POLICY, phase=phase, state='running',
                  pid=os.getpid(), updated_at=time.time(), workers=1, total_sources=len(catalogue),
                  prepared_processed=len(saved), prepared_statuses=dict(Counter(r['status'] for r in saved.values())),
                  verified=len([r for r in verified.values() if r['status'] in VERIFIED]),
                  installed=False, hardware_accepted=False, **extra))
        def cook_ready():
            ready = [row for base, row in sorted(saved.items()) if row['status'] in READY and base not in verified]
            if not ready:
                return
            from realface_batch import key_of
            import realface_batch_release as factory
            from realface_budget_cook import resume_import_chunk
            batch = work / 'batches' / key_of([r['cache_key'] for r in ready])[:16]
            batch_config = dict(config, work_dir=str(batch))
            write(batch / 'config.local.json', batch_config); write(batch / 'prepare-report.json', ready)
            status('cook', current_batch=len(ready))
            original = factory.import_chunk
            try:
                factory.import_chunk = resume_import_chunk
                factory.cook(batch_config)
            finally:
                factory.import_chunk = original
            status('verify', current_batch=len(ready))
            for result in factory.verify(batch_config, workers=1):
                assert_owner(result, catalogue[result['base_id']])
                if result['status'] in VERIFIED:
                    validate_head(result)
                    from realface_budget_package import counts
                    actual = counts(read(Path(result['cooked_folder']) / 'verification.json'),
                                    result['budgets']['head_cap'])
                    if actual['triangles'] != result['triangles'] or actual['triangles'] >= 7000:
                        raise ValueError('Cooked head does not match its bounded preparation')
                verified[result['base_id']] = result
                write(verify_path, sorted(verified.values(), key=lambda r: r['base_id']))
        # Reuse the accepted assets without starting a preparation worker.
        cook_ready()
        for start in range(0, len(pending), config['import_chunk_size']):
            worker = PreparationProcess(config['blender'], trial.HERE / 'blender_realface_budget_worker.py')
            try:
                for base in pending[start:start + config['import_chunk_size']]:
                    status('prepare', current_base_id=base, current_name=catalogue[base]['name'])
                    result = prepare_player(config, catalogue[base], worker)
                    assert_owner(result, catalogue[base]); saved[base] = result
                    write(report, sorted(saved.values(), key=lambda r: r['base_id']))
                    print(json.dumps(dict(done=len(saved), total=len(catalogue), base_id=base,
                                          status=result['status'], triangles=result.get('triangles'),
                                          reason=result.get('reason')), ensure_ascii=True), flush=True)
            finally:
                worker.close()
            cook_ready()
        if set(saved) == catalogue.keys():
            status('package_pending_review')
        else:
            status('batch_limit_reached')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=('init', 'run', 'status'))
    p.add_argument('--config', type=Path)
    p.add_argument('--baseline-config', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--v54-candidate', type=Path)
    p.add_argument('--limit', type=int)
    a = p.parse_args()
    if a.phase == 'init':
        if not all((a.baseline_config, a.output, a.v54_candidate)):
            p.error('init requires baseline config, output and v54 candidate')
        initialize(a.baseline_config, a.output, a.v54_candidate)
    elif not a.config:
        p.error('--config required')
    elif a.phase == 'status':
        print(json.dumps(read(Path(read(a.config)['work_dir']) / 'RUN-STATUS.json'), indent=2))
    else:
        try:
            run(a.config, a.limit)
        except Exception as error:
            work = local_output(read(a.config)['work_dir'])
            if 'already active' not in str(error):
                write(work / 'RUN-STATUS.json', dict(state='failed', reason=str(error),
                      pid=os.getpid(), updated_at=time.time(), installed=False))
            raise


if __name__ == '__main__':
    main()

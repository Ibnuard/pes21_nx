"""Isolated head-budget comparison; no release or active-runtime writes.

Keep identity, textures, two materials, original eyes and the same hair policy
constant across three triangle ceilings. Reuse the established preparation,
surface/UV/normal, rig and independent cooked-mesh gates. A successful offline
trial is not evidence of device appearance or frame rate.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import threading

from realface_batch import key_of, output_hashes, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_league_mobile import PreparationProcess, recipe_code
from realface_lite import LIMITS, sources
from realface_mobile import PROFILE_POLICY
from realface_pipeline import sha


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CAPS = (3000, 4500, 5000, 6000, 7000)
COHORT = (162114, 119835, 60512)
POLICY = dict(PROFILE_POLICY, face_texture_size=256)


def allocation(cap):
    """Only geometry allowance changes; texture, eye and material costs do not."""
    if cap not in CAPS:
        raise ValueError('Experimental cap must be 3000, 4500, 5000, 6000 or 7000')
    skin = {3000: 2100, 4500: 3000, 5000: 3000, 6000: 3900, 7000: 3900}[cap]
    return dict(face_skin=skin, eye=256, hair=cap-skin-276, head_cap=cap,
                skin_error_cm=.3, eye_error_cm=.06, eye_uv_weight=.1,
                skin_uv_weight=10., skin_normal_weight=.1,
                skin_feature_policy=True, native_seam_alias=True,
                source_eye=True, source_eye_policy='original_lod',
                normal_export_recovery=True, hair_mode='cards')


def validate_preparation(proof, projection, cap):
    total = proof['total_triangles']
    if not isinstance(total, int) or not 0 < total <= cap:
        raise ValueError('Complete head exceeds the explicit experimental ceiling')
    # These duplicate the existing mobile gates intentionally: no experimental
    # caller can publish a success merely because its worker forgot a check.
    if (projection['silhouette_iou_min'] < .80 or
            projection['silhouette_iou_mean'] < .85 or
            projection['missing_coverage_max'] > .15):
        raise ValueError('Hair silhouette held')
    if projection['card_fragments_after'] > projection['card_fragments_before'] * 1.05:
        raise ValueError('Hair card workload increased')
    if (projection['method']['mode'] == 'visible_cards' and
            projection['missing_coverage_max'] > .12):
        raise ValueError('Card gaps require a separate joined-hair experiment')
    return total


def isolated_config(config, output, cap):
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT/'local-debug') or output == ROOT/'local-debug':
        raise ValueError('Use a dedicated ignored local-debug experiment directory')
    # This tool has no package phase and never borrows mutable production caches.
    return dict(config, work_dir=str(output/str(cap)),
                cache_dir=str(output/'cache'), experimental_head_cap=cap,
                import_chunk_size=config.get('import_chunk_size',3), serial_texture_cook=True)


def team_scope(config, verification, teams):
    if not teams or not set(teams) <= {100,108}:
        raise ValueError('This controlled team experiment is limited to Barca and MU')
    catalogue = {p['base_id']:p for p in sources(config)}
    roster = [p for p in read(verification)['players'] if set(p.get('team_ids',[])) & set(teams)]
    if not roster or len({p['base_id'] for p in roster}) != len(roster):
        raise ValueError('Experimental roster is absent or duplicated')
    selected, unresolved = [], []
    for row in roster:
        source = catalogue.get(row['base_id'])
        if source is None:
            unresolved.append({k:row.get(k) for k in ('base_id','name','status','reason','team_ids')})
        elif any(source[k] != row[k] for k in ('native_player_id','fingerprint')):
            raise ValueError('Roster/source identity mismatch: '+str(row['base_id']))
        else:
            selected.append(row['base_id'])
    return dict(teams=sorted(teams), roster_count=len(roster), source_count=len(selected),
                selected_base_ids=selected, unresolved=unresolved,
                verification_sha256=sha(verification))


def effective_allocation(config, base):
    cap=config['experimental_head_cap']
    budget=allocation(cap)
    override=config.get('experimental_allocations',{}).get(str(base))
    if override is not None:
        # Allow per-identity distribution, never alternate quality thresholds.
        if (set(override)!={'face_skin','hair','hair_face_lock'} or
                override['face_skin'] not in (3000,2800,2600) or
                type(override['hair']) is not int or override['hair']<=0 or
                type(override['hair_face_lock']) is not bool or
                override['face_skin']+budget['eye']+override['hair']+20>cap):
            raise ValueError('Invalid bounded experimental allocation')
        budget.update(override)
        if override['hair_face_lock']:
            budget.update(hair_error_cm=.45,hair_uv_weight=.5)
    return budget


def prepare_one(config, row, worker):
    cap = config['experimental_head_cap']
    budget = effective_allocation(config,row['base_id'])
    if config.get('experimental_hair_policy') == 'face_locked_cards':
        budget.update(hair_face_lock=True,hair_error_cm=.45,hair_uv_weight=.5)
    elif config.get('experimental_hair_policy','cards') != 'cards':
        raise ValueError('Unknown explicit experimental hair policy')
    profile = read(row['profile'])
    if profile['native_player_id'] != row['native_player_id'] or profile.get('hair_skin_materials'):
        raise ValueError('Unsupported identity or skin carried in source hair')
    for path, digest in row['input_hashes'].items():
        if sha(path) != digest:
            raise ValueError('Pinned original source changed: '+path)
    limits = dict(LIMITS, hair={})
    code = recipe_code(budget)
    code[Path(__file__).name] = sha(__file__)
    code['blender_realface_budget_worker.py'] = sha(HERE/'blender_realface_budget_worker.py')
    tool_hashes = {k: sha(config[k]) for k in ('native_rig', 'cooked_rig', 'meshoptimizer')}
    if config.get('fast_raster'):
        tool_hashes['fast_raster'] = sha(config['fast_raster'])
    key = key_of(dict(source=row['input_hashes'], owner={k:row[k] for k in
        ('base_id', 'native_player_id', 'fingerprint')}, code=code, tools=tool_hashes,
        profile=profile, policy=POLICY, budgets=budget, limits=limits))
    folder = Path(config['cache_dir'])/'prepared'/(str(row['base_id'])+'-'+key[:16])
    entry = {k:row[k] for k in ('base_id', 'native_player_id', 'fingerprint', 'name')}
    entry.update(folder=str(folder), cache_key=key, budgets=budget,
                 quality_level=CAPS.index(cap), recipe_source_sha256=code,
                 experimental_only=True, device_appearance_pass=False, hardware_profiled=False)
    if valid_prepared_cache(folder, key):
        total = validate_preparation(read(folder/'simplification.json'),
                                     read(folder/'hair-projection.json'), cap)
        return dict(entry, status='prepared_cached', triangles=total)
    if (folder/'held.json').exists():
        return dict(entry, status='held_geometry', reason=read(folder/'held.json')['reason'])
    folder.mkdir(parents=True, exist_ok=True)
    job = dict(entry, source_profile=profile, native_rig=config['native_rig'],
               cooked_rig=config['cooked_rig'], limits=limits, node=config['node'],
               meshoptimizer=config['meshoptimizer'], mobile_v35=True,
               fast_raster=config.get('fast_raster'))
    write(folder/'job.json', job)
    try:
        worker(folder/'job.json', folder/'prepare.log')
        current = recipe_code(budget)
        current[Path(__file__).name] = sha(__file__)
        current['blender_realface_budget_worker.py'] = sha(HERE/'blender_realface_budget_worker.py')
        if current != code:
            raise ValueError('Preparation code changed while the trial was running')
        total = validate_preparation(read(folder/'simplification.json'),
                                     read(folder/'hair-projection.json'), cap)
        ue = dict(profile, face_fbx=str(folder/'face.fbx'), hair_fbx=str(folder/'hair.fbx'),
                  face_texture=str(folder/'opaque-atlas.png'), **POLICY)
        if (folder/'hair-shell.png').exists():
            ue['hair_texture'] = str(folder/'hair-shell.png')
        ue.pop('report', None)
        write(folder/'ue-profile.json', ue)
        write(folder/'recipe.json', dict(eye={}, source=row, mobile_v35=True,
                                        experimental_budget=cap))
        write(folder/'complete.json', dict(cache_key=key, outputs=output_hashes(folder)))
        return dict(entry, status='prepared', triangles=total)
    except Exception as error:
        write(folder/'held.json', dict(reason=str(error), experimental_budget=cap))
        return dict(entry, status='held_geometry', reason=str(error))


def prepare(configs, selected, workers):
    catalogue = {p['base_id']:p for p in sources(configs[0])}
    if not selected or any(base not in catalogue for base in selected):
        raise ValueError('Every experimental BaseId must have a verified source identity')
    if len(selected) > (59 if configs[0].get('experimental_teams') else 8):
        raise ValueError('Experimental cohort exceeds its explicitly selected scope')
    state, processes, lock = threading.local(), [], threading.Lock()
    source_locks = {base:threading.Lock() for base in selected}
    def one(config, row):
        if not hasattr(state, 'worker'):
            state.worker = PreparationProcess(config['blender'], HERE/'blender_realface_budget_worker.py')
            with lock:
                processes.append(state.worker)
        # Source-view cache writes share the source identity; do not run two
        # budget variants of that identity concurrently in different workers.
        with source_locks[row['base_id']]:
            return config, prepare_one(config, row, state.worker)
    results = {c['experimental_head_cap']:[] for c in configs}
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = [pool.submit(one, c, catalogue[b]) for c in configs for b in sorted(selected)]
            for future in as_completed(jobs):
                config, result = future.result()
                rows = results[config['experimental_head_cap']]
                rows.append(result)
                write(Path(config['work_dir'])/'prepare-report.json', sorted(rows,key=lambda r:r['base_id']))
                print(json.dumps(dict(cap=config['experimental_head_cap'], base_id=result['base_id'],
                    status=result['status'], triangles=result.get('triangles'),
                    reason=result.get('reason')), ensure_ascii=True), flush=True)
    finally:
        for process in processes:
            process.close()
    return results


def summarize(configs):
    output = Path(configs[0]['work_dir']).parent
    rows = []
    for config in configs:
        work = Path(config['work_dir'])
        for phase in ('prepare', 'cook', 'verify'):
            path = work/(phase+'-report.json')
            if path.exists():
                for row in read(path):
                    summary = dict(cap=config['experimental_head_cap'], phase=phase,
                        **{k:row[k] for k in ('base_id', 'name', 'status')},
                        triangles=row.get('triangles'), reason=row.get('reason'),
                        folder=row['folder'])
                    if phase == 'verify' and row['status'] in ('validated', 'validated_cached'):
                        checked = read(Path(row['cooked_folder'])/'verification.json')
                        # Use the independent cooked result, not requested target counts.
                        meshes = checked['parts']
                        total = sum(component['triangles'] for part in ('face','hair')
                                    for component in meshes[part]['components'].values())
                        from realface_budget_package import head_limit
                        limit=head_limit(row,config['experimental_head_cap'])
                        if (not 0 < total <= limit or
                                (row.get('accepted_baseline') and total!=row['accepted_baseline']['triangles'])):
                            raise ValueError('Cooked head exceeds this experiment ceiling')
                        summary['cooked_triangles'] = total
                    rows.append(summary)
    report = dict(experimental_only=True, device_appearance_pass=False, hardware_profiled=False,
        production_face_pak_created=False, policy=POLICY, rows=rows,
        note='Geometry/UV/rig gates do not prove in-game materials, animation, appearance or frame time.')
    write(output/'comparison.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'cook', 'verify', 'status'))
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--player', type=int, action='append')
    parser.add_argument('--cap', type=int, action='append', choices=CAPS)
    parser.add_argument('--workers', type=int, default=2, choices=(1,2))
    parser.add_argument('--team', type=int, action='append', choices=(100,108))
    parser.add_argument('--scope-verification')
    parser.add_argument('--hair-policy', choices=('cards','face_locked_cards'))
    args = parser.parse_args()
    config = read(args.config)
    if args.hair_policy is not None:
        config = dict(config, experimental_hair_policy=args.hair_policy)
    caps = sorted(set(args.cap or CAPS))
    selected = set(args.player or COHORT)
    scope = None
    if args.team:
        if not args.scope_verification:
            parser.error('--team requires --scope-verification')
        scope = team_scope(config,args.scope_verification,set(args.team))
        allowed = set(scope['selected_base_ids'])
        if args.player and not selected <= allowed:
            raise ValueError('Requested player is outside the verified Barca/MU source cohort')
        selected = selected if args.player else allowed
        config = dict(config,experimental_teams=scope['teams'])
    configs = [isolated_config(config,args.output,cap) for cap in caps]
    if scope:
        write(Path(args.output)/'team-scope.json',scope)
    for trial in configs:
        write(Path(trial['work_dir'])/'config.local.json', trial)
    if args.phase == 'prepare':
        prepare(configs, selected, args.workers)
    elif args.phase == 'cook':
        from realface_batch_release import cook
        for trial in configs:
            cook(trial, selected)
    elif args.phase == 'verify':
        from realface_batch_release import verify
        for trial in configs:
            verify(trial,args.workers)
    report = summarize(configs)
    print(json.dumps(dict(records=len(report['rows']), statuses=dict(Counter(
        (str(r['cap'])+'/'+r['phase']+'/'+r['status']) for r in report['rows'])))), flush=True)


if __name__ == '__main__':
    main()

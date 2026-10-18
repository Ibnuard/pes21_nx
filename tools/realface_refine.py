"""Audit and selectively rebuild difficult mobile faces and compact hairstyles.

All inputs and outputs are local. Reuse verified unaffected heads; never
increase the 2,000-triangle/two-section ceiling or replace player identity.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path

from realface_batch import command, key_of, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_mobile import CODE
from realface_pipeline import sha
from realface_surface_patch import BASE, NEW_PARENT, NEW_NORMAL, validate_source
from realface_surface_quality import audit_cached_player

HERE = Path(__file__).resolve().parent
REFINE_CODE = CODE+('realface_surface_quality.py', 'realface_hair_envelope.py', 'blender_realface_refine.py')


def retry_compact_hair(previous, owner, code):
    """Keep a successful bounded envelope, or retry a rejected solid fill once."""
    if (not previous or previous.get('recipe_source_sha256') != code or
            previous.get('baseline', {}).get('cache_key') != owner['cache_key'] or
            any(previous.get(k) != owner[k] for k in ('base_id','native_player_id','fingerprint'))):
        return False
    if previous.get('status') in ('prepared', 'prepared_cached'):
        return previous['budgets'].get('solid_scalp') is False
    return (previous.get('status') == 'held_geometry' and
            previous.get('reason', '').startswith('Hair silhouette held:'))


def baseline(config):
    report = read(config['baseline_verification'])
    verified = read(config['baseline_identity_report'])
    extra = {BASE+NEW_PARENT+s for s in ('.uasset', '.uexp')} | {
        BASE+NEW_NORMAL+s for s in ('.uasset', '.uexp', '.ubulk')}
    if not extra <= set(report['asset_hashes']):
        raise ValueError('A verified isolated face normal material is required')
    stripped = dict(report, asset_hashes={k:v for k,v in report['asset_hashes'].items() if k not in extra})
    owners = validate_source(stripped, verified, read(config['identity_state']))
    for p in report['players']:
        if p.get('fingerprint') != owners[p['base_id']]['fingerprint'] or p.get('material') != NEW_PARENT:
            raise ValueError('Baseline identity or isolated material changed')
    if sha(config['baseline_pak']) != report['pak_sha256']:
        raise ValueError('Baseline PAK changed')
    return report, owners


def plan(config):
    work = Path(config['work_dir']).resolve()
    if not any(work.is_relative_to(HERE.parent/d) and work != HERE.parent/d for d in ('local-debug', 'local-inputs')):
        raise ValueError('Output must be a dedicated ignored directory')
    report, owners = baseline(config)
    code = {name: sha(HERE/name) for name in REFINE_CODE}
    audit_key = key_of(dict(report=sha(config['baseline_identity_report']),
                            audit=code['realface_surface_quality.py'], raster=code['realface_mobile_geometry.py']))
    audit_file = work/'audits'/(audit_key+'.json')
    if audit_file.is_file():
        audited = read(audit_file)
        # Recheck the audited input bytes, even when no raster needs rerunning.
        for row in audited:
            folder = Path(owners[row['base_id']]['folder'])
            if any(sha(folder/name) != value for name,value in row['input_sha256'].items()):
                raise ValueError('Audited reduction cache changed')
    else:
        with ProcessPoolExecutor(max_workers=2) as pool:
            audited = list(pool.map(audit_cached_player, owners.values()))
        write(audit_file, audited)
    write(work/'baseline-surface-audit.json', audited)
    projections = {p['base_id']: p for p in audited}
    previous = ({p['base_id']:p for p in read(work/'prepare-report.json')}
                if (work/'prepare-report.json').exists() else {})
    selected = []
    for player in report['players']:
        row = owners[player['base_id']]
        projection = projections[row['base_id']]
        hair = player['hair_projection']
        refine_face = projection['priority']
        refine_hair = (hair['method']['mode'] == 'visible_cards' and
                       hair['missing_coverage_max'] > .12)
        if not (refine_face or refine_hair): continue
        old = Path(row['folder'])
        if not valid_prepared_cache(old, row['cache_key']):
            raise ValueError('Baseline prepared cache changed: '+str(row['base_id']))
        source = read(old/'recipe.json')['source']
        for name, digest in source['input_hashes'].items():
            if sha(name) != digest: raise ValueError('Pinned source changed: '+name)
        budgets = dict(row['budgets'])
        if refine_face:
            budgets.update(skin_uv_weight=10., skin_normal_weight=.1, skin_feature_policy=True)
        if refine_hair:
            bounded = (row['base_id'] in config.get('bounded_hair_base_ids', []) or
                       retry_compact_hair(previous.get(row['base_id']), row, code))
            budgets.update(hair_mode='shell', solid_scalp=not bounded)
        entry = {k:row[k] for k in ('base_id', 'native_player_id', 'fingerprint', 'name')}
        key = key_of(dict(baseline=row['cache_key'], code=code, budgets=budgets,
                          source=source['input_hashes'], face=refine_face, hair=refine_hair,
                          tools={k:sha(config[k]) for k in ('native_rig','cooked_rig','meshoptimizer')}))
        folder = Path(config['cache_dir'])/'refined-jobs'/(str(row['base_id'])+'-'+key[:16])
        entry.update(folder=str(folder), cache_key=key, baseline=row, budgets=budgets,
                     refine_face=refine_face, refine_hair=refine_hair,
                     baseline_projection=projection, recipe_source_sha256=code)
        selected.append(entry)
    if not selected: raise ValueError('No faces or hairstyles require this refinement policy')
    manifest = dict(players=selected, report=str(work/'prepare-report.json'),
                    baseline_pak_sha256=report['pak_sha256'], audit_key=audit_key)
    write(work/'plan.json', manifest)
    print(json.dumps(dict(audited=len(audited), selected=len(selected),
                          face=sum(r['refine_face'] for r in selected), hair=sum(r['refine_hair'] for r in selected))), flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('phase', choices=('plan', 'prepare', 'cook', 'verify', 'preview', 'package'))
    args = parser.parse_args()
    config = read(args.config)
    if args.phase in ('plan', 'prepare'):
        plan(config)
        if args.phase == 'prepare':
            work = Path(config['work_dir'])
            for attempt in range(2):
                command([config['blender'], '--background', '--threads', '2', '--python-exit-code', '1',
                         '--python', HERE/'blender_realface_refine.py', '--', work/'plan.json'], work/('prepare-'+str(attempt)+'.log'))
                rows = read(work/'prepare-report.json')
                retry = any(r['status']=='held_geometry' and r['budgets'].get('solid_scalp') and
                            r.get('reason','').startswith('Hair silhouette held:') for r in rows)
                if not retry or attempt == 1: break
                plan(config)
            print(json.dumps(dict(prepared=sum(r['status'] in ('prepared', 'prepared_cached') for r in rows),
                                  held=[dict(base_id=r['base_id'], reason=r.get('reason')) for r in rows if r['status']=='held_geometry'])))
            if any(r['status']=='held_geometry' for r in rows):
                raise SystemExit('Refinement held: review prepare-report.json before continuing')
    elif args.phase in ('cook', 'verify'):
        from realface_batch_release import cook, verify
        (cook if args.phase == 'cook' else verify)(config)
    elif args.phase == 'preview':
        from realface_refine_preview import preview
        preview(config)
    else:
        from realface_refine_release import package
        package(config)


if __name__ == '__main__':
    main()

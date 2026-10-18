"""Report current league coverage without treating stale draft passes as release approval.

This is a metadata snapshot. It does not replace the factory's asset hash,
identity, geometry, cooked-buffer, visual or hardware release checks.
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from realface_batch_inventory import read, write
from realface_league_mobile import recipe_code


def indexed(rows, label):
    result = {}
    for row in rows:
        base = row['base_id']
        if base in result:
            raise ValueError('Duplicate BaseId in ' + label + ': ' + str(base))
        result[base] = row
    return result


def owner_matches(row, owner):
    return all(row.get(k) == owner.get(k) and row.get(k) is not None
               for k in ('base_id', 'native_player_id', 'fingerprint'))


def concise_reason(reason):
    """Keep spreadsheet rows readable; coverage.json retains full diagnostics."""
    title, separator, detail = str(reason).partition(': ')
    if separator and detail.startswith('{'):
        try:
            proof = json.loads(detail)
            metrics = []
            for key, label in (('silhouette_iou_min','minimum IoU'),
                               ('silhouette_iou_mean','mean IoU'),
                               ('missing_coverage_max','missing coverage'),
                               ('max_cm','maximum distance cm'),
                               ('p95_cm','p95 distance cm'),
                               ('lower_neck_max_cm','neck distance cm')):
                if isinstance(proof.get(key), (int,float)):
                    metrics.append(label+' '+format(proof[key],'.4g'))
            return title+(' ('+'; '.join(metrics)+')' if metrics else '')
        except (json.JSONDecodeError, TypeError):
            pass
    return str(reason)[:240]


def passing_trial(label, preparations, verifications, owners, current_recipe=recipe_code):
    """A failed optional experiment must not replace a valid earlier candidate."""
    prepared=indexed(preparations,label+'/prepare')
    verified=indexed(verifications,label+'/verify')
    for rows in (prepared,verified):
        for base,row in rows.items():
            if not owner_matches(row,owners.get(base,{})):
                raise ValueError('Trial identity differs from source: '+str(base))
    selected=[];outcomes=[]
    for base,row in prepared.items():
        if row.get('reuse_cooked'):continue
        checked=verified.get(base,{})
        current=('budgets' in row and row.get('recipe_source_sha256')==current_recipe(row['budgets']))
        matches=checked.get('cache_key')==row.get('cache_key')
        passed=(current and row['status'] in ('prepared','prepared_cached') and matches and
                checked.get('status') in ('validated','validated_cached'))
        if passed:selected.append(row)
        reason=row.get('reason') or (row.get('attempts') or [{}])[-1].get('reason')
        if matches and checked.get('reason'):reason=checked['reason']
        outcomes.append(dict(batch=label,base_id=base,name=row.get('name'),selected=passed,
            preparation_status=row['status'],current_recipe=current,
            cook_status=checked.get('status') if matches else None,reason=reason,
            visual_review='pending'))
    return selected,outcomes


def summarize(owners, source_ids, batches, current_recipe=recipe_code):
    owners = indexed(owners, 'source verification')
    if not source_ids <= owners.keys():
        raise ValueError('Source profiles include an unknown owner')
    prepared, verified, historical_passes = {}, {}, set()
    verifications_by_key={}
    def is_current(row):
        return bool(row.get('reuse_cooked') and row.get('inherited_release_sha256')) or (
            'budgets' in row and row.get('recipe_source_sha256')==current_recipe(row['budgets']))
    for label, preparations, verifications in batches:
        for kind, rows, target in (('prepare', preparations, prepared), ('verify', verifications, verified)):
            for base, row in indexed(rows, label + '/' + kind).items():
                if base not in source_ids or not owner_matches(row, owners[base]):
                    raise ValueError('Report identity differs from source: ' + str(base))
                if kind=='verify' and row['status'] in ('validated','validated_cached'):
                    historical_passes.add(base)
                if kind=='verify':verifications_by_key[(base,row.get('cache_key'))]=row
                if kind=='prepare' and base in target and is_current(target[base]) and not is_current(row):
                    continue
                target[base] = row
    players = []
    for base, owner in sorted(owners.items()):
        p=prepared.get(base)
        v=verifications_by_key.get((base,p.get('cache_key') if p else None),verified.get(base))
        row = {k: owner.get(k) for k in ('base_id', 'native_player_id', 'fingerprint', 'name', 'team_ids')}
        row.update(source_status=owner['status'], triangles=None, visual_review='pending',
                   historical_cook_pass=False, current_recipe=False)
        if base not in source_ids:
            row.update(stage='source_unresolved', reason=owner['status'])
        elif p is None:
            row.update(stage='prepare_pending', reason='No preparation record')
        else:
            same = v is not None and v.get('cache_key') == p.get('cache_key')
            passed = same and v['status'] in ('validated', 'validated_cached')
            inherited = bool(p.get('reuse_cooked') and p.get('inherited_release_sha256'))
            current = inherited or ('budgets' in p and p.get('recipe_source_sha256') == current_recipe(p['budgets']))
            row.update(triangles=p.get('triangles'), current_recipe=current,
                       historical_cook_pass=base in historical_passes,
                       cache_key=p.get('cache_key'))
            if inherited:
                row.update(stage='accepted_v37', visual_review='accepted_v37',
                           reason='Pinned previously accepted release')
            elif p['status']=='held_source_layout':
                row.update(stage=p['status'], reason=p.get('reason', p['status']))
            elif not current:
                row.update(stage='recipe_changed', reason='Historical draft requires current preparation and review')
            elif p['status'].startswith('held'):
                reason=p.get('reason') or (p.get('attempts') or [{}])[-1].get('reason', p['status'])
                row.update(stage=p['status'], reason=reason)
            elif same and v['status'].startswith('held'):
                row.update(stage=v['status'], reason=v.get('reason', v['status']))
            elif passed:
                row.update(stage='cooked_needs_visual_review', reason='Current technical pass; appearance not approved')
            else:
                row.update(stage='cook_pending', reason='Current prepared head needs matching cooked validation')
            if current and row['triangles'] is not None and not 0 < row['triangles'] <= 2000:
                raise ValueError('Current complete head exceeds triangle limit: ' + str(base))
        players.append(row)
    return dict(metadata_snapshot_only=True, maximum_head_triangles=2000,
                roster_identities=len(owners), verified_sources=len(source_ids),
                historical_cook_passes=len(historical_passes),
                current_cook_passes=sum(p['stage'] in ('accepted_v37','cooked_needs_visual_review') for p in players),
                counts=dict(Counter(p['stage'] for p in players)), players=players)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--overlay', action='append', default=[], help='Recovery work directory, in precedence order')
    parser.add_argument('--trial', action='append', default=[],
        help='Optional experiment: overlay only current cooked passes; retain failed attempts in the report')
    parser.add_argument('--output', required=True)
    args=parser.parse_args();config=read(args.config)
    source=read(config['source_verification']);profiles=indexed(read(config['source_profiles']), 'source profiles')
    owners=indexed(source['players'], 'source verification')
    if any(not owner_matches(row, owners.get(base, {})) for base,row in profiles.items()):
        raise ValueError('Source profile identity differs from verification')
    batches=[];holds=[];trial_outcomes=[]
    folders=[(Path(folder),False) for folder in [config['work_dir'],*args.overlay]]
    folders.extend((Path(folder),True) for folder in args.trial)
    for folder,is_trial in folders:
        reports=[read(folder/(stage+'-report.json')) if (folder/(stage+'-report.json')).exists() else []
                 for stage in ('prepare','verify')]
        if is_trial:
            reports[0],outcomes=passing_trial(str(folder),*reports,owners)
            trial_outcomes.extend(outcomes)
        batches.append((str(folder),*reports))
        if (folder/'QUALITY-HOLD.json').exists():holds.append(str(folder/'QUALITY-HOLD.json'))
    report=summarize(source['players'],set(profiles),batches)
    report['release_holds']=holds
    report['trial_outcomes']=trial_outcomes
    report['teams']=[dict(team,counts=dict(Counter(p['stage'] for p in report['players']
                              if team['team_id'] in (p['team_ids'] or [])))) for team in source['teams']]
    out=Path(args.output);write(out/'coverage.json',report)
    fields=('base_id','native_player_id','fingerprint','name','team_ids','source_status','stage',
            'triangles','visual_review','current_recipe','historical_cook_pass','reason')
    subsets={
        'PLAYER-STATUS.csv':report['players'],
        'HELD-GEOMETRY.csv':[p for p in report['players'] if p['stage'].startswith('held')],
        'UNRESOLVED-SOURCES.csv':[p for p in report['players'] if p['stage']=='source_unresolved'],
        'CURRENT-TECHNICAL-PASSES.csv':[p for p in report['players'] if p['stage'] in ('accepted_v37','cooked_needs_visual_review')],
    }
    for filename, players in subsets.items():
        with (out/filename).open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader()
            for row in players:
                writer.writerow(dict(row,team_ids=';'.join(map(str,row['team_ids'] or [])),
                                     reason=concise_reason(row['reason'])))
    stages=sorted(report['counts'])
    with (out/'TEAM-STATUS.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        fields=('team_id','name','roster_identities',*stages)
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for team in report['teams']:
            writer.writerow(dict(team_id=team['team_id'],name=team.get('name',team.get('team_name','')),
                roster_identities=sum(team['counts'].values()),**{k:team['counts'].get(k,0) for k in stages}))
    print({k:v for k,v in report.items() if k not in ('players','teams','trial_outcomes')})


if __name__=='__main__':main()

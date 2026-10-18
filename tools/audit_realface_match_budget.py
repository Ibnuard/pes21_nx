"""Summarize a selected roster's verified head costs without recooking assets.

Counts describe the roster, not the starting XI, simultaneous draws, GPU time,
or measured frame pacing. Native slot comparison is a cost reference only.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics


def distribution(values):
    values = list(values)
    return dict(min=min(values), median=statistics.median(values),
                max=max(values), total=sum(values)) if values else None


def audit(verification, status, native, team_ids):
    if not team_ids:
        raise ValueError('Select at least one roster team')
    if len({r['base_id'] for r in status}) != len(status):
        raise ValueError('Duplicate status identity')
    if len({r['base_id'] for r in verification['players']}) != len(verification['players']):
        raise ValueError('Duplicate release identity')
    owners = {r['base_id']: r for r in verification['players']}
    known_teams = {r['team_id']: r for r in verification['teams']}
    if not team_ids <= set(known_teams):
        raise ValueError('Unknown roster team')
    selected = {base: r for base, r in owners.items() if team_ids & set(r['team_ids'])}
    rows = []
    for row in status:
        base = row['base_id']
        if base not in owners or row['native_player_id'] != owners[base]['native_player_id']:
            raise ValueError('Status identity differs from release')
        if base not in selected:
            continue
        if row['status'] not in ('validated', 'validated_cached'):
            raise ValueError('Selected mesh is not validated')
        item = dict(row, team_ids=sorted(team_ids & set(selected[base]['team_ids'])))
        slot = str(row['native_player_id'])
        pair = [native['meshes'].get(slot+'_'+part) for part in ('face', 'hair')]
        item['native_slot_pair_present'] = all(pair)
        if all(pair):
            item['native_slot_triangles'] = sum(p['lods'][0]['triangles'] for p in pair)
            item['native_slot_sections'] = sum(p['lods'][0]['sections'] for p in pair)
        rows.append(item)
    accepted = {base for base, row in selected.items()
                if row['status'] in ('candidate_pending_device', 'preserved_verified')}
    if {r['base_id'] for r in rows} != accepted:
        raise ValueError('Selected accepted coverage is incomplete')
    if not rows:
        raise ValueError('Selected roster has no verified real faces')
    native_pairs = []
    for name, mesh in native['meshes'].items():
        if name.endswith('_face') and (hair := native['meshes'].get(name[:-5]+'_hair')):
            native_pairs.append(dict(triangles=mesh['lods'][0]['triangles']+hair['lods'][0]['triangles'],
                                     sections=mesh['lods'][0]['sections']+hair['lods'][0]['sections']))
    return dict(scope='Selected roster heads, including substitutes; not a frame or starting XI',
        hardware_profiled=False, teams=[known_teams[i] for i in sorted(team_ids)],
        players=len(rows), unavailable_target_players=len(selected)-len(rows),
        triangles=distribution(r['lite_triangles'] for r in rows),
        vertices=distribution(r['lite_vertices'] for r in rows),
        material_sections=dict(Counter(r['material_sections'] for r in rows)),
        native_slot_pairs_present=sum(r['native_slot_pair_present'] for r in rows),
        native_reference=dict(pairs=len(native_pairs),
            triangles=distribution(r['triangles'] for r in native_pairs),
            material_sections=dict(Counter(r['sections'] for r in native_pairs))),
        players_over_2000=sum(r['lite_triangles']>2000 for r in rows),
        players_over_4000=sum(r['lite_triangles']>4000 for r in rows),
        roster=sorted(rows, key=lambda r: (-r['lite_triangles'], r['base_id'])))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verification', type=Path, required=True)
    p.add_argument('--status', type=Path, required=True)
    p.add_argument('--native-metrics', type=Path, required=True)
    p.add_argument('--team', type=int, action='append', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    paths = dict(verification=a.verification, status=a.status, native=a.native_metrics)
    docs = {key: json.loads(path.read_text(encoding='utf-8-sig')) for key, path in paths.items()}
    result = audit(docs['verification'], docs['status'], docs['native'], set(a.team))
    result['inputs'] = {key: dict(file=str(path.resolve()),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for key, path in paths.items()}
    result['lite_pak_sha256'] = docs['verification']['pak_sha256']
    result['native_pak_sha256'] = docs['native']['pak_sha256']
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key not in ('roster', 'inputs')},
                     indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()

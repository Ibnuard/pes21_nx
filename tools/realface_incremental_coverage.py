"""Reconcile every league identity, including failed recovery attempts.

This metadata report never grants appearance/device approval. The package
factory independently checks all selected prepared/cooked bytes and screens.
"""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path

from realface_batch_inventory import read, write
from realface_league_progress import owner_matches, concise_reason
from realface_pipeline import sha


def summarize(baseline, inventory, reports, rejects, verified):
    result = {k: deepcopy(baseline[k]) for k in
              ('maximum_head_triangles', 'roster_identities', 'players', 'teams')}
    roster = {r['base_id']: r for r in result['players']}
    sources = {r['base_id']: r for r in inventory['players']}
    if len(roster) != len(result['players']) or len(sources) != len(inventory['players']) or set(roster) != set(sources):
        raise ValueError('Recovery must account for the complete unique roster')
    retained = {r['base_id'] for r in baseline['players_in_package']}
    for base, row in roster.items():
        if not owner_matches(row, sources[base]):
            raise ValueError('Source inventory ownership changed')
        row['source_status'] = sources[base]['status']
        row['recovery_attempts'] = []
        if base not in retained and row['status'] == 'source_unresolved' and sources[base]['status'] == 'source_ready':
            row.update(status='source_recovered_pending', reason='Identity alias verified; model processing pending.')
        if sources[base].get('source_identity_evidence'):
            row['source_identity_evidence'] = sources[base]['source_identity_evidence']
    for label, rows in reports:
        for item in rows:
            base = item['base_id']
            if base in retained or not owner_matches(item, roster.get(base, {})):
                raise ValueError('Recovery report replaces a baseline head or changes identity')
            reason = item.get('reason') or (item.get('attempts') or [{}])[-1].get('reason')
            record = dict(batch=label, cache_key=item.get('cache_key'), status=item['status'],
                          reason=concise_reason(reason) if reason else None)
            roster[base]['recovery_attempts'].append(record)
            roster[base].update(status=item['status'], triangles=item.get('triangles'),
                reason=record['reason'] or 'Recovery candidate requires current visual and cooked checks.')
    rejected = {(r['base_id'], r['cache_key']): r for r in rejects}
    for base, row in roster.items():
        observed = [rejected[(base, a['cache_key'])] for a in row['recovery_attempts']
                    if (base, a['cache_key']) in rejected]
        if base not in retained and observed:
            row.update(status='held_visual', reason=observed[-1]['reason'])
            row['visual_rejections'] = observed
    selected = []; seen = set()
    for item in verified:
        base = item['base_id']; row = roster.get(base, {})
        if base in retained or not owner_matches(item, row):
            raise ValueError('Cook report changes baseline/roster identity')
        if item['status'] not in ('validated', 'validated_cached'):
            row.update(status=item['status'], reason=item.get('reason') or 'Independent cooked verification did not pass.')
            continue
        if base in seen or (base, item['cache_key']) in rejected:
            raise ValueError('Duplicate or visually rejected cooked candidate')
        if not any(a['cache_key'] == item['cache_key'] and a['status'] == 'candidate_visual_hold'
                   for a in row['recovery_attempts']):
            raise ValueError('Cooked candidate has no matching geometry report')
        seen.add(base); selected.append(item)
        row.update(status='recovered_cooked_visual_hold', triangles=item['triangles'],
            reason='Front-screened and independently cooked; full appearance and Switch review pending.')
    result.update(counts=dict(Counter(r['status'] for r in result['players'])),
        source_counts=dict(Counter(r['status'] for r in inventory['players'])),
        source_aliases_recovered=len(inventory.get('source_recovery', {}).get('recovered', [])),
        recovery_candidates_cooked=len(selected), maximum_head_triangles=2000,
        device_profiled=False, visual_approved=False, test_candidate=True)
    return result, sorted(selected, key=lambda r: r['base_id'])


def build(specification, work):
    spec = read(specification); work = Path(work).resolve()
    root = Path(__file__).resolve().parent.parent / 'local-debug'
    if not work.is_relative_to(root) or work == root:
        raise ValueError('Recovery coverage must remain in a dedicated ignored directory')
    inputs = [spec['baseline'], spec['inventory'], *spec['reports'], *spec['rejects'], *spec['verified']]
    proof = {p: sha(p) for p in inputs}
    result, selected = summarize(read(spec['baseline']), read(spec['inventory']),
        [(p, read(p)) for p in spec['reports']], [r for p in spec['rejects'] for r in read(p)],
        [r for p in spec['verified'] for r in read(p)])
    if proof != {p: sha(p) for p in inputs}:
        raise ValueError('Recovery reports changed during reconciliation')
    result['recovery_evidence_sha256'] = proof
    write(work / 'coverage.json', result)
    write(work / 'selected-verified.json', selected)
    print(dict(selected=len(selected), counts=result['counts']), flush=True)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--specification', required=True)
    p.add_argument('--work-dir', required=True)
    a = p.parse_args(); build(a.specification, a.work_dir)

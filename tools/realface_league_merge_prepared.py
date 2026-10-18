"""Merge validated preparation retries into a held league cook queue."""
import argparse
from collections import Counter
from pathlib import Path

from realface_batch import valid_prepared_cache
from realface_batch_inventory import read, write
from realface_league_mobile import recipe_code
from realface_league_progress import indexed, owner_matches


def merge_rows(existing, overlays, owners, current_code=recipe_code,
               check_cache=valid_prepared_cache):
    result = indexed(existing, 'target preparation')
    changed = []
    for label, rows in overlays:
        for base, row in indexed(rows, label).items():
            if not owner_matches(row, owners.get(base, {})):
                raise ValueError('Retry identity differs from the pinned source')
            previous = result.get(base, {})
            if row.get('reuse_cooked'):
                if not previous.get('reuse_cooked') or previous['cache_key'] != row['cache_key']:
                    raise ValueError('Retry cannot introduce or replace an inherited head')
                continue
            if row['status'] not in ('prepared', 'prepared_cached'):
                continue
            if previous.get('reuse_cooked'):
                raise ValueError('Retry cannot replace an accepted inherited head')
            if row.get('recipe_source_sha256') != current_code(row['budgets']):
                raise ValueError('Retry recipe changed since preparation')
            if not 0 < row.get('triangles', 0) <= 2000:
                raise ValueError('Retry exceeds the complete-head triangle limit')
            if not check_cache(Path(row['folder']), row['cache_key']):
                raise ValueError('Retry prepared assets changed')
            if previous.get('cache_key') != row['cache_key']:
                changed.append(dict(base_id=base, previous_key=previous.get('cache_key'),
                                    cache_key=row['cache_key'], source=label))
            result[base] = row
    return sorted(result.values(), key=lambda r: r['base_id']), changed


def merge(config_path, overlay_paths):
    config = read(config_path)
    work = Path(config['work_dir'])
    hold = work/'QUALITY-HOLD.json'
    if not hold.exists() or read(hold).get('approved'):
        raise ValueError('Preparation retries require an unreleased quality-held queue')
    owners = indexed(read(config['source_profiles']), 'source identities')
    overlays = [(str(p), read(Path(p)/'prepare-report.json')) for p in overlay_paths]
    rows, changed = merge_rows(read(work/'prepare-report.json'), overlays, owners)
    # Persist actual successful allocations for a later resumable preparation.
    overrides = config.setdefault('allocation_overrides', {})
    changed_ids = {r['base_id'] for r in changed}
    for row in rows:
        if row['base_id'] in changed_ids:
            overrides[str(row['base_id'])] = [row['budgets']]
    write(config_path, config)
    write(work/'prepare-merge.json', dict(changed=changed, counts=dict(Counter(r['status'] for r in rows))))
    # This atomic write lets an already-running cook queue see the next batch;
    # cooked rows are never copied or relabelled as matching the new key.
    write(work/'prepare-report.json', rows)
    print(dict(merged=len(changed), heads=len(rows), visual_approval=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--overlay', action='append', required=True)
    args = parser.parse_args()
    merge(args.config, args.overlay)

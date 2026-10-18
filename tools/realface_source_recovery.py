"""Recover explicit name aliases without weakening automatic identity rules."""
import argparse
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from realface_batch_inventory import read, write
from realface_pipeline import sha
from realface_source_identity import tokens


def build_index(config, destination):
    """Index local archives once; future recovery runs reuse the saved index."""
    from realface_batch_inventory import source_index
    destination = Path(destination).resolve()
    root = Path(__file__).resolve().parent.parent / 'local-debug'
    if not destination.is_relative_to(root):
        raise ValueError('Source index must remain in ignored local-debug')
    biographies = {}
    players, sources, archives = source_index(config['cpks'], biographies)
    write(destination, dict(players={str(k): asdict(v) for k, v in players.items()},
          sources=sources, biographies=biographies, archives=archives))


def match_alias(owner, candidate, bio, alias):
    if (not candidate or not bio or owner['base_id'] != alias['base_id'] or
            candidate['player_id'] != owner['base_id'] or not owner.get('fingerprint')):
        return None
    names = {tuple(tokens(n)) for n in alias['names']}
    if tuple(tokens(owner['name'])) not in names or tuple(tokens(candidate['name'])) not in names:
        return None
    if not alias.get('evidence') or any(not u.startswith('https://') for u in alias['evidence']):
        return None
    if (abs(owner['height']-bio['height']) > 3 or abs(owner['age']-bio['age']) > 3 or
            owner['foot'] != bio['foot'] or (owner['position'] == 0) != (bio['position'] == 0)):
        return None
    if owner['country'] != bio['country']:
        if set(alias.get('country_pair', [])) != {owner['country'], bio['country']}:
            return None
    return dict(policy='explicit_alias_base_fingerprint_v1', base_id=owner['base_id'],
                canonical_fingerprint=owner['fingerprint'], source_row_sha256=bio['row_sha256'],
                canonical_name=owner['name'], source_name=candidate['name'],
                public_evidence=alias['evidence'], alias_note=alias['note'],
                height_delta_cm=bio['height']-owner['height'], age_delta=bio['age']-owner['age'],
                country_pair=[owner['country'], bio['country']], same_foot=True,
                same_goalkeeper_class=True, runtime_identity_changed=False)


def recover(config, inventory_path, index_path, aliases_path, work):
    if not Path(index_path).exists():
        build_index(config, index_path)
    inv = read(inventory_path); index = read(index_path)
    owners = read(config['identity_state'])['identities']
    if inv['source_state_sha256'] != sha(config['identity_state']):
        raise ValueError('Canonical identity state changed')
    aliases = read(aliases_path)['aliases']
    if len({a['base_id'] for a in aliases}) != len(aliases):
        raise ValueError('Duplicate identity alias')
    aliases = {a['base_id']: a for a in aliases}
    if index['archives'] != inv['archives']:
        raise ValueError('Source index does not describe the inventory archives')
    for archive in index['archives']:
        stat = Path(archive['path']).stat()
        if stat.st_size != archive['size'] or stat.st_mtime_ns != archive['mtime_ns']:
            raise ValueError('Source archive changed')
    recovered = []
    for row in inv['players']:
        if row['status'] not in ('missing_identity', 'ambiguous_identity', 'missing_source'):
            continue
        base = row['base_id']; key = str(base)
        if base not in aliases:
            continue
        owner = owners['ef:' + key]
        if owner['fingerprint'] != row['fingerprint'] or owner['native_player_id'] != row['native_player_id']:
            raise ValueError('Roster identity differs from canonical owner')
        candidate = index['players'].get(key)
        evidence = match_alias(owner, candidate, index['biographies'].get(key), aliases[base])
        members = index['sources'].get(key, {})
        if not evidence or not all(any(n.lower().endswith(s) for n in members)
                                   for s in ('/face.fpk', '/face_bsm_alp.ftex')):
            continue
        row.update(source_player=candidate, source_members=members, source_identity_evidence=evidence,
                   identity_status='verified_explicit_alias', status='source_ready')
        recovered.append({k: row[k] for k in ('base_id', 'native_player_id', 'name', 'fingerprint')})
    inv['counts'] = dict(Counter(r['status'] for r in inv['players']))
    inv['source_recovery'] = dict(original_inventory_sha256=sha(inventory_path),
                                aliases_sha256=sha(aliases_path), recovered=recovered)
    work = Path(work).resolve()
    root = Path(__file__).resolve().parent.parent / 'local-debug'
    if not work.is_relative_to(root) or work == root:
        raise ValueError('Source recovery must use an ignored output directory')
    write(work / 'inventory.local.json', inv)
    write(work / 'config.local.json', dict(config, work_dir=str(work)))
    write(work / 'source-recovery.json', inv['source_recovery'])
    print(dict(recovered=len(recovered), runtime_identity_changed=False), flush=True)
    return inv


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True); p.add_argument('--inventory', required=True)
    p.add_argument('--index', required=True); p.add_argument('--aliases', required=True)
    p.add_argument('--work-dir', required=True)
    a = p.parse_args()
    recover(read(a.config), a.inventory, a.index, a.aliases, a.work_dir)

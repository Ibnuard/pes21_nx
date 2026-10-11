"""Inventory local face sources against an exact prepared runtime roster.

Writes local evidence only. Native slots never serve as source-face identity.
CPKs are ordered low to high priority by the supplied config, not filesystem order.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import zlib

from build_inter_miami_release_experiment import cpk_index
from build_fl26_cup_catalog import cpk_member
from pes21_player_migration import identity_fingerprint, normalize_name
from pesdb import parse_player_records


def digest(data):
    return hashlib.sha256(data).hexdigest()


def select_source(target, native, candidates):
    # Require the entire normalized name and country, never only a numeric ID.
    matches = [p for p in candidates.values()
               if normalize_name(p.name) == normalize_name(target['name'])
               and p.nationality_code == native.nationality_code]
    if len(matches) != 1:
        return None, 'missing_identity' if not matches else 'ambiguous_identity'
    return matches[0], 'verified_name_country'


def inventory(config):
    team = str(config['team_id'])
    roster_path = Path(config['rosters'])
    roster_bytes = roster_path.read_bytes()
    all_rosters = json.loads(roster_bytes)
    roster = all_rosters[team]
    owners = {}
    for squad in all_rosters.values():
        for p in squad:
            owners.setdefault(p['native_player_id'], set()).add(p.get('key', 'ef:'+str(p.get('base_id'))))
    if any(len(owners[p['native_player_id']]) != 1 for p in roster):
        raise ValueError('Native slot has conflicting BaseId owners')
    if len({p['base_id'] for p in roster}) != len(roster):
        raise ValueError('Duplicate BaseId in target squad')
    selector = Path(config['selector']).read_bytes()
    m = re.search(rb'exhibition_migration_team_'+team.encode()+rb'_players\[\] = \{(.*?)\};', selector, re.S)
    if not m or [int(n) for n in re.findall(rb'(\d+)u', m[1])] != [p['native_player_id'] for p in roster]:
        raise ValueError('Roster does not match compiled selector order')
    build = re.search(rb'PES21_PLAYER_MIGRATION_BUILD_ID "([^"]+)"', selector)[1].decode()
    native_cpk = Path(config['native_cpk'])
    _, index, base = cpk_index(native_cpk)
    member = 'common/etc/pesdb/Player.bin'
    raw = cpk_member(native_cpk, index, base, member)
    raw = zlib.decompress(raw[16:]) if raw[3:8] == b'WESYS' else raw
    native = parse_player_records(raw, 'pes21')
    pc, sources, archives = {}, {}, []
    for path_text in config['cpks']:
        path = Path(path_text)
        _, index, base = cpk_index(path)
        entry = {'path': str(path), 'size': path.stat().st_size,
                 'mtime_ns': path.stat().st_mtime_ns, 'members': len(index)}
        if member in index:
            data = cpk_member(path, index, base, member)
            data = zlib.decompress(data[16:]) if data[3:8] == b'WESYS' else data
            pc.update(parse_player_records(data, 'pes21'))
            entry['player_table_sha256'] = digest(data)
        archives.append(entry)
        for name, row in index.items():
            m = re.match(r'Asset/model/character/face/real/(\d+)/', name)
            if m:
                sources.setdefault(int(m[1]), {})[name] = {
                    'archive': str(path), 'offset': base+int(row['FileOffset']),
                    'size': int(row['FileSize']), 'extracted_size': int(row['ExtractSize'])}
    records = []
    for p in roster:
        n = native[p['native_player_id']]
        if normalize_name(n.name) != normalize_name(p['name']):
            raise ValueError('Native identity differs from roster: '+str(p['native_player_id']))
        fingerprint = identity_fingerprint({'BaseId':p['base_id'], 'Name':p['name'],
            'Country':p['country'], 'Height':p['height'], 'Foot':p['foot']})
        candidate, status = select_source(p, n, pc)
        r = dict(p, fingerprint=fingerprint, native_evidence=asdict(n), identity_status=status)
        r['native_row_sha256'] = digest(next(raw[i:i+312] for i in range(0,len(raw),312)
            if int.from_bytes(raw[i+8:i+12],'little') == p['native_player_id']))
        r['source_player'] = asdict(candidate) if candidate else None
        members = sources.get(candidate.player_id, {}) if candidate else {}
        r['source_members'] = members
        required = ('/#Win/face.fpk', '/sourceimages/#windx11/face_bsm_alp.ftex',
                    '/sourceimages/#windx11/hair_parts_bsm_alp.ftex')
        complete = all(any(n.endswith(suffix) for n in members) for suffix in required)
        r['status'] = ('preserve_accepted' if p['base_id'] in config.get('preserve_base_ids', [])
                       else 'source_ready' if candidate and complete
                       else 'missing_source' if candidate else status)
        records.append(r)
    return {'team_id':int(team), 'build_id':build, 'rosters_sha256':digest(roster_bytes),
            'selector_sha256':digest(selector), 'native_player_table_sha256':digest(raw),
            'archives':archives, 'counts':dict(Counter(r['status'] for r in records)),
            'players':records, 'hardware_accepted':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inventory(json.loads(args.config.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'build':result['build_id'], 'counts':result['counts']}))

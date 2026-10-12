"""Lock a league/team face batch to native squads and the canonical identity state.

Indexes each local FL26 archive once. Numeric native/source IDs never constitute
identity evidence. Reports and copyrighted source payloads stay in ignored paths.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
import json
from pathlib import Path
import re

from build_fl26_cup_catalog import decoded_member, index_cpk
from efootballdb_reconcile import load_identity_state
from pesdb import parse_player_records, parse_pes21_assignments
from realface_pipeline import sha
from sync_player_physique import native_rows
from pes21_player_migration import normalize_name
from prepare_loose_cpk import read_manifest
from convert_efootball10_players import read_bits
from realface_source_identity import match_base_fingerprint
import hashlib
import struct
import os
import tempfile


PLAYER = 'common/etc/pesdb/Player.bin'
ASSIGNMENTS = 'common/etc/pesdb/PlayerAssignment.bin'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Readers and interrupted reruns must see a complete previous/new report.
    payload = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    descriptor, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def selected_teams(catalog, categories, team_ids=()):
    known = {c['key']: c for c in catalog['categories']}
    if set(categories) - set(known):
        raise ValueError('Unknown league category')
    ids = set(team_ids)
    for key in categories:
        ids.update(known[key]['team_ids'])
    teams = [t for t in catalog['teams'] if t['team_id'] in ids]
    if not ids or {t['team_id'] for t in teams} != ids:
        raise ValueError('Missing selected playable teams')
    if len({t['physical_team_id'] for t in teams}) != len(teams):
        raise ValueError('Conflicting physical team slots')
    return teams


def source_index(paths, biographies=None):
    players, members, archives = {}, {}, []
    for text in paths:
        path = Path(text).resolve()
        index, offset = index_cpk(path)
        stat = path.stat()
        record = dict(path=str(path), size=stat.st_size, mtime_ns=stat.st_mtime_ns, members=len(index))
        if PLAYER in index:
            raw = decoded_member(path, index, offset, PLAYER)
            players.update(parse_player_records(raw, 'pes21'))
            record['player_table_sha256'] = hashlib.sha256(raw).hexdigest()
            if biographies is not None:
                for start in range(0, len(raw), 312):
                    row = raw[start:start + 312]
                    pid = struct.unpack_from('<I', row, 8)[0]
                    biographies[pid] = dict(country=read_bits(row,233,9), height=row[27]+100,
                        age=read_bits(row,408,6)+15, foot=read_bits(row,514,1),
                        position=players[pid].position, row_sha256=hashlib.sha256(row).hexdigest())
        for name, row in index.items():
            match = re.match(r'Asset/model/character/face/real/(\d+)/', name)
            if match:
                members.setdefault(int(match[1]), {})[name] = dict(
                    archive=str(path), offset=offset + int(row['FileOffset']),
                    size=int(row['FileSize']), extracted_size=int(row['ExtractSize']))
        archives.append(record)
    return players, members, archives


def preserved_matches(proof, owner, current_hash, old, physical):
    if proof['native_player_id'] != owner['native_player_id']:
        return False
    if proof['fingerprint'] == owner['fingerprint']:
        return True
    # Older face batches fingerprinted the roster's measured height. A later
    # physical-data sync preserves the asset identity; require the exact old
    # row -> new row checksum chain rather than silently accepting a new hash.
    return bool(old and physical and old['base_id'] == owner['base_id']
                and old['fingerprint'] == proof['fingerprint']
                and old['native_player_id'] == owner['native_player_id']
                and physical['asset_fingerprint'] == owner['fingerprint']
                and physical['row_sha256_before'] == old['native_row_sha256']
                and physical['row_sha256_after'] == current_hash)


def inventory(config):
    runtime = Path(config['runtime_base'])
    cpk = runtime / 'LooseCpk/dt200_mobile_all.cpk'
    manifest = read_manifest(runtime)
    entry = next(r for r in manifest['files'] if r['name'] == cpk.name)
    if sha(cpk) != entry['sha256'] or cpk.stat().st_size != entry['size']:
        raise ValueError('Native CPK differs from manifest')
    catalog = read(config['catalog'])
    teams = selected_teams(catalog, config.get('categories', []), config.get('team_ids', []))
    index, offset = index_cpk(cpk)
    raw = decoded_member(cpk, index, offset, PLAYER)
    parsed = parse_player_records(raw, 'pes21')
    rows, native = native_rows(raw)
    identities, owners = load_identity_state(read(config['identity_state']), native)
    owners = {p['native_player_id']: p for p in identities.values() if p['status'] == 'active'}
    assignments = parse_pes21_assignments(decoded_member(cpk, index, offset, ASSIGNMENTS))
    selector = Path(config['selector']).read_text(encoding='utf-8')
    build = re.search(r'PES21_PLAYER_MIGRATION_BUILD_ID "([^"]+)"', selector)
    if not build or build[1] != manifest['build_id']:
        raise ValueError('Compiled selector/runtime build pairing differs')
    memberships = defaultdict(list)
    for team in teams:
        tid = team['team_id']
        squad = [p.player_id for p in assignments[team['physical_team_id']]]
        match = re.search(r'exhibition_migration_team_' + str(tid) + r'_players\[\] = \{(.*?)\};', selector, re.S)
        if not match or squad != [int(n) for n in re.findall(r'(\d+)u', match[1])]:
            raise ValueError('Native/compiled roster order mismatch: ' + str(tid))
        if not 11 <= len(squad) <= 40 or len(squad) != len(set(squad)):
            raise ValueError('Invalid native squad')
        for pid in squad:
            memberships[pid].append(tid)
    biographies = {}
    pc, sources, archives = source_index(config['cpks'], biographies)
    by_identity = defaultdict(list)
    for source in pc.values():
        by_identity[(normalize_name(source.name), source.nationality_code)].append(source)
    preserved = {}
    previous = {}
    physical = {}
    if config.get('preserved_verification'):
        proof = read(config['preserved_verification'])
        if sha(config['preserved_pak']) != proof['pak_sha256']:
            raise ValueError('Preserved face PAK checksum changed')
        preserved = {p['base_id']: p for p in proof['players'] if p['status'] in
                     ('candidate_pending_device', 'accepted_pilot_included')}
        previous = {p['base_id']: p for p in read(config['preserved_inventory'])['players']}
        physical = {p['base_id']: p for p in read(config['physique_report'])['players']}
    result = []
    for pid, tids in sorted(memberships.items()):
        owner = owners.get(pid)
        base = owner.get('base_id') if owner else None
        record = dict(native_player_id=pid, base_id=base, team_ids=tids, name=parsed[pid].name,
                      status='held_unverified_identity', native_row_sha256=native[pid]['native_sha256'])
        if not owner or not base or not owner.get('fingerprint'):
            result.append(record)
            continue
        if normalize_name(owner['name']) != normalize_name(parsed[pid].name):
            if normalize_name(parsed[pid].name) not in owner.get('aliases', []):
                raise ValueError('Native identity name changed')
        record.update(name=owner['name'], fingerprint=owner['fingerprint'],
                      native_evidence=asdict(parsed[pid]), registry=owner.get('registry', {}))
        if base in preserved:
            p = preserved[base]
            if not preserved_matches(p, owner, native[pid]['native_sha256'], previous.get(base), physical.get(base)):
                raise ValueError('Preserved face ownership differs')
            record['status'] = 'preserve_existing'
            result.append(record)
            continue
        matches = by_identity.get((normalize_name(owner['name']), parsed[pid].nationality_code), [])
        candidate = matches[0] if len(matches) == 1 else None
        direct = pc.get(base)
        evidence = match_base_fingerprint(owner, direct, biographies.get(base)) if direct else None
        # Explicit BaseId/biography evidence also resolves same-name players.
        if evidence:
            candidate = direct
            record['source_identity_evidence'] = evidence
        identity = 'verified_name_country' if candidate else 'ambiguous_identity' if matches else 'missing_identity'
        if evidence:
            identity = 'verified_base_fingerprint'
        record['identity_status'] = identity
        record['source_player'] = asdict(candidate) if candidate else None
        record['source_members'] = sources.get(candidate.player_id, {}) if candidate else {}
        # Bald heads need no hair atlas; custom hairstyles can name it
        # differently. Actual material dependencies are checked in prepare.
        required = ('/face.fpk', '/face_bsm_alp.ftex')
        complete = all(any(n.lower().endswith(s) for n in record['source_members']) for s in required)
        record['status'] = 'source_ready' if complete else 'missing_source' if candidate else identity
        result.append(record)
    bases = [p['base_id'] for p in result if p['base_id']]
    if len(bases) != len(set(bases)):
        raise ValueError('Duplicate BaseId ownership')
    return dict(schema_version=1, build_id=manifest['build_id'],
                source_state_sha256=sha(config['identity_state']), source_cpk_sha256=sha(cpk),
                selector_sha256=sha(config['selector']), catalog_sha256=sha(config['catalog']),
                teams=[dict(team_id=t['team_id'], name=t['display_name'], category=t['category']) for t in teams],
                archives=archives, players=result, counts=dict(Counter(p['status'] for p in result)),
                hardware_accepted=False)

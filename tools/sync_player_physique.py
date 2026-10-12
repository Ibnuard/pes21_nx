#!/usr/bin/env python3
"""Sync native height/weight from a frozen API snapshot into a local candidate.

No network access, roster imports, asset reassignment or runtime scaling hooks.
The only writable Player.bin bits are height [216,224) and weight [256,263).
Appearance proportions are audited, never guessed from height/weight.
"""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from build_fl26_cup_catalog import cpk_member, decoded_member, index_cpk
from convert_efootball10_players import encode_pes21_wesys, read_bits
from efootballdb_reconcile import canonical_biography_drift, load_identity_state
from pes21_player_migration import identity_fingerprint, name_tokens, normalize_name
from pesdb import parse_pes21_assignments, parse_player_records, split_records
from prepare_loose_cpk import read_manifest, write_manifest
from sync_efootballdb_rosters import (
    API, GENERATOR, PLAYER_API, cached_team, local_output, playable_teams, read_json,
)

ROOT = Path(__file__).resolve().parents[1]
PLAYER_MEMBER = 'common/etc/pesdb/Player.bin'
APPEARANCE_MEMBER = 'common/etc/appearance/PlayerAppearance.bin'
ROW_BYTES = 312
BODY_BITS = {
    'neck_length': 32, 'neck_size': 36, 'shoulder_height': 40,
    'shoulder_width': 44, 'chest': 48, 'waist': 52, 'arm_size': 56,
    'arm_length': 60, 'thigh_size': 64, 'calf_size': 68, 'leg_length': 72,
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def integer(value: object, label: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{label} must be an integer in {low}..{high}')
    return value


def physical_fields(player: dict, registered_card: int | None = None) -> dict:
    """Units are the API's integer centimetres/kilograms, never metres/BMI."""
    base = integer(player.get('base_pes_id'), 'BaseId', 1, 0xffffffff)
    card = integer(player.get('pes_id'), 'card ID', 1, (1 << 53) - 1)
    canonical = card == base and player.get('fake_version') == 0
    # Some established identities use a licensed/unlicensed base-card alias.
    # Only the exact already-registered source card is eligible, never an
    # arbitrary special card or a guessed subtraction from a numeric ID.
    registered_base = (registered_card is not None and card == registered_card
                       and card != base and card - base in (1 << 23, 1 << 24))
    if player.get('card_type') != 0 or not (canonical or registered_base):
        raise ValueError(f'Canonical base profile required for {base}')
    national = player.get('nationality_a')
    country = national.get('country_id') if isinstance(national, dict) else national
    name = player.get('player_name')
    if not isinstance(name, str) or not normalize_name(name):
        raise ValueError(f'Missing player name for {base}')
    return {
        'base_id': base, 'name': name,
        'country': integer(country, 'country', 1, 511),
        'foot': integer(player.get('strong_foot'), 'foot', 0, 1),
        'age': integer(player.get('age'), 'age', 15, 78),
        'height_cm': integer(player.get('height'), 'height_cm', 100, 230),
        'weight_kg': integer(player.get('weight'), 'weight_kg', 30, 157),
    }


def native_rows(raw: bytes) -> tuple[dict, dict]:
    parsed = parse_player_records(raw, 'pes21')  # rejects duplicate/zero IDs
    if not parsed:
        raise ValueError('Player table is empty')
    rows, identities = {}, {}
    for offset in range(0, len(raw), ROW_BYTES):
        row = raw[offset:offset + ROW_BYTES]
        native = struct.unpack_from('<I', row, 8)[0]
        rows[native] = (offset, row)
        identities[native] = {
            'native_player_id': native, 'name': parsed[native].name,
            'country': read_bits(row, 233, 9), 'foot': read_bits(row, 514, 1),
            'height': row[27] + 100, 'native_sha256': digest(row),
        }
    return rows, identities


def physique_rows(raw: bytes) -> dict:
    result = {}
    for row in split_records(raw, 60, 'PlayerAppearance.bin'):
        native = struct.unpack_from('<I', row)[0]
        if not native or native in result:
            raise ValueError('Duplicate/zero native appearance ID')
        # 0..14 encode -7..7; 15 is the native default sentinel, not +8.
        result[native] = {
            field: None if read_bits(row, bit, 4) == 15 else read_bits(row, bit, 4) - 7
            for field, bit in BODY_BITS.items()
        }
    return result


def same_name(left: str, right: str, aliases: list[str] = ()) -> bool:
    tokens = name_tokens(left)
    return (normalize_name(right) in {normalize_name(left), *aliases}
            or (len(tokens) >= 2 and sorted(tokens) == sorted(name_tokens(right))))


def source_fields_for_owner(player: dict, owner: dict) -> dict:
    try:
        return physical_fields(player, owner.get('registry', {}).get('source_card_id'))
    except ValueError as original:
        # A known base-card alias can also be identified by an exact complete
        # asset fingerprint, including height. This cannot authorize a different
        # person, a height change, or a special-card variation.
        candidate = physical_fields(player, player.get('pes_id'))
        fingerprint = identity_fingerprint({
            'BaseId': candidate['base_id'], 'Name': candidate['name'],
            'Country': candidate['country'], 'Foot': candidate['foot'],
            'Height': candidate['height_cm']})
        if fingerprint != owner['fingerprint']:
            raise original
        return candidate


def verify_request(request: dict, identities: dict, native: dict) -> tuple[dict, dict, dict | None]:
    base = integer(request['player'].get('base_pes_id'), 'BaseId', 1, 0xffffffff)
    owner = identities.get(f'ef:{base}')
    if not owner or owner['status'] != 'active' or not owner.get('fingerprint'):
        raise ValueError(f'Expected one active fingerprinted identity: {base}')
    native_id = owner['native_player_id']
    registry = owner.get('registry', {})
    promoted = (registry.get('source_key') == f"fl26:{registry.get('fl26_player_id')}"
                and registry.get('source_key') in owner.get('previous_keys', [])
                and owner.get('asset_fingerprint') == owner['fingerprint'])
    if ((registry.get('ef_base_id') != base and not promoted)
            or registry.get('native_player_id') != native_id
            or registry.get('fingerprint', owner['fingerprint']) != owner['fingerprint']):
        raise ValueError(f'Registry ownership/fingerprint differs: {base}')
    source = source_fields_for_owner(request['player'], owner)
    current = native[native_id]
    if (not same_name(owner['name'], current['name'], owner.get('aliases', []))
            or current['country'] != owner['country'] or current['foot'] != owner['foot']):
        raise ValueError(f'Native biography differs from identity state: {base}')
    reconciliation = None
    if (not same_name(owner['name'], source['name'], owner.get('aliases', []))
            or source['country'] != owner['country'] or source['foot'] != owner['foot']):
        # Reuse the roster importer's conservative, independently fetched
        # canonical-profile rule. It permits one biography correction only,
        # with full name, BaseId, age, keeper/outfield type and other fields
        # agreeing. The actual foot/country fields are still never written.
        if (request['source']['kind'] == 'canonical_profile'
                and owner.get('position') in range(13)
                and request['player'].get('main_position') in range(13)):
            reconciliation = canonical_biography_drift(owner, dict(
                source, height=source['height_cm'], position=request['player'].get('main_position', -1)))
        if not reconciliation:
            raise ValueError(f'BaseId biography mismatch: {base}')
    if not 0 <= source['age'] - owner['age'] <= 3:
        raise ValueError(f'Unexpected API age progression: {base}')
    if abs(current['height'] - source['height_cm']) > 10:
        review = request.get('height_review', {})
        expected = {'base_id': base, 'native_player_id': native_id,
                    'asset_fingerprint': owner['fingerprint'], 'native_row_sha256': current['native_sha256'],
                    'api_sha256': request['source']['sha256'],
                    'height_before_cm': current['height'], 'height_after_cm': source['height_cm']}
        if not review.get('reason') or any(review.get(k) != v for k, v in expected.items()):
            raise ValueError(f'Height correction over 10 cm requires a separate identity audit: {base}')
        reconciliation = {'field': 'height', 'review': review}
    return source, owner, reconciliation


def sync_records(raw: bytes, appearance: bytes, state: dict,
                 requests: list[dict], *, hold_unverified: bool = False) -> tuple[bytes, dict, dict]:
    """Validate the entire identity state, then patch selected canonical players.

    Each request contains a canonical API player and its frozen provenance.
    The returned state must accompany future imports: its row hashes are updated,
    while existing asset identity fingerprints and ownership stay unchanged.
    """
    rows, native = native_rows(raw)
    identities, _owners = load_identity_state(state, native)
    bodies = physique_rows(appearance)
    updated = copy.deepcopy(state)
    result = bytearray(raw)
    reports, held, seen = [], [], set()
    if not requests:
        raise ValueError('No players selected')
    for request in requests:
        base = integer(request['player'].get('base_pes_id'), 'BaseId', 1, 0xffffffff)
        if base in seen:
            raise ValueError(f'Duplicate BaseId in physical sync: {base}')
        seen.add(base)
        key = f'ef:{base}'
        try:
            source, owner, reconciliation = verify_request(request, identities, native)
        except ValueError as error:
            if not hold_unverified:
                raise
            held.append({'base_id': base, 'native_player_id': identities.get(key, {}).get('native_player_id'),
                         'name': identities.get(key, {}).get('name'), 'reason': str(error),
                         'source': request['source']})
            continue
        native_id = owner['native_player_id']
        offset, row = rows[native_id]
        before = {'height_cm': row[27] + 100, 'weight_kg': (row[32] & 127) + 30}
        after = {field: source[field] for field in before}
        result[offset + 27] = after['height_cm'] - 100
        result[offset + 32] = (row[32] & 0x80) | (after['weight_kg'] - 30)
        patched = bytes(result[offset:offset + ROW_BYTES])
        changed = [i for i, (a, b) in enumerate(zip(row, patched)) if a != b]
        if set(changed) - {27, 32} or ((row[32] ^ patched[32]) & 0x80):
            raise RuntimeError('Physical patch changed unrelated bits')
        person = updated['identities'][key]
        person['native_sha256'] = digest(patched)
        person['height'] = after['height_cm']
        person['weight'] = after['weight_kg']
        report = {
            'base_id': base, 'native_player_id': native_id, 'name': owner['name'],
            'asset_fingerprint': owner['fingerprint'], 'before': before, 'after': after,
            'changed': bool(changed), 'changed_row_bytes': changed,
            'row_sha256_before': digest(row), 'row_sha256_after': digest(patched),
            'source': request['source'],
            'biography_reconciliation': reconciliation,
            'appearance': 'preserved' if native_id in bodies else 'native_default',
            'body_adjustments': bodies.get(native_id),
        }
        if changed:
            person['physical_sync'] = {
                'source': request['source'], 'before': before, 'after': after,
                'row_sha256_before': digest(row), 'row_sha256_after': digest(patched),
                'source_biography_fingerprint': identity_fingerprint({
                    'BaseId': base, 'Name': source['name'], 'Country': source['country'],
                    'Foot': source['foot'], 'Height': after['height_cm']}),
                'asset_fingerprint_preserved': owner['fingerprint'],
            }
        reports.append(report)
    # Future roster syncs must accept the candidate state without reallocation.
    load_identity_state(updated, native_rows(bytes(result))[1])
    return bytes(result), updated, {
        'schema_version': 1, 'generator': 'tools/sync_player_physique.py',
        'players': reports, 'player_count': len(rows), 'selected_players': len(reports),
        'held_players': held,
        'changed_players': sum(p['changed'] for p in reports),
        'changed_bytes': sum(len(p['changed_row_bytes']) for p in reports),
        'height_changes': sum(p['before']['height_cm'] != p['after']['height_cm'] for p in reports),
        'weight_changes': sum(p['before']['weight_kg'] != p['after']['weight_kg'] for p in reports),
        'input_player_sha256': digest(raw), 'output_player_sha256': digest(bytes(result)),
        'appearance_sha256': digest(appearance),
        'physique_policy': 'preserve native body/head proportions and skin; API provides height/weight only',
        'hardware_tested': False,
    }


def load_requests(collection: Path, profiles: Path | None, state: dict,
                  assignments: dict, team_ids: list[int]) -> tuple[list[dict], dict]:
    manifest = read_json(collection / 'collection.json')
    catalog_raw = (collection / 'catalog.json').read_bytes()
    if (manifest.get('generator') != GENERATOR or manifest.get('source') != API
            or digest(catalog_raw) != manifest.get('catalog_sha256')):
        raise ValueError('Collection provenance mismatch')
    catalog = playable_teams(json.loads(catalog_raw))
    if manifest.get('snapshot_id') != state.get('collection_snapshot_id'):
        raise ValueError('Use the API collection paired with this identity state')
    profile_manifest = read_json(profiles / 'profiles.json') if profiles else None
    if profile_manifest and (profile_manifest.get('generator') != GENERATOR
            or profile_manifest.get('source') != PLAYER_API
            or profile_manifest.get('collection_snapshot_id') != manifest['snapshot_id']):
        raise ValueError('Profile collection provenance mismatch')
    requests, teams = {}, []
    for team_id in sorted(set(team_ids)):
        if team_id not in catalog or str(team_id) not in manifest['teams']:
            raise ValueError(f'Team unavailable in frozen collection: {team_id}')
        entry = manifest['teams'][str(team_id)]
        if entry.get('problems') or str(team_id) in manifest.get('errors', {}):
            raise ValueError(f'Team API response was not validated: {team_id}')
        team = json.loads(cached_team(collection, team_id, entry))['data']
        if team.get('pes_id') != team_id:
            raise ValueError('API response belongs to another team')
        physical_team = int(catalog[team_id]['physical_team_id'])
        native_ids, bases = [], set()
        for assignment in team['player_assignments']:
            player = assignment['player']
            base = integer(player.get('base_pes_id'), 'BaseId', 1, 0xffffffff)
            if base in bases:
                raise ValueError('Duplicate team BaseId')
            bases.add(base)
            owner = state['identities'].get(f'ef:{base}')
            if not owner or owner['status'] != 'active':
                raise ValueError(f'Team has an unverified identity: {base}')
            native_ids.append(owner['native_player_id'])
            source = {'kind': 'team_base_profile', 'snapshot_id': manifest['snapshot_id'],
                      'url': entry['url'], 'fetched_at': entry['fetched_at'], 'sha256': entry['sha256']}
            if profile_manifest and str(base) in profile_manifest['players']:
                profile = profile_manifest['players'][str(base)]
                player = json.loads(cached_team(profiles, base, profile))['data']
                source = {'kind': 'canonical_profile', 'snapshot_id': profile_manifest['snapshot_id'],
                          'url': profile['url'], 'fetched_at': profile['fetched_at'], 'sha256': profile['sha256']}
            fields = physical_fields(player)
            if fields['base_id'] != base:
                raise ValueError('Canonical profile BaseId mismatch')
            if base in requests and physical_fields(requests[base]['player']) != fields:
                raise ValueError(f'Conflicting API physical data across teams: {base}')
            requests.setdefault(base, {'player': player, 'source': source})
        actual = [row.player_id for row in assignments.get(physical_team, [])]
        if len(actual) != len(set(actual)) or set(actual) != set(native_ids):
            raise ValueError(f'Native/API roster differs for team {team_id}; reconcile memberships first')
        teams.append({'team_id': team_id, 'physical_team_id': physical_team,
                      'name': entry['name'], 'players': len(bases)})
    return [requests[base] for base in sorted(requests)], {
        'teams': teams, 'collection_snapshot_id': manifest['snapshot_id'],
        'collection_manifest_sha256': digest((collection / 'collection.json').read_bytes()),
        'profiles_manifest_sha256': digest((profiles / 'profiles.json').read_bytes()) if profiles else None,
    }


def load_playable_requests(collection: Path, profiles: Path | None, state: dict,
                           assignments: dict, catalog_path: Path) -> tuple[list[dict], dict]:
    """Walk the current native playable roster, not the API's proposed transfers.

    Missing identities/profiles are explicit held entries. Corrupt provenance or
    invalid native roster structure still aborts the entire candidate.
    """
    manifest = read_json(collection / 'collection.json')
    frozen_catalog = (collection / 'catalog.json').read_bytes()
    if (manifest.get('generator') != GENERATOR or manifest.get('source') != API
            or digest(frozen_catalog) != manifest.get('catalog_sha256')
            or manifest.get('snapshot_id') != state.get('collection_snapshot_id')):
        raise ValueError('Collection provenance differs from the identity state')
    catalog_raw = catalog_path.read_bytes()
    catalog = playable_teams(json.loads(catalog_raw))
    # A later presentation catalog may rename clubs, but it cannot silently
    # change the native slot identity used for this frozen update.
    frozen_slots = playable_teams(json.loads(frozen_catalog))
    for team, slot in catalog.items():
        if team not in frozen_slots or slot['physical_team_id'] != frozen_slots[team]['physical_team_id']:
            raise ValueError(f'Playable catalog/native team mapping changed: {team}')
    owners = {}
    for person in state['identities'].values():
        native = person['native_player_id']
        if native in owners:
            raise ValueError('Duplicate native owner in canonical state')
        owners[native] = person
    members = collections.defaultdict(list)
    teams = []
    for team, slot in sorted(catalog.items()):
        roster = assignments.get(slot['physical_team_id'], [])
        ids = [r.player_id for r in roster]
        if not 11 <= len(ids) <= 40 or len(ids) != len(set(ids)):
            raise ValueError(f'Invalid playable native roster: {team}')
        teams.append({'team_id': team, 'physical_team_id': slot['physical_team_id'],
                      'players': len(ids)})
        for native in ids:
            members[native].append(team)
    bases = {owners[native]['base_id'] for native in members if native in owners} - {None}
    observations = collections.defaultdict(list)
    for key, entry in sorted(manifest['teams'].items(), key=lambda kv: int(kv[0])):
        if entry.get('problems') or key in manifest.get('errors', {}):
            continue
        team = json.loads(cached_team(collection, int(key), entry))['data']
        if team.get('pes_id') != int(key):
            raise ValueError('API response belongs to another team')
        source = {'kind': 'team_base_profile', 'snapshot_id': manifest['snapshot_id'],
                  'url': entry['url'], 'fetched_at': entry['fetched_at'], 'sha256': entry['sha256']}
        for assignment in team['player_assignments']:
            player = assignment['player']
            if player.get('base_pes_id') in bases:
                observations[player['base_pes_id']].append({'player': player, 'source': source})
    profile_manifest = read_json(profiles / 'profiles.json') if profiles else None
    if profile_manifest and (profile_manifest.get('generator') != GENERATOR
            or profile_manifest.get('source') != PLAYER_API
            or profile_manifest.get('collection_snapshot_id') != manifest['snapshot_id']):
        raise ValueError('Profile collection provenance mismatch')
    canonical = {}
    for base in sorted(bases):
        if profile_manifest and str(base) in profile_manifest['players']:
            entry = profile_manifest['players'][str(base)]
            player = json.loads(cached_team(profiles, base, entry))['data']
            if player.get('base_pes_id') != base or player.get('pes_id') != base:
                raise ValueError('Canonical profile BaseId mismatch')
            canonical[base] = {'player': player, 'source': {
                'kind': 'canonical_profile', 'snapshot_id': profile_manifest['snapshot_id'],
                'url': entry['url'], 'fetched_at': entry['fetched_at'], 'sha256': entry['sha256']}}
    requests, held = [], []
    for native, team_ids in sorted(members.items()):
        owner = owners.get(native)
        base = owner.get('base_id') if owner else None
        reason = None
        if not owner or owner.get('status') != 'active':
            reason = 'no_active_registered_identity'
        elif base is None:
            reason = 'no_verified_api_BaseId'
        elif base in canonical:
            requests.append(canonical[base])
        else:
            options = observations.get(base, [])
            eligible = []
            for request in options:
                try:
                    fields = source_fields_for_owner(request['player'], owner)
                except ValueError:
                    continue
                eligible.append((request, fields))
            canonical_options = [(r, f) for r, f in eligible if r['player']['pes_id'] == base]
            eligible = canonical_options or eligible
            if not eligible:
                reason = 'no_frozen_api_profile' if not options else 'only_unverified_card_alias'
            elif any(fields != eligible[0][1] for _request, fields in eligible[1:]):
                reason = 'conflicting_frozen_api_observations'
            else:
                requests.append(eligible[0][0])
        if reason:
            held.append({'native_player_id': native, 'base_id': base,
                         'name': owner.get('name') if owner else None,
                         'team_ids': team_ids, 'reason': reason})
    return sorted(requests, key=lambda r: r['player']['base_pes_id']), {
        'scope': 'all_current_playable_players', 'teams': teams,
        'playable_players': len(members), 'playable_roster_slots': sum(map(len, members.values())),
        'unavailable_players': held, 'catalog_sha256': digest(catalog_raw),
        'collection_snapshot_id': manifest['snapshot_id'],
        'collection_manifest_sha256': digest((collection / 'collection.json').read_bytes()),
        'profiles_manifest_sha256': digest((profiles / 'profiles.json').read_bytes()) if profiles else None,
    }


def compare_archive(before: Path, after: Path) -> tuple[int, list[str]]:
    old, old_base = index_cpk(before)
    new, new_base = index_cpk(after)
    if list(old) != list(new):
        raise ValueError('CPK member order/count changed')
    changed = []
    with before.open('rb') as a, after.open('rb') as b:
        for name in old:
            for key in set(old[name]) | set(new[name]):
                if key not in ('FileOffset', 'FileSize', 'ExtractSize') and old[name].get(key) != new[name].get(key):
                    raise ValueError(f'CPK member metadata changed: {name}')
            a.seek(old_base + int(old[name]['FileOffset']))
            b.seek(new_base + int(new[name]['FileOffset']))
            if a.read(int(old[name]['FileSize'])) != b.read(int(new[name]['FileSize'])):
                changed.append(name)
    return len(old), changed


def save_json(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write('\n')


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['audit', 'apply'])
    p.add_argument('--collection', type=Path, required=True)
    p.add_argument('--profiles', type=Path)
    p.add_argument('--identity-state', type=Path, required=True)
    p.add_argument('--runtime-base', type=Path, required=True,
                   help='Accepted runtime/update with LooseCpk/manifest.txt and dt200')
    scope = p.add_mutually_exclusive_group(required=True)
    scope.add_argument('--team-id', type=int, action='append')
    scope.add_argument('--all-playable', action='store_true')
    p.add_argument('--catalog', type=Path, help='Required with --all-playable: current accepted selector catalog')
    p.add_argument('--height-reviews', type=Path,
                   help='Optional exact-row and exact-source reviews for corrections over 10 cm')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.all_playable != bool(a.catalog):
        p.error('--all-playable requires --catalog; do not use --catalog with --team-id')
    output = local_output(a.output)
    if output.exists():
        raise ValueError('Output must be a new local directory')
    manifest = read_manifest(a.runtime_base)
    cpk = a.runtime_base / 'LooseCpk/dt200_mobile_all.cpk'
    cpk_sha = digest(cpk.read_bytes())
    entry = next(row for row in manifest['files'] if row['name'] == cpk.name)
    if entry['sha256'] != cpk_sha or entry['size'] != cpk.stat().st_size:
        raise ValueError('Baseline dt200 differs from its runtime manifest')
    state = read_json(a.identity_state)
    index, offset = index_cpk(cpk)
    raw = decoded_member(cpk, index, offset, PLAYER_MEMBER)
    if len(raw) != 43074 * ROW_BYTES:
        raise ValueError('Expected the fixed 43,074 native player rows')
    appearance = decoded_member(cpk, index, offset, APPEARANCE_MEMBER)
    assignments = parse_pes21_assignments(decoded_member(
        cpk, index, offset, 'common/etc/pesdb/PlayerAssignment.bin'))
    if a.all_playable:
        requests, provenance = load_playable_requests(a.collection, a.profiles, state, assignments, a.catalog)
    else:
        requests, provenance = load_requests(a.collection, a.profiles, state, assignments, a.team_id)
    if a.height_reviews:
        reviews = read_json(a.height_reviews)
        rows = reviews.get('players', [])
        if (reviews.get('schema_version') != 1 or not rows
                or len({r['base_id'] for r in rows}) != len(rows)):
            raise ValueError('Expected unique version 1 height reviews')
        by_base = {r['base_id']: r for r in rows}
        for request in requests:
            if request['player']['base_pes_id'] in by_base:
                request['height_review'] = by_base[request['player']['base_pes_id']]
        provenance['height_reviews_sha256'] = digest(a.height_reviews.read_bytes())
    patched, updated, report = sync_records(raw, appearance, state, requests, hold_unverified=a.all_playable)
    repeated, repeated_state, repeated_report = sync_records(
        patched, appearance, updated, requests, hold_unverified=a.all_playable)
    if repeated != patched or repeated_state != updated or repeated_report['changed_players']:
        raise ValueError('Physical synchronization is not idempotent')
    report.update(provenance, mode=a.mode, runtime_build_id=manifest['build_id'],
                  source_cpk_sha256=cpk_sha, source_identity_sha256=digest(a.identity_state.read_bytes()),
                  source_manifest_sha256=digest((a.runtime_base / 'LooseCpk/manifest.txt').read_bytes()),
                  active_runtime_modified=False, idempotent=True)
    report['held_players'].extend(report.pop('unavailable_players', []))
    report['held_players_count'] = len(report['held_players'])
    if a.all_playable and report['selected_players'] + report['held_players_count'] != report['playable_players']:
        raise ValueError('Full playable coverage accounting failed')
    output.mkdir(parents=True)
    if a.mode == 'apply':
        destination = output / 'update/LooseCpk/dt200_mobile_all.cpk'
        destination.parent.mkdir(parents=True)
        if patched == raw:
            report['package'] = 'unnecessary_all_selected_metrics_already_match'
        else:
            with tempfile.TemporaryDirectory(prefix='physique-', dir=output) as temporary:
                table = Path(temporary) / 'Player.bin'
                original = cpk_member(cpk, index, offset, PLAYER_MEMBER)
                table.write_bytes(encode_pes21_wesys(patched) if original[3:8] == b'WESYS' else patched)
                subprocess.run([sys.executable, str(ROOT / 'tools/repack_cpk_members.py'),
                                str(cpk), str(destination), '--expect-members', str(len(index)),
                                '--replace', PLAYER_MEMBER + '=' + str(table)],
                               check=True, capture_output=True, text=True)
            count, changed = compare_archive(cpk, destination)
            check_index, check_offset = index_cpk(destination)
            if (changed != [PLAYER_MEMBER]
                    or decoded_member(destination, check_index, check_offset, PLAYER_MEMBER) != patched):
                raise ValueError('Candidate archive failed full member/decoded table verification')
            entry.update(size=destination.stat().st_size, sha256=digest(destination.read_bytes()))
            write_manifest(output / 'update', manifest)
            report.update(cpk_members_compared=count, changed_members=changed,
                          output_cpk_sha256=entry['sha256'], output_cpk_bytes=entry['size'])
            report['package'] = 'dt200_and_manifest_only; same roster/NRO pairing'
        # Keep the producer marker for load_local_identities compatibility. Only
        # native record hashes/physical biography change, not asset fingerprints.
        updated['build_id'] = manifest['build_id']
        save_json(output / 'identity-state.json', updated)
    save_json(output / 'physical-sync-report.json', report)
    print(json.dumps({key: report[key] for key in (
        'mode', 'selected_players', 'held_players_count', 'changed_players', 'height_changes', 'weight_changes', 'changed_bytes')},
        sort_keys=True))


if __name__ == '__main__':
    main()

"""Synthetic records only; no copyrighted game fixtures are required."""
import copy
import gzip
import json
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from convert_efootball10_players import read_bits, write_bits
from pes21_player_migration import identity_fingerprint
from pesdb import PlayerAssignment
from sync_player_physique import (
    API, GENERATOR, PLAYER_API, digest, load_playable_requests, load_requests, native_rows,
    physical_fields, physique_rows, sync_records,
)


def fixture():
    rows = []
    for native in (10, 20, 30):
        row = bytearray((i * 17 + native) % 256 for i in range(312))
        struct.pack_into('<I', row, 8, native)
        write_bits(row, 216, 8, 80)
        write_bits(row, 256, 7, 42)
        write_bits(row, 263, 1, 1)  # unrelated bit sharing the weight byte
        write_bits(row, 233, 9, 236)
        write_bits(row, 514, 1, 1)
        row[251:] = b'Synthetic Player'.ljust(61, b'\0')
        rows.append(bytes(row))
    fp = identity_fingerprint(dict(BaseId=99, Name='Synthetic Player', Country=236, Height=180, Foot=1))
    state = {'schema_version': 1, 'generator': 'tools/stage_efootballdb_update.py',
             'collection_snapshot_id': 'snapshot', 'build_id': '0123456789abcdef',
             'identities': {'ef:99': {
                 'key': 'ef:99', 'base_id': 99, 'native_player_id': 20, 'status': 'active',
                 'name': 'Synthetic Player', 'aliases': ['syntheticplayer'],
                 'age': 22, 'height': 180, 'country': 236, 'foot': 1,
                 'fingerprint': fp, 'native_sha256': digest(rows[1]),
                 'registry': {'ef_base_id': 99, 'native_player_id': 20,
                              'fingerprint': fp, 'face_owner_id': 20, 'portrait_asset_id': 20},
             }}}
    appearance = b''.join(struct.pack('<I', i) + bytes([0x77]) * 56 for i in (10, 20, 30))
    player = {'base_pes_id': 99, 'pes_id': 99, 'card_type': 0, 'fake_version': 0,
              'player_name': 'Synthetic Player', 'nationality_a': {'country_id': 236},
              'strong_foot': 1, 'height': 182, 'weight': 79, 'age': 23}
    request = {'player': player, 'source': {'kind': 'canonical_profile', 'sha256': 'local-test',
                                          'snapshot_id': 'snapshot'}}
    return b''.join(rows), appearance, state, [request]


def test_changes_physical_bits_only_and_keeps_identity_assets_and_neighbours():
    raw, appearance, state, requests = fixture()
    old_state = copy.deepcopy(state)
    out, updated, report = sync_records(raw, appearance, state, requests)
    changes = [i for i, (a, b) in enumerate(zip(raw, out)) if a != b]
    assert changes == [312 + 27, 312 + 32]
    assert out[312 + 32] & 0x80  # adjacent weight bit survives
    assert out[312 + 27] + 100 == 182
    assert (out[312 + 32] & 127) + 30 == 79
    assert state == old_state
    assert updated['identities']['ef:99']['registry'] == state['identities']['ef:99']['registry']
    assert updated['identities']['ef:99']['fingerprint'] == state['identities']['ef:99']['fingerprint']
    assert updated['identities']['ef:99']['native_sha256'] == digest(out[312:624])
    assert set(native_rows(out)[0]) == set(native_rows(raw)[0])
    assert report['changed_players'] == 1 and report['changed_bytes'] == 2
    assert report['appearance_sha256'] == digest(appearance)
    assert report['players'][0]['body_adjustments'] == dict.fromkeys(physique_rows(appearance)[20], 0)


def test_reapply_uses_updated_state_and_is_a_no_op():
    raw, appearance, state, requests = fixture()
    once, new_state, _ = sync_records(raw, appearance, state, requests)
    twice, second_state, report = sync_records(once, appearance, new_state, requests)
    assert twice == once and second_state == new_state
    assert report['changed_bytes'] == 0 and report['changed_players'] == 0
    with pytest.raises(ValueError, match='record changed'):
        sync_records(once, appearance, state, requests)


def test_missing_appearance_retains_native_default_without_inventing_proportions():
    raw, appearance, state, requests = fixture()
    _, _, report = sync_records(raw, appearance[:60] + appearance[120:], state, requests)
    assert report['players'][0]['appearance'] == 'native_default'
    assert report['players'][0]['body_adjustments'] is None


def test_appearance_default_sentinel_is_not_positive_eight():
    assert physique_rows(struct.pack('<I', 20) + b'\xff' * 56)[20] == dict.fromkeys(
        physique_rows(struct.pack('<I', 20) + b'\x77' * 56)[20], None)


@pytest.mark.parametrize('field,value', [
    ('height', 1.82), ('height', '182 cm'), ('height', None), ('height', True),
    ('height', 99), ('height', 231), ('weight', 0), ('weight', 158),
    ('weight', '79'), ('weight', False), ('strong_foot', 2), ('base_pes_id', True),
])
def test_invalid_units_and_values_are_never_coerced_or_clamped(field, value):
    _, _, _, requests = fixture()
    requests[0]['player'][field] = value
    with pytest.raises(ValueError):
        physical_fields(requests[0]['player'])


@pytest.mark.parametrize('height,weight', [(100, 30), (230, 157), (182, 79)])
def test_supported_units(height, weight):
    _, _, _, requests = fixture()
    requests[0]['player'].update(height=height, weight=weight)
    fields = physical_fields(requests[0]['player'])
    assert (fields['height_cm'], fields['weight_kg']) == (height, weight)


@pytest.mark.parametrize('field,value', [
    ('base_pes_id', 100), ('pes_id', 9000099), ('card_type', 3), ('fake_version', 1),
    ('player_name', 'Another Player'), ('nationality_a', {'country_id': 204}),
    ('strong_foot', 0), ('age', 21), ('age', 30), ('height', 200),
])
def test_wrong_identity_or_variant_fails_closed(field, value):
    raw, appearance, state, requests = fixture()
    requests[0]['player'][field] = value
    with pytest.raises(ValueError):
        sync_records(raw, appearance, state, requests)


@pytest.mark.parametrize('mutation', ['row', 'native_owner', 'fingerprint', 'inactive', 'duplicate_owner'])
def test_registry_and_native_slot_guards(mutation):
    raw, appearance, state, requests = fixture()
    if mutation == 'row':
        raw = raw[:400] + bytes([raw[400] ^ 1]) + raw[401:]
    elif mutation == 'native_owner':
        state['identities']['ef:99']['registry']['native_player_id'] = 30
    elif mutation == 'fingerprint':
        state['identities']['ef:99']['fingerprint'] = 'wrong'
    elif mutation == 'inactive':
        state['identities']['ef:99']['status'] = 'tombstone'
    else:
        state['identities']['ef:100'] = dict(state['identities']['ef:99'], key='ef:100', base_id=100)
    with pytest.raises(ValueError):
        sync_records(raw, appearance, state, requests)


def test_invalid_tables_and_duplicate_requests_fail():
    raw, appearance, state, requests = fixture()
    for invalid in (b'', raw[:-1], raw + raw[:312]):
        with pytest.raises(ValueError):
            sync_records(invalid, appearance, state, requests)
    for invalid in (appearance[:-1], appearance + appearance[:60]):
        with pytest.raises(ValueError):
            sync_records(raw, invalid, state, requests)
    for invalid in ([], requests * 2):
        with pytest.raises(ValueError):
            sync_records(raw, appearance, state, invalid)


def make_collection(tmp_path, team_ids=(108,)):
    raw, appearance, state, requests = fixture()
    folder = tmp_path / 'snapshot'
    (folder / 'raw').mkdir(parents=True)
    catalog = {'categories': [{'key': 'spanish_league', 'team_ids': list(team_ids)}],
               'teams': [{'team_id': t, 'physical_team_id': t, 'category': 'spanish_league'} for t in team_ids]}
    catalog_raw = json.dumps(catalog).encode()
    (folder / 'catalog.json').write_bytes(catalog_raw)
    manifest = {'generator': GENERATOR, 'source': API, 'snapshot_id': 'snapshot',
                'catalog_sha256': digest(catalog_raw), 'teams': {}, 'errors': {}}
    for team_id in team_ids:
        payload = json.dumps({'data': {'pes_id': team_id,
                            'player_assignments': [{'player': requests[0]['player']}]}}).encode()
        (folder / 'raw' / f'{team_id}.json.gz').write_bytes(gzip.compress(payload))
        manifest['teams'][str(team_id)] = {'sha256': digest(payload), 'name': 'Synthetic Club',
            'url': API + str(team_id), 'fetched_at': '2026-10-05', 'problems': []}
    (folder / 'collection.json').write_text(json.dumps(manifest))
    assignments = {t: [PlayerAssignment(20, t, 0, 9)] for t in team_ids}
    return folder, state, assignments


def test_same_canonical_identity_across_two_teams_is_synced_once(tmp_path):
    folder, state, assignments = make_collection(tmp_path, (108, 7))
    requests, provenance = load_requests(folder, None, state, assignments, [108, 7])
    assert len(requests) == 1 and len(provenance['teams']) == 2
    assert requests[0]['player']['base_pes_id'] == 99


@pytest.mark.parametrize('mutation', ['missing_player', 'extra_player', 'wrong_snapshot', 'bad_checksum'])
def test_roster_or_snapshot_drift_is_not_silently_imported(tmp_path, mutation):
    folder, state, assignments = make_collection(tmp_path)
    if mutation == 'missing_player':
        assignments[108] = []
    elif mutation == 'extra_player':
        assignments[108].append(PlayerAssignment(30, 108, 1, 10))
    elif mutation == 'wrong_snapshot':
        state['collection_snapshot_id'] = 'other'
    else:
        (folder / 'raw/108.json.gz').write_bytes(gzip.compress(b'{}'))
    with pytest.raises(ValueError):
        load_requests(folder, None, state, assignments, [108])


def test_verified_canonical_profile_has_priority_and_wrong_base_is_rejected(tmp_path):
    folder, state, assignments = make_collection(tmp_path)
    profiles = tmp_path / 'profiles'
    (profiles / 'raw').mkdir(parents=True)
    player = fixture()[3][0]['player']
    player['weight'] = 81
    def write_profile():
        raw = json.dumps({'data': player}).encode()
        (profiles / 'raw/99.json.gz').write_bytes(gzip.compress(raw))
        (profiles / 'profiles.json').write_text(json.dumps({
            'generator': GENERATOR, 'source': PLAYER_API, 'snapshot_id': 'profile-snapshot',
            'collection_snapshot_id': 'snapshot', 'players': {'99': {
                'sha256': digest(raw), 'url': PLAYER_API + '99', 'fetched_at': '2026-10-05'}},
        }))
    write_profile()
    requests, _ = load_requests(folder, profiles, state, assignments, [108])
    assert requests[0]['player']['weight'] == 81
    assert requests[0]['source']['kind'] == 'canonical_profile'
    player.update(base_pes_id=100, pes_id=100)
    write_profile()
    with pytest.raises(ValueError, match='BaseId mismatch'):
        load_requests(folder, profiles, state, assignments, [108])


def test_conflicting_team_data_cannot_depend_on_iteration_order(tmp_path):
    folder, state, assignments = make_collection(tmp_path, (108, 7))
    raw = json.loads(gzip.decompress((folder / 'raw/7.json.gz').read_bytes()))
    raw['data']['player_assignments'][0]['player']['weight'] = 88
    encoded = json.dumps(raw).encode()
    (folder / 'raw/7.json.gz').write_bytes(gzip.compress(encoded))
    manifest = json.loads((folder / 'collection.json').read_text())
    manifest['teams']['7']['sha256'] = digest(encoded)
    (folder / 'collection.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Conflicting'):
        load_requests(folder, None, state, assignments, [108, 7])


@pytest.mark.parametrize('offset', [1 << 23, 1 << 24])
def test_only_exact_registered_base_card_alias_can_supply_physical_data(offset):
    raw, appearance, state, requests = fixture()
    requests[0]['player'].update(pes_id=99 + offset, fake_version=int(offset == 1 << 23))
    with pytest.raises(ValueError, match='Canonical'):
        sync_records(raw, appearance, state, requests)
    state['identities']['ef:99']['registry']['source_card_id'] = 99 + offset
    out, _, report = sync_records(raw, appearance, state, requests)
    assert report['changed_players'] == 1 and out != raw
    requests[0]['player']['card_type'] = 3
    with pytest.raises(ValueError, match='Canonical'):
        sync_records(raw, appearance, state, requests)


def test_canonical_single_biography_drift_preserves_native_country_and_foot():
    raw, appearance, state, requests = fixture()
    state['identities']['ef:99']['position'] = 5
    requests[0]['player'].update(main_position=5, strong_foot=0)
    out, updated, report = sync_records(raw, appearance, state, requests)
    assert report['players'][0]['biography_reconciliation']['field'] == 'foot'
    assert read_bits(out[312:624], 514, 1) == 1
    assert updated['identities']['ef:99']['foot'] == 1
    requests[0]['player']['nationality_a']['country_id'] = 204
    with pytest.raises(ValueError, match='biography'):
        sync_records(raw, appearance, state, requests)


def test_all_scope_holds_unverified_player_without_writing_any_of_its_bits():
    raw, appearance, state, requests = fixture()
    other = copy.deepcopy(state['identities']['ef:99'])
    other.update(key='ef:100', base_id=100, native_player_id=30, native_sha256=digest(raw[624:]))
    other['registry'].update(ef_base_id=100, native_player_id=30)
    state['identities']['ef:100'] = other
    bad = copy.deepcopy(requests[0])
    bad['player'].update(base_pes_id=100, pes_id=100, player_name='Unrelated Person')
    requests.append(bad)
    out, updated, report = sync_records(raw, appearance, state, requests, hold_unverified=True)
    assert out[624:] == raw[624:]
    assert updated['identities']['ef:100'] == other
    assert report['selected_players'] == 1 and report['held_players'][0]['base_id'] == 100
    # Bad baseline/state provenance is still a global failure, never a held row.
    state['identities']['ef:100']['native_sha256'] = 'wrong'
    with pytest.raises(ValueError, match='record changed'):
        sync_records(raw, appearance, state, requests, hold_unverified=True)


def make_full_collection(tmp_path):
    folder, state, _ = make_collection(tmp_path, (108, 7))
    prototype = copy.deepcopy(state['identities']['ef:99'])
    state['identities'] = {}
    players = []
    for i in range(11):
        native, base = 20 + i, 99 + i
        person = copy.deepcopy(prototype)
        person.update(key=f'ef:{base}', base_id=base, native_player_id=native)
        person['registry'].update(ef_base_id=base, native_player_id=native)
        state['identities'][person['key']] = person
        players.append(dict(fixture()[3][0]['player'], base_pes_id=base, pes_id=base))
    manifest = json.loads((folder / 'collection.json').read_text())
    assignments = {}
    for team in (108, 7):
        payload = json.dumps({'data': {'pes_id': team,
                            'player_assignments': [{'player': p} for p in players]}}).encode()
        (folder / f'raw/{team}.json.gz').write_bytes(gzip.compress(payload))
        manifest['teams'][str(team)]['sha256'] = digest(payload)
        assignments[team] = [PlayerAssignment(20 + i, team, i, i + 1) for i in range(11)]
    (folder / 'collection.json').write_text(json.dumps(manifest))
    return folder, state, assignments


def test_full_scope_counts_every_native_player_once_and_reports_missing_api_identity(tmp_path):
    folder, state, assignments = make_full_collection(tmp_path)
    state['identities']['ef:99']['base_id'] = None  # A local-only identity cannot borrow a numeric BaseId.
    requests, report = load_playable_requests(folder, None, state, assignments, folder / 'catalog.json')
    assert len(requests) == 10
    assert report['playable_players'] == 11 and report['playable_roster_slots'] == 22
    assert report['unavailable_players'][0]['reason'] == 'no_verified_api_BaseId'


def test_full_scope_does_not_import_incoming_api_players_or_remove_local_outgoing(tmp_path):
    folder, state, assignments = make_full_collection(tmp_path)
    person = state['identities'].pop('ef:99')
    person.update(key='ef:999', base_id=999)
    person['registry']['ef_base_id'] = 999
    state['identities']['ef:999'] = person
    requests, report = load_playable_requests(folder, None, state, assignments, folder / 'catalog.json')
    assert len(requests) == 10
    assert all(r['player']['base_pes_id'] != 99 for r in requests)
    assert report['unavailable_players'][0]['base_id'] == 999
    assert report['unavailable_players'][0]['reason'] == 'no_frozen_api_profile'


def test_full_scope_refuses_catalog_slot_changes(tmp_path):
    folder, state, assignments = make_full_collection(tmp_path)
    catalog = json.loads((folder / 'catalog.json').read_text())
    catalog['teams'][0]['physical_team_id'] = 555
    separate = tmp_path / 'current-catalog.json'
    separate.write_text(json.dumps(catalog))
    with pytest.raises(ValueError, match='mapping changed'):
        load_playable_requests(folder, None, state, assignments, separate)


def test_existing_fl26_to_baseid_promotion_keeps_pinned_assets():
    raw, appearance, state, requests = fixture()
    owner = state['identities']['ef:99']
    owner['previous_keys'] = ['fl26:555']
    owner['asset_fingerprint'] = owner['fingerprint']
    owner['registry'].pop('ef_base_id')
    owner['registry'].update(source_key='fl26:555', fl26_player_id=555)
    out, updated, report = sync_records(raw, appearance, state, requests)
    assert report['changed_players'] == 1 and out != raw
    assert updated['identities']['ef:99']['registry'] == owner['registry']
    owner['previous_keys'] = []
    with pytest.raises(ValueError, match='ownership'):
        sync_records(raw, appearance, state, requests)


def test_nonregistered_base_alias_needs_exact_full_asset_fingerprint():
    raw, appearance, state, requests = fixture()
    requests[0]['player'].update(pes_id=99 + (1 << 23), fake_version=1, height=180)
    out, _, report = sync_records(raw, appearance, state, requests)
    assert report['changed_players'] == 1
    assert out[312 + 27] == raw[312 + 27]
    requests[0]['player']['height'] = 181
    with pytest.raises(ValueError, match='Canonical'):
        sync_records(raw, appearance, state, requests)


def test_large_height_review_is_bound_to_exact_identity_row_and_api_response():
    raw, appearance, state, requests = fixture()
    requests[0]['player']['height'] = 198
    owner = state['identities']['ef:99']
    review = dict(base_id=99, native_player_id=20, asset_fingerprint=owner['fingerprint'],
                  native_row_sha256=owner['native_sha256'], api_sha256=requests[0]['source']['sha256'],
                  height_before_cm=180, height_after_cm=198, reason='Explicit synthetic source audit')
    requests[0]['height_review'] = review
    out, updated, report = sync_records(raw, appearance, state, requests)
    assert out[312 + 27] + 100 == 198
    assert report['players'][0]['biography_reconciliation']['field'] == 'height'
    assert sync_records(out, appearance, updated, requests)[0] == out
    for field in ('asset_fingerprint', 'native_row_sha256', 'api_sha256', 'height_after_cm'):
        bad = copy.deepcopy(requests)
        bad[0]['height_review'][field] = 'wrong'
        with pytest.raises(ValueError, match='separate identity audit'):
            sync_records(raw, appearance, state, bad)

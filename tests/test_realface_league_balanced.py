"""League expansion preserves source identity, the accepted cohort and 5k gates."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import realface_league_balanced as league


def put(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')
    return str(path)


def fixture(tmp_path):
    owner = dict(base_id=1, native_player_id=7, fingerprint='identity', team_ids=[100])
    config = dict(catalog=put(tmp_path/'catalog.json', dict(categories=[
        dict(key='english_league', team_ids=[100]), dict(key='spanish_league', team_ids=[108])])),
        source_verification=put(tmp_path/'proof.json', dict(players=[owner])),
        identity_state=put(tmp_path/'identity.json', dict(identities={'1': dict(owner, status='active')})))
    return config, owner


def test_scope_requires_current_identity_and_both_categories(tmp_path):
    config, owner = fixture(tmp_path)
    scope = league.scope_for(config, {1: owner})
    assert scope['teams'] == [100, 108] and scope['selected_base_ids'] == [1]
    assert scope['policy'] == league.POLICY
    altered = dict(owner, fingerprint='new owner')
    with pytest.raises(ValueError, match='ownership'):
        league.scope_for(config, {1: altered})
    identity = Path(config['identity_state'])
    put(identity, dict(identities={'1': dict(altered, status='active')}))
    with pytest.raises(ValueError, match='active identity'):
        league.scope_for(config, {1: owner})


def test_missing_source_keeps_explicit_fallback(tmp_path):
    config, owner = fixture(tmp_path)
    scope = league.scope_for(config, {})
    assert scope['source_count'] == 0 and scope['unresolved'] == [owner]
    row = dict(owner, input_hashes={str(tmp_path/'absent.fbx'): 'hash'})
    result = league.prepare_player({}, row, None)
    assert result['status'] == 'held_source' and result['native_player_id'] == 7


def test_opaque_skin_hair_is_checkpointed_without_trial_or_identity_bypass(tmp_path, monkeypatch):
    profile = tmp_path/'profile.json'
    put(profile, dict(native_player_id=7, hair_skin_materials=['own_skin']))
    row = dict(base_id=1, native_player_id=7, fingerprint='identity',
               profile=str(profile), input_hashes={str(profile): league.sha(profile)})
    def refuse(config, source, worker):
        raise ValueError('Unsupported identity or skin carried in source hair')
    monkeypatch.setattr(league.trial, 'prepare_one', refuse)
    result = league.prepare_player({}, row, None)
    assert result['status'] == 'held_source'
    assert result['source_hold_kind'] == 'opaque_skin_in_hair'
    assert result['fingerprint'] == row['fingerprint']
    with pytest.raises(ValueError, match='Unsupported identity'):
        league.prepare_player({}, dict(row, native_player_id=8), None)
    put(profile, dict(native_player_id=7, hair_skin_materials=['changed_skin']))
    with pytest.raises(ValueError, match='Pinned original source changed'):
        league.prepare_player({}, row, None)


def test_additional_leagues_and_two_explicit_clubs(tmp_path):
    config,owner=fixture(tmp_path)
    config.update(categories=['ligue_1','serie_a'],team_ids=[5738,18961])
    categories=[dict(key='ligue_1',team_ids=[1]),dict(key='serie_a',team_ids=[2])]
    teams=[dict(team_id=i,physical_team_id=i+100) for i in (1,2,5738,18961)]
    put(Path(config['catalog']),dict(categories=categories,teams=teams))
    owner['team_ids']=[1]
    put(Path(config['source_verification']),dict(players=[owner]))
    scope=league.scope_for(config,{1:owner})
    assert scope['teams']==[1,2,5738,18961]
    assert scope['categories']==['ligue_1','serie_a']
    config['team_ids'].append(99999)
    with pytest.raises(ValueError,match='Missing selected'): league.scope_for(config,{1:owner})


def test_duplicate_native_owner_is_rejected():
    with pytest.raises(ValueError, match='Duplicate'):
        league.unique([dict(base_id=1, native_player_id=7), dict(base_id=2, native_player_id=7)], 'scope')


def test_5k_failures_can_use_bounded_exception_but_not_over_7000(tmp_path, monkeypatch):
    calls = []
    folder = tmp_path/'head'; folder.mkdir()
    def prepare(config, row, worker):
        cap = config['experimental_head_cap']; calls.append(cap)
        if cap == 5000:
            return dict(row, folder=str(folder), cache_key='held', status='held_geometry', reason='Hair silhouette held')
        return dict(row, folder=str(folder), cache_key='ready', status='prepared', triangles=6500)
    monkeypatch.setattr(league.trial, 'prepare_one', prepare)
    monkeypatch.setattr(league, 'validate_head', lambda row: row['triangles'])
    row = dict(base_id=1, native_player_id=7, fingerprint='id', input_hashes={})
    result = league.prepare_player({}, row, None)
    assert calls == [5000, 5000, 5000, 7000]
    assert result['triangles'] == 6500 and result['league_exception']['attempts']
    monkeypatch.setattr(league.trial, 'prepare_one', lambda c, r, w:
        dict(r, folder=str(folder), cache_key='bad', status='prepared', triangles=7001))
    assert league.prepare_player({}, row, None)['status'] == 'held_geometry'


def test_face_failure_does_not_lower_face_allocation(tmp_path, monkeypatch):
    calls = []
    def prepare(config, row, worker):
        calls.append(config['experimental_head_cap'])
        return dict(row, folder=str(tmp_path), cache_key='held', status='held_geometry', reason='Visible face UV distortion held')
    monkeypatch.setattr(league.trial, 'prepare_one', prepare)
    league.prepare_player({}, dict(base_id=1, input_hashes={}), None)
    assert calls == [5000, 7000]


def test_facial_hair_is_protected_before_selecting_result(tmp_path, monkeypatch):
    put(tmp_path/'lite_hair-meshopt.json', dict(positions=[0, 6, 160]*3, indices=[0, 1, 2]*20))
    calls = []
    def prepare(config, row, worker):
        locked = config['experimental_allocations'][str(row['base_id'])]['hair_face_lock']
        calls.append(locked)
        return dict(row, folder=str(tmp_path), cache_key=str(locked), status='prepared', triangles=4900)
    monkeypatch.setattr(league.trial, 'prepare_one', prepare)
    monkeypatch.setattr(league, 'validate_head', lambda row: row['triangles'])
    result = league.prepare_player({}, dict(base_id=1, input_hashes={}), None)
    assert calls == [False, True] and result['facial_hair_policy']['locked']


def test_head_proof_and_exception_are_mandatory(tmp_path, monkeypatch):
    put(tmp_path/'simplification.json', {})
    put(tmp_path/'hair-projection.json', {})
    monkeypatch.setattr(league.trial, 'validate_preparation', lambda a, b, cap: 6500)
    row = dict(status='prepared', folder=str(tmp_path), triangles=6500, budgets={'head_cap':7000})
    with pytest.raises(ValueError, match='exception'):
        league.validate_head(row)
    assert league.validate_head(dict(row, league_exception={'reason':'explicit'})) == 6500
    with pytest.raises(ValueError, match='proof'):
        league.validate_head(dict(row, triangles=6499))
    monkeypatch.setattr(league.trial, 'validate_preparation', lambda a,b,cap:7000)
    assert league.validate_head(dict(row,triangles=7000,league_exception={'reason':'unique hairstyle'}))==7000


def test_initialization_writes_only_new_output_and_preserves_v54(tmp_path, monkeypatch):
    accepted = tmp_path/'accepted'; accepted.mkdir()
    release = accepted/'release'; release.mkdir()
    config = {}
    for key in ('source_profiles', 'source_verification', 'identity_state', 'catalog', 'selector'):
        config[key] = put(accepted/(key+'.json'), {})
    for name in ('prepare-report.json', 'verify-report.json'):
        put(accepted/name, [])
    put(accepted/'latest-test.json', {'release': str(release)})
    put(release/'VERIFICATION.json', {})
    baseline = Path(put(accepted/'config.local.json', config))
    candidate = tmp_path/'v54'; candidate.mkdir()
    files = {}
    for name in ('pes21_nx.nro', 'referee-probe.txt', 'Animations/referee.nxra', 'Commentary/players-v53.nxcp'):
        relative = 'switch/pes21_nx/'+name
        path = candidate/relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(('immutable '+name).encode())
        files[relative] = {'sha256':league.sha(path), 'bytes':path.stat().st_size}
    put(candidate.parent/'release-validation.json', dict(
        executing_build_id='79cf4f629bf5992fc6e878d96f15f7ff29a32c19', files=files))
    before = {name:(candidate/name).read_bytes() for name in files}
    monkeypatch.setattr(league, 'sources', lambda config: [])
    monkeypatch.setattr(league, 'scope_for', lambda config, rows: {'roster_count':0,'teams':[]})
    monkeypatch.setattr(league, 'local_output', lambda p: Path(p))
    output = tmp_path/'new-output'
    league.initialize(baseline, output, candidate)
    assert (output/'config.local.json').is_file()
    assert all((candidate/name).read_bytes()==data for name, data in before.items())

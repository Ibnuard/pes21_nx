"""Batch identity, payload allowlist and resume tests with synthetic inputs."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_batch import PREFIX, classify_documents, output_hashes, valid_cache, verify_inputs
from realface_batch_inventory import preserved_matches, selected_teams
from realface_batch_package import allowed_assets, check_asset_path, release_rows, preserved_marker
from realface_batch_status import exports
from realface_batch_release import verify_one, check_import_completion


def test_leagues_deduplicate_teams_and_reject_conflicting_storage():
    catalog = dict(categories=[dict(key='england', team_ids=[1, 2])],
                   teams=[dict(team_id=1, physical_team_id=11), dict(team_id=2, physical_team_id=12)])
    assert len(selected_teams(catalog, ['england'], [1])) == 2
    with pytest.raises(ValueError, match='Unknown'):
        selected_teams(catalog, ['missing'])
    catalog['teams'][1]['physical_team_id'] = 11
    with pytest.raises(ValueError, match='Conflicting'):
        selected_teams(catalog, ['england'])


def test_old_face_fingerprint_needs_exact_physique_chain():
    proof = dict(native_player_id=100, fingerprint='old')
    owner = dict(base_id=7, native_player_id=100, fingerprint='pinned')
    old = dict(base_id=7, native_player_id=100, fingerprint='old', native_row_sha256='before')
    physical = dict(asset_fingerprint='pinned', row_sha256_before='before', row_sha256_after='after')
    assert preserved_matches(proof, owner, 'after', old, physical)
    assert not preserved_matches(proof, owner, 'other', old, physical)
    assert not preserved_matches(proof, owner, 'after', None, physical)
    assert not preserved_matches(proof, dict(owner, native_player_id=101), 'after', old, physical)
    assert not preserved_matches(proof, owner, 'after', dict(old, base_id=8), physical)


def test_resume_rejects_changes_missing_and_added_outputs(tmp_path):
    asset = tmp_path / 'face.fbx'
    asset.write_bytes(b'original')
    stamp = tmp_path / 'complete.json'
    stamp.write_text(json.dumps(dict(cache_key='key', outputs=output_hashes(tmp_path))))
    assert valid_cache(tmp_path, 'key')
    assert not valid_cache(tmp_path, 'other-code-or-input')
    (tmp_path / 'unexpected.uasset').write_bytes(b'extra')
    assert not valid_cache(tmp_path, 'key')
    (tmp_path / 'unexpected.uasset').unlink()
    asset.write_bytes(b'changed')
    assert not valid_cache(tmp_path, 'key')
    asset.unlink()
    assert not valid_cache(tmp_path, 'key')


def test_incremental_reuse_keeps_original_proof_and_rejects_modified_assets(tmp_path):
    from realface_batch import reuse_verified
    row=dict(base_id=7,native_player_id=100,reused_from='previous-batch',cache_key='prepared-v1',cooked_cache_key='cooked-v1')
    for folder,key in [('folder','cache_key'),('cooked_folder','cooked_cache_key')]:
        path=tmp_path/folder;path.mkdir();(path/'asset.bin').write_bytes(b'verified')
        if folder=='folder':
            (path/'ue-profile.json').write_text(json.dumps(dict(base_id=7,native_player_id=100)))
        (path/'complete.json').write_text(json.dumps(dict(cache_key=row[key],outputs=output_hashes(path))))
        row[folder]=str(path)
    result=reuse_verified(row)
    assert result['cache_key']=='prepared-v1'
    assert result['reuse_cooked']['cooked_cache_key']=='cooked-v1'
    (Path(row['cooked_folder'])/'asset.bin').write_bytes(b'changed')
    with pytest.raises(ValueError,match='Previously verified cache changed'):
        reuse_verified(row)


def test_prepared_cache_allows_only_identical_embedded_texture_copies(tmp_path):
    from realface_batch import valid_prepared_cache
    (tmp_path/'face.fbx').write_bytes(b'fbx')
    (tmp_path/'texture.png').write_bytes(b'png')
    (tmp_path/'complete.json').write_text(json.dumps(dict(cache_key='key',outputs=output_hashes(tmp_path))))
    sidecar=tmp_path/'face.fbm';sidecar.mkdir()
    (sidecar/'texture.png').write_bytes(b'png')
    assert not valid_cache(tmp_path,'key')
    assert valid_prepared_cache(tmp_path,'key')
    (sidecar/'texture.png').write_bytes(b'changed')
    assert not valid_prepared_cache(tmp_path,'key')
    (sidecar/'texture.png').write_bytes(b'png')
    (sidecar/'unverified.png').write_bytes(b'png')
    assert not valid_prepared_cache(tmp_path,'key')


def test_package_cannot_include_shared_or_unowned_assets():
    assert len(allowed_assets(100)) == 17
    for name in allowed_assets(100):
        check_asset_path(PREFIX + name, {100})
    for name in ('PesMobile/Content/Assets/character/BaseAssets/test_body_Skeleton.uasset',
                 PREFIX + '101_face.uasset', PREFIX + '../100_face.uasset',
                 PREFIX + '100_face.ubulk', PREFIX + 'M_RealFaceBase.uasset'):
        with pytest.raises(ValueError, match='Unowned/shared'):
            check_asset_path(name, {100})
    assert '100_eye_tablet.uasset' not in allowed_assets(100)
    check_asset_path(PREFIX + '100_eye_tablet.uasset', {100}, legacy=True)


def test_legacy_pilot_labels_can_be_omitted_without_accepting_shared_payloads():
    assert preserved_marker('PES21NX_LAMINE_CANARY_V19C.txt')
    assert preserved_marker('PES21NX_RAPHINHA_CANARY_V1.txt')
    assert preserved_marker('PESNX_BARCELONA_REALFACE_COMBINED_V2.txt')
    for name in ('PES21NX_bad.uasset', 'shared.txt', 'folder/PESNX_x.txt', 'folder\\PESNX_x.txt'):
        assert not preserved_marker(name)


def test_release_covers_held_players_and_rejects_moved_native_slot():
    players = [dict(base_id=7, native_player_id=100, name='One', fingerprint='fp', team_ids=[1], status='source_ready'),
               dict(base_id=8, native_player_id=101, name='Two', fingerprint='fp2', team_ids=[1], status='missing_source')]
    verified = [dict(base_id=7, native_player_id=100, status='validated')]
    rows = release_rows(dict(players=players), [], verified)
    assert [r['status'] for r in rows] == ['candidate_pending_device', 'missing_source']
    assert rows == release_rows(dict(players=players), [], [dict(verified[0], status='validated_cached')])
    with pytest.raises(ValueError, match='ownership'):
        release_rows(dict(players=players), [], [dict(verified[0], native_player_id=101)])
    with pytest.raises(ValueError, match='Duplicate'):
        release_rows(dict(players=players), [], verified * 2)


def test_material_roles_override_misleading_file_and_labels():
    def material(technique, texture):
        return dict(name='fox_skin_mat', extras=dict(fmdlTechnique=technique,
                    fmdlTextures=[dict(role='Base_Tex_SRGB', filename=texture)]))
    docs = dict(face=dict(materials=[material('pes3DDC_Wet', 'face_bsm_alp.dds'),
                                    material('pes3DDF_Hair2', 'native_hair_bsm_alp.dds')]),
                hair=dict(materials=[material('pes3DDF_Skin_Face', 'face_bsm_alp.dds')]))
    roles, parts, scalp = classify_documents(docs)
    assert roles['face'][0]['role'] == 'effect'
    assert parts == dict(face=['rf_skin', 'eye_mat'], hair=['rf_hair'])
    assert not scalp


def test_retry_held_selects_only_failed_or_new_sources():
    from realface_batch import pending_players
    inv=dict(players=[dict(base_id=i,native_player_id=i+100,status='source_ready') for i in (1,2,3)])
    inv['players'].append(dict(base_id=4,native_player_id=104,status='missing_source'))
    rows=[dict(base_id=1,native_player_id=101,status='prepared_cached'),
          dict(base_id=2,native_player_id=102,status='held_conversion')]
    assert pending_players(inv,rows)=={2,3}
    rows[0]['native_player_id']=999
    with pytest.raises(ValueError,match='identity moved'):
        pending_players(inv,rows)


def test_atomic_report_keeps_previous_content_when_replacement_fails(tmp_path, monkeypatch):
    import realface_batch_inventory as inventory
    path=tmp_path/'report.json'
    inventory.write(path,dict(complete=True))
    original=path.read_bytes()
    def fail(*args):raise OSError('simulated replacement failure')
    monkeypatch.setattr(inventory.os,'replace',fail)
    with pytest.raises(OSError):inventory.write(path,dict(complete=False))
    assert path.read_bytes()==original
    assert list(tmp_path.iterdir())==[path]


def test_verification_resume_does_not_launch_tools_and_rejects_tampering(tmp_path):
    (tmp_path / 'verification.json').write_text('{}')
    (tmp_path / 'complete.json').write_text(json.dumps(dict(cache_key='key', outputs=output_hashes(tmp_path))))
    row = dict(status='cooked_pending_verification', cooked_folder=str(tmp_path), cooked_cache_key='key')
    assert verify_one({}, row)['status'] == 'validated_cached'
    (tmp_path / 'verification.json').write_text('changed')
    assert verify_one({}, dict(row, status='cooked_cached'))['status'] == 'held_cook_validation'


def test_status_exports_include_all_players_and_escape_names(tmp_path):
    report = dict(new_faces=1, preserved_faces=0,
                  teams=[dict(team_id=1, name='Club', category='english_league')],
                  players=[dict(name='A <script>', team_ids=[1], status='candidate_pending_device'),
                           dict(name='Missing Name', team_ids=[1], status='missing_source')])
    exports(report, tmp_path)
    text = (tmp_path / 'PLAYER-STATUS.txt').read_text(encoding='utf-8')
    html = (tmp_path / 'PLAYER-STATUS.html').read_text(encoding='utf-8')
    assert 'SUDAH / DIPERTAHANKAN (1)' in text and 'BELUM (1)' in text
    assert 'Missing Name' in text and 'A <script>' in text
    assert 'A &lt;script&gt;' in html and html.count('<tr data-state=') == 2


def test_recovery_list_counts_only_failed_conversions_and_locks_identity(tmp_path):
    from realface_batch_package import recovery_summary
    def player(base,status):
        return dict(base_id=base,native_player_id=base+100,fingerprint='owner'+str(base),
                    name='Player '+str(base),team_ids=[1],status=status)
    before=[player(1,'held_conversion'),player(2,'held_cook_validation'),player(3,'missing_source'),
            player(4,'candidate_pending_device')]
    after=[player(1,'candidate_pending_device'),player(2,'held_conversion'),player(3,'candidate_pending_device'),
           player(4,'candidate_pending_device')]
    recovery=dict(recovery_summary(after,before),baseline='previous')
    assert (recovery['targeted'],recovery['recovered'],recovery['pending'])==(2,1,1)
    report=dict(new_faces=3,preserved_faces=0,players=after,recovery=recovery,
                teams=[dict(team_id=1,name='Club',category='english_league')])
    exports(report,tmp_path)
    text=(tmp_path/'RECOVERY-STATUS.txt').read_text(encoding='utf-8')
    assert 'Player 1' in text and 'Player 2' in text and 'Player 3' not in text
    assert json.loads((tmp_path/'RECOVERY-STATUS.json').read_text())['recovered']==1
    after[0]['fingerprint']='other-owner'
    with pytest.raises(ValueError,match='identity'):
        recovery_summary(after,before)


def test_changed_selector_cannot_reuse_an_inventory(tmp_path):
    from realface_pipeline import sha
    config = dict(runtime_base=str(tmp_path))
    inv = {}
    for name, field in [('identity_state', 'source_state_sha256'), ('selector', 'selector_sha256'),
                        ('catalog', 'catalog_sha256')]:
        path = tmp_path / name
        path.write_bytes(b'locked')
        config[name] = str(path)
        inv[field] = sha(path)
    cpk = tmp_path / 'LooseCpk/dt200_mobile_all.cpk'
    cpk.parent.mkdir()
    cpk.write_bytes(b'cpk')
    inv['source_cpk_sha256'] = sha(cpk)
    verify_inputs(config, inv)
    Path(config['selector']).write_bytes(b'new squad order')
    with pytest.raises(ValueError, match='selection changed'):
        verify_inputs(config, inv)


def test_import_batch_can_hold_one_failure_but_cannot_hide_a_crash(tmp_path):
    profiles = []
    for native in (100, 101):
        path = tmp_path / f'{native}.json'
        report = tmp_path / f'{native}.report.json'
        path.write_text(json.dumps(dict(native_player_id=native, report=str(report))))
        report.write_text(json.dumps(dict(status='imported', player=native, parts=dict(face={}, hair={}))))
        profiles.append(str(path))
    marker = tmp_path / 'complete.json'
    with pytest.raises(ValueError, match='entire batch'):
        check_import_completion(profiles, marker)
    marker.write_text(json.dumps(dict(profiles=2)))
    assert check_import_completion(profiles, marker) == 0
    report.write_text(json.dumps(dict(status='failed', reason='Mesh import failed: hair')))
    assert check_import_completion(profiles, marker) == 1
    report.write_text(json.dumps(dict(status='imported', player=999, parts=dict(face={}, hair={}))))
    with pytest.raises(ValueError, match='identity'):
        check_import_completion(profiles, marker)


def test_blender_worker_reuses_process_and_isolates_player_failures(tmp_path, monkeypatch):
    import io
    from types import SimpleNamespace
    import realface_validation_process as worker
    launches = []
    process = SimpleNamespace(stdin=io.StringIO(), stdout=io.StringIO(
        'startup\n' + '\n'.join(worker.PREFIX + json.dumps(result) for result in [
            dict(token='token', ok=True), dict(token='token', ok=False, reason='bad eye fit'),
            dict(token='token', ok=True)]) + '\n'),
        poll=lambda: None, wait=lambda timeout: 0)
    monkeypatch.setattr(worker.subprocess, 'Popen', lambda *a, **k: launches.append(a) or process)
    monkeypatch.setattr(worker.uuid, 'uuid4', lambda: SimpleNamespace(hex='token'))
    validator = worker.ValidationProcess('blender')
    validator(tmp_path / 'one.json', tmp_path / 'one.log')
    with pytest.raises(ValueError, match='bad eye fit'):
        validator(tmp_path / 'two.json', tmp_path / 'two.log')
    validator(tmp_path / 'three.json', tmp_path / 'three.log')
    assert len(launches) == 1
    assert len(process.stdin.getvalue().splitlines()) == 3
    validator.close()
    assert process.stdin.closed and process.stdout.closed

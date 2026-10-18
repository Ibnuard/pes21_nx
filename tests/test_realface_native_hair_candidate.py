import csv
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_native_hair_candidate import select_verified, archive_release, coverage_tables, status_reason
from realface_native_hair_queue import pending, batch_paths


def test_test_package_requires_all_current_candidates_to_have_cook_results():
    trials = [dict(base_id=1, cache_key='one', status='prepared'), dict(base_id=2, cache_key='two', status='prepared')]
    verified = [dict(trials[0], status='validated'), dict(trials[1], status='held_cook_validation')]
    assert [r['base_id'] for r in select_verified(trials, verified)] == [1]
    with pytest.raises(ValueError, match='independent cook result'):
        select_verified(trials, verified[:1])
    with pytest.raises(ValueError, match='no longer matches'):
        select_verified(trials, [dict(verified[0], cache_key='stale'), verified[1]])


def test_cook_queue_only_reuses_the_current_prepared_key():
    rows = [dict(base_id=1, status='candidate_visual_hold', cache_key='new'),
            dict(base_id=2, status='held_composite_geometry', cache_key='held'),
            dict(base_id=3, status='candidate_visual_hold', cache_key='same')]
    saved = {1: dict(cache_key='old'), 3: dict(cache_key='same')}
    assert [r['base_id'] for r in pending(rows, saved)] == [1]


def test_queue_dependency_paths_fit_legacy_umodel_limit():
    trial, work = batch_paths('league', ['key'])
    dependency = work / 'cook-jobs/0123456789abcdef/PesMobile/Saved/Cooked/Android_ETC1/PesMobile/Content/Assets/character/BaseAssets/hair_parts_tablet_ss.uasset'
    assert len(str(dependency)) < 250
    assert trial != work


def test_archive_retry_excludes_old_archive_and_partial_output(tmp_path):
    pak = tmp_path / 'update/faces.pak'; pak.parent.mkdir()
    pak.write_bytes(b'authored packaging fixture')
    (tmp_path / 'INSTALL.txt').write_text('Test only', encoding='utf-8')
    (tmp_path / 'ARCHIVE.json').write_text('stale', encoding='utf-8')
    archive = tmp_path / 'test.zip'; archive.write_bytes(b'interrupted old archive')
    archive.with_suffix('.zip.tmp').write_bytes(b'interrupted temporary archive')
    for _ in range(2):
        archive_release(tmp_path, archive, pak)
        with zipfile.ZipFile(archive) as bundle:
            assert set(bundle.namelist()) == {'FootballNX-NativeHair-v39-TEST/INSTALL.txt',
                                              'FootballNX-NativeHair-v39-TEST/update/faces.pak'}
            assert bundle.testzip() is None
        assert not archive.with_suffix('.zip.tmp').exists()


def test_coverage_tables_count_unique_scope_and_actual_package_membership(tmp_path):
    report = dict(teams=[dict(team_id=1, name='Club A', category='english_league'),
                         dict(team_id=2, name='Club B', category='spanish_league')], players=[
        dict(base_id=10, name='Retained', team_ids=[1, 2], status='accepted_v37_retained'),
        dict(base_id=11, name='Candidate', team_ids=[1], status='native_cooked_visual_hold'),
        dict(base_id=12, name='Rejected', team_ids=[2], status='held_visual', reason='Visible scalp gap')])
    coverage_tables(tmp_path, report, {10, 11})
    with (tmp_path / 'PLAYER-STATUS.csv').open(encoding='utf-8-sig', newline='') as stream:
        players = list(csv.DictReader(stream))
    assert len(players) == 3
    assert players[0]['teams'] == 'Club A;Club B'
    assert players[2]['included'] == 'False' and players[2]['reason'] == 'Visible scalp gap'
    with (tmp_path / 'TEAM-COVERAGE.csv').open(encoding='utf-8-sig', newline='') as stream:
        teams = list(csv.DictReader(stream))
    assert [(t['included'], t['not_included']) for t in teams] == [('2', '0'), ('1', '1')]
    assert 'Target katalog: 3 identitas pemain, 2 tim.' in (tmp_path / 'COVERAGE.txt').read_text(encoding='utf-8')


def test_held_coverage_explains_missing_reason_without_losing_actual_diagnostic():
    assert 'multi-view' in status_reason(dict(status='held_composite_geometry', reason=None))
    assert 'identity-verified' in status_reason(dict(status='source_unresolved'))
    assert status_reason(dict(status='held_geometry', reason='Face UV seam failed')) == 'Face UV seam failed'

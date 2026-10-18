import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import realface_native_hair_leagues as league


def test_league_coverage_keeps_accepted_missing_and_failed_players_distinct():
    players = [dict(base_id=i, team_ids=[1], stage='source_unresolved') for i in range(1, 7)]
    canonical = {1: dict(reuse_cooked=True, triangles=1999), 2: dict(status='prepared'),
                 3: dict(status='prepared'), 4: dict(status='prepared'), 5: dict(status='prepared')}
    native = {2: dict(status='candidate_visual_hold', cache_key='fresh', triangles=2000),
              3: dict(status='held_composite_geometry'), 4: dict(status='candidate_visual_hold', cache_key='new')}
    verified = [dict(base_id=2, cache_key='fresh', status='validated'),
                dict(base_id=4, cache_key='old', status='validated')]
    report = league.coverage(dict(players=players, teams=[dict(team_id=1)]), canonical, native, verified)
    assert [r['status'] for r in report['players']] == [
        'accepted_v37_retained', 'native_cooked_visual_hold', 'held_composite_geometry',
        'candidate_visual_hold', 'native_pending', 'source_unresolved']
    assert sum(report['teams'][0]['native_counts'].values()) == 6
    assert not report['visual_approved'] and not report['device_profiled']
    again = league.coverage(report, canonical, native, verified)
    assert again['counts'] == report['counts']


def test_reuse_rejects_changed_faces_sources_and_candidate_bytes(monkeypatch):
    owner = dict(base_id=1, native_player_id=9, fingerprint='person', input_hashes={'source': 'source-hash'})
    face = dict(cache_key='face-key', folder='face')
    row = dict(owner, status='candidate_visual_hold', composite_geometry_pass=True,
               source_face_key='face-key', recipe_source_sha256={'tool': 'code'}, folder='native', cache_key='native-key')
    monkeypatch.setattr(league, 'valid_prepared_cache', lambda *a: True)
    monkeypatch.setattr(league, 'valid_cache', lambda *a: True)
    monkeypatch.setattr(league, 'sha', lambda p: 'source-hash')
    assert league.reusable(row, face, owner, {'tool': 'code'})
    assert not league.reusable(dict(row, source_face_key='other'), face, owner, {'tool': 'code'})
    assert not league.reusable(row, face, dict(owner, fingerprint='donor'), {'tool': 'code'})
    monkeypatch.setattr(league, 'valid_cache', lambda *a: False)
    with pytest.raises(ValueError, match='candidate bytes changed'):
        league.reusable(row, face, owner, {'tool': 'code'})


def test_workers_have_separate_reports_and_stop_after_first_gate_pass(monkeypatch, tmp_path):
    calls = []; reports = {}
    def trial(cfg, face_report, ids, dest, budget, mode, colour, closing):
        calls.append((ids, dest, closing))
        reports[dest / 'trial-report.json'] = [dict(base_id=ids[0], status=(
            'candidate_visual_hold' if closing == 1 else 'held_composite_geometry'))]
    monkeypatch.setattr(league, 'trial', trial)
    monkeypatch.setattr(league, 'read', lambda p: reports[p])
    result = league.convert({}, 'faces', 1, tmp_path)
    assert result['status'] == 'candidate_visual_hold'
    assert [c[2] for c in calls] == [3, 1]
    assert calls[0][1] != calls[1][1]
    assert all('players/1' in c[1].as_posix() for c in calls)

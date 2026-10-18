import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import realface_native_hair_finish as finish


def test_finisher_waits_for_cook_process_then_runs_technical_queue_and_test_pack(monkeypatch, tmp_path):
    root = tmp_path / 'repo'; work = root / 'local-debug' / 'league'
    monkeypatch.setattr(finish, 'HERE', root / 'tools')
    docs = {Path('config'): {}, work / 'chosen-faces.json': [dict(status='prepared')],
            work / 'trial-report.json': [dict(base_id=1, status='candidate_visual_hold', cache_key='current')],
            work / 'release/VERIFICATION.json': dict(counts={'native_cooked_visual_hold': 1}),
            work / 'latest-test.json': dict(test_only=True)}
    writes = []; events = []; state = iter((True, False))
    monkeypatch.setattr(finish, 'read', lambda p: docs[Path(p)])
    monkeypatch.setattr(finish, 'write', lambda p, v: writes.append((p, v)))
    monkeypatch.setattr(finish, 'running', lambda pid: next(state))
    monkeypatch.setattr(finish.time, 'sleep', lambda seconds: events.append('wait'))
    monkeypatch.setattr(finish, 'queue', lambda *a, **kw: events.append('verify'))
    monkeypatch.setattr(finish, 'recover', lambda *a: events.append('source_recovery') or ({}, work))
    monkeypatch.setattr(finish, 'package', lambda *a: events.append('test_pack') or work / 'release')
    finish.finish('config', work, 1, 2)
    assert events == ['source_recovery', 'wait', 'verify', 'verify', 'test_pack']
    assert writes[-1][1]['phase'] == 'test_candidate_complete'
    assert not writes[-1][1]['approved'] and not writes[-1][1]['installed']


def test_finisher_cannot_merge_recovery_caches_while_early_worker_owns_them(monkeypatch, tmp_path):
    root = tmp_path / 'repo'; work = root / 'local-debug' / 'league'
    work.mkdir(parents=True); (work / 'PRECOMPUTE-STATUS.json').touch()
    monkeypatch.setattr(finish, 'HERE', root / 'tools')
    docs = {Path('config'): {}, work / 'chosen-faces.json': [dict(status='prepared')],
            work / 'trial-report.json': [dict(base_id=1, status='candidate_visual_hold', cache_key='current')],
            work / 'PRECOMPUTE-STATUS.json': dict(phase='running', pid=3, completed=4, active_base_id=1),
            work / 'release/VERIFICATION.json': dict(counts={'native_cooked_visual_hold': 1}),
            work / 'latest-test.json': dict(test_only=True)}
    events = []; writes = []; active = iter((True, False))
    monkeypatch.setattr(finish, 'read', lambda p: docs[Path(p)])
    monkeypatch.setattr(finish, 'write', lambda p, v: writes.append(v))
    monkeypatch.setattr(finish, 'running', lambda pid: next(active) if pid == 3 else False)
    monkeypatch.setattr(finish.time, 'sleep', lambda seconds: events.append('wait_for_cache'))
    monkeypatch.setattr(finish, 'queue', lambda *a, **kw: events.append('verify'))
    monkeypatch.setattr(finish, 'recover', lambda *a: events.append('merge_recovery') or ({}, work))
    monkeypatch.setattr(finish, 'package', lambda *a: events.append('test_pack') or work / 'release')
    finish.finish('config', work, 1, 2)
    assert events == ['wait_for_cache', 'merge_recovery', 'verify', 'verify', 'test_pack']
    assert any(v['phase'] == 'waiting_for_recovery_cache' for v in writes)


def test_late_primary_cooks_cannot_replace_recovered_candidate_keys(tmp_path):
    original = tmp_path / 'original'; recovered = tmp_path / 'recovered'
    original.mkdir(); recovered.mkdir()
    finish.write(original / 'verify-report.json', [dict(base_id=1, cache_key='old'),
                                                  dict(base_id=2, cache_key='unchanged')])
    finish.write(recovered / 'trial-report.json', [dict(base_id=1, cache_key='new'),
                                                  dict(base_id=2, cache_key='unchanged')])
    finish.write(recovered / 'verify-report.json', [dict(base_id=1, cache_key='new')])
    finish.merge_primary_verification(original, recovered)
    rows = finish.read(recovered / 'verify-report.json')
    assert [(r['base_id'], r['cache_key']) for r in rows] == [(1, 'new'), (2, 'unchanged')]

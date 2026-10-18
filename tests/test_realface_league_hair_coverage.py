from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import realface_league_hair_coverage as audit
from realface_batch_inventory import read, write


def test_incremental_audit_keeps_matching_rows_and_drops_stale_ones(tmp_path, monkeypatch):
    rows = [dict(base_id=i, name=str(i), status='prepared', cache_key='mesh-'+str(i),
                 folder=str(tmp_path/str(i))) for i in (1,2,3)]
    write(tmp_path/'prepare-report.json', rows)
    write(tmp_path/'hair-visibility/report.json', [
        dict(base_id=1, audit_key='mesh-1', status='audited', retained=True),
        dict(base_id=3, audit_key='superseded', status='audited')])
    monkeypatch.setattr(audit, 'sha', lambda _: 'code')
    monkeypatch.setattr(audit, 'key_of', lambda value: value['prepared'])
    monkeypatch.setattr(audit, 'valid_prepared_cache', lambda *_: True)
    calls = []

    class Worker:
        def __init__(self, *_args, **_kwargs): pass
        def __call__(self, job_path, _log):
            job = read(job_path)
            row = job['row']
            calls.append(row['base_id'])
            write(Path(job['folder'])/'coverage.json', dict(base_id=row['base_id'],
                cache_key=row['cache_key'], diagnostic_only=True, visual_approval=False))
        def close(self): pass

    monkeypatch.setattr(audit, 'PreparationProcess', Worker)
    result = audit.run(dict(work_dir=str(tmp_path), fast_raster='unused', blender='unused'), 1, {2})
    assert calls == [2]
    assert {r['base_id'] for r in result} == {1,2}
    assert next(r for r in result if r['base_id']==1)['retained']
    assert not next(r for r in result if r['base_id']==2)['visual_approval']


def test_unknown_selection_does_not_start_workers(tmp_path, monkeypatch):
    write(tmp_path/'prepare-report.json', [])
    monkeypatch.setattr(audit, 'sha', lambda _: 'code')
    with pytest.raises(ValueError, match='prepared'):
        audit.run(dict(work_dir=str(tmp_path), fast_raster='unused'), selected={99})

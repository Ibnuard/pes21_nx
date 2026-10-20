"""Inspection bookkeeping must not promote stale or uninspected previews."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from realface_batch_inventory import read, write
from realface_pipeline import sha
import realface_review_progress as review


def fixture(tmp_path, views=('front',), count=2):
    rows = [dict(base_id=b, native_player_id=b+100, fingerprint='owner-'+str(b),
                 cache_key='prepared-'+str(b), cooked_cache_key='cooked-'+str(b),
                 status='validated') for b in range(1, count+1)]
    write(tmp_path/'verify-report.json', rows)
    write(tmp_path/'prepare-report.json', [dict(r, status='prepared') for r in rows])
    folder = tmp_path/'review/front/current'; folder.mkdir(parents=True)
    pages = (count+max(1, 8//len(views))*6-1)//(max(1, 8//len(views))*6)
    sheets = []
    for page in range(pages):
        sheet = folder/('sheet-%02d.png'%(page+1)); sheet.write_bytes(b'generated-sheet')
        sheets.append(str(sheet))
    for row in rows:
        for view in views:
            image = folder/(str(row['base_id'])+'-'+view+'.png'); image.write_bytes(b'generated-image')
            write(image.with_suffix('.json'), dict(prepared_key=row['cache_key'],
                cooked_key=row['cooked_cache_key'], view=view, image_sha256=sha(image),
                renderer_sha256=sha(review.HERE/'blender_preview_realface.py')))
    write(folder/'PROVENANCE.json', dict(stage='cooked', views=list(views),
        sheets=sheets, players=[dict(base_id=r['base_id']) for r in rows]))
    seal(folder)
    return dict(work_dir=str(tmp_path)), [Path(p) for p in sheets], rows


def seal(folder):
    write(folder/'PREVIEW-COMPLETE.json', dict(hashes={str(p): sha(p)
        for p in folder.iterdir() if p.name != 'PREVIEW-COMPLETE.json'}))


def test_record_only_explicit_sheet_and_never_final_acceptance(tmp_path):
    config, sheets, _ = fixture(tmp_path, ('front', 'left', 'right', 'above'), 13)
    assert len(sheets) == 2
    result = review.record(config, [sheets[1]], 'Inspected only the last four-view head.', [13])
    assert result == dict(inspected_front_heads=1, inspected_images=4,
                          superseded_images=0, final_acceptance=False)
    progress = read(tmp_path/'VISUAL-REVIEW-PROGRESS.json')
    assert {r['base_id'] for r in progress['images']} == {13}
    assert progress['complete'] is False and progress['pending_detail_base_ids'] == [13]
    pending = review.status(config)['pending_sheets']
    assert len(pending) == 1 and pending[0]['uninspected_images'] == 48
    assert not (tmp_path/'VISUAL-REVIEW.json').exists()


@pytest.mark.parametrize('change', ['pixels', 'cooked_key', 'source_only', 'batch_hash'])
def test_changed_preview_cannot_be_recorded(tmp_path, change):
    config, sheets, _ = fixture(tmp_path)
    folder = sheets[0].parent; image = folder/'1-front.png'; proof = image.with_suffix('.json')
    if change == 'pixels':
        image.write_bytes(b'changed-image'); seal(folder)
    elif change == 'cooked_key':
        data = read(proof); data['cooked_key'] = 'other-cook'; write(proof, data); seal(folder)
    elif change == 'source_only':
        data = read(folder/'PROVENANCE.json'); data['stage'] = 'source'
        write(folder/'PROVENANCE.json', data); seal(folder)
    else:
        sheets[0].write_bytes(b'changed-sheet')
    with pytest.raises(ValueError):
        review.record(config, sheets, 'Must not bless this changed preview.')
    assert not (tmp_path/'VISUAL-REVIEW-PROGRESS.json').exists()


def test_old_inspection_does_not_carry_to_a_different_cook(tmp_path):
    config, sheets, rows = fixture(tmp_path)
    review.record(config, sheets, 'Actually inspected the original sheet.')
    rows[0]['cooked_cache_key'] = 'new-cook'
    write(tmp_path/'verify-report.json', rows)
    snapshot = review.status(config)
    assert snapshot['inspected_front_heads'] == 1
    assert snapshot['stale_inspection_images'] == 1


def test_identity_change_and_missing_attestation_fail(tmp_path):
    config, sheets, rows = fixture(tmp_path)
    with pytest.raises(ValueError, match='finding'):
        review.record(config, sheets, '')
    rows[0]['fingerprint'] = 'different-owner'
    write(tmp_path/'verify-report.json', rows)
    with pytest.raises(ValueError, match='identity'):
        review.record(config, sheets, 'Should fail ownership checks.')


@pytest.mark.parametrize('action', ['details', 'source_comparisons'])
def test_flagged_render_cannot_start_beside_the_active_runner(tmp_path, monkeypatch, action):
    if sys.platform != 'win32':
        pytest.skip('Production process lock uses Windows msvcrt')
    from realface_league_balanced import exclusive
    from realface_preview_process import PreviewProcess
    config, _, _ = fixture(tmp_path)
    monkeypatch.setattr(PreviewProcess, '__enter__', lambda self: pytest.fail('Duplicate worker started'))
    with exclusive(tmp_path):
        with pytest.raises(RuntimeError, match='already active'):
            if action == 'details':
                review.render_details(config)
            else:
                review.render_comparisons(config, [1])


def test_source_comparison_request_is_pending_not_inspected(tmp_path):
    config, sheets, _ = fixture(tmp_path)
    review.record(config, sheets, 'Actually inspected these fronts; source check pending.', source_pending=[1])
    progress = read(tmp_path/'VISUAL-REVIEW-PROGRESS.json')
    assert progress['source_comparison_pending_base_ids'] == [1]
    assert progress['complete'] is False and progress['pending_detail_base_ids'] == []
    assert review.status(config)['source_comparison_pending_base_ids'] == [1]


@pytest.mark.parametrize('field', ['pending_detail_base_ids', 'source_comparison_pending_base_ids'])
def test_legacy_out_of_cohort_request_is_reported_and_rejected_before_hashing(tmp_path, monkeypatch, field):
    config, sheets, _ = fixture(tmp_path)
    progress = dict(images=[], sheets=[], findings=[], pending_detail_base_ids=[],
                    source_comparison_pending_base_ids=[])
    progress[field] = [999]
    write(tmp_path/'VISUAL-REVIEW-PROGRESS.json', progress)
    assert review.status(config)['invalid_pending_base_ids'] == [999]
    monkeypatch.setattr(review, 'current_images', lambda *a: pytest.fail('Hashed images before rejecting an invalid request'))
    with pytest.raises(ValueError, match=r'outside cooked cohort: \[999\]'):
        review.record(config, sheets, 'Previously viewed sheets do not authorize an unowned review ID.')
    assert read(tmp_path/'VISUAL-REVIEW-PROGRESS.json') == progress


def test_comparison_cannot_use_a_player_outside_the_current_cohort(tmp_path, monkeypatch):
    from contextlib import nullcontext
    import realface_league_balanced
    from realface_preview_process import PreviewProcess
    config, _, _ = fixture(tmp_path)
    monkeypatch.setattr(realface_league_balanced, 'exclusive', lambda _: nullcontext())
    monkeypatch.setattr(PreviewProcess, '__enter__', lambda self: pytest.fail('Unexpected worker'))
    with pytest.raises(ValueError, match='inside the cooked cohort'):
        review.render_comparisons(config, [999])


def test_comparison_batches_are_serial_and_do_not_mark_inspection(tmp_path, monkeypatch):
    from contextlib import nullcontext
    import realface_league_balanced
    import realface_lite
    import realface_league_preview
    import realface_preview_process
    config, _, rows = fixture(tmp_path, count=25)
    config['blender'] = 'unused'
    monkeypatch.setattr(realface_league_balanced, 'exclusive', lambda _: nullcontext())
    monkeypatch.setattr(realface_lite, 'sources', lambda _: [dict(r, input_hashes={'own-source': str(r['base_id'])}) for r in rows])
    workers, calls = [], []
    class Worker:
        def __init__(self, _): workers.append(self)
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def render(_, stage, selected, limit, views, output, render_worker):
        calls.append((stage, selected, render_worker))
        assert limit <= 12 and views == ('front',)
        write(output/'PROVENANCE.json', dict(sheets=[str(output/'sheet-01.png')]))
    monkeypatch.setattr(realface_preview_process, 'PreviewProcess', Worker)
    monkeypatch.setattr(realface_league_preview, 'preview', render)
    result = review.render_comparisons(config, list(range(1, 26)))
    assert len(workers) == 1 and len(calls) == 6
    assert all(worker is workers[0] for _, _, worker in calls)
    assert all(stage in ('source', 'prepared') for stage, _, _ in calls)
    assert not result['final_acceptance'] and not result['valid_for_cooked_acceptance']
    assert not result['inspected_automatically']
    assert len(result['current_cooked_fronts']) == 25
    assert not (tmp_path/'VISUAL-REVIEW-PROGRESS.json').exists()
    assert not (tmp_path/'VISUAL-REVIEW.json').exists()


@pytest.mark.parametrize('failure', ['source_identity', 'missing_cooked_front'])
def test_comparison_refuses_unbound_source_or_missing_current_reference(tmp_path, monkeypatch, failure):
    from contextlib import nullcontext
    import realface_league_balanced
    import realface_lite
    from realface_preview_process import PreviewProcess
    config, sheets, rows = fixture(tmp_path)
    source = dict(rows[0], input_hashes={'own-source': 'hash'})
    if failure == 'source_identity':
        source['fingerprint'] = 'different-owner'
    else:
        (sheets[0].parent/'1-front.png').unlink()
    monkeypatch.setattr(realface_league_balanced, 'exclusive', lambda _: nullcontext())
    monkeypatch.setattr(realface_lite, 'sources', lambda _: [source])
    monkeypatch.setattr(PreviewProcess, '__enter__', lambda self: pytest.fail('Unexpected worker'))
    with pytest.raises(ValueError, match='identity differs|Current cooked front'):
        review.render_comparisons(config, [1])

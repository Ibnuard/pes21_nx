import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_batch_inventory import read, write
from realface_native_hair_screen_review import record
from realface_pipeline import sha


def fixture(tmp_path):
    report = tmp_path / 'snapshot.json'; screen = tmp_path / 'screen'; screen.mkdir()
    rejects = tmp_path / 'VISUAL-REJECT.json'
    write(report, [dict(base_id=10, name='Authored fixture', cache_key='candidate')])
    (screen / '10.png').write_bytes(b'authored image fixture')
    (screen / 'sheet-01.png').write_bytes(b'authored contact sheet fixture')
    write(screen / '10.json', dict(candidate_key='candidate', image_sha256=sha(screen / '10.png')))
    return report, screen, rejects


def test_repeated_screen_does_not_clear_an_observed_defect(tmp_path):
    report, screen, rejects = fixture(tmp_path)
    record(report, screen, rejects, 1, {10: 'Visible scalp gap'})
    result = record(report, screen, rejects, 1, {})
    assert result == dict(screened=1, known_visual_rejects=1, approved=False)
    assert read(rejects)[0]['reason'] == 'Visible scalp gap'
    checked = read(screen / 'REVIEW.json')['pages']['1']['players'][0]
    assert checked['front_major_defect_observed'] and not checked['full_visual_approval']


def test_tampered_image_cannot_publish_review_or_rejection(tmp_path):
    report, screen, rejects = fixture(tmp_path)
    (screen / '10.png').write_bytes(b'changed image')
    with pytest.raises(ValueError, match='Rendered image'):
        record(report, screen, rejects, 1, {10: 'Defect'})
    assert not rejects.exists() and not (screen / 'REVIEW.json').exists()


def test_changed_snapshot_cannot_reuse_old_review(tmp_path):
    report, screen, rejects = fixture(tmp_path)
    record(report, screen, rejects, 1, {})
    write(report, [dict(base_id=10, name='Changed fixture', cache_key='candidate')])
    with pytest.raises(ValueError, match='snapshot changed'):
        record(report, screen, rejects, 1, {})


def test_wrong_page_or_empty_reason_is_rejected(tmp_path):
    report, screen, rejects = fixture(tmp_path)
    for page, notes in [(0, {}), (2, {}), (1, {11: 'Wrong player'}), (1, {10: ' '})]:
        with pytest.raises(ValueError):
            record(report, screen, rejects, page, notes)
    assert not rejects.exists()

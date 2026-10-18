import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_batch_inventory import write
from realface_native_hair_screen_gate import require_screened
from realface_native_hair_screen_review import record
from realface_pipeline import sha


def evidence(tmp_path, reject=False):
    report = tmp_path / 'snapshot.json'; screen = tmp_path / 'screen'; screen.mkdir()
    rows = [dict(base_id=10, name='Authored fixture', cache_key='candidate')]
    write(report, rows)
    (screen / '10.png').write_bytes(b'authored image fixture')
    (screen / 'sheet-01.png').write_bytes(b'authored sheet fixture')
    write(screen / '10.json', dict(candidate_key='candidate', image_sha256=sha(screen / '10.png'), view='front'))
    record(report, screen, tmp_path / 'rejects.json', 1, {10: 'Visible gap'} if reject else {})
    return rows, [dict(report=str(report), screen_dir=str(screen))]


def test_front_screen_gate_records_coverage_without_appearance_or_fps_approval(tmp_path):
    rows, specifications = evidence(tmp_path)
    proof = require_screened(rows, specifications)
    assert proof['selected_heads'] == 1 and proof['scope'] == 'front_screen_only'
    assert not proof['full_visual_approval'] and not proof['hardware_profiled']


def test_new_or_changed_candidate_cannot_use_old_front_screen(tmp_path):
    rows, specifications = evidence(tmp_path)
    for candidate in [dict(rows[0], cache_key='replacement'), dict(rows[0], base_id=11)]:
        with pytest.raises(ValueError, match='no current front-screen review'):
            require_screened([candidate], specifications)


def test_observed_defect_must_be_removed_from_selected_package(tmp_path):
    rows, specifications = evidence(tmp_path, reject=True)
    with pytest.raises(ValueError, match='defect is still selected'):
        require_screened(rows, specifications)
    assert require_screened([], specifications)['selected_heads'] == 0


def test_changed_image_is_rejected_even_when_review_is_unchanged(tmp_path):
    rows, specifications = evidence(tmp_path)
    (Path(specifications[0]['screen_dir']) / '10.png').write_bytes(b'changed image')
    with pytest.raises(ValueError, match='image/provenance changed'):
        require_screened(rows, specifications)

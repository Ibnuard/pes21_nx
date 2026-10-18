import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from audit_realface_match_budget import audit


def inputs():
    owner = dict(base_id=9, native_player_id=20, team_ids=[100, 108], status='candidate_pending_device')
    release = dict(players=[owner, dict(base_id=10, native_player_id=21, team_ids=[100], status='missing_source')],
                   teams=[dict(team_id=100), dict(team_id=108)])
    rows = [dict(base_id=9, native_player_id=20, status='validated', lite_triangles=2440,
                 lite_vertices=1500, material_sections=3)]
    native = dict(meshes={'20_face': dict(lods=[dict(triangles=1156, sections=1)]),
                          '20_hair': dict(lods=[dict(triangles=200, sections=1)]),
                          '21_face': dict(lods=[dict(triangles=1158, sections=1)])})
    return release, rows, native


def test_shared_roster_identity_is_counted_once_and_missing_hair_is_not_zero():
    report = audit(*inputs(), {100, 108})
    assert report['players'] == 1 and report['unavailable_target_players'] == 1
    assert report['native_reference']['pairs'] == 1
    assert report['native_reference']['triangles']['median'] == 1356
    assert report['native_slot_pairs_present'] == 1 and not report['hardware_profiled']


@pytest.mark.parametrize('change', ['duplicate', 'mismatch', 'missing', 'held'])
def test_invalid_status_cannot_produce_a_clean_budget_report(change):
    release, rows, native = inputs()
    if change == 'duplicate': rows.append(dict(rows[0]))
    if change == 'mismatch': rows[0]['native_player_id'] = 99
    if change == 'missing': rows.clear()
    if change == 'held': rows[0]['status'] = 'held_geometry'
    with pytest.raises(ValueError): audit(release, rows, native, {100})

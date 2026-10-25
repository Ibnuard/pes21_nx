from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_skin_scope import diagnose_scope, effective_body_skin


PALETTE = {i: [240 - i * 25, 210 - i * 25, 190 - i * 25] for i in range(1, 7)}


def inputs(selector=7, nearest=2):
    identity = dict(base_id=12, native_player_id=102, fingerprint='own-identity', name='Player')
    row = dict(identity, status='held_measurement', current_skin=selector,
               profile_sha256='profile', texture_sha256='texture')
    proof = dict(identity, status='provenance_verified', source_profile_sha256='profile',
                 source_texture_sha256='texture', neck=dict(
                     source_rgb=[PALETTE[nearest]] * 3, cooked_rgb=[PALETTE[nearest]] * 3,
                     max_delta_e76=0, error_limit=4, palette_recommendation_stable=True))
    return [dict(state='audit_complete', players=[row]),
            dict(state='provenance_complete', players_checked=1, players=[proof]),
            dict(state='native_body_default_and_missing_row_diagnosed',
                 body_static_semantics={'0': 1, '7': 6}, missing_players=[])]


@pytest.mark.parametrize('raw,expected', list(enumerate([1, 1, 2, 3, 4, 5, 6, 6])))
def test_exact_native_body_clamp(raw, expected):
    assert effective_body_skin(raw) == expected


@pytest.mark.parametrize('bad', [-1, 8, None, True, '7'])
def test_invalid_selectors_rejected(bad):
    with pytest.raises(ValueError):
        effective_body_skin(bad)


def test_default_mismatch_queues_review_and_never_patches():
    report = diagnose_scope(*inputs(), PALETTE, [], set())
    player = report['players'][0]
    assert player['effective_body_skin'] == 6
    assert player['status'] == 'pending_cooked_palette_review'
    assert not player['terminal'] and not player['automatic_patch']
    assert report['pending'] == 1 and not report['scope_terminal']


def test_default_nearest_is_preserved_using_effective_body_not_face_clamp():
    report = diagnose_scope(*inputs(selector=7, nearest=6), PALETTE, [], set())
    assert report['scope_terminal']
    assert report['players'][0]['status'] == 'retained_effective_nearest'


def test_small_colour_difference_is_a_specific_retention_not_generic_hold():
    a, p, n = inputs(selector=2, nearest=1)
    palette = dict(PALETTE)
    palette[2] = [x - 1 for x in palette[1]]
    report = diagnose_scope(a, p, n, palette, [], set())
    row = report['players'][0]
    assert row['status'] == 'retained_bounded_palette_difference'
    assert row['cooked']['improvement'] < 4 and row['terminal']
    assert 'gain is only' in row['reason']


@pytest.mark.parametrize('change', ['identity', 'profile', 'coverage', 'native_face_clamp'])
def test_changed_identity_provenance_or_consumer_rejected(change):
    a, p, n = inputs()
    if change == 'identity':
        p['players'][0]['fingerprint'] = 'other-person'
    elif change == 'profile':
        p['players'][0]['source_profile_sha256'] = 'different-profile'
    elif change == 'coverage':
        p['players'] = []
    else:
        n['body_static_semantics']['7'] = 1
    with pytest.raises(ValueError):
        diagnose_scope(a, p, n, PALETTE, [], set())


def missing_inputs():
    a, p, n = inputs()
    a['players'][0]['status'] = 'held_missing_appearance'
    row = deepcopy(a['players'][0])
    row.update(diagnosis='terminal_current_schema_no_existing_canonical_or_native_masked_appearance_row',
               identity_exact=True, appearance_present=False, row_manufacture_allowed=False,
               diagnostic_keys={k: dict(appearance_present=False) for k in
                                ('exact_native', 'base_id', 'editwork_actual_keymask_f007ffff')},
               specific_reason='Exact native 102 and its actual masked lookup are absent')
    n['missing_players'] = [row]
    return a, p, n


def test_missing_rows_require_own_native_schema_proof():
    a, p, n = missing_inputs()
    report = diagnose_scope(a, p, n, PALETTE, [], set())
    assert report['players'][0]['status'] == 'held_native_missing_appearance'
    assert report['scope_terminal']
    n['missing_players'][0]['diagnostic_keys']['base_id']['appearance_present'] = True
    with pytest.raises(ValueError):
        diagnose_scope(a, p, n, PALETTE, [], set())


def test_protected_and_staged_owners_cannot_be_silently_overridden():
    a, p, n = inputs()
    report = diagnose_scope(a, p, n, PALETTE, [], {12})
    assert report['players'][0]['status'] == 'preserved_explicit_policy'
    policy = dict(base_id=12, native_player_id=102, fingerprint='own-identity',
                  skin=2, reason='Reviewed own texture')
    report = diagnose_scope(a, p, n, PALETTE, [policy], set())
    assert report['players'][0]['status'] == 'staged_reviewed_correction'
    with pytest.raises(ValueError):
        diagnose_scope(a, p, n, PALETTE, [policy], {12})
    policy['native_player_id'] = 103
    with pytest.raises(ValueError):
        diagnose_scope(a, p, n, PALETTE, [policy], set())

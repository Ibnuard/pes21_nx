import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_source_recovery import match_alias
from realface_joined_recovery import eligible, check_tools, tool_snapshot
from realface_incremental_candidate import select_new


def identity():
    return dict(base_id=10, native_player_id=90, fingerprint='current-owner', name='Ivan Player',
                height=185, age=25, country=1, foot=0, position=0)


def alias_fixture():
    return (dict(player_id=10, name='Pichu Player'),
            dict(height=185, age=25, country=1, foot=0, position=0, row_sha256='source-row'),
            dict(base_id=10, names=['Ivan Player', 'Pichu Player'], evidence=['https://club.example/profile'], note='Nickname'))


def test_alias_still_requires_same_base_id_biography_and_fingerprint():
    owner = identity(); candidate, bio, alias = alias_fixture()
    assert match_alias(owner, candidate, bio, alias)['canonical_fingerprint'] == 'current-owner'
    assert match_alias(owner, dict(candidate, player_id=90), bio, alias) is None
    for changed in (dict(bio, height=189), dict(bio, age=29), dict(bio, foot=1), dict(bio, position=5)):
        assert match_alias(owner, candidate, changed, alias) is None
    assert match_alias(dict(owner, fingerprint=None), candidate, bio, alias) is None
    assert match_alias(dict(owner, name='Unrelated Player'), candidate, bio, alias) is None


def test_country_disagreement_requires_exact_documented_pair():
    candidate, bio, alias = alias_fixture(); owner = identity()
    assert match_alias(owner, candidate, dict(bio, country=2), alias) is None
    proof = match_alias(owner, candidate, dict(bio, country=2), dict(alias, country_pair=[1, 2]))
    assert proof and not proof['runtime_identity_changed']
    assert match_alias(owner, candidate, dict(bio, country=3), dict(alias, country_pair=[1, 2])) is None
    assert match_alias(owner, candidate, bio, dict(alias, evidence=[])) is None


def test_preparation_never_replaces_baseline_or_reuses_mismatched_owner():
    owner = identity(); row = dict(owner, status='prepared')
    assert eligible(row, owner, set())
    assert not eligible(row, owner, {10})
    assert not eligible(dict(row, reuse_cooked={'key': 'accepted'}), owner, set())
    assert not eligible(row, dict(owner, fingerprint='other-player'), set())


def test_incremental_package_rejects_baseline_collision_and_unverified_heads():
    owner = identity(); row = dict(owner, status='validated', composite_geometry_pass=True)
    baseline = dict(players_in_package=[dict(base_id=20, native_player_id=100)])
    assert select_new([row], baseline, {10: owner}) == [row]
    for bad in (dict(row, base_id=20), dict(row, native_player_id=100)):
        with pytest.raises(ValueError, match='baseline'):
            select_new([bad], baseline, {10: owner})
    with pytest.raises(ValueError, match='canonical fingerprint'):
        select_new([dict(row, fingerprint='stale')], baseline, {10: owner})
    with pytest.raises(ValueError, match='cooked validation'):
        select_new([dict(row, status='prepared')], baseline, {10: owner})
    with pytest.raises(ValueError, match='geometry evidence'):
        select_new([dict(row, composite_geometry_pass=False)], baseline, {10: owner})
    with pytest.raises(ValueError, match='Duplicate|baseline'):
        select_new([row, row], baseline, {10: owner})


def test_batched_tool_hashing_detects_executable_change(tmp_path):
    executable = tmp_path / 'tool'; executable.write_bytes(b'authored executable fixture')
    snapshot = tool_snapshot({'blender': str(executable)})
    check_tools(snapshot)
    executable.write_bytes(b'changed executable')
    with pytest.raises(ValueError, match='Tool changed'):
        check_tools(snapshot)


def test_coverage_keeps_unresolved_sources_and_rejects_false_recovery():
    from realface_incremental_coverage import summarize
    one = identity(); two = dict(one, base_id=20, native_player_id=100)
    old = dict(maximum_head_triangles=2000, roster_identities=2, teams=[], players_in_package=[],
               players=[dict(one, status='source_unresolved'), dict(two, status='source_unresolved')])
    inv = dict(players=[dict(one, status='source_ready'), dict(two, status='missing_source')])
    candidate = dict(one, cache_key='new', status='candidate_visual_hold', triangles=1990)
    cooked = dict(candidate, status='validated')
    report, selected = summarize(old, inv, [('trial', [candidate])], [], [cooked])
    assert report['counts'] == {'recovered_cooked_visual_hold': 1, 'source_unresolved': 1}
    assert selected == [cooked]
    assert old['players'][0]['status'] == 'source_unresolved'
    with pytest.raises(ValueError, match='visually rejected'):
        summarize(old, inv, [('trial', [candidate])], [dict(candidate, reason='Visible hole')], [cooked])
    with pytest.raises(ValueError, match='geometry report'):
        summarize(old, inv, [], [], [cooked])
    with pytest.raises(ValueError, match='complete unique roster'):
        summarize(old, dict(players=[inv['players'][0]]), [], [], [])

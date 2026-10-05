from __future__ import annotations

import copy
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from restore_fl26_presentation import restore_kit_flags, sha, DT120, DT200, DT240


def team_row(team, flag):
    row = bytearray(1532)
    struct.pack_into('<I', row, 8, team)
    row[84] = flag
    row[100:104] = b'TEAM'
    return bytes(row)


@pytest.fixture
def fixture():
    assets = {}
    migrated = []
    for team in (137, 138):
        kits, previews = [], []
        for kind, suffix in (('1st', 'p1'), ('2nd', 'p2'), ('GK1st', 'g1')):
            member = f'common/etc/uniform/team/{team}/{team}_DEF_{kind}_realUni.bin'
            assets[DT200, member] = bytes(120)
            kit = dict(kind=kind, descriptor_target=member, assets=[])
            for role, folder, ending in (('body', 'D', ''), ('back', 'Font', '_back')):
                member = f'Models/character/Uniform16/{folder}/u{team:04d}{suffix}{ending}.png'
                payload = member.encode()
                assets[DT120, member] = payload
                kit['assets'].append(dict(role=role, target_member=member, target_sha256=sha(payload)))
            if suffix != 'g1':
                member = f'common/render/thumbnail/uniform/{team}_{suffix}.png'
                payload = member.encode()
                assets[DT240, member] = payload
                kit['preview_members'] = [member]
                previews.append(dict(suffix=suffix, members=[member], sha256=sha(payload)))
            kits.append(kit)
        migrated.append(dict(team_id=team, physical_team_id=team, kits=kits, previews=previews))
    catalog = {'teams': [dict(team_id=t, physical_team_id=t, display_name=f'Team {t}') for t in (137, 138)]}
    return dict(raw=team_row(137, 0) + team_row(138, 12) + team_row(999, 0),
                reference_raw=team_row(137, 15) + team_row(138, 15) + team_row(999, 15),
                catalog=catalog, reference_catalog=copy.deepcopy(catalog),
                reference_report={'migrated_teams': migrated},
                current_assets=copy.deepcopy(assets), reference_assets=assets)


def restore(fixture, selected=None):
    args = {key: fixture[key] for key in ('raw', 'reference_raw', 'catalog', 'reference_catalog', 'reference_report')}
    return restore_kit_flags(**args, selected=selected,
        read_current=lambda a, m: fixture['current_assets'][a, m],
        read_reference=lambda a, m: fixture['reference_assets'][a, m])


def test_restore_only_verified_active_flags_and_preserve_every_other_byte(fixture):
    patched, changes, held = restore(fixture)
    assert [i for i, (a, b) in enumerate(zip(fixture['raw'], patched)) if a != b] == [84, 1532 + 84]
    assert [c['team_id'] for c in changes] == [137, 138]
    assert all(len(c['verified_assets']) == 11 for c in changes)
    assert held == []
    fixture['raw'] = patched
    assert restore(fixture) == (patched, [], [])


def test_explicit_team_scope_does_not_restore_another_team(fixture):
    patched, changes, held = restore(fixture, {137})
    assert patched[84] == 15 and patched[1532 + 84] == 12
    assert [c['team_id'] for c in changes] == [137] and not held


@pytest.mark.parametrize('problem', ['mapping', 'identity', 'descriptor', 'texture', 'preview', 'missing', 'report_hash'])
def test_hold_unproven_team_instead_of_inheriting_donor_or_wrong_assets(fixture, problem):
    report = fixture['reference_report']['migrated_teams'][0]
    if problem == 'mapping':
        fixture['reference_catalog']['teams'][0]['physical_team_id'] = 999
    elif problem == 'identity':
        raw = bytearray(fixture['raw'])
        raw[100] ^= 1
        fixture['raw'] = bytes(raw)
    elif problem == 'report_hash':
        report['kits'][0]['assets'][0]['target_sha256'] = '0' * 64
    else:
        if problem == 'descriptor':
            key = (DT200, report['kits'][0]['descriptor_target'])
        elif problem == 'preview':
            key = (DT240, report['previews'][0]['members'][0])
        else:
            key = (DT120, report['kits'][0]['assets'][0]['target_member'])
        if problem == 'missing':
            del fixture['current_assets'][key]
        else:
            fixture['current_assets'][key] = b'changed'
    patched, changed, held = restore(fixture)
    assert patched[84] == 0
    assert [c['team_id'] for c in changed] == [138]
    assert [c['team_id'] for c in held] == [137]


def test_incomplete_goalkeeper_set_is_held(fixture):
    fixture['reference_report']['migrated_teams'][0]['kits'].pop()
    _, changed, held = restore(fixture)
    assert [c['team_id'] for c in changed] == [138]
    assert 'three complete kits' in held[0]['reason']


def test_duplicate_team_rows_are_rejected(fixture):
    fixture['raw'] += team_row(137, 0)
    with pytest.raises(ValueError, match='duplicate'):
        restore(fixture)

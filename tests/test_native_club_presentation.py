from __future__ import annotations

import copy
from pathlib import Path
import struct
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_native_club_presentation import complete_real_family, crest_families
from build_eng_spa_license_pack import fixed_ascii, set_fixed_ascii
from stage_native_club_presentation import (
    all_verified_policy, identity_proof, load_crest, patch_identity,
)
from stage_team_crest_override import native_crest_plan, native_png


def row(tid, name, code='PAL'):
    value = bytearray(1532)
    struct.pack_into('<I', value, 8, tid)
    value[84] = 15
    value[108:112] = b'KEEP'
    set_fixed_ascii(value, 368, 70, name)
    for offset in (882, 1382):
        set_fixed_ascii(value, offset, 4, code)
    return bytes(value)


@pytest.fixture
def inputs():
    raw = row(137, 'BARRA FUNDA V') + row(138, 'OTHER', 'OTH')
    fl = row(137, 'SE Palmeiras')
    cat = dict(content_id='old', categories=[dict(label='PRESERVE')], teams=[
        dict(team_id=137, physical_team_id=137, display_name='SE PALMEIRAS', badge_slot=94),
        dict(team_id=138, physical_team_id=138, display_name='OTHER', badge_slot=95)])
    policy = dict(schema_version=1, teams=[dict(team_id=137, physical_team_id=137,
        expected_native_names=['BARRA FUNDA V', 'PALMEIRAS'],
        expected_selector_names=['SE PALMEIRAS', 'PALMEIRAS'],
        expected_fl26_name='SE Palmeiras', official_name='PALMEIRAS', short_code='PAL')])
    return raw, fl, cat, policy


def test_scoped_text_patch_preserves_kits_mappings_and_unrelated_data(inputs):
    raw, fl, cat, policy = inputs
    unchanged = copy.deepcopy(cat)
    patched, updated, report = patch_identity(*inputs)
    assert cat == unchanged
    assert patched[1532:] == raw[1532:]
    assert fixed_ascii(patched, 368, 70) == 'PALMEIRAS'
    allowed = set(range(368, 438)) | set(range(882, 886)) | set(range(1382, 1386))
    assert all(i in allowed for i, (a, b) in enumerate(zip(raw, patched)) if a != b)
    assert patched[84] == 15 and updated['categories'] == cat['categories']
    assert updated['teams'][0] == dict(cat['teams'][0], display_name='PALMEIRAS')
    assert updated['teams'][1] == cat['teams'][1]
    assert report['unrelated_rows_byte_identical'] == 1
    assert patch_identity(patched, fl, updated, policy)[0] == patched


@pytest.mark.parametrize('problem', ['native_name', 'fl_name', 'fl_code', 'mapping',
                                    'selector_name', 'duplicate', 'native_code'])
def test_rejects_reused_numeric_ids_without_identity_proof(inputs, problem):
    raw, fl, cat, policy = copy.deepcopy(inputs)
    if problem == 'native_name':
        raw = row(137, 'WRONG TEAM')
    elif problem == 'fl_name':
        fl = row(137, 'WRONG TEAM')
    elif problem == 'fl_code':
        fl = row(137, 'SE Palmeiras', 'BAD')
    elif problem == 'mapping':
        cat['teams'][0]['physical_team_id'] = 999
    elif problem == 'selector_name':
        cat['teams'][0]['display_name'] = 'WRONG TEAM'
    elif problem == 'duplicate':
        policy['teams'] *= 2
    elif problem == 'native_code':
        raw = row(137, 'BARRA FUNDA V', 'BAD')
    with pytest.raises(ValueError):
        patch_identity(raw, fl, cat, policy)


def test_fake_only_crest_gets_all_real_aliases_and_not_another_team():
    prefix = 'common/render/symbol/flag/e_000137_'
    index = {prefix + 'f_l.png': {}, 'common/render/symbol/emblemLc/emb_0137_b.png': {}}
    plan = native_crest_plan(index, 137)
    assert {prefix + f + s + '.png' for f in ('f', 'r') for s in ('', '_l', '_s')} <= set(plan)
    assert len(plan) == 7
    assert sorted(plan.values()) == [64, 64, 128, 128, 128, 256, 256]
    with pytest.raises(ValueError, match='no existing'):
        native_crest_plan(index, 138)


def test_audit_accepts_contrast_licensed_variants_and_unused_fake_absence():
    prefix = 'common/render/symbol/flag/e_000100_'
    index = {prefix + f + s + '.png': {} for f in ('r_b', 'r_w') for s in ('', '_l', '_s')}
    families = crest_families(index, 100)
    assert complete_real_family(families)
    assert set(families) == {'r_b', 'r_w'}
    assert len(native_crest_plan(index, 100)) == 12
    del families['r_w']['_s']
    assert not complete_real_family(families)
    assert not complete_real_family(crest_families({prefix + 'f_l.png': {}}, 100))


def test_all_team_policy_holds_reused_id_even_when_fl26_has_assets(inputs):
    raw, fl, cat, policy = inputs
    raw += row(199, 'PES UNITED', 'PES')
    fl += row(199, 'Zalgiris Vilnius', 'ZLG')
    cat['teams'].append(dict(team_id=199, physical_team_id=199, display_name='PES UNITED'))
    idx = {'common/render/symbol/flag/e_000199_r_l.png': {}}
    result, held = all_verified_policy(raw, fl, cat, policy, idx, [])
    assert [t['team_id'] for t in result['teams']] == [137]
    assert any(t['team_id'] == 199 and 'unproven' in t['reason'] for t in held)


def test_all_team_policy_accepts_actual_uppercase_source_member(inputs):
    raw, fl, cat, _ = inputs
    idx = {'common/render/symbol/flag/e_000137_R_l.png': {}}
    result, _ = all_verified_policy(raw, fl, cat, dict(teams=[]), idx, [])
    assert result['teams'][0]['crest_member'].endswith('_R_l.png')


def test_common_city_word_alone_does_not_prove_same_club():
    team = dict(team_id=1, display_name='MANCHESTER UNITED')
    assert not identity_proof(team, row(1, 'MANCHESTER UNITED', 'MUN'),
                              row(1, 'Manchester City', 'MCI'), [])
    assert identity_proof(dict(team_id=176, display_name='BLACKBURN BW'),
                          row(176, 'BLACKBURN BW', 'BLB'),
                          row(176, 'Blackburn Rovers', 'BLB'), [])


def test_transliterated_fl26_names_remain_verifiable_after_first_sync():
    fl = bytearray(row(1, 'PLACEHOLDER', 'SON'))
    name = 'Sønderjyske Fodbold'.encode('utf-8')
    fl[368:438] = name + bytes(70 - len(name))
    assert identity_proof(dict(team_id=1, display_name='SONDERJYSKE FODBOLD'),
                          row(1, 'SONDERJYSKE FODBOLD', 'SON'), bytes(fl), [])


def test_crest_source_hash_size_and_transparency_gates():
    image = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    image.paste((20, 210, 80, 255), (16, 16, 240, 240))
    encoded = native_png(image, 256)
    assert load_crest(encoded).tobytes() == image.tobytes()
    with pytest.raises(ValueError, match='hash'):
        load_crest(encoded, '0' * 64)
    with pytest.raises(ValueError, match='256x256'):
        load_crest(native_png(image, 64))
    with pytest.raises(ValueError, match='transparent'):
        load_crest(native_png(Image.new('RGBA', (256, 256), 'white'), 256))

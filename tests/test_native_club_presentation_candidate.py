"""Optional binary QA of a locally staged, paired native presentation update."""
from __future__ import annotations

import os
from pathlib import Path
import re
import struct
import sys

from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from audit_native_club_presentation import audit, complete_real_family, crest_families
from build_barca_real_madrid_mobile_kit_canary import validate_cpk
from build_eng_spa_license_pack import fixed_ascii
from build_fl26_cup_catalog import index_cpk
from build_full_mobile_kit_migration import ATLAS_WIDTH, BADGE_CELL, fit_badge
from cleanse_playable_categories import RETIRED
from package_loose_update import verify_nro
from prepare_loose_cpk import read_manifest
from prepare_runtime import read_cpk_packet
from restore_fl26_presentation import (
    DT200, DT240, TEAM_MEMBER, archive_reader, read_json, sha, team_records,
)
from stage_native_club_presentation import load_crest, ROSTER, SCORERS
from stage_team_crest_override import native_png


@pytest.fixture(scope='module')
def candidate():
    value = os.environ.get('PESNX_NATIVE_PRESENTATION_CANDIDATE')
    if not value:
        pytest.skip('set PESNX_NATIVE_PRESENTATION_CANDIDATE to an ignored paired candidate')
    path = Path(value)
    report = read_json(path / 'native-presentation-report.json')
    return path, report, Path(report['source_base'])


def test_every_playable_team_audited_and_all_real_crest_gaps_resolved(candidate):
    path, report, base = candidate
    catalog = read_json(path / 'selector/catalog.json')
    before = audit(base, read_json(Path(report['source_catalog'])))
    after = audit(path, catalog)
    assert before == read_json(path / 'audit-before.json')
    assert after == read_json(path / 'audit-after.json')
    assert before['teams_checked'] == after['teams_checked'] == 394
    assert before['real_crest_gaps'] == 41 and after['real_crest_gaps'] == 0
    assert after['teams_with_errors'] == 0
    # Do not silently borrow FL26 teams for fantasy, Thai or remapped slots.
    assert len(report['held_teams']) == 18
    assert {199, 200, 1700, 1775, 17873, 18961} <= {t['team_id'] for t in report['held_teams']}


def test_only_approved_native_text_fields_change_and_all_gameplay_members_stay_identical(candidate):
    path, report, base = candidate
    old, new = archive_reader(base), archive_reader(path)
    before, after = old(DT200, TEAM_MEMBER), new(DT200, TEAM_MEMBER)
    a, b = team_records(before), team_records(after)
    targets = {t['physical_team_id']: t for t in report['source_policy']['teams']}
    assert len(before) == len(after) and a.keys() == b.keys()
    allowed = set(range(368, 438)) | set(range(882, 886)) | set(range(1382, 1386))
    for physical, original in a.items():
        if physical not in targets:
            assert original == b[physical]
            continue
        target = targets[physical]
        assert all(i in allowed for i, (x, y) in enumerate(zip(original, b[physical])) if x != y)
        assert fixed_ascii(b[physical], 368, 70) == target['official_name']
        assert [fixed_ascii(b[physical], n, 4) for n in (882, 1382)] == [target['short_code']] * 2
        assert original[84] == b[physical][84]  # All restored kits retained.
    encoded = (path / 'tables/Team.bin').read_bytes()
    checked = validate_cpk(base / 'LooseCpk' / DT200, path / 'LooseCpk' / DT200,
                          {TEAM_MEMBER: 'replace'}, {TEAM_MEMBER: encoded})
    assert checked['unrelated_members_byte_identical'] == 2839
    assert fixed_ascii(b[137], 368, 70) == 'PALMEIRAS'
    assert fixed_ascii(b[205], 368, 70) == 'MIDDLESBROUGH'


def test_every_crest_alias_has_verified_pixels_and_original_cpk_order_ids_survive(candidate):
    path, report, base = candidate
    old_index, _ = index_cpk(base / 'LooseCpk' / DT240)
    new_index, _ = index_cpk(path / 'LooseCpk' / DT240)
    read = archive_reader(path)
    payloads = {}
    for team in report['crests']:
        raw = (path / f"crest-sources/{team['team_id']}.png").read_bytes()
        assert sha(raw) == team['source_sha256']
        image = load_crest(raw)
        encoded = {size: native_png(image, size) for size in set(team['native_members'].values())}
        for name, size in team['native_members'].items():
            assert read(DT240, name) == encoded[size]
            payloads[name] = encoded[size]
        assert complete_real_family(crest_families(new_index, team['physical_team_id']))
    actions = {n: 'replace' if n in old_index else 'add' for n in payloads}
    checked = validate_cpk(base / 'LooseCpk' / DT240, path / 'LooseCpk' / DT240, actions, payloads)
    assert checked['unrelated_members_byte_identical'] == report['dt240']['unrelated_members_byte_identical']
    additions = sorted(set(new_index) - set(old_index))
    assert len(additions) == 1020
    assert list(new_index) == [*old_index, *additions]
    assert all(new_index[n]['ID'] == old_index[n]['ID'] for n in old_index)
    with (path / 'LooseCpk' / DT240).open('rb') as stream:
        assert read_cpk_packet(stream, 0, b'CPK ')[0]['Sorted'] == 0


def test_catalog_cleansing_custom_palmeiras_and_all_unrelated_atlas_cells_retained(candidate):
    path, report, _ = candidate
    before = read_json(Path(report['source_catalog']))
    after = read_json(path / 'selector/catalog.json')
    assert before['categories'] == after['categories'] and before['counts'] == after['counts']
    assert not RETIRED & {c['key'] for c in after['categories']}
    for a, b in zip(before['teams'], after['teams']):
        assert {k: v for k, v in a.items() if k != 'display_name'} == {
            k: v for k, v in b.items() if k != 'display_name'}
    old_raw = Path(report['source_atlas']).read_bytes()
    new_raw = (path / 'selector/badge_atlas.bin').read_bytes()
    size = (ATLAS_WIDTH, len(old_raw) // (ATLAS_WIDTH * 4))
    old, new = [Image.frombytes('RGBA', size, raw) for raw in (old_raw, new_raw)]
    updated = {t['badge_slot']: t for t in report['crests'] if t['selector_badge_updated']}
    assert 94 not in updated  # User-supplied Palmeiras is not replaced with FL26's logo.
    for slot in range((size[0] // BADGE_CELL) * (size[1] // BADGE_CELL)):
        x, y = (slot % 32) * BADGE_CELL, (slot // 32) * BADGE_CELL
        box = (x, y, x + BADGE_CELL, y + BADGE_CELL)
        expected = old.crop(box)
        if slot in updated:
            expected = fit_badge((path / f"crest-sources/{updated[slot]['team_id']}.png").read_bytes())
        assert new.crop(box).tobytes() == expected.tobytes()


def test_nro_contains_matching_id_atlas_and_all_394_native_mapped_names(candidate):
    path, report, base = candidate
    verify_nro(path, report['build_id'])
    from elftools.elf.elffile import ELFFile
    catalog = read_json(path / 'selector/catalog.json')
    payload = (path / 'pes21_nx.nro').read_bytes()
    expected = [(t['team_id'], t['physical_team_id'], t['display_name'], t['badge_slot'])
                for t in catalog['teams']]
    found_catalog, found_atlas = False, False
    with (path / 'pes21_nx.elf').open('rb') as stream:
        elf = ELFFile(stream)
        for symbol in elf.get_section_by_name('.symtab').iter_symbols():
            start, size = symbol['st_value'], symbol['st_size']
            if re.fullmatch(r'exhibition_team_catalog(?:\..*)?', symbol.name):
                actual = []
                for offset in range(start, start + size, 24):
                    logical, physical, name, slot = struct.unpack_from('<IIQI', payload, offset)
                    actual.append((logical, physical, payload[name:payload.index(b'\0', name)].decode('utf-8'), slot))
                assert actual == expected
                found_catalog = True
            if symbol.name == 'badge_atlas_bin':
                atlas = (path / 'selector/badge_atlas.bin').read_bytes()
                assert payload[start:start + len(atlas)] == atlas
                found_atlas = True
    assert found_catalog and found_atlas
    before, after = read_manifest(base), read_manifest(path)
    assert all(a == b for a, b in zip(before['files'], after['files']) if a['name'] not in {DT200, DT240})
    assert (path / 'selector' / SCORERS).read_bytes() == (base / 'selector' / SCORERS).read_bytes()
    assert (path / 'selector' / ROSTER).read_text(encoding='utf-8').replace(
        report['build_id'], report['base_build_id']) == (base / 'selector' / ROSTER).read_text(encoding='utf-8')

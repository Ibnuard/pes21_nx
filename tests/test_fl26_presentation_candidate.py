"""Optional read-only integration checks of an ignored restored candidate."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import struct
import sys

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_barca_real_madrid_mobile_kit_canary import validate_cpk
from build_full_mobile_kit_migration import BADGE_CELL, ATLAS_WIDTH
from cleanse_playable_categories import RETIRED
from package_loose_update import verify_nro
from prepare_loose_cpk import read_manifest, digest
from restore_fl26_presentation import (
    archive_reader, restore_kit_flags, DT200, TEAM_MEMBER,
)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def candidate():
    folder = os.environ.get('PESNX_PRESENTATION_CANDIDATE')
    if not folder:
        pytest.skip('set PESNX_PRESENTATION_CANDIDATE to an ignored restored candidate')
    path = Path(folder)
    report = read(path / 'restoration-report.json')
    return path, report, Path(report['source_base']), Path(report['source_reference'])


def test_native_flags_are_independently_reverified_and_no_other_cpk_member_changes(candidate):
    path, report, base, reference = candidate
    old, ref, new = archive_reader(base), archive_reader(reference), archive_reader(path)
    original = old(DT200, TEAM_MEMBER)
    expected, changes, held = restore_kit_flags(
        original, ref(DT200, TEAM_MEMBER), read(Path(report['source_catalog'])),
        read(reference / 'league-branding/exhibition_team_catalog.json'),
        read(reference / 'full-kit-migration-report.json'), old, ref)
    assert changes == report['changed_kit_flags'] and held == report['held_kit_flags'] == []
    assert len(changes) == 110 and any(r['team_id'] == 137 for r in changes)
    assert new(DT200, TEAM_MEMBER) == expected
    assert sum(a != b for a, b in zip(original, expected)) == 110
    encoded = (path / 'tables/Team.bin').read_bytes()
    checked = validate_cpk(base / 'LooseCpk' / DT200, path / 'LooseCpk' / DT200,
                          {TEAM_MEMBER: 'replace'}, {TEAM_MEMBER: encoded})
    assert checked['changed_members'] == [TEAM_MEMBER]
    assert checked['unrelated_members_byte_identical'] == 2839
    before, after = read_manifest(base), read_manifest(path)
    assert all(a == b for a, b in zip(before['files'], after['files']) if a['name'] != DT200)


def test_branding_retains_cleansing_team_ids_slots_and_every_unrelated_atlas_cell(candidate):
    path, report, _, reference = candidate
    before = read(Path(report['source_catalog']))
    after = read(path / 'selector/catalog.json')
    assert after['teams'] == before['teams'] and after['counts'] == before['counts']
    assert len(after['teams']) == 394 and len(after['categories']) == 27
    assert not RETIRED & {c['key'] for c in after['categories']}
    for a, b in zip(before['categories'], after['categories']):
        assert {k: v for k, v in b.items() if k not in {'label', 'football_life_brand_member'}} == {
            k: v for k, v in a.items() if k not in {'label', 'football_life_brand_member'}}
    raw = Path(report['source_atlas']).read_bytes()
    atlas = (path / 'league-branding/badge_atlas.bin').read_bytes()
    source = Image.frombytes('RGBA', (ATLAS_WIDTH, len(raw) // (ATLAS_WIDTH * 4)), raw)
    current = Image.frombytes('RGBA', source.size, atlas)
    expected = (reference / 'league-branding/badge_atlas.bin').read_bytes()
    original_fl26 = Image.frombytes('RGBA', source.size, expected)
    changed = {row['badge_slot'] for row in report['branding']['rows']}
    assert len(changed) == 18
    for slot in range((source.width // BADGE_CELL) * (source.height // BADGE_CELL)):
        x, y = (slot % 32) * BADGE_CELL, (slot // 32) * BADGE_CELL
        box = x, y, x + BADGE_CELL, y + BADGE_CELL
        expected_image = original_fl26 if slot in changed else source
        assert current.crop(box).tobytes() == expected_image.crop(box).tobytes()
    for row in report['branding']['rows']:
        category = next(c for c in after['categories'] if c['key'] == row['key'])
        assert category['label'] == row['after']
        assert digest(Path(row['logo_path'])) == row['source_sha256']


def test_rosters_and_scorer_pools_unchanged_and_nro_uses_real_branding(candidate):
    path, report, base, _ = candidate
    before = (base / 'selector/exhibition_rosters_migration_canary_generated.inc').read_text(encoding='utf-8')
    after = (path / 'selector/exhibition_rosters_migration_canary_generated.inc').read_text(encoding='utf-8')
    assert after.replace(report['build_id'], report['base_build_id']) == before
    name = 'selector/league_scorer_pool_generated.inc'
    assert (path / name).read_bytes() == (base / name).read_bytes()
    verify_nro(path, report['build_id'])
    from elftools.elf.elffile import ELFFile
    nro = (path / 'pes21_nx.nro').read_bytes()
    catalog = read(path / 'selector/catalog.json')
    expected_rows = [(c['label'], len(c['team_ids']), c['badge_slot']) for c in catalog['categories']]
    found_atlas, found_categories = False, False
    with (path / 'pes21_nx.elf').open('rb') as stream:
        elf = ELFFile(stream)
        for symbol in elf.get_section_by_name('.symtab').iter_symbols():
            start, size = symbol['st_value'], symbol['st_size']
            if symbol.name == 'badge_atlas_bin':
                atlas = (path / 'league-branding/badge_atlas.bin').read_bytes()
                assert nro[start:start + len(atlas)] == atlas
                found_atlas = True
            elif re.fullmatch(r'exhibition_team_categories(?:\..*)?', symbol.name):
                actual = []
                for offset in range(start, start + size, 32):
                    label, _icon, _teams, count, slot = struct.unpack_from('<QQQII', nro, offset)
                    actual.append((nro[label:nro.index(b'\0', label)].decode('utf-8'), count, slot))
                assert actual == expected_rows
                found_categories = True
    assert found_atlas and found_categories

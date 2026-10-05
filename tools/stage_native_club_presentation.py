#!/usr/bin/env python3
"""Pair native club names/crests with the current selector, without roster edits.

Only explicit, same-identity overrides are accepted. All binary outputs and
locally supplied FL26 assets remain in a new ignored candidate directory.
"""
from __future__ import annotations

import argparse
import copy
import io
from pathlib import Path
import re
import shutil
import subprocess
import sys

from PIL import Image

from build_barca_real_madrid_mobile_kit_canary import validate_cpk
from build_eng_spa_license_pack import fixed_ascii, normalized_ascii, patch_team_rows
from build_fl26_cup_catalog import decoded_member, index_cpk
from build_full_mobile_kit_migration import (
    ATLAS_WIDTH, BADGE_CELL, fit_badge, replace_badge_cell, write_badge_header,
)
from cleanse_playable_categories import render_curated_include
from generate_exhibition_team_catalog import ascii_display_name
from audit_native_club_presentation import audit
from pes21_player_migration import content_id, encode_pes21_wesys
from prepare_loose_cpk import clone_full, update, verify
from restore_fl26_presentation import (
    DT200, DT240, TEAM_MEMBER, archive_reader, read_json, sha, team_records, write_json,
)
from stage_team_crest_override import native_crest_plan, native_png, pack_native_crests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / 'data/native_club_presentation_overrides.json'
DEFAULT_ALIASES = ROOT / 'data/native_club_identity_aliases.json'
ROSTER = 'exhibition_rosters_migration_canary_generated.inc'
SCORERS = 'league_scorer_pool_generated.inc'


def name_signature(name: str) -> set[str]:
    words = normalized_ascii(ascii_display_name(name).replace("'", '')).split()
    colors = set('A B V R N W M O Y G AB BA RW BW WB RA RB AR AA BB BN NB RN NR '
                 'GB GA AN ANV HB RH SR BY YG OB MB RY VA AV RBV WBW VB'.split())
    if words and words[-1] in colors:
        words.pop()
    affixes = set('FC CF SC AC CA CD UD RC AFC BC SSC SS AS FK SK CSD SV TSG SE '
                  'F C CLUB CALCIO FOOTBALL SPORTING CLUBE'.split())
    return set(word for word in words if word not in affixes)


def identity_proof(team: dict, native: bytes, fl26: bytes, aliases: list) -> str | None:
    """Never accept a numeric ID or a shared town token alone as identity."""
    original, official = fixed_ascii(native, 368, 70), fixed_ascii(fl26, 368, 70)
    selector, code = team['display_name'], fixed_ascii(fl26, 882, 4)
    if not code or len(code.encode('ascii', errors='replace')) > 3:
        return None
    normalized = lambda name: normalized_ascii(ascii_display_name(name))
    if normalized(official) in (normalized(selector), normalized(original)):
        return 'exact_name_and_mapped_team_id'
    if [int(team['team_id']), selector, official] in aliases:
        return 'reviewed_identity_alias'
    source = name_signature(official)
    for value in (selector, original):
        current = name_signature(value)
        if not current or not source:
            continue
        if current == source:
            return 'same_club_name_without_affixes'
        if (current <= source and len(''.join(current)) >= 4 and
                code in [fixed_ascii(native, n, 4) for n in (882, 1382)]):
            return 'club_name_and_native_short_code'
    return None


def all_verified_policy(raw: bytes, fl_raw: bytes, catalog: dict, overrides: dict,
                        fl_index: dict, aliases: list):
    native, fl26 = team_records(raw), team_records(fl_raw)
    explicit = {int(t['team_id']): t for t in overrides['teams']}
    source_names = {name.lower(): name for name in fl_index}
    if len(source_names) != len(fl_index):
        raise ValueError('case-ambiguous FL26 crest members')
    targets, held = [], []
    for team in catalog['teams']:
        logical, physical = int(team['team_id']), int(team['physical_team_id'])
        original = native.get(physical)
        if original is None:
            raise ValueError(f'active team {logical} has no native row')
        source_id = logical
        source = fl26.get(source_id)
        proof = identity_proof(team, original, source, aliases) if source else None
        if not proof and physical != logical:
            # A remapped physical key may also exist in FL26, but it is usable
            # ONLY when its name independently agrees with the active team.
            alternate = fl26.get(physical)
            alternate_proof = identity_proof(team, original, alternate, []) if alternate else None
            if alternate_proof:
                source_id, source, proof = physical, alternate, alternate_proof
        if not proof:
            held.append(dict(team_id=logical, name=team['display_name'],
                reason='fl26_identity_unavailable_or_unproven'))
            continue
        override = explicit.get(logical)
        crest_member = next((source_names[f'common/render/symbol/flag/e_{source_id:06d}_{form}_l.png']
            for form in ('r', 'r_b', 'r_w')
            if f'common/render/symbol/flag/e_{source_id:06d}_{form}_l.png' in source_names), None)
        if not crest_member and not override:
            held.append(dict(team_id=logical, name=team['display_name'], reason='fl26_crest_missing'))
            continue
        official = ascii_display_name(fixed_ascii(source, 368, 70))
        target = dict(team_id=logical, physical_team_id=physical, fl26_team_id=source_id,
            expected_native_names=[fixed_ascii(original, 368, 70), official],
            expected_selector_names=[team['display_name'], official],
            expected_native_short_codes=[fixed_ascii(original, n, 4) for n in (882, 1382)],
            expected_fl26_name=fixed_ascii(source, 368, 70), official_name=official,
            short_code=fixed_ascii(source, 882, 4), crest_source='fl26',
            crest_member=crest_member, update_selector_badge=True, identity_proof=proof)
        if override:
            target.update(override)
        targets.append(target)
    return dict(schema_version=1, teams=targets), held


def patch_identity(raw: bytes, fl26_raw: bytes, catalog: dict, policy: dict):
    """Prove logical/native/name mapping, then change only known text fields."""
    if policy.get('schema_version') != 1 or not policy.get('teams'):
        raise ValueError('invalid native presentation policy')
    native, fl26 = team_records(raw), team_records(fl26_raw)
    result = copy.deepcopy(catalog)
    by_id = {int(t['team_id']): t for t in result['teams']}
    if len(by_id) != len(result['teams']):
        raise ValueError('duplicate selector team ID')
    targets, seen_logical, seen_physical = [], set(), set()
    for target in policy['teams']:
        logical, physical = int(target['team_id']), int(target['physical_team_id'])
        fl_id = int(target.get('fl26_team_id', logical))
        if logical in seen_logical or physical in seen_physical:
            raise ValueError('duplicate identity override')
        seen_logical.add(logical)
        seen_physical.add(physical)
        team = by_id.get(logical)
        if team is None or int(team['physical_team_id']) != physical:
            raise ValueError(f'team {logical}: selector/native mapping mismatch')
        if team['display_name'] not in target['expected_selector_names']:
            raise ValueError(f'team {logical}: unexpected selector identity')
        if physical not in native or fl_id not in fl26:
            raise ValueError(f'team {logical}: native/FL26 identity missing')
        if fixed_ascii(native[physical], 368, 70) not in target['expected_native_names']:
            raise ValueError(f'team {logical}: unexpected native identity')
        if (fixed_ascii(fl26[fl_id], 368, 70) != target['expected_fl26_name'] or
                fixed_ascii(fl26[fl_id], 882, 4) != target['short_code']):
            raise ValueError(f'team {logical}: FL26 fingerprint mismatch')
        # The short code may have a licensed and an unlicensed copy (PAL/BFU).
        old_codes = [fixed_ascii(native[physical], n, 4) for n in (882, 1382)]
        if (target['short_code'] not in old_codes and
                old_codes != target.get('expected_native_short_codes')):
            raise ValueError(f'team {logical}: native short-code fingerprint mismatch')
        targets.append(dict(team_id=physical, official_name=target['official_name'],
                            short_code=target['short_code'], team_bin_policy='patch_existing'))
        team['display_name'] = target['official_name']
    patched, report = patch_team_rows(raw, targets)
    result.pop('content_id', None)
    result['content_id'] = content_id(result)
    return patched, result, report


def load_crest(raw: bytes, expected_hash: str | None = None) -> Image.Image:
    if expected_hash and sha(raw) != expected_hash:
        raise ValueError('approved crest source hash differs')
    with Image.open(io.BytesIO(raw)) as source:
        if source.format != 'PNG' or source.size != (256, 256):
            raise ValueError('expected a 256x256 native/FL26 PNG crest')
        image = source.convert('RGBA')
    if not image.getchannel('A').getbbox() or image.getchannel('A').getextrema()[0] != 0:
        raise ValueError('crest needs visible pixels and a transparent background')
    return image


def stage(args) -> dict:
    base, output = args.base.resolve(), args.output.resolve()
    if output.exists() or (ROOT / 'local-debug').resolve() not in output.parents:
        raise ValueError('use a fresh candidate inside local-debug')
    baseline = verify(base)
    if baseline['version'] != 2:
        raise ValueError('expected a full loose CPK baseline')
    policy = read_json(args.policy)
    catalog = read_json(args.catalog)
    read = archive_reader(base)
    fl_team = args.fl26_root / 'download/data_s2526c.cpk'
    fl_raw = decoded_member(fl_team, *index_cpk(fl_team), TEAM_MEMBER)
    fl_crests = args.fl26_root / 'Data/dt15_x64.cpk'
    fl_index, fl_offset = index_cpk(fl_crests)
    held = []
    if args.all_verified:
        aliases = read_json(DEFAULT_ALIASES)['aliases']
        policy, held = all_verified_policy(read(DT200, TEAM_MEMBER), fl_raw, catalog,
                                           policy, fl_index, aliases)
    before_audit = audit(base, catalog)
    patched, catalog, names_report = patch_identity(
        read(DT200, TEAM_MEMBER), fl_raw, catalog, policy)
    native_source = base / 'LooseCpk' / DT240
    native_index, _ = index_cpk(native_source)
    raw_atlas = args.atlas.read_bytes()
    if not raw_atlas or len(raw_atlas) % (ATLAS_WIDTH * BADGE_CELL * 4):
        raise ValueError('source atlas has a partial row')
    atlas = Image.frombytes('RGBA', (ATLAS_WIDTH, len(raw_atlas) // (ATLAS_WIDTH * 4)), raw_atlas)
    teams = {int(t['team_id']): t for t in catalog['teams']}
    payloads, sources, crest_reports = {}, {}, []
    for target in policy['teams']:
        logical, physical = int(target['team_id']), int(target['physical_team_id'])
        if target['crest_source'] == 'current_native':
            if not re.fullmatch('[0-9a-f]{64}', target.get('crest_sha256', '')):
                raise ValueError('current native crest needs an approved source hash')
            source_member = f'common/render/symbol/flag/e_{physical:06d}_f_l.png'
            raw = read(DT240, source_member)
            source_archive = native_source
        elif target['crest_source'] == 'fl26':
            source_member = target.get('crest_member') or f'common/render/symbol/flag/e_{logical:06d}_r_l.png'
            fl_id = int(target.get('fl26_team_id', logical))
            if not re.fullmatch(rf'common/render/symbol/flag/e_{fl_id:06d}_r(?:_[bw])?_l\.png', source_member, re.I):
                raise ValueError('crest source belongs to another FL26 team')
            raw = decoded_member(fl_crests, fl_index, fl_offset, source_member)
            source_archive = fl_crests
        else:
            raise ValueError('unknown crest source policy')
        image = load_crest(raw, target.get('crest_sha256'))
        sources[logical] = raw
        members = native_crest_plan(native_index, physical)
        encoded_sizes = {size: native_png(image, size) for size in set(members.values())}
        for member, size in members.items():
            if member in native_index:
                before = read(DT240, member)
                with Image.open(io.BytesIO(before)) as current:
                    if current.size != (size, size):
                        raise ValueError(f'unexpected native dimensions: {member}')
            payloads[member] = encoded_sizes[size]
        slot = int(teams[logical]['badge_slot'])
        if target['update_selector_badge']:
            if (sum(int(t['badge_slot']) == slot for t in catalog['teams']) != 1 or
                    any(int(c['badge_slot']) == slot for c in catalog['categories'])):
                raise ValueError('team crest would overwrite a shared atlas cell')
            replace_badge_cell(atlas, slot, fit_badge(raw))
        crest_reports.append(dict(team_id=logical, physical_team_id=physical,
            badge_slot=slot, selector_badge_updated=target['update_selector_badge'],
            source_archive=str(source_archive), source_member=source_member,
            source_sha256=sha(raw), native_members=members))
    build_id = content_id(dict(base=baseline['build_id'], policy=policy,
        team_table=sha(patched), catalog=catalog['content_id'], atlas=sha(atlas.tobytes()),
        crests={name: sha(data) for name, data in payloads.items()}))
    # Check the paired input BEFORE creating any output.
    roster = (base / 'selector' / ROSTER).read_text(encoding='utf-8')
    old_id = baseline['build_id']
    if roster.count(old_id) != 2 or not re.search(
            rf'^#define PES21_PLAYER_MIGRATION_BUILD_ID "{old_id}"$', roster, re.M):
        raise ValueError('baseline roster include is not paired')
    clone_full(base, output, build_id)
    tables = output / 'tables'
    tables.mkdir()
    encoded = encode_pes21_wesys(patched)
    team_path = tables / 'Team.bin'
    team_path.write_bytes(encoded)
    replacements = output / 'team-replacement.json'
    write_json(replacements, {TEAM_MEMBER: str(team_path)})
    packed = output / 'dt200-patched.cpk'
    subprocess.run([sys.executable, str(ROOT / 'tools/repack_cpk_members.py'),
        str(base / 'LooseCpk' / DT200), str(packed), '--replace-manifest', str(replacements)],
        check=True, stdout=subprocess.DEVNULL)
    cpk_names = validate_cpk(base / 'LooseCpk' / DT200, packed,
                             {TEAM_MEMBER: 'replace'}, {TEAM_MEMBER: encoded})
    update(output, DT200, packed)
    packed.unlink()  # Only the newly generated duplicate.
    packed, cpk_crests = pack_native_crests(native_source, payloads, output / 'native-crests')
    update(output, DT240, packed)
    packed.unlink()
    selector = output / 'selector'
    selector.mkdir()
    write_json(selector / 'catalog.json', catalog)
    (selector / 'badge_atlas.bin').write_bytes(atlas.tobytes())
    write_badge_header(selector / 'badge_atlas.h', dict(catalog, content_id=build_id), atlas)
    (selector / 'exhibition_teams_migration_generated.inc').write_text(
        render_curated_include(catalog, build_id), encoding='utf-8')
    (selector / ROSTER).write_text(roster.replace(old_id, build_id), encoding='utf-8')
    shutil.copy2(base / 'selector' / SCORERS, selector / SCORERS)
    source_output = output / 'crest-sources'
    source_output.mkdir()
    for logical, raw in sources.items():
        (source_output / f'{logical}.png').write_bytes(raw)
    after = verify(output)
    if any(a != b for a, b in zip(baseline['files'], after['files'])
           if a['name'] not in {DT200, DT240}):
        raise ValueError('unrelated CPK changed')
    # clone_full/update must never alter the installed-baseline hard links.
    if verify(base) != baseline:
        raise ValueError('baseline changed during staging')
    after_audit = audit(output, catalog)
    write_json(output / 'audit-before.json', before_audit)
    write_json(output / 'audit-after.json', after_audit)
    report = dict(build_id=build_id, base_build_id=old_id, source_base=str(base),
        source_catalog=str(args.catalog.resolve()), source_atlas=str(args.atlas.resolve()),
        source_policy=policy, source_fl26_team=str(fl_team), names=names_report,
        crests=crest_reports, dt200=cpk_names, dt240=cpk_crests, held_teams=held,
        audit_before={k: v for k, v in before_audit.items() if k != 'rows'},
        audit_after={k: v for k, v in after_audit.items() if k != 'rows'},
        active_runtime_modified=False, matching_nro='pending', hardware_tested=False)
    write_json(output / 'native-presentation-report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--atlas', type=Path, required=True)
    parser.add_argument('--policy', type=Path, default=DEFAULT_POLICY)
    parser.add_argument('--all-verified', action='store_true',
                        help='restore only identity-verified FL26 teams in the current playable catalog')
    parser.add_argument('--fl26-root', type=Path, default=Path('D:/Games/SP Football Life 2026'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = stage(args)
    print(f"Staged {report['build_id']}: {report['names']['patched_team_rows']} names, "
          f"{len(report['dt240']['added_members'])} missing crest aliases added")


if __name__ == '__main__':
    main()

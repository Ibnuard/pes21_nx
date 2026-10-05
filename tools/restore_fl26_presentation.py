#!/usr/bin/env python3
"""Restore verified FL26 kit flags and selector branding onto a NEW candidate.

Only the kit-selection byte of proven same-identity teams is restored. Player
records, transfers, lineups, native slots, kit textures and crests are retained.
The original installed runtime and reference package are never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

from build_fl26_cup_catalog import decoded_member, index_cpk
from build_full_mobile_kit_migration import build_league_branding
from build_barca_real_madrid_mobile_kit_canary import validate_cpk
from build_real_madrid_mobile_kit_canary import index_cpk as logo_index
from pes21_player_migration import encode_pes21_wesys
from pesdb import PES21_TEAM_RECORD_SIZE, split_records
from prepare_loose_cpk import clone_full, digest, update, verify

ROOT = Path(__file__).resolve().parents[1]
TEAM_MEMBER = 'common/etc/pesdb/Team.bin'
DT200 = 'dt200_mobile_all.cpk'
DT120 = 'dt120_mobile_all.cpk'
DT240 = 'dt240_mobile_all.cpk'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def team_records(raw: bytes) -> dict[int, bytes]:
    rows = split_records(raw, PES21_TEAM_RECORD_SIZE, 'Team.bin')
    result = {struct.unpack_from('<I', row, 8)[0]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError('duplicate native team IDs')
    return result


def archive_reader(root: Path):
    archives = {}
    def read(archive: str, member: str) -> bytes:
        if archive not in archives:
            path = root / 'LooseCpk' / archive
            archives[archive] = (path, *index_cpk(path))
        path, index, offset = archives[archive]
        return decoded_member(path, index, offset, member)
    return read


def verified_kit_members(row: dict, read_current, read_reference) -> list[dict]:
    """Check every migrated mobile kit component against the audited source."""
    kits = {kit['kind']: kit for kit in row['kits']}
    if len(row['kits']) != 3 or set(kits) != {'1st', '2nd', 'GK1st'}:
        raise ValueError('reference does not contain three complete kits')
    checked = []
    def check(archive, member, expected_hash=None, descriptor=False):
        before = read_reference(archive, member)
        after = read_current(archive, member)
        if not before or before != after or (expected_hash and sha(before) != expected_hash):
            raise ValueError(f'kit asset mismatch: {member}')
        if descriptor and len(before) != 120:
            raise ValueError('invalid mobile uniform descriptor')
        checked.append(dict(archive=archive, member=member, sha256=sha(before)))
    physical = int(row['physical_team_id'])
    expected_previews = set()
    for kind, kit in kits.items():
        member = f'common/etc/uniform/team/{physical}/{physical}_DEF_{kind}_realUni.bin'
        if kit['descriptor_target'] != member:
            raise ValueError('reference descriptor belongs to another team')
        check(DT200, member, descriptor=True)
        assets = kit['assets']
        if len(assets) != 2 or {a['role'] for a in assets} != {'body', 'back'}:
            raise ValueError('incomplete reference textures')
        suffix = {'1st': 'p1', '2nd': 'p2', 'GK1st': 'g1'}[kind]
        for asset in assets:
            folder, ending = ('D', '') if asset['role'] == 'body' else ('Font', '_back')
            expected = f'Models/character/Uniform16/{folder}/u{physical:04d}{suffix}{ending}.png'
            if asset['target_member'] != expected:
                raise ValueError('reference texture belongs to another team')
            check(DT120, expected, asset['target_sha256'])
        if kind != 'GK1st':
            members = kit.get('preview_members', [])
            if not members:
                raise ValueError('missing home/away preview reference')
            expected_previews.update(members)
    previews = row.get('previews', [])
    if len(previews) != 2 or {p['suffix'] for p in previews} != {'p1', 'p2'}:
        raise ValueError('incomplete preview reference')
    actual_previews = set()
    for preview in previews:
        for member in preview['members']:
            check(DT240, member, preview['sha256'])
            actual_previews.add(member)
    if actual_previews != expected_previews:
        raise ValueError('preview reference sets differ')
    return checked


def restore_kit_flags(raw: bytes, reference_raw: bytes, catalog: dict,
                      reference_catalog: dict, reference_report: dict,
                      read_current, read_reference, selected: set[int] | None = None):
    current, reference = team_records(raw), team_records(reference_raw)
    old_teams = {int(t['team_id']): t for t in reference_catalog['teams']}
    kit_teams = {int(t['team_id']): t for t in reference_report['migrated_teams']}
    changes, held = [], []
    for team in catalog['teams']:
        logical, physical = int(team['team_id']), int(team['physical_team_id'])
        if selected is not None and logical not in selected:
            continue
        if physical not in current or logical not in old_teams or logical not in kit_teams:
            continue
        if current[physical][84] == 15:
            continue
        old, kit = old_teams[logical], kit_teams[logical]
        try:
            if (physical != int(old['physical_team_id']) or physical != int(kit['physical_team_id'])
                    or physical not in reference or reference[physical][84] != 15):
                raise ValueError('unproven native team mapping or reference kit flag')
            a, b = current[physical], reference[physical]
            # A numeric native ID alone is not identity proof. Every other
            # byte of Team.bin must agree; newer/repurposed team rows are held.
            if a[:84] + a[85:] != b[:84] + b[85:]:
                raise ValueError('team identity/metadata differs outside kit byte')
            assets = verified_kit_members(kit, read_current, read_reference)
        except (KeyError, ValueError, FileNotFoundError) as error:
            held.append(dict(team_id=logical, physical_team_id=physical, reason=str(error)))
            continue
        changes.append(dict(team_id=logical, physical_team_id=physical,
                            name=team['display_name'], before=current[physical][84],
                            after=15, verified_assets=assets))
    allowed = {row['physical_team_id'] for row in changes}
    result = bytearray(raw)
    for offset in range(0, len(raw), PES21_TEAM_RECORD_SIZE):
        if struct.unpack_from('<I', raw, offset + 8)[0] in allowed:
            result[offset + 84] = 15
    differences = [i for i, (a, b) in enumerate(zip(raw, result)) if a != b]
    if len(differences) != len(allowed) or any(i % PES21_TEAM_RECORD_SIZE != 84 for i in differences):
        raise ValueError('kit restoration changed a field outside the allowlist')
    return bytes(result), changes, held


def stage(args) -> dict:
    output = args.output.resolve()
    if output.exists() or (ROOT / 'local-debug').resolve() not in output.parents:
        raise ValueError('use a fresh output folder inside local-debug')
    base, reference = args.base.resolve(), args.reference.resolve()
    baseline = verify(base)
    verify(reference)
    catalog = read_json(args.catalog)
    reference_report = read_json(reference / 'full-kit-migration-report.json')
    reference_catalog = read_json(reference / 'league-branding/exhibition_team_catalog.json')
    read_current, read_reference = archive_reader(base), archive_reader(reference)
    old_table = read_current(DT200, TEAM_MEMBER)
    patched, changed, held = restore_kit_flags(
        old_table, read_reference(DT200, TEAM_MEMBER), catalog, reference_catalog,
        reference_report, read_current, read_reference,
        None if args.all_verified_kits else set(args.team),
    )
    if not changed:
        raise ValueError('no verified kit-flag regressions to restore')
    policy = read_json(ROOT / 'data/full_mobile_kit_migration.json')
    build_id = sha(json.dumps(dict(base=baseline['build_id'], team_table=sha(patched),
        catalog=digest(args.catalog), atlas=digest(args.atlas),
        league_branding=policy['league_branding']), sort_keys=True).encode())[:16]
    clone_full(base, output, build_id)
    tables = output / 'tables'
    tables.mkdir()
    team_path = tables / 'Team.bin'
    encoded = encode_pes21_wesys(patched)
    team_path.write_bytes(encoded)
    replacement = output / 'team-replacement.json'
    write_json(replacement, {TEAM_MEMBER: str(team_path)})
    packed = output / 'packed/dt200_mobile_all.cpk'
    subprocess.run([sys.executable, str(ROOT / 'tools/repack_cpk_members.py'),
                    str(base / 'LooseCpk' / DT200), str(packed),
                    '--replace-manifest', str(replacement)], check=True)
    cpk_report = validate_cpk(base / 'LooseCpk' / DT200, packed,
                              {TEAM_MEMBER: 'replace'}, {TEAM_MEMBER: encoded})
    update(output, DT200, packed)
    packed.unlink()  # Tool-generated duplicate, never an input/runtime file.
    branding = build_league_branding(output, catalog, policy['league_branding'],
        logo_index(args.fl26_root / policy['football_life_league_archive'], 'fl26', 0),
        atlas_path=args.atlas, paired_build_id=build_id)
    selector = output / 'selector'
    selector.mkdir()
    old_id = baseline['build_id']
    roster = (base / 'selector/exhibition_rosters_migration_canary_generated.inc').read_text(encoding='utf-8')
    if len(re.findall(rf'^#define PES21_PLAYER_MIGRATION_BUILD_ID "{old_id}"$', roster, re.M)) != 1:
        raise ValueError('base roster include is not paired')
    (selector / 'exhibition_rosters_migration_canary_generated.inc').write_text(
        roster.replace(old_id, build_id), encoding='utf-8')
    shutil.copy2(base / 'selector/league_scorer_pool_generated.inc', selector / 'league_scorer_pool_generated.inc')
    shutil.copy2(branding['catalog'], selector / 'catalog.json')
    after = verify(output)
    if any(a != b for a, b in zip(baseline['files'], after['files']) if a['name'] != DT200):
        raise ValueError('unrelated CPK changed')
    if archive_reader(output)(DT200, TEAM_MEMBER) != patched:
        raise ValueError('packed Team.bin differs from verified repair')
    report = dict(build_id=build_id, base_build_id=old_id, active_runtime_modified=False,
                  changed_kit_flags=changed, held_kit_flags=held, cpk=cpk_report,
                  branding=branding, roster_arrays_unchanged=True,
                  source_base=str(base), source_reference=str(reference),
                  source_catalog=str(args.catalog.resolve()), source_atlas=str(args.atlas.resolve()),
                  matching_nro='pending', hardware_tested=False)
    write_json(output / 'restoration-report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--atlas', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--fl26-root', type=Path, default=Path('D:/Games/SP Football Life 2026'))
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--all-verified-kits', action='store_true')
    scope.add_argument('--team', type=int, action='append')
    parser.add_argument('--output', type=Path, required=True)
    report = stage(parser.parse_args())
    print(json.dumps(dict(build_id=report['build_id'], restored=len(report['changed_kit_flags']),
                          held=report['held_kit_flags'], branded=report['branding']['categories_updated'])))


if __name__ == '__main__':
    main()

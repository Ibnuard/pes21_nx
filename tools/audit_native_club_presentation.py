#!/usr/bin/env python3
"""Read-only audit of every active logical/native team and its crest families.

Licensed clubs may use _r, or separate _r_b/_r_w contrast variants. Absence
of unused _f aliases is not a defect. Name differences are review findings,
not automatic authorization to rename or replace a physical slot.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import re

from PIL import Image

from build_eng_spa_license_pack import fixed_ascii, normalized_ascii
from build_fl26_cup_catalog import index_cpk
from restore_fl26_presentation import (
    DT200, DT240, TEAM_MEMBER, archive_reader, read_json, team_records, write_json,
)


def crest_families(index: dict, physical: int) -> dict[str, dict[str, str]]:
    pattern = re.compile(
        rf'common/render/symbol/flag/e_{physical:06d}_([rf](?:_[bw])?)(|_l|_s)\.png$')
    families = {}
    for name in index:
        match = pattern.fullmatch(name)
        if match:
            form, size = match.groups()
            families.setdefault(form, {})[size] = name
    return families


def complete_real_family(families: dict) -> bool:
    complete = {form for form, sizes in families.items() if set(sizes) == {'', '_l', '_s'}}
    return 'r' in complete or {'r_b', 'r_w'} <= complete


def audit(base: Path, catalog: dict) -> dict:
    read = archive_reader(base)
    rows = team_records(read(DT200, TEAM_MEMBER))
    index, _ = index_cpk(base / 'LooseCpk' / DT240)
    findings, seen_logical, seen_physical = [], set(), set()
    for team in catalog['teams']:
        logical, physical = int(team['team_id']), int(team['physical_team_id'])
        errors = []
        if logical in seen_logical or physical in seen_physical:
            errors.append('duplicate_logical_or_physical_mapping')
        seen_logical.add(logical)
        seen_physical.add(physical)
        row = rows.get(physical)
        if row is None:
            findings.append(dict(team_id=logical, physical_team_id=physical,
                                 errors=[*errors, 'native_team_missing']))
            continue
        families = crest_families(index, physical)
        real = complete_real_family(families)
        if row[84] == 15 and not real:
            errors.append('licensed_team_missing_complete_real_crest')
        if not any(set(sizes) == {'', '_l', '_s'} for sizes in families.values()):
            errors.append('no_complete_crest_family')
        sizes_report = {}
        for family in families.values():
            for suffix, name in family.items():
                try:
                    with Image.open(io.BytesIO(read(DT240, name))) as image:
                        image.load()
                        expected = {'': 128, '_l': 256, '_s': 64}[suffix]
                        if image.format != 'PNG' or image.size != (expected, expected):
                            errors.append(f'invalid_crest_dimensions:{name}')
                        if not image.convert('RGBA').getchannel('A').getbbox():
                            errors.append(f'empty_crest:{name}')
                        sizes_report[name] = list(image.size)
                except (ValueError, OSError) as error:
                    errors.append(f'unreadable_crest:{name}:{error}')
        native_name = fixed_ascii(row, 368, 70)
        if not native_name.strip() or '\ufffd' in native_name:
            errors.append('invalid_native_name')
        findings.append(dict(team_id=logical, physical_team_id=physical,
            selector_name=team['display_name'], native_name=native_name,
            short_codes=[fixed_ascii(row, n, 4) for n in (882, 1382)], kit_flags=row[84],
            real_crest_complete=real, crest_families=sorted(families),
            crest_sizes=sizes_report, errors=errors,
            name_differs=normalized_ascii(native_name) != normalized_ascii(team['display_name'])))
    return dict(teams_checked=len(findings),
        teams_with_errors=sum(bool(t['errors']) for t in findings),
        name_differences=sum(t.get('name_differs', False) for t in findings),
        real_crest_gaps=sum('licensed_team_missing_complete_real_crest' in t['errors'] for t in findings),
        rows=findings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.base, read_json(args.catalog))
    if args.report.exists():
        raise FileExistsError('use a new audit report path')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.report, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))


if __name__ == '__main__':
    main()

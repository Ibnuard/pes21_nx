#!/usr/bin/env python3
"""Stage Football Life crests and apply identity-only catalog overrides.

Never changes team IDs, roster membership, tactics, or player identities.
Outputs are detached by default; pass the resulting catalog to the badge builder.
"""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path

from PIL import Image
from build_eng_spa_license_pack import index_cpk, read_cpk_member
from exhibition_team_catalog import load_catalog
from generate_exhibition_team_catalog import render_team_include

ROOT = Path(__file__).resolve().parents[1]


def apply_identities(catalog, overrides):
    result = copy.deepcopy(catalog)
    by_id = {int(row['team_id']): row for row in overrides}
    if len(by_id) != len(overrides):
        raise ValueError('duplicate license team ID')
    applied = []
    for team in result['teams']:
        row = by_id.get(int(team['team_id']))
        if row is None:
            continue
        name = row['display_name'].strip()
        if not name or not name.isascii():
            raise ValueError('display name must be nonempty ASCII')
        team['display_name'] = name
        team['name_source'] = 'football_life_license'
        team['badge_source'] = row['badge_source']
        team['badge_source_root'] = 'repo'
        applied.append(int(team['team_id']))
    result.pop('content_id', None)
    canonical = json.dumps(result, sort_keys=True, separators=(',', ':')).encode()
    result['content_id'] = hashlib.sha256(canonical).hexdigest()[:16]
    return result, sorted(applied), sorted(set(by_id) - set(applied))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=ROOT/'data/exhibition_team_catalog.json')
    parser.add_argument('--names', type=Path, default=ROOT/'local-debug/eng-spa-license-pack/selector-name-overrides.json')
    parser.add_argument('--crest-cpk', type=Path, action='append', required=True,
                        help='Repeat from oldest to newest; newest available crest wins')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(ROOT)
    sources = [index_cpk(path, str(path), i) for i, path in enumerate(args.crest_cpk)]
    names = json.loads(args.names.read_text(encoding='utf-8'))['teams']
    overrides, payloads, provenance = [], [], []
    for row in names:
        team_id = int(row['team_id'])
        value = member = chosen = None
        for source in reversed(sources):
            for suffix in ('r_ll', 'r_l', 'r', 'r_b'):
                candidate = f'common/render/symbol/flag/e_{team_id:06d}_{suffix}.png'
                data = read_cpk_member(source, candidate)
                if data is not None:
                    value, member, chosen = data, candidate, source['path']
                    break
            if value is not None:
                break
        if value is None:
            raise ValueError(f'No Football Life crest for {team_id}; no output committed')
        with Image.open(io.BytesIO(value)) as im:
            im.verify()
        target = output/'crests'/f'{team_id}.png'
        payloads.append((target, value))
        overrides.append(dict(row, badge_source=target.relative_to(ROOT).as_posix()))
        provenance.append(dict(team_id=team_id, archive=str(chosen), member=member,
                               sha256=hashlib.sha256(value).hexdigest()))
    catalog, applied, pending = apply_identities(load_catalog(args.catalog), overrides)
    output.mkdir(parents=True, exist_ok=True)
    for target, value in payloads:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
    for name, data in [('exhibition_team_catalog.json', catalog),
                       ('identity-overrides.json', overrides),
                       ('report.json', dict(applied=applied, pending_missing_slot=pending,
                                            sources=provenance, runtime_tested=False))]:
        (output/name).write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    (output/'exhibition_teams_generated.inc').write_text(render_team_include(catalog), encoding='utf-8')
    print(json.dumps(dict(applied=len(applied), pending=pending, output=str(output))))


if __name__ == '__main__':
    main()

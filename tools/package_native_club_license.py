#!/usr/bin/env python3
"""Merge native crests and audited mobile kit payloads into a NEW OBB.

The selected base owns all roster/player data. Never transplant a whole
Team.bin from a kit canary; only enable real uniforms for its selected teams.
"""
import argparse
import io
import json
import re
import struct
from pathlib import Path
from PIL import Image
from build_pesdb_famous_teams_candidate import (
    member_payload, package_outer_obb, validate_outer_obb, sha256_file,
)
from build_barca_real_madrid_mobile_kit_canary import (
    cpk_inventory, package_cpk, decode_wesys_payload,
)
from build_eng_spa_license_pack import encode_wesys

ROOT = Path(__file__).resolve().parents[1]


def enable_real_kits(payload, team_ids):
    raw, _ = decode_wesys_payload(payload, 'Team.bin')
    if len(raw) % 1532:
        raise ValueError('invalid Team.bin record length')
    result = bytearray(raw)
    changes = []
    for offset in range(0, len(raw), 1532):
        team = struct.unpack_from('<I', raw, offset + 8)[0]
        if team in team_ids:
            before = result[offset + 84]
            result[offset + 84] = 15
            changes.append(dict(team_id=team, before=before, after=15))
    if {row['team_id'] for row in changes} != set(team_ids):
        raise ValueError('kit team missing from selected base')
    allowed = {o + 84 for o in range(0, len(raw), 1532)
               if struct.unpack_from('<I', raw, o + 8)[0] in team_ids}
    assert all(a == b or i in allowed for i, (a, b) in enumerate(zip(raw, result)))
    return encode_wesys(bytes(result)), changes


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-obb', type=Path, required=True)
    p.add_argument('--kit-pack', type=Path, required=True)
    p.add_argument('--identities', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--verify-existing', action='store_true',
                   help='Revalidate existing output without repacking or overwriting binaries')
    args = p.parse_args()
    output = args.output.resolve()
    if output.exists() and not args.verify_existing:
        raise FileExistsError('use a fresh output directory')
    plan = json.loads((args.kit_pack/'cpk-actions.json').read_text())
    identities = json.loads(args.identities.read_text())
    # Infer teams from explicit descriptor member paths, not hardcoded IDs.
    kit_ids = {int(m.split('/')[4]) for m in plan['dt200']['paths']
               if m.startswith('common/etc/uniform/team/')}
    output.mkdir(parents=True, exist_ok=args.verify_existing)
    replacements, reports = {}, {}
    for label in ('dt120', 'dt200', 'dt240'):
        member = f'Expansion/{label}_mobile_all.cpk'
        base = output/f'base-{label}.cpk'
        original_payload = member_payload(args.base_obb, member)
        if args.verify_existing:
            if base.read_bytes() != original_payload:
                raise ValueError('staged base differs from specified OBB')
        else:
            base.write_bytes(original_payload)
        inventory = cpk_inventory(base)
        payloads = {}
        if label in plan:
            for name, relative in plan[label]['paths'].items():
                if name != 'common/etc/pesdb/Team.bin':
                    payloads[name] = (args.kit_pack/relative).read_bytes()
        if label == 'dt200':
            name = 'common/etc/pesdb/Team.bin'
            payloads[name], reports['kit_flags'] = enable_real_kits(
                member_payload(base, name), kit_ids)
        if label == 'dt240':
            for row in identities:
                team_id = int(row['team_id'])
                pattern = re.compile(rf'common/render/symbol/flag/e_{team_id:06d}_.*\.png$')
                names = [n for n in inventory if pattern.fullmatch(n)]
                if not names:
                    continue  # Absent native slot (reported separately by identity tool).
                with Image.open(ROOT/row['badge_source']) as src:
                    crest = src.convert('RGBA')
                    for name in names:
                        with Image.open(io.BytesIO(member_payload(base, name))) as old:
                            size = old.size
                        buf = io.BytesIO()
                        crest.resize(size, Image.Resampling.LANCZOS).save(buf, format='PNG')
                        payloads[name] = buf.getvalue()
        actions = {name: 'replace' if name in inventory else 'add' for name in payloads}
        paths = {}
        for i, (name, value) in enumerate(sorted(payloads.items())):
            path = output/'payloads'/label/f'{i:04d}.bin'
            path.parent.mkdir(parents=True, exist_ok=True)
            if args.verify_existing:
                if path.read_bytes() != value:
                    raise ValueError(f'staged payload differs: {name}')
            else:
                path.write_bytes(value)
            paths[name] = str(path)
        if args.verify_existing:
            from build_barca_real_madrid_mobile_kit_canary import validate_cpk
            reports[label] = validate_cpk(base, output/f'{label}_barca_real_madrid_canary.cpk', actions, payloads)
        else:
            reports[label] = package_cpk(ROOT, output, label, base, actions, payloads, paths)
        candidate = Path(reports[label]['candidate'])
        if sha256_file(base) != sha256_file(candidate):
            replacements[member] = candidate
    obb = output/args.base_obb.name
    if args.verify_existing:
        mode, note = 'repacked', 'Verified existing repacked artifact'
    else:
        mode, note = package_outer_obb(args.base_obb, obb, replacements)
    reports['obb'] = validate_outer_obb(args.base_obb, obb, replacements, packaging_mode=mode)
    reports['base_sha256'] = sha256_file(args.base_obb)
    reports['note'] = note
    reports['runtime_tested'] = False
    (output/'validation-report.json').write_text(json.dumps(reports, indent=2)+'\n')
    print(json.dumps(reports['obb'], indent=2), flush=True)


if __name__ == '__main__':
    main()

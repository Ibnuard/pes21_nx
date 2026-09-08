"""Isolate kit/TOC regressions while keeping the current crest archive.

Restore dt120 and dt200 from an explicitly supplied previously working OBB.
Never modify originals. Validate all other OBB members byte-for-byte.
"""
import argparse
import json
from pathlib import Path
from build_pesdb_famous_teams_candidate import member_payload, validate_outer_obb
from patch_cpk_slots import patch_slots
from build_barca_real_madrid_mobile_kit_canary import (
    index_cpk, read_indexed, decode_wesys_payload,
)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--current', type=Path, required=True)
    p.add_argument('--previous', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise FileExistsError(a.output)
    a.output.mkdir(parents=True)
    replacements = {}
    for label in ('dt120', 'dt200'):
        member = f'Expansion/{label}_mobile_all.cpk'
        target = a.output/f'{label}-recovery.cpk'
        target.write_bytes(member_payload(a.previous, member))
        replacements[member] = target
    # Reject a baseline that silently rolls back ratings or assignments.
    cur_path = a.output/'current-dt200.cpk'
    cur_path.write_bytes(member_payload(a.current, 'Expansion/dt200_mobile_all.cpk'))
    cur = index_cpk(cur_path, 'current', 0)
    prev = index_cpk(replacements['Expansion/dt200_mobile_all.cpk'], 'previous', 0)
    preserved = []
    for item in cur['rows'].values():
        name = item['name']
        if not name.startswith('common/etc/pesdb/'):
            continue
        left, right = read_indexed(cur, name), read_indexed(prev, name)
        if name.endswith('/Team.bin'):
            import struct
            lraw, _ = decode_wesys_payload(left, name)
            rraw, _ = decode_wesys_payload(right, name)
            if len(lraw) != len(rraw):
                raise ValueError('Team.bin row count differs')
            allowed = {i + 84 for i in range(0, len(lraw), 1532)
                       if struct.unpack_from('<I', lraw, i+8)[0] in (108, 109)}
            if any(x != y and i not in allowed for i, (x, y) in enumerate(zip(lraw, rraw))):
                raise ValueError('Team.bin differs beyond kit flags')
        elif left != right:
            raise ValueError(f'baseline would revert database: {name}')
        preserved.append(name)
    obb = a.output/a.current.name
    patch_slots(a.current, obb, replacements)
    report = validate_outer_obb(a.current, obb, replacements)
    report['database_preserved_except_kit_flags'] = preserved
    report['runtime_tested'] = False
    report['note'] = 'Madrid may return to generic kit. Test Barca, celebration and pause first.'
    (a.output/'validation-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()

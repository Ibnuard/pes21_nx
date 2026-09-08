"""Experimental TOC sorting (NOT the stable kit migration path).

The v3 global-sort candidate booted but regressed kits/celebration/pause.
Use build_madrid_preserve_order.py for the hardware-confirmed Madrid path.
"""
import argparse
import json
import shutil
import struct
from pathlib import Path
from add_cpk_members_canary import packet_payload, utf_layout, parse_toc_rows, member_name
from prepare_runtime import decrypt_utf
from build_barca_real_madrid_mobile_kit_canary import validate_cpk
from build_pesdb_famous_teams_candidate import member_payload, validate_outer_obb
from patch_cpk_slots import patch_slots


def sorted_rows(rows):
    return sorted(rows, key=lambda row: member_name(row).lower())


def repair(source, output):
    from prepare_runtime import read_cpk_packet
    if output.exists():
        raise FileExistsError(output)
    with source.open('rb') as stream:
        header = read_cpk_packet(stream, 0, b'CPK ')[0]
        toc = int(header['TocOffset'])
        _, packet, encrypted = packet_payload(stream, toc, b'TOC ')
    layout = utf_layout(packet)
    rows = parse_toc_rows(packet)
    ordered = sorted_rows(rows)
    patched = bytearray(packet)
    start = layout['rows']
    patched[start:start + len(rows)*layout['row_length']] = b''.join(row['_raw'] for row in ordered)
    changed = bytes(patched) != packet
    shutil.copyfile(source, output)
    with output.open('r+b') as stream:
        stream.seek(toc+16)
        stream.write(decrypt_utf(bytes(patched)) if encrypted else patched)
    report = validate_cpk(source, output, {}, {})
    with output.open('rb') as stream:
        rebuilt_header = read_cpk_packet(stream, 0, b'CPK ')[0]
        _, rebuilt_packet, _ = packet_payload(stream, toc, b'TOC ')
    if rebuilt_header != header:
        raise ValueError('repair changed CPK header')
    actual = parse_toc_rows(rebuilt_packet)
    if {member_name(r): r for r in actual} != {member_name(r): r for r in rows}:
        raise ValueError('repair changed row metadata or payload offsets')
    if actual != ordered:
        raise ValueError('written TOC ordering mismatch')
    report['toc_reordered'] = changed
    report['sorted_flag'] = header['Sorted']
    report['payload_offsets_preserved'] = True
    # Exercise binary search for EVERY member, rather than dict-only auditing.
    keys = [member_name(r).lower() for r in actual]
    from bisect import bisect_left
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate case-insensitive paths')
    assert all(keys[bisect_left(keys, k)] == k for k in keys)
    report['binary_lookup_passed'] = len(keys)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-obb', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    reports, replacements = {}, {}
    for label in ('dt120', 'dt200'):
        name = f'Expansion/{label}_mobile_all.cpk'
        base, fixed = args.output/f'base-{label}.cpk', args.output/f'{label}-sorted.cpk'
        base.write_bytes(member_payload(args.base_obb, name))
        reports[label] = repair(base, fixed)
        if reports[label]['toc_reordered']:
            replacements[name] = fixed
    if not replacements:
        raise ValueError('no unsorted tables found')
    obb = args.output/args.base_obb.name
    patch_slots(args.base_obb, obb, replacements)
    reports['obb'] = validate_outer_obb(args.base_obb, obb, replacements)
    reports['runtime_tested'] = False
    (args.output/'validation-report.json').write_text(json.dumps(reports, indent=2)+'\n')
    print(json.dumps(reports, indent=2), flush=True)


if __name__ == '__main__':
    main()

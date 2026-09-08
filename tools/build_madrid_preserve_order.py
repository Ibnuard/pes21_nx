"""Madrid kit trial on a hardware-tested recovery base.

Keep original TOC row order and IDs. Set Sorted=0 rather than claiming that
appended files are sorted or reordering existing game resources. Native loader
support for this flag must be confirmed on hardware; this is a test candidate.
"""
import argparse
import json
import shutil
import struct
from pathlib import Path
from add_cpk_members_canary import packet_payload, parse_toc_rows, utf_layout, member_name
from prepare_runtime import decrypt_utf, read_cpk_packet
from repack_cpk_members import patch_utf_rows
from build_barca_real_madrid_mobile_kit_canary import package_cpk, cpk_inventory, validate_cpk
from build_pesdb_famous_teams_candidate import member_payload, validate_outer_obb
from package_native_club_license import enable_real_kits
from patch_cpk_slots import patch_slots

ROOT = Path(__file__).resolve().parents[1]


def restore_order(source, output, names):
    if output.exists():
        raise FileExistsError(output)
    with source.open('rb') as stream:
        header = read_cpk_packet(stream, 0, b'CPK ')[0]
        stream.seek(8)
        header_size = struct.unpack('<Q', stream.read(8))[0]
        header_payload = stream.read(header_size)
        toc = int(header['TocOffset'])
        _, packet, encrypted = packet_payload(stream, toc, b'TOC ')
    rows = parse_toc_rows(packet)
    by_name = {member_name(r): r for r in rows}
    if len(names) != len(rows) or set(names) != set(by_name):
        raise ValueError('TOC order plan differs from member set')
    layout = utf_layout(packet)
    ordered = [by_name[n] for n in names]
    patched = bytearray(packet)
    start = layout['rows']
    patched[start:start+len(rows)*layout['row_length']] = b''.join(r['_raw'] for r in ordered)
    new_header = patch_utf_rows(header_payload, [{'Sorted': 0}])
    if len(new_header) != len(header_payload):
        raise ValueError('header size changed')
    shutil.copyfile(source, output)
    with output.open('r+b') as stream:
        stream.seek(16)
        stream.write(new_header)
        stream.seek(toc+16)
        stream.write(decrypt_utf(bytes(patched)) if encrypted else patched)
    report = validate_cpk(source, output, {}, {})
    with output.open('rb') as stream:
        check_header = read_cpk_packet(stream, 0, b'CPK ')[0]
        _, checked, _ = packet_payload(stream, toc, b'TOC ')
    if check_header != dict(header, Sorted=0) or parse_toc_rows(checked) != ordered:
        raise ValueError('written header/order verification failed')
    report['sorted_flag'] = 0
    report['row_metadata_ids_offsets_preserved'] = True
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-obb', type=Path, required=True)
    p.add_argument('--kit-pack', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    plan = json.loads((a.kit_pack/'cpk-actions.json').read_text())
    report, replacements = {}, {}
    for label in ('dt120', 'dt200'):
        member = f'Expansion/{label}_mobile_all.cpk'
        base = out/f'base-{label}.cpk'
        base.write_bytes(member_payload(a.base_obb, member))
        inventory = cpk_inventory(base)
        original_names = list(inventory)
        if label == 'dt120':
            # Recovery already contains the converted Madrid/Barca textures.
            # Assert exact provenance, do not replace or reorder them.
            for name, relative in plan[label]['paths'].items():
                if member_payload(base, name) != (a.kit_pack/relative).read_bytes():
                    raise ValueError(f'recovery texture drift: {name}')
            stage = base
        else:
            team = 'common/etc/pesdb/Team.bin'
            payloads = {n: (a.kit_pack/path).read_bytes()
                        for n, path in plan[label]['paths'].items()
                        if n.startswith('common/etc/uniform/team/109/')}
            if len(payloads) != 3:
                raise ValueError('expected three Madrid descriptors')
            payloads[team], report['kit_flags'] = enable_real_kits(member_payload(base, team), {109})
            actions = {n: 'replace' if n in inventory else 'add' for n in payloads}
            paths = {}
            for i, (n, data) in enumerate(payloads.items()):
                path = out/f'payload-{i}.bin'
                path.write_bytes(data)
                paths[n] = str(path)
            report['dt200_merge'] = package_cpk(ROOT, out, label, base, actions, payloads, paths)
            stage = Path(report['dt200_merge']['candidate'])
            original_names.extend(sorted(n for n in payloads if n not in inventory))
        fixed = out/f'{label}-original-order.cpk'
        report[label] = restore_order(stage, fixed, original_names)
        replacements[member] = fixed
    obb = out/a.base_obb.name
    patch_slots(a.base_obb, obb, replacements)
    report['obb'] = validate_outer_obb(a.base_obb, obb, replacements)
    report['runtime_tested'] = False
    report['hypothesis'] = 'Native loader accepts appended members with Sorted=0 while original row order/IDs are retained'
    (out/'validation-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report['obb'], indent=2), flush=True)


if __name__ == '__main__':
    main()

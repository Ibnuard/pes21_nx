"""Build English/Spanish mobile kits on a selected stable OBB, never overwrite dist.

Existing native realUni descriptors are retained. PC shared font references are
resolved at source and materialized under each native kit's unique mobile name.
Original inner TOC order/IDs are retained and additions appended with Sorted=0.
"""
import argparse
import json
import shutil
import struct
from pathlib import Path

from build_barca_real_madrid_mobile_kit_canary import (
    cpk_inventory, decode_wesys_payload, descriptor_texture_names, package_cpk,
    validate_cpk,
)
from build_real_madrid_mobile_kit_canary import (
    source_indexes, winning_member, decode_ftex_top, convert_body, convert_back,
    image_png_bytes, sha256_bytes,
)
from build_madrid_preserve_order import restore_order
from build_pesdb_famous_teams_candidate import (
    member_payload, package_outer_obb, validate_outer_obb, sha256_file,
)
from package_native_club_license import enable_real_kits

ROOT = Path(__file__).resolve().parents[1]
KINDS = (('1st', 'p1'), ('2nd', 'p2'), ('GK1st', 'g1'))


def mobile_descriptor(pc, prefix):
    """Keep PC kit parameters but give every font a unique native mobile name."""
    descriptor_texture_names(pc)  # checks size and ASCII
    result = bytearray(pc)
    for offset, name in zip((40, 56, 88, 104),
                            (prefix, prefix+'_back', prefix+'_leg', prefix+'_name')):
        encoded = name.encode('ascii')
        if len(encoded) >= 16:
            raise ValueError('mobile texture reference too long')
        result[offset:offset+16] = encoded.ljust(16, b'\0')
    return bytes(result)


def safe_reference(name):
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name):
        raise ValueError(f'unsafe texture reference: {name!r}')
    return name


def build(args):
    out = args.output.resolve()
    if out.exists():
        raise FileExistsError('use a fresh output; stable dist is never overwritten')
    out.mkdir(parents=True)
    manifest = json.loads((ROOT/'data/barca_real_madrid_mobile_kit_canary.json').read_text())
    license_map = json.loads((ROOT/'data/eng_spa_license_overrides.json').read_text())
    teams = [dict(t, league=league['label']) for league in license_map['leagues'] for t in league['teams']]
    ids = [t['team_id'] for t in teams]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate team mapping')
    indexes = source_indexes(ROOT, manifest, Path(manifest['football_life']['root']))
    bases, inventories = {}, {}
    for label in ('dt120', 'dt200', 'dt240'):
        bases[label] = out/f'base-{label}.cpk'
        bases[label].write_bytes(member_payload(args.base_obb, f'Expansion/{label}_mobile_all.cpk'))
        inventories[label] = cpk_inventory(bases[label])
    team_member = 'common/etc/pesdb/Team.bin'
    original_team = member_payload(bases['dt200'], team_member)
    raw, _ = decode_wesys_payload(original_team, team_member)
    if len(raw) % 1532:
        raise ValueError('invalid Team.bin')
    active = {struct.unpack_from('<I', raw, o+8)[0] for o in range(0, len(raw), 1532)}
    old_flags = {struct.unpack_from('<I', raw, o+8)[0]: raw[o+84] for o in range(0, len(raw), 1532)}
    payloads = {label: {} for label in bases}
    report = dict(base_sha256=sha256_file(args.base_obb), runtime_tested=False,
                  preserved_stable_teams=[108, 109], teams=[], pending_native_slots=[])
    flags = set()
    for team in teams:
        tid = team['team_id']
        if tid in (108, 109):
            report['teams'].append(dict(team, status='preserved_hardware_verified', kits=[]))
            continue
        row = dict(team, status='converted' if tid in active else 'assets_only_missing_native_slot', kits=[])
        if tid not in active:
            report['pending_native_slots'].append(tid)
        for kind, suffix in KINDS:
            prefix = f'u{tid:04d}{suffix}'
            native_name = f'common/etc/uniform/team/{tid}/{tid}_DEF_{kind}_realUni.bin'
            source_name = f'common/character0/model/character/uniform/team/{tid}/{tid}_DEF_{kind}_realUni.bin'
            pc, pc_meta = winning_member(indexes, source_name)
            source_refs = descriptor_texture_names(pc)
            native = (member_payload(bases['dt200'], native_name)
                      if native_name in inventories['dt200'] else mobile_descriptor(pc, prefix))
            refs = descriptor_texture_names(native)
            if refs[0] != prefix:
                raise ValueError(f'{tid}/{kind}: unexpected native body name {refs[0]}')
            outputs, sources = {}, {}
            for role, ref, target_ref in (('body', source_refs[0], refs[0]), ('back', source_refs[1], refs[1])):
                source = manifest['football_life']['texture_root'] + safe_reference(ref) + '.ftex'
                data, provenance = winning_member(indexes, source)
                image, metadata = decode_ftex_top(data)
                # FL shared EPL fonts use a 2x-resolution version of the same 8:1 atlas.
                expected = {(2048, 2048)} if role == 'body' else {(2048, 256), (4096, 512)}
                if image.size not in expected:
                    raise ValueError(f'{source}: unverified layout size {image.size}, expected {expected}')
                converted = image_png_bytes((convert_body if role == 'body' else convert_back)(image, manifest['atlas_transform']))
                folder = 'D' if role == 'body' else 'Font'
                member = f'Models/character/Uniform16/{folder}/{safe_reference(target_ref)}.png'
                # Never let a shared native font silently acquire another team's pixels.
                if member in payloads['dt120'] and payloads['dt120'][member] != converted:
                    raise ValueError(f'conflicting shared mobile texture: {member}')
                if tid in active:
                    payloads['dt120'][member] = converted
                path = out/'converted'/str(tid)/f'{suffix}-{role}.png'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(converted)
                outputs[role] = dict(member=member, sha256=sha256_bytes(converted), path=str(path))
                sources[role] = dict(provenance=provenance, texture=metadata)
            (out/'converted'/str(tid)/f'{suffix}-realUni.bin').write_bytes(native)
            if tid in active and native_name not in inventories['dt200']:
                payloads['dt200'][native_name] = native
            row['kits'].append(dict(kind=kind, sources=sources, outputs=outputs,
                                    descriptor_source=pc_meta,
                                    descriptor_policy='preserve_native' if native_name in inventories['dt200'] else 'add_normalized_pc'))
        if tid in active:
            flags.add(tid)
            # Newly licensed slots request _r instead of the existing _f crests.
            if old_flags[tid] != 15:
                stem = f'common/render/symbol/flag/e_{tid:06d}_'
                sources = [n for n in inventories['dt240'] if n.startswith(stem+'f')]
                if not sources and not any(n.startswith(stem+'r') for n in inventories['dt240']):
                    raise ValueError(f'missing crest variants: {tid}')
                for source in sources:
                    target = stem+'r'+source[len(stem)+1:]
                    if target not in inventories['dt240']:
                        payloads['dt240'][target] = member_payload(bases['dt240'], source)
        report['teams'].append(row)
        print(f"Converted {tid} {team['official_name']}: {row['status']}", flush=True)
    payloads['dt200'][team_member], report['kit_flags'] = enable_real_kits(original_team, flags)
    (out/'asset-report.json').write_text(json.dumps(report, indent=2)+'\n')
    if args.assets_only:
        return
    replacements = {}
    for label in bases:
        data = payloads[label]
        if not data:
            continue
        actions = {n: 'replace' if n in inventories[label] else 'add' for n in data}
        paths = {}
        for i, (name, content) in enumerate(data.items()):
            path = out/'payloads'/label/f'{i}.bin'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            paths[name] = str(path)
        merged = package_cpk(ROOT, out, label, bases[label], actions, data, paths)
        final = out/f'{label}-original-order.cpk'
        names = list(inventories[label]) + sorted(n for n in data if n not in inventories[label])
        report[label] = restore_order(Path(merged['candidate']), final, names)
        report[label]['payload_validation'] = validate_cpk(bases[label], final, actions, data)
        replacements[f'Expansion/{label}_mobile_all.cpk'] = final
    obb = out/args.base_obb.name
    mode, note = package_outer_obb(args.base_obb, obb, replacements)
    report['obb'] = validate_outer_obb(args.base_obb, obb, replacements, packaging_mode=mode)
    report['packaging_note'] = note
    if obb.stat().st_size == args.base_obb.stat().st_size:
        shutil.copyfile(args.base_nro, out/'pes21_nx.nro')
        report['nro'] = dict(mode='production_unchanged', sha256=sha256_file(out/'pes21_nx.nro'))
    else:
        report['nro'] = dict(status='matching_size_allowance_build_required', obb_bytes=obb.stat().st_size)
    (out/'validation-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(obb=report['obb'], nro=report['nro']), indent=2), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-obb', type=Path, default=ROOT/'dist/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb')
    p.add_argument('--base-nro', type=Path, default=ROOT/'dist/pes21_nx/pes21_nx.nro')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--assets-only', action='store_true')
    build(p.parse_args())

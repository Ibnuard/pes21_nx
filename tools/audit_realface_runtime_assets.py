"""Read-only packaged-face checks for a runtime appearance regression.

Validate the exact staged bytes and every cooked mip. This does not emulate
native material selection, skeletal animation, occlusion or the GPU. In
particular, a valid package must never be reported as a device appearance pass.
All reports stay in an ignored, caller-selected local audit directory.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from build_low_pitch_phase_patch import name_entries
from cooked_texture import Texture


ROOT = Path(__file__).resolve().parents[1]
FACE = 'PesMobile/Content/Assets/character/RealFace/'
GAME = '/Game/Assets/character/'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def texture_evidence(texture):
    """Include small mips: alpha loss can hide masked hair only at a distance."""
    rows = []
    for index, mip in enumerate(texture.mips):
        rgba = np.asarray(texture.decode(index))
        if rgba.shape != (mip.height, mip.width, 4):
            raise ValueError('Decoded mip dimensions differ from metadata')
        alpha = rgba[:, :, 3]
        rows.append(dict(index=index, width=mip.width, height=mip.height,
                         payload_file=mip.file, payload_bytes=mip.size,
                         alpha_min=int(alpha.min()), alpha_max=int(alpha.max()),
                         visible_fraction_at_native_cutoff=float(np.mean(alpha >= 85))))
    return dict(format=texture.format, width=texture.width, height=texture.height,
                mip_count=len(rows), gpu_payload_bytes=sum(m.size for m in texture.mips),
                every_mip_opaque=all(r['alpha_min'] == 255 for r in rows),
                fully_discarded_mips=[r['index'] for r in rows if r['alpha_max'] < 85],
                mips=rows)


def validate_manifest(stage, expected):
    if not expected:
        raise ValueError('Missing release asset hashes')
    def check(item):
        name, digest = item
        path = (stage / name).resolve()
        if not path.is_relative_to(stage) or path == stage:
            raise ValueError('Asset path escapes the selected stage')
        if not path.is_file():
            return dict(asset=name, reason='missing')
        elif sha(path) != digest:
            return dict(asset=name, reason='hash_mismatch')
    with ThreadPoolExecutor(max_workers=4) as pool:
        failures = [r for r in pool.map(check,expected.items()) if r is not None]
    actual = {p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
    failures += [dict(asset=n, reason='unexpected') for n in sorted(actual - set(expected))]
    return failures


def import_names(data):
    """Resolve UE4.22 FNames including their separately serialized suffix.

    For example face_162114 is stored as name 'face', number 162115. Searching
    only the raw string table would falsely flag every correctly cooked head.
    """
    names = [name for name,_,_ in name_entries(data)]
    folder_length = struct.unpack_from('<i',data,28)[0]
    count,offset = struct.unpack_from('<ii',data,60+folder_length)
    if not 0 <= count < 10000 or offset < 0 or offset+count*28 > len(data):
        raise ValueError('Unsupported or truncated UE4.22 import table')
    found = set()
    for i in range(count):
        # FObjectImport: ClassPackage FName, ClassName FName, OuterIndex, ObjectName FName.
        index,number = struct.unpack_from('<ii',data,offset+i*28+20)
        if not 0 <= index < len(names) or number < 0:
            raise ValueError('Invalid imported FName')
        found.add(names[index]+('_'+str(number-1) if number else ''))
    return found


def dependency_names(stage, native):
    """Resolved import declarations, not observed runtime texture binding."""
    required = {
        f'{native}_face': {GAME + 'BaseAssets/test_body_Skeleton', GAME + f'RealFace/face_{native}'},
        f'{native}_hair': {GAME + 'BaseAssets/test_body_Skeleton', GAME + 'BaseAssets/hair_parts_tablet_ss'},
        f'face_{native}': {GAME + 'BaseAssets/M_NXFaceSmooth', GAME + f'RealFace/{native}_face_tablet'},
    }
    missing = []
    for stem, names in required.items():
        present = import_names((stage / FACE / (stem + '.uasset')).read_bytes())
        missing += [dict(asset=stem, declaration=n) for n in sorted(names - present)]
    return missing


def audit(stage, verification, output, players=None, received_pak=None):
    stage = Path(stage).resolve()
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT / 'local-debug') or output == ROOT / 'local-debug':
        raise ValueError('Use a separate ignored local-debug report directory')
    report = json.loads(Path(verification).read_text(encoding='utf-8-sig'))
    rows = report['players_in_package']
    if len({r['native_player_id'] for r in rows}) != len(rows) or len({r['base_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate packaged face ownership')
    if players:
        selected = set(players)
        rows = [r for r in rows if r['base_id'] in selected]
        if {r['base_id'] for r in rows} != selected:
            raise ValueError('Requested BaseId is absent from the release')
    failures = validate_manifest(stage, report['asset_hashes'])
    if failures:
        raise ValueError('Stage differs from release: ' + json.dumps(failures[:10]))
    received_hash = sha(received_pak) if received_pak else None
    if received_hash and received_hash != report['pak_sha256']:
        raise ValueError('Received PAK is not this verified release')
    records = []
    for row in rows:
        native = row['native_player_id']
        parts = {}
        for kind, suffix in (('face', '_face_tablet'), ('hair', '_hair_parts_color_tablet')):
            texture = Texture(stage / FACE / (str(native) + suffix + '.uexp'))
            parts[kind] = texture_evidence(texture)
        records.append(dict(base_id=row['base_id'], native_player_id=native, name=row['name'],
                            head_triangles=row['triangles'],
                            missing_dependency_name_declarations=dependency_names(stage, native),
                            textures=parts))
    findings = dict(
        packaged_heads_checked=len(records), staged_assets_hash_checked=len(report['asset_hashes']),
        received_pak_sha256=received_hash, verified_release_pak_sha256=report['pak_sha256'],
        release_verification_sha256=sha(verification),
        dependency_name_failures=sum(len(r['missing_dependency_name_declarations']) for r in records),
        nonopaque_face_base_ids=[r['base_id'] for r in records if not r['textures']['face']['every_mip_opaque']],
        hair_with_fully_discarded_mips=[dict(base_id=r['base_id'], mips=r['textures']['hair']['fully_discarded_mips'])
                                      for r in records if r['textures']['hair']['fully_discarded_mips']],
        texture_format_counts=dict(Counter(p['format'] for r in records for p in r['textures'].values())),
        gpu_colour_payload_bytes=sum(p['gpu_payload_bytes'] for r in records for p in r['textures'].values()),
        players=records, device_appearance_pass=False, hardware_profiled=False,
        limitations=[
            'Name-table presence does not prove the runtime selected this package or parameter.',
            'GPU payload sum covers the selected catalogue, not textures resident during one match.',
            'Bounds, animation, material binding and GPU state still require separate evidence.',
            'Fully discarded hair mips can be intentional for empty hair placeholders; inspect the mesh before changing alpha.',
        ])
    output.mkdir(parents=True, exist_ok=True)
    (output / 'asset-audit.json').write_text(json.dumps(findings, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in findings.items() if k not in ('players', 'limitations')}, indent=2))
    return findings


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True)
    parser.add_argument('--verification', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--received-pak')
    parser.add_argument('--player', type=int, action='append')
    args = parser.parse_args()
    audit(args.stage, args.verification, args.output, args.player, args.received_pak)

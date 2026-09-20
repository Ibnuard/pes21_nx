"""Apply an identity-guarded, player-local PES21 appearance skin override.

The 60-byte appearance row stores the native skin selector in bits 0..2 of
byte 37. Supported native body textures are skin1..skin6. No mesh, face ID,
physique field, shared texture, or other player's record is changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from convert_efootball10_players import encode_pes21_wesys
from pesdb import decode_wesys


def patch_skin(raw: bytes, registry: dict, base_id: int, fingerprint: str,
               expected_row_sha256: str, skin: int) -> tuple[bytes, dict]:
    if len(raw) == 0 or len(raw) % 60:
        raise ValueError('Appearance table must contain complete 60-byte rows')
    if not 1 <= skin <= 6:
        raise ValueError('Native skin index must be 1..6')
    owners = [r for r in registry['players'] if r['ef_base_id'] == base_id]
    if len(owners) != 1 or owners[0].get('status') != 'active':
        raise ValueError('Expected one active BaseId identity')
    owner = owners[0]
    if not fingerprint or owner['fingerprint'] != fingerprint:
        raise ValueError('Player identity fingerprint mismatch')
    native_id = owner['native_player_id']
    if sum(r['native_player_id'] == native_id and r.get('status') == 'active'
           for r in registry['players']) != 1:
        raise ValueError('Native player slot has multiple active owners')
    offsets = [o for o in range(0, len(raw), 60)
               if struct.unpack_from('<I', raw, o)[0] == native_id]
    if len(offsets) != 1:
        raise ValueError('Expected exactly one target appearance row')
    offset = offsets[0]
    row = raw[offset:offset + 60]
    if hashlib.sha256(row).hexdigest() != expected_row_sha256:
        raise ValueError('Target appearance row changed; audit before retrying')
    result = bytearray(raw)
    result[offset + 37] = (result[offset + 37] & 0xf8) | skin
    return bytes(result), {
        'base_id': base_id, 'native_player_id': native_id,
        'fingerprint': fingerprint, 'name': owner['canonical_name'],
        'skin_before': row[37] & 7, 'skin_after': skin,
        'row_offset': offset, 'row_sha256_before': expected_row_sha256,
        'row_sha256_after': hashlib.sha256(result[offset:offset + 60]).hexdigest(),
        'changed_byte_offsets': [i for i, (a, b) in enumerate(zip(raw, result)) if a != b],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--registry', type=Path, required=True)
    p.add_argument('--base-id', type=int, required=True)
    p.add_argument('--fingerprint', required=True)
    p.add_argument('--expect-row-sha256', required=True)
    p.add_argument('--skin', type=int, required=True)
    a = p.parse_args()
    report = a.output.with_suffix('.skin-report.json')
    if a.output.exists() or report.exists():
        raise ValueError('Refusing to overwrite an existing output/report')
    source = a.input.read_bytes()
    wrapped = source[3:8] == b'WESYS'
    raw = decode_wesys(a.input) if wrapped else source
    patched, audit = patch_skin(raw, json.loads(a.registry.read_text()),
                               a.base_id, a.fingerprint, a.expect_row_sha256, a.skin)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(encode_pes21_wesys(patched) if wrapped else patched)
    check = decode_wesys(a.output) if wrapped else a.output.read_bytes()
    if check != patched:
        raise RuntimeError('Output appearance failed round-trip validation')
    audit.update(input_sha256=hashlib.sha256(source).hexdigest(),
                 output_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest())
    report.write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()

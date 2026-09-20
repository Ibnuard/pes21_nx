import hashlib
import struct
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from patch_player_skin import patch_skin
from convert_efootball10_players import encode_pes21_wesys
from pesdb import decode_wesys


def fixture():
    rows = [struct.pack('<I', i) + bytes([0xa9]) * 56 for i in (10, 20, 30)]
    registry = {'players': [{'ef_base_id': 99, 'native_player_id': 20,
                            'fingerprint': 'verified', 'status': 'active',
                            'canonical_name': 'Synthetic player'}]}
    return b''.join(rows), registry, hashlib.sha256(rows[1]).hexdigest()


def test_only_target_skin_bits_change():
    raw, registry, digest = fixture()
    out, report = patch_skin(raw, registry, 99, 'verified', digest, 4)
    assert report['changed_byte_offsets'] == [97]
    assert out[97] == 0xac
    assert out[:97] == raw[:97] and out[98:] == raw[98:]
    assert report['skin_before'] == 1 and report['skin_after'] == 4
    assert len(out) == len(raw)


@pytest.mark.parametrize('skin', [0, 7, -1, 100])
def test_invalid_native_skin(skin):
    raw, registry, digest = fixture()
    with pytest.raises(ValueError):
        patch_skin(raw, registry, 99, 'verified', digest, skin)


def test_identity_and_row_guards():
    raw, registry, digest = fixture()
    for base, fingerprint, row_hash in [(100, 'verified', digest),
                                       (99, 'wrong', digest),
                                       (99, 'verified', 'wrong')]:
        with pytest.raises(ValueError):
            patch_skin(raw, registry, base, fingerprint, row_hash, 4)
    for invalid in (raw[:-1], raw[:60], raw + raw[60:120], b''):
        with pytest.raises(ValueError):
            patch_skin(invalid, registry, 99, 'verified', digest, 4)


def test_duplicate_native_owner_rejected():
    raw, registry, digest = fixture()
    registry['players'].append(dict(registry['players'][0], ef_base_id=100))
    with pytest.raises(ValueError):
        patch_skin(raw, registry, 99, 'verified', digest, 4)


def test_idempotent_same_skin():
    raw, registry, digest = fixture()
    out, report = patch_skin(raw, registry, 99, 'verified', digest, 1)
    assert out == raw and report['changed_byte_offsets'] == []


@pytest.mark.parametrize('wrapped', [False, True])
def test_cli_roundtrip_and_no_overwrite(tmp_path, wrapped):
    import json
    raw, registry, digest = fixture()
    source = tmp_path / 'source.bin'
    output = tmp_path / 'patched.bin'
    registry_path = tmp_path / 'registry.json'
    source.write_bytes(encode_pes21_wesys(raw) if wrapped else raw)
    registry_path.write_text(json.dumps(registry))
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'tools/patch_player_skin.py'),
               '--input', str(source), '--output', str(output),
               '--registry', str(registry_path), '--base-id', '99',
               '--fingerprint', 'verified', '--expect-row-sha256', digest, '--skin', '4']
    subprocess.run(command, check=True, capture_output=True)
    actual = decode_wesys(output) if wrapped else output.read_bytes()
    assert actual == patch_skin(raw, registry, 99, 'verified', digest, 4)[0]
    assert (decode_wesys(source) if wrapped else source.read_bytes()) == raw
    assert subprocess.run(command, capture_output=True).returncode != 0

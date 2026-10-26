"""Repair the v93 score packet length field without changing native artwork.

Only the pinned detached archive is accepted. Game-derived inputs/outputs stay
local. Native payload/source identities, movies, pixels and other members are
preserved; the NXSB target checksum is refreshed for the four repaired bytes.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct

from build_footballnx27_scoreboard import HEADER
from pack_runtime_assets import read_archive, pack_entries, checksum

BASELINE_SHA = 'fedd91d229bbba49c328efd05d7cc73c8b0072bff9222518b687a534eca95d39'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def repair_packet(packet):
    if len(packet) < 140:
        raise ValueError('truncated NXSB packet')
    magic, source_size, size, source_hash, target_hash = HEADER.unpack_from(packet)
    payload = packet[32:]
    if (magic != b'NXSB01\0\0' or size != len(payload) or
            checksum(payload) != target_hash or payload[:4] != b'TXP2'):
        raise ValueError('invalid NXSB target identity')
    if struct.unpack_from('>I', payload, 12)[0] == size:
        raise ValueError('target size is already valid')
    length = struct.unpack_from('<I', payload, 12)[0]
    if not size - 15 <= length <= size or any(payload[length:]):
        raise ValueError('not the measured little-endian length regression')
    result = bytearray(payload[:length])
    struct.pack_into('>I', result, 12, length)
    result = bytes(result)
    return HEADER.pack(magic, source_size, length, source_hash, checksum(result)) + result


def stage(source, output):
    if digest(source.read_bytes()) != BASELINE_SHA:
        raise ValueError('requires the pinned v93 archive')
    output.mkdir(parents=True, exist_ok=True)
    _, before = read_archive(source)
    after = dict(before)
    changes = {}
    for name, packet in before.items():
        if not name.startswith('scoreboards/c') or not name.endswith('.nxsb'):
            continue
        fixed = repair_packet(packet)
        after[name] = fixed
        changes[name] = {'source_sha256': digest(packet), 'sha256': digest(fixed),
                         'bytes': len(fixed), 'native_payload_bytes_changed': 4,
                         'removed_zero_alignment_bytes': len(packet)-len(fixed)}
    if len(changes) != 23:
        raise ValueError('unexpected scoreboard cohort')
    archive = output / 'FootballNX.assets'
    pack_entries(after, archive)
    _, verified = read_archive(archive)
    if verified != after:
        raise ValueError('archive roundtrip differs')
    protected = {name: digest(data) for name, data in before.items() if name not in changes}
    if any(verified[name] != before[name] for name in protected):
        raise ValueError('unrelated archive member changed')
    for name in changes:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(after[name])
    report = {'status': 'detached_asset_candidate_not_installed', 'baseline_sha256': BASELINE_SHA,
              'sha256': digest(archive.read_bytes()), 'bytes': archive.stat().st_size,
              'changed_packets': changes, 'protected_members': protected,
              'native_scripts_pixels_rounding_aggregate_exact': True,
              'device_accepted': False}
    (output / 'REPAIR-REPORT.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = stage(args.source, args.output)
    print(json.dumps({k: report[k] for k in ('status', 'sha256', 'bytes')}))

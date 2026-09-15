"""Recolor the native corporate fade rectangle, preserving its geometry."""
import json
import struct
from pathlib import Path

from build_androswitch_corporate_splash import (
    member_bytes, extract_member, decode_wesys, encode_wesys, sha256_file,
)
from patch_cpk_slots import patch_slots


def patch_backdrop(raw):
    before = bytes.fromhex('b60014ff')
    if raw.count(before) != 1:
        raise ValueError('corporate red color must occur exactly once')
    color = raw.index(before)
    geo = color - 92
    if raw[geo:geo + 4] != b'GE2D' or struct.unpack_from('>I', raw, geo + 12)[0] != 112:
        raise ValueError('unexpected corporate background geometry')
    if raw[geo + 84:color] != bytes.fromhex('0409ffff00060000'):
        raise ValueError('unexpected corporate fill record')
    # Matches the flat background of the packaged AndroSwitch splash.
    result = raw[:color] + bytes((0, 28, 97, 255)) + raw[color + 4:]
    assert len(result) == len(raw)
    assert result[:color] == raw[:color] and result[color + 4:] == raw[color + 4:]
    return result, color


def main():
    root = Path('local-debug/startup-brand-v4')
    work = root / 'cpk-work'
    work.mkdir(parents=True, exist_ok=True)
    source = Path('local-debug/startup-brand-v3/install/patch.305030001.jp.nyan2021.pesam.obb')
    inner_name = 'Expansion/dt210_mobile_android.cpk'
    member = 'common/menu/general/titleCorporate.bin'
    inner = work / 'dt210-source.cpk'
    patched = work / 'dt210-blue.cpk'
    payload_path = work / 'titleCorporate-blue.bin'
    output = root / 'install' / source.name
    if any(p.exists() for p in (inner, patched, payload_path, output)):
        raise FileExistsError('build output already exists')
    extract_member(source, inner_name, inner)
    payload = member_bytes(inner, member)
    raw, offset = patch_backdrop(decode_wesys(payload))
    payload_path.write_bytes(encode_wesys(raw, payload[:8]))
    inner_report = patch_slots(inner, patched, {member: payload_path})
    outer_report = patch_slots(source, output, {inner_name: patched})
    report = {'output': str(output), 'sha256': sha256_file(output),
              'color_offset': offset, 'old_rgba': '#B60014FF',
              'new_rgba': '#001C61FF', 'inner': inner_report, 'outer': outer_report}
    (root / 'blue-backdrop-report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'output': str(output), 'sha256': report['sha256']}))


if __name__ == '__main__':
    main()

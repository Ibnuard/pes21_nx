#!/usr/bin/env python3
"""Prepare, verify, and update loose CPK runtime packages.

V1 is the two-pack hardware canary and retains the original OBB. V2 extracts
all 24 nested CPKs and emits a tiny valid OBB containing placeholder members.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct

from prepare_runtime import read_cpk_packet
from repack_cpk_members import patch_utf_rows

PATCH_OBB = 'patch.305030001.jp.nyan2021.pesam.obb'
CANARY_NAMES = ('dt200_mobile_all.cpk', 'dt241_mobile_all.cpk')
FULL_NAMES = (
    'dt120_mobile_all.cpk',
    'dt200_mobile_all.cpk',
    'dt210_mobile_android.cpk',
    'dt220_mobile_all.cpk',
    'dt230_mobile_all.cpk',
    'dt240_mobile_all.cpk',
    'dt241_mobile_all.cpk',
    'dt250_mobile_all.cpk',
    'dt260_mobile_all.cpk',
    'dt270_mobile_all.cpk',
    'dt500_mobile_all.cpk',
    'dt520_mobile_all.cpk',
    'dt530_mobile_bra_all.cpk',
    'dt530_mobile_can_all.cpk',
    'dt530_mobile_eng_all.cpk',
    'dt530_mobile_fra_all.cpk',
    'dt530_mobile_ger_all.cpk',
    'dt530_mobile_ita_all.cpk',
    'dt530_mobile_jpn_all.cpk',
    'dt530_mobile_kor_all.cpk',
    'dt530_mobile_man_all.cpk',
    'dt530_mobile_spa_all.cpk',
    'dt540_mobile_all.cpk',
    'dt700_mobile_android.cpk',
)
NAMES = CANARY_NAMES
MAGIC_V1 = 'PESNX_LOOSE_CPK_V1'
MAGIC_V2 = 'PESNX_LOOSE_CPK_V2'


def align(value: int, boundary: int) -> int:
    return (value + boundary - 1) // boundary * boundary


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def member_name(row: dict) -> str:
    return '/'.join(
        str(part) for part in (row.get('DirName'), row.get('FileName'))
        if part not in (None, '', '<NULL>')
    )


def cpk_layout(path: Path) -> tuple[dict, list[dict], int]:
    with path.open('rb') as stream:
        header_rows = read_cpk_packet(stream, 0, b'CPK ')
        if len(header_rows) != 1:
            raise ValueError(f'Invalid CPK header: {path}')
        header = header_rows[0]
        toc = int(header['TocOffset'])
        rows = read_cpk_packet(stream, toc, b'TOC ')
        return header, rows, min(toc, int(header['ContentOffset']))


def checked_cpk(path: Path) -> None:
    _header, rows, base = cpk_layout(path)
    size = path.stat().st_size
    if not rows:
        raise ValueError(f'Empty CPK: {path}')
    for row in rows:
        offset, length = base + int(row['FileOffset']), int(row['FileSize'])
        if offset < 0 or length < 0 or offset + length > size:
            raise ValueError(f'Out-of-bounds CPK member: {path}')


def source_members(obb: Path, expected: tuple[str, ...]) -> list[tuple[str, int, int]]:
    _header, rows, base = cpk_layout(obb)
    layout = tuple(member_name(row).removeprefix('Expansion/') for row in rows)
    if expected == FULL_NAMES and layout != FULL_NAMES:
        raise ValueError('Source OBB does not have the approved 24-member layout')
    result = []
    size = obb.stat().st_size
    by_name = {member_name(row).removeprefix('Expansion/'): row for row in rows}
    for name in expected:
        row = by_name.get(name)
        if row is None:
            raise ValueError(f'Missing source member: {name}')
        length = int(row['FileSize'])
        offset = base + int(row['FileOffset'])
        if (length != int(row['ExtractSize']) or length <= 0 or offset < 0 or
                offset + length > size):
            raise ValueError(f'Compressed/invalid source member: {name}')
        result.append((name, offset, length))
    return result


def read_manifest(root: Path) -> dict:
    lines = (root / 'LooseCpk/manifest.txt').read_text(encoding='ascii').splitlines()
    if not lines:
        raise ValueError('Empty loose CPK manifest')
    header = lines[0].split()
    if len(header) == 3 and header[0] == MAGIC_V1:
        version, names, parent_sha = 1, CANARY_NAMES, None
    elif len(header) == 4 and header[0] == MAGIC_V2:
        version, names, parent_sha = 2, FULL_NAMES, header[3]
        if not re.fullmatch('[0-9a-f]{64}', parent_sha):
            raise ValueError('Invalid dummy OBB hash')
    else:
        raise ValueError('Invalid loose CPK manifest header')
    if len(lines) != len(names) + 1 or not re.fullmatch('[0-9a-f]{16}', header[1]):
        raise ValueError('Invalid manifest version/build ID or entry count')
    parent_size = int(header[2])
    if parent_size <= 0:
        raise ValueError('Invalid parent OBB size')
    rows = []
    for name, line in zip(names, lines[1:]):
        fields = line.split()
        if (len(fields) != 3 or fields[0] != name or int(fields[1]) <= 0 or
                not re.fullmatch('[0-9a-f]{64}', fields[2])):
            raise ValueError(f'Invalid manifest entry: {line}')
        rows.append(dict(name=name, size=int(fields[1]), sha256=fields[2]))
    return dict(version=version, build_id=header[1], parent_obb_bytes=parent_size,
                parent_obb_sha256=parent_sha, files=rows)


def write_manifest(root: Path, manifest: dict) -> None:
    magic = MAGIC_V2 if manifest['version'] == 2 else MAGIC_V1
    text = f"{magic} {manifest['build_id']} {manifest['parent_obb_bytes']}"
    if manifest['version'] == 2:
        text += f" {manifest['parent_obb_sha256']}"
    text += '\n'
    text += ''.join(f"{r['name']} {r['size']} {r['sha256']}\n"
                    for r in manifest['files'])
    path = root / 'LooseCpk/manifest.txt'
    temp = path.with_suffix('.part')
    with temp.open('x', encoding='ascii', newline='\n') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def checked_dummy_obb(path: Path) -> None:
    _header, rows, base = cpk_layout(path)
    layout = tuple(member_name(row).removeprefix('Expansion/') for row in rows)
    if layout != FULL_NAMES:
        raise ValueError('Dummy OBB member list/order mismatch')
    with path.open('rb') as stream:
        for row in rows:
            if int(row['FileSize']) != 4 or int(row['ExtractSize']) != 4:
                raise ValueError('Dummy OBB contains a non-placeholder member')
            stream.seek(base + int(row['FileOffset']))
            if stream.read(4) != b'CPK ':
                raise ValueError('Dummy OBB placeholder signature mismatch')


def build_dummy_obb(source_path: Path, output_path: Path) -> None:
    header, rows, data_base = cpk_layout(source_path)
    layout = tuple(member_name(row).removeprefix('Expansion/') for row in rows)
    if layout != FULL_NAMES:
        raise ValueError('Cannot build dummy from an unexpected OBB layout')
    toc_offset = int(header['TocOffset'])
    content_offset = int(header['ContentOffset'])
    alignment = int(header['Align'])
    with source_path.open('rb') as source:
        prefix = bytearray(source.read(content_offset))
        if len(prefix) != content_offset:
            raise ValueError('Truncated OBB prefix')
        cursor = content_offset
        updates = [{} for _ in rows]
        payload_offsets = []
        for row_index, row in sorted(enumerate(rows), key=lambda item: int(item[1]['FileOffset'])):
            cursor = align(cursor, alignment)
            updates[row_index] = dict(FileOffset=cursor - data_base, FileSize=4, ExtractSize=4)
            payload_offsets.append(cursor)
            cursor += 4
        final_size = align(cursor, alignment)

        source.seek(toc_offset)
        toc_packet_header = source.read(16)
        toc_packet_size = struct.unpack_from('<Q', toc_packet_header, 8)[0]
        toc_packet = source.read(toc_packet_size)
        patched_toc = patch_utf_rows(toc_packet, updates)
        prefix[toc_offset + 16:toc_offset + 16 + toc_packet_size] = patched_toc

        source.seek(0)
        cpk_packet_header = source.read(16)
        cpk_packet_size = struct.unpack_from('<Q', cpk_packet_header, 8)[0]
        cpk_packet = source.read(cpk_packet_size)
        header_update = dict(ContentSize=final_size - content_offset,
                             EnabledPackedSize=4 * len(rows),
                             EnabledDataSize=4 * len(rows), Files=len(rows))
        patched_header = patch_utf_rows(cpk_packet, [header_update])
        prefix[16:16 + cpk_packet_size] = patched_header

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('xb') as output:
        output.write(prefix)
        for offset in payload_offsets:
            if output.tell() < offset:
                output.write(b'\0' * (offset - output.tell()))
            if output.tell() != offset:
                raise RuntimeError('Dummy OBB content offset ordering failure')
            output.write(b'CPK ')
        if output.tell() < final_size:
            output.write(b'\0' * (final_size - output.tell()))
    checked_dummy_obb(output_path)


def verify(root: Path, obb: Path | None = None) -> dict:
    result = read_manifest(root)
    if result['version'] == 1:
        if obb is not None and obb.stat().st_size != result['parent_obb_bytes']:
            raise ValueError('Parent OBB size mismatch')
    else:
        dummy = root / PATCH_OBB
        if (dummy.stat().st_size != result['parent_obb_bytes'] or
                digest(dummy) != result['parent_obb_sha256']):
            raise ValueError('Missing/corrupt dummy OBB')
        checked_dummy_obb(dummy)
    for row in result['files']:
        path = root / 'LooseCpk' / row['name']
        if (path.is_symlink() or path.stat().st_size != row['size'] or
                digest(path) != row['sha256']):
            raise ValueError(f"Missing/corrupt loose CPK: {row['name']}")
        checked_cpk(path)
    return result


def extract_members(obb: Path, target: Path, names: tuple[str, ...]) -> list[dict]:
    selected = source_members(obb, names)
    rows = []
    with obb.open('rb') as stream:
        for name, offset, size in selected:
            stream.seek(offset)
            destination = target / name
            temp = destination.with_suffix('.part')
            sha = hashlib.sha256()
            with temp.open('xb') as out:
                remaining = size
                while remaining:
                    chunk = stream.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError(f'Truncated source: {name}')
                    sha.update(chunk)
                    out.write(chunk)
                    remaining -= len(chunk)
            checked_cpk(temp)
            os.replace(temp, destination)
            rows.append(dict(name=name, size=size, sha256=sha.hexdigest()))
    return rows


def extract(obb: Path, root: Path, build: str) -> dict:
    if not re.fullmatch('[0-9a-f]{16}', build):
        raise ValueError('Build ID must contain 16 lowercase hexadecimal characters')
    target = root / 'LooseCpk'
    if target.exists():
        raise ValueError(f'Refusing to overwrite existing package: {target}')
    target.mkdir(parents=True)
    rows = extract_members(obb, target, CANARY_NAMES)
    manifest = dict(version=1, build_id=build, parent_obb_bytes=obb.stat().st_size,
                    parent_obb_sha256=None, files=rows)
    write_manifest(root, manifest)
    result = verify(root, obb)
    result['source_obb_sha256'] = digest(obb)
    (root / 'loose-cpk-source.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def extract_full(obb: Path, root: Path, build: str) -> dict:
    if not re.fullmatch('[0-9a-f]{16}', build):
        raise ValueError('Build ID must contain 16 lowercase hexadecimal characters')
    target = root / 'LooseCpk'
    dummy = root / PATCH_OBB
    if target.exists() or dummy.exists():
        raise ValueError(f'Refusing to overwrite existing full package: {root}')
    target.mkdir(parents=True)
    rows = extract_members(obb, target, FULL_NAMES)
    build_dummy_obb(obb, dummy)
    manifest = dict(version=2, build_id=build, parent_obb_bytes=dummy.stat().st_size,
                    parent_obb_sha256=digest(dummy), files=rows)
    write_manifest(root, manifest)
    result = verify(root)
    result['source_obb_bytes'] = obb.stat().st_size
    result['source_obb_sha256'] = digest(obb)
    (root / 'loose-cpk-source.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def clone_full(source_root: Path, root: Path, build: str) -> dict:
    """Clone a verified V2 package without duplicating unchanged payloads.

    Hard links make a new migration candidate cheap on disk.  Subsequent
    ``update`` calls publish replacements with ``os.replace``, so the source
    checkpoint remains byte-identical.  Copying is the safe fallback when the
    two roots are on different volumes or the filesystem rejects hard links.
    """
    if not re.fullmatch('[0-9a-f]{16}', build):
        raise ValueError('Build ID must contain 16 lowercase hexadecimal characters')
    source = verify(source_root)
    if source['version'] != 2:
        raise ValueError('Only a full V2 loose CPK package can be cloned')
    target = root / 'LooseCpk'
    dummy = root / PATCH_OBB
    if target.exists() or dummy.exists():
        raise ValueError(f'Refusing to overwrite existing full package: {root}')
    target.mkdir(parents=True)

    def link_or_copy(source_path: Path, destination: Path) -> str:
        try:
            os.link(source_path, destination)
            return 'hardlink'
        except OSError:
            shutil.copy2(source_path, destination)
            return 'copy'

    modes = []
    for row in source['files']:
        modes.append(link_or_copy(
            source_root / 'LooseCpk' / row['name'], target / row['name']))
    modes.append(link_or_copy(source_root / PATCH_OBB, dummy))
    manifest = dict(
        version=2,
        build_id=build,
        parent_obb_bytes=source['parent_obb_bytes'],
        parent_obb_sha256=source['parent_obb_sha256'],
        files=[dict(row) for row in source['files']],
    )
    write_manifest(root, manifest)
    result = verify(root)
    result['clone_mode'] = 'hardlink' if set(modes) == {'hardlink'} else 'mixed_or_copy'
    return result


def update(root: Path, member: str, source: Path) -> dict:
    result = verify(root)
    names = tuple(row['name'] for row in result['files'])
    if member not in names:
        raise ValueError(f'Unsupported member for this package: {member}')
    checked_cpk(source)
    destination = root / 'LooseCpk' / member
    sha = digest(source)
    row = next(row for row in result['files'] if row['name'] == member)
    if row['sha256'] == sha:
        return dict(result, changed=[])
    cache = root / 'LooseCpk/verified-v2.txt'
    if result['version'] == 2:
        cache.unlink(missing_ok=True)
    temp = destination.with_suffix('.part')
    with source.open('rb') as src, temp.open('xb') as out:
        while chunk := src.read(1024 * 1024):
            out.write(chunk)
        out.flush()
        os.fsync(out.fileno())
    if digest(temp) != sha:
        raise ValueError('Source changed while copying')
    size = temp.stat().st_size
    os.replace(temp, destination)
    row.update(size=size, sha256=sha)
    write_manifest(root, result)
    return dict(verify(root), changed=[f'LooseCpk/{member}', 'LooseCpk/manifest.txt'])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('extract', 'extract-full'):
        p = sub.add_parser(command)
        p.add_argument('--obb', type=Path, required=True)
        p.add_argument('--output', type=Path, required=True)
        p.add_argument('--build-id', required=True)
    p = sub.add_parser('clone-full')
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--build-id', required=True)
    p = sub.add_parser('verify')
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--obb', type=Path)
    p = sub.add_parser('update')
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--member', required=True)
    p.add_argument('--file', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'extract':
        result = extract(args.obb, args.output, args.build_id)
    elif args.command == 'extract-full':
        result = extract_full(args.obb, args.output, args.build_id)
    elif args.command == 'clone-full':
        result = clone_full(args.source, args.output, args.build_id)
    elif args.command == 'verify':
        result = verify(args.root, args.obb)
    else:
        result = update(args.root, args.member, args.file)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

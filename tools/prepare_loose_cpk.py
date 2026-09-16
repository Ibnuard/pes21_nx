#!/usr/bin/env python3
"""Prepare/verify a two-pack loose CPK canary from a user-owned patch OBB.

The parent OBB is retained. Updates replace one CPK and publish the manifest
last; an interrupted copy fails runtime validation instead of falling back.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from prepare_runtime import read_cpk_packet

NAMES = ('dt200_mobile_all.cpk', 'dt241_mobile_all.cpk')
MAGIC = 'PESNX_LOOSE_CPK_V1'


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checked_cpk(path: Path) -> None:
    with path.open('rb') as stream:
        rows = read_cpk_packet(stream, 0, b'CPK ')
        if len(rows) != 1:
            raise ValueError(f'Invalid CPK header: {path}')
        header = rows[0]
        toc = int(header['TocOffset'])
        base = min(toc, int(header['ContentOffset']))
        members = read_cpk_packet(stream, toc, b'TOC ')
        size = path.stat().st_size
        if not members:
            raise ValueError(f'Empty CPK: {path}')
        for row in members:
            offset, length = base + int(row['FileOffset']), int(row['FileSize'])
            if offset < 0 or length < 0 or offset + length > size:
                raise ValueError(f'Out-of-bounds CPK member: {path}')


def read_manifest(root: Path) -> tuple[str, int, list[dict]]:
    lines = (root / 'LooseCpk/manifest.txt').read_text(encoding='ascii').splitlines()
    if len(lines) != 3:
        raise ValueError('Manifest must contain header and exactly two CPKs')
    magic, build, parent_size = lines[0].split()
    if magic != MAGIC or not re.fullmatch('[0-9a-f]{16}', build):
        raise ValueError('Invalid manifest version/build ID')
    rows = []
    for name, line in zip(NAMES, lines[1:]):
        actual, size, sha = line.split()
        if actual != name or int(size) <= 0 or not re.fullmatch('[0-9a-f]{64}', sha):
            raise ValueError(f'Invalid manifest entry: {line}')
        rows.append(dict(name=name, size=int(size), sha256=sha))
    if int(parent_size) <= 0:
        raise ValueError('Invalid parent OBB size')
    return build, int(parent_size), rows


def write_manifest(root: Path, build: str, parent_size: int, rows: list[dict]) -> None:
    text = f'{MAGIC} {build} {parent_size}\n'
    text += ''.join(f"{r['name']} {r['size']} {r['sha256']}\n" for r in rows)
    path = root / 'LooseCpk/manifest.txt'
    temp = path.with_suffix('.part')
    with temp.open('x', encoding='ascii', newline='\n') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def verify(root: Path, obb: Path | None = None) -> dict:
    build, parent_size, rows = read_manifest(root)
    if obb is not None and obb.stat().st_size != parent_size:
        raise ValueError('Parent OBB size mismatch')
    for row in rows:
        path = root / 'LooseCpk' / row['name']
        if path.is_symlink() or path.stat().st_size != row['size'] or digest(path) != row['sha256']:
            raise ValueError(f"Missing/corrupt loose CPK: {row['name']}")
        checked_cpk(path)
    return dict(build_id=build, parent_obb_bytes=parent_size, files=rows)


def extract(obb: Path, root: Path, build: str) -> dict:
    if not re.fullmatch('[0-9a-f]{16}', build):
        raise ValueError('Build ID must contain 16 lowercase hexadecimal characters')
    target = root / 'LooseCpk'
    if target.exists():
        raise ValueError(f'Refusing to overwrite existing package: {target}')
    with obb.open('rb') as stream:
        header = read_cpk_packet(stream, 0, b'CPK ')[0]
        toc = int(header['TocOffset'])
        base = min(toc, int(header['ContentOffset']))
        entries = read_cpk_packet(stream, toc, b'TOC ')
        selected = []
        for name in NAMES:
            matches = [r for r in entries if r['FileName'] == name]
            if len(matches) != 1:
                raise ValueError(f'Expected one source member: {name}')
            row = matches[0]
            size = int(row['FileSize'])
            offset = base + int(row['FileOffset'])
            if size != int(row['ExtractSize']) or size <= 0 or offset < 0 or offset + size > obb.stat().st_size:
                raise ValueError(f'Compressed/invalid source member: {name}')
            selected.append((name, offset, size))
        target.mkdir(parents=True)
        rows = []
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
    write_manifest(root, build, obb.stat().st_size, rows)
    result = verify(root, obb)
    result['source_obb_sha256'] = digest(obb)
    (root / 'loose-cpk-source.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def update(root: Path, member: str, source: Path) -> dict:
    if member not in NAMES:
        raise ValueError('Only dt200 and dt241 are supported in this canary')
    result = verify(root)
    checked_cpk(source)
    destination = root / 'LooseCpk' / member
    sha = digest(source)
    row = next(r for r in result['files'] if r['name'] == member)
    if row['sha256'] == sha:
        return dict(result, changed=[])
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
    write_manifest(root, result['build_id'], result['parent_obb_bytes'], result['files'])
    return dict(verify(root), changed=[f'LooseCpk/{member}', 'LooseCpk/manifest.txt'])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('extract')
    p.add_argument('--obb', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--build-id', required=True)
    p = sub.add_parser('verify')
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--obb', type=Path)
    p = sub.add_parser('update')
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--member', choices=NAMES, required=True)
    p.add_argument('--file', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'extract':
        result = extract(args.obb, args.output, args.build_id)
    elif args.command == 'verify':
        result = verify(args.root, args.obb)
    else:
        result = update(args.root, args.member, args.file)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

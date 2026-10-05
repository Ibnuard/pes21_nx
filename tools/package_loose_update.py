#!/usr/bin/env python3
"""Create a copy-only NRO/LooseCpk delta against explicitly verified baselines.

Build/audit files stay outside the payload. This is not a complete runtime
installer: unchanged files must already be installed from a listed baseline.
Requires pyelftools from tools/native-audit-requirements.txt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile

from prepare_loose_cpk import PATCH_OBB, digest, verify


def check_nro_payload(payload: bytes, build_id: str, symbol: tuple[int, bytes],
                      loads: list[tuple[int, bytes]]) -> None:
    """Match the executable, not an arbitrary build-ID string in an asset."""
    if len(payload) < 128 or payload[16:20] != b'NRO0':
        raise ValueError('Invalid NRO header')
    size = struct.unpack_from('<I', payload, 24)[0]
    segments = [struct.unpack_from('<II', payload, offset) for offset in (32, 40, 48)]
    if not 128 <= size <= len(payload) or len(loads) != 3:
        raise ValueError('Invalid NRO/ELF segment layout')
    end = 0
    for (offset, length), (address, data) in zip(segments, loads):
        if offset != end or not length or offset + length > size:
            raise ValueError('Invalid NRO segment bounds')
        if address != offset or len(data) > length:
            raise ValueError('NRO/ELF load segment mismatch')
        # elf2nro fills the first 128 bytes with its executable header.
        skip = 128 if offset == 0 else 0
        if payload[offset + skip:offset + len(data)] != data[skip:]:
            raise ValueError('NRO does not match the supplied ELF')
        end = offset + length
    if end != size:
        raise ValueError('Invalid NRO executable size')
    address, value = symbol
    expected = build_id.encode('ascii') + b'\0'
    if value != expected or not any(
        start <= address and address + len(value) <= start + len(data)
        for start, data in loads
    ) or payload[address:address + len(value)] != expected:
        raise ValueError('NRO/ELF migration build ID differs from manifest')


def verify_nro(root: Path, build_id: str) -> dict:
    from elftools.elf.elffile import ELFFile

    nro, elf_path = root / 'pes21_nx.nro', root / 'pes21_nx.elf'
    with elf_path.open('rb') as stream:
        elf = ELFFile(stream)
        if elf.elfclass != 64 or not elf.little_endian or elf['e_machine'] != 'EM_AARCH64':
            raise ValueError('Expected a Switch AArch64 ELF')
        table = elf.get_section_by_name('.symtab')
        symbols = [] if table is None else [s for s in table.iter_symbols() if
            s.name == 'exhibition_player_migration_build_id' or
            s.name.startswith('exhibition_player_migration_build_id.')]
        if len(symbols) != 1 or not isinstance(symbols[0]['st_shndx'], int):
            raise ValueError('Expected one compiled migration build-ID symbol')
        symbol = symbols[0]
        section = elf.get_section(symbol['st_shndx'])
        start = symbol['st_value'] - section['sh_addr']
        value = section.data()[start:start + symbol['st_size']]
        loads = [(s['p_vaddr'], s.data()) for s in elf.iter_segments()
                 if s['p_type'] == 'PT_LOAD']
        payload = nro.read_bytes()
        check_nro_payload(payload, build_id, (symbol['st_value'], value), loads)
    return dict(size=len(payload), sha256=hashlib.sha256(payload).hexdigest())


def verified_full(root: Path) -> dict:
    manifest = verify(root)
    if manifest['version'] != 2:
        raise ValueError('Copy-only updates require a full V2 baseline/candidate')
    # read_manifest accepts whitespace that the native prefix check rejects.
    expected = (f"PESNX_LOOSE_CPK_V2 {manifest['build_id']} "
                f"{manifest['parent_obb_bytes']} {manifest['parent_obb_sha256']}")
    raw = (root / 'LooseCpk/manifest.txt').read_bytes()
    if raw.splitlines()[0] != expected.encode('ascii'):
        raise ValueError('Manifest header is not in the canonical native format')
    return manifest


def package_update(candidate: Path, baselines: list[Path], output: Path) -> dict:
    candidate, output = candidate.resolve(), output.resolve()
    baselines = [path.resolve() for path in baselines]
    if not baselines:
        raise ValueError('Specify at least one supported installed baseline')
    if output.exists():
        raise FileExistsError('Use a fresh copy-only output folder; refusing to overwrite')
    if any(output.is_relative_to(path) for path in [candidate, *baselines]):
        raise ValueError('Keep the copy-only folder outside candidate/baseline folders')
    current = verified_full(candidate)
    nro = verify_nro(candidate, current['build_id'])
    previous = [verified_full(path) for path in baselines]
    changed = [row for index, row in enumerate(current['files'])
               if any(row != old['files'][index] for old in previous)]
    files = [('pes21_nx.nro', nro)]
    files += [('LooseCpk/' + row['name'], row) for row in changed]
    if any((old['parent_obb_bytes'], old['parent_obb_sha256']) !=
           (current['parent_obb_bytes'], current['parent_obb_sha256']) for old in previous):
        files.append((PATCH_OBB, dict(size=current['parent_obb_bytes'],
                                    sha256=current['parent_obb_sha256'])))
    manifest_path = candidate / 'LooseCpk/manifest.txt'
    files.append(('LooseCpk/manifest.txt', dict(size=manifest_path.stat().st_size,
                                              sha256=digest(manifest_path))))
    # Publish only after every copy is hash-verified. The temporary directory
    # is tool-owned; no source payloads, installed runtime, or saves are changed.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='loose-update-', dir=output.parent) as folder:
        staging = Path(folder) / 'payload'
        staging.mkdir()
        for relative, expected in files:
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate / relative, target)
            if target.stat().st_size != expected['size'] or digest(target) != expected['sha256']:
                raise ValueError(f'Source changed or copy failed: {relative}')
        if output.exists():
            raise FileExistsError('Output appeared while packaging; refusing to overwrite')
        staging.rename(output)
    return dict(build_id=current['build_id'],
                supported_baseline_build_ids=[old['build_id'] for old in previous],
                files=[dict(path=relative, size=row['size'], sha256=row['sha256'])
                       for relative, row in files])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # Report to stdout, never inside the copy-only folder.
    print(json.dumps(package_update(args.candidate, args.baseline, args.output), indent=2))


if __name__ == '__main__':
    main()

"""Replace a stored CPK member using existing padding, without moving others.

Fail closed if it does not fit. Output must be a new file. This avoids changing
the deployed OBB size or unrelated migrated player/portrait data.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import struct
from prepare_runtime import read_cpk_packet
from repack_cpk_members import patch_utf_rows


def member_name(row):
    return '/'.join(str(row.get(k) or '') for k in ('DirName','FileName')).strip('/')


def patch_slot(source: Path, output: Path, member: str, replacement: Path):
    if source.resolve()==output.resolve() or output.exists():
        raise ValueError('output must be a new path, distinct from source')
    with source.open('rb') as f:
        header=read_cpk_packet(f,0,b'CPK ')[0]
        toc=header['TocOffset']
        rows=read_cpk_packet(f,toc,b'TOC ')
        base=min(toc,header['ContentOffset'])
        targets=[(i,r) for i,r in enumerate(rows) if member_name(r)==member]
        if len(targets)!=1:
            raise ValueError(f'expected one target: {member}')
        index,row=targets[0]
        if row['FileSize']!=row['ExtractSize']:
            raise ValueError('compressed CPK entries unsupported')
        start=base+row['FileOffset']
        next_offsets=[base+r['FileOffset'] for r in rows if r['FileOffset']>row['FileOffset']]
        # Only use the next member boundary, not arbitrary trailing metadata.
        limit=min(next_offsets) if next_offsets else start+row['FileSize']
        payload=replacement.read_bytes()
        if len(payload)>limit-start:
            raise ValueError(f'replacement needs {len(payload)}; slot capacity {limit-start}')
        if len(payload)>row['FileSize']:
            f.seek(start+row['FileSize'])
            if any(f.read(len(payload)-row['FileSize'])):
                raise ValueError('nonzero bytes in proposed padding extension')
        f.seek(toc+8)
        size=struct.unpack('<Q',f.read(8))[0]
        packet=f.read(size)
        updates=[{} for _ in rows]
        updates[index]={'FileSize':len(payload),'ExtractSize':len(payload)}
        modified=patch_utf_rows(packet,updates)
        if len(modified)!=len(packet):
            raise ValueError('TOC size changed')
    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,output)
    with output.open('r+b') as f:
        f.seek(start)
        f.write(payload)
        if len(payload)<row['FileSize']:
            f.write(b'\0'*(row['FileSize']-len(payload)))
        f.seek(toc+16)
        f.write(modified)
    assert output.stat().st_size==source.stat().st_size
    # Validate every unrelated row AND member, not only the replacement.
    with source.open('rb') as old, output.open('rb') as new:
        rebuilt=read_cpk_packet(new,toc,b'TOC ')
        for i,(before,after) in enumerate(zip(rows,rebuilt)):
            if i==index:
                assert after['FileOffset']==before['FileOffset']
                new.seek(start)
                assert new.read(len(payload))==payload
            else:
                assert before==after
                old.seek(base+before['FileOffset'])
                new.seek(base+after['FileOffset'])
                remaining=before['FileSize']
                while remaining:
                    count=min(remaining,4*1024*1024)
                    assert old.read(count)==new.read(count)
                    remaining-=count
    return {'member':member,'before':row['FileSize'],'after':len(payload),
            'container_size_unchanged':True,'unrelated_members_byte_identical':len(rows)-1,
            'replacement_sha256':hashlib.sha256(payload).hexdigest()}


def patch_slots(source: Path, output: Path, replacements: dict[str, Path]):
    """Patch several stored members after copying the outer CPK only once."""
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError('output must be a new path, distinct from source')
    if not replacements:
        raise ValueError('at least one replacement is required')
    normalized = {
        name.replace('\\', '/').strip('/'): Path(path)
        for name, path in replacements.items()
    }
    with source.open('rb') as original:
        header = read_cpk_packet(original, 0, b'CPK ')[0]
        toc = int(header['TocOffset'])
        rows = read_cpk_packet(original, toc, b'TOC ')
        base = min(toc, int(header['ContentOffset']))
        by_name = {member_name(row): (index, row) for index, row in enumerate(rows)}
        missing = sorted(set(normalized) - set(by_name))
        if missing:
            raise ValueError(f'missing replacement targets: {missing}')
        updates = [{} for _ in rows]
        targets = []
        for name, replacement in normalized.items():
            if not replacement.is_file():
                raise FileNotFoundError(replacement)
            index, row = by_name[name]
            if row['FileSize'] != row['ExtractSize']:
                raise ValueError(f'compressed CPK entry unsupported: {name}')
            start = base + int(row['FileOffset'])
            next_offsets = [
                base + int(other['FileOffset'])
                for other in rows
                if int(other['FileOffset']) > int(row['FileOffset'])
            ]
            limit = min(next_offsets) if next_offsets else start + int(row['FileSize'])
            size = replacement.stat().st_size
            if size > limit - start:
                raise ValueError(
                    f'replacement needs {size}; slot capacity {limit - start}: {name}'
                )
            if size > int(row['FileSize']):
                original.seek(start + int(row['FileSize']))
                if any(original.read(size - int(row['FileSize']))):
                    raise ValueError(f'nonzero bytes in proposed padding extension: {name}')
            updates[index] = {'FileSize': size, 'ExtractSize': size}
            targets.append((name, replacement, start, int(row['FileSize']), size))
        original.seek(toc + 8)
        packet_size = struct.unpack('<Q', original.read(8))[0]
        packet = original.read(packet_size)
        modified = patch_utf_rows(packet, updates)
        if len(modified) != len(packet):
            raise ValueError('TOC size changed')

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output)
    with output.open('r+b') as destination:
        for _name, replacement, start, old_size, size in targets:
            destination.seek(start)
            with replacement.open('rb') as payload:
                shutil.copyfileobj(payload, destination, 1024 * 1024)
            if size < old_size:
                destination.write(b'\0' * (old_size - size))
        destination.seek(toc + 16)
        destination.write(modified)
    if output.stat().st_size != source.stat().st_size:
        raise RuntimeError('outer CPK size changed')

    result = []
    with output.open('rb') as rebuilt:
        rebuilt_rows = read_cpk_packet(rebuilt, toc, b'TOC ')
        rebuilt_by_name = {member_name(row): row for row in rebuilt_rows}
        for name, replacement, _start, _old_size, size in targets:
            row = rebuilt_by_name[name]
            rebuilt.seek(base + int(row['FileOffset']))
            observed = hashlib.sha256()
            remaining = size
            while remaining:
                chunk = rebuilt.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise RuntimeError(f'truncated patched member: {name}')
                observed.update(chunk)
                remaining -= len(chunk)
            expected = hashlib.sha256()
            with replacement.open('rb') as payload:
                for chunk in iter(lambda: payload.read(1024 * 1024), b''):
                    expected.update(chunk)
            if observed.digest() != expected.digest():
                raise RuntimeError(f'replacement verification failed: {name}')
            result.append({'member': name, 'size': size, 'sha256': observed.hexdigest()})
    return result


if __name__=='__main__':
    import json
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('member')
    p.add_argument('replacement',type=Path)
    a=p.parse_args()
    print(json.dumps(patch_slot(a.source,a.output,a.member,a.replacement),indent=2))

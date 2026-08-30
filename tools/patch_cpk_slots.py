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


if __name__=='__main__':
    import json
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('member')
    p.add_argument('replacement',type=Path)
    a=p.parse_args()
    print(json.dumps(patch_slot(a.source,a.output,a.member,a.replacement),indent=2))

"""Extract one owned nested stadium CPK without copying the outer archive.

Only its shell, audience layout and source textures are written. All payloads
must remain in an ignored local workspace. Compressed CPK entries are rejected.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
from prepare_loose_cpk import cpk_layout, member_name
from prepare_runtime import read_cpk_packet


class Window:
    def __init__(self, stream, start, size):
        self.stream, self.start, self.size, self.position = stream, start, size, 0

    def seek(self, offset, whence=0):
        position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        if not 0 <= position <= self.size:
            raise ValueError('Nested CPK seek outside member')
        self.position = position
        return position

    def read(self, count=-1):
        if count < 0:
            count = self.size - self.position
        if count > self.size - self.position:
            raise ValueError('Nested CPK read outside member')
        self.stream.seek(self.start + self.position)
        result = self.stream.read(count)
        if len(result) != count:
            raise ValueError('Truncated nested CPK')
        self.position += count
        return result


def extract(archive, stadium_id, output):
    if not re.fullmatch(r'st[0-9]{3}', stadium_id):
        raise ValueError('Invalid stadium ID')
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Use a fresh extraction directory')
    _, rows, base = cpk_layout(Path(archive))
    matches = [r for r in rows if member_name(r).lower() == 'asset/model/bg/' + stadium_id + '.cpk']
    if len(matches) != 1:
        raise ValueError('Expected one nested stadium archive')
    row = matches[0]
    if row['FileSize'] != row['ExtractSize']:
        raise ValueError('Compressed outer CPK member unsupported')
    extracted = []
    with Path(archive).open('rb') as source:
        nested = Window(source, base + row['FileOffset'], row['FileSize'])
        header = read_cpk_packet(nested, 0, b'CPK ')[0]
        toc = header['TocOffset']
        inner_base = min(toc, header['ContentOffset'])
        for item in read_cpk_packet(nested, toc, b'TOC '):
            name = member_name(item).replace('\\', '/')
            prefix = 'Asset/model/bg/' + stadium_id + '/'
            if not name.lower().startswith(prefix.lower()):
                continue
            relative = name[len(prefix):].lower()
            wanted = relative in ('#win/' + stadium_id + '.fpk', 'audi/#win/audiarea_' + stadium_id + '.fpk')
            wanted |= relative.startswith('sourceimages/') and relative.endswith('.ftex')
            if not wanted:
                continue
            if item['FileSize'] != item['ExtractSize']:
                raise ValueError('Compressed inner CPK member unsupported: ' + name)
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or ':' in name:
                raise ValueError('Unsafe member path')
            target = output.joinpath(*path.parts)
            nested.seek(inner_base + item['FileOffset'])
            data = nested.read(item['FileSize'])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            extracted.append(dict(name=name, bytes=len(data)))
    required = [output / ('Asset/model/bg/' + stadium_id + '/' + tail) for tail in
                ('#Win/' + stadium_id + '.fpk', 'audi/#Win/audiarea_' + stadium_id + '.fpk')]
    if not all(p.is_file() for p in required):
        raise ValueError('Incomplete shell/audience extraction')
    (output / 'extraction.local.json').write_text(json.dumps(dict(archive=str(archive), stadium_id=stadium_id, members=extracted), indent=2))
    return extracted


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', required=True, type=Path)
    p.add_argument('--stadium-id', required=True)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    rows = extract(a.archive, a.stadium_id, a.output)
    print('Extracted', len(rows), 'members,', sum(r['bytes'] for r in rows), 'bytes')

"""Extract only verified face inputs from a locked, local team inventory.

Never unpack entire archives. FPK/FTEX parsers and game data are local inputs.
An existing output must match its recorded hash; changed data is not overwritten.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import sys

from PIL import Image


def safe_member(root, name):
    parts = PurePosixPath(name.replace('\\', '/'))
    if parts.is_absolute() or '..' in parts.parts or ':' in name:
        raise ValueError('Unsafe archive member: '+name)
    path = root.joinpath(*parts.parts).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Archive member escapes output')
    return path


def write_once(path, data):
    if path.exists() and path.read_bytes() != data:
        raise ValueError('Existing extracted input changed: '+str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def extract(inventory, work, parser_root, *, all_textures=False):
    work = work.resolve()
    sys.path.insert(0, str(parser_root))
    from pes_file_tools import fpk, ftex
    archives = {a['path']: a for a in inventory['archives']}
    # Revalidate archive identity before trusting recorded offsets.
    for name, a in archives.items():
        s = Path(name).stat()
        if s.st_size != a['size'] or s.st_mtime_ns != a['mtime_ns']:
            raise ValueError('Source archive changed since inventory: '+name)
    rows = []
    for player in inventory['players']:
        if player['status'] != 'source_ready':
            continue
        folder = work/str(player['base_id'])/'source'
        files = []
        for name, member in player['source_members'].items():
            if not (name.endswith(('/face.fpk', '/face_bsm_alp.ftex',
                    '/hair_parts_bsm_alp.ftex', '/eye_sclera_bsm.ftex')) or
                    (all_textures and name.endswith('.ftex'))):
                continue
            if member['extracted_size'] != member['size']:
                raise ValueError('Compressed CPK member needs an explicit decoder: '+name)
            with Path(member['archive']).open('rb') as stream:
                stream.seek(member['offset'])
                data = stream.read(member['size'])
            if len(data) != member['size']:
                raise ValueError('Truncated CPK member: '+name)
            path = safe_member(folder, name)
            files.append(dict(member=name, bytes=len(data), sha256=write_once(path,data)))
            if path.suffix == '.fpk':
                package = fpk.FpkFile(); package.read(data)
                for nested, value in package.entries.items():
                    if nested.endswith(('.fmdl', 'face_diff.bin')):
                        target = safe_member(folder, nested.lstrip('/'))
                        payload = bytes(value)
                        files.append(dict(member=nested, bytes=len(payload), sha256=write_once(target,payload)))
            else:
                image = Image.open(io.BytesIO(ftex.ftexToDdsBuffer(data)))
                output = io.BytesIO(); image.save(output, format='PNG')
                files.append(dict(member=str(path.with_suffix('.png').relative_to(folder)),
                                  sha256=write_once(path.with_suffix('.png'),output.getvalue())))
        row = dict(base_id=player['base_id'], native_player_id=player['native_player_id'],
                   fingerprint=player['fingerprint'], files=files)
        report = work/str(player['base_id'])/'extraction.json'
        write_once(report,(json.dumps(row,indent=2)+'\n').encode())
        rows.append(row)
    return rows


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--parser-root', type=Path, required=True)
    args = p.parse_args()
    rows = extract(json.loads(args.inventory.read_text(encoding='utf-8')),args.work,args.parser_root)
    print(json.dumps({'extracted_players':len(rows), 'files':sum(len(r['files']) for r in rows)}))

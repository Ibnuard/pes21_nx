"""Local Football Life stadium discovery; no game payloads are bundled."""
import re
import hashlib


def asset_key(value):
    if not re.match(r'[A-Z][A-Za-z0-9]{0,47}\Z', value):
        raise ValueError('Invalid stadium asset key')
    return value


def material_key(value):
    """UE package names cannot contain spaces, punctuation or long Blender IDs."""
    clean=re.sub('[^A-Za-z0-9_]', '_', value)
    if clean!=value or len(clean)>60:
        clean=clean[:49]+'_'+hashlib.sha256(value.encode('utf-8')).hexdigest()[:10]
    return clean


def discover(root):
    """Only advertise standalone shell archives actually present on disk."""
    from pathlib import Path
    rows = []
    for folder in sorted(Path(root).iterdir()):
        if not folder.is_dir() or folder.name == 'common':
            continue
        bg = folder / 'Asset/model/bg'
        candidates = sorted(p for p in bg.glob('st*/#Win/st*.fpk')
                            if p.stem == p.parent.parent.name)
        if len(candidates) != 1:
            rows.append(dict(name=folder.name, source=str(folder), status='missing_or_ambiguous_shell'))
            continue
        shell = candidates[0]
        native = shell.stem
        area = shell.parent.parent / ('audi/#Win/audiarea_' + native + '.fpk')
        rows.append(dict(name=folder.name, key=asset_key(re.sub('[^A-Za-z0-9]', '', folder.name)),
                         source=str(folder), source_id=native, shell=str(shell),
                         audience=str(area), status='available' if area.is_file() else 'missing_audience'))
    return rows

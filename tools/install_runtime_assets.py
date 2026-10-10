"""Install a verified FootballNX.assets and retire identical loose assets.

Run with the game closed. A ZIP backup outside the runtime is verified before
any loose file is removed. Different/custom loose files stop the migration;
repack those inputs first instead of silently discarding overrides.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid
import zipfile

from pack_runtime_assets import FOLDERS, normalize, verify


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(root: Path, entries: dict) -> dict[str, str]:
    files = {}
    for folder in FOLDERS:
        directory = root / folder
        if not directory.exists():
            continue
        if directory.is_symlink() or not directory.is_dir() or directory.resolve().parent != root:
            raise ValueError(f'expected a local asset directory: {directory}')
        for path in directory.iterdir():
            if path.is_symlink() or not path.is_file() or path.resolve().parent != directory:
                raise ValueError(f'unsupported loose asset; left untouched: {path}')
            relative = folder + '/' + path.name
            entry = entries.get(normalize(relative))
            actual = digest(path)
            if entry is None or entry['sha256'] != actual:
                raise ValueError(f'loose asset differs or is absent from archive: {relative}; repack it first')
            files[relative] = actual
    return files


def install(root: Path, archive: Path, backup_dir: Path, check_only=False) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('runtime must be a directory')
    archive = archive.resolve(strict=True)
    backup_dir = backup_dir.resolve()
    if backup_dir == root or root in backup_dir.parents:
        raise ValueError('backup directory must be outside the runtime')
    report = verify(archive)
    files = inventory(root, report['entries'])
    target = root / 'FootballNX.assets'
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ValueError('archive target must be a regular local file')
    result = {'archive_sha256': report['sha256'], 'entries': len(report['entries']),
              'retired_files': len(files), 'check_only': check_only}
    if check_only:
        return result
    # Verify the staged copy, preserving an existing archive until it passes.
    staged = None
    try:
        with tempfile.NamedTemporaryFile(dir=root, prefix='FootballNX.', suffix='.tmp', delete=False) as stream:
            staged = Path(stream.name)
            with archive.open('rb') as source:
                while chunk := source.read(1024 * 1024):
                    stream.write(chunk)
        if verify(staged)['sha256'] != report['sha256']:
            raise ValueError('archive changed during staging')
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = backup_dir / ('FootballNX-loose-' + stamp + '-' + uuid.uuid4().hex[:8] + '.zip')
        saved = dict(files)
        if target.exists():
            saved['FootballNX.assets'] = digest(target)
        with zipfile.ZipFile(backup, 'x', zipfile.ZIP_DEFLATED) as out:
            for name in saved:
                out.write(root / name, name)
            out.writestr('MIGRATION.json', json.dumps({'files': saved, **result}, indent=2))
        with zipfile.ZipFile(backup) as out:
            if out.testzip() is not None:
                raise ValueError('backup ZIP failed verification')
            for name, expected in saved.items():
                if hashlib.sha256(out.read(name)).hexdigest() != expected:
                    raise ValueError('backup differs from original: ' + name)
        if inventory(root, report['entries']) != files:
            raise ValueError('loose assets changed during migration; originals retained')
        os.replace(staged, target)
        staged = None
        for name, expected in files.items():
            path = root / name
            if digest(path) != expected:
                raise ValueError('loose asset changed; migration stopped: ' + name)
            path.unlink()  # Exact verified file only; recoverable from backup.
        for folder in FOLDERS:
            path = root / folder
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()  # Empty directory only, never recursive.
        result['backup'] = str(backup)
        return result
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--backup-dir', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(json.dumps(install(args.root, args.archive, args.backup_dir, args.check), indent=2))


if __name__ == '__main__':
    main()

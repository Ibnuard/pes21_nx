"""Compose a partial CPK update without reverting unrelated manifest rows.

The caller supplies the current manifest explicitly. Overlay verification reads
the first existing file in copy precedence order, including unchanged files;
it never clones an OBB, installs files or accepts a later matching fallback
after finding a corrupt higher-priority file.
"""
from pathlib import Path

from prepare_loose_cpk import (FULL_NAMES, PATCH_OBB, checked_cpk,
                               checked_dummy_obb, digest, read_manifest)


def compose_manifest(baseline_root, replacements):
    manifest = read_manifest(Path(baseline_root))
    if manifest['version'] != 2:
        raise ValueError('Composition requires a full V2 baseline manifest')
    if not replacements or set(replacements) - set(FULL_NAMES):
        raise ValueError('Specify only approved loose CPK replacement names')
    for row in manifest['files']:
        if row['name'] in replacements:
            path = Path(replacements[row['name']])
            if path.is_symlink() or not path.is_file():
                raise ValueError('Missing or symlinked replacement: ' + row['name'])
            checked_cpk(path)
            row.update(size=path.stat().st_size, sha256=digest(path))
    return manifest


def verify_overlay(manifest, roots):
    """Verify an installed merge without copying unchanged proprietary inputs."""
    if (manifest['version'] != 2 or
            tuple(row['name'] for row in manifest['files']) != FULL_NAMES):
        raise ValueError('Expected the complete ordered V2 manifest')
    roots = [Path(root).resolve() for root in roots]
    if not roots or len(set(roots)) != len(roots):
        raise ValueError('Specify distinct roots in copy precedence order')

    def resolve(relative):
        for root in roots:
            path = root / relative
            if path.exists() or path.is_symlink():
                if path.is_symlink() or not path.is_file():
                    raise ValueError('Invalid overlay file: ' + relative)
                return path
        raise ValueError('Missing overlay file: ' + relative)

    dummy = resolve(PATCH_OBB)
    if (dummy.stat().st_size != manifest['parent_obb_bytes'] or
            digest(dummy) != manifest['parent_obb_sha256']):
        raise ValueError('Overlay dummy OBB differs')
    checked_dummy_obb(dummy)
    files = []
    for row in manifest['files']:
        relative = 'LooseCpk/' + row['name']
        path = resolve(relative)
        if path.stat().st_size != row['size'] or digest(path) != row['sha256']:
            raise ValueError('Overlay CPK differs: ' + row['name'])
        checked_cpk(path)
        files.append(dict(row, source=str(path)))
    return dict(build_id=manifest['build_id'], files=files,
                parent_obb_source=str(dummy), all_cpk_hashes_verified=True)

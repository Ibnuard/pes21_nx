"""Reuse only exact current mesh/texture/renderer preview evidence on D."""
from pathlib import Path
import shutil

from realface_batch_inventory import read
from realface_pipeline import sha


def index_views(root, rows, renderer):
    owners = {r['base_id']: r for r in rows}
    found = {}
    for proof in Path(root).glob('*/*/*-*.json'):
        try:
            base = int(proof.stem.split('-')[0])
        except ValueError:
            continue
        if base not in owners:
            continue
        metadata = read(proof); row = owners[base]; image = proof.with_suffix('.png')
        view = metadata.get('view')
        if (view not in ('front', 'left', 'right', 'above') or
                metadata.get('prepared_key') != row['cache_key'] or
                metadata.get('cooked_key') != row['cooked_cache_key'] or
                metadata.get('renderer_sha256') != renderer or not image.is_file() or
                sha(image) != metadata.get('image_sha256')):
            continue
        found[(base, view)] = image
    return found


def seed_views(output, rows, views, cache):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    for row in rows:
        for view in views:
            source = cache.get((row['base_id'], view))
            if source is None:
                continue
            target = output/source.name
            if source.resolve() == target.resolve():
                continue
            # Revalidate between indexing and copying; a stale image must not
            # get a current sidecar simply because its filename matches.
            proof = read(source.with_suffix('.json'))
            if sha(source) != proof['image_sha256']:
                raise ValueError('Preview cache changed during reuse')
            shutil.copy2(source, target)
            shutil.copy2(source.with_suffix('.json'), target.with_suffix('.json'))

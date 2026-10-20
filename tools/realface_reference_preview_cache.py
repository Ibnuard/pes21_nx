"""Reuse exact source/prepared reference images across regrouped review batches.

These receipts never count as cooked evidence or visual acceptance. Source and
prepared stages have separate identity/config/recipe checks, even when their
numeric IDs or image filenames happen to match.
"""
from pathlib import Path
import shutil

from realface_batch import key_of
from realface_batch_inventory import read, write
from realface_pipeline import sha

POLICY = 'source_prepared_reference_cache_v1'


def owners(stage, rows, catalogue):
    if stage not in ('source', 'prepared'):
        raise ValueError('Reference cache only supports source/prepared stages')
    return {r['base_id']: dict(native_player_id=r['native_player_id'],
        fingerprint=r['fingerprint'], prepared_key=key_of(catalogue[r['base_id']]['input_hashes'])
        if stage == 'source' else r['cache_key']) for r in rows}


def header(config, stage, renderer, preview_tool):
    return dict(policy=POLICY, stage=stage, config_key=key_of(config),
                renderer_sha256=renderer, preview_tool_sha256=preview_tool)


def proof(path, owner, renderer):
    metadata = read(path.with_suffix('.json'))
    expected = dict(prepared_key=owner['prepared_key'], cooked_key=None,
                    renderer_sha256=renderer, view='front', image_sha256=sha(path))
    if metadata != expected:
        raise ValueError('Reference image differs from its stage/recipe')
    return dict(image_sha256=expected['image_sha256'], metadata_sha256=sha(path.with_suffix('.json')))


def index_references(root, expected_header, expected_owners):
    found = {}
    for stamp in Path(root).glob('*/*/REFERENCE-COMPLETE.json'):
        try:
            saved = read(stamp)
            if any(saved.get(k) != v for k, v in expected_header.items()):
                continue
            for key, evidence in saved['images'].items():
                base = int(key)
                if base not in expected_owners or saved['owners'][key] != expected_owners[base]:
                    continue
                path = stamp.parent/(str(base)+'-front.png')
                actual = proof(path, expected_owners[base], expected_header['renderer_sha256'])
                if actual == evidence:
                    found[(base, 'front')] = (path, actual)
        except (ValueError, KeyError, OSError, TypeError):
            continue
    return found


def seed_references(output, selected_owners, cached):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for base in selected_owners:
        item = cached.get((base, 'front'))
        if item is None:
            continue
        source, evidence = item
        if (sha(source) != evidence['image_sha256'] or
                sha(source.with_suffix('.json')) != evidence['metadata_sha256']):
            raise ValueError('Reference cache changed during reuse')
        target = output/source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
            shutil.copy2(source.with_suffix('.json'), target.with_suffix('.json'))


def seal_references(output, expected_header, expected_owners):
    output = Path(output)
    provenance = read(output/'PROVENANCE.json')
    if (provenance.get('stage') != expected_header['stage'] or
            {p['base_id'] for p in provenance['players']} != expected_owners.keys()):
        raise ValueError('Reference batch stage/owners differ')
    images = {str(base): proof(output/(str(base)+'-front.png'), owner,
                              expected_header['renderer_sha256'])
              for base, owner in expected_owners.items()}
    write(output/'REFERENCE-COMPLETE.json', dict(expected_header,
        owners={str(base): owner for base, owner in expected_owners.items()}, images=images,
        valid_for_cooked_acceptance=False, inspected_automatically=False))

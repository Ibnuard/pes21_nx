"""Read-only provenance gate before projecting raw UV0 colors onto a reduced head.

An existing per-owner UV repair may intentionally differ from the dense catalog
entry. Matching the raw atlas alone then says nothing about the prepared UVs.
This check rejects automatic reuse in that case; it does not approve appearance,
reconstruct a PC shader, or replace geometry/cache/identity validation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from realface_batch_inventory import read, write
from realface_pipeline import sha

IDENTITY = ('base_id', 'native_player_id', 'fingerprint')


def correspondence(prepared, source, job, dense):
    """Bind the prepared source FBX/atlas to the intended dense UV0 recipe."""
    original = job['source_profile']
    for owner in (source, job, original, dense):
        if any(prepared[key] != owner[key] for key in IDENTITY):
            raise ValueError('Hair atlas owner identity differs')
    if not prepared['fingerprint']:
        raise ValueError('Hair atlas owner fingerprint is missing')
    files = {
        'parent_source_hair_fbx': Path(original['hair_fbx']),
        'dense_hair_fbx': Path(dense['hair_fbx']),
        'parent_source_hair_texture': Path(original['hair_texture']),
        'dense_hair_texture': Path(dense['hair_texture']),
    }
    if any(not path.is_file() for path in files.values()):
        raise FileNotFoundError('Optional local hair source/atlas fixture is unavailable')
    memo = {}
    hashes = {}
    for role, path in files.items():
        canonical = path.resolve()
        if canonical not in memo:
            memo[canonical] = sha(canonical)
        hashes[role] = memo[canonical]
    same_fbx = hashes['parent_source_hair_fbx'] == hashes['dense_hair_fbx']
    same_atlas = hashes['parent_source_hair_texture'] == hashes['dense_hair_texture']
    same_domain = job['budgets'].get('hair_mode') == 'cards'
    return dict(
        **{key: prepared[key] for key in IDENTITY},
        prepared_key=prepared['cache_key'],
        source_files={role: str(path.resolve()) for role, path in files.items()},
        source_hashes=hashes,
        source_fbx_byte_identical=same_fbx,
        source_atlas_byte_identical=same_atlas,
        source_hair_mode=job['budgets'].get('hair_mode'),
        recipe_correspondence=('same_source_fbx_atlas_cards' if same_fbx and same_atlas and same_domain
                               else 'requires_own_repair_uv_proof_do_not_promote_rgb'),
        geometry_validated=False,
        visual_accepted=False,
        promoted=False,
    )


def audit(config, selected=None):
    work = Path(config['work_dir'])
    sources = {row['base_id']: row for row in read(config['source_profiles'])}
    prepared = {row['base_id']: row for row in read(work/'verify-report.json')}
    selected = set(selected if selected is not None else
                   read(work/'VISUAL-REVIEW-PROGRESS.json')['pending_detail_base_ids'])
    if not selected <= sources.keys() or not selected <= prepared.keys():
        raise ValueError('Hair correspondence selection has no verified source owner')
    rows = []
    for base in sorted(selected):
        row = prepared[base]
        folder = Path(row['folder'])
        job_path = folder/'job.json'
        profile_path = Path(sources[base]['profile'])
        result = correspondence(row, sources[base], read(job_path), read(profile_path))
        result['provenance_files'] = {str(path.resolve()): sha(path)
                                      for path in (job_path, profile_path)}
        rows.append(result)
    return dict(
        prepare_sha256=sha(work/'prepare-report.json'),
        verify_sha256=sha(work/'verify-report.json'),
        audit_code_sha256=sha(__file__),
        rows=rows,
        counts=dict(Counter(row['recipe_correspondence'] for row in rows)),
        source_changed=False,
        geometry_validated=False,
        visual_accepted=False,
        promoted=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--base-id', type=int, action='append')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    local = Path(__file__).resolve().parents[1]/'local-debug'
    if output.drive.lower() != 'd:' or not output.is_relative_to(local):
        raise ValueError('Write this local audit under the workspace local-debug on D:')
    report = audit(read(args.config), args.base_id)
    write(output, report)
    print(report['counts'])


if __name__ == '__main__':
    main()

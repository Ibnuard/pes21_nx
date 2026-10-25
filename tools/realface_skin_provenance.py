"""Bind a neck-palette audit to the independently validated, released textures.

Read-only and checkpointed per identity. This does not select runtime materials
or authorize RGB-only patches. Reviewed policies remain a separate input.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path

from PIL import Image, ImageStat

from audit_realface_runtime_assets import FACE, dependency_names
from audit_skin_palette import lab, sample
from cooked_texture import Texture
from realface_skin_batch import (ROIS, canonical_owners, checked_profile,
                                 classify, read, sha, unique, write)


IDENTITY = ('base_id', 'native_player_id', 'fingerprint')


def matching_identity(*rows):
    if any(tuple(row.get(k) for k in IDENTITY) != tuple(rows[0].get(k) for k in IDENTITY)
           for row in rows[1:]):
        raise ValueError('Canonical, audited, prepared and released identities disagree')


def neck_colors(image):
    image = image.convert('RGBA')
    result = []
    for roi in ROIS:
        box = tuple(round(v * image.size[i % 2]) for i, v in enumerate(roi))
        crop = image.crop(box)
        if crop.getchannel('A').getextrema()[0] < 250:
            raise ValueError('Neck sample is not opaque')
        result.append(ImageStat.Stat(crop.convert('RGB')).median)
    return result


def compare_necks(source, cooked, palette, current, limit=4):
    source_colors, cooked_colors = neck_colors(source), neck_colors(cooked)
    errors = [math.dist(lab(a), lab(b)) for a, b in zip(source_colors, cooked_colors)]
    before = classify(source_colors, palette, current)
    after = classify(cooked_colors, palette, current)
    stable = (max(errors) <= limit and before['nearest_skin'] == after['nearest_skin'])
    return dict(source_rgb=source_colors, cooked_rgb=cooked_colors,
                max_delta_e76=max(errors), error_limit=limit,
                source_classification=before, cooked_classification=after,
                palette_recommendation_stable=stable)


def checked_file(path, expected):
    actual = sha(path)
    if actual != expected:
        raise ValueError('Bound provenance file changed: ' + str(path))
    return actual


def player_proof(audited, row, owner, released, stage, release_hashes, palette):
    matching_identity(audited, row, owner, released)
    profile_path, profile = checked_profile(row, owner)
    checked_file(profile_path, audited['profile_sha256'])
    texture_path = Path(profile['face_texture'])
    checked_file(texture_path, audited['texture_sha256'])
    prepared = read(Path(row['folder']) / 'complete.json')
    if prepared['cache_key'] != row['cache_key']:
        raise ValueError('Prepared cache identity changed')
    for path in (profile_path, texture_path):
        relative = path.resolve().relative_to(Path(row['folder']).resolve()).as_posix()
        checked_file(path, prepared['outputs'][relative])
    import_profile = read(row['ue_profile'])
    if {k: v for k, v in import_profile.items() if k != 'report'} != profile:
        raise ValueError('Cook import profile differs from reviewed prepared profile')
    imported = read(import_profile['report'])
    native = row['native_player_id']
    if (imported['status'] != 'imported' or imported['player'] != native or
            set(imported['parts']['face'].values()) != {
                f'/Game/Assets/character/RealFace/face_{native}.face_{native}'}):
        raise ValueError('Face import report has another material owner')
    cooked = Path(row['cooked_folder'])
    complete = read(cooked / 'complete.json')
    if complete['cache_key'] != row['cooked_cache_key']:
        raise ValueError('Cooked cache key changed')
    bindings = {}
    for suffix in ('.uasset', '.uexp', '.ubulk'):
        name = str(native) + '_face_tablet' + suffix
        source = cooked / 'assets' / name
        expected = complete['outputs']['assets/' + name]
        checked_file(source, expected)
        relative = FACE + name
        checked_file(stage / relative, release_hashes[relative])
        if expected != release_hashes[relative]:
            raise ValueError('Released texture differs from validated own cooked texture')
        bindings[relative] = expected
    missing = dependency_names(stage, native)
    if missing:
        raise ValueError('Released material import declarations differ: ' + json.dumps(missing))
    texture = Texture(stage / FACE / (str(native) + '_face_tablet.uexp'))
    with Image.open(texture_path) as source:
        comparison = compare_necks(source, texture.decode(), palette, audited.get('current_skin', 0))
    return dict(**{k: audited[k] for k in IDENTITY}, name=audited['name'],
                status='provenance_verified', original_status=audited['status'],
                source_profile_sha256=sha(profile_path), source_texture_sha256=sha(texture_path),
                cooked_stamp_sha256=sha(cooked / 'complete.json'),
                released_texture_members=bindings, material_import_declarations_verified=True,
                pixel_format=texture.format, size=[texture.width, texture.height],
                neck=comparison, runtime_material_selection_observed=False,
                device_accepted=False)


def run(config_path):
    config = read(config_path)
    audit_config = read(config['audit_config'])
    for name, h in audit_config['pinned_inputs'].items():
        checked_file(name, h)
    audit = read(Path(audit_config['work_dir']) / 'AUDIT.json')
    release = read(config['release_verification'])
    checked_file(config['release_verification'], config['release_verification_sha256'])
    checked_file(config['received_pak'], release['pak_sha256'])
    rows = unique(read(audit_config['verified_report']), 'base_id')
    owners = canonical_owners(read(audit_config['identity_state']))
    released = unique(release['players_in_package'], 'base_id')
    palette = {int(p['skin']): sample(p) for p in audit_config['palette']}
    out = Path(config['output'])
    out.mkdir(parents=True, exist_ok=True)
    (out / 'players').mkdir(exist_ok=True)
    context = hashlib.sha256(json.dumps(dict(config=config, audit=sha(Path(audit_config['work_dir']) / 'AUDIT.json'),
        tool=sha(__file__)), sort_keys=True).encode()).hexdigest()
    results = []
    for audited in audit['players']:
        base = audited['base_id']
        # Recheck all source/cooked hashes even when a prior checkpoint exists;
        # a matching cache label alone cannot prove the underlying bytes.
        result = player_proof(audited, rows[base], owners[base], released[base],
                              Path(config['release_stage']), release['asset_hashes'], palette)
        result['context'] = context
        write(out / 'players' / (str(base) + '.json'), result)
        results.append(result)
        if len(results) % 50 == 0:
            print(json.dumps(dict(checked=len(results), total=audit['player_count'])), flush=True)
    summary = dict(state='provenance_complete', context=context, players=results,
        players_checked=len(results), counts=dict(Counter(x['status'] for x in results)),
        palette_stable=sum(x['neck']['palette_recommendation_stable'] for x in results),
        audit_sha256=sha(Path(audit_config['work_dir']) / 'AUDIT.json'),
        release_verification_sha256=sha(config['release_verification']),
        received_pak_sha256=release['pak_sha256'], runtime_mutated=False, hardware_accepted=False)
    write(out / 'PROVENANCE.json', summary)
    return {k: v for k, v in summary.items() if k != 'players'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    cfg = read(args.config)
    output = Path(cfg['output']); output.mkdir(parents=True, exist_ok=True)
    lock = output / 'provenance.lock'
    with lock.open('x') as f:
        json.dump(dict(pid=os.getpid(), config=str(args.config.resolve())), f)
    try:
        print(json.dumps(run(args.config), indent=2), flush=True)
    finally:
        lock.unlink()

"""Checkpoint a serial, identity-bound face/body palette audit; never patch on RGB alone.

The batch reads validated profiles and the currently paired appearance CPK. It
does not recook faces, rewrite textures, install a runtime, or infer skin from a
name/nationality. A separate reviewed patch_player_skin policy is required.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import struct

from PIL import Image
from audit_skin_palette import lab, sample
from pes21_player_migration import member_payload


MEMBER = 'common/etc/appearance/PlayerAppearance.bin'
ROIS = ((.30, .88, .43, .96), (.435, .88, .565, .96), (.57, .88, .70, .96))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    tmp.replace(path)


def classify(colors, palette, current):
    if set(palette) != set(range(1, 7)) or len(colors) != 3:
        raise ValueError('Expected six native palettes and three neck swatches')
    distances = [{k: math.dist(lab(color), lab(p)) for k, p in palette.items()}
                 for color in colors]
    votes = [min(d, key=d.get) for d in distances]
    ranked = sorted(palette, key=lambda k: sum(d[k] for d in distances))
    best = ranked[0]
    means = {k: sum(d[k] for d in distances) / len(distances) for k in palette}
    margin = means[ranked[1]] - means[best]
    spread = max(math.dist(lab(a), lab(b)) for a in colors for b in colors)
    improvement = means.get(current, float('inf')) - means[best]
    # This is a review queue, never an automatic authorization to change skin.
    confident = (votes.count(best) == 3 and margin >= 2 and spread <= 10 and
                 means[best] <= 22 and improvement >= 4)
    status = ('already_nearest' if current == best else
              'review_candidate' if confident and current in palette else 'held_measurement')
    return dict(status=status, nearest_skin=best, current_skin=current,
                rgb=colors, votes=votes, delta_e76=means, margin=margin,
                swatch_spread=spread, improvement=(improvement if math.isfinite(improvement) else None),
                automatic_patch=False)


def unique(rows, key):
    indexed = {r[key]: r for r in rows}
    if len(indexed) != len(rows):
        raise ValueError('Duplicate identity: ' + key)
    return indexed


def checked_profile(row, owner):
    profile_path = Path(row['folder']) / 'ue-profile.json'
    profile = read(profile_path)
    if row['status'] != 'validated' or owner.get('status') != 'active' or any(
            profile[k] != row[k] or row[k] != owner[k]
            for k in ('base_id', 'native_player_id', 'fingerprint')):
        raise ValueError('Validated head and canonical identity disagree')
    return profile_path, profile


def canonical_owners(state):
    active = [p for p in state['identities'].values() if p.get('status') == 'active']
    unique(active, 'native_player_id')
    # Registered FL-only identities can have BaseId=null. They do not select
    # an eFootball asset and must never collapse into a shared numeric donor.
    return unique([p for p in active if type(p.get('base_id')) is int and p['base_id'] > 0], 'base_id')


def audit(config_path):
    config = read(config_path)
    work = Path(config['work_dir'])
    work.mkdir(parents=True, exist_ok=True)
    cache = work / 'players'
    cache.mkdir(exist_ok=True)
    inputs = config['pinned_inputs']
    for path, expected in inputs.items():
        if sha(path) != expected:
            raise ValueError('Pinned audit input changed: ' + path)
    verified = unique(read(config['verified_report']), 'base_id')
    unique(list(verified.values()), 'native_player_id')
    old = unique(read(config['preserved_report']), 'base_id')
    owners = canonical_owners(read(config['identity_state']))
    raw = member_payload(Path(config['runtime_cpk']), MEMBER)
    if not raw or len(raw) % 60:
        raise ValueError('Incomplete appearance table')
    appearance = unique([dict(native_player_id=struct.unpack_from('<I', raw, i)[0],
                              data=raw[i:i+60]) for i in range(0, len(raw), 60)], 'native_player_id')
    palette = {int(p['skin']): sample(p) for p in config['palette']}
    protected = set(config['protected_base_ids'])
    context = hashlib.sha256(json.dumps(dict(inputs=inputs, palette=palette, rois=ROIS,
        protected=sorted(protected), tool=sha(__file__)), sort_keys=True).encode()).hexdigest()
    results = []
    for base, row in sorted(verified.items()):
        if base in old:
            continue  # Earlier accepted heads/appearance decisions are outside this correction.
        entry = dict(base_id=base, native_player_id=row['native_player_id'], fingerprint=row['fingerprint'],
                     name=row['name'], context=context)
        if base not in owners:
            raise ValueError('Validated head has no canonical owner')
        profile_path, profile = checked_profile(row, owners[base])
        texture = Path(profile['face_texture'])
        entry.update(profile_sha256=sha(profile_path), texture_sha256=sha(texture), texture=str(texture))
        key = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
        checkpoint = cache / (str(base) + '.json')
        if checkpoint.exists() and read(checkpoint).get('cache_key') == key:
            result = read(checkpoint)
        else:
            app = appearance.get(row['native_player_id'])
            if app is None:
                result = dict(entry, status='held_missing_appearance', automatic_patch=False)
            else:
                skin = app['data'][37] & 7
                with Image.open(texture) as image:
                    rgba = image.convert('RGBA')
                    for roi in ROIS:
                        box = tuple(round(x * rgba.size[i % 2]) for i, x in enumerate(roi))
                        if rgba.crop(box).getchannel('A').getextrema()[0] < 250:
                            raise ValueError('Neck ROI has nonopaque pixels: ' + str(base))
                colors = [sample(dict(texture=str(texture), roi=roi)) for roi in ROIS]
                result = dict(entry, **classify(colors, palette, skin),
                              appearance_row_sha256=hashlib.sha256(app['data']).hexdigest())
                if base in protected:
                    result['status'] = 'preserved_explicit_policy'
            result['cache_key'] = key
            write(checkpoint, result)
        results.append(result)
        if len(results) % 50 == 0:
            print(json.dumps(dict(audited=len(results), counts=dict(Counter(x['status'] for x in results)))), flush=True)
    report = dict(state='audit_complete', context=context, player_count=len(results),
                  counts=dict(Counter(x['status'] for x in results)), players=results,
                  rois=ROIS, pinned_inputs=inputs, measurement_only=True,
                  reviewed_policy_required=True, runtime_mutated=False, device_validated=False)
    write(work / 'AUDIT.json', report)
    write(work / 'RUN-STATUS.json', {k: v for k, v in report.items() if k != 'players'})
    return {k: v for k, v in report.items() if k not in ('players', 'pinned_inputs')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('audit', 'status'))
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    config = read(args.config)
    if args.command == 'status':
        print(json.dumps(read(Path(config['work_dir'])/'RUN-STATUS.json'), indent=2))
        return
    work = Path(config['work_dir']); work.mkdir(parents=True, exist_ok=True)
    lock = work / 'audit.lock'
    # A prior lock is never assumed stale from a historical PID.
    with lock.open('x', encoding='utf-8') as stream:
        json.dump(dict(pid=os.getpid(), config=str(args.config.resolve())), stream)
    try:
        print(json.dumps(audit(args.config), indent=2))
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()

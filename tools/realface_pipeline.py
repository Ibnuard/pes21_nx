"""Run identity-checked native-reference fits from a prepared local manifest.

Version 1 covers fitting, FBX round-trip, synthetic poses and resumable batch
reports. Source extraction, UE cooking and device acceptance remain explicit
steps. Missing FL26 sources are recorded as skips, without substituting faces.
Use: python tools/realface_pipeline.py plan|run --manifest local.json [--player ID] [--resume]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
INPUTS = ('face_fbx', 'native_rig', 'cooked_rig', 'native_face', 'native_body')
CODE = ('realface_pipeline.py', 'blender_fit_realface.py', 'realface_reference.py',
        'blender_export_ue_fbx.py', 'validate_realface_fit.py')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identify(profile, registry):
    owners = [r for r in registry['players'] if r['ef_base_id'] == profile['base_id'] and r.get('status') == 'active']
    if len(owners) != 1:
        raise ValueError('Expected one active BaseId owner')
    owner = owners[0]
    if not profile.get('fingerprint') or owner['fingerprint'] != profile['fingerprint']:
        raise ValueError('Identity fingerprint mismatch')
    if owner['native_player_id'] != profile['native_player_id']:
        raise ValueError('Native identity mapping mismatch')
    if sum(r['native_player_id'] == owner['native_player_id'] and r.get('status') == 'active' for r in registry['players']) != 1:
        raise ValueError('Multiple owners of the native slot')
    return owner


def cache_key(profile):
    recipe = {k:v for k,v in profile.items() if k != 'output'}
    files = {str(HERE/name):sha(HERE/name) for name in CODE}
    for key in INPUTS:
        path = Path(profile[key]).resolve()
        files[str(path)] = sha(path)
        if key in ('native_face', 'native_body'):
            doc = json.loads(path.read_text(encoding='utf-8'))
            for buffer in doc['buffers']:
                binary = (path.parent/buffer['uri']).resolve()
                if not binary.is_relative_to(path.parent):
                    raise ValueError('Reference buffer is outside its directory')
                files[str(binary)] = sha(binary)
    return hashlib.sha256(json.dumps(dict(recipe=recipe,files=files),sort_keys=True).encode()).hexdigest()


def plan(manifest):
    registry = json.loads(Path(manifest['registry']).read_text(encoding='utf-8'))
    records, ids = [], set()
    for profile in manifest['players']:
        base = profile['base_id']
        if base in ids:
            raise ValueError('Duplicate BaseId in manifest')
        ids.add(base)
        owner = identify(profile, registry)
        record = dict(base_id=base,name=owner['canonical_name'])
        if profile.get('source_status') == 'missing':
            record.update(status='skipped_missing_source',reason=profile.get('source_note','FL26 source unavailable'))
        elif profile.get('source_status') != 'available':
            raise ValueError('Explicit source_status available/missing is required')
        else:
            missing = [key for key in INPUTS if not Path(profile.get(key, '')).is_file()]
            record.update(status='needs_inputs' if missing else 'ready',missing_inputs=missing)
        records.append(record)
    return records


def cached_outputs_valid(folder, key):
    report = folder/'complete.json'
    if not report.is_file():
        return False
    saved = json.loads(report.read_text())
    expected = {'face.fbx','fit-report.json','roundtrip-pose-report.json','motion-samples.json','reference-fit.blend'}
    return (saved.get('cache_key') == key and set(saved.get('outputs',{})) == expected and
            all((folder/'candidate'/name).is_file() and sha(folder/'candidate'/name) == digest
                for name,digest in saved['outputs'].items()))


def run(manifest, selected=None, resume=False):
    records = plan(manifest)
    if selected is not None and selected not in {r['base_id'] for r in records}:
        raise ValueError('Selected BaseId is absent from manifest')
    blender = Path(manifest['blender']).resolve()
    work = Path(manifest['work_dir']).resolve()
    work.mkdir(parents=True,exist_ok=True)
    for profile,record in zip(manifest['players'],records):
        if selected is not None and profile['base_id'] != selected:
            record['status'] = 'not_selected'
            continue
        if record['status'] != 'ready':
            continue
        try:
            key = hashlib.sha256((cache_key(profile)+sha(blender)).encode()).hexdigest()
            folder = work/(str(profile['base_id'])+'-'+key[:16])
            if folder.exists() and not resume:
                raise ValueError('Existing job requires --resume')
            folder.mkdir(exist_ok=True)
            record['output'] = str(folder/'candidate')
            if resume and cached_outputs_valid(folder,key):
                record['status'] = 'validated_cached'
                continue
            if (folder/'complete.json').exists():
                raise ValueError('Cached output changed; use a fresh work_dir for rebuilding')
            candidate = folder/'candidate'
            recipe = dict(profile,output=str(candidate))
            config = folder/'profile.json'
            config.write_text(json.dumps(recipe,indent=2)+'\n',encoding='utf-8')
            commands = []
            if not candidate.exists():
                commands.append(('fit',HERE/'blender_fit_realface.py',['--profile',str(config)]))
            elif not all((candidate/name).is_file() for name in ('face.fbx','fit-report.json','motion-samples.json','reference-fit.blend')):
                raise ValueError('Incomplete fit requires a fresh work_dir')
            commands.append(('validate',HERE/'validate_realface_fit.py',['--profile',str(config),'--candidate',str(candidate)]))
            for stage,script,args in commands:
                with (folder/(stage+'.log')).open('w',encoding='utf-8') as log:
                    subprocess.run([str(blender),'--background','--python-exit-code','1',
                                    '--python',str(script),'--',*args],check=True,stdout=log,stderr=subprocess.STDOUT)
            outputs = {name:sha(candidate/name) for name in ('face.fbx','fit-report.json','roundtrip-pose-report.json','motion-samples.json','reference-fit.blend')}
            (folder/'complete.json').write_text(json.dumps(dict(cache_key=key,outputs=outputs,hardware_accepted=False),indent=2)+'\n')
            record['status'] = 'validated_pending_device'
        except (ValueError, OSError, subprocess.CalledProcessError) as error:
            record.update(status='needs_review',reason=str(error))
    (work/'batch-report.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('plan','run'))
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--player',type=int)
    parser.add_argument('--resume',action='store_true')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    records = plan(manifest) if args.command == 'plan' else run(manifest,args.player,args.resume)
    print(json.dumps(records,indent=2))
    if any(r['status'] in ('needs_inputs','needs_review') for r in records):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

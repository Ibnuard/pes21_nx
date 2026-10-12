"""Optimize an already reviewed local stadium batch without reconverting FL26.

Config requires blender. The source workspace must contain prepared/<key>.
Outputs are separate, source inputs are never modified, OBBs are not copied.
"""
import argparse
import json
from pathlib import Path
import subprocess
from stadium_assets import asset_key
from stadium_atlas import prepare


def main():
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--keys', nargs='+')
    p.add_argument('--manifest', type=Path, default=root/'data/stadiums/fl26_addons_v25.json')
    p.add_argument('--vertex-camera-cull', action='store_true')
    p.add_argument('--rebuild', action='store_true')
    a = p.parse_args()
    config = json.loads(a.config.read_text())
    rows = json.loads(a.manifest.read_text())['stadiums']
    keys = [asset_key(k) for k in a.keys] if a.keys else [r['key'] for r in rows]
    if len(set(keys)) != len(keys) or set(keys) - {r['key'] for r in rows}:
        raise ValueError('Duplicate or unreviewed stadium key')
    if a.source.resolve() == a.work.resolve():
        raise ValueError('Use a separate output workspace')
    for key in keys:
        row = next(r for r in rows if r['key'] == key)
        source = a.source.resolve() / 'prepared' / key / 'fbx.local.json'
        target = a.work.resolve() / 'prepared' / key
        if (target / 'fbx.local.json').exists() and not a.rebuild:
            raise FileExistsError('Use --rebuild to replace this candidate: ' + key)
        target.mkdir(parents=True, exist_ok=True)
        print('ATLAS', key, flush=True)
        prepare(source, target / 'textures')
        def blender(script, arguments, log_name):
            with (target / log_name).open('w') as log:
                subprocess.run([config['blender'], '--background', '--python-exit-code', '1',
                    '--python', str(root / 'tools' / script), '--'] + arguments,
                    stdout=log, stderr=subprocess.STDOUT, check=True)
        use_cull = a.vertex_camera_cull and row.get('vertex_camera_cull', True)
        blender('optimize_stadium_shell.py', ['--profile', str(source), '--output', str(target)]+(['--vertex-camera-cull'] if use_cull else []), 'optimize.log')
        blend = target / (key + 'Shell.blend')
        blender('audit_stadium_camera.py', ['--blend', str(blend), '--mesh', key + 'Shell',
            '--output', str(target / 'camera.local.json')], 'camera.log')
        blender('audit_stadium_roof.py', ['--blend', str(blend), '--output', str(target / 'roof.local.json'),
            '--min-height', str(row['min_roof_height_m'])], 'roof.log')
        report = json.loads((target / 'fbx.local.json').read_text())
        print('OPTIMIZED', key, report['optimization'], flush=True)


if __name__ == '__main__':
    main()

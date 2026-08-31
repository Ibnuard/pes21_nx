"""Stage only this UI delta on the tested v1.98-derived runtime source.

The user's dist, stable worktree and installed binaries are never overwritten.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

MODIFIED = ('source/android_shim.c', 'source/config.c', 'source/config.h', 'source/overlay.c',
            'source/ue4_hooks.c', 'source/ue4_hooks.h')
ADDED = ('source/match_visual_policy.h',)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, default=Path('local-debug/v198-stable-player-build'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (root/args.output).resolve()
    output.relative_to(root/'local-debug')
    if output.exists():
        raise ValueError('output must be a new build directory')
    baseline = args.baseline.resolve()
    output.mkdir(parents=True)
    for directory in ('source', 'data'):
        shutil.copytree(baseline/directory, output/directory)
    for name in ('Makefile', 'icon.jpg', 'build-wsl.ps1'):
        shutil.copy2(baseline/name, output/name)
    patch = subprocess.run(['git', 'diff', '--binary', '--', *MODIFIED],
                           cwd=root, check=True, capture_output=True).stdout
    if not patch:
        raise ValueError('no runtime delta to build')
    prefix = str(output.relative_to(root)).replace('\\', '/')
    # Apply mechanically to a NEW copy, never the v1.98-derived baseline.
    command = ['git', 'apply', '--whitespace=nowarn', '--directory='+prefix]
    subprocess.run(command+['--check', '-'], input=patch, cwd=root, check=True)
    subprocess.run(command+['-'], input=patch, cwd=root, check=True)
    for name in ADDED:
        shutil.copy2(root/name, output/name)
    changes = []
    allowed = set(MODIFIED+ADDED)
    for path in (output/'source').iterdir():
        if not path.is_file():
            continue
        name = path.relative_to(output).as_posix()
        previous = baseline/name
        if not previous.exists() or path.read_bytes() != previous.read_bytes():
            if name not in allowed:
                raise ValueError('unexpected runtime change: '+name)
            changes.append(name)
    report = {'baseline': str(baseline), 'changed_source_files': changes,
              'camera_render_polling_allocator_rosters_unchanged': True,
              'diagnostics': False, 'perf_trace': False,
              'delta_sha256': hashlib.sha256(patch).hexdigest(),
              'source_sha256': {name:hashlib.sha256((output/name).read_bytes()).hexdigest()
                                for name in changes}}
    (output/'runtime-delta.patch').write_bytes(patch)
    (output/'source-validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

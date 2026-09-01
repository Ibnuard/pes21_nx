"""Stage an explicit revision delta on a tested runtime snapshot.

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
ADDED = ('source/match_visual_policy.h', 'source/native_pad_lab.inc')


def revision_delta(root, revision, paths=MODIFIED):
    # Never use bare `git diff`: after a commit it silently omits accepted
    # features, yet the patch can still apply to an older runtime snapshot.
    base = subprocess.run(['git', 'rev-parse', '--verify', revision],
                          cwd=root, check=True, capture_output=True,
                          text=True).stdout.strip()
    kind = subprocess.run(['git', 'cat-file', '-t', base], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()
    if kind != 'commit':
        raise ValueError('delta base must resolve to a commit')
    patch = subprocess.run(['git', 'diff', '--binary', base, '--', *paths],
                           cwd=root, check=True, capture_output=True).stdout
    return base, patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--delta-base', required=True,
                        help='Git commit matching the feature level of the snapshot')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (root/args.output).resolve()
    output.relative_to(root/'local-debug')
    if output.exists():
        raise ValueError('output must be a new build directory')
    baseline = args.baseline.resolve()
    base, patch = revision_delta(root, args.delta_base)
    if not patch:
        raise ValueError('no runtime delta to build')
    output.mkdir(parents=True)
    for directory in ('source', 'data'):
        shutil.copytree(baseline/directory, output/directory)
    for name in ('Makefile', 'icon.jpg', 'build-wsl.ps1'):
        shutil.copy2(baseline/name, output/name)
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
    report = {'baseline': str(baseline), 'delta_base_commit': base,
              'changed_source_files': changes,
              'baseline_unchanged_outside_listed_source_files': True,
              'diagnostics': False, 'perf_trace': False,
              'delta_sha256': hashlib.sha256(patch).hexdigest(),
              'source_sha256': {name:hashlib.sha256((output/name).read_bytes()).hexdigest()
                                for name in changes}}
    (output/'runtime-delta.patch').write_bytes(patch)
    (output/'source-validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

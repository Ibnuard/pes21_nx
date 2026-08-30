"""Extract local EF10 scoreboard/pitch sources; never transplant newer packages.

Uses the same locally verified retoc/key pipeline as the portrait converter.
Output is private, ignored staging data, not a distributable game asset pack.
"""
from pathlib import Path
import argparse
import subprocess
from extract_efootball10_portraits import DEFAULT_AES_KEY


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--container-dir', type=Path, default=Path('local-debug/efootball10-audit/pad-assets/assets'))
    p.add_argument('--output', type=Path, default=Path('local-debug/stability-visuals/ef10'))
    p.add_argument('--retoc', type=Path, default=Path('local-debug/tools/retoc-v0.1.5/retoc.exe'))
    p.add_argument('--aes-key', default=DEFAULT_AES_KEY)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for asset_filter in ('/MatchTime/', '/MatchScore/', '/Pitch/'):
        result = subprocess.run([
            str(args.retoc.resolve()), '--aes-key', args.aes_key,
            '--override-container-header-version', 'PreInitial',
            'to-legacy', str(args.container_dir.resolve()), str(args.output.resolve()),
            '--filter', asset_filter, '--version', 'UE4_26', '--no-shaders', '--no-parallel',
        ], capture_output=True, text=True)
        label = asset_filter.strip('/')
        (args.output / f'{label}-extract.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        print(f'{label}: retoc exit={result.returncode}', flush=True)
        if result.returncode:
            raise RuntimeError(f'Extraction failed; see {label}-extract.log')


if __name__ == '__main__':
    main()

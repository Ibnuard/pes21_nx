"""Resume the serial Barca/MU experiment from one explicit pipeline phase.

This is a local CLI batch, not a scheduler. It uses one Blender/validation
worker and stops on command failures. It does not install its test package.
"""
import argparse
from pathlib import Path
import subprocess
import sys

from realface_batch_inventory import read, write
from realface_budget_experiment import CAPS, ROOT


PHASES = ('prepare', 'recover', 'cook', 'verify', 'preview', 'package')
HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--baseline-stage', required=True, type=Path)
    p.add_argument('--baseline-verification', required=True, type=Path)
    p.add_argument('--cap', type=int, choices=CAPS, default=6000)
    p.add_argument('--from-phase', choices=PHASES, default='prepare')
    p.add_argument('--import-chunk-size', type=int, choices=range(1,17), default=8)
    a = p.parse_args()
    output = a.output.resolve()
    if not output.is_relative_to(ROOT/'local-debug') or output == ROOT/'local-debug':
        p.error('Use a dedicated ignored local-debug directory')
    work = output/str(a.cap)
    for phase in PHASES[PHASES.index(a.from_phase):]:
        if phase == 'recover' and a.cap != 6000:
            continue
        write(output/'RUN-STATUS.json', dict(phase=phase, state='running', cap=a.cap,
              workers=1, installed=False, hardware_accepted=False))
        if phase in ('prepare', 'verify'):
            args = [sys.executable, str(HERE/'realface_budget_experiment.py'), phase,
                    '--config', str(a.config.resolve()), '--output', str(output),
                    '--cap', str(a.cap), '--team', '100', '--team', '108',
                    '--scope-verification', str(a.baseline_verification.resolve()), '--workers', '1']
        elif phase == 'cook':
            args = [sys.executable, str(HERE/'realface_budget_cook.py'),
                    '--config', str(work/'config.local.json'),
                    '--chunk-size', str(a.import_chunk_size)]
        elif phase == 'recover':
            args = [sys.executable, str(HERE/'realface_budget_recover.py'),
                    '--config', str(work/'config.local.json')]
        elif phase == 'preview':
            rows = read(work/'verify-report.json')
            selected = [r['base_id'] for r in rows if r['base_id'] in (162114,119835,60512)
                        and r['status'] in ('validated','validated_cached')]
            if not selected:
                raise ValueError('No verified pilot heads available for preview')
            args = [sys.executable, str(HERE/'realface_league_preview.py'), '--config',
                    str(work/'config.local.json'), '--stage', 'cooked',
                    '--views', 'front', 'left', 'right', 'above']
            for base in selected: args += ['--player', str(base)]
        else:
            args = [sys.executable, str(HERE/'realface_budget_package.py'),
                    '--config', str(work/'config.local.json'), '--scope', str(output/'team-scope.json'),
                    '--baseline-stage', str(a.baseline_stage.resolve()),
                    '--baseline-verification', str(a.baseline_verification.resolve())]
        try:
            subprocess.run(args, check=True, cwd=ROOT)
        except (subprocess.CalledProcessError, OSError) as error:
            write(output/'RUN-STATUS.json', dict(phase=phase, state='failed', reason=str(error),
                  cap=a.cap, workers=1, installed=False, hardware_accepted=False))
            raise
    write(output/'RUN-STATUS.json', dict(phase='package', state='test_package_ready', cap=a.cap,
          workers=1, installed=False, hardware_accepted=False, visual_review_required=True))


if __name__ == '__main__':
    main()

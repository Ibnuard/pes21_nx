"""Serial complete-cohort continuation, including documented source aliases."""
import argparse
import subprocess
import sys
from pathlib import Path

from realface_league_source_extension import extend
from realface_league_balanced import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    args=parser.parse_args()
    # Each stage owns/releases the same exclusive lock. No nested Blender
    # workers or editor processes run across these stage boundaries.
    proof=extend(args.config)
    print(dict(phase='source_extension',source_count=proof['source_count'],
               added_base_ids=proof['added_base_ids']),flush=True)
    run(args.config)
    subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('realface_league_hold_repair.py')),
                    '--config',args.config],check=True)


if __name__=='__main__':
    main()

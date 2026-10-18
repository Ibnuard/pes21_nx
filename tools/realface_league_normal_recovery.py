"""Rebuild held exports with explicit finite eye normals, under the same head cap."""
import argparse
from pathlib import Path
import shutil

from realface_batch_inventory import read,write
import realface_league_mobile as mobile

BASE_ALLOCATIONS=mobile.allocations()


def allocations():
    return [dict(row,normal_export_recovery=True) for row in BASE_ALLOCATIONS]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--player',action='append',type=int,default=[])
    parser.add_argument('--workers',type=int,default=2,choices=(1,2))
    args=parser.parse_args();config=read(args.config);source=Path(config['work_dir']);work=source.parent/'normal-export'
    selected=set(args.player) or {r['base_id'] for r in read(source/'verify-report.json') if r['status']=='held_cook_validation'}
    if not selected:raise ValueError('No held cook or explicitly selected players')
    work.mkdir(parents=True,exist_ok=True)
    hold=source/'QUALITY-HOLD.json'
    if not hold.exists():raise ValueError('Recovery requires the visual release hold')
    if hold.resolve()!=(work/hold.name).resolve():shutil.copy2(hold,work/hold.name)
    local=dict(config,work_dir=str(work));write(work/'config.local.json',local)
    mobile.allocations=allocations;process=mobile.PreparationProcess
    mobile.PreparationProcess=lambda blender:process(blender,script=mobile.HERE/'blender_realface_normal_worker.py')
    mobile.prepare(local,selected,args.workers)


if __name__=='__main__':main()

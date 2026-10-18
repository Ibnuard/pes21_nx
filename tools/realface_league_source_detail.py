"""Bounded source-eye and face-detail recovery, isolated from the default recipe."""
import argparse
from pathlib import Path
import shutil

from realface_batch_inventory import read,write
import realface_league_mobile as mobile


def allocations():
    rows=[]
    for policy in ('original_visible','measured_aperture'):
        for skin in (1500,1400,1600,1300,1700):
            for mode in ('shell','closed'):
                rows.append(dict(face_skin=skin,eye=256,hair=600,head_cap=2000,source_eye_policy=policy,
                hair_mode=mode,solid_scalp=True,source_eye=True,eyelid_lock_cm=.4,
                skin_feature_policy=True,skin_error_cm=.45,eye_error_cm=.06,
                eye_uv_weight=.1,skin_uv_weight=10.,skin_normal_weight=1.))
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--player',action='append',type=int,required=True)
    parser.add_argument('--workers',type=int,default=2,choices=(1,2))
    args=parser.parse_args();config=read(args.config);source=Path(config['work_dir'])
    work=source.parent/'source-detail';work.mkdir(parents=True,exist_ok=True)
    if (source/'QUALITY-HOLD.json').exists():
        if source.resolve()!=work.resolve():shutil.copy2(source/'QUALITY-HOLD.json',work/'QUALITY-HOLD.json')
    else:raise ValueError('Source-detail trials require an explicit visual release hold')
    local=dict(config,work_dir=str(work))
    write(work/'config.local.json',local)
    mobile.allocations=allocations
    process=mobile.PreparationProcess
    mobile.PreparationProcess=lambda blender:process(blender,script=mobile.HERE/'blender_realface_source_worker.py')
    mobile.prepare(local,set(args.player),args.workers)


if __name__=='__main__':main()

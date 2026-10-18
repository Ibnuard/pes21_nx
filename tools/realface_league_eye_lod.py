"""Bounded original-eye LOD trials; preserve placement and the strict head cap."""
import argparse
from pathlib import Path
import shutil

from realface_batch_inventory import read,write
import realface_league_mobile as mobile

def allocations():
    return [dict(face_skin=skin,eye=eye,hair=hair,hair_mode=mode,solid_scalp=True,head_cap=2000,
        source_eye=True,source_eye_policy='original_lod',normal_export_recovery=True,
        eyelid_lock_cm=.4,skin_feature_policy=True,skin_error_cm=.45,eye_error_cm=.06,
        eye_uv_weight=.1,skin_uv_weight=10.,skin_normal_weight=1.)
        for skin,eye,hair in ((1600,160,240),(1500,192,300),(1500,256,240),(1400,320,270),(1400,192,400))
        for mode in ('shell','closed')]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True)
    parser.add_argument('--player',action='append',type=int,required=True)
    parser.add_argument('--workers',type=int,default=1,choices=(1,2));args=parser.parse_args()
    config=read(args.config);source=Path(config['work_dir']);work=source.parent/'eye-lod'
    work.mkdir(parents=True,exist_ok=True);hold=source/'QUALITY-HOLD.json'
    if not hold.exists():raise ValueError('Eye-LOD trials require the visual release hold')
    if hold.resolve()!=(work/hold.name).resolve():shutil.copy2(hold,work/hold.name)
    local=dict(config,work_dir=str(work));write(work/'config.local.json',local)
    mobile.allocations=allocations;process=mobile.PreparationProcess
    mobile.PreparationProcess=lambda blender:process(blender,script=mobile.HERE/'blender_realface_eye_lod_worker.py')
    mobile.prepare(local,set(args.player),args.workers)

if __name__=='__main__':main()

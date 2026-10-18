"""Isolated, bounded joined-hair retries; never publish a technical-only pass."""
import argparse
from pathlib import Path
import shutil

from realface_batch_inventory import read,write
import realface_league_mobile as mobile
from realface_league_progress import indexed,owner_matches


def select(owners,prepared,players=None,held=None):
    candidates=set(players or [])
    if held is not None:
        for row in held:
            base=row['base_id']
            if not owner_matches(row,owners.get(base,{})):
                raise ValueError('Hair retry source identity differs')
            if row['status'].startswith('held') and prepared.get(base,{}).get('status') not in ('prepared','prepared_cached'):
                candidates.add(base)
    if candidates-owners.keys():raise ValueError('Hair retry requires a verified source identity')
    if any(prepared.get(base,{}).get('reuse_cooked') for base in candidates):
        raise ValueError('An accepted inherited head cannot be replaced by a hair experiment')
    return candidates


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    selection=parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--player',action='append',type=int)
    selection.add_argument('--held-report',help='Retry held source identities absent from the canonical prepared set')
    parser.add_argument('--work-dir')
    parser.add_argument('--workers',type=int,choices=(1,2),default=1)
    args=parser.parse_args();config=read(args.config);source=Path(config['work_dir'])
    owners=indexed(read(config['source_profiles']),'sources')
    prepared=indexed(read(source/'prepare-report.json'),'prepared')
    for base,row in prepared.items():
        if not owner_matches(row,owners.get(base,{})):raise ValueError('Prepared owner differs from hair source')
    selected=select(owners,prepared,args.player,read(args.held_report) if args.held_report else None)
    print(dict(selected=len(selected),source_heads=len(owners),visual_approval=False),flush=True)
    if not selected:return
    work=Path(args.work_dir) if args.work_dir else source.parent/'volume-recovery'
    if work.resolve()==source.resolve() or not any(
            work.resolve().is_relative_to(mobile.HERE.parent/name) and work.resolve()!=mobile.HERE.parent/name
            for name in ('local-debug','local-inputs')):
        raise ValueError('Hair trials require a separate ignored work directory')
    hold=source/'QUALITY-HOLD.json'
    if not hold.exists() or read(hold).get('approved') is not False:
        raise ValueError('Hair experiments require an explicit unresolved visual hold')
    budget=dict(head_cap=2000,skin_feature_policy=True,skin_error_cm=.45,eye_error_cm=.06,
        eye_uv_weight=.1,skin_uv_weight=10.,skin_normal_weight=1.,native_seam_alias=True,
        normal_export_recovery=True,source_eye=True,source_eye_policy='original_lod',
        eyelid_lock_cm=.4,eye=128,hair=650,hair_mode='alpha_volume',volume_closing_steps=5)
    # Hair is an upper bound. The worker spends only what remains after the
    # actual face/eye triangle count, then rechecks the complete head at 2,000.
    overrides={str(base):[dict(budget,face_skin=skin) for skin in (1400,1500,1600,1700)] for base in selected}
    work.mkdir(parents=True,exist_ok=True);shutil.copy2(hold,work/hold.name)
    config=dict(config,work_dir=str(work.resolve()),allocation_overrides=overrides)
    write(work/'config.local.json',config)
    process=mobile.PreparationProcess
    mobile.PreparationProcess=lambda blender:process(blender,script=mobile.HERE/'blender_realface_volume_worker.py')
    mobile.prepare(config,selected,args.workers)


if __name__=='__main__':main()

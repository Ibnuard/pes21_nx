"""Retry exceptional league inputs with explicit, cached source/geometry policy."""
import argparse
from pathlib import Path
import shutil

from realface_batch import command
from realface_batch_inventory import read, write
from realface_pipeline import sha
import realface_league_mobile as mobile

BASE_ALLOCATIONS=mobile.allocations()


def allocations():
    rows=list(BASE_ALLOCATIONS)
    for uv in (3.,1.):
        for skin,eye,hair in ((1600,128,260),(1500,192,300),(1600,192,200),
                               (1400,192,400),(1200,192,600),(1700,192,100)):
            for mode,solid in (('shell',True),('shell',False),('cards',False),('closed',False)):
                row=dict(BASE_ALLOCATIONS[0],face_skin=skin,eye=eye,hair=hair,
                         hair_mode=mode,solid_scalp=solid,skin_uv_weight=uv)
                rows.append(row)
    # Explicit skin-only / bald sources can use almost all geometry on skin.
    for skin,eye in ((1800,192),(1735,256),(1650,320)):
        for uv in (10.,3.,1.):
            rows.append(dict(BASE_ALLOCATIONS[0],face_skin=skin,eye=eye,hair=1,
                             hair_mode='closed',solid_scalp=False,skin_uv_weight=uv))
    # Extra angular samples and a wider inner ring keep visible sclera while
    # the unchanged enclosure gate continues to reject spill or a lost pupil.
    for uv in (10.,3.,1.):
        for skin,eye,hair in ((1500,192,300),(1400,256,340),(1600,256,130)):
            for mode,solid in (('shell',True),('shell',False),('cards',False),('closed',False)):
                rows.append(dict(BASE_ALLOCATIONS[0],face_skin=skin,eye=eye,hair=hair,
                    hair_mode=mode,solid_scalp=solid,skin_uv_weight=uv,eye_recovery=True))
    return [dict(row,league_recovery=True,normal_export_recovery=True) for row in rows]


def repartition(config):
    sources=read(config['source_profiles']);work=Path(config['work_dir']).parent
    script=mobile.HERE/'blender_realface_merge_scalp.py'
    for row in sources:
        profile=read(row['profile'])
        if not profile.get('hair_skin_materials'):continue
        for path,digest in row['input_hashes'].items():
            if sha(path)!=digest:raise ValueError('Scalp source changed')
        folder=work/'scalp-partitions'/str(row['base_id'])
        job=dict(profile=profile,source_profile_path=row['profile'],folder=str(folder),
                 native_rig=config['native_rig'],cooked_rig=config['cooked_rig'])
        write(folder/'job.json',job)
        command([config['blender'],'--background','--threads','2','--python-exit-code','1',
                 '--python',script,'--',folder/'job.json'],folder/'partition.log')
        row['profile']=str(folder/'ue-profile.json')
        row['input_hashes'].update({str(p):sha(p) for p in [script,folder/'ue-profile.json',folder/'face.fbx',
            folder/'hair.fbx',folder/'empty-hair.png',folder/'partition-proof.json']})
        print('REPARTITIONED',row['base_id'],flush=True)
    output=work/'scalp-sources.local.json';write(output,sources)
    return str(output)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--partition',action='store_true')
    parser.add_argument('--player',action='append',type=int,default=[])
    parser.add_argument('--workers',type=int,default=2,choices=range(1,5))
    args=parser.parse_args();config=read(args.config)
    if args.partition:
        repartition(config);return
    source=Path(config['work_dir']);records=read(source/'prepare-report.json')
    selected=set(args.player) or {r['base_id'] for r in records if r['status'].startswith('held')}
    local=dict(config,work_dir=str(source.parent/'recovery'))
    work=Path(local['work_dir']);work.mkdir(parents=True,exist_ok=True)
    hold=source/'QUALITY-HOLD.json'
    if not hold.exists():raise ValueError('Recovery requires the visual release hold')
    if hold.resolve()!=(work/hold.name).resolve():shutil.copy2(hold,work/hold.name)
    override=source.parent/'scalp-sources.local.json'
    if override.exists():local['source_profiles']=str(override)
    write(work/'config.local.json',local)
    mobile.allocations=allocations
    original_process=mobile.PreparationProcess
    mobile.PreparationProcess=lambda blender:original_process(blender,
        script=mobile.HERE/'blender_realface_league_recovery_worker.py')
    mobile.prepare(local,selected,args.workers)


if __name__=='__main__':main()

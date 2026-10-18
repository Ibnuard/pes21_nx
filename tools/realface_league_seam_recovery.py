"""Retry selected prepared heads with seam-safe index reduction and unchanged budgets."""
import argparse
from pathlib import Path
import shutil

from realface_batch_inventory import read,write
import realface_league_mobile as mobile
from realface_league_progress import owner_matches,indexed


def marker_candidates(rows):
    """Cheap preselection only; the worker checks actual weights and visibility."""
    from realface_pipeline import sha
    from realface_skin_markers import marker_triangles
    selected=set()
    for base,row in rows.items():
        if row.get('reuse_cooked') or row.get('budgets',{}).get('skin_marker_cleanup'):
            continue
        folder=Path(row['folder']);source=folder/'lite_skin-meshopt.json'
        if not source.exists():continue
        stamp=read(folder/'complete.json')
        if stamp.get('cache_key')!=row['cache_key'] or stamp.get('outputs',{}).get(source.name)!=sha(source):
            raise ValueError('Marker preselection input differs from its immutable preparation')
        data=read(source)
        possible,_=marker_triangles(data['positions'],data['indices'],
            [(('preselection_only',1.),)]*(len(data['positions'])//3))
        if len(possible)>=24:selected.add(base)
    return selected


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True)
    parser.add_argument('--overlay',action='append',default=[])
    selection=parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--player',type=int,action='append')
    selection.add_argument('--all-prepared',action='store_true')
    parser.add_argument('--work-dir',help='Separate ignored work directory for an isolated retry')
    parser.add_argument('--rebalance',action='store_true',
        help='Try shifting up to 80 skin triangles to hair, retaining all quality gates')
    parser.add_argument('--marker-cleanup',action='store_true',
        help='Remove only isolated microscopic skin markers with unchanged 13-view coverage/depth')
    parser.add_argument('--workers',type=int,choices=(1,2,3,4),default=2);args=parser.parse_args()
    config=read(args.config);source=Path(config['work_dir'])
    owners=indexed(read(config['source_profiles']),'sources');rows={}
    for folder in map(Path,[config['work_dir'],*args.overlay]):
        for base,row in indexed(read(folder/'prepare-report.json'),str(folder)).items():
            if not owner_matches(row,owners.get(base,{})):raise ValueError('Recovery source identity differs')
            if row['status'] in ('prepared','prepared_cached') and not row.get('reuse_cooked'):rows[base]=row
    selected=set(rows) if args.all_prepared else set(args.player)
    if selected-rows.keys():raise ValueError('Selected players require an existing prepared budget')
    if args.marker_cleanup and args.all_prepared:
        selected=marker_candidates(rows)
        print(dict(marker_candidates=len(selected),prepared_heads_checked=len(rows)),flush=True)
    # The lower-level factory interprets an empty selection as the full batch.
    # A clean marker scan must be a no-op, never an accidental full rebuild.
    if not selected:return
    overrides={str(base):[dict(rows[base]['budgets'],native_seam_alias=True,normal_export_recovery=True)]
               for base in selected}
    if args.marker_cleanup:
        for budgets in overrides.values():budgets[0]['skin_marker_cleanup']=True
    if args.rebalance:
        for budgets in overrides.values():
            original=budgets[0]
            budgets.extend(dict(original,face_skin=original['face_skin']-shift,hair=original['hair']+shift)
                           for shift in (20,40,80) if original['face_skin']-shift>=1200)
    work=Path(args.work_dir) if args.work_dir else source.parent/('marker-recovery' if args.marker_cleanup else 'seam-recovery')
    if not any(work.resolve().is_relative_to(mobile.HERE.parent/folder) and work.resolve()!=mobile.HERE.parent/folder
               for folder in ('local-debug','local-inputs')):
        raise ValueError('Recovery output must be a dedicated ignored local directory')
    work.mkdir(parents=True,exist_ok=True)
    hold=source/'QUALITY-HOLD.json'
    if not hold.exists():raise ValueError('Seam recovery requires the visual release hold')
    if hold.resolve()!=(work/hold.name).resolve():shutil.copy2(hold,work/hold.name)
    local=dict(config,work_dir=str(work),allocation_overrides=overrides)
    write(work/'config.local.json',local)
    process=mobile.PreparationProcess
    script='blender_realface_marker_worker.py' if args.marker_cleanup else 'blender_realface_seam_worker.py'
    mobile.PreparationProcess=lambda blender:process(blender,script=mobile.HERE/script)
    mobile.prepare(local,selected,args.workers)


if __name__=='__main__':main()

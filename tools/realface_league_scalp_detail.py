"""Recover facial detail without wasting triangles on a verified empty hair slot."""
import argparse
from pathlib import Path
import shutil

from realface_batch_inventory import read,write
import realface_league_mobile as mobile


def allocations(whole_eye_lod=False):
    rows=[dict(face_skin=skin,eye=eye,hair=1,hair_mode='closed',head_cap=2000,
        face_detail=True,normal_export_recovery=True,skin_feature_policy=True,
        source_eye=True,source_eye_policy='original_visible',
        eyelid_lock_cm=.4,skin_error_cm=.45,eye_error_cm=.06,eye_uv_weight=.1,
        skin_uv_weight=10.,skin_normal_weight=1.)
        for skin,eye in ((1800,192),(1700,288),(1600,384),(1500,480))]
    if whole_eye_lod:
        return [dict(row,source_eye_policy='scalp_original_lod') for row in rows]
    return rows+[dict(rows[0],source_eye=False,source_eye_policy='existing_cleanup')]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True)
    parser.add_argument('--whole-eye-lod',action='store_true',
        help='Try bounded reduction of original whole eyes in a separate work directory')
    parser.add_argument('--workers',type=int,default=2,choices=(1,2));args=parser.parse_args()
    config=read(args.config);source=Path(config['work_dir'])
    work=source.parent/('scalp-eye-lod' if args.whole_eye_lod else 'scalp-detail')
    candidates=[row for row in read(config['source_profiles'])
        if any(Path(path).name=='partition-proof.json' for path in row['input_hashes'])]
    selected={row['base_id'] for row in candidates
        if read(row['profile']).get('empty_hair_slot',{}).get('policy')=='all_source_skin_transferred_to_face'}
    if not selected:raise ValueError('No verified skin-only source partitions')
    work.mkdir(parents=True,exist_ok=True);hold=source/'QUALITY-HOLD.json'
    if not hold.exists():raise ValueError('Scalp-detail recovery requires the visual release hold')
    if hold.resolve()!=(work/hold.name).resolve():shutil.copy2(hold,work/hold.name)
    local=dict(config,work_dir=str(work));write(work/'config.local.json',local)
    mobile.allocations=lambda:allocations(args.whole_eye_lod);process=mobile.PreparationProcess
    script='blender_realface_scalp_eye_lod_worker.py' if args.whole_eye_lod else 'blender_realface_scalp_detail_worker.py'
    mobile.PreparationProcess=lambda blender:process(blender,script=mobile.HERE/script)
    mobile.prepare(local,selected,args.workers)


if __name__=='__main__':main()

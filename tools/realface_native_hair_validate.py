"""Cook/validate current native-style hair trials; never package or install.

Geometry holds stay in their trial reports. A successful cook remains an
appearance/device hold and cannot replace the canonical or accepted heads.
"""
import argparse
from pathlib import Path

from realface_batch import valid_cache
from realface_batch_inventory import read,write
from realface_batch_release import cook,verify
from realface_league_progress import indexed,owner_matches
from realface_mobile import cooked_counts
from realface_native_hair_trial import CODE,HERE
from realface_pipeline import sha


def candidates(config,trials):
    owners=indexed(read(config['source_profiles']),'sources')
    canonical=indexed(read(Path(config['work_dir'])/'prepare-report.json'),'prepared')
    code={name:sha(HERE/name) for name in CODE};selected={}
    for trial in trials:
        for row in read(Path(trial)/'trial-report.json'):
            if row['status']!='candidate_visual_hold':continue
            base=row['base_id']
            if not owner_matches(row,owners.get(base,{})):
                raise ValueError('Native hair candidate source identity differs')
            if canonical.get(base,{}).get('reuse_cooked'):
                raise ValueError('Native hair candidate cannot replace an accepted inherited head')
            if row.get('recipe_source_sha256')!=code:
                raise ValueError('Native hair candidate uses an older geometry recipe')
            if not row.get('composite_geometry_pass') or not valid_cache(Path(row['folder']),row['cache_key']):
                raise ValueError('Native hair candidate bytes or geometry proof changed')
            if base in selected and selected[base]['cache_key']!=row['cache_key']:
                raise ValueError('Select one native hair candidate per identity')
            selected[base]=dict(row,status='prepared',candidate_status=row['status'],quality_level=0,
                budgets=dict(head_cap=2000,native_opaque_base=True,native_detail_cards=True,source_eye=True))
    return sorted(selected.values(),key=lambda r:r['base_id'])


def validate(config,trials,work,workers=2):
    work=Path(work).resolve();root=HERE.parent
    if (not work.is_relative_to(root/'local-debug') or work==root/'local-debug' or
            work in [Path(config['work_dir']).resolve(),*(Path(t).resolve() for t in trials)]):
        raise ValueError('Native hair validation requires a separate ignored work directory')
    rows=candidates(config,trials)
    if not rows:
        print(dict(selected=0,action='no_op'),flush=True);return
    hold=work/'QUALITY-HOLD.json'
    if hold.exists() and read(hold).get('approved') is not False:
        raise ValueError('Choose a separate directory; do not overwrite an appearance approval')
    work.mkdir(parents=True,exist_ok=True)
    write(hold,dict(approved=False,reason='Native hair trials: appearance/device review pending; no release'))
    cfg=dict(config,work_dir=str(work));write(work/'config.local.json',cfg);write(work/'prepare-report.json',rows)
    cook(cfg);verify(cfg,workers)
    result=[]
    for row in read(work/'verify-report.json'):
        counts=cooked_counts(read(Path(row['cooked_folder'])/'verification.json')) if row['status'].startswith('validated') else {}
        result.append(dict(base_id=row['base_id'],name=row['name'],status=row['status'],
            reason=row.get('reason'),**counts,visual_approved=False,hardware_profiled=False))
    write(work/'native-validation-summary.json',result)
    print(dict(selected=len(rows),validated=sum(r['status'].startswith('validated') for r in result),
               visual_approved=False,packaged=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True);p.add_argument('--trial',action='append',required=True)
    p.add_argument('--work-dir',required=True);p.add_argument('--workers',type=int,choices=(1,2),default=2)
    a=p.parse_args();validate(read(a.config),a.trial,a.work_dir,a.workers)

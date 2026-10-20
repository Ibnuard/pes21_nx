"""Resume bounded hair reduction after exact source-sentinel cleanup."""
from contextlib import contextmanager
from pathlib import Path
import json
import numpy as np

import realface_budget_experiment as trial
from realface_batch import key_of
from realface_batch_inventory import read,write
from realface_league_balanced import READY,assert_owner,validate_head
from realface_league_finalize import recovery_allocation,status
from realface_league_mobile import PreparationProcess
from realface_pipeline import sha

HERE=Path(__file__).resolve().parent
CODE=('realface_league_outlier_repair.py','realface_zero_area_policy.py',
      'blender_realface_source_cleanup_worker.py')


@contextmanager
def cleanup_recipe(error,weight):
    allocation,code=trial.effective_allocation,trial.recipe_code
    def effective(config,base):
        return dict(allocation(config,base),cleanup_exact_zero_area_outliers=True,
                    hair_error_cm=error,hair_uv_weight=weight)
    def recipe(budget):return dict(code(budget),**{n:sha(HERE/n) for n in CODE})
    try:
        trial.effective_allocation,trial.recipe_code=effective,recipe
        yield
    finally:
        trial.effective_allocation,trial.recipe_code=allocation,code


def repair_outliers(config,prepared,verified,catalogue):
    work=Path(config['work_dir']);report=work/'final-outlier-repair-report.json'
    records=read(report) if report.exists() else {}
    for base,old in list(sorted(prepared.items())):
        if old['status'] in READY:continue
        audit=work/'remaining-hold-audit'/str(base)/'source-geometry.npz'
        if not audit.is_file():continue
        with np.load(audit) as stored:
            if not (np.abs(stored['positions'])>1000).any():continue
        source=catalogue[base];assert_owner(old,source)
        worker=PreparationProcess(config['blender'],HERE/'blender_realface_source_cleanup_worker.py')
        try:
            for error,weight in ((.45,.5),(.65,.25),(.9,.1)):
                for cap,skin in ((5000,3000),(7000,3000),(7000,2600)):
                    spec=dict(error=error,weight=weight,cap=cap,skin=skin,
                              code={n:sha(HERE/n) for n in CODE},source_key=old['cache_key'])
                    key=str(base)+'-'+key_of(spec)[:16]
                    if key in records:
                        result=records[key]['result']
                        if result['status'] not in READY:continue
                    else:
                        status(work,'final_outlier_repair',prepared,verified,current_base_id=base,current_name=old['name'])
                        job=dict(config,experimental_head_cap=cap,experimental_hair_policy='cards',
                            experimental_allocations={str(base):recovery_allocation(cap,skin,True)})
                        with cleanup_recipe(error,weight):result=trial.prepare_one(job,source,worker)
                        records[key]=dict(spec=spec,result=result);write(report,records)
                    print(json.dumps(dict(base_id=base,phase='final_outlier_repair',status=result['status'],
                        triangles=result.get('triangles'),reason=result.get('reason'))),flush=True)
                    if result['status'] in READY:
                        result['source_cleanup']=read(Path(result['folder'])/'source-cleanup-proof.json')
                        result['facial_hair_policy']=dict(locked=True,reason='Conservative original-card lock after sentinel repair')
                        if result['triangles']>5000:
                            result['league_exception']=dict(reason='Bounded reduction after source-sentinel repair',triangles=result['triangles'])
                        validate_head(result);prepared[base]=result
                        write(work/'prepare-report.json',sorted(prepared.values(),key=lambda r:r['base_id']))
                        break
                    if 'not proven zero-area' in result.get('reason',''):break
                if prepared[base]['status'] in READY:break
                if 'not proven zero-area' in result.get('reason',''):break
        finally:worker.close()

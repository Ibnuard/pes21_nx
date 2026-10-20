"""Serial source-proof recovery for invisible hair slots; no visible hair removed."""
from contextlib import contextmanager
from pathlib import Path
import json

import realface_budget_experiment as trial
from realface_batch_inventory import read,write
from realface_batch import key_of
from realface_league_balanced import READY,assert_owner,validate_head
from realface_league_finalize import recovery_allocation,status
from realface_league_mobile import PreparationProcess
from realface_pipeline import sha

HERE=Path(__file__).resolve().parent
CODE=('realface_league_slot_repair.py','realface_invisible_slot_policy.py',
      'blender_realface_invisible_budget_worker.py','realface_source_empty_part.py')


@contextmanager
def slot_recipe(source_proof=None):
    allocation,code=trial.effective_allocation,trial.recipe_code
    def effective(config,base):
        result=dict(allocation(config,base),verified_invisible_source_slot=True)
        if source_proof:result['source_authored_empty_part']=source_proof
        return result
    def recipe(budget):
        return dict(code(budget),**{n:sha(HERE/n) for n in CODE})
    try:
        trial.effective_allocation,trial.recipe_code=effective,recipe
        yield
    finally:
        trial.effective_allocation,trial.recipe_code=allocation,code


def repair_slots(config,prepared,verified,catalogue):
    work=Path(config['work_dir']); report=work/'final-slot-repair-report.json'
    records=read(report) if report.exists() else {}
    for base,old in list(sorted(prepared.items())):
        if old['status'] in READY or not old.get('reason','').startswith(('No visible hair pixels','Empty/nonfinite reduced surface')):
            continue
        source=catalogue[base];assert_owner(old,source)
        from realface_source_empty_part import source_part_proof
        source_proof=source_part_proof(config,source)
        worker=PreparationProcess(config['blender'],HERE/'blender_realface_invisible_budget_worker.py')
        try:
            for cap in (5000,7000):
                attempt=str(base)+'-'+str(cap)+'-'+key_of({n:sha(HERE/n) for n in CODE})[:16]
                if attempt in records:
                    cached=records[attempt]['result']
                    if cached['status'] not in READY:continue
                    result=cached
                else:
                    status(work,'final_slot_repair',prepared,verified,current_base_id=base,current_name=old['name'])
                    job=dict(config,experimental_head_cap=cap,experimental_hair_policy='cards',
                             experimental_allocations={str(base):recovery_allocation(cap,3000,False)})
                    with slot_recipe(source_proof):result=trial.prepare_one(job,source,worker)
                    records[attempt]=dict(source_cache_key=old['cache_key'],result=result)
                    write(report,records)
                print(json.dumps(dict(base_id=base,phase='final_slot_repair',status=result['status'],
                                      triangles=result.get('triangles'),reason=result.get('reason'))),flush=True)
                if result['status'] in READY:
                    result['source_slot_repair']=dict(previous_cache_key=old['cache_key'],
                        proof=read(Path(result['folder'])/'invisible-source-slot-proof.json'))
                    result['facial_hair_policy']=old.get('facial_hair_policy',{})
                    if result['triangles']>5000:
                        result['league_exception']=dict(reason='Source-proven invisible slot recovery',triangles=result['triangles'])
                    validate_head(result);prepared[base]=result
                    write(work/'prepare-report.json',sorted(prepared.values(),key=lambda r:r['base_id']))
                    break
                if ('Only classified hair' in result.get('reason','') or
                        'unproven triangles' in result.get('reason','')):
                    break # Budget changes cannot establish source invisibility.
        finally:
            worker.close()

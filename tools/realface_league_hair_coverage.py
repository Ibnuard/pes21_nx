"""Cache a whole-league diagnostic of visible scalp gaps after simplification."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import threading
from realface_batch_inventory import read,write
from realface_batch import key_of,valid_prepared_cache
from realface_league_mobile import PreparationProcess
from realface_pipeline import sha

HERE=Path(__file__).resolve().parent


def run(config,workers=2,selected=None):
    work=Path(config['work_dir']);out=work/'hair-visibility'
    code={name:sha(HERE/name) for name in ('realface_hair_coverage.py',
        'blender_realface_hair_coverage_worker.py','blender_realface_mobile.py',
        'blender_realface_hair_clearance.py','realface_fast_raster.py')}
    code['raster_library']=sha(config['fast_raster'])
    rows=[r for r in read(work/'prepare-report.json') if r['status'] in ('prepared','prepared_cached') and not r.get('reuse_cooked')]
    expected={r['base_id']:key_of(dict(prepared=r['cache_key'],code=code)) for r in rows}
    if selected and set(selected)-expected.keys():raise ValueError('Hair audit requires prepared, non-inherited players')
    retained=[]
    if selected:
        # Keep earlier matching diagnostics when auditing newly recovered heads.
        # This is an incremental report, not a fresh asset rehash of those rows.
        report=out/'report.json'
        if report.exists():
            retained=[r for r in read(report) if r.get('audit_key')==expected.get(r['base_id']) and r['base_id'] not in selected]
        rows=[r for r in rows if r['base_id'] in selected]
    local=threading.local();processes=[];lock=threading.Lock();results=[]
    def one(row):
        if not valid_prepared_cache(Path(row['folder']),row['cache_key']):raise ValueError('Prepared audit input changed')
        key=key_of(dict(prepared=row['cache_key'],code=code));folder=out/(str(row['base_id'])+'-'+key[:16])
        proof=folder/'coverage.json'
        if not proof.exists():
            if not hasattr(local,'worker'):
                local.worker=PreparationProcess(config['blender'],script=HERE/'blender_realface_hair_coverage_worker.py')
                with lock:processes.append(local.worker)
            write(folder/'job.json',dict(folder=str(folder),row=row))
            try:local.worker(folder/'job.json',folder/'audit.log')
            except Exception as error:
                return dict(base_id=row['base_id'],name=row['name'],cache_key=row['cache_key'],status='audit_failed',reason=str(error))
        result=read(proof)
        if result.get('cache_key')!=row['cache_key']:raise ValueError('Hair audit belongs to another prepared mesh')
        return dict(result,name=row['name'],status='audited',audit_key=key)
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for index,future in enumerate(as_completed([pool.submit(one,r) for r in rows]),1):
                result=future.result();results.append(result)
                write(out/'report.json',sorted(retained+results,key=lambda r:r['base_id']))
                if index%25==0 or index==len(rows):print(dict(audited=index,total=len(rows)),flush=True)
    finally:
        for process in processes:process.close()
    return retained+results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True)
    parser.add_argument('--workers',type=int,choices=(1,2),default=2)
    parser.add_argument('--player',action='append',type=int,help='Incremental audit of newly prepared players')
    args=parser.parse_args()
    run(read(args.config),args.workers,set(args.player) if args.player else None)

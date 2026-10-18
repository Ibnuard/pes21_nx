"""Rebuild stair surfaces from owned glTFs within the reviewed native budget.

Config extends a local stadium cook configuration with raw_profiles (per key),
native_pitch, polygon_modules, Blender, Node and meshoptimizer paths. Never
reuses the already damaged reduced surface as the reconstruction source.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from stadium_atlas import prepare
from realface_pipeline import sha


def run(config,manifest,work,keys):
    root=Path(__file__).resolve().parents[1]
    work=Path(work).resolve()
    if not work.is_relative_to(root/'local-debug') or work==root/'local-debug':
        raise ValueError('Use a dedicated ignored local-debug output directory')
    work.mkdir(parents=True,exist_ok=True)
    rows=json.loads(Path(manifest).read_text())['stadiums']
    if not set(keys)<=set(r['key'] for r in rows):raise ValueError('Unreviewed stadium key')
    reports=[]
    for row in rows:
        key=row['key']
        if key not in keys:continue
        source=Path(config['raw_profiles'][key]).resolve(strict=True)
        raw=work/'raw/prepared'/key;optimized=work/'optimized/prepared'/key;final=work/'prepared'/key
        profile=json.loads(source.read_text())
        paths=[source,source.parent/'conversion.local.json',Path(profile['fbx']).with_suffix('.blend'),
               *source.parent.glob('*.gltf'),*source.parent.glob('*.bin')]
        paths += [Path(p) for p in profile.get('texture_files',{}).values() if Path(p).is_file()]
        native=Path(config['native_pitch']);paths.append(native)
        paths += [native.parent/b['uri'] for b in json.loads(native.read_text())['buffers']]
        inputs={str(p):sha(p) for p in paths}
        for name in ('stadium_shell_fbx.py','blender_stadium_reduction.py','meshopt_stadium_reduce.mjs',
                     'stadium_atlas.py','optimize_stadium_shell.py','repair_stadium_apron.py',
                     'stadium_apron_geometry.py','stadium_floor_underlay.py'):
            path=root/'tools'/name;inputs[str(path)]=sha(path)
        inputs[config['meshoptimizer']]=sha(config['meshoptimizer'])
        contract=hashlib.sha256(json.dumps(dict(inputs=inputs,row=row),sort_keys=True).encode()).hexdigest()
        stamp=final/'surface-verification.json'
        if stamp.exists():
            proof=json.loads(stamp.read_text())
            if proof['contract']!=contract or sha(final/(key+'Shell.fbx'))!=proof['fbx_sha256']:
                raise ValueError('Existing surface candidate changed; choose a fresh work directory')
            reports.append(proof);continue
        def blender(name,args,phase):
            with (work/(key+'-'+phase+'.log')).open('w') as log:
                subprocess.run([config['blender'],'--background','--threads','2','--python-exit-code','1',
                    '--python',str(root/'tools'/name),'--',*map(str,args)],stdout=log,stderr=subprocess.STDOUT,check=True)
        print('SURFACES',key,flush=True)
        underlays=[]
        for material in row.get('floor_underlay_materials',[]):underlays+=['--floor-underlay-material',material]
        blender('stadium_shell_fbx.py',[source.parent,'--output',raw,'--target-triangles',row['triangle_budget'],
            '--crowd-profile',source,'--node',config['node'],'--meshoptimizer',config['meshoptimizer'],
            '--polygon-python',sys.executable,'--polygon-modules',config['polygon_modules'],*underlays],'rebuild')
        optimized.mkdir(parents=True,exist_ok=True);prepare(raw/'fbx.local.json',optimized/'textures')
        blender('optimize_stadium_shell.py',['--profile',raw/'fbx.local.json','--output',optimized,
            '--triangles',row['triangle_budget']]+(['--vertex-camera-cull'] if row['vertex_camera_cull'] else []),'atlas')
        args=['--profile',optimized/'fbx.local.json','--native-pitch',config['native_pitch'],'--output',final,
            '--polygon-python',sys.executable,'--polygon-modules',config['polygon_modules'],
            '--floor-min-height','-0.25','--omit-native-floor-decals']
        for material in row.get('raised_floor_materials',[]):args+=['--raise-floor-material',material]
        for item in row.get('raised_floor_ranges',[]):
            args+=['--raise-floor-range',item['material'],str(item['min_m']),str(item['max_m'])]
        blender('repair_stadium_apron.py',args,'apron')
        profile=json.loads((final/'fbx.local.json').read_text())
        total=profile['shell_triangles']['reduced']+profile['crowd']['triangles']
        if (total>row['maximum_total_triangles'] or
                profile['crowd']['triangles']!=row['preserved_crowd_triangles']):
            raise ValueError('Stadium/crowd budget changed: '+key)
        proof=dict(key=key,contract=contract,inputs=inputs,triangles=total,
            fbx_sha256=sha(final/(key+'Shell.fbx')),hardware_tested=False)
        stamp.write_text(json.dumps(proof,indent=2)+'\n');reports.append(proof)
        print('SURFACES_PREPARED',key,total,flush=True)
    (work/'surface-report.json').write_text(json.dumps(reports,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--manifest',type=Path,default=Path('data/stadiums/fl26_selected_v34.json'))
    p.add_argument('--keys',nargs='+',required=True)
    a=p.parse_args();run(json.loads(a.config.read_text()),a.manifest,a.work,a.keys)

"""Prepare the reviewed FL26 addon batch from owned, local stadium folders.

Config JSON: stadium_root, blender, fmdl_parser, texture_parser, crowd_atlas.
Existing profiles are preserved unless --rebuild is supplied. Conversion never
copies OBBs or edits an installed runtime. numpy/scipy are needed for roof fit.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from convert_fl26_stadium import convert
from stadium_assets import asset_key, discover


def main():
    root = Path(__file__).resolve().parents[1]; tools=root/'tools'
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True,type=Path)
    p.add_argument('--work',required=True,type=Path)
    p.add_argument('--manifest',type=Path,default=root/'data/stadiums/fl26_addons_v25.json')
    p.add_argument('--keys',nargs='+')
    p.add_argument('--rebuild',action='store_true')
    a=p.parse_args();cfg=json.loads(a.config.read_text())
    rows=json.loads(a.manifest.read_text())['stadiums']
    requested={asset_key(v) for v in a.keys} if a.keys else {row['key'] for row in rows}
    if requested - {row['key'] for row in rows}:raise ValueError('Keys missing from reviewed manifest')
    owned={r['key']:r for r in discover(cfg['stadium_root']) if r.get('status')=='available'}
    results=[];a.work.mkdir(parents=True,exist_ok=True)
    for row in rows:
        key=row['key']
        if key not in requested:continue
        src=owned.get(key)
        if not src or src['source_id']!=row['source_id']:raise ValueError('Owned shell/audience unavailable: '+key)
        target=a.work.resolve()/'prepared'/key
        if (target/'fbx.local.json').exists() and not a.rebuild:
            raise FileExistsError('Prepared output exists; use a fresh work directory or --rebuild: '+key)
        print('PREPARE',key,flush=True)
        convert(Path(src['source']),target,Path(cfg['fmdl_parser']),Path(cfg['texture_parser']),
                True,row['source_id'],key,row['shell_parts'],True)
        def blender(script,arguments,log_name):
            with (target/log_name).open('w') as log:
                subprocess.run([cfg['blender'],'--background','--python-exit-code','1','--python',
                    str(tools/script),'--',*arguments],check=True,stdout=log,stderr=subprocess.STDOUT)
        blender('stadium_shell_fbx.py',[str(target),'--target-triangles',str(row['triangle_budget']),
            '--crowd-area',str(target/'audiarea.bin'),'--crowd-atlas',cfg['crowd_atlas'],'--crowd-flipbook'],'blender.log')
        blend=target/(key+'Shell.blend')
        blender('audit_stadium_roof.py',['--blend',str(blend),'--output',str(target/'roof.local.json'),
            '--min-height',str(row['min_roof_height_m'])],'roof.log')
        subprocess.run([sys.executable,str(tools/'fit_stadium_roof.py'),str(target/'roof.local.json')],check=True)
        blender('audit_stadium_camera.py',['--blend',str(blend),'--mesh',key+'Shell',
            '--output',str(target/'camera.local.json')],'camera.log')
        results.append(dict(key=key,status='prepared',profile=str(target/'fbx.local.json')))
        (a.work/'prepare-report.json').write_text(json.dumps(results,indent=2)+'\n')
    print('Review the roof fit and camera reports before cooking.',flush=True)


if __name__=='__main__':
    main()

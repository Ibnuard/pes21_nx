"""Hash-pinned, four-angle review of held native-style hair candidates."""
import argparse
from pathlib import Path

from PIL import Image,ImageDraw
from realface_batch import command,valid_cache
from realface_batch_inventory import read,write
from realface_pipeline import sha

HERE=Path(__file__).resolve().parent
VIEWS={'front':(0,90,0),'left':(-70,70,12),'right':(70,70,12),'above':(0,75,55)}


def preview(config,work):
    work=Path(work);rows=[r for r in read(work/'trial-report.json') if r['status']!='held_conversion']
    if not rows:raise ValueError('No exported hair candidates to preview')
    out=work/'review';out.mkdir(exist_ok=True)
    targets=[];pending=[]
    for row in rows:
        folder=Path(row['folder'])
        if not valid_cache(folder,row['cache_key']):raise ValueError('Held hair candidate bytes changed')
        for view,offset in VIEWS.items():
            image=out/(str(row['base_id'])+'-'+view+'.png');stamp=image.with_suffix('.json')
            proof=dict(candidate_key=row['cache_key'],renderer_sha256=sha(HERE/'blender_preview_realface.py'),
                view=view,mesh_stage='prepared_fbx',texture_stage='prepared_png',hardware_capture=False)
            if image.exists() and stamp.exists() and read(stamp)==dict(proof,image_sha256=sha(image)):continue
            targets.append(dict(recipe=dict(ue=read(folder/'ue-profile.json'),native_rig=config['native_rig'],
                cooked_rig=config['cooked_rig'],view_offset=offset,samples=8),output=str(image.resolve())))
            pending.append((stamp,proof,image))
    write(out/'targets.json',targets)
    if targets:
        command([config['blender'],'--background','--threads','2','--python-exit-code','1','--python',
            HERE/'blender_preview_realface.py','--',out/'targets.json'],out/'render.log')
        for stamp,proof,image in pending:write(stamp,dict(proof,image_sha256=sha(image)))
    # A bounded trial should be reviewed as full-size PNGs as well as a sheet.
    for start in range(0,len(rows),6):
        page=rows[start:start+6];sheet=Image.new('RGB',(1280,len(page)*344+26),'#30343a');draw=ImageDraw.Draw(sheet)
        draw.text((8,7),'HELD NATIVE-STYLE CANDIDATE - prepared mesh/textures; no device timing',fill='white')
        for i,row in enumerate(page):
            for j,view in enumerate(VIEWS):
                image=Image.open(out/(str(row['base_id'])+'-'+view+'.png'));image.thumbnail((320,320))
                sheet.paste(image,(j*320,26+i*344+20))
                label=str(row['base_id'])+' '+row['name'][:14]+' '+view+' / '+str(row['triangles'])
                if row['status'].startswith('held_'):label+=' HELD'
                draw.text((j*320+5,26+i*344+4),label,fill='white')
        sheet.save(out/('sheet-%02d.png'%(start//6+1)))
    print(dict(review=str(out),players=len(rows),visual_approval=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--work-dir',required=True)
    a=p.parse_args();preview(read(a.config),a.work_dir)

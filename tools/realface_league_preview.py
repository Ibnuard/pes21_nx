"""Review sheets for league heads; explicitly distinguish prepared/cooked evidence."""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from cooked_texture import Texture
from realface_batch import command,valid_cache,valid_prepared_cache
from realface_batch_inventory import read,write
from realface_pipeline import sha

HERE=Path(__file__).resolve().parent
VIEWS={'front':(0,90,0),'left':(-70,70,12),'right':(70,70,12),'above':(0,75,55)}


def preview(config,stage='cooked',selected=None,limit=48,views=('front',),output=None):
    if not views or len(set(views))!=len(views) or any(v not in VIEWS for v in views):
        raise ValueError('Select distinct supported review views')
    work=Path(config['work_dir']);report=work/('verify-report.json' if stage=='cooked' else 'prepare-report.json')
    rows=[r for r in read(report) if r['status'] in ('prepared','prepared_cached','validated','validated_cached')]
    rows=[r for r in rows if not selected or r['base_id'] in selected]
    if not selected:
        # Spread deterministic samples over the full identity range; always
        # include repaired exceptions and the worst retained coverage scores.
        critical=[r for r in rows if r['budgets'].get('eye_recovery') or r['budgets'].get('skin_uv_weight') in (1.,3.)]
        ordinary=[r for r in rows if r not in critical]
        remaining=max(0,limit-len(critical));step=max(1,len(ordinary)//max(remaining,1))
        rows=critical+ordinary[::step][:remaining]
    output=(Path(output) if output is not None else work/(stage+'-review')).resolve()
    output.mkdir(parents=True,exist_ok=True);targets=[];pending_proofs=[]
    for row in rows:
        prepared=Path(row['folder']);native=str(row['native_player_id']);base=str(row['base_id'])
        if not valid_prepared_cache(prepared,row['cache_key']):raise ValueError('Prepared preview cache changed')
        recipe=dict(folder=row['folder'],native_rig=config['native_rig'],cooked_rig=config['cooked_rig'])
        if stage=='cooked':
            cooked=Path(row['cooked_folder'])
            if not valid_cache(cooked,row['cooked_cache_key']):raise ValueError('Cooked preview cache changed')
            textures={}
            for role,suffix in (('skin','_face_tablet'),('hair','_hair_parts_color_tablet')):
                path=output/(base+'-'+role+'.png')
                Texture(cooked/'assets'/(native+suffix+'.uexp')).decode().save(path)
                textures[role]=str(path)
            recipe['texture_overrides']=textures
        for view in views:
            image=output/(base+'-'+view+'.png');proof=image.with_suffix('.json')
            provenance=dict(prepared_key=row['cache_key'],cooked_key=row.get('cooked_cache_key') if stage=='cooked' else None,
                            renderer_sha256=sha(HERE/'blender_preview_realface.py'),view=view)
            previous=read(proof) if proof.exists() else {}
            expected=dict(provenance,image_sha256=sha(image)) if image.exists() else None
            if expected is None or previous!=expected:
                targets.append(dict(recipe=dict(recipe,view_offset=VIEWS[view]),output=str(image)))
                pending_proofs.append((proof,provenance,image))
    write(output/'targets.json',targets)
    if targets:
        command([config['blender'],'--background','--threads','2','--python-exit-code','1',
                 '--python',HERE/'blender_preview_realface.py','--',output/'targets.json'],output/'render.log')
        # A failed/interrupted render must never bless an older PNG with a new
        # prepared key. Only record provenance after successful rendering.
        for proof,provenance,image in pending_proofs:
            write(proof,dict(provenance,image_sha256=sha(image)))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)
    sheets=[]
    columns=max(1,8//len(views));page_size=columns*6;cell_width=150*len(views)
    for start in range(0,len(rows),page_size):
        page=rows[start:start+page_size];sheet=Image.new('RGB',(1200,((len(page)+columns-1)//columns)*202+40),'#182031')
        label='PREPARED MESH + COOKED TEXTURES' if stage=='cooked' else 'PREPARED MESH'
        draw=ImageDraw.Draw(sheet);draw.text((12,10),label+' — offline, not a device capture',font=font,fill='white')
        for i,row in enumerate(page):
            x=(i%columns)*cell_width;y=40+(i//columns)*202
            for j,view in enumerate(views):
                pic=Image.open(output/(str(row['base_id'])+'-'+view+'.png'));pic.thumbnail((150,150))
                sheet.paste(pic,(x+j*150,y));draw.text((x+j*150+3,y+150),view,font=font,fill='#8CD5F7')
            draw.text((x+3,y+167),row['name'][:max(21,len(views)*21)],font=font,fill='white')
            draw.text((x+3,y+182),str(row['base_id']),font=font,fill='#8CD5F7')
        path=output/('sheet-%02d.png'%(start//page_size+1));sheet.save(path);sheets.append(str(path))
    write(output/'PROVENANCE.json',dict(stage=stage,mesh='prepared_fbx',texture_stage=stage,views=views,
        hardware_capture=False,players=[dict(base_id=r['base_id'],name=r['name']) for r in rows],sheets=sheets))
    print(dict(previews=str(output),players=len(rows),sheets=sheets),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True)
    parser.add_argument('--stage',choices=('prepared','cooked'),default='cooked')
    parser.add_argument('--output',type=Path,help='Separate review folder, for example for a full-cohort sheet')
    parser.add_argument('--player',action='append',type=int,default=[]);parser.add_argument('--limit',type=int,default=48)
    parser.add_argument('--views',nargs='+',choices=tuple(VIEWS),default=['front'])
    args=parser.parse_args();preview(read(args.config),args.stage,set(args.player),args.limit,args.views,args.output)

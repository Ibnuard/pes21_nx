"""Rasterize the actual corner HUD C emitter with public FootballNX font data.

Synthetic state and host draw recorder only; not a Switch/game screenshot.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from PIL import Image
import preview_frontdoor as frontend
import preview_cup as shared

ROOT=shared.ROOT
DRIVER=r'''
static void capture(const char *name,unsigned mode,int split,unsigned layout) {
  MasterLeagueRender ui={0};static GLfloat vertices[4096*24+8];int quads=0;
  for(int i=4096*24;i<4096*24+8;i++)vertices[i]=12345.f;
  FnxCornerView v={.available=1,.open=1,.mode=mode,.short_allowed=mode!=3,.current=0};
  v.layout=layout;
  const FnxCornerView before=v;
  corner_tactics_emit(&ui,0,split?2:1,&v,1.f,vertices,&quads);
  assert(ui.draws[0].round.radius==ui.draws[1].round.radius);
  assert(ui.draws[2].round.radius==0 && ui.draws[3].round.radius==0);
  if(split){v.mode=3;v.short_allowed=0;v.current=3;if(layout)v.layout=2;corner_tactics_emit(&ui,1,2,&v,1.f,vertices,&quads);}
  else assert(!memcmp(&v,&before,sizeof(v)));
  assert(quads<1024 && ui.draw_count<80);
  for(int i=4096*24;i<4096*24+8;i++)assert(vertices[i]==12345.f);
  for(int i=0;i<quads*24;i+=4){assert(isfinite(vertices[i]) && isfinite(vertices[i+1]));
    assert(fabsf(vertices[i])<=1.002f && fabsf(vertices[i+1])<=1.002f);
    if(!split)assert(vertices[i]>=.455f); /* Compact one-player right edge. */}
  /* Both owner panels have one bottom baseline, with equal edge inset. */
  if(split){
    MasterLeagueRender a={0},b={0};GLfloat av[4096*24],bv[4096*24];int aq=0,bq=0;
    corner_tactics_emit(&a,0,2,&v,1.f,av,&aq);
    corner_tactics_emit(&b,1,2,&v,1.f,bv,&bq);
    assert(aq==bq);
    for(int i=0;i<aq*24;i+=4){
      assert(fabsf(av[i+1]-bv[i+1])<.00001f);
      /* Font glyphs snap to pixel centres; the panel's first quad is exact. */
      assert(fabsf((bv[i]-av[i])-1.432f)<(i<24 ? .00001f : .004f));
    }
  }
  char path[80];snprintf(path,sizeof(path),"%s.json",name);
  frame=fopen(path,"w");assert(frame);fprintf(frame,"[");draw_count=0;
  memset(uniforms,0,sizeof(uniforms));bound_texture=0;
  active_quads=quads;active_vertices=vertices;master_league_draw(&ui);
  fprintf(frame,"]");fclose(frame);printf("%s: %d quads, %u draws\n",name,quads,ui.draw_count);
}
int main(void) {
  initialize_gl();FILE *f=fopen("font.pgm","wb");assert(f);
  fprintf(f,"P5\n%d %d\n255\n",EFOOTBALL_FONT_ATLAS_W,EFOOTBALL_FONT_ATLAS_H);
  fwrite(efootball_font_atlas_alpha,1,sizeof(efootball_font_atlas_alpha),f);fclose(f);
  capture("attack",1,0,0);capture("short",2,0,0);capture("defence",3,0,0);capture("two-player",1,1,0);
  capture("horizontal-left",1,0,1);capture("horizontal-right",2,0,2);capture("horizontal-two-player",1,1,1);
  {MasterLeagueRender ui={0};GLfloat vertices[24];int quads=0;
   FnxCornerView closed={.available=1,.open=0};
   corner_tactics_emit(&ui,0,1,&closed,1.f,vertices,&quads);
   assert(!quads && !ui.draw_count); /* Closed entry belongs to the helper list. */}
  return 0;
}
'''

def build_driver():
    base=frontend.build_driver((ROOT/'source/overlay.c').read_text()).split('static FrontdoorView view;',1)[0]
    return base+'\n#include "corner_tactics.h"\n'+(ROOT/'source/corner_tactics_overlay.inc').read_text()+'\n'+DRIVER

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'local-debug/corner-tactics-v69/preview')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    compiler=shutil.which('gcc') or shutil.which('clang')
    if not compiler:raise SystemExit('Host C compiler required')
    with tempfile.TemporaryDirectory(prefix='fnx-corner-preview-') as temp:
        temp=Path(temp);source=temp/'preview.c';source.write_text(build_driver())
        (temp/'ue4_hooks.h').write_text((ROOT/'source/ue4_hooks.h').read_text().replace(
            '#include "so_util.h"','typedef struct so_module so_module;'))
        command=[compiler,'-std=c11','-O1','-pthread','-I',temp.as_posix(),'-I',
            (ROOT/'source').as_posix(),source.as_posix(),(ROOT/'source/corner_tactics.c').as_posix(),
            '-lm','-o',(temp/'preview.exe').as_posix()]
        result=subprocess.run(command,capture_output=True,text=True)
        if result.returncode:raise SystemExit(result.stderr)
        result=subprocess.run([str(temp/'preview.exe')],cwd=temp,capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stderr)
        assets={2:Image.open(temp/'font.pgm').convert('RGB'),20:Image.open(ROOT/'data/main_menu_button_a.bin').convert('RGBA'),21:Image.open(ROOT/'data/main_menu_button_b.bin').convert('RGBA')}
        import re
        header=(ROOT/'source/switch_button_assets.h').read_text()
        for i,(name,_) in enumerate(re.findall(r'X\((\w+), "([^"]+)"\)',header)):
            if name in ('b_dark','x_dark','up','down','left','right','sl','sr','x','y'):
                assets[22+i]=Image.open(ROOT/'data'/f'switch_button_{name}.bin').convert('RGBA')
        for p in temp.glob('*.json'):
            shared.rasterize(json.loads(p.read_text()),assets).save(output/p.with_suffix('.png').name)
            shutil.copy2(p,output/p.name)
        names=['source/corner_tactics_overlay.inc','source/corner_tactics.c','source/efootball_font_atlas.h',
            'source/switch_button_assets.h','data/switch_button_b_dark.bin','data/switch_button_x_dark.bin']
        proof={'scope':'Actual C geometry/font/draw recorder; synthetic state; no device acceptance',
            'bounds_and_immutable_snapshot_checks':True,'results':result.stdout.splitlines(),
            'sources':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}}
        (output/'VERIFICATION.json').write_text(json.dumps(proof,indent=2)+'\n')
        print(result.stdout,end='');print(output)

if __name__=='__main__':main()

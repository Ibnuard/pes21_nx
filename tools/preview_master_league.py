"""Render the actual career C layout/font vertices on the host for visual QA.

This software preview is not a Switch capture. Uses synthetic career state,
the production renderer's geometry, shared bitmap font and public badge atlas.
No native payload is read. Output stays under ignored local-debug.
"""
from pathlib import Path
import json
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from test_gameplan_editor import function, struct


def main(output=None):
    output=Path(output) if output else ROOT/'local-debug/master-league-v2/previews'
    output.mkdir(parents=True,exist_ok=True)
    overlay=(ROOT/'source/overlay.c').read_text(encoding='utf-8')
    renderer=(ROOT/'source/master_league_overlay.inc').read_text(encoding='utf-8').split('static void master_league_draw')[0]
    fixture=(ROOT/'tests/test_master_league_frontend.c').read_text().split('int main(void)')[0]
    prefix='''
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "efootball_font_atlas.h"
#include "badge_atlas.h"
typedef float GLfloat;
typedef unsigned int GLuint;
static int screen_width=1280,screen_height=720;
static struct {GLuint badge_tex,master_league_background_tex,master_league_pearl_tex,master_league_cards_tex;int loc_color;} gl={2,4,5,6,0};
static float rgba[4];
static void glUniform4f(int loc,float r,float g,float b,float a){(void)loc;rgba[0]=r;rgba[1]=g;rgba[2]=b;rgba[3]=a;}
static uint64_t ticks=1000000000u;
static uint64_t armGetSystemTick(void){return ticks;}
static uint64_t armTicksToNs(uint64_t t){return t;}
static GLuint gameplan_portrait_texture(uint32_t id){(void)id;return 0;}
enum { FNX_BUTTON_FRAME, FNX_BUTTON_FILL, FNX_BUTTON_GLOSS, FNX_BUTTON_TEXT };
'''
    funcs=['emit_image_rect_uv','emit_image_rect','emit_round_rect_quad',
           'efootball_raster_level','efootball_raster_height','efootball_raster_width',
           'efootball_raster_advances','measure_efootball_line_mode','emit_efootball_line_mode',
           'fnx_button_color','emit_badge']
    driver=r'''
static void dump(const char *name) {
  static GLfloat vertices[16000*24];
  MasterLeagueRender ui;int quads=0;
  master_league_emit(&ui,vertices,&quads);ticks+=200000000u;quads=0;
  master_league_emit(&ui,vertices,&quads);
  assert(ui.draw_count<224u && quads<4096);
  if(ui.shoulders) {
    ml_ui_image(&ui,13,0,.066f-.035f*.5625f*.5f,ui.shoulder_y-.0175f,.035f*.5625f,.035f,vertices,&quads);
    ml_ui_image(&ui,14,0,.934f-.035f*.5625f*.5f,ui.shoulder_y-.0175f,.035f*.5625f,.035f,vertices,&quads);
  }
  for(uint32_t i=0;i<ui.view.helper_count;i++) {
    const char *key=ui.view.helper_key[i];GLuint texture=10;
    if(!strcmp(key,"B"))texture=11;else if(!strcmp(key,"X"))texture=12;
    else if(!strcmp(key,"L"))texture=13;else if(!strcmp(key,"R"))texture=14;
    else if(!strcmp(key,"SL"))texture=15;else if(!strcmp(key,"SR"))texture=16;
    ml_ui_image(&ui,texture,0,ui.helper_centers[i]-.030f*.5625f*.5f,.943f,.030f*.5625f,.030f,vertices,&quads);
  }
  char path[80];snprintf(path,sizeof(path),"%s.json",name);FILE *out=fopen(path,"w");
  fprintf(out,"[");
  for(uint32_t i=0;i<ui.draw_count;i++) {
    MlDraw *d=&ui.draws[i];
    if(d->theme>=0){fnx_button_color(d->theme,d->selected,d->enabled);memcpy(d->color,rgba,sizeof(rgba));}
    fprintf(out,"%s{\"kind\":%d,\"texture\":%u,\"radius\":%g,\"color\":[%g,%g,%g,%g],\"vertices\":[",i ? "," : "",d->kind,d->texture,d->round.radius,d->color[0],d->color[1],d->color[2],d->color[3]);
    for(int j=0;j<d->count*24;j++)fprintf(out,"%s%g",j ? "," : "",vertices[d->first*24+j]);
    fprintf(out,"]}");
  }
  fprintf(out,"]");fclose(out);
}
int main(void) {
  FILE *font=fopen("font.pgm","wb");fprintf(font,"P5\n%d %d\n255\n",EFOOTBALL_FONT_ATLAS_W,EFOOTBALL_FONT_ATLAS_H);
  fwrite(efootball_font_atlas_alpha,1,sizeof(efootball_font_atlas_alpha),font);fclose(font);
  ml_frontend_open();dump("landing");press(A);dump("settings");
  press(DOWN);press(RIGHT); /* opening fixture, rather than the public pool's bye */
  for(int i=0;i<4;i++)press(DOWN);press(A);
  ml_frontend_name_result("Andro NX");press(DOWN);press(A);press(A);dump("manager");
  press(DOWN);press(A);press(A);assert(view().page==ML_PAGE_HUB);dump("home");
  press(R);dump("squad-section");press(R);dump("office-section");press(R);dump("competitions-section");
  press(LEFT);press(LEFT);press(LEFT);press(LEFT);press(LEFT);press(LEFT);
  press(UP);press(RIGHT);press(A);assert(view().page==ML_PAGE_NEWS);dump("club-feed");return 0;
}
'''
    # Raw string above intentionally expresses the C escapes verbatim.
    source='\n'.join([prefix,struct(overlay,'RoundedRectStyle'),
        *[function(overlay,n) for n in funcs],fixture,renderer,driver])
    # JSON quotes/newlines in C string literals (not command interpolation).
    source=source.replace('\\\\\\"','\\"').replace('P5\\\\n','P5\\n').replace('%d %d\\\\n255\\\\n','%d %d\\n255\\n')
    with tempfile.TemporaryDirectory(prefix='pes-career-preview-') as temp:
        file=Path(temp)/'preview.c';file.write_text(source,encoding='utf-8')
        exe=Path(temp)/'preview.exe'
        core=['master_league.c','master_league_save.c','master_league_frontend.c',
              'gameplan_preset.c','league_tournament.c','cup_tournament.c']
        subprocess.run([shutil.which('gcc'),'-std=c11','-I',str(ROOT/'source'),str(file),
            *[str(ROOT/'source'/name) for name in core],'-lm','-o',str(exe)],check=True)
        subprocess.run([str(exe)],cwd=temp,check=True)
        for generated in Path(temp).glob('*.json'):
            shutil.copy2(generated,output/generated.name)
        shutil.copy2(Path(temp)/'font.pgm',output/'font.pgm')
    font=Image.open(output/'font.pgm').convert('L')
    textures={4:Image.open(ROOT/'art/master-league/manager-office-v1.png').convert('RGBA'),
              5:Image.open(ROOT/'art/master-league/pearl-football-v2.png').convert('RGBA'),
              6:Image.open(ROOT/'art/master-league/card-sprites-v2.png').convert('RGBA')}
    header=(ROOT/'source/badge_atlas.h').read_text()
    def define(name):return int(re.search(r'#define '+name+r' (\d+)',header)[1])
    cell=define('BADGE_CELL_SIZE')
    textures[2]=Image.frombytes('RGBA',(cell*define('BADGE_ATLAS_COLS'),cell*define('BADGE_ATLAS_ROWS')),(ROOT/'data/badge_atlas.bin').read_bytes())
    for tex,name in enumerate(['main_menu_button_a','main_menu_button_b','switch_button_x','switch_button_l','switch_button_r','switch_button_sl','switch_button_sr'],10):
        textures[tex]=Image.open(ROOT/f'data/{name}.bin').convert('RGBA')
    for path in output.glob('*.json'):
        canvas=Image.new('RGBA',(1280,720),(0,0,0,255))
        for draw in json.loads(path.read_text()):
            color=tuple(round(v*255) for v in draw['color'])
            verts=draw['vertices']
            for i in range(0,len(verts),24):
                v=verts[i:i+24]
                x0,y0=round((v[0]+1)*640),round((1-v[1])*360)
                x1,y1=round((v[16]+1)*640),round((1-v[17])*360)
                w,h=max(1,x1-x0),max(1,y1-y0)
                if draw['kind']==0:
                    tile=Image.new('RGBA',(w,h),color)
                    mask=Image.new('L',(w*4,h*4));ImageDraw.Draw(mask).rounded_rectangle((0,0,w*4-1,h*4-1),radius=draw['radius']*4,fill=color[3])
                    tile.putalpha(mask.resize((w,h),Image.Resampling.LANCZOS))
                elif draw['kind']==1:
                    box=(v[2]*font.width,v[3]*font.height,v[18]*font.width,v[19]*font.height)
                    alpha=font.transform((w,h),Image.Transform.EXTENT,box,resample=Image.Resampling.BILINEAR)
                    tile=Image.new('RGBA',(w,h),color);tile.putalpha(alpha)
                elif draw['texture'] in textures:
                    texture=textures[draw['texture']]
                    box=(v[2]*texture.width,v[3]*texture.height,v[18]*texture.width,v[19]*texture.height)
                    tile=texture.transform((w,h),Image.Transform.EXTENT,box,resample=Image.Resampling.BILINEAR)
                    if draw['radius']>0:
                        mask=Image.new('L',(w*4,h*4));ImageDraw.Draw(mask).rounded_rectangle((0,0,w*4-1,h*4-1),radius=draw['radius']*4,fill=255)
                        tile.putalpha(ImageChops.multiply(tile.getchannel('A'),mask.resize((w,h),Image.Resampling.LANCZOS)))
                else:
                    continue
                canvas.alpha_composite(tile,(x0,y0))
        canvas.convert('RGB').save(path.with_suffix('.png'))
    print(output)

if __name__=='__main__':
    main(sys.argv[1] if len(sys.argv)>1 else None)

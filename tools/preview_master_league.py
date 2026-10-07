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
    output=Path(output) if output else ROOT/'local-debug/master-league-v6/previews'
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
#include "fl26_league_catalog_generated.h"
typedef float GLfloat;
typedef unsigned int GLuint;
static int screen_width=1280,screen_height=720;
static struct {GLuint badge_tex,master_league_background_tex,master_league_pearl_tex,master_league_cards_tex,master_league_icons_tex;
  GLuint league_logo_tex[FL26_LEAGUE_CATALOG_COUNT];int league_logo_uploaded[FL26_LEAGUE_CATALOG_COUNT];
  float league_logo_aspect[FL26_LEAGUE_CATALOG_COUNT];int loc_color;} gl={.badge_tex=2,.master_league_background_tex=4,.master_league_pearl_tex=5,.master_league_cards_tex=6,.master_league_icons_tex=7};
static void prepare_league_logo_index(uint32_t index){(void)index;}
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
  assert(ui.draw_count<384u && quads<4096);
  if(ui.shoulders) {
    ml_ui_image(&ui,13,0,.066f-.035f*.5625f*.5f,ui.shoulder_y-.0175f,.035f*.5625f,.035f,vertices,&quads);
    ml_ui_image(&ui,14,0,.934f-.035f*.5625f*.5f,ui.shoulder_y-.0175f,.035f*.5625f,.035f,vertices,&quads);
  }
  for(uint32_t i=0;i<ui.view.helper_count;i++) {
    const char *key=ui.view.helper_key[i];GLuint texture=10;
    if(!strcmp(key,"B"))texture=11;else if(!strcmp(key,"X"))texture=12;
    else if(!strcmp(key,"L"))texture=13;else if(!strcmp(key,"R"))texture=14;
    else if(!strcmp(key,"SL"))texture=15;else if(!strcmp(key,"SR"))texture=16;
    else if(!strcmp(key,"Y"))texture=17;
    ml_ui_image(&ui,texture,0,ui.helper_centers[i]-.0444f*.5625f*.5f,.9625f-.0222f,.0444f*.5625f,.0444f,vertices,&quads);
  }
  char path[80];snprintf(path,sizeof(path),"%s.json",name);FILE *out=fopen(path,"w");
  /* Match native base -> helper sprites -> foreground toast/modal paint order. */
  for(uint32_t i=1;i<ui.draw_count;i++) {
    MlDraw d=ui.draws[i];uint32_t j=i;
    while(j && d.layer!=1 && d.layer!=3 &&
        (ui.draws[j-1u].layer==1 || ui.draws[j-1u].layer==3)){ui.draws[j]=ui.draws[j-1u];j--;}
    ui.draws[j]=d;
  }
  fprintf(out,"[");
  for(uint32_t i=0;i<ui.draw_count;i++) {
    MlDraw *d=&ui.draws[i];
    if(d->theme>=0){fnx_button_color(d->theme,d->selected,d->enabled);memcpy(d->color,rgba,sizeof(rgba));}
    fprintf(out,"%s{\"kind\":%d,\"layer\":%d,\"texture\":%u,\"radius\":%g,\"color\":[%g,%g,%g,%g],\"vertices\":[",i ? "," : "",d->kind,d->layer,d->texture,d->round.radius,d->color[0],d->color[1],d->color[2],d->color[3]);
    for(int j=0;j<d->count*24;j++)fprintf(out,"%s%g",j ? "," : "",vertices[d->first*24+j]);
    fprintf(out,"]}");
  }
  fprintf(out,"]");fclose(out);
}
static void go(uint32_t section,uint32_t item) {
  while(view().drawer.open)press(B);
  while(view().page!=ML_PAGE_HUB)press(B);
  while(view().section<section)press(R);
  while(view().section>section)press(1u<<4);
  press(UP);if(view().selected==1u)press(LEFT);
  if(item>=2u)press(DOWN);
  if(item==1u || item==3u)press(RIGHT);
  if(item==4u){press(RIGHT);press(RIGHT);}
  press(A);
}
int main(void) {
  FILE *font=fopen("font.pgm","wb");fprintf(font,"P5\n%d %d\n255\n",EFOOTBALL_FONT_ATLAS_W,EFOOTBALL_FONT_ATLAS_H);
  fwrite(efootball_font_atlas_alpha,1,sizeof(efootball_font_atlas_alpha),font);fclose(font);
  ml_frontend_open();dump("landing");press(A);dump("settings");
  press(A);dump("league-selector");press(B);
  press(DOWN);press(A);press(DOWN);dump("club-selector");press(A);
  press(DOWN);press(RIGHT);dump("difficulty-selector");
  for(int i=0;i<5;i++)press(DOWN);dump("settings-next");press(A);
  ml_frontend_name_result("Andro NX");press(DOWN);press(A);dump("nationality-selector");press(A);dump("manager");
  press(DOWN);press(A);dump("save-slots");press(A);assert(view().page==ML_PAGE_HUB);dump("home");
  go(0,4);press(A);assert(view().modal.open);dump("overwrite-modal");press(B);press(B);
  press(1u<<3);dump("quick-save");ticks+=3100000000u;dump("quick-save-dismissed");
  press(DOWN);press(RIGHT);dump("ranking-focus");press(A);dump("league-table");press(Y);dump("scorers-empty");
  go(0,2);dump("calendar");press(R);dump("calendar-august");
  go(1,0);dump("squad");press(A);dump("squad-list");press(B);press(B);dump("squad-section");
  go(2,1);dump("contracts");press(A);dump("contract-term");press(B);press(B);dump("office-section");
  go(2,0);dump("market");press(DOWN);press(DOWN);press(DOWN);press(A);dump("market-leagues");
  press(A);dump("market-clubs");press(A);dump("market-players");press(A);dump("offer-terms");
  press(DOWN);press(DOWN);press(DOWN);press(A);
  go(0,0);dump("next-window");press(A);dump("save-toast");ticks+=3100000000u;dump("toast-dismissed");
  go(2,0);press(A);dump("my-teams");press(A);dump("incoming-offers");press(A);dump("offer-actions");
  go(0,0);ml_frontend_pad(A);dump("advance-start");ui_clock+=600u;ml_frontend_tick(ui_clock);dump("advance-moving");finish_advance();dump("advance-arrived");
  go(2,0);dump("market-unread");press(B);ticks+=3100000000u;dump("hub-unread");go(2,0);
  press(DOWN);press(A);dump("transfer-response");press(A);dump("response-actions");
  go(2,3);dump("manager-office");press(DOWN);press(A);dump("president-messages");press(A);dump("president-message");
  go(2,4);dump("career-settings");
  go(3,2);dump("cup-bracket");press(R);dump("cup-next-round");press(B);dump("competitions-section");
  go(0,1);assert(view().page==ML_PAGE_NEWS);dump("club-feed");press(RIGHT);dump("feed-results-empty");
  press(RIGHT);dump("feed-season");press(RIGHT);dump("feed-transfers");
  for(uint32_t i=0;i<12u;i++) {
    MlEvent event;assert(ml_next_event(ml_frontend_career(),&event));
    if(event.kind<ML_EVENT_WINDOW)break;
    go(0,0);press(A);
  }
  go(0,0);press(B);ticks+=3100000000u;dump("next-match-aligned");
  go(0,0);dump("next-match");press(DOWN);press(A);assert(view().modal.open);dump("simulate-modal");
  press(B);press(UP);press(A);assert(view().modal.open);dump("play-modal");press(A);
  assert(ml_frontend_take_action()==ML_ACTION_MATCH);
  const MasterLeague *career=ml_frontend_career();
  const LeagueScorer scorer={.team=career->settings.club,.base_id=career->players[0].identity,
    .portrait_id=career->players[0].native_id,.goals=2u,.name="Synthetic Striker"};
  ml_frontend_result(2u,0u,&scorer,1u);assert(ml_frontend_restore() && view().page==ML_PAGE_ADVANCE);
  ui_clock+=900u;ml_frontend_tick(ui_clock);dump("advance-match-date");finish_advance();
  go(0,3);press(Y);dump("scorers-with-badges");
  go(0,1);while(view().feed_index!=1u)press(RIGHT);ticks+=3100000000u;dump("feed-results");
  go(2,0);press(A);press(DOWN);press(A);dump("my-players");press(A);dump("my-player-actions");
  press(DOWN);press(A);assert(view().modal.open);dump("release-modal");press(B);
  /* Synthetic terminal states exercise projection only, without game payloads. */
  MasterLeague *fixture=(MasterLeague *)ml_frontend_career();
  for(uint32_t i=0;i<fixture->office.offer_count;i++)
    fixture->office.offers[i].status=fixture->office.offers[i].incoming ? ML_OFFER_EXPIRED : ML_OFFER_REJECTED;
  go(2,0);press(A);press(A);press(A);dump("expired-offer");press(A);dump("expired-renewal");
  go(2,0);press(DOWN);press(A);press(A);dump("rejected-offer");return 0;
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
              6:Image.open(ROOT/'art/master-league/card-sprites-v2.png').convert('RGBA'),
              7:Image.open(ROOT/'art/master-league/office-icons-v4.png').convert('RGBA')}
    header=(ROOT/'source/badge_atlas.h').read_text()
    def define(name):return int(re.search(r'#define '+name+r' (\d+)',header)[1])
    cell=define('BADGE_CELL_SIZE')
    textures[2]=Image.frombytes('RGBA',(cell*define('BADGE_ATLAS_COLS'),cell*define('BADGE_ATLAS_ROWS')),(ROOT/'data/badge_atlas.bin').read_bytes())
    for tex,name in enumerate(['main_menu_button_a','main_menu_button_b','switch_button_x','switch_button_l','switch_button_r','switch_button_sl','switch_button_sr','switch_button_y'],10):
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
                    tile.putalpha(tile.getchannel('A').point(lambda a: round(a*color[3]/255)))
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

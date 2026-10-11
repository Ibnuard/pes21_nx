"""Render the production Game Plan panels using synthetic, non-game data."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import tempfile

from PIL import Image
import preview_frontdoor as frontdoor
import preview_cup as shared

ROOT = shared.ROOT
DRIVER = r'''
static EditorPanel views[2];
static void capture(const char *name) {
  static GLfloat vertices[4096*24+8];
  for(int i=4096*24;i<4096*24+8;i++)vertices[i]=12345.f;
  MasterLeagueRender ui={0};int quads=0;
  EditorPanel before[2];memcpy(before,views,sizeof(views));
  ml_ui_image(&ui,70,0,0,0,1,1,vertices,&quads);
  for(uint32_t side=0;side<(views[0].setplay ? 1u : 2u);side++) {
    if(!views[0].setplay) {
      const float x=.018f+side*.489f;
      fd_art(&ui,side,x,.025f,.475f,.120f,vertices,&quads);
      fd_text(&ui,side ? "AWAY / PLAYER 2" : "HOME / PLAYER 1",x+.020f,.052f,.4f,.030f,-1,vertices,&quads);
      fd_text(&ui,"GAME PLAN",x+.020f,.101f,.4f,.021f,-1,vertices,&quads);
    }
    editor_panel_emit(&ui,&views[side],side,vertices,&quads);
  }
  assert(!memcmp(before,views,sizeof(views)));
  assert(quads<4096 && ui.draw_count<384);
  for(int i=4096*24;i<4096*24+8;i++)assert(vertices[i]==12345.f);
  for(int i=0;i<quads*24;i+=4)assert(isfinite(vertices[i]) && isfinite(vertices[i+1]) && fabsf(vertices[i])<=1.002f && fabsf(vertices[i+1])<=1.002f);
  char file[128];snprintf(file,sizeof(file),"%s.json",name);
  frame=fopen(file,"w");assert(frame);fprintf(frame,"[");draw_count=0;
  memset(uniforms,0,sizeof(uniforms));bound_texture=0;
  active_quads=quads;active_vertices=vertices;
  master_league_draw(&ui);fprintf(frame,"]");fclose(frame);
  printf("%s: %d quads / %u draws\n",name,quads,ui.draw_count);
}
static void panel(uint32_t side,uint32_t page,const char *title,const char *sub) {
  EditorPanel *v=&views[side];memset(v,0,sizeof(*v));v->active=1;v->page=page;
  fd_copy(v->title,sizeof(v->title),title);fd_copy(v->subtitle,sizeof(v->subtitle),sub);
}
int main(void) {
  initialize_gl();gl.frontdoor_flat_tex=70;gl.frontdoor_panels_tex=76;gl.gameplan_icons_tex=77;
  for(int left=0;left<2;left++) {
    GLfloat vertices[48];int count=0;MasterLeagueRender pair={0};
    editor_foot_pair(&pair,left,.2f,.5f,vertices,&count);
    assert(count==2 && pair.draw_count==2);
    assert(pair.draws[0].color[3]==(left?1.f:.20f));
    assert(pair.draws[1].color[3]==(left?.20f:1.f));
  }
  FILE *font=fopen("font.pgm","wb");assert(font);
  fprintf(font,"P5\n%d %d\n255\n",EFOOTBALL_FONT_ATLAS_W,EFOOTBALL_FONT_ATLAS_H);
  fwrite(efootball_font_atlas_alpha,1,sizeof(efootball_font_atlas_alpha),font);fclose(font);
  panel(0,2,"FORMATION","CURRENT SHAPE / 4-3-3");views[0].count=4;
  const char *labels[]={"PLAYING STYLE","TEAM SHAPE","OFFSIDE TRAP","SUBSTITUTIONS"};
  const char *values[]={"ATTACKING","4-3-3","OFF","ON"};
  for(int i=0;i<4;i++) {fd_copy(views[0].rows[i].label,96,labels[i]);fd_copy(views[0].rows[i].value,96,values[i]);views[0].rows[i].icon=(uint32_t[]){5,11,7,8}[i];}
  panel(1,3,"TEAM PRESETS","LINEUP / TACTICS / SET-PIECE ROLES");views[1].count=2;views[1].focus=1;
  fd_copy(views[1].rows[0].label,96,"SAVE FORMATION");fd_copy(views[1].rows[0].value,96,"Store this team's setup");
  fd_copy(views[1].rows[1].label,96,"LOAD FORMATION");fd_copy(views[1].rows[1].value,96,"Restore a saved setup");
  views[1].rows[0].icon=9;views[1].rows[1].icon=10;
  capture("01-formation-presets");
  panel(0,4,"PLAYER ROLES","CAPTAIN / SET PIECES / ATTACKERS");views[0].count=9;views[0].focus=5;
  const char *roles[]={"CAPTAIN","RIGHT CORNER KICK","LEFT CORNER KICK","LONG FREE KICK","SHORT FREE KICK","PENALTY KICK","SET-PIECE ATTACKER 1","SET-PIECE ATTACKER 2","SET-PIECE ATTACKER 3"};
  for(int i=0;i<9;i++) {fd_copy(views[0].rows[i].label,96,roles[i]);fd_copy(views[0].rows[i].value,96,i>5 ? "NONE" : i%2 ? "Alexander Longname" : "Daniel Sample");}
  panel(1,3,"LOAD PRESET","LINEUP / TACTICS / SET-PIECE ROLES");views[1].step=1;views[1].count=3;
  for(int i=0;i<3;i++) {snprintf(views[1].rows[i].label,96,"PRESET %02d",i+1);fd_copy(views[1].rows[i].value,96,i ? "EMPTY" : "SAVED");}
  for(int i=0;i<9;i++) {EditorRow *r=&views[0].rows[i];r->icon=(uint32_t[]){0,1,2,3,3,4,5,5,5}[i];
    if(i<6) {r->player=1;r->portrait=i+1;fd_copy(r->role,8,preview_roles[i]);fd_copy(r->value,96,preview_names[i]);}}
  for(int i=0;i<3;i++)views[1].rows[i].icon=10;
  capture("02-roles-slots");
  panel(0,4,"ASSIGN PLAYER","SHORT FREE KICK");views[0].picker=1;views[0].total=11;views[0].count=7;views[0].first=3;views[0].focus=6;
  for(int i=0;i<7;i++) {EditorRow *r=&views[0].rows[i];fd_copy(r->label,96,i%2 ? "Alexander Longname" : "Daniel Sample");fd_copy(r->role,8,i%2 ? "CMF" : "CB");r->player=1;r->left=i%2;r->power=66+i;r->assigned=i==1;}
  for(int i=0;i<7;i++) {EditorRow *r=&views[0].rows[i];r->portrait=i+1;
    fd_copy(r->label,96,preview_names[i]);fd_copy(r->role,8,preview_roles[i]);r->left=preview_left[i];r->power=preview_power[i];}
  panel(1,2,"CHOOSE SHAPE","CURRENT SHAPE / 4-3-3");views[1].picker=1;views[1].count=5;views[1].focus=3;
  for(int i=0;i<5;i++)fd_copy(views[1].rows[i].label,96,i%2 ? "4-4-2" : "4-3-3");views[1].rows[0].assigned=1;
  for(int i=0;i<5;i++)views[1].rows[i].icon=11;
  capture("03-player-picker-shapes");
  views[0].setplay=1;views[0].page=0;
  fd_copy(views[0].title,64,"FREE KICK");fd_copy(views[0].subtitle,96,"CHOOSE A TAKER");
  fd_copy(views[0].select_key,8,"A");fd_copy(views[0].back_key,8,"B");
  capture("04-free-kick");
  fd_copy(views[0].title,64,"THROW-IN");fd_copy(views[0].select_key,8,"DOWN");fd_copy(views[0].back_key,8,"LEFT");
  capture("05-thrower-single-joycon");
  screen_width=1920;screen_height=1080;capture("06-taker-1080p");
  screen_width=1280;screen_height=720;
  views[0].count=1;views[0].total=1;views[0].first=views[0].focus=0;capture("07-one-player");
  views[0].count=views[0].total=0;capture("08-loading-players");
  panel(0,3,"SAVE PRESET","LINEUP / TACTICS / SET-PIECE ROLES");
  views[0].step=2;views[0].count=3;views[0].target=views[0].focus=0;views[0].modal_focus=1;
  for(int i=0;i<3;i++) {snprintf(views[0].rows[i].label,96,"PRESET %02d",i+1);fd_copy(views[0].rows[i].value,96,i?"EMPTY":"SAVED");views[0].rows[i].icon=9;}
  panel(1,3,"LOAD PRESET","LINEUP / TACTICS / SET-PIECE ROLES");
  views[1]=views[0];views[1].loading=1;fd_copy(views[1].title,64,"LOAD PRESET");
  capture("09-preset-confirmations");
  views[0].step=views[1].step=3;capture("10-preset-success");
  views[1].step=4;fd_copy(views[1].status,96,"PRESET 01 COULD NOT BE LOADED");capture("11-preset-error");
  return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', type=Path, default=ROOT / 'local-debug/review-v16/ui-preview')
    parser.add_argument('--geometry-only', action='store_true')
    parser.add_argument('--player-samples', type=Path, help='Optional local JSON: seven name/role/left/power/portrait rows')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    samples = json.loads(args.player_samples.read_text()) if args.player_samples else [
        dict(name='Alexander Longname' if i % 2 else 'Daniel Sample', role='CMF' if i % 2 else 'CB', left=i % 2, power=66+i) for i in range(7)]
    if len(samples) != 7:
        raise ValueError('Exactly seven preview players required')
    sample_source = '\n'.join('static const char *preview_' + key + '[]={' + ','.join(json.dumps(r[field], ensure_ascii=True) for r in samples) + '};' for key, field in [('names','name'),('roles','role')])
    sample_source += '\n' + '\n'.join('static const uint32_t preview_' + key + '[]={' + ','.join(str(int(r[key])) for r in samples) + '};' for key in ['left','power'])
    with tempfile.TemporaryDirectory(prefix='pes-editor-preview-') as temporary:
        tmp = Path(temporary)
        base = frontdoor.build_driver((ROOT / 'source/overlay.c').read_text()).split('static FrontdoorView view;', 1)[0]
        if args.player_samples:
            base = base.replace('static GLuint gameplan_portrait_texture(uint32_t id) { (void)id;return 0; }','static GLuint gameplan_portrait_texture(uint32_t id) { return id && id<=7u ? 600u+id : 0u; }')
        src = base + '\n#define PESNX_EDITOR_PREVIEW\n' + (ROOT / 'source/gameplan_panels.inc').read_text() + sample_source + DRIVER
        (tmp / 'preview.c').write_text(src)
        (tmp / 'ue4_hooks.h').write_text((ROOT / 'source/ue4_hooks.h').read_text().replace('#include "so_util.h"', 'typedef struct so_module so_module;'))
        subprocess.run([shutil.which('gcc'), '-std=c11', '-O1', '-I', str(tmp), '-I', str(ROOT / 'source'), str(tmp / 'preview.c'), '-lm', '-o', str(tmp / 'preview.exe')], check=True)
        subprocess.run([str(tmp / 'preview.exe')], cwd=tmp, check=True)
        if not args.geometry_only:
            assets = shared.textures(tmp)
            assets[70] = Image.open(ROOT / 'data/frontdoor_flat_v3.bin').convert('RGBA')
            assets[76] = Image.open(ROOT / 'data/frontdoor_panels_v2.bin').convert('RGBA')
            assets[77] = Image.open(ROOT / 'data/gameplan_icons_v1.bin').convert('RGBA')
            if args.player_samples:
                for i, r in enumerate(samples):
                    assets[601+i] = Image.open(r['portrait']).convert('RGBA')
            frames = sorted(tmp.glob('*.json'))
            for path in frames:
                shared.rasterize(json.loads(path.read_text()), assets).save(args.output / path.with_suffix('.png').name)
            shared.write_gallery(args.output, frames)


if __name__ == '__main__':
    main()

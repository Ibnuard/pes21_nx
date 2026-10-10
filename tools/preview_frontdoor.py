"""Synthetic Flat Matchday previews from the production C renderer.

No game runtime, native fixtures or save access. Uses public artwork, atlas
badges and synthetic lineup/rating data. Not a Switch/emulator capture.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile

from PIL import Image
import preview_cup as shared

ROOT = shared.ROOT

DRIVER = r'''
static FrontdoorView view;
static int max_quads,max_draws;
static void capture(const char *name) {
  static GLfloat vertices[4096*24+8];
  for(int i=4096*24;i<4096*24+8;i++)vertices[i]=12345.f;
  MasterLeagueRender ui;int quads=0;const FrontdoorView before=view;
  frontdoor_emit(&ui,&view,vertices,&quads);
  assert(!memcmp(&before,&view,sizeof(view)));
  assert(quads<4096 && ui.draw_count<380);
  for(int i=4096*24;i<4096*24+8;i++)assert(vertices[i]==12345.f);
  for(int i=0;i<quads*24;i+=4) {
    assert(isfinite(vertices[i]) && isfinite(vertices[i+1]));
    assert(fabsf(vertices[i])<=1.002f && fabsf(vertices[i+1])<=1.002f);
  }
  if(quads>max_quads)max_quads=quads;
  if((int)ui.draw_count>max_draws)max_draws=(int)ui.draw_count;
  char filename[160];snprintf(filename,sizeof(filename),"%s.json",name);
  frame=fopen(filename,"w");assert(frame);fprintf(frame,"[");draw_count=0;
  memset(uniforms,0,sizeof(uniforms));bound_texture=0;
  active_quads=quads;active_vertices=vertices;
  master_league_draw(&ui);fprintf(frame,"]");fclose(frame);
  printf("%s: %d quads, %u draws\n",name,quads,ui.draw_count);
}
static void base(FrontdoorPage page) {
  memset(&view,0,sizeof(view));view.page=page;view.side_count=2;
  view.exhibition=1;view.portrait_mix=1.f;view.action_count=5;
  view.menu_weights[0]=1.f;
}
static void menu(uint32_t focus) {
  base(FD_MENU);view.focus=focus;
  memset(view.menu_weights,0,sizeof(view.menu_weights));view.menu_weights[focus]=1.f;
  view.portrait_previous=view.portrait_current=focus;
}
static void menu_motion(void) {
  FrontdoorMenuMotion motion={0};
  menu(0);fd_menu_motion_step(&motion,1,0,0);
  memcpy(view.menu_weights,motion.weights,sizeof(view.menu_weights));capture("motion-00");
  const uint32_t focus_order[]={1,2,3,0};
  uint32_t index=1;
  for(uint32_t step=0;step<4;step++) {
    uint64_t start=(step+1)*1000000000ULL;view.focus=focus_order[step];
    fd_menu_motion_step(&motion,1,view.focus,start);
    for(uint32_t frame=1;frame<=8;frame++) {
      fd_menu_motion_step(&motion,1,view.focus,start+frame*32500000ULL);
      float sum=0;for(uint32_t i=0;i<4;i++) {
        assert(motion.weights[i]>=0.f && motion.weights[i]<=1.f);sum+=motion.weights[i];
      }
      assert(fabsf(sum-1.f)<.00001f);
      memcpy(view.menu_weights,motion.weights,sizeof(view.menu_weights));
      view.menu_pattern_phase=motion.pattern_phase;
      char name[48];snprintf(name,sizeof(name),"motion-%02u",index++);capture(name);
    }
  }
  /* A quick second tap and reversal retain the current pose exactly. */
  fd_menu_motion_step(&motion,1,1,5000000000ULL);
  fd_menu_motion_step(&motion,1,1,5060000000ULL);
  float before[4];memcpy(before,motion.weights,sizeof(before));
  memcpy(view.menu_weights,before,sizeof(before));view.focus=1;capture("retarget-before");
  fd_menu_motion_step(&motion,1,3,5060000000ULL);
  assert(!memcmp(before,motion.weights,sizeof(before)));
  memcpy(view.menu_weights,motion.weights,sizeof(before));view.focus=3;capture("retarget-after");
  fd_menu_motion_step(&motion,1,0,5100000000ULL);
  fd_menu_motion_step(&motion,1,0,5360000000ULL);
  assert(motion.weights[0]==1.f);
  for(uint32_t i=1;i<4;i++)assert(motion.weights[i]==0.f);
  fd_menu_motion_step(&motion,0,0,5400000000ULL);
  assert(!motion.initialized);
  fd_menu_motion_step(&motion,1,2,5410000000ULL);
  assert(motion.weights[2]==1.f);
  /* Same time, same pose regardless of update frequency. */
  FrontdoorMenuMotion sparse=motion,dense=motion;
  fd_menu_motion_step(&sparse,1,1,5500000000ULL);
  fd_menu_motion_step(&dense,1,1,5500000000ULL);
  fd_menu_motion_step(&sparse,1,1,5630000000ULL);
  for(uint64_t time=5510000000ULL;time<=5630000000ULL;time+=10000000ULL)
    fd_menu_motion_step(&dense,1,1,time);
  for(uint32_t i=0;i<4;i++)assert(fabsf(sparse.weights[i]-dense.weights[i])<.00001f);
  /* Idle focused background: one full loop with a fixed border and content. */
  menu(0);memset(&motion,0,sizeof(motion));fd_menu_motion_step(&motion,1,0,0);
  for(uint32_t frame=0;frame<60u;frame++) {
    fd_menu_motion_step(&motion,1,0,frame*100000000ULL);
    view.menu_pattern_phase=motion.pattern_phase;
    char name[48];snprintf(name,sizeof(name),"pattern-%02u",frame);capture(name);
  }
  fd_menu_motion_step(&motion,1,0,6000000000ULL);
  assert(motion.pattern_phase==0.f);
  view.menu_pattern_phase=motion.pattern_phase;capture("pattern-cycle-end");
}
static void selector(int teams) {
  base(FD_SELECTOR);
  static const char *const names[]={"CHELSEA FC","ARSENAL FC"};
  static const char *const nearby[]={"ASTON VILLA FC","AFC BOURNEMOUTH","LIVERPOOL FC","MANCHESTER UNITED"};
  static const char *const regions[]={"ENGLISH 2ND DIV","SPANISH LEAGUE","LIGUE 1","SERIE A"};
  static const uint32_t neighbours[]={FD_BADGE_VILLA,FD_BADGE_BOURNEMOUTH,FD_BADGE_LIVERPOOL,FD_BADGE_UNITED};
  for(uint32_t side=0;side<2;side++) {
    FrontdoorSide *s=&view.sides[side];s->active=side==0;
    s->phase=teams ? PES_2P_TEAM_SELECTOR_PHASE_TEAM : PES_2P_TEAM_SELECTOR_PHASE_LEAGUE;
    fd_copy(s->name,sizeof(s->name),teams ? names[side] : "ENGLISH LEAGUE");
    fd_copy(s->owner,sizeof(s->owner),side ? "COM / AWAY" : "P1 / HOME");
    fd_copy(s->title,sizeof(s->title),teams ? "ENGLISH LEAGUE" : "SELECT LEAGUE");
    s->badge=teams ? (side ? FD_BADGE_ARSENAL : FD_BADGE_CHELSEA) : FD_BADGE_ENGLISH;
    s->ratings[0]=92;s->ratings[1]=94;s->ratings[2]=91;s->grade=9;s->stats_valid=teams;
    s->neighbour_count=4;
    for(uint32_t i=0;i<4;i++) {
      s->neighbours[i].relative=i<2 ? (int)i-2 : (int)i-1;
      s->neighbours[i].badge=teams ? neighbours[i] : FD_BADGE_ENGLISH;
      fd_copy(s->neighbours[i].label,sizeof(s->neighbours[i].label),teams ? nearby[i] : regions[i]);
    }
  }
}
static void hub(void) {
  base(FD_HUB);view.focus=2;
  fd_copy(view.subtitle,sizeof(view.subtitle),"HOME STADIUM / NIGHT / FINE");
  static const char *const home[]={"Home Goalkeeper","Home Left Back","Home Centre Back","Home Centre Back","Home Right Back","Home Midfielder","Home Midfielder","Home Left Wing","Home Playmaker","Home Right Wing","Home Striker"};
  static const char *const away[]={"Away Goalkeeper","Away Left Back","Away Centre Back","Away Centre Back","Away Right Back","Away Midfielder","Away Midfielder","Away Left Wing","Away Playmaker","Away Right Wing","Away Striker"};
  for(uint32_t side=0;side<2;side++) {
    FrontdoorSide *s=&view.sides[side];s->lineup_count=11;
    s->badge=side ? FD_BADGE_ARSENAL : FD_BADGE_CHELSEA;
    fd_copy(s->name,sizeof(s->name),side ? "ARSENAL FC" : "CHELSEA FC");
    fd_copy(s->owner,sizeof(s->owner),side ? "AWAY" : "HOME");
    for(uint32_t i=0;i<11;i++)fd_copy(s->lineup[i],sizeof(s->lineup[i]),side ? away[i] : home[i]);
    s->kit_count=3;s->kit_index=side;s->kit_number=side+1;
  }
}
int main(void) {
  initialize_gl();
  gl.frontdoor_flat_tex=70;gl.team_rating_star_tex=71;gl.frontdoor_panels_tex=76;
  for(uint32_t i=0;i<4;i++)gl.main_menu_portrait_tex[i]=72+i;
  FILE *font=fopen("font.pgm","wb");assert(font);
  fprintf(font,"P5\n%d %d\n255\n",EFOOTBALL_FONT_ATLAS_W,EFOOTBALL_FONT_ATLAS_H);
  fwrite(efootball_font_atlas_alpha,1,sizeof(efootball_font_atlas_alpha),font);fclose(font);
  base(FD_TITLE);capture("01-title");
  menu(0);capture("02-main-menu");
  menu(1);capture("03-main-menu-modes");
  menu(2);capture("04-main-menu-settings");
  menu(3);capture("05-main-menu-credits");
  menu_motion();
  base(FD_MATCH);view.row_count=2;
  fd_copy(view.rows[0].label,sizeof(view.rows[0].label),"EXHIBITION");
  fd_copy(view.rows[1].label,sizeof(view.rows[1].label),"2 PLAYER");
  capture("06-exhibition");view.focus=1;capture("07-two-player");
  base(FD_MODES);view.row_count=3;
  fd_copy(view.rows[0].label,sizeof(view.rows[0].label),"CUP");
  fd_copy(view.rows[1].label,sizeof(view.rows[1].label),"LEAGUE");
  fd_copy(view.rows[2].label,sizeof(view.rows[2].label),"MASTER LEAGUE");capture("08-modes");
  selector(0);capture("09-select-league");
  selector(1);capture("10-select-team-home");
  view.sides[0].ready=1;view.sides[0].ready_mix=1;view.sides[0].active=0;view.sides[1].active=1;
  capture("11-select-team-away");
  view.sides[1].ready=1;view.sides[1].ready_mix=1;capture("12-teams-ready");
  selector(1);view.exhibition=0;view.sides[1].active=1;
  fd_copy(view.sides[1].owner,sizeof(view.sides[1].owner),"P2 / AWAY");capture("13-two-player-select");
  view.sides[0].neighbour_count=0;view.sides[1].neighbour_count=1;
  fd_copy(view.sides[0].name,sizeof(view.sides[0].name),"BORUSSIA MONCHENGLADBACH VERY LONG TEAM NAME");
  view.sides[1].stats_valid=0;capture("14-selector-edge-and-long-name");
  selector(1);view.side_count=1;capture("15-single-slot-picker");
  hub();capture("16-match-hub");
  for(uint32_t count=4;count<=5;count++)for(uint32_t focus=0;focus<count;focus++) {
    view.action_count=count;view.focus=focus;
    char name[96];snprintf(name,sizeof(name),"17-hub-%u-buttons-focus-%u",count,focus);capture(name);
  }
  hub();view.page=FD_KITS;view.focus=0;capture("18-kits-home");
  view.focus=1;capture("19-kits-away");
  view.kit_editing=1;capture("19-kits-away-editing");
  view.focus=0;capture("18-kits-home-editing");
  base(FD_STADIUM);view.row_count=view.total_rows=6;
  static const char *const labels[]={"STADIUM","MATCH TIME","WEATHER","SEASON","GRASS LENGTH","PITCH CONDITION"};
  static const char *const values[]={"KONAMI STADIUM","NIGHT","FINE","SUMMER","NORMAL","DRY"};
  fd_copy(view.status,sizeof(view.status),"GRASS / PITCH AFFECT BALL SURFACE; WINTER CHANGES SEASON");
  for(uint32_t i=0;i<6;i++) {
    fd_copy(view.rows[i].label,sizeof(view.rows[i].label),labels[i]);
    fd_copy(view.rows[i].value,sizeof(view.rows[i].value),values[i]);
  }
  capture("20-stadium");view.focus=5;capture("21-stadium-last-row");
  base(FD_SETTINGS);view.row_count=6;view.total_rows=9;
  static const char *const settings[]={"MATCH LEVEL","MATCH TIME","EXTRA TIME","PENALTIES","SUBSTITUTIONS","INJURIES"};
  static const char *const options[]={"REGULAR","10 MIN","OFF","ON","5","ON"};
  for(uint32_t i=0;i<6;i++) {
    fd_copy(view.rows[i].label,sizeof(view.rows[i].label),settings[i]);
    fd_copy(view.rows[i].value,sizeof(view.rows[i].value),options[i]);
  }
  capture("22-general-settings");view.first_row=3;view.focus=8;capture("23-general-settings-scroll");
  view.page=FD_PAUSE_SETTINGS;fd_copy(view.title,sizeof(view.title),"MATCH SETTINGS");capture("28-pause-match-settings");
  view.row_count=view.total_rows=4;view.first_row=0;view.focus=0;
  fd_copy(view.title,sizeof(view.title),"CAMERA SETTINGS");
  static const char *const camera[]={"CAMERA TYPE","HEIGHT","ZOOM","ANGLE"};
  for(uint32_t i=0;i<4;i++) {fd_copy(view.rows[i].label,sizeof(view.rows[i].label),camera[i]);fd_copy(view.rows[i].value,sizeof(view.rows[i].value),i ? "5" : "DYNAMIC WIDE");}
  capture("29-pause-camera-settings");
  base(FD_VIDEO);view.row_count=view.total_rows=2;fd_copy(view.title,sizeof(view.title),"VIDEO SETTINGS");
  fd_copy(view.rows[0].label,sizeof(view.rows[0].label),"GRAPHICS");fd_copy(view.rows[0].value,sizeof(view.rows[0].value),"HIGH");
  fd_copy(view.rows[1].label,sizeof(view.rows[1].label),"FRAME RATE");fd_copy(view.rows[1].value,sizeof(view.rows[1].value),"60 FPS");capture("30-video-settings");
  base(FD_INFO);view.row_count=3;
  fd_copy(view.rows[0].label,sizeof(view.rows[0].label),"Port & Mod By Ibnuard");
  fd_copy(view.rows[1].label,sizeof(view.rows[1].label),"Support: androswitch.vercel.app");
  fd_copy(view.rows[2].label,sizeof(view.rows[2].label),"Version: production candidate");capture("31-credits");
  base(FD_LOADING);capture("32-loading");
  hub();view.page=FD_VS;capture("33-prematch-loading");
  hub();view.page=FD_PAUSE;view.focus=0;
  for(uint32_t s=0;s<2;s++) {
    fd_copy(view.score[s],sizeof(view.score[s]),s ? "0" : "1");
    for(uint32_t r=0;r<8;r++)fd_copy(view.stats[s][r],sizeof(view.stats[s][r]),r ? "3" : s ? "45%" : "55%");
  }
  capture("34-pause");view.confirm=1;view.confirm_focus=1;capture("35-return-confirm-cancel");
  view.confirm_focus=0;capture("36-return-confirm");
  /* The four native result surfaces use the same production presentation.
   * Exercise one/two/three actions, every focus and each return destination. */
  view.page=FD_RESULT;view.confirm=0;view.focus=0;view.action_count=1;
  fd_copy(view.sides[1].name,sizeof(view.sides[1].name),"WOLVERHAMPTON WANDERERS");
  view.sides[1].badge=FD_BADGE_WOLVES;
  fd_copy(view.score[1],sizeof(view.score[1]),"1");
  fd_copy(view.title,sizeof(view.title),"HALF TIME");
  fd_copy(view.rows[0].label,sizeof(view.rows[0].label),"NEXT");
  capture("37-half-time-overview");
  view.action_count=3;
  fd_copy(view.rows[0].label,sizeof(view.rows[0].label),"GAME PLAN");
  fd_copy(view.rows[1].label,sizeof(view.rows[1].label),"NEXT");
  fd_copy(view.rows[2].label,sizeof(view.rows[2].label),"BACK TO MASTER LEAGUE");
  fd_copy(view.status,sizeof(view.status),view.rows[2].label);
  for(uint32_t i=0;i<3u;i++) {
    view.focus=i;char name[64];snprintf(name,sizeof(name),"38-half-time-menu-focus-%u",i);capture(name);
  }
  fd_copy(view.title,sizeof(view.title),"FULL TIME");
  fd_copy(view.score[0],sizeof(view.score[0]),"3");
  view.action_count=1;view.focus=0;view.status[0]=0;
  fd_copy(view.rows[0].label,sizeof(view.rows[0].label),"NEXT");capture("39-full-time-overview");
  fd_copy(view.rows[0].label,sizeof(view.rows[0].label),"BACK TO MASTER LEAGUE");
  fd_copy(view.status,sizeof(view.status),view.rows[0].label);capture("40-full-time-master-league");
  const char *const returns[]={"BACK TO CUP","BACK TO LEAGUE","TOP TO MENU"};
  for(uint32_t i=0;i<3u;i++) {
    fd_copy(view.rows[0].label,sizeof(view.rows[0].label),returns[i]);
    fd_copy(view.status,sizeof(view.status),returns[i]);
    char name[64];snprintf(name,sizeof(name),"41-full-time-return-%u",i);capture(name);
  }
  view.action_count=3;
  fd_copy(view.rows[0].label,sizeof(view.rows[0].label),"GAME PLAN");
  fd_copy(view.rows[1].label,sizeof(view.rows[1].label),"GO TO OVERTIME");
  fd_copy(view.rows[2].label,sizeof(view.rows[2].label),"BACK TO CUP");
  fd_copy(view.status,sizeof(view.status),view.rows[2].label);
  for(uint32_t i=0;i<3u;i++) {
    view.focus=i;char name[64];snprintf(name,sizeof(name),"42-overtime-focus-%u",i);capture(name);
  }
  view.action_count=2;
  fd_copy(view.rows[0].label,sizeof(view.rows[0].label),"GO TO PENALTIES");
  fd_copy(view.rows[1].label,sizeof(view.rows[1].label),"BACK TO CUP");
  for(uint32_t i=0;i<2u;i++) {
    view.focus=i;char name[64];snprintf(name,sizeof(name),"43-penalties-focus-%u",i);capture(name);
  }
  view.action_count=1;view.focus=0;view.status[0]=0;
  fd_copy(view.rows[0].label,sizeof(view.rows[0].label),"NEXT");
  for(uint32_t side=0;side<2u;side++) {
    fd_copy(view.score[side],sizeof(view.score[side]),"--");
    for(uint32_t row=0;row<8u;row++)fd_copy(view.stats[side][row],sizeof(view.stats[side][row]),"--");
  }
  capture("44-results-missing-stats");
  screen_width=1920;screen_height=1080;capture("45-results-1080p");
  screen_width=1280;screen_height=720;
  base(FD_MENU);view.portrait_previous=0;view.portrait_current=1;view.portrait_mix=.5f;capture("24-portrait-crossfade");
  selector(1);view.sides[0].ready=1;view.sides[0].ready_mix=.5f;capture("25-ready-transition");
  screen_width=1920;screen_height=1080;hub();capture("26-hub-1080p");
  selector(1);capture("27-selector-1080p");
  printf("Maximum: %d / 4096 quads; %d / 384 draw records\n",max_quads,max_draws);
  return 0;
}
'''


def build_driver(source):
    # The common preview contains the exact ML draw helpers and GL recorder.
    base = shared.build_driver(source).split('static void capture(', 1)[0]
    base = '#include "stadium_catalog.h"\n#include "match_environment.h"\n' + base
    base = base.replace('#include <assert.h>', '#include <assert.h>\n#undef assert\n#define assert(c) do { if(!(c)) { fprintf(stderr,"assertion: %s:%d: %s\\n",__FILE__,__LINE__,#c); _Exit(97); } } while(0)')
    catalog = json.loads((ROOT / 'data/exhibition_team_catalog.json').read_text())
    teams = catalog['teams']
    def badge(term):
        return next(t['badge_slot'] for t in teams if term in t['display_name'])
    names = {'CHELSEA': 'CHELSEA', 'ARSENAL': 'ARSENAL', 'VILLA': 'ASTON VILLA',
             'BOURNEMOUTH': 'BOURNEMOUTH', 'LIVERPOOL': 'LIVERPOOL', 'UNITED': 'MANCHESTER UNITED',
             'WOLVES': 'WOLVERHAMPTON'}
    defines = '\n'.join(f'#define FD_BADGE_{key} {badge(term)}u' for key, term in names.items())
    english = next(c for c in catalog['categories'] if c['label'] == 'ENGLISH LEAGUE')
    defines += f"\n#define FD_BADGE_ENGLISH {english['badge_slot']}u\n"
    return base + '\n' + defines + (ROOT / 'source/frontdoor_overlay.inc').read_text() + '\n' + DRIVER


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', type=Path, default=ROOT / 'local-debug/frontdoor-v3-preview')
    parser.add_argument('--geometry-only', action='store_true')
    parser.add_argument('--animate', action='store_true', help='Render the production menu tween to an animated GIF')
    args = parser.parse_args()
    output = args.output.resolve();output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pes-frontdoor-preview-') as temporary:
        temp = Path(temporary)
        source = (ROOT / 'source/overlay.c').read_text()
        (temp / 'preview.c').write_text(build_driver(source))
        (temp / 'ue4_hooks.h').write_text((ROOT / 'source/ue4_hooks.h').read_text().replace('#include "so_util.h"', 'typedef struct so_module so_module;'))
        command = [shutil.which('cc') or shutil.which('gcc'), '-std=c11', '-O1',
                   '-I', str(temp), '-I', str(ROOT / 'source'), str(temp / 'preview.c'), '-lm', '-o', str(temp / 'preview.exe')]
        compile_result = subprocess.run(command, capture_output=True, text=True)
        if compile_result.returncode:
            print(compile_result.stderr);raise SystemExit(compile_result.returncode)
        run = subprocess.run([str(temp / 'preview.exe')], cwd=temp, check=True, capture_output=True, text=True, timeout=30)
        print(run.stdout)
        frames = sorted(p for p in temp.glob('*.json') if p.stem[:2].isdigit())
        motion_frames = sorted(temp.glob('motion-*.json'))
        pattern_frames = sorted(p for p in temp.glob('pattern-*.json') if p.stem != 'pattern-cycle-end')
        if not args.geometry_only:
            assets = shared.textures(temp)
            assets[70] = Image.open(ROOT / 'data/frontdoor_flat_v3.bin').convert('RGBA')
            assets[76] = Image.open(ROOT / 'data/frontdoor_panels_v2.bin').convert('RGBA')
            # Luminance mask matches the runtime texture, not an edited image.
            header = (ROOT / 'source/team_rating_star.h').read_text()
            coverage = bytes(int(v, 16) for v in re.findall(r'0x([0-9a-fA-F]{2})', header))
            assets[71] = Image.frombytes('L', (128, 128), coverage).convert('RGB')
            for i, name in enumerate(['exhibition', '2player', 'settings', 'credits']):
                assets[72+i] = Image.open(ROOT / 'data' / f'main_menu_portrait_{name}.bin').convert('RGBA')
            for path in frames:
                shared.rasterize(json.loads(path.read_text()), assets).save(output / path.with_suffix('.png').name)
            shared.write_gallery(output, frames)
            html = (output / 'index.html').read_text(encoding='utf-8')
            html = html.replace('Cup · News carousel direction', 'Flat Matchday · Full flow v3')
            html = html.replace('Cup UI review', 'Main flow UI review').replace('FootballNX / Design review 06', 'FootballNX / Flat Matchday v3')
            links = [('01-title', 'Title'), ('02-main-menu', 'Main Menu'), ('06-exhibition', 'Exhibition'),
                     ('09-select-league', 'Select League'), ('10-select-team-home', 'Select Team'),
                     ('12-teams-ready', 'Ready'), ('16-match-hub', 'Match Hub'), ('18-kits-home', 'Kits'), ('20-stadium', 'Stadium'),
                     ('37-half-time-overview', 'Half Time'), ('40-full-time-master-league', 'Full Time')]
            stems = [p.stem for p in frames]
            nav = '<nav aria-label="Flow utama">' + ''.join(f'<button data-frame="{stems.index(stem)}">{title}</button>' for stem, title in links) + '</nav>'
            html = re.sub(r'<nav aria-label="Flow utama">.*?</nav>', nav, html)
            html = html.replace('</main>', '<p class="meta">Ratings dan starting XI adalah data sintetis. Kit native tidak dimuat, sehingga preview menampilkan fallback yang jujur. Transisi dan input tidak diemulasikan oleh galeri.</p></main>')
            if args.animate:
                clips = [shared.rasterize(json.loads(p.read_text()), assets) for p in motion_frames]
                durations = [700 if i == 0 or i % 8 == 0 else 33 for i in range(len(clips))]
                clips[0].save(output / 'menu-focus-motion.gif', save_all=True, append_images=clips[1:],
                              duration=durations, loop=0, disposal=2, optimize=False)
                del clips
                clips = [shared.rasterize(json.loads(p.read_text()), assets) for p in pattern_frames]
                clips[0].save(output / 'menu-pattern-loop.gif', save_all=True, append_images=clips[1:],
                              duration=100, loop=0, disposal=2, optimize=False)
                html = html.replace('</main>', '<h2>Menu focus motion</h2><p class="meta">Tween 260 ms dari renderer produksi; urutan input sintetis, portrait ditahan agar gerak tile lebih jelas.</p><img src="menu-focus-motion.gif" alt="Menu kiri mengembang pada fokus dan mengecil ketika tidak aktif"></main>')
                html = html.replace('</main>', '<h2>Focused pattern loop</h2><p class="meta">Loop UV 6 detik, preview diambil 10 fps; runtime mengikuti frame rate game. Border dan teks tidak bergerak.</p><img src="menu-pattern-loop.gif" alt="Pattern biru bergerak loop di dalam tile aktif"></main>')
            (output / 'index.html').write_text(html, encoding='utf-8')
        for path in frames:shutil.copy2(path, output / path.name)
        motion_output = output / 'motion';motion_output.mkdir(exist_ok=True)
        for path in [*motion_frames, *temp.glob('retarget-*.json'), *temp.glob('pattern-*.json')]:
            shutil.copy2(path, motion_output / path.name)
        sources = ['source/overlay.c', 'source/frontdoor_overlay.inc', 'source/master_league_overlay.inc', 'data/frontdoor_flat_v3.bin', 'data/frontdoor_panels_v2.bin']
        (output / 'provenance.json').write_text(json.dumps({
            'description': 'Production C presentation renderer; synthetic state; no game runtime, native lineup or saves',
            'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources},
            'frames': [p.with_suffix('.png').name for p in frames],
            'validation': run.stdout.splitlines()[-1]}, indent=2) + '\n')
    print(output)


if __name__ == '__main__':main()

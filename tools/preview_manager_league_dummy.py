"""Preview the Switch dummy's actual C layout and input flow, without game data."""
from pathlib import Path
import argparse
import fnmatch
import hashlib
import json
import shutil
import subprocess
import tempfile
from PIL import Image
import preview_frontdoor as frontdoor
import preview_cup as shared

ROOT=Path(__file__).resolve().parents[1]
DRIVER=r'''
#include "manager_league_dummy.h"
#include <time.h>
/* Preview-only wall clock. The production implementation is compiled intact
 * against this fixed clock so every visual review has the same synthetic tape. */
int md_preview_clock_gettime(clockid_t id,struct timespec *out) {
  (void)id;out->tv_sec=1793015700;out->tv_nsec=0;return 0;
}
static void capture(const char *name,MdPage expected) {
  MdView observed;manager_dummy_view(&observed);
  if(expected!=(MdPage)99)assert(observed.page==expected);
  static GLfloat verts[4096*24+8];int quads=0;MasterLeagueRender ui;
  for(int i=4096*24;i<4096*24+8;i++)verts[i]=12345;
  if(expected==(MdPage)99) {
    FrontdoorView menu={0};menu.page=FD_MENU;menu.focus=2;menu.menu_weights[2]=1;
    menu.portrait_previous=menu.portrait_current=nx_menu_portrait(2);menu.portrait_mix=1;
    frontdoor_emit(&ui,&menu,verts,&quads);
  } else {manager_dummy_emit(&ui,verts,&quads);if(strncmp(name,"motion",6)){preview_ticks+=200000000ull;quads=0;manager_dummy_emit(&ui,verts,&quads);}}
  assert(quads<4096 && ui.draw_count<384);
  for(int i=4096*24;i<4096*24+8;i++)assert(verts[i]==12345);
  for(int i=0;i<quads*24;i+=4)assert(isfinite(verts[i]) && isfinite(verts[i+1]) && fabsf(verts[i])<=1.002f && fabsf(verts[i+1])<=1.002f);
  char path[128];snprintf(path,sizeof(path),"%s.json",name);frame=fopen(path,"w");assert(frame);
  fprintf(frame,"[");draw_count=0;memset(uniforms,0,sizeof(uniforms));bound_texture=0;
  active_quads=quads;active_vertices=verts;master_league_draw(&ui);master_league_draw_layer(&ui,1);fprintf(frame,"]");fclose(frame);
  printf("%s: %d quads / %u draws\n",name,quads,ui.draw_count);
}
static void dashboard_action(uint32_t section,uint32_t target) {
  MdView v;manager_dummy_view(&v);
  for(uint32_t i=0;i<8 && v.page!=MD_DASHBOARD;i++){manager_dummy_pad(1);manager_dummy_view(&v);}
  assert(v.page==MD_DASHBOARD);
  while(v.focus>=2){manager_dummy_pad(1024);manager_dummy_view(&v);}
  if(v.focus==1)manager_dummy_pad(4096);
  manager_dummy_view(&v);
  for(uint32_t i=0;i<4 && v.tab!=section;i++){manager_dummy_pad(v.tab>section ? 16 : 128);manager_dummy_view(&v);}
  assert(v.tab==section);
  if(target==1)manager_dummy_pad(8192);
  else if(target>=2){manager_dummy_pad(2048);for(uint32_t i=2;i<target;i++)manager_dummy_pad(8192);}
  manager_dummy_view(&v);assert(v.focus==target);manager_dummy_pad(2);
}
static void select_broadcast(uint32_t fixture) {
  MdView v;manager_dummy_view(&v);assert(v.page==MD_SCHEDULE && !v.focus && fixture<v.total);
  for(uint32_t i=0;i<fixture/2u;i++)manager_dummy_pad(2048);
  if(fixture%2u)manager_dummy_pad(8192);
  manager_dummy_view(&v);assert(v.focus==fixture);manager_dummy_pad(2);
}
int main(void) {
  initialize_gl();gl.master_league_pearl_tex=77;gl.frontdoor_flat_tex=70;gl.frontdoor_panels_tex=76;
  for(uint32_t i=0;i<4;i++)gl.main_menu_portrait_tex[i]=72+i;
  FILE *font=fopen("font.pgm","wb");assert(font);
  fprintf(font,"P5\n%d %d\n255\n",EFOOTBALL_FONT_ATLAS_W,EFOOTBALL_FONT_ATLAS_H);
  fwrite(efootball_font_atlas_alpha,1,sizeof(efootball_font_atlas_alpha),font);fclose(font);
  gl.manager_unknown_club_tex=78;
  manager_dummy_open();manager_dummy_tick_at(1793015700000ULL);capture("00-main-menu",(MdPage)99);capture("01-registration",MD_REGISTER);
  manager_dummy_pad(2);capture("02-league-selection",MD_LEAGUES);manager_dummy_pad(2);capture("03-club-selection",MD_CLUB);
  manager_dummy_pad(2);manager_dummy_name_result("Androswitch FC");manager_dummy_pad(2048);manager_dummy_name_result("androswitch_27");
  manager_dummy_pad(2048);manager_dummy_name_result("Preview-Only-Password");capture("04-account",MD_NAME);
  manager_dummy_pad(8);capture("05-tutorial",MD_DASHBOARD);for(int i=0;i<3;i++)manager_dummy_pad(2);capture("06-dashboard",MD_DASHBOARD);
  MdSave save;manager_dummy_copy_save(&save);
  dashboard_action(1,0);capture("12-team-info",MD_TEAM_INFO);manager_dummy_pad(2);capture("13-player-profile",MD_PLAYER_INFO);
  dashboard_action(1,2);capture("19-player-shop",MD_SHOP);manager_dummy_pad(2);capture("20-pack-pool",MD_PACK);
  manager_dummy_pad(2);manager_dummy_tick_at(1793015700600ULL);capture("20a-pack-opening",MD_PACK_OPENING);
  manager_dummy_tick_at(1793015704100ULL);capture("20b-pack-select",MD_PACK_SELECT);manager_dummy_pad(2);manager_dummy_pad(8192);manager_dummy_pad(2);
  while(1){MdView v;manager_dummy_view(&v);if(v.focus==v.pack_pool)break;manager_dummy_pad(2048);}capture("20c-pack-confirm",MD_PACK_SELECT);
  manager_dummy_pad(2);capture("21-pack-result",MD_PACK_RESULT);
  uint32_t goal_fixture=0,first_goal=0,first_save=0,first_sub=0;
  for(uint32_t f=0;f<MD_FIXTURES && !first_goal;f++)
    for(uint32_t i=0;i<manager_dummy_event_count(&save.fixtures[f]);i++)
      if(save.fixtures[f].events[i].kind==MD_GOAL) {
        goal_fixture=f;first_goal=save.fixtures[f].events[i].at_ms;break;
      }
  assert(first_goal);
  for(uint32_t i=0;i<manager_dummy_event_count(&save.fixtures[goal_fixture]);i++) {
    const MdEvent *e=&save.fixtures[goal_fixture].events[i];
    if(e->kind==MD_SAVE && !first_save)first_save=e->at_ms;
    if(e->kind==MD_SUB && !first_sub)first_sub=e->at_ms;
  }
  manager_dummy_tick_at(save.fixtures[goal_fixture].kickoff_ms+first_goal+500);dashboard_action(2,2);capture("22-match-centre",MD_SCHEDULE);
  select_broadcast(goal_fixture);capture("30-live-goal",MD_WATCH);
  manager_dummy_tick_at(save.fixtures[goal_fixture].kickoff_ms+first_save+30);capture("31-live-save",MD_WATCH);
  manager_dummy_tick_at(save.fixtures[goal_fixture].kickoff_ms+first_sub+700);capture("32-live-substitution",MD_WATCH);
  manager_dummy_tick_at(save.fixtures[goal_fixture].kickoff_ms+manager_dummy_duration(&save.fixtures[goal_fixture]));manager_dummy_pad(2);manager_dummy_pad(8192);capture("33-replay",MD_WATCH);
  for(uint32_t i=0;i<MD_FIXTURES;i++)if(!save.fixtures[i].home || !save.fixtures[i].away) {
    manager_dummy_tick_at(save.fixtures[i].kickoff_ms+25000);dashboard_action(0,2);capture("40d-week-live",MD_CALENDAR);break;
  }
  manager_dummy_tick_at(save.fixtures[0].kickoff_ms+3u*MD_DEMO_DAY_MS);dashboard_action(0,3);capture("10-standings",MD_TABLE);
  for(int i=0;i<6;i++)manager_dummy_pad(2048);capture("11-standings-page-two",MD_TABLE);
  dashboard_action(0,2);capture("40-week-schedule",MD_CALENDAR);
  for(uint32_t i=0;i<6;i++)manager_dummy_pad(1024);capture("40a-week-preparation",MD_CALENDAR);
  for(uint32_t i=0;i<4;i++)manager_dummy_pad(2048);capture("40b-week-match-days",MD_CALENDAR);
  manager_dummy_pad(2048);manager_dummy_pad(2048);capture("40c-week-result",MD_CALENDAR);
  dashboard_action(1,4);capture("41-other-clubs",MD_TEAMS_PAGE);
  dashboard_action(2,1);capture("42-overall-ranking",MD_OVERALL);
  manager_dummy_pad(1);manager_dummy_pad(2048);manager_dummy_pad(4096);capture("22a-competition",MD_DASHBOARD);
  manager_dummy_pad(2);capture("42b-overall-ranking-card",MD_OVERALL);
  dashboard_action(0,1);capture("43-news",MD_NEWS);
  dashboard_action(2,4);capture("44-league-guide",MD_RULES);
#ifdef MD_ANIMATED
  dashboard_action(1,2);
  for(uint32_t i=0;i<28;i++){char name[48];snprintf(name,sizeof(name),"motion-focus-%02u",i);preview_ticks+=500000000;capture(name,MD_SHOP);}
  manager_dummy_pad(8192);manager_dummy_pad(8192);manager_dummy_pad(2);manager_dummy_pad(2);
  MdView opening;manager_dummy_view(&opening);assert(opening.page==MD_PACK_OPENING);
  for(uint32_t i=0;i<44;i++){char name[48];snprintf(name,sizeof(name),"motion-open-%02u",i);preview_ticks+=100000000;
    manager_dummy_tick_at(opening.now_ms+i*100);capture(name,i<34 ? MD_PACK_OPENING : MD_PACK_SELECT);}
#endif
#ifdef MD_BROADCAST_ANIMATED
  manager_dummy_tick_at(save.fixtures[0].kickoff_ms);dashboard_action(2,2);manager_dummy_pad(2);
  for(uint32_t i=0;i<46;i++){char name[48];snprintf(name,sizeof(name),"motion-kickoff-%02u",i);
    manager_dummy_tick_at(save.fixtures[0].kickoff_ms+i*200u);capture(name,MD_WATCH);}
  manager_dummy_tick_at(save.fixtures[goal_fixture].kickoff_ms+first_goal-4500u);dashboard_action(2,2);select_broadcast(goal_fixture);
  for(uint32_t i=0;i<46;i++){char name[48];snprintf(name,sizeof(name),"motion-goal-%02u",i);
    manager_dummy_tick_at(save.fixtures[goal_fixture].kickoff_ms+first_goal-4500u+i*200u);capture(name,MD_WATCH);}
#endif
  MdView final_view;manager_dummy_view(&final_view);
  for(uint32_t i=0;i<8 && final_view.page!=MD_DASHBOARD;i++){manager_dummy_pad(1);manager_dummy_view(&final_view);}
  assert(final_view.page==MD_DASHBOARD);manager_dummy_pad(8);capture("07-logout",MD_LOGOUT);
  manager_dummy_pad(4096);manager_dummy_pad(2);capture("08-login-register",MD_REGISTER);
  manager_dummy_pad(2);capture("09-login",MD_LOGIN);
  manager_dummy_name_result("androswitch_27");manager_dummy_pad(2048);manager_dummy_name_result("Preview-Only-Password");
  manager_dummy_pad(2048);manager_dummy_pad(2);capture("09b-login-return",MD_DASHBOARD);
  return 0;
}
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',nargs='?',type=Path,default=ROOT/'local-debug/manager-league-phases-v93/previews')
    parser.add_argument('--geometry-only',action='store_true')
    parser.add_argument('--frames',nargs='+',help='Optional output names or glob patterns; all C capture checks still run')
    parser.add_argument('--animate-shop',action='store_true',help='Record actual C focus and opening frames as GIF previews')
    parser.add_argument('--native-assets',action='store_true',help='Use ignored exact paired catalog, crests and portraits for local visual review')
    parser.add_argument('--animate-broadcast',action='store_true',help='Capture actual kickoff and goal/restart C timelines')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    overlay=(ROOT/'source/overlay.c').read_text(encoding='utf8')
    base=frontdoor.build_driver(overlay).removesuffix(frontdoor.DRIVER)
    ml=(ROOT/'source/master_league_overlay.inc').read_text()
    helpers='\n'.join(shared.function(ml,n) for n in ['ml_ui_minirows','ml_ui_feed_summary','ml_ui_feature','ml_ui_hub','ml_ui_chrome','ml_ui_primary','ml_ui_table','ml_ui_calendar'])
    helpers+='\ntypedef struct {uint32_t serial;uint64_t began;} MlUiMotion;\n'+shared.function(ml,'ml_ui_navigation_slide')
    base=base.replace('static GLuint gameplan_portrait_texture(uint32_t id) { (void)id;return 0; }','static GLuint gameplan_portrait_texture(uint32_t id) {return id ? 200000u+id : 0;}')
    if args.native_assets:base+='\nint ml_add_player(MasterLeague *c,uint32_t team,const MlPlayer *p){(void)c;(void)team;(void)p;return 0;}\n'
    source=base+'\n'+shared.function(overlay,'emit_segment')+'\n'+helpers+'\n#include "manager_league_dummy.h"\n'+(ROOT/'source/manager_league_dummy_overlay.inc').read_text()+'\n'+DRIVER
    with tempfile.TemporaryDirectory(prefix='manager-dummy-preview-') as temp:
        work=Path(temp);(work/'preview.c').write_text(source,encoding='utf8')
        if not args.native_assets:source=source.replace('#include \"manager_league_dummy.h\"','#include \"manager_league_dummy.h\"\n#include \"manager_league_catalog_fixture.inc\"',1);(work/'preview.c').write_text(source,encoding='utf8')
        (work/'ue4_hooks.h').write_text((ROOT/'source/ue4_hooks.h').read_text().replace('#include "so_util.h"','typedef struct so_module so_module;'))
        exe=work/'preview.exe'
        native=[str(ROOT/'source/master_league_catalog.c'),'-DML_CATALOG_INCLUDE=\"'+(ROOT/'local-debug/master-league-v1/master_league_catalog_generated.inc').as_posix()+'\"','-ffunction-sections','-Wl,--gc-sections'] if args.native_assets else []
        if args.animate_shop:native+=['-DMD_ANIMATED=1']
        if args.animate_broadcast:native+=['-DMD_BROADCAST_ANIMATED=1']
        result=subprocess.run([shutil.which('gcc'),'-std=c11','-O1','-D_POSIX_C_SOURCE=200809L',
          '-Dclock_gettime=md_preview_clock_gettime','-I',str(work),'-I',str(ROOT/'source'),'-I',str(ROOT/'tests'),
          str(work/'preview.c'),str(ROOT/'source/manager_league_dummy.c'),str(ROOT/'source/manager_league_motion.c'),str(ROOT/'source/manager_league_plan.c'),str(ROOT/'source/gameplan_preset.c'),*native,'-lm','-pthread','-o',str(exe)],capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stderr)
        run=subprocess.run([str(exe)],cwd=work,capture_output=True,text=True,timeout=40)
        if run.returncode:raise RuntimeError(run.stdout+'\n'+run.stderr)
        print(run.stdout)
        paths=sorted(p for p in work.glob('*.json') if not args.frames or any(fnmatch.fnmatch(p.stem,pattern) for pattern in args.frames))
        if not args.geometry_only:
            assets=shared.textures(work)
            assets[77]=Image.open(ROOT/'data/master_league_pearl_v2.bin').convert('RGBA')
            assets[70]=Image.open(ROOT/'data/frontdoor_flat_v3.bin').convert('RGBA')
            assets[76]=Image.open(ROOT/'data/frontdoor_panels_v2.bin').convert('RGBA')
            placeholder=ROOT/'local-debug/manager-league-v94/assets/emblem-blankTeam_l.png'
            if args.native_assets:
                from build_fl26_cup_catalog import index_cpk,decoded_member
                from io import BytesIO
                assets[78]=Image.open(placeholder).convert('RGBA')
                archive=ROOT/'local-debug/native-club-presentation-2026-10-05-v1/LooseCpk/dt241_mobile_all.cpk'
                index,base_offset=index_cpk(archive)
                portrait_ids={d['texture']-200000 for p in paths for d in json.loads(p.read_text()) if d['texture']>=200000}
                for portrait in portrait_ids:assets[portrait+200000]=Image.open(BytesIO(decoded_member(archive,index,base_offset,f'common/player/{portrait}.png'))).convert('RGBA')
            else:
                # Public previews retain neutral portrait tiles, explicitly synthetic.
                from PIL import ImageDraw
                for portrait in range(30000,30256):
                    tile=Image.new('RGBA',(128,128),(0,0,0,0));draw=ImageDraw.Draw(tile);draw.ellipse((42,15,86,61),fill='#b7c6d9');draw.rounded_rectangle((23,65,105,125),20,fill='#b7c6d9');assets[portrait+200000]=tile

            for i,name in enumerate(['exhibition','2player','settings','credits']):
                assets[72+i]=Image.open(ROOT/'data'/f'main_menu_portrait_{name}.bin').convert('RGBA')
            for path in paths:shared.rasterize(json.loads(path.read_text()),assets).convert('RGB').save(out/(path.stem+'.png'))
            if args.animate_shop:
                for kind,duration in [('focus',500),('open',100)]:
                    frames=[Image.open(out/(p.stem+'.png')).resize((960,540),Image.Resampling.LANCZOS) for p in paths if p.stem.startswith('motion-'+kind)]
                    if frames:frames[0].save(out/('pack-'+kind+'.gif'),save_all=True,append_images=frames[1:],duration=duration,loop=0 if kind=='focus' else 1)

            if args.animate_broadcast:
                for kind in ('kickoff','goal'):
                    frames=[Image.open(out/(p.stem+'.png')).resize((960,540),Image.Resampling.LANCZOS) for p in paths if p.stem.startswith('motion-'+kind)]
                    if frames:frames[0].save(out/('broadcast-'+kind+'.gif'),save_all=True,append_images=frames[1:],duration=200,loop=0)

            animated=''.join(f'<article><h2>{p.stem}</h2><img src="{p.name}" alt="{p.stem}"></article>' for p in sorted(out.glob('*.gif')))
            cards=animated+''.join(f'<article><h2>{p.stem}</h2><img src="{p.stem}.png" alt="{p.stem}"></article>' for p in paths if not p.stem.startswith('motion-'))
            (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Manager League dummy / C renderer</title><style>body{font:16px system-ui;background:#eaf0f5;color:#192535;margin:30px}article{margin:24px 0}img{width:100%;max-width:1280px;border-radius:12px}h2{font-size:18px}</style><h1>Manager League / native C previews</h1><p>Actual Switch presentation geometry. Offline synthetic fixtures; host previews, not device captures.</p>'+cards,encoding='utf8')
        for path in paths:shutil.copy2(path,out/path.name)
        sources=['source/manager_league_motion.c','source/manager_league_profile.inc','source/manager_league_auth.h','source/manager_league_archive.inc','source/master_league_frontend.h','source/manager_league_dummy.c','source/manager_league_dummy.h','source/manager_league_dummy_overlay.inc','source/manager_league_watch_overlay.inc','source/frontdoor_overlay.inc','source/master_league_overlay.inc','source/competition_hub_navigation.h','source/overlay.c','tools/preview_manager_league_dummy.py','tools/preview_cup.py','tools/preview_frontdoor.py']
        (out/'PROVENANCE.json').write_text(json.dumps({'kind':'actual_C_renderer_host_preview','fixed_host_epoch_ms':1793015700000,'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'validation':run.stdout.splitlines(),'device_accepted':False,'native_assets':args.native_assets},indent=2)+'\n')
    print(out)

if __name__=='__main__':main()

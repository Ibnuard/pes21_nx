"""Preview the League broadcast UI using production C geometry and synthetic seasons.

No game runtime is loaded. Saves stay in a temporary directory. Outputs are
for visual review, not Switch captures. Requires a host C compiler and Pillow.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import preview_cup as shared
from PIL import Image

ROOT = shared.ROOT


def build_driver(source):
    base = shared.build_driver(source).split('static void capture(', 1)[0]
    # Failed host assertions exit immediately, avoiding OS crash-report dialogs.
    base=base.replace('#include <assert.h>', '#include <assert.h>\n#undef assert\n#define assert(c) do { if(!(c)) { fprintf(stderr,"assertion: %s:%d: %s\\n",__FILE__,__LINE__,#c); _Exit(97); } } while(0)')
    capture=r'''
static void capture(const char *name) {
  static GLfloat verts[16000*24];int quads=0;MasterLeagueRender ui;
  const LeagueTournament *live=competition_frontend_league_tournament();
  const LeagueTournament before=live?*live:(LeagueTournament){0};
  league_news_emit(&ui,competition_frontend_state(),verts,&quads);
  preview_ticks+=200000000ull;quads=0;
  league_news_emit(&ui,competition_frontend_state(),verts,&quads);
  assert(quads<4096 && ui.draw_count<380);
  assert(!live || !memcmp(&before,live,sizeof(before)));
  if(competition_frontend_league_page()==LEAGUE_PAGE_TABLE && live && live->team_count) {
    uint8_t order[LEAGUE_MAX_TEAMS];league_tournament_ranked_slots(live,order);
    const uint32_t start=competition_frontend_league_table_page()*ML_TABLE_PAGE_ROWS;
    uint32_t expected=0u,drawn=0u;
    for(uint32_t r=start;r<live->team_count && r<start+ML_TABLE_PAGE_ROWS;r++)
      expected+=league_ui_owner(live->standings[order[r]].team)!=0u;
    for(uint32_t i=0;i<ui.draw_count;i++) {
      const MlDraw *d=&ui.draws[i];
      drawn+=d->kind==0 && d->color[0]==.03f && d->color[1]==.42f && d->color[2]==.70f;
    }
    assert(drawn==expected);
  }
  for(uint32_t i=0;i<ui.view.helper_count;i++)
    ml_ui_image(&ui,switch_button_texture(ui.view.helper_key[i]),0,
      ui.helper_centers[i]-.0444f*.5625f*.5f,.9625f-.0222f,.0444f*.5625f,.0444f,verts,&quads);
  char filename[128];snprintf(filename,sizeof(filename),"%s.json",name);
  frame=fopen(filename,"w");assert(frame);fprintf(frame,"[");draw_count=0;
  memset(uniforms,0,sizeof(uniforms));bound_texture=0;active_quads=quads;active_vertices=verts;
  master_league_draw(&ui);master_league_draw_layer(&ui,1);
  fprintf(frame,"]");fclose(frame);
  printf("%s: %d quads, %d draws\n",name,quads,draw_count);
}
'''
    return base+'\n'+(ROOT/'source/league_overlay.inc').read_text()+'\n'+capture+'\n'+DRIVER


DRIVER=r'''
enum {B=1u<<0,A=1u<<1,Y=1u<<2,X=1u<<3,L=1u<<4,R=1u<<7,UP=1u<<10,DOWN=1u<<11,LEFT=1u<<12,RIGHT=1u<<13};
static void press(uint32_t key) {
  competition_frontend_pad_event(0,0);competition_frontend_pad_event(key,0);competition_frontend_pad_event(0,0);
}
static void enter_league(void) {
  competition_frontend_close();competition_frontend_finish_close();competition_frontend_open_modes();
  competition_frontend_pad_event(0,0);press(DOWN);press(A);
  assert(competition_frontend_state()==COMPETITION_FRONTEND_LEAGUE_LANDING);
}
static void focus_hub(uint32_t target) {
  assert(competition_frontend_state()==COMPETITION_FRONTEND_LEAGUE_HUB);
  if(competition_frontend_cup_general_open())press(B);
  if(competition_frontend_league_page()!=LEAGUE_PAGE_HOME)press(B);
  const int top=target==5u || target==2u;
  const uint32_t current=competition_frontend_focus();
  if(top!=(current==5u || current==2u))press(UP);
  for(uint32_t i=0;i<4u && competition_frontend_focus()!=target;i++)press(RIGHT);
  assert(competition_frontend_focus()==target);
}
static void custom_league(uint32_t teams,int standing,int home_away,uint32_t players) {
  enter_league();press(A);press(LEFT);press(DOWN);press(DOWN);
  for(uint32_t i=0;i<32u && competition_frontend_league_team_count()>teams;i++)press(LEFT);
  for(uint32_t i=0;i<32u && competition_frontend_league_team_count()<teams;i++)press(RIGHT);
  assert(competition_frontend_league_team_count()==teams);
  press(UP);for(uint32_t i=1;i<players;i++)press(RIGHT);press(DOWN);press(DOWN);
  if(home_away)press(RIGHT);press(DOWN);if(standing)press(RIGHT);press(DOWN);press(A);
  assert(competition_frontend_state()==COMPETITION_FRONTEND_LEAGUE_HUB);
  press(A);press(X);assert(competition_draft_ready(competition_frontend_league_draft()));press(B);
}
static void play_match(void) {
  focus_hub(2);press(A);assert(competition_frontend_take_action()==COMPETITION_ACTION_LEAGUE_FIXTURE);
  uint32_t home=0,away=0;assert(competition_frontend_league_match_teams(&home,&away));
  competition_frontend_league_handoff_result(1);competition_frontend_league_match_result(2,0);
  competition_frontend_league_restore_after_match();competition_frontend_pad_event(0,0);
}
int main(void) {
  setvbuf(stdout,NULL,_IONBF,0);initialize_gl();
  gl.league_news_tex=60;gl.league_pearl_tex=61;gl.competition_actions_tex=62;gl.league_header_tex=63;
  FILE *font=fopen("font.pgm","wb");assert(font);
  fprintf(font,"P5\n%d %d\n255\n",EFOOTBALL_FONT_ATLAS_W,EFOOTBALL_FONT_ATLAS_H);
  fwrite(efootball_font_atlas_alpha,1,sizeof(efootball_font_atlas_alpha),font);fclose(font);
  enter_league();capture("01-new-continue");press(DOWN);capture("02-continue-focus");press(A);capture("03-load-empty");press(B);press(A);
  capture("04-league-settings");press(DOWN);press(RIGHT);capture("05-two-player-settings");
  while(competition_frontend_focus()!=5u)press(DOWN);capture("06-settings-create");press(A);capture("07-hub-empty");
  press(A);press(A);competition_frontend_cup_team_picker_result(101u);
  press(DOWN);press(A);competition_frontend_cup_team_picker_result(102u);press(X);
  assert(competition_draft_ready(competition_frontend_league_draft()));capture("08-participants");press(Y);capture("09-participants-page2");press(B);
  capture("10-hub-ready");focus_hub(2);capture("11-next-match");press(R);capture("12-news-matchday");press(R);capture("13-news-table");press(R);capture("14-news-title-race");
  focus_hub(4);press(A);capture("15-standings");press(R);capture("16-standings-page2");press(B);
  focus_hub(5);press(A);capture("17-match-centre");press(Y);capture("18-fixtures-page2");press(R);capture("19-next-matchday");press(X);capture("20-scorers-empty");press(B);
  focus_hub(1);press(A);capture("21-general-settings");for(int i=0;i<5;i++)press(DOWN);capture("22-general-settings-page2");press(B);
  focus_hub(3);press(A);capture("23-save-slots");press(A);preview_ticks+=200000000ull;capture("24-saved-toast");
  press(A);press(A);assert(competition_frontend_confirmation_active());capture("55-overwrite-cancel");
  press(LEFT);capture("56-overwrite-selected");press(B);press(B);
  press(B);assert(competition_frontend_confirmation_active());capture("57-leave-unsaved-league");press(B);
  enter_league();press(DOWN);press(A);capture("25-continue-saved");press(A);capture("26-loaded-hub");
  focus_hub(2);press(A);assert(competition_frontend_take_action()==COMPETITION_ACTION_LEAGUE_FIXTURE);
  uint32_t home=0,away=0;assert(competition_frontend_league_match_teams(&home,&away));
  LeagueScorer scorer={.base_id=900001u,.portrait_id=0,.team=home,.goals=2};snprintf(scorer.name,sizeof(scorer.name),"SYNTHETIC PLAYER");
  competition_frontend_league_handoff_result(1);competition_frontend_league_match_result_with_scorers(2,0,&scorer,1);
  competition_frontend_league_restore_after_match();competition_frontend_pad_event(0,0);capture("27-matchday-result");
  focus_hub(5);press(A);press(X);capture("28-top-scorers");focus_hub(4);press(A);capture("29-table-after-match");press(R);capture("54-table-movement-page2");
  focus_hub(0);press(A);assert(!competition_frontend_league_teams_editing());capture("30-participants-locked");
  custom_league(4,0,0,1);
  for(uint32_t i=0;i<64u && competition_frontend_league_tournament()->phase==LEAGUE_PHASE_TABLE;i++)play_match();
  assert(competition_frontend_league_tournament()->phase==LEAGUE_PHASE_KNOCKOUT);capture("31-knockout-hub");
  focus_hub(4);press(A);capture("32-qualified-table");press(Y);capture("33-knockout-bracket");press(R);capture("34-final-upcoming");
  for(uint32_t i=0;i<16u && competition_frontend_league_tournament()->phase!=LEAGUE_PHASE_COMPLETE;i++)play_match();
  assert(competition_frontend_league_tournament()->phase==LEAGUE_PHASE_COMPLETE);capture("35-knockout-champions");
  focus_hub(2);press(A);capture("36-final-champion-atlas");focus_hub(3);press(A);capture("37-save-complete");press(A);
  custom_league(4,1,0,1);
  for(uint32_t i=0;i<64u && competition_frontend_league_tournament()->phase!=LEAGUE_PHASE_COMPLETE;i++)play_match();
  assert(competition_frontend_league_tournament()->phase==LEAGUE_PHASE_COMPLETE);capture("38-standings-champions");focus_hub(2);press(A);capture("39-final-league-table");
  custom_league(32,0,1,8);capture("40-32-teams-eight-players");focus_hub(0);press(A);capture("41-eight-player-badges");
  focus_hub(4);press(A);capture("51-table-eight-players-page1");press(R);capture("52-table-eight-players-page2");
  press(R);press(R);press(R);press(R);capture("53-table-last-page");
  press(L);press(L);capture("42-table-page4");focus_hub(5);press(A);capture("43-large-matchday");
  custom_league(3,1,1,2);focus_hub(0);press(A);capture("44-three-participants");focus_hub(5);press(A);capture("45-odd-team-matchday");
  custom_league(2,0,0,1);play_match();assert(competition_frontend_league_tournament()->phase==LEAGUE_PHASE_KNOCKOUT);
  focus_hub(4);press(A);press(Y);capture("46-two-team-final");
  custom_league(4,0,1,1);
  for(uint32_t i=0;i<64u && competition_frontend_league_tournament()->phase==LEAGUE_PHASE_TABLE;i++)play_match();
  assert(competition_frontend_league_tournament()->phase==LEAGUE_PHASE_KNOCKOUT);
  focus_hub(4);press(A);press(Y);capture("47-knockout-home-away");play_match();capture("48-return-leg-hub");
  focus_hub(4);press(A);press(Y);capture("49-first-leg-result");play_match();
  focus_hub(4);press(A);press(Y);press(L);capture("50-aggregate-result");
  custom_league(19,1,0,1);focus_hub(0);press(A);capture("58-nineteen-participants");
  press(Y);press(Y);capture("59-participants-last-page");
  return 0;
}
'''



def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',nargs='?',type=Path,default=ROOT/'local-debug/league-news-preview')
    parser.add_argument('--geometry-only',action='store_true',help='Skip PNG rasterization for layout regression checks')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    source=(ROOT/'source/overlay.c').read_text()
    with tempfile.TemporaryDirectory(prefix='pes-league-preview-') as temporary:
        temp=Path(temporary)
        generated=build_driver(source)
        (temp/'preview.c').write_text(generated)
        (temp/'ue4_hooks.h').write_text((ROOT/'source/ue4_hooks.h').read_text().replace('#include "so_util.h"','typedef struct so_module so_module;'))
        shutil.copy2(ROOT/'source/competition_frontend.c',temp/'competition_frontend.c')
        core=['competition_entry_draft.c','cup_tournament.c','cup_save.c','league_tournament.c','league_save.c','master_league.c','master_league_save.c','master_league_frontend.c','master_league_catalog.c','gameplan_preset.c']
        result=subprocess.run(['cc','-std=c11','-O1','-Wno-constant-logical-operand','-I',str(temp),'-I',str(ROOT/'source'),str(temp/'preview.c'),str(temp/'competition_frontend.c'),*[str(ROOT/'source'/n) for n in core],'-lm','-o',str(temp/'preview')],capture_output=True,text=True)
        if result.returncode:
            (output/'compile-error.txt').write_text(result.stderr)
            (output/'driver-debug.c').write_text(generated)
            print(result.stderr);raise SystemExit(result.returncode)
        subprocess.run([str(temp/'preview')],cwd=temp,check=True,timeout=45)
        for name in ['compile-error.txt','driver-debug.c']:
            (output/name).unlink(missing_ok=True)
        assets=shared.textures(temp)
        for tex,name in {60:'league_news_v1',61:'league_pearl_v2',62:'competition_actions_v1',63:'league_header_v2'}.items():
            assets[tex]=Image.open(ROOT/'data'/f'{name}.bin').convert('RGBA')
        frames=sorted(temp.glob('*.json'))
        for path in frames:
            if not args.geometry_only:
                shared.rasterize(json.loads(path.read_text()),assets).save(output/path.with_suffix('.png').name)
            shutil.copy2(path,output/path.name)
        shared.write_gallery(output,frames)
        html=(output/'index.html').read_text(encoding='utf-8').replace('Cup · News carousel direction','League · Season broadcast').replace('FootballNX / Design review 06','FootballNX / League redesign').replace('Cup UI review','League UI review')
        html=re.sub(r'<nav aria-label="Flow utama">.*?</nav>','<nav aria-label="Flow utama"><button data-frame="0">New / Continue</button><button data-frame="3">Settings</button><button data-frame="10">League Hub</button><button data-frame="7">Participants</button><button data-frame="14">Standings</button><button data-frame="16">Match Centre</button><button data-frame="27">Top Scorers</button><button data-frame="32">Knockout</button><button data-frame="35">Champions</button></nav>',html)
        html=html.replace('</main>','<p class="meta">Logo liga dan portrait pemain mengikuti fallback native karena aset runtime tidak disertakan di Git. Preview memakai data musim sintetis dan save sementara.</p></main>')
        (output/'index.html').write_text(html,encoding='utf-8')
        (output/'provenance.json').write_text(json.dumps({'description':'Production League broadcast geometry, synthetic seasons, temporary saves; no game runtime or device capture','source_sha256':{n:hashlib.sha256((ROOT/'source'/n).read_bytes()).hexdigest() for n in ['overlay.c','league_overlay.inc','competition_frontend.c']},'runtime_assets':'Mapped LeagueLogos and player portraits unavailable; native fallback rendering used','frames':[p.with_suffix('.png').name for p in frames]},indent=2)+'\n')
    print(output)

if __name__=='__main__':main()

"""Exercise the production Cup/League leg resolver without unrelated UI flows."""
from pathlib import Path
import shutil
import subprocess

import pytest
from test_gameplan_editor import function

ROOT=Path(__file__).resolve().parents[1]


def test_actual_frontend_aggregate_contexts_and_previous_leg_storage(tmp_path):
    compiler=shutil.which('gcc') or shutil.which('clang')
    if not compiler:pytest.skip('host C compiler required')
    actual=function((ROOT/'source/competition_frontend.c').read_text(encoding='utf8'),
                    'competition_frontend_match_leg')
    source=r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include "competition_frontend.h"
#include "scoreboard_aggregate_policy.h"
static uint32_t cup_match_active,cup_tournament_valid,cup_pending_round;
static uint32_t cup_pending_index,cup_match_swapped;
static uint32_t league_match_active,league_tournament_valid,league_pending_round;
static uint32_t league_pending_index,league_match_swapped,ml_active;
static CompetitionFrontendState frontend_state;
static CupTournament cup_tournament;
static LeagueTournament league_tournament;
static int ml_frontend_match_active(void){return ml_active!=0;}
'''+actual+r'''
static void assert_leg(uint32_t leg,uint8_t home,uint8_t away){
  uint8_t h=255,a=255;
  assert(competition_frontend_match_leg(&h,&a)==leg);
  assert(h==home && a==away);
  assert(competition_frontend_match_leg(NULL,NULL)==leg);
  NxNativeFirstLegScore stored=nx_native_first_leg_score(leg,h,a);
  assert(stored.previous_home==(leg==2?away:0));
  assert(stored.previous_away==(leg==2?home:0));
}
static void two_leg_cases(CupTournament *bracket,uint32_t *swap){
  const uint32_t teams[4]={11,22,33,44},human[1]={11};
  assert(cup_tournament_init(bracket,teams,4,human,1,123));
  cup_tournament_set_rules(bracket,1,0);
  CupFixture *f=&bracket->fixtures[0][0];
  assert(f->home && f->away);
  assert_leg(1,0,0);
  f->first_leg_complete=1;f->first_leg_home_goals=3;f->first_leg_away_goals=1;
  *swap=0;assert_leg(2,3,1);
  *swap=1;assert_leg(2,1,3);
  bracket->home_away=0;assert_leg(0,0,0);bracket->home_away=1;
  f->complete=1;assert_leg(0,0,0);f->complete=0;
  uint32_t saved=f->home;f->home=0;assert_leg(0,0,0);f->home=saved;
  saved=f->away;f->away=0;assert_leg(0,0,0);f->away=saved;
  /* Native single-leg final even when the tournament Home/Away setting is on. */
  CupFixture *final=&bracket->fixtures[1][0];
  final->home=11;final->away=22;final->first_leg_complete=1;
  if(bracket==&cup_tournament)cup_pending_round=1;else league_pending_round=1;
  assert_leg(0,0,0);
  if(bracket==&cup_tournament)cup_pending_round=0;else league_pending_round=0;
}
int main(void){
  assert_leg(0,0,0); /* Exhibition/no active competition. */
  cup_match_active=cup_tournament_valid=1;
  two_leg_cases(&cup_tournament,&cup_match_swapped);
  ml_active=1;assert_leg(0,0,0);ml_active=0; /* Career domestic cups are single-leg. */
  cup_match_active=0;frontend_state=COMPETITION_FRONTEND_CUP_BRACKET;
  assert_leg(2,1,3); /* Preview and native match share one team-order resolver. */
  cup_tournament_valid=0;assert_leg(0,0,0);
  frontend_state=COMPETITION_FRONTEND_NONE;
  league_match_active=league_tournament_valid=1;
  league_tournament.phase=LEAGUE_PHASE_KNOCKOUT;
  two_leg_cases(&league_tournament.knockout,&league_match_swapped);
  league_tournament.phase=LEAGUE_PHASE_TABLE;assert_leg(0,0,0);
  league_tournament.phase=LEAGUE_PHASE_COMPLETE;assert_leg(0,0,0);
  league_tournament.phase=LEAGUE_PHASE_KNOCKOUT;
  league_match_active=0;frontend_state=COMPETITION_FRONTEND_LEAGUE_HUB;
  assert_leg(2,1,3);
  league_tournament_valid=0;assert_leg(0,0,0);
  assert(nx_native_first_leg_score(99,3,1).previous_home==0);
  return 0;
}
'''
    path=tmp_path/'aggregate-context.c';binary=tmp_path/'aggregate-context.exe'
    path.write_text(source,encoding='utf8')
    built=subprocess.run([compiler,'-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'source'),
        str(path),str(ROOT/'source/cup_tournament.c'),'-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert built.returncode==0,built.stdout+built.stderr
    ran=subprocess.run([str(binary)],capture_output=True,text=True,timeout=15)
    assert ran.returncode==0,ran.stdout+ran.stderr

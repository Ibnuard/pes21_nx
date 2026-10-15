#include "competition_frontend.h"
#include "cup_save.h"
#include "league_save.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

enum { B=1u,A=2u,X=8u,UP=1u<<10,DOWN=1u<<11,LEFT=1u<<12,RIGHT=1u<<13 };
uint32_t pes_controller_native_hid_connected_mask(void){return 3u;}
static void press(uint32_t b){competition_frontend_pad_event(0,0);competition_frontend_pad_event(b,0);competition_frontend_pad_event(0,0);}
static void focus_save(void) {
  const uint32_t next=competition_frontend_state()==COMPETITION_FRONTEND_CUP_BRACKET ? 1u : 2u;
  if(competition_frontend_focus()==next || competition_frontend_focus()==5u)press(DOWN);
  for(uint32_t i=0;i<4u && competition_frontend_focus()!=3u;i++)press(RIGHT);
  assert(competition_frontend_focus()==3u);
}
static void save_current(void) {
  focus_save();press(A);press(A);
  if(competition_frontend_confirmation_active()){press(LEFT);press(A);}
  assert(!competition_frontend_save_pending());
}
static void new_competition(int cup) {
  competition_frontend_close();competition_frontend_finish_close();
  competition_frontend_open_modes();competition_frontend_pad_event(0,0);
  if(!cup)press(DOWN);
  press(A);press(A);press(LEFT);press(DOWN);press(DOWN);
  for(uint32_t i=0;i<30u;i++)press(LEFT); /* 2 teams */
  if(cup){press(RIGHT);press(RIGHT);} /* Four-team cup: a next fixture after recovery. */
  while(competition_frontend_focus()!=5u)press(DOWN);
  press(A);press(A);press(X);press(B);
}
static void recovery(int cup) {
  const CompetitionFrontendState hub=cup ? COMPETITION_FRONTEND_CUP_BRACKET : COMPETITION_FRONTEND_LEAGUE_HUB;
  new_competition(cup);save_current();
  const uint32_t saved_seed=cup ? competition_frontend_cup_tournament()->seed : competition_frontend_league_tournament()->seed;
  press(UP);const uint32_t next=cup ? 1u : 2u;
  if(competition_frontend_focus()!=next)press(RIGHT);
  assert(competition_frontend_focus()==next);press(A);
  assert(competition_frontend_take_action()==(cup ? COMPETITION_ACTION_CUP_FIXTURE : COMPETITION_ACTION_LEAGUE_FIXTURE));
  uint32_t home=0,away=0;
  assert(cup ? competition_frontend_cup_match_teams(&home,&away) : competition_frontend_league_match_teams(&home,&away));
  /* Synthetic filesystem failure, confined to this test's TemporaryDirectory. */
  assert(!rename("SaveData","held-test-saves"));
  FILE *blocked=fopen("SaveData","wb");assert(blocked);assert(!fclose(blocked));
  if(cup)competition_frontend_cup_handoff_result(1);else competition_frontend_league_handoff_result(1);
  competition_frontend_penalty_result(5u,4u);
  if(cup){competition_frontend_cup_match_result(1u,1u);competition_frontend_cup_restore_after_match();}
  else {competition_frontend_league_match_result(2u,0u);competition_frontend_league_restore_after_match();}
  assert(competition_frontend_state()==hub && competition_frontend_save_pending());
  static CupTournament cup_result;static LeagueTournament league_result;
  if(cup)cup_result=*competition_frontend_cup_tournament();else league_result=*competition_frontend_league_tournament();
  for(uint32_t i=0;i<20u;i++)competition_frontend_tick(i*1000u);
  assert(strstr(competition_frontend_status(),"UNSAVED PROGRESS"));
  press(A);assert(competition_frontend_take_action()==COMPETITION_ACTION_NONE);
  press(B);assert(competition_frontend_confirmation_active());
  assert(!strcmp(competition_frontend_confirmation_accept(),"RETRY & LEAVE"));
  press(LEFT);press(A);
  assert(competition_frontend_state()==hub && !competition_frontend_closing());
  assert(competition_frontend_save_pending());
  assert(cup ? !memcmp(&cup_result,competition_frontend_cup_tournament(),sizeof(cup_result)) :
      !memcmp(&league_result,competition_frontend_league_tournament(),sizeof(league_result)));
  assert(!remove("SaveData"));assert(!rename("held-test-saves","SaveData"));
  save_current();
  if(cup) {
    CupSaveState loaded;assert(cup_save_read(0,&loaded));
    assert(!memcmp(&cup_result,&loaded.tournament,sizeof(cup_result)) && loaded.tournament.seed==saved_seed);
  } else {
    static LeagueSaveState loaded;assert(league_save_read(0,&loaded));
    assert(!memcmp(&league_result,&loaded.tournament,sizeof(league_result)) && loaded.tournament.seed==saved_seed);
    press(UP);if(competition_frontend_focus()!=2u)press(RIGHT);press(A);
    assert(competition_frontend_take_action()==COMPETITION_ACTION_LEAGUE_FIXTURE);
    assert(competition_frontend_league_match_teams(&home,&away));competition_frontend_league_handoff_result(1);
    competition_frontend_league_match_result(1u,1u); /* no guessed winner */
    assert(competition_frontend_league_tournament()->phase==LEAGUE_PHASE_KNOCKOUT);
    competition_frontend_penalty_result(4u,5u);competition_frontend_league_match_result(1u,1u);
    assert(competition_frontend_league_tournament()->knockout.champion==away);
    competition_frontend_league_match_result(9u,0u); /* duplicate callback ignored */
    assert(competition_frontend_league_tournament()->knockout.champion==away);
    competition_frontend_league_restore_after_match();
  }
  new_competition(cup);
  const uint32_t fresh_seed=cup ? competition_frontend_cup_tournament()->seed : competition_frontend_league_tournament()->seed;
  assert(fresh_seed && fresh_seed!=saved_seed);
}
int main(void){recovery(1);recovery(0);puts("competition recovery, shootout bridge and fresh seeds OK");return 0;}

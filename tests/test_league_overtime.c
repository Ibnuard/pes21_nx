/* Built against the real frontend translation unit, with public hook stubs. */
#include "league_overtime_frontend.inc"
#define main recovery_fixture_main
#include "test_competition_recovery.c"
#undef main
int main(void){
  new_competition(0);
  for(unsigned overtime=0;overtime<2;overtime++){
    frontend_state=COMPETITION_FRONTEND_LEAGUE_HUB;frontend_focus=1;press(A);assert(cup_general_open);
    cup_general_focus=2-competition_general_first_row();if(cup_extra_time!=overtime)press(LEFT);
    assert(cup_extra_time==overtime);press(B);
    league_tournament.phase=LEAGUE_PHASE_TABLE;
    assert(!competition_frontend_league_extra_time()&&!competition_frontend_league_penalty());
    for(unsigned teams=2;teams<=4;teams+=2)for(unsigned two_legs=0;two_legs<2;two_legs++){
      uint32_t ids[]={100,101,102,103};
      assert(cup_tournament_init(&league_tournament.knockout,ids,teams,ids,teams,31));
      cup_tournament_set_rules(&league_tournament.knockout,two_legs,0);
      cup_tournament_set_final_two_legs(&league_tournament.knockout,two_legs);
      league_tournament.phase=LEAGUE_PHASE_KNOCKOUT;league_pending_round=league_pending_index=0;
      assert(competition_frontend_league_penalty()==!two_legs);
      assert(competition_frontend_league_extra_time()==(overtime&&!two_legs));
      if(two_legs){
        assert(cup_tournament_record_decided(&league_tournament.knockout,0,0,1,0,0));
        assert(competition_frontend_league_penalty());
        assert(competition_frontend_league_extra_time()==(int)overtime);
      }
    }
  }
  puts("League table, knockout, first/deciding legs and Overtime ON/OFF OK");
}

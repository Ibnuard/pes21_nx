#include "master_league.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void make_career(MasterLeague *c, uint32_t teams_count) {
  const MlSettings settings={11u,101u,3u,10u,5u,1u,5u,15u};
  assert(ml_init(c,"synthetic-roster-v1",&settings,"Andro NX",1001u,772u));
  uint32_t teams[32];
  for (uint32_t t=0;t<teams_count;t++) {
    teams[t]=101u+t;
    for (uint32_t p=0;p<24u;p++) {
      MlPlayer player={0};
      player.identity=1000u+t*100u+p; player.native_id=10000u+t*100u+p;
      player.portrait_id=player.native_id; player.overall=75u+(p%10u);
      player.position=(p==0u || p==11u) ? 0u : 12u;
      player.shirt=p+1u;
      snprintf(player.name,sizeof(player.name),"Synthetic %u %u",t,p);
      assert(ml_add_player(c,teams[t],&player));
    }
  }
  assert(ml_start_season(c,teams,teams_count,teams,teams_count));
  assert(ml_valid(c));
}

int main(void) {
  MasterLeague *c=malloc(sizeof(*c)), *copy=malloc(sizeof(*copy));
  assert(c && copy);
  assert(ml_manager_name_valid("Ibnu Ardiansyah"));
  assert(!ml_manager_name_valid(" "));
  assert(!ml_manager_name_valid("Name "));
  assert(!ml_manager_name_valid("1234"));
  make_career(c,4u);
  MlEvent shootout;
  while (ml_next_event(c,&shootout) && shootout.kind!=ML_EVENT_CUP)
    assert(ml_simulate_event(c,&shootout));
  assert(shootout.home && shootout.away);
  *copy=*c;
  assert(!ml_record_event(c,&shootout,1u,1u,NULL,0u,0));
  assert(!memcmp(c,copy,sizeof(*c))); /* no charge/advance when decider is missing */
  assert(ml_record_event_decided(c,&shootout,1u,1u,NULL,0u,0,shootout.away));
  assert(c->cup.fixtures[shootout.round][shootout.index].winner==shootout.away);
  assert(c->cup.fixtures[shootout.round][shootout.index].home_goals==1u);
  assert(ml_valid(c));
  make_career(c,4u);
  *copy=*c;
  const uint32_t purchase=ml_club(c,102u)->players[1];
  const uint32_t identity=c->players[purchase].identity;
  assert(!*ml_transfer(c,purchase,101u,3u));
  assert(c->players[purchase].identity==identity && c->players[purchase].club==101u);
  assert(ml_club(c,101u)->count==25u && ml_club(c,102u)->count==23u);
  assert(c->players[ml_club(c,102u)->players[0]].position==0u);
  assert(copy->players[purchase].club==102u); /* base snapshot not mutated */
  assert(ml_valid(c));
  assert(*ml_transfer(c,purchase,101u,3u));
  GameplanPreset plan={0}; plan.team_id=101u; plan.player_count=ml_club(c,101u)->count;
  for (uint32_t i=0;i<plan.player_count;i++) {
    uint32_t native=c->players[ml_club(c,101u)->players[i]].native_id;
    memcpy(plan.players[i].player_id,&native,4u);
    plan.players[i].order_no=i;
  }
  plan.players[1].order_no=12u; plan.players[12].order_no=1u;
  assert(ml_store_plan(c,&plan));
  assert(ml_plan_compatible(c,&plan));
  memcpy(plan.players[2].player_id,plan.players[1].player_id,4u);
  plan.players[2].player_id[8]=1u;
  assert(!ml_plan_compatible(c,&plan)); /* encoded aliases cannot duplicate identity */
  assert(ml_save_write(0u,c));
  assert(ml_save_read(0u,c->content_id,copy));
  assert(!memcmp(c,copy,sizeof(*c)));
  assert(!ml_save_read(0u,"wrong-version",copy));
  assert(!memcmp(c,copy,sizeof(*c)));
  assert(ml_save_write(0u,c));
  FILE *bad=fopen("SaveData/footballnx_master_league_1_b.bin","wb");
  assert(bad); fputs("torn write",bad); fclose(bad);
  assert(ml_save_read(0u,c->content_id,copy)); /* previous A survives */
  uint32_t events=0;
  MlEvent event;
  while (ml_next_event(c,&event) && event.kind!=ML_EVENT_SEASON_END) {
    const uint32_t old=c->league.active_matchday;
    assert(ml_simulate_event(c,&event));
    assert(!ml_simulate_event(c,&event)); /* retry cannot double-charge or double-score */
    if (event.kind==ML_EVENT_LEAGUE) assert(c->league.active_matchday==old+1u);
    assert(ml_valid(c));
    assert(++events<100u);
  }
  assert(c->league.phase==LEAGUE_PHASE_COMPLETE && c->cup.champion);
  assert(c->league.scorer_count>0u && c->wages_paid>0 && c->match_income>0);
  assert(c->prize_income>0 && c->last_rank>0u);
  assert(ml_save_write(1u,c));
  assert(ml_next_season(c));
  assert(c->season==2u && c->day==0u && c->league.active_matchday==0u);
  assert(c->players[purchase].club==101u && ml_valid(c));
  for (uint32_t n=0;n<3u;n++) {
    while (ml_next_event(c,&event) && event.kind!=ML_EVENT_SEASON_END)
      assert(ml_simulate_event(c,&event));
    for (uint32_t i=0;i<c->player_count;i++)
      if(c->players[i].club==101u) assert(!*ml_renew(c,i,3u));
    assert(ml_next_season(c) && ml_valid(c));
  }
  make_career(c,3u); /* odd-team byes must advance without fictitious matches */
  events=0;
  while (ml_next_event(c,&event) && event.kind!=ML_EVENT_SEASON_END) {
    assert(ml_simulate_event(c,&event));
    assert(ml_valid(c) && ++events<100u);
  }
  puts("master league core: identity, calendar, transfers, saves, 5 seasons OK");
  free(c); free(copy); return 0;
}

#define main existing_career_tests
#include "test_master_league.c"
#undef main

typedef struct {MasterLeagueV3 prefix;_Alignas(8) uint32_t seen[ML_MAX_OFFERS];} MasterLeagueV4;
_Static_assert(sizeof(MasterLeagueV4)==offsetof(MasterLeague,world),"frozen v4 ABI changed");

static void world_season(MasterLeague *c) {
  make_career(c,4u);ml_world_enable(c);assert(c->world.version==1u && ml_valid(c));
  assert(c->world.continental.team_count>=2u);
  unsigned counts[ML_EVENT_WORLD_CUP+1u]={0};MlEvent e;unsigned steps=0u,job_accepted=0u;
  const uint32_t owner=c->players[0].club,identity=c->players[0].identity;
  while(ml_next_event(c,&e) && e.kind!=ML_EVENT_SEASON_END) {
    assert(++steps<160u && e.day>=c->day);counts[e.kind]++;
    ml_club(c,c->settings.club)->cash=500000000;
    MasterLeague *before=malloc(sizeof(*before));assert(before);*before=*c;
    if(ml_event_is_match(e.kind) && e.home && e.away) {
      uint32_t managed=ml_event_manager_team(c,e.kind);
      if(ml_event_is_knockout(e.kind)) {
        assert(!ml_record_event(c,&e,1u,1u,NULL,0u,0));assert(!memcmp(before,c,sizeof(*c)));
      }
      assert(ml_record_event(c,&e,e.home==managed ? 3u : 0u,e.away==managed ? 3u : 0u,NULL,0u,0));
    }else assert(ml_simulate_event(c,&e));
    if(ml_event_is_national(e.kind)) {
      assert(c->settings.club==before->settings.club && c->player_count==before->player_count);
      assert(!memcmp(c->players,before->players,sizeof(c->players)));
      assert(c->match_income==before->match_income && c->prize_income==before->prize_income);
    }
    assert(!ml_simulate_event(c,&e)); /* duplicate callback cannot double-advance */
    free(before);
    if(c->world.national_count && !c->world.national_team) {
      const uint32_t club=c->settings.club;
      assert(!*ml_accept_national_job(c,0u));assert(c->settings.club==club && c->world.national_team);
      assert(*ml_accept_national_job(c,0u));
    }
    if(!job_accepted && c->office.job_team) {
      const uint32_t day=c->day,national=c->world.national_team,new_team=c->office.job_team;
      const int64_t cash=ml_club(c,new_team)->cash;
      assert(!*ml_accept_job(c));assert(c->day==day && c->world.national_team==national);
      assert(c->settings.club==new_team && ml_club(c,new_team)->cash==cash && !c->current_plan.player_count);
      assert(!c->office.losses && !c->wages_paid && !c->match_income);job_accepted=1u;
    }
    assert(ml_valid(c));
  }
  assert(counts[ML_EVENT_CONTINENTAL] && counts[ML_EVENT_FRIENDLY]==2u && counts[ML_EVENT_QUALIFIER]==6u);
  assert(counts[ML_EVENT_REGIONAL] && counts[ML_EVENT_WORLD_CUP]);
  assert(job_accepted);
  assert(c->players[0].club==owner && c->players[0].identity==identity);
  MasterLeague *copy=malloc(sizeof(*copy));assert(copy);
  assert(ml_save_write(0u,c) && ml_save_read(0u,c->content_id,copy));assert(!memcmp(c,copy,sizeof(*c)));
  copy->world.qualifiers.standings[0].points++;assert(!ml_valid(copy));
  *copy=*c;copy->world.continental.fixtures[1][0].home=999999u;assert(!ml_valid(copy));
  assert(ml_next_season(c) && ml_valid(c));assert(c->world.national_team && !c->world.friendly_mask);
  free(copy);
}
static void migration(MasterLeague *c,MasterLeague *copy) {
  make_career(c,4u);const uint32_t size=sizeof(MasterLeagueV4);uint32_t hash=2166136261u;
  for(uint32_t i=0;i<size;i++)hash=(hash^((const unsigned char *)c)[i])*16777619u;
  assert(ml_save_write(2u,c));
  const uint32_t header[]={0x314c4d46u,4u,size,99999u,hash};
  FILE *f=fopen("SaveData/footballnx_master_league_3_a.bin","wb");assert(f);
  assert(fwrite(header,1,sizeof(header),f)==sizeof(header));assert(fwrite(c,1,size,f)==size);assert(!fclose(f));
  assert(ml_save_read(2u,c->content_id,copy));assert(!memcmp(c,copy,sizeof(*c)) && !copy->world.version);
  ml_world_enable(copy);assert(copy->world.version && ml_valid(copy));
  make_career(c,4u);c->day=150u;c->wage_week=c->day/7u;ml_world_enable(c);
  assert(!c->world.continental.team_count && c->world.national_checked); /* no invented past results */
}
static void transfer_balance(MasterLeague *c,MasterLeague *copy) {
  unsigned accepted=0u,counter=0u,rejected=0u;
  for(uint32_t seed=1u;seed<=100u;seed++) {
    make_career(c,4u);c->seed=seed;c->office.milestone_mask=1u;
    const uint32_t index=ml_club(c,102u)->players[1u];MlPlayer *p=&c->players[index];p->overall=98u;
    ml_club(c,101u)->cash=500000000;ml_club(c,101u)->wage_budget=10000000;
    const uint32_t fee=ml_transfer_fee(c,p);
    assert(!*ml_offer_submit(c,index,fee,100000u,3u,0u));
    MlEvent e;assert(ml_next_event(c,&e));assert(ml_process_office_event(c,&e));
    MlOffer *o=&c->office.offers[0];
    accepted+=o->status==ML_OFFER_ACCEPTED;counter+=o->status==ML_OFFER_COUNTER;rejected+=o->status==ML_OFFER_REJECTED;
    if(o->status==ML_OFFER_COUNTER){assert(o->fee>fee*17u/10u && o->wage>p->wage);assert(!*ml_offer_accept(c,o->id));}
    else if(o->status==ML_OFFER_REJECTED){*copy=*c;assert(*ml_offer_submit(c,index,fee*3u,200000u,5u,0u));assert(!memcmp(c,copy,sizeof(*c)));}
    assert(ml_valid(c));
  }
  assert(!accepted && counter>20u && rejected>20u);
  make_career(c,4u);c->options.transfer_difficulty=1u;c->office.milestone_mask=1u;
  uint32_t index=ml_club(c,102u)->players[1u];c->players[index].overall=98u;
  assert(!*ml_offer_submit(c,index,ml_transfer_fee(c,&c->players[index]),100000u,3u,0u));
  MlEvent e;assert(ml_next_event(c,&e) && ml_process_office_event(c,&e));assert(c->office.offers[0].status==ML_OFFER_ACCEPTED);
}
static void national_offer_tests(MasterLeague *c,MasterLeague *copy) {
  uint32_t first_country=0u,varied=0u;
  for(uint32_t seed=1u;seed<=12u;seed++) {
    make_career(c,4u);c->seed=seed;ml_world_enable(c);
    while(!c->world.national_count) {
      MlEvent e;assert(ml_next_event(c,&e) && e.day<=76u);
      *copy=*c;copy->manager_nationality=99u;
      if(ml_event_is_match(e.kind) && e.home && e.away)
        assert(ml_record_event(c,&e,e.home==c->settings.club ? 3u : 0u,e.away==c->settings.club ? 3u : 0u,NULL,0u,0));
      else assert(ml_simulate_event(c,&e));
      if(c->world.national_count) {
        assert(ml_simulate_event(copy,&e));
        assert(!memcmp(c->world.national_offers,copy->world.national_offers,sizeof(c->world.national_offers)));
      }
    }
    assert(c->world.national_count>=2u && c->world.national_count<=ML_MAX_NATIONAL_OFFERS);
    if(!first_country)first_country=c->world.national_offers[0].team;
    varied+=first_country!=c->world.national_offers[0].team;
    assert(ml_valid(c));
  }
  assert(varied);
  assert(ml_national_offer_unread(c,0u));ml_national_offer_mark_read(c,0u);
  assert(!ml_national_offer_unread(c,0u) && ml_national_offer_unread(c,1u));
  assert(ml_save_write(1u,c) && ml_save_read(1u,c->content_id,copy));assert(!memcmp(c,copy,sizeof(*c)));
  copy->world.national_offers[1].team=copy->world.national_offers[0].team;assert(!ml_valid(copy));
  *copy=*c;assert(*ml_accept_national_job(c,ML_MAX_NATIONAL_OFFERS));assert(!memcmp(c,copy,sizeof(*c)));
  assert(!*ml_reject_national_job(c,0u) && ml_national_offer_status(c,0u)==ML_OFFER_REJECTED);
  assert(ml_national_offer_status(c,1u)==ML_OFFER_WAITING && !c->world.national_team);
  *copy=*c;assert(*ml_reject_national_job(c,0u));assert(!memcmp(c,copy,sizeof(*c)));
  const uint32_t team=c->world.national_offers[1].team,club=c->settings.club,day=c->day;
  assert(!*ml_accept_national_job(c,1u) && c->world.national_team==team && c->settings.club==club && c->day==day);
  for(uint32_t i=2u;i<c->world.national_count;i++)assert(ml_national_offer_status(c,i)==ML_OFFER_CANCELLED);
  assert(ml_valid(c));
  copy->day=77u;assert(ml_national_offer_status(copy,1u)==ML_OFFER_EXPIRED);
  assert(*ml_accept_national_job(copy,1u) && *ml_reject_national_job(copy,1u));
}
int main(void) {
  MasterLeague *c=malloc(sizeof(*c)),*copy=malloc(sizeof(*copy));assert(c && copy);
  world_season(c);migration(c,copy);transfer_balance(c,copy);national_offer_tests(c,copy);
  free(c);free(copy);puts("world career OK");return 0;
}

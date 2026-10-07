#include "master_league.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>

/* Frozen outer v1 layout: independently check the append-only boundary. */
typedef struct {
  uint32_t seed,season,day,transaction_sequence;
  uint32_t club_count,player_count,target_rank,last_rank,seasons_completed;
  uint32_t wage_week,cup_enabled;
  int64_t wages_paid,match_income,prize_income;
  char content_id[ML_CONTENT_ID_SIZE],manager_name[ML_NAME_SIZE];
  uint32_t manager_nationality;
  MlSettings settings;
  MlClub clubs[ML_MAX_CLUBS];MlPlayer players[ML_MAX_PLAYERS];
  LeagueTournament league;CupTournament cup;
  GameplanPreset current_plan,presets[GAMEPLAN_PRESET_SLOTS];
} MasterLeagueV1;
_Static_assert(sizeof(MasterLeagueV1)==offsetof(MasterLeague,options),"v1 save ABI changed");
typedef struct { MasterLeagueV1 prefix; MlCareerOptions options; } MasterLeagueV2;
_Static_assert(sizeof(MasterLeagueV2)==offsetof(MasterLeague,office),"v2 save ABI changed");
typedef struct { MasterLeagueV2 prefix; _Alignas(8) MlOfficeState office; } MasterLeagueV3;
_Static_assert(sizeof(MasterLeagueV3)==offsetof(MasterLeague,offer_seen),"v3 save ABI changed");

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

static void office_tests(MasterLeague *c,MasterLeague *copy) {
  make_career(c,4u);MlEvent e;
  assert(ml_next_event(c,&e) && e.kind==ML_EVENT_WINDOW && e.day==0u);
  assert(ml_process_office_event(c,&e));
  assert(!ml_process_office_event(c,&e));
  assert(c->office.offer_count && c->office.offers[0].incoming);
  const uint32_t player=ml_club(c,102u)->players[1u],identity=c->players[player].identity;
  const uint32_t fee=ml_transfer_fee(c,&c->players[player]),wage=c->players[player].wage;
  const int64_t cash=ml_club(c,101u)->cash;
  assert(!*ml_offer_submit(c,player,fee*8u/10u,wage,4u,0u));
  MlOffer *o=&c->office.offers[c->office.offer_count-1u];const uint32_t id=o->id;
  assert(o->due>=1u && o->due<=3u && o->status==ML_OFFER_WAITING);
  assert(c->players[player].club==102u && ml_club(c,101u)->cash==cash);
  *copy=*c;assert(*ml_offer_submit(c,player,fee,wage,3u,0u));assert(!memcmp(c,copy,sizeof(*c)));
  assert(ml_save_write(0u,c) && ml_save_read(0u,c->content_id,copy));assert(!memcmp(c,copy,sizeof(*c)));
  assert(ml_next_event(c,&e) && e.kind==ML_EVENT_RESPONSE && e.day==o->due);
  assert(ml_process_office_event(c,&e) && o->status==ML_OFFER_COUNTER);
  assert(o->fee==fee && !*ml_offer_accept(c,id));
  assert(c->players[player].identity==identity && c->players[player].club==101u);
  assert(ml_club(c,101u)->cash==cash-fee && c->players[player].wage==wage);
  assert(c->players[player].contract_end==c->season+3u && ml_valid(c));
  *copy=*c;assert(*ml_offer_accept(c,id));assert(!memcmp(c,copy,sizeof(*c)));
  const uint32_t reject_player=ml_club(c,103u)->players[2u];
  assert(!*ml_offer_submit(c,reject_player,0u,c->players[reject_player].wage,2u,0u));
  o=&c->office.offers[c->office.offer_count-1u];
  assert(o->due>c->day && o->due-c->day<=3u);
  assert(ml_next_event(c,&e) && ml_process_office_event(c,&e));assert(o->status==ML_OFFER_REJECTED);
  while(ml_next_event(c,&e) && e.day<=30u)assert(ml_process_office_event(c,&e));
  assert(c->day==30u && ml_window_open(c));
  assert(*ml_offer_submit(c,reject_player,fee,wage,2u,0u)); /* deadline cannot promise a later reply */
  assert(ml_next_event(c,&e) && e.kind==ML_EVENT_LEAGUE && ml_simulate_event(c,&e));
  assert(!ml_window_open(c) && ml_valid(c));
  for(uint32_t i=0;i<c->office.offer_count;i++)assert(c->office.offers[i].status>ML_OFFER_COUNTER);
  /* Read a real v2 prefix, including non-default settings, without rewriting. */
  make_career(c,4u);c->options.currency=2u;c->settings.condition=2u;
  const uint32_t size=(uint32_t)offsetof(MasterLeague,office);uint32_t hash=2166136261u;
  const unsigned char *bytes=(const unsigned char *)c;
  for(uint32_t i=0;i<size;i++)hash=(hash^bytes[i])*16777619u;
  const uint32_t header[]={0x314c4d46u,2u,size,999u,hash};
  FILE *f=fopen("SaveData/footballnx_master_league_2_a.bin","wb");assert(f);
  assert(fwrite(header,1,sizeof(header),f)==sizeof(header));assert(fwrite(c,1,size,f)==size);assert(!fclose(f));
  assert(ml_save_read(1u,c->content_id,copy));assert(copy->options.currency==2u && copy->settings.condition==5u && !copy->office.offer_count);
  /* Board warnings give a full 14-day grace period, then end the career. */
  make_career(c,4u);ml_club(c,101u)->cash=-1;
  assert(ml_next_event(c,&e) && e.kind==ML_EVENT_BOARD && ml_process_office_event(c,&e));
  assert(c->office.negative_since==1u && !c->office.dismissed);
  while(ml_next_event(c,&e) && e.day<14u)assert(ml_simulate_event(c,&e));
  assert(e.day==14u && e.kind==ML_EVENT_BOARD && ml_process_office_event(c,&e));
  assert(c->office.dismissed==2u && !ml_next_event(c,&e) && ml_valid(c));
  assert(*ml_transfer(c,25u,101u,3u));assert(ml_save_write(0u,c));
  /* Six losses are counted only from mid-season; the third issues a warning. */
  make_career(c,10u);ml_club(c,101u)->cash=INT64_C(10000000000);uint32_t losses=0u;
  while(ml_next_event(c,&e) && e.kind!=ML_EVENT_SEASON_END) {
    if(e.kind>=ML_EVENT_WINDOW)assert(ml_process_office_event(c,&e));
    else if(e.home && e.away) {
      const uint32_t winner=e.home==101u ? e.away : e.home;
      assert(ml_record_event_decided(c,&e,e.home==winner ? 1u : 0u,e.away==winner ? 1u : 0u,NULL,0u,0,0u));
      if(e.day>=183u)losses++;
    } else assert(ml_simulate_event(c,&e));
    if(losses==3u)assert(c->office.notices[c->office.notice_count-1u].kind==ML_NOTICE_WARNING);
  }
  assert(losses==6u && c->office.dismissed==1u && ml_valid(c));
  /* Same-league job acceptance preserves every result and schedules, but
   * changes the human team and invalidates old club plans/pending offers. */
  make_career(c,10u);
  for(uint32_t i=0;i<c->club_count;i++)c->clubs[i].cash=INT64_C(10000000000);
  while(c->day<183u && ml_next_event(c,&e)) {
    if(e.kind>=ML_EVENT_WINDOW)assert(ml_process_office_event(c,&e));
    else if(e.home && e.away)assert(ml_record_event(c,&e,e.home==101u ? 2u : 0u,e.away==101u ? 2u : 0u,NULL,0u,0));
    else assert(ml_simulate_event(c,&e));
  }
  assert(c->office.job_team);*copy=*c;const uint32_t team=c->office.job_team;
  assert(!*ml_accept_job(c) && c->settings.club==team && ml_valid(c));
  assert(!memcmp(c->league.fixtures,copy->league.fixtures,sizeof(c->league.fixtures)));
  assert(!memcmp(c->cup.fixtures,copy->cup.fixtures,sizeof(c->cup.fixtures)));
  /* Malformed extension data must fail closed before lookup/indexing. */
  *copy=*c;c->office.offer_count=ML_MAX_OFFERS+1u;assert(!ml_valid(c));*c=*copy;
  puts("office: pending/counter/reject/accept, deadline, save v2 migration, dismissal and jobs OK");
}
static void renewal_tests(MasterLeague *c,MasterLeague *copy) {
  make_career(c,4u);
  const uint32_t p=ml_club(c,101u)->players[1u];
  const int64_t fee=ml_renew_fee(c,p,3u),cash=ml_club(c,101u)->cash;
  assert(fee==(int64_t)c->players[p].wage*12u);
  ml_club(c,101u)->cash=fee-1;*copy=*c;
  assert(!strcmp(ml_renew(c,p,3u),"INSUFFICIENT TRANSFER BUDGET"));
  assert(!memcmp(c,copy,sizeof(*c)));
  ml_club(c,101u)->cash=cash;
  const uint32_t sequence=c->transaction_sequence;
  assert(!*ml_renew(c,p,3u));
  assert(c->players[p].contract_end==c->season+3u && ml_club(c,101u)->cash==cash-fee);
  assert(c->transaction_sequence==sequence+1u && ml_valid(c));
  *copy=*c;assert(*ml_renew(c,p,3u));assert(!memcmp(c,copy,sizeof(*c)));
  assert(*ml_renew(c,p,1u));assert(!memcmp(c,copy,sizeof(*c)));
  assert(ml_save_write(0u,c) && ml_save_read(0u,c->content_id,copy));
  assert(!memcmp(c,copy,sizeof(*c)));
}
static void release_tests(MasterLeague *c,MasterLeague *copy) {
  make_career(c,4u);
  const uint32_t p=ml_club(c,101u)->players[1u],id=c->players[p].identity;
  const uint32_t native=c->players[p].native_id,portrait=c->players[p].portrait_id;
  const uint32_t wages=ml_weekly_wage(c,101u),wage=c->players[p].wage;
  const uint32_t quote=ml_release_value(c,p),sequence=c->transaction_sequence;
  const int64_t cash=ml_club(c,101u)->cash;
  assert(quote==ml_transfer_value(&c->players[p])/4u);
  *copy=*c;assert(*ml_release(c,ML_MAX_PLAYERS));assert(!memcmp(c,copy,sizeof(*c)));
  assert(*ml_release(c,24u));assert(!memcmp(c,copy,sizeof(*c)));
  c->office.dismissed=1u;*copy=*c;
  assert(*ml_release(c,p));assert(!memcmp(c,copy,sizeof(*c)));c->office.dismissed=0u;
  /* A live buyer offer becomes closed, never transfers a released identity. */
  c->office.offer_count=c->office.next_id=1u;
  c->office.offers[0]=(MlOffer){.id=1u,.player=p,.from=101u,.to=102u,
    .fee=quote,.wage=wage,.years=3u,.season=1u,.status=ML_OFFER_ACCEPTED,.incoming=1u};
  assert(!*ml_release(c,p));
  assert(c->players[p].club==0u && c->players[p].contract_end==0u && c->players[p].wage==0u);
  assert(c->players[p].identity==id && c->players[p].native_id==native && c->players[p].portrait_id==portrait);
  assert(ml_club(c,101u)->count==23u && ml_club(c,101u)->cash==cash+quote);
  assert(c->players[ml_club(c,101u)->players[0]].position==0u);
  assert(ml_weekly_wage(c,101u)==wages-wage && c->transaction_sequence==sequence+1u);
  assert(c->office.offers[0].status==ML_OFFER_CANCELLED && ml_valid(c));
  *copy=*c;assert(*ml_release(c,p));assert(!memcmp(c,copy,sizeof(*c)));
  assert(ml_save_write(0u,c) && ml_save_read(0u,c->content_id,copy));assert(!memcmp(c,copy,sizeof(*c)));
  assert(!*ml_transfer(c,p,101u,3u));assert(ml_release_value(c,p)==0u);
  const int64_t second_cash=ml_club(c,101u)->cash;
  assert(!*ml_release(c,p) && ml_club(c,101u)->cash==second_cash && ml_valid(c));
  /* Retain a goalkeeper, a full matchday squad, and matching starter cover. */
  make_career(c,4u);uint32_t keeper=ml_club(c,101u)->players[0];
  assert(!*ml_release(c,keeper));keeper=ml_club(c,101u)->players[0];*copy=*c;
  assert(!strcmp(ml_release(c,keeper),"CANNOT RELEASE THE LAST GOALKEEPER"));assert(!memcmp(c,copy,sizeof(*c)));
  while(ml_club(c,101u)->count>18u)assert(!*ml_release(c,ml_club(c,101u)->players[ml_club(c,101u)->count-1u]));
  *copy=*c;assert(*ml_release(c,ml_club(c,101u)->players[17]));assert(!memcmp(c,copy,sizeof(*c)));
  make_career(c,4u);
  for(uint32_t i=11u;i<24u;i++)c->players[ml_club(c,101u)->players[i]].position=0u;
  *copy=*c;assert(!strcmp(ml_release(c,p),"NO SUITABLE STARTER REPLACEMENT"));assert(!memcmp(c,copy,sizeof(*c)));
  make_career(c,4u);ml_club(c,101u)->cash=INT64_C(1000000000000);*copy=*c;
  assert(*ml_release(c,p));assert(!memcmp(c,copy,sizeof(*c)));
  make_career(c,4u);MlEvent e;
  while(c->day<42u){assert(ml_next_event(c,&e));assert(ml_simulate_event(c,&e));}
  assert(!ml_window_open(c));
  assert(!*ml_release(c,p) && ml_valid(c)); /* release is not a transfer-window bid */
  c->players[p].reserved=2u;assert(!ml_valid(c));
}
static void unread_tests(MasterLeague *c,MasterLeague *copy) {
  make_career(c,4u);
  const uint32_t p=ml_club(c,102u)->players[1u];
  assert(!*ml_offer_submit(c,p,ml_transfer_fee(c,&c->players[p]),c->players[p].wage,3u,0u));
  assert(!ml_offer_unread(c,0u));
  MlEvent e;
  while(c->office.offers[0].status==ML_OFFER_WAITING){assert(ml_next_event(c,&e));assert(ml_process_office_event(c,&e));}
  assert(ml_offer_unread(c,0u));
  ml_offer_mark_read(c,0u);assert(!ml_offer_unread(c,0u));
  assert(ml_save_write(0u,c) && ml_save_read(0u,c->content_id,copy));assert(!memcmp(c,copy,sizeof(*c)));
  /* Re-negotiation on the same date is a new revision, even if status repeats. */
  const uint32_t id=c->office.offers[0].id;
  assert(!*ml_offer_submit(c,p,ml_transfer_fee(c,&c->players[p]),c->players[p].wage,4u,id));
  assert(!ml_offer_unread(c,0u));
  while(c->office.offers[0].status==ML_OFFER_WAITING){assert(ml_next_event(c,&e));assert(ml_process_office_event(c,&e));}
  assert(ml_offer_unread(c,0u));
  /* Frozen v3 payload migrates without touching its old bytes or disk file. */
  const uint32_t size=sizeof(MasterLeagueV3);uint32_t hash=2166136261u;
  for(uint32_t i=0;i<size;i++)hash=(hash^((const unsigned char *)c)[i])*16777619u;
  const uint32_t header[]={0x314c4d46u,3u,size,100000u,hash};
  FILE *file=fopen("SaveData/footballnx_master_league_3_a.bin","wb");assert(file);
  assert(fwrite(header,1,sizeof(header),file)==sizeof(header));assert(fwrite(c,1,size,file)==size);assert(!fclose(file));
  assert(ml_save_read(2u,c->content_id,copy));assert(!memcmp(c,copy,size));
  for(uint32_t i=0;i<ML_MAX_OFFERS;i++)assert(!copy->offer_seen[i]);
  assert(ml_offer_unread(copy,0u));
  /* Inbox compaction moves read receipts with their exact offer. */
  MlOffer template=c->office.offers[0];template.status=ML_OFFER_REJECTED;
  c->office.offer_count=c->office.next_id=ML_MAX_OFFERS;
  for(uint32_t i=0;i<ML_MAX_OFFERS;i++) {
    c->office.offers[i]=template;c->office.offers[i].id=i+1u;c->offer_seen[i]=0u;
    if(i+1u<ML_MAX_OFFERS)ml_offer_mark_read(c,i);
  }
  assert(!*ml_offer_submit(c,p+1u,template.fee,template.wage,3u,0u));
  assert(c->office.offers[0].id==2u && !ml_offer_unread(c,0u));
  assert(c->office.offers[30].id==32u && ml_offer_unread(c,30u));
  assert(c->office.offers[31].id==33u && !ml_offer_unread(c,31u) && !c->offer_seen[31]);
  assert(ml_valid(c));
}

int main(void) {
  MasterLeague *c=malloc(sizeof(*c)), *copy=malloc(sizeof(*copy));
  assert(c && copy);
  office_tests(c,copy);
  renewal_tests(c,copy);
  release_tests(c,copy);
  unread_tests(c,copy);
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
  const uint32_t normal_fee=ml_transfer_fee(c,&c->players[purchase]);
  c->options.transfer_difficulty=1u;
  assert(ml_transfer_fee(c,&c->players[purchase])==normal_fee*9u/10u);
  c->options.transfer_difficulty=2u;
  assert(ml_transfer_fee(c,&c->players[purchase])==normal_fee*125u/100u);
  c->options.transfer_difficulty=0u;c->options.skip_first_window=1u;
  assert(!ml_window_open(c) && *ml_transfer(c,purchase,101u,3u));
  c->day=184u;assert(ml_window_open(c));c->day=0u;
  c->options.skip_first_window=0u;c->options.currency=2u;
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
  /* A real v1 prefix/checksum upgrades in memory; no read rewrites the file. */
  const uint32_t old_size=(uint32_t)offsetof(MasterLeague,options);
  const unsigned char *bytes=(const unsigned char *)c;
  uint32_t hash=2166136261u;
  for(uint32_t i=0;i<old_size;i++)hash=(hash^bytes[i])*16777619u;
  const uint32_t legacy_header[]={0x314c4d46u,1u,old_size,1u,hash};
  FILE *legacy=fopen("SaveData/footballnx_master_league_3_a.bin","wb");assert(legacy);
  assert(fwrite(legacy_header,1,sizeof(legacy_header),legacy)==sizeof(legacy_header));
  assert(fwrite(c,1,old_size,legacy)==old_size);assert(!fclose(legacy));
  assert(ml_save_read(2u,c->content_id,copy));
  assert(!memcmp(c,copy,old_size));
  assert(!copy->options.currency && !copy->options.transfer_difficulty && !copy->options.skip_first_window);
  assert(ml_save_write(2u,copy) && ml_save_read(2u,c->content_id,copy));
  uint32_t events=0;
  /* The endurance fixture isolates rollover from the separately tested
   * dismissal economy. A small synthetic four-club league earns less gate. */
  ml_club(c,c->settings.club)->cash=INT64_C(10000000000);
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

#include "master_league_frontend.h"
#include "master_league_catalog.h"
#include "fl26_league_catalog_generated.h"
#include "exhibition_team_catalog.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

enum { B=1u,A=2u,Y=4u,R=128u,DOWN=1u<<11,UP=1u<<10,LEFT=1u<<12,RIGHT=1u<<13 };
const char *ml_catalog_content_id(void) { return "synthetic-career-ui"; }
const char *ml_catalog_pair_id(void) { return "synthetic"; }
int ml_catalog_has_team(uint32_t team) {
  for(uint32_t i=0;i<fl26_league_catalog[0].pool_count;i++)
    if(fl26_league_catalog[0].team_ids[i]==team) return 1;
  return 0;
}
int ml_catalog_import(MasterLeague *c) {
  for(uint32_t i=0;i<fl26_league_catalog[0].pool_count;i++) {
    const uint32_t team=fl26_league_catalog[0].team_ids[i];
    for(uint32_t j=0;j<24u;j++) {
      MlPlayer p={0};p.identity=10000u+i*100u+j;p.native_id=p.identity;
      p.overall=75;p.shirt=j+1u;p.position=(j==0u||j==11u) ? 0u : 12u;
      snprintf(p.name,sizeof(p.name),"Synthetic %u %u",i,j);
      if(!ml_add_player(c,team,&p)) return 0;
    }
  }
  return 1;
}
/* Do not allocate a 44KB return temporary for every assertion at -O0. */
static const MlView *read_view(void) { static MlView v;ml_frontend_view(&v);return &v; }
#define view() (*read_view())
static uint64_t ui_clock;
static void finish_advance(void) {
  if(view().page==ML_PAGE_ADVANCE){ui_clock+=4000u;ml_frontend_tick(ui_clock);}
}
static void press(uint32_t b) { ml_frontend_pad(b);finish_advance(); }
static void office_go(uint32_t section,uint32_t item) {
  if(view().drawer.open)press(B);
  for(uint32_t i=0;i<5u && view().page!=ML_PAGE_HUB;i++)press(B);
  assert(view().page==ML_PAGE_HUB);
  while(view().section<section)press(R);
  while(view().section>section)press(1u<<4);
  press(UP);if(view().selected==1u)press(LEFT);
  if(item>=2u)press(DOWN);
  if(item==1u || item==3u)press(RIGHT);
  if(item==4u){press(RIGHT);press(RIGHT);}
  press(A);
}
static uint32_t term_tenths(const char *text,char unit) {
  char currency[4],suffix[2];uint32_t whole,decimal;
  assert(sscanf(text,"%3s %u.%u %1s",currency,&whole,&decimal,suffix)==4);
  assert(decimal<10u && suffix[0]==unit);return whole*10u+decimal;
}
static void office_ui_tests(void) {
  ml_frontend_close();ml_frontend_open();press(A);
  for(uint32_t i=0;i<7u;i++)press(DOWN);
  press(A);ml_frontend_name_result("Office Test");press(DOWN);press(A);press(A);
  press(DOWN);press(A);press(DOWN);press(A);assert(view().page==ML_PAGE_HUB);
  const MasterLeague *c=ml_frontend_career();assert(c && ml_window_open(c));
  press(1u<<3);assert(view().toast_serial && !strcmp(view().toast,"Career saved") && !view().status[0]);
  office_go(2u,1u);
  const uint32_t own_player=ml_find_club(c,c->settings.club)->players[0];
  const int64_t renew_cash=ml_find_club(c,c->settings.club)->cash;
  press(A);assert(strstr(view().drawer.detail,"SIGNING FEE") && !strcmp(view().drawer.confirm_label,"PAY & RENEW"));
  press(A);press(A);
  assert(!view().drawer.open && !view().status[0] && strstr(view().toast,"signing fee paid"));
  assert(ml_find_club(c,c->settings.club)->cash==renew_cash-ml_renew_fee(c,own_player,3u));
  office_go(0u,3u);assert(view().table_count==8u);press(R);assert(view().first==8u && view().table[0].rank==9u);
  press(Y);assert(view().empty[0] && !view().info[0][0]);
  office_go(3u,2u);assert(view().bracket_count==7u);press(R);assert(view().bracket_round==1u);
  office_go(2u,0u);assert(view().count==4u && !strcmp(view().rows[0].label,"MY TEAMS"));
  press(DOWN);press(A);assert(view().page==ML_PAGE_OFFERS && view().empty[0]);
  press(B);press(DOWN);press(DOWN);press(A);assert(view().page==ML_PAGE_MARKET_PLAYERS && view().rows[0].rating);
  assert(strstr(view().left_title,"WEAK POSITION"));
  press(B);press(DOWN);press(DOWN);press(DOWN);press(A);
  assert(!strcmp(view().drawer.title,"SELECT LEAGUE"));
  press(A);assert(!strcmp(view().drawer.title,"SELECT TEAM"));
  if(!strcmp(view().drawer.rows[view().drawer.selected].label,exhibition_team_catalog_name(c->settings.club)))press(DOWN);
  press(A);assert(view().page==ML_PAGE_MARKET_PLAYERS);
  const int64_t balance=ml_find_club(c,c->settings.club)->cash;
  press(A);assert(view().drawer.open && view().drawer.modal && view().drawer.count==3u);
  assert(view().drawer.rows[1].adjustable==2u);
  const uint32_t wage=term_tenths(view().drawer.rows[1].value,'K');
  const uint32_t fee=term_tenths(view().drawer.rows[2].value,'M');
  press(RIGHT); /* four years */
  press(DOWN);press(RIGHT);assert(term_tenths(view().drawer.rows[1].value,'K')==wage+10u);
  press(DOWN);press(RIGHT);assert(term_tenths(view().drawer.rows[2].value,'M')==fee+1u);
  press(DOWN);press(A);assert(!view().drawer.open && c->office.offer_count==1u);
  const MlOffer *o=&c->office.offers[0];const uint32_t player=o->player;
  assert(o->years==4u && o->status==ML_OFFER_WAITING && c->players[player].club!=c->settings.club);
  assert(balance==ml_find_club(c,c->settings.club)->cash);
  office_go(0u,0u);assert(!strcmp(view().left_title,"TRANSFER WINDOW OPENS"));
  ml_frontend_pad(A);assert(view().page==ML_PAGE_ADVANCE && !view().helper_count);
  const uint32_t committed=c->transaction_sequence;
  ml_frontend_pad(A|B|R);assert(view().page==ML_PAGE_ADVANCE && c->transaction_sequence==committed);
  finish_advance();
  assert(view().page==ML_PAGE_HUB && c->day==0u);
  office_go(0u,0u);assert(!strcmp(view().left_title,"TRANSFER RESPONSE"));ml_frontend_pad(A);
  assert(view().page==ML_PAGE_ADVANCE && !view().advance_progress);
  const uint32_t landed=c->day,sequence=c->transaction_sequence;
  const int64_t saved_cash=ml_find_club(c,c->settings.club)->cash;
  ui_clock+=600u;ml_frontend_tick(ui_clock);assert(view().advance_progress>0.f && view().advance_progress<1.f);
  for(uint32_t i=0;i<20u;i++){(void)view();ml_frontend_pad(A);}
  assert(c->day==landed && c->transaction_sequence==sequence && ml_find_club(c,c->settings.club)->cash==saved_cash);
  finish_advance();assert(view().page==ML_PAGE_HUB && strstr(view().toast,"response"));
  assert(view().transfer_unread && ml_offer_unread(c,0u));
  assert(o->status==ML_OFFER_ACCEPTED && c->day>=1u && c->day<=3u);
  office_go(2u,0u);assert(view().rows[1].unread);press(DOWN);press(A);assert(view().page==ML_PAGE_OFFERS);
  assert(view().rows[0].unread);(void)view();assert(ml_offer_unread(c,0u)); /* mere projection is not reading */
  press(A);assert(!view().rows[0].unread && !ml_offer_unread(c,0u));
  assert(!strcmp(view().drawer.rows[0].label,"ACCEPT TERMS"));press(A);
  assert(o->status==ML_OFFER_COMPLETED && c->players[player].club==c->settings.club && ml_valid(c));
  office_go(2u,0u);press(A);assert(view().page==ML_PAGE_MY_TEAM && view().count==2u);
  press(A);assert(view().page==ML_PAGE_OFFERS && view().count);
  press(A);press(DOWN);press(A); /* decline inbound */
  assert(strstr(view().rows[0].detail,"CANCELLED"));
  press(A);assert(view().drawer.modal==2 && !view().drawer.count && view().helper_count==1u);
  const uint32_t closed_sequence=c->transaction_sequence;press(A);
  assert(c->transaction_sequence==closed_sequence);press(B);
  /* Expired BUYER offer does not mean an expired player contract. Renewal
   * changes the contract/fee only, never reopens or accepts that old bid. */
  MasterLeague *fixture=(MasterLeague *)c;MlOffer *expired=NULL;
  for(uint32_t i=0;i<fixture->office.offer_count;i++)if(fixture->office.offers[i].incoming) {
    fixture->office.offers[i].status=ML_OFFER_EXPIRED;expired=&fixture->office.offers[i];
  }
  assert(expired);press(A);assert(view().drawer.count==1u);
  assert(!strcmp(view().drawer.rows[0].label,"RENEW PLAYER CONTRACT"));press(A);
  assert(view().drawer.modal==1 && !strcmp(view().drawer.title,"RENEW CONTRACT"));
  uint32_t renewal_years=0u;assert(sscanf(view().drawer.rows[0].value,"%u",&renewal_years)==1);
  const uint32_t renewal_day=c->day;
  const int64_t expired_cash=ml_find_club(c,c->settings.club)->cash;
  press(A);press(A);assert(!view().drawer.open && expired->status==ML_OFFER_EXPIRED);
  assert(c->players[expired->player].contract_end==c->season+renewal_years && c->day==renewal_day);
  assert(ml_find_club(c,c->settings.club)->cash==expired_cash-ml_renew_fee(c,expired->player,renewal_years));
  /* My Teams exposes contract and release actions without a buyer offer. */
  press(B);press(DOWN);press(A);assert(view().page==ML_PAGE_MY_PLAYERS);
  press(DOWN);
  const uint32_t released=ml_find_club(c,c->settings.club)->players[1u];
  const uint32_t release_quote=ml_release_value(c,released);
  const int64_t release_cash=ml_find_club(c,c->settings.club)->cash;
  press(A);press(DOWN);press(A);assert(view().modal.open && view().modal.selected==1u);
  press(A);assert(!view().modal.open && view().selected==1u && c->players[released].club==c->settings.club);
  press(A);press(DOWN);press(A);press(LEFT);assert(view().modal.selected==0u);press(A);
  assert(c->players[released].club==0u && ml_find_club(c,c->settings.club)->cash==release_cash+release_quote);
  assert(ml_valid(c) && !view().modal.open);
  /* Overwrite is a modal on the slots page and always defaults to Cancel. */
  office_go(0u,4u);press(A);
  assert(view().page==ML_PAGE_SLOTS && view().modal.open && view().modal.selected==1u);
  press(A);assert(!view().modal.open && view().selected==1u);
  office_go(2u,3u);assert(view().page==ML_PAGE_MANAGER_OFFICE);press(DOWN);press(A);
  assert(view().page==ML_PAGE_MESSAGES && view().count);press(A);assert(view().drawer.body[0]);
  office_go(0u,2u);int markers=0;for(uint32_t i=0;i<42u;i++)markers+=view().calendar[i].transfer!=0u;
  assert(markers>=4); /* opening, response, middle, deadline */
  for(uint32_t currency=1u;currency<=2u;currency++) {
    office_go(2u,4u);press(DOWN);press(DOWN);press(DOWN);press(RIGHT);
    press(DOWN);press(DOWN);press(A);assert(c->options.currency==currency);
    const int64_t original_cash=ml_find_club(c,c->settings.club)->cash;
    office_go(2u,0u);press(DOWN);press(DOWN);press(A);press(A);
    const uint32_t old_fee=term_tenths(view().drawer.rows[2].value,'M');
    press(A);press(A); /* A advances fields, never sends early */
    press(RIGHT);assert(term_tenths(view().drawer.rows[2].value,'M')==old_fee+1u);
    press(LEFT);assert(term_tenths(view().drawer.rows[2].value,'M')==old_fee);
    press(B);assert(ml_find_club(c,c->settings.club)->cash==original_cash);
  }
  puts("office UI: market navigation, compact currency steps, replies, accept/reject and manager mail OK");
}
int main(void) {
  ml_frontend_open();assert(view().page==ML_PAGE_LANDING);
  press(A);assert(view().page==ML_PAGE_SETTINGS);
  assert(view().count==7u && !view().drawer.open);
  assert(view().rows[0].league_logo && view().rows[0].badge); /* embedded fallback */
  press(A);assert(view().drawer.open && !strcmp(view().drawer.title,"SELECT LEAGUE"));
  press(B);assert(!view().drawer.open && view().selected==0u);
  press(DOWN);press(A);press(DOWN);press(A); /* first seed has an opening bye */
  assert(view().selected==1u && !view().drawer.open);
  press(DOWN);press(A);assert(!view().drawer.open); /* general values inline */
  assert(!strcmp(view().rows[2].value,"PROFESSIONAL"));
  press(RIGHT);press(RIGHT);press(RIGHT); /* Legend */
  press(DOWN);press(RIGHT); /* 15 min */
  press(DOWN);press(RIGHT); /* Hard transfers */
  press(DOWN);press(RIGHT); /* GBP */
  press(DOWN);press(RIGHT); /* skip first window */
  press(DOWN);
  press(A);assert(view().page==ML_PAGE_MANAGER && view().count==2u);
  press(DOWN);press(DOWN);press(A);
  assert(view().page==ML_PAGE_MANAGER && !ml_frontend_career());
  press(UP);press(UP);press(A);
  assert(ml_frontend_take_action()==ML_ACTION_NAME_INPUT);
  ml_frontend_name_result("Test Manager");
  press(DOWN);press(A);assert(view().page==ML_PAGE_MANAGER && view().drawer.open);
  assert(view().drawer.count>0u);
  for(uint32_t i=1;i<view().drawer.count;i++)assert(strcmp(view().drawer.rows[i-1u].label,view().drawer.rows[i].label)<0);
  press(A);
  assert(view().page==ML_PAGE_MANAGER);
  press(DOWN);press(A);assert(view().page==ML_PAGE_SLOTS);
  press(A);assert(view().page==ML_PAGE_HUB);
  const MasterLeague *career=ml_frontend_career();assert(career && ml_valid(career));
  assert(career->settings.difficulty==6u && career->settings.match_minutes==15u);
  assert(career->options.currency==1u && career->options.transfer_difficulty==2u);
  assert(career->options.skip_first_window && !ml_window_open(career));
  assert(!strcmp(career->manager_name,"Test Manager") && career->manager_nationality);
  /* Dashboard cards must project this career, not canned demo data. Reading
   * the view never advances dates, fixtures or transactions. */
  MlView dashboard=view();MlEvent preview_event;
  assert(ml_next_event(career,&preview_event));
  assert(!strcmp(dashboard.club_name,exhibition_team_catalog_name(career->settings.club)));
  assert(dashboard.squad_size==24u && dashboard.ranking_count==3u);
  assert(dashboard.fixture_count>0u && dashboard.fixture_count<=3u);
  assert(dashboard.squad_count==3u && dashboard.rank==ml_rank(career));
  if(preview_event.home && preview_event.away) {
    assert(!strcmp(dashboard.next.home,exhibition_team_catalog_name(preview_event.home)));
    assert(dashboard.next.home_badge==exhibition_team_catalog_badge(preview_event.home));
    assert(!strcmp(dashboard.next.away,exhibition_team_catalog_name(preview_event.away)));
  }
  const uint32_t before_day=career->day,before_transactions=career->transaction_sequence;
  for(int i=0;i<8;i++)(void)view();
  assert(career->day==before_day && career->transaction_sequence==before_transactions);
  assert(dashboard.annual_budget[0] && dashboard.transfer_budget[0]);
  /* Bottom row has three real focus targets, not a skipped middle snapshot. */
  press(DOWN);assert(view().selected==2u);
  press(RIGHT);assert(view().selected==3u);press(A);assert(view().page==ML_PAGE_TABLE);
  press(B);press(DOWN);press(A);assert(view().page==ML_PAGE_CALENDAR);
  assert(view().calendar_count==42u && !strcmp(view().calendar_month,"JULY 2026"));
  press(R);assert(!strcmp(view().calendar_month,"AUGUST 2026"));
  int scheduled=0;for(uint32_t i=0;i<42u;i++)scheduled+=view().calendar[i].kind!=0u;
  assert(scheduled && career->day==before_day);press(B);
  /* Existing careers skip locked league/club; B rolls back un-applied values. */
  press(R);press(R);press(DOWN);press(RIGHT);press(RIGHT);press(A);
  assert(view().page==ML_PAGE_SETTINGS && view().selected==2u);
  press(UP);assert(view().selected==2u && !view().rows[0].enabled);
  press(A);assert(!view().drawer.open);press(LEFT);assert(view().rows[2].adjustable);
  press(B);assert(view().page==ML_PAGE_HUB);
  /* The office editor creates no fixture and cannot accept match results. */
  press(LEFT);press(LEFT);press(LEFT); /* section one, top/right or bottom/right */
  while(view().section>1u)press(1u<<4);
  press(UP);press(LEFT); /* force first card via direct section shortcut below */
  if(view().section==0u)press(R);
  if(view().selected)press(LEFT);
  press(A);assert(view().page==ML_PAGE_SQUAD && view().count==2u);
  press(A);assert(view().drawer.open && view().drawer.total==24u);press(B);
  press(DOWN);press(A);assert(ml_frontend_plan_editor());
  assert(ml_frontend_take_action()==ML_ACTION_MATCH && career->day==before_day);
  GameplanPreset permanent={0};permanent.team_id=career->settings.club;
  const MlClub *managed=ml_find_club(career,career->settings.club);permanent.player_count=managed->count;
  for(uint32_t i=0;i<managed->count;i++) {
    const uint32_t native=career->players[managed->players[i]].native_id;
    memcpy(permanent.players[i].player_id,&native,4u);permanent.players[i].order_no=i;
  }
  permanent.players[1].order_no=12u;permanent.players[12].order_no=1u;
  assert(ml_frontend_store_current_plan(&permanent));
  assert(!memcmp(&career->current_plan,&permanent,sizeof(permanent)));
  const uint32_t before_fixtures=career->league.active_matchday;
  ml_frontend_result(9,0,NULL,0);assert(career->league.active_matchday==before_fixtures);
  assert(ml_frontend_restore() && view().page==ML_PAGE_SQUAD && !ml_frontend_plan_editor());
  press(B);press(1u<<4); /* home */
  /* Two-dimensional navigation: only crossing a horizontal edge changes page. */
  press(UP); /* normalize focus to top row */
  if(view().selected)press(LEFT);
  assert(view().section==0u && view().selected==0u);
  press(RIGHT);assert(view().section==0u && view().selected==1u);
  press(RIGHT);assert(view().section==1u && view().selected==0u);
  const uint32_t serial=view().navigation_serial;
  press(LEFT);assert(view().section==0u && view().selected==1u);
  assert(view().navigation_serial>serial);
  press(A);assert(view().page==ML_PAGE_NEWS);
  press(RIGHT);assert(view().feed_index==1u);
  press(LEFT);assert(view().feed_index==0u);
  press(B);assert(view().page==ML_PAGE_HUB);
  press(UP);press(A);assert(view().page==ML_PAGE_NEXT);
  const int64_t match_cash=ml_find_club(career,career->settings.club)->cash;
  press(A);assert(view().modal.open && view().page==ML_PAGE_NEXT);
  assert(ml_frontend_take_action()==ML_ACTION_NONE && career->day==before_day);
  press(B);assert(!view().modal.open && !ml_frontend_match_active());
  press(A);press(A);assert(ml_frontend_take_action()==ML_ACTION_MATCH);
  assert(career->day==before_day && ml_find_club(career,career->settings.club)->cash==match_cash);
  ml_frontend_handoff_result(0);
  assert(!ml_frontend_match_active() && career->day==before_day);
  assert(ml_find_club(career,career->settings.club)->cash==match_cash);
  office_go(0u,0u);press(A);press(A);assert(ml_frontend_take_action()==ML_ACTION_MATCH);
  assert(ml_frontend_match_active());
  assert(!ml_frontend_plan_editor());
  GameplanPreset temporary=permanent;temporary.tactics=1u;
  assert(!ml_frontend_store_current_plan(&temporary));
  assert(!memcmp(&career->current_plan,&permanent,sizeof(permanent)));
  uint32_t home,away,ids[40],count;uint8_t shirts[40];
  assert(ml_frontend_match_teams(&home,&away) && home==career->settings.club && away!=home);
  assert(ml_frontend_roster(home,ids,shirts,&count) && count==24u);
  assert(ml_frontend_player_allowed(home,ids[0])==1);
  assert(ml_frontend_player_allowed(away,ids[0])==0);
  ml_frontend_handoff_result(1);
  const uint32_t scoring_player=managed->players[1u];
  const LeagueScorer scorer={.team=career->settings.club,.base_id=career->players[scoring_player].identity,
    .portrait_id=career->players[scoring_player].native_id,.goals=3u,.name="Synthetic Scorer"};
  ml_frontend_result(3u,1u,&scorer,1u);
  const uint32_t day=career->league.active_matchday;
  ml_frontend_result(3u,1u,NULL,0u);assert(career->league.active_matchday==day);
  assert(ml_frontend_restore() && !ml_frontend_match_active());
  assert(view().page==ML_PAGE_ADVANCE && view().advance_progress==0.f);
  const uint32_t landed_day=career->day,landed_sequence=career->transaction_sequence;
  const int64_t landed_cash=ml_find_club(career,career->settings.club)->cash;
  ml_frontend_pad(A|B|R);assert(view().page==ML_PAGE_ADVANCE);
  assert(!ml_frontend_restore());finish_advance();assert(view().page==ML_PAGE_HUB);
  assert(career->day==landed_day && career->transaction_sequence==landed_sequence);
  assert(ml_find_club(career,career->settings.club)->cash==landed_cash);
  assert(ml_frontend_player_allowed(home,ids[0])==-1); /* base mode regains authority */
  assert(!ml_frontend_roster(home,ids,shirts,&count));
  office_go(0u,3u);press(Y);assert(view().count && view().rows[0].badge);
  office_go(0u,1u);while(view().feed_index!=1u)press(RIGHT);
  assert(view().story.has_result && view().story.home_badge && view().story.away_badge && view().story.history_count);
  assert(view().story.home_goals+view().story.away_goals==4u);
  press(B);
  press(B);assert(ml_frontend_take_action()==ML_ACTION_EXIT);
  ml_frontend_open();press(DOWN);press(A);press(A);
  assert(view().page==ML_PAGE_HUB && ml_frontend_career()->league.active_matchday==day);
  assert(career->options.currency==1u && career->options.transfer_difficulty==2u && career->options.skip_first_window);
  /* The managed club is always native HOME even for an away cup fixture. */
  MlEvent next;int decided=0;
  for(unsigned tries=0;tries<64u;tries++) {
    assert(ml_next_event(career,&next) && next.kind!=ML_EVENT_SEASON_END);
    press(A);assert(view().page==ML_PAGE_NEXT);
    if(next.kind==ML_EVENT_CUP && next.home && next.away) {
      press(A);assert(view().modal.open);press(A);assert(ml_frontend_take_action()==ML_ACTION_MATCH);
      assert(ml_frontend_match_teams(&home,&away) && home==career->settings.club);
      const uint32_t round=career->cup.active_round;
      ml_frontend_result(1u,1u,NULL,0u);
      assert(career->cup.active_round==round); /* missing shootout must not guess */
      ml_frontend_penalty_result(5u,4u);
      ml_frontend_result(1u,1u,NULL,0u);
      assert(career->cup.fixtures[next.round][next.index].winner==career->settings.club);
      assert(ml_frontend_restore());finish_advance();decided=1;break;
    }
    if(next.kind>=ML_EVENT_WINDOW)press(A);
    else {press(DOWN);press(A);assert(view().modal.open && view().page==ML_PAGE_NEXT);press(A);}
    assert(view().page==ML_PAGE_HUB);
  }
  assert(decided && ml_valid(career));
  for(int i=0;i<5;i++)press(R);
  assert(view().section==3u);
  office_ui_tests();
  puts("career UI: profile, paged hub, feed, native context, save/continue OK");
  return 0;
}

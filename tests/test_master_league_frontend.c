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
static MlView view(void) { MlView v;ml_frontend_view(&v);return v; }
static void press(uint32_t b) { ml_frontend_pad(b); }
int main(void) {
  ml_frontend_open();assert(view().page==ML_PAGE_LANDING);
  press(A);assert(view().page==ML_PAGE_SETTINGS);
  press(DOWN);press(RIGHT); /* first seed has an opening bye in odd leagues */
  for(int i=0;i<4;i++)press(DOWN);
  press(A);assert(view().page==ML_PAGE_MANAGER && view().count==2u);
  press(DOWN);press(DOWN);press(A);
  assert(view().page==ML_PAGE_MANAGER && !ml_frontend_career());
  press(UP);press(UP);press(A);
  assert(ml_frontend_take_action()==ML_ACTION_NAME_INPUT);
  ml_frontend_name_result("Test Manager");
  press(DOWN);press(A);assert(view().page==ML_PAGE_NATIONALITY);
  assert(view().count>0u);press(A);
  assert(view().page==ML_PAGE_MANAGER);
  press(DOWN);press(A);assert(view().page==ML_PAGE_SLOTS);
  press(A);assert(view().page==ML_PAGE_HUB);
  const MasterLeague *career=ml_frontend_career();assert(career && ml_valid(career));
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
  press(A);assert(ml_frontend_take_action()==ML_ACTION_MATCH);
  assert(ml_frontend_match_active());
  uint32_t home,away,ids[40],count;uint8_t shirts[40];
  assert(ml_frontend_match_teams(&home,&away) && home==career->settings.club && away!=home);
  assert(ml_frontend_roster(home,ids,shirts,&count) && count==24u);
  assert(ml_frontend_player_allowed(home,ids[0])==1);
  assert(ml_frontend_player_allowed(away,ids[0])==0);
  ml_frontend_handoff_result(1);
  ml_frontend_result(3u,1u,NULL,0u);
  const uint32_t day=career->league.active_matchday;
  ml_frontend_result(3u,1u,NULL,0u);assert(career->league.active_matchday==day);
  assert(ml_frontend_restore() && !ml_frontend_match_active());
  assert(ml_frontend_player_allowed(home,ids[0])==-1); /* base mode regains authority */
  assert(!ml_frontend_roster(home,ids,shirts,&count));
  press(B);assert(ml_frontend_take_action()==ML_ACTION_EXIT);
  ml_frontend_open();press(DOWN);press(A);press(A);
  assert(view().page==ML_PAGE_HUB && ml_frontend_career()->league.active_matchday==day);
  /* The managed club is always native HOME even for an away cup fixture. */
  MlEvent next;int decided=0;
  for(unsigned tries=0;tries<64u;tries++) {
    assert(ml_next_event(career,&next) && next.kind!=ML_EVENT_SEASON_END);
    press(A);assert(view().page==ML_PAGE_NEXT);
    if(next.kind==ML_EVENT_CUP && next.home && next.away) {
      press(A);assert(ml_frontend_take_action()==ML_ACTION_MATCH);
      assert(ml_frontend_match_teams(&home,&away) && home==career->settings.club);
      const uint32_t round=career->cup.active_round;
      ml_frontend_result(1u,1u,NULL,0u);
      assert(career->cup.active_round==round); /* missing shootout must not guess */
      ml_frontend_penalty_result(5u,4u);
      ml_frontend_result(1u,1u,NULL,0u);
      assert(career->cup.fixtures[next.round][next.index].winner==career->settings.club);
      assert(ml_frontend_restore());decided=1;break;
    }
    press(DOWN);press(A);assert(view().page==ML_PAGE_CONFIRM);
    press(A);assert(view().page==ML_PAGE_HUB);
  }
  assert(decided && ml_valid(career));
  for(int i=0;i<5;i++)press(R);
  assert(view().section==3u);
  puts("career UI: profile, paged hub, feed, native context, save/continue OK");
  return 0;
}

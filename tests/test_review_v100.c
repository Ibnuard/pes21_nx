#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "manager_league_catalog_fixture.inc"
#include "../source/manager_league_dummy.c"
#include "match_preferences.h"
#include "menu_axis_navigation.h"
#include "loading_popup.h"
#include "trophy_canary_config.h"
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#c);exit(97);}}while(0)
int main(void) {
  uint32_t seed=99,seen_time=0,seen_weather=0,seen_season=0;
  for(uint32_t i=0;i<1000;i++) {
    uint32_t time=nx_preference_resolve(NX_TIME_RANDOM,2,&seed);
    uint32_t weather=nx_preference_resolve(NX_WEATHER_RANDOM,3,&seed);
    uint32_t season=nx_preference_resolve(NX_SEASON_RANDOM,2,&seed);
    assert(time<2 && weather<3 && season<2);
    seen_time|=1u<<time;seen_weather|=1u<<weather;seen_season|=1u<<season;
  }
  assert(seen_time==3 && seen_weather==7 && seen_season==3);
  uint32_t before=seed;assert(nx_preference_resolve(1,2,&seed)==1 && seed==before);
  assert(nx_preference_next(2,2,1)==0 && nx_preference_next(0,2,-1)==2);
  assert(!strcmp(nx_time_preference_label(2),"RANDOM") && !strcmp(nx_season_preference_label(2),"RANDOM"));
  NxMenuAxisRepeat nav={0};uint32_t buttons=nx_menu_axis_buttons(2,0,32767);
  assert(buttons==(2|DOWN));assert(!nx_menu_axis_repeat(&nav,buttons,100));
  assert(!nx_menu_axis_repeat(&nav,buttons,449));assert(nx_menu_axis_repeat(&nav,buttons,450)==DOWN);
  assert(!nx_menu_axis_repeat(&nav,buttons,559));assert(nx_menu_axis_repeat(&nav,buttons,560)==DOWN);
  assert(!nx_menu_axis_repeat(&nav,0,600));assert(nx_menu_axis_buttons(0,12000,12000)==0);
  assert(nx_menu_axis_buttons(0,-32767,19000)==LEFT);
  assert(nx_menu_axis_buttons(UP,32767,32767)==UP);
  uint64_t old=nx_loading_begin("CONNECTING","Contacting the league server...");
  uint64_t current=nx_loading_begin("LOADING","Loading club data...");NxLoadingView loading;
  assert(nx_loading_active() && !nx_loading_finish(old) && !nx_loading_update(old,"stale"));
  assert(nx_loading_update(current,"Preparing your club..."));nx_loading_snapshot(&loading);
  assert(loading.token==current && !strcmp(loading.message,"Preparing your club..."));
  assert(nx_loading_finish(current) && !nx_loading_active() && !nx_loading_finish(current));
  epoch_now=MD_RANK_EPOCH+9u*UINT64_C(3600000);loaded=authenticated=1;
  memset(&md,0,sizeof(md));md.balance=5000;md.seed=1729;md.club=100;md.week_id=1;
  strcpy(md.name,"Review United");assert(profile_create());strcpy(profile.user_id,"review_manager");
  profile.tutorials=7;assert(profile_save());md.created=md.joined=1;make_fixtures();assert(persist());
  notice[0]=0;page=MD_WATCH;fixture_choice=0;epoch_now=md.fixtures[0].kickoff_ms+180000;
  manager_dummy_pad(Y);MdView *v=malloc(sizeof(*v));assert(v);manager_dummy_view(v);
  assert(v->touchline_total>=20 && v->touchline_first==0 && v->touchline[0].selected);
  manager_dummy_pad(DOWN);manager_dummy_view(v);assert(v->touchline[1].selected);
  for(uint32_t i=0;i<5;i++)manager_dummy_pad(DOWN);manager_dummy_view(v);
  assert(v->touchline_first==4 && v->touchline[2].selected);
  manager_dummy_pad(B);assert(page==MD_WATCH && !touchline_open);
  page=MD_REWARDS;focus=0;for(uint32_t i=0;i<8;i++)manager_dummy_pad(DOWN);
  manager_dummy_view(v);assert(v->focus==4 && v->rows[4].selected);
  manager_dummy_pad(UP);manager_dummy_view(v);assert(v->focus==3 && v->rows[3].selected);
  free(v);return 0;
}

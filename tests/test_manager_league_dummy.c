#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include "manager_league_dummy.h"
#include "main_menu_layout.h"
#include "competition_hub_navigation.h"
#include <math.h>
#include "manager_league_catalog_fixture.inc"
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#c);exit(97);}}while(0)
enum {B=1,A=2,Y=4,X=8,UP=1024,DOWN=2048,LEFT=4096,RIGHT=8192,L=16,R=128};
static MdView view(void) {MdView v;manager_dummy_view(&v);return v;}
static void go(uint32_t section,uint32_t target) {
  for(unsigned i=0;i<8 && view().page!=MD_DASHBOARD;i++)manager_dummy_pad(B);
  assert(view().page==MD_DASHBOARD);
  while(view().focus>=2)manager_dummy_pad(UP);
  if(view().focus==1)manager_dummy_pad(LEFT);
  for(unsigned i=0;i<4 && view().tab!=section;i++)manager_dummy_pad(view().tab>section ? L : R);
  assert(view().tab==section);
  if(target==1)manager_dummy_pad(RIGHT);
  else if(target>=2){manager_dummy_pad(DOWN);for(unsigned i=2;i<target;i++)manager_dummy_pad(RIGHT);}
  assert(view().focus==target);manager_dummy_pad(A);
}

static void onboard(void) {
  manager_dummy_open();assert(view().page==MD_REGISTER && view().placeholder && !view().badge);
  assert(!strcmp(view().name,"YOUR CLUB"));manager_dummy_tick_at(1793015700000ULL);
  manager_dummy_pad(A);assert(view().page==MD_LEAGUES);
  manager_dummy_pad(A);assert(view().page==MD_CLUB);manager_dummy_pad(A);assert(view().page==MD_NAME);
  manager_dummy_pad(A);assert(manager_dummy_take_action()==MD_ACTION_NAME);
  manager_dummy_name_result(" Androswitch FC ");assert(!strcmp(view().name,"Androswitch FC"));
  manager_dummy_pad(DOWN);manager_dummy_name_result("wrong id!");assert(!view().user_id[0]);
  manager_dummy_name_result("androswitch_27");assert(!strcmp(view().user_id,"androswitch_27"));
  manager_dummy_pad(DOWN);assert(manager_dummy_input_password());manager_dummy_name_result("Secret-Password-27");
  manager_dummy_pad(X);assert(view().page==MD_DASHBOARD && view().tutorial==1);
  assert(view().modal.information);manager_dummy_pad(B);assert(view().tutorial==1);
  for(int i=0;i<3;i++)manager_dummy_pad(A);assert(!view().tutorial);
}
static void choose_pack(void) {
  MdView v=view();assert(v.page==MD_PACK_OPENING && v.balance<=5000);
  manager_dummy_pad(A);assert(view().page==MD_PACK_OPENING);
  manager_dummy_tick_at(v.now_ms+MD_PACK_OPEN_MS+500);v=view();assert(v.page==MD_PACK_SELECT && v.pack_selection_count==0);
  uint32_t needed=v.pack_draw,pool=v.pack_pool;
  for(uint32_t i=0;i<needed;i++) {
    while(view().focus%4>i%4)manager_dummy_pad(LEFT);
    while(view().focus%4<i%4)manager_dummy_pad(RIGHT);
    if(view().focus/4<i/4)manager_dummy_pad(DOWN);
    manager_dummy_pad(A);
  }
  assert(view().page==MD_PACK_SELECT && view().pack_selection_count==needed);
  while(view().focus!=pool)manager_dummy_pad(DOWN);
}
static void motion_test(const MdFixture *f) {
  MdDot a[23],b[23],same[23];
  manager_dummy_sample(f,0,a);
  assert(a[22].x==.5f && a[22].y==.5f);
  for(uint32_t n=0;n<11;n++) {
    assert(a[n].x<.5f && a[11+n].x>.5f);
    if(n)assert(hypotf((a[11+n].x-.5f)*105,(a[11+n].y-.5f)*68)>=9.15f);
  }
  manager_dummy_sample(f,500,b);assert(!memcmp(a,b,sizeof(a)));
  manager_dummy_sample(f,1100,b);assert(b[22].x<.5f); /* backward kickoff pass */
  for(uint32_t t=0;t<MD_DURATION;t+=17) {
    manager_dummy_sample(f,t,a);manager_dummy_sample(f,t+1,b);manager_dummy_sample(f,t,same);
    assert(!memcmp(a,same,sizeof(a)));
    for(uint32_t i=0;i<23;i++){assert(a[i].x>=0 && a[i].x<=1 && a[i].y>=0 && a[i].y<=1);
      assert(fabsf(a[i].x-b[i].x)<.002f && fabsf(a[i].y-b[i].y)<.002f);}
  }
  for(uint32_t i=0;i<MD_EVENTS;i++) {
    const MdEvent *e=&f->events[i];manager_dummy_sample(f,e->at_ms,a);
    if(e->kind==MD_SAVE){uint32_t keeper=(1-e->side)*11;assert(a[22].x==a[keeper].x && a[22].y==a[keeper].y);}
    if(e->kind==MD_GOAL)assert(a[22].x>.98f || a[22].x<.02f);
    if(e->kind==MD_GOAL) {
      manager_dummy_sample(f,e->at_ms+500,b);assert(b[22].x==a[22].x && b[22].y==a[22].y);
      manager_dummy_sample(f,e->at_ms+3150,b);assert(b[22].x==.5f && b[22].y==.5f);
    }
    if(e->kind==MD_FOUL || e->kind==MD_YELLOW || e->kind==MD_SAVE) {
      manager_dummy_sample(f,e->at_ms+500,b);assert(b[22].x==a[22].x && b[22].y==a[22].y);
    }
    if(e->kind==MD_PASS){int found=0;for(uint32_t n=0;n<11;n++){MdDot *p=&a[e->side*11+n];if(p->x==a[22].x && p->y==a[22].y)found=1;}assert(found);}
    if(e->kind==MD_SUB){int found=0;for(uint32_t n=0;n<11;n++)found|=a[e->side*11+n].number==e->other;assert(found);}
  }
}
int main(int argc,char **argv) {
  assert(argc==2);
  if(!strcmp(argv[1],"reload")) {
    manager_dummy_open();assert(view().page==MD_REGISTER);manager_dummy_pad(A);assert(view().page==MD_LOGIN);
    manager_dummy_name_result("androswitch_27");manager_dummy_pad(DOWN);manager_dummy_name_result("Secret-Password-27");
    manager_dummy_pad(DOWN);manager_dummy_pad(A);assert(view().page==MD_DASHBOARD && !view().tutorial);
    assert(view().balance==4000 && !strcmp(view().user_id,"androswitch_27"));
    MdSave saved;manager_dummy_copy_save(&saved);assert(manager_dummy_valid(&saved));return 0;
  }
  if(!strcmp(argv[1],"corrupt")) {
    manager_dummy_open();assert(strstr(view().status,"INVALID"));manager_dummy_pad(A);assert(view().page==MD_REGISTER);
    manager_dummy_pad(B);assert(manager_dummy_take_action()==MD_ACTION_EXIT);return 0;
  }
  onboard();MdSave saved,before;manager_dummy_copy_save(&saved);assert(manager_dummy_valid(&saved));before=saved;
  if(!strcmp(argv[1],"shopfail")) {
    go(1,2);manager_dummy_pad(A);assert(view().page==MD_PACK);
    assert(mkdir("SaveData/manager-league-profile-v2.dat.tmp",0700)==0);
    manager_dummy_pad(A);choose_pack();manager_dummy_pad(A);assert(view().balance==5000 && strstr(view().status,"NO POINTS CHARGED"));return 0;
  }
  if(!strcmp(argv[1],"tier1") || !strcmp(argv[1],"tier2")) {
    uint32_t k=(uint32_t)(argv[1][4]-'0');go(1,2);for(uint32_t n=0;n<k;n++)manager_dummy_pad(RIGHT);manager_dummy_pad(A);
    assert(view().pack_pool==(k==1 ? 6 : 8) && view().pack_draw==(k==1 ? 4 : 5));manager_dummy_pad(A);choose_pack();manager_dummy_pad(A);
    assert(view().page==MD_PACK_RESULT && view().pack_count==(k==1 ? 4 : 5));
    for(uint32_t i=0;i<view().pack_count;i++)for(uint32_t j=0;j<i;j++)assert(view().pack_players[i].identity!=view().pack_players[j].identity);return 0;
  }
  assert(view().week.state==MD_PRE_LEAGUE && view().roster_size==18);
  go(0,1);assert(view().page==MD_NEWS && view().total==MD_TEAMS);
  for(uint32_t i=0;i<6;i++)manager_dummy_pad(DOWN);
  assert(view().focus==6);manager_dummy_pad(A);assert(view().page==MD_TEAM_INFO);
  manager_dummy_pad(B);assert(view().page==MD_NEWS && view().focus==6);
  go(2,2);assert(view().count==MD_MATCH_VISIBLE && view().total==MD_FIXTURES);
  manager_dummy_pad(RIGHT);assert(view().focus==1);manager_dummy_pad(DOWN);assert(view().focus==3);
  manager_dummy_pad(UP);manager_dummy_pad(LEFT);assert(!view().focus);

  for(uint32_t day=1;day<=7;day++) {
    uint64_t t=day<=3 ? saved.fixtures[0].kickoff_ms-(4u-day)*(uint64_t)MD_PREPARATION_DAY_MS
                     : saved.fixtures[0].kickoff_ms+(day-4u)*(uint64_t)MD_DEMO_DAY_MS;
    MdWeek week=manager_dummy_week(&saved,t);assert(week.day==day && week.state==(day<=3 ? MD_PRE_LEAGUE : day<=6 ? MD_MATCH_DAY : MD_RESULT));
  }
  go(0,2);assert(view().page==MD_CALENDAR && view().count==MD_WEEK_VISIBLE && view().total==7);
  uint32_t own_matches=0;
  for(uint32_t d=0;d<7;d++) {
    MdView week=view();assert(week.focus==d && week.focus>=week.first && week.focus<week.first+week.count);
    assert(week.count==3 && week.first<=4 && week.first+week.count<=week.total);
    for(uint32_t i=0;i<week.count;i++)assert(strlen(week.rows[i].value)>=10 && strchr(week.schedule[i].period,':'));
    uint32_t i=week.focus-week.first;assert(week.rows[i].selected);
    MdScheduleDay *tile=&week.schedule[i];uint32_t expected=0;
    for(uint32_t f=0;f<MD_FIXTURES;f++) {
      const MdFixture *match=&saved.fixtures[f];uint32_t day=match->round<3 ? 3 : match->round<5 ? 4 : 5;
      if(day==d && (match->home==0 || match->away==0)) {
        assert(expected<tile->match_count);
        MdRow *opponent=&tile->matches[expected++];
        assert(opponent->team_id==(match->home ? match->home : match->away));
        assert(!strncmp(opponent->label,"Vs ",3) && strlen(opponent->label)>3 && strchr(opponent->value,':') && opponent->badge);
        assert(!strcmp(opponent->detail,match->home==0 ? "HOME" : "AWAY"));
      }
    }
    assert(tile->match_count==expected);own_matches+=expected;
    if(d==3) {
      manager_dummy_pad(A);assert(view().page==MD_SCHEDULE && view().total==9);
      manager_dummy_pad(B);assert(view().page==MD_CALENDAR && view().focus==d);
    }
    manager_dummy_pad(DOWN);
  }
  assert(own_matches==6 && view().focus==6 && view().first==4);
  for(uint32_t d=6;d;d--){manager_dummy_pad(UP);assert(view().focus==d-1);}
  manager_dummy_pad(UP);assert(view().focus==0 && view().first==0);
  go(1,0);assert(view().page==MD_TEAM_INFO && view().count==5 && view().rows[0].portrait && view().rows[0].identity);
  uint32_t ids[18]={0};for(uint32_t i=0;i<18;i++){MdView v=view();MdRow *r=&v.rows[v.focus-v.first];assert(r->rating>=60 && r->rating<=69);
    ids[i]=r->identity;for(uint32_t j=0;j<i;j++)assert(ids[j]!=ids[i]);manager_dummy_pad(DOWN);}
  go(1,1);assert(manager_dummy_take_action()==MD_ACTION_PLAN && manager_dummy_plan_editor());
  uint32_t home=0,away=0,players[40],count=0;uint8_t shirts[40];assert(manager_dummy_plan_teams(&home,&away) && home!=away);
  assert(manager_dummy_roster(home,players,shirts,&count) && count==18);assert(manager_dummy_player_allowed(home,players[0])==1);
  ManagerLeaguePlanScope scope;assert(manager_dummy_plan_scope(&scope) && scope.player_count==18 && manager_league_plan_scope_valid(&scope));
  assert(!manager_dummy_preset_write(away,0,NULL));
  GameplanPreset plan={0};plan.team_id=home;plan.player_count=count;
  for(uint32_t i=0;i<count;i++){memcpy(plan.players[i].player_id,&players[i],4);plan.players[i].order_no=(uint8_t)i;}
  plan.players[1].order_no=11;plan.players[11].order_no=1;
  assert(manager_dummy_store_current_plan(&plan));GameplanPreset loaded_plan;assert(manager_dummy_preset_read(home,3,&loaded_plan) && !memcmp(&plan,&loaded_plan,sizeof(plan)));
  manager_dummy_plan_handoff_result(1);assert(manager_dummy_restore() && !manager_dummy_restore());
  assert(manager_dummy_player_allowed(home,players[0])==-1);
  go(1,2);assert(view().page==MD_SHOP);manager_dummy_pad(A);assert(view().page==MD_PACK && view().pack_pool==5 && view().pack_draw==2 && !view().pack_count);
  manager_dummy_pad(A);choose_pack();manager_dummy_pad(A);assert(view().page==MD_PACK_RESULT && view().balance==4000 && view().pack_count==2);
  assert(view().pack_players[0].identity!=view().pack_players[1].identity);
  uint32_t won=view().pack_players[0].identity;manager_dummy_pad(B);manager_dummy_pad(A);manager_dummy_pad(A);
  assert(view().balance==4000 && view().pack_players[0].identity==won); // receipt, never another debit/draw
  manager_dummy_tick_at(saved.fixtures[0].kickoff_ms+60000);go(1,2);manager_dummy_pad(RIGHT);manager_dummy_pad(A);manager_dummy_pad(A);
  assert(view().shop_locked && view().balance==4000 && view().page==MD_PACK);
  go(0,0);assert(view().page==MD_SCHEDULE);manager_dummy_pad(A);assert(view().page==MD_WATCH && view().elapsed_ms==60000 && !view().watching_replay);
  uint32_t serial=view().timeline_serial;manager_dummy_tick_at(saved.fixtures[0].kickoff_ms+MD_DURATION);
  manager_dummy_pad(A);assert(view().watching_replay && view().elapsed_ms==0 && view().timeline_serial!=serial);
  manager_dummy_pad(RIGHT);assert(view().elapsed_ms==15000);manager_dummy_pad(X);assert(view().elapsed_ms==0);
  motion_test(&saved.fixtures[0]);
  for(uint32_t i=0;i<20;i++)(void)view();manager_dummy_copy_save(&saved);assert(!memcmp(&saved,&before,sizeof(saved)));
  assert(view().event_serial==0);
  return 0;
}

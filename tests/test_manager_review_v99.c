#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "manager_league_catalog_fixture.inc"
#include "../source/manager_league_dummy.c"
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"%s:%d: %s (notice=%s)\n",__FILE__,__LINE__,#c,notice);exit(97);}}while(0)
static MdView view(void){MdView v;manager_dummy_view(&v);return v;}
static void setup(void) {
  epoch_now=MD_RANK_EPOCH+9u*UINT64_C(3600000);loaded=authenticated=1;
  memset(&md,0,sizeof(md));md.balance=5000;md.seed=1729;md.club=100;md.week_id=1;
  strcpy(md.name,"Review United");assert(profile_create());strcpy(profile.user_id,"review_manager");
  profile.tutorials=7;assert(profile_save());md.created=md.joined=1;make_fixtures();assert(persist());
  assert(grant_entry_locked(NULL));page=MD_PACK;pack_choice=focus=0;packs_build();notice[0]=0;
}
static void pay(void) {
  manager_dummy_pad(A);assert(page==MD_PACK_BUY && profile.balance==6500 && !pack_pending);
  MdView v=view();assert(v.modal.open && strstr(v.modal.body,"deducted now"));
  manager_dummy_pad(LEFT);manager_dummy_pad(A);
  assert(page==MD_PACK_OPENING && profile.balance==5500 && pack_pending);
  manager_dummy_pad(B);assert(page==MD_PACK_OPENING);
  manager_dummy_tick_at(epoch_now+MD_PACK_OPEN_MS+1);assert(page==MD_PACK_SELECT);
  v=view();for(uint32_t i=0;i<v.helper_count;i++)assert(strcmp(v.helper_key[i],"B"));
}
static void choose(void) {
  manager_dummy_pad(A);manager_dummy_pad(RIGHT);manager_dummy_pad(A);assert(pack_selected==3);
  focus=pack_pools[0];
}
static void finish(void) {
  uint32_t balance=profile.balance;manager_dummy_pad(A);
  assert(page==MD_PACK_RESULT && !pack_pending && profile.balance==balance && profile.collection_count==20);
  assert((profile.receipts&7)==1 && !(profile.receipts&MD_PACK_PENDING_MASK) && !file_exists(MD_PACK_FILE));
}
static void read_raw_profile(MdProfile *p) {
  FILE *f=fopen(MD_PROFILE_FILE,"rb");assert(f && fread(p,1,sizeof(*p),f)==sizeof(*p));fclose(f);
}
int main(int argc,char **argv) {
  assert(argc==2);
  if(!strcmp(argv[1],"recover-corrupt")) {
    epoch_now=MD_RANK_EPOCH+9u*UINT64_C(3600000);load_once();
    assert(blocked && profile_ready && profile.balance==5500 && profile.collection_count==18);
    assert(strstr(notice,"preserved"));return 0;
  }
  if(!strcmp(argv[1],"recover-paid") || !strcmp(argv[1],"recover-debit") || !strcmp(argv[1],"recover-grant")) {
    epoch_now=MD_RANK_EPOCH+9u*UINT64_C(3600000);load_once();assert(!blocked && profile_ready);
    authenticated=1;tutorial=0;
    if(!strcmp(argv[1],"recover-grant")) {
      assert(profile.balance==5500 && profile.collection_count==20 && !pack_pending && !file_exists(MD_PACK_FILE));return 0;
    }
    assert(pack_resume() && page==MD_PACK_SELECT && profile.balance==5500 && profile.collection_count==18);
    if(!strcmp(argv[1],"recover-paid"))assert(pack_selected==1);
    pack_selected=0;focus=0;choose();finish();return 0;
  }
  setup();
  if(!strcmp(argv[1],"flow")) {
    manager_dummy_pad(A);manager_dummy_pad(B);assert(page==MD_PACK && profile.balance==6500);
    pay();manager_dummy_pad(B);assert(page==MD_PACK_SELECT);choose();finish();
    assert(manager_dummy_valid(&md) && profile_valid(&profile));
  } else if(!strcmp(argv[1],"paid-exit")) {
    pay();manager_dummy_pad(A);assert(pack_selected==1);
  } else if(!strcmp(argv[1],"debit-fail")) {
    MdProfile before=profile;assert(!mkdir(MD_PACK_FILE ".tmp",0700));
    manager_dummy_pad(A);manager_dummy_pad(LEFT);manager_dummy_pad(A);
    assert(!blocked && !pack_pending && !memcmp(&before,&profile,sizeof(profile)) && !file_exists(MD_PACK_FILE));
  } else if(!strcmp(argv[1],"debit-interrupt")) {
    manager_dummy_pad(A);assert(!mkdir(MD_PROFILE_FILE ".tmp",0700));manager_dummy_pad(LEFT);manager_dummy_pad(A);
    assert(blocked && file_exists(MD_PACK_FILE));MdProfile saved;read_raw_profile(&saved);assert(saved.balance==6500);
  } else if(!strcmp(argv[1],"grant-interrupt")) {
    pay();choose();assert(!mkdir(MD_PROFILE_FILE ".tmp",0700));manager_dummy_pad(A);
    assert(blocked && file_exists(MD_PACK_FILE));MdProfile saved;read_raw_profile(&saved);assert(saved.balance==5500 && saved.collection_count==18);
  } else if(!strcmp(argv[1],"pending-prize")) {
    pay();epoch_now=manager_dummy_week(&md,UINT64_MAX).result_ms;uint32_t prize=league_prize(&md,0,NULL);
    manager_dummy_tick_at(epoch_now);assert(profile.balance==5500+prize);notice[0]=0;
    assert(!manager_dummy_next_week() && md.week_id==1);notice[0]=0;page=MD_PACK_SELECT;focus=0;
    choose();finish();assert(profile.balance==5500+prize);
  } else if(!strcmp(argv[1],"ranking")) {
    uint32_t points[7];ranking_points(points);for(uint32_t i=0;i<7;i++)assert(!points[i]);
    for(uint32_t league=0;league<4;league++) {
      epoch_now=manager_dummy_week(&md,UINT64_MAX).result_ms;assert(manager_dummy_next_week());
    }
    epoch_now=MD_RANK_EPOCH+14u*(uint64_t)MD_CALENDAR_DAY_MS;
    ranking_points(points);for(uint32_t i=0;i<7;i++)assert(!points[i]);
    page=MD_OVERALL;focus=0;MdView v=view();assert(v.rank_reset_ms==MD_RANK_EPOCH+28u*(uint64_t)MD_CALENDAR_DAY_MS && strstr(v.caption,"TWO REAL WEEKS"));
    page=MD_CHAMPIONS;v=view();assert(v.total==4 && v.count==4 && v.rows[0].badge);
    manager_dummy_pad(A);assert(page==MD_CHAMPION && champion_choice==4);v=view();assert(v.count==4 && v.badge);
  } else if(!strcmp(argv[1],"schedule")) {
    epoch_now=md.fixtures[0].kickoff_ms+1000;page=MD_SCHEDULE;schedule_group_auto=1;focus=0;
    MdView v=view();assert(v.match_group==0 && v.count==3 && v.match_groups[0]==3 && v.match_groups[1]==18);
    manager_dummy_pad(R);v=view();assert(v.match_group==1 && v.total==18);
    manager_dummy_pad(R);v=view();assert(v.match_group==2 && !v.total);
    epoch_now=manager_dummy_week(&md,UINT64_MAX).result_ms;schedule_group_auto=1;v=view();assert(v.match_group==2 && v.total==21);
    uint32_t idx[21];schedule_indices(idx);for(uint32_t i=1;i<21;i++)assert(md.fixtures[idx[i-1]].kickoff_ms>=md.fixtures[idx[i]].kickoff_ms);
  } else if(!strcmp(argv[1],"touchline")) {
    uint32_t fixture=0,event=0;
    for(uint32_t f=0;f<21 && !event;f++)for(uint32_t e=0;e<99;e++)if(md.fixtures[f].events[e].kind==MD_GOAL){fixture=f;event=e+1;break;}
    assert(event);fixture_choice=fixture;page=MD_WATCH;epoch_now=md.fixtures[fixture].kickoff_ms+md.fixtures[fixture].events[event-1].at_ms;
    manager_dummy_pad(Y);MdView v=view();assert(v.touchline_open && v.touchline_total==event && v.touchline[0].phase==MD_GOAL);
    assert(v.touchline[0].detail[0] && v.touchline[0].value[0]);
    ManagerLeagueAudioFrame audio;manager_dummy_audio_frame(&audio,1234);assert(audio.visible_watch && !audio.paused);
    manager_dummy_pad(B);assert(!touchline_open && page==MD_WATCH);
  } else if(!strcmp(argv[1],"passes")) {
    uint32_t chains=0,passes=0;
    assert(manager_dummy_valid(&md));
    for(uint32_t f=0;f<21;f++)for(uint32_t e=0;e<99;e++) {
      MdEvent *p=&md.fixtures[f].events[e];if(p->kind!=MD_PASS)continue;
      assert(p->other && p->other!=p->player);passes++;
      if(e && md.fixtures[f].events[e-1].kind==MD_PASS && md.fixtures[f].events[e-1].side==p->side) {
        assert(md.fixtures[f].events[e-1].other==p->player);chains++;
      }
    }
    assert(passes>1000 && chains>500);
  } else assert(0);
  return 0;
}

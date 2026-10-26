#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <math.h>
#include "manager_league_catalog_fixture.inc"
#include "../source/manager_league_dummy.c"
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#c);exit(97);}}while(0)
static void new_club(void) {
  authenticated=1;
  epoch_now=1793015700000ULL;memset(&md,0,sizeof(md));md.balance=5000;
  md.seed=1729;md.club=100;md.week_id=1;md.day_ms=MD_DEMO_DAY_MS;
  strcpy(md.name,"Timing United");assert(profile_create());strcpy(profile.user_id,"timing_manager");
  assert(profile_save());md.created=md.joined=1;make_fixtures();assert(persist());
  packs_build();pack_choice=0;pack_selected=3;pack_confirm();
  assert(profile.receipts==1 && profile.balance==4000 && profile.collection_count==20);
}
static void assert_timing(void) {
  assert(manager_dummy_valid(&md));
  uint32_t outcomes[6][6]={{0}},different=0;
  for(uint32_t n=0;n<MD_FIXTURES;n++) {
    const MdFixture *f=&md.fixtures[n];assert(f->event_count==99 && f->duration_ms==600000);
    assert(manager_dummy_phase(f,f->kickoff_ms-1)==0);
    assert(manager_dummy_phase(f,f->kickoff_ms)==1);
    assert(manager_dummy_phase(f,f->kickoff_ms+599999)==1);
    assert(manager_dummy_phase(f,f->kickoff_ms+600000)==2);
    assert(manager_dummy_elapsed(f,f->kickoff_ms+60001)==60001);
    assert(manager_dummy_elapsed(f,UINT64_MAX)==600000);
    assert(manager_dummy_game_seconds(f,300000)==2700);
    assert(manager_dummy_game_seconds(f,600000)==5400);
    assert(f->events[49].kind==MD_HALF && f->events[49].at_ms==300000);
    uint32_t goals[2],shots=0,substitutions=0,passes=0;
    manager_dummy_score(f,0,goals);assert(!goals[0] && !goals[1]);
    for(uint32_t i=0;i<f->event_count;i++) {
      const MdEvent *e=&f->events[i];passes+=e->kind==MD_PASS;substitutions+=e->kind==MD_SUB;
      shots+=e->kind==MD_SHOT || e->kind==MD_SAVE || e->kind==MD_GOAL;
      assert(e->at_ms==(i+1)*6000);
    }
    assert(passes>=50 && shots>=12 && substitutions==4);
    manager_dummy_score(f,600000,goals);assert(goals[0]+goals[1]<=5);
    if(!outcomes[goals[0]][goals[1]]++)different++;
    for(uint32_t i=0;i<f->event_count;i++)if(f->events[i].kind==MD_GOAL) {
      uint32_t before[2],after[2];const MdEvent *e=&f->events[i];
      manager_dummy_score(f,e->at_ms-1,before);manager_dummy_score(f,e->at_ms,after);
      assert(after[e->side]==before[e->side]+1 && after[1-e->side]==before[1-e->side]);
    }
    if(n<3) {
      static const uint32_t boundaries[]={0,350,700,900,1000,1500,3000,3150,3300,3650,3900,4200,4550,4950};
      for(uint32_t i=0;i<f->event_count;i++)for(uint32_t o=0;o<sizeof(boundaries)/sizeof(*boundaries);o++) {
        uint32_t t=f->events[i].at_ms+boundaries[o];MdDot before[23],after[23];
        manager_dummy_sample(f,t-1,before);manager_dummy_sample(f,t,after);
        for(uint32_t p=0;p<23;p++)assert(isfinite(after[p].x) && isfinite(after[p].y) &&
          fabsf(after[p].x-before[p].x)<.002f && fabsf(after[p].y-before[p].y)<.002f);
      }
    }
  }
  assert((md.week_id!=1 || outcomes[0][0]) && different>=5);
  for(uint32_t a=0;a<MD_FIXTURES;a++)for(uint32_t b=a+1;b<MD_FIXTURES;b++) {
    const MdFixture *f=&md.fixtures[a],*g=&md.fixtures[b];
    if(f->home==g->home || f->home==g->away || f->away==g->home || f->away==g->away)
      assert(f->kickoff_ms+f->duration_ms<=g->kickoff_ms || g->kickoff_ms+g->duration_ms<=f->kickoff_ms);
  }
  for(uint32_t day=1;day<=7;day++) {
    uint64_t t=day<=3 ? md.fixtures[0].kickoff_ms-(4u-day)*(uint64_t)MD_PREPARATION_DAY_MS
                     : md.fixtures[0].kickoff_ms+(day-4u)*(uint64_t)md.day_ms;
    MdWeek week=manager_dummy_week(&md,t);assert(week.day==day);
    assert(week.state==(day<=3 ? MD_PRE_LEAGUE : day<=6 ? MD_MATCH_DAY : MD_RESULT));
  }
  page=MD_WATCH;fixture_choice=0;epoch_now=md.fixtures[0].kickoff_ms+300000;
  MdView v;manager_dummy_view(&v);assert(v.elapsed_ms==300000 && v.duration_ms==600000 && !strcmp(v.clock,"45:00"));
  ManagerLeagueAudioFrame audio;manager_dummy_audio_frame(&audio,1234);
  assert(audio.position_ms==300000 && audio.event_kind==MD_HALF && audio.event_serial==50);
  epoch_now=md.fixtures[0].kickoff_ms+600000;manager_dummy_audio_frame(&audio,1235);
  assert(audio.event_kind==MLA_FULL_TIME && audio.event_serial==100 && audio.event_at_ms==600000);
}
static void write_legacy(void) {
  new_club();MdSaveV1 old={0};
  memcpy(&old,&md,offsetof(MdSaveV1,fixtures));old.version=1;old.bytes=sizeof(old);
  uint64_t first=md.fixtures[0].kickoff_ms;
  static const uint32_t kinds[MD_LEGACY_EVENTS]={
    MD_PASS,MD_SHOT,MD_SAVE,MD_FOUL,MD_PASS,MD_GOAL,MD_CORNER,MD_YELLOW,
    MD_SHOT,MD_PASS,MD_OFFSIDE,MD_SAVE,MD_FOUL,MD_PASS,MD_HALF,MD_PASS,
    MD_SHOT,MD_CORNER,MD_GOAL,MD_SUB,MD_FOUL,MD_SAVE,MD_SHOT,MD_PASS,
    MD_SUB,MD_OFFSIDE,MD_CORNER,MD_SAVE,MD_SHOT};
  for(uint32_t i=0;i<MD_FIXTURES;i++) {
    const MdFixture *f=&md.fixtures[i];MdFixtureV1 *to=&old.fixtures[i];
    to->home=f->home;to->away=f->away;to->round=f->round;to->seed=f->seed;
    uint32_t round=f->round;
    to->kickoff_ms=first+(round<3 ? round*180000u : round<5 ? MD_LEGACY_DAY_MS+(round-3)*240000u : 2u*MD_LEGACY_DAY_MS+(round-5)*240000u);
    uint32_t active[2][11];for(uint32_t s=0;s<2;s++)for(uint32_t p=0;p<11;p++)active[s][p]=p+1;
    for(uint32_t j=0;j<MD_LEGACY_EVENTS;j++) {
      MdEvent *e=&to->events[j];e->at_ms=(j+1)*6000;e->kind=kinds[j];e->goal=e->kind==MD_GOAL;
      e->side=(j+i)%2;e->player=active[e->side][1+(j%10)];
      if(e->kind==MD_SUB){e->other=j==19 ? 12 : 13;active[e->side][1+(j%10)]=e->other;}
    }
  }
  old.checksum=record_hash(&old,sizeof(old),offsetof(MdSaveV1,checksum));
  FILE *f=fopen(MD_LEGACY_FILE,"wb");assert(f && fwrite(&old,1,sizeof(old),f)==sizeof(old) && !fclose(f));
  assert(!remove(MD_FILE));remove(MD_FILE ".bak");
}
static void assert_import(void) {
  epoch_now=1793015700000ULL;load_once();assert(!blocked && profile_ready && manager_dummy_valid(&md));
  authenticated=1;
  assert(md.week_id==1 && md.day_ms==MD_LEGACY_DAY_MS && !strcmp(md.name,"Timing United"));
  MdSaveV1 old;FILE *file=fopen(MD_LEGACY_FILE,"rb");assert(file && fread(&old,1,sizeof(old),file)==sizeof(old));fclose(file);
  assert(!memcmp(md.name,old.name,sizeof(old.name)) && md.seed==old.seed && md.clock_offset_ms==old.clock_offset_ms);
  for(uint32_t i=0;i<MD_FIXTURES;i++) {
    const MdFixture *f=&md.fixtures[i];assert(f->duration_ms==180000 && f->event_count==29);
    assert(!memcmp(f->events,old.fixtures[i].events,sizeof(old.fixtures[i].events)));
    assert(f->kickoff_ms==old.fixtures[i].kickoff_ms && f->seed==old.fixtures[i].seed && f->home==old.fixtures[i].home && f->away==old.fixtures[i].away);
    assert(manager_dummy_game_seconds(f,90000)==2700 && manager_dummy_game_seconds(f,180000)==5400);
  }
  page=MD_WATCH;fixture_choice=0;epoch_now=md.fixtures[0].kickoff_ms+90000;
  MdView v;manager_dummy_view(&v);assert(!strcmp(v.clock,"45:00") && v.duration_ms==180000);
}
static void result_time(void) {epoch_now=manager_dummy_week(&md,UINT64_MAX).result_ms;}
static void assert_history(void) {
  assert(md.week_id==2 && profile_ready && !blocked);assert_timing();
  assert(profile.receipts==1 && profile.balance==4000 && profile.collection_count==20 && profile.counts[0]==20);
  strcpy(md.name,"Renamed United");assert(persist());
  uint32_t p=profile.match_roster[0][1];profile.match_roster[0][1]=profile.match_roster[0][2];profile.match_roster[0][2]=p;
  assert(profile_save());
  page=MD_SCHEDULE;assert(manager_dummy_history_select(1));
  assert(history.save.fixtures[0].seed!=md.fixtures[0].seed);
  uint32_t old_score[2],new_score[2];
  manager_dummy_score(&history.save.fixtures[0],manager_dummy_duration(&history.save.fixtures[0]),old_score);
  manager_dummy_score(&md.fixtures[0],manager_dummy_duration(&md.fixtures[0]),new_score);
  assert(old_score[0]!=new_score[0] || old_score[1]!=new_score[1]);
  MdArchive on_disk;char historical_path[96];archive_path(historical_path,1);
  assert(archive_read(historical_path,&on_disk));
  assert(on_disk.save.fixtures[0].seed==history.save.fixtures[0].seed &&
         !memcmp(on_disk.save.fixtures,history.save.fixtures,sizeof(history.save.fixtures)));
  assert(!strcmp(broadcast_team_name(0),"Timing United"));
  assert(history.players.match_roster[0][1]!=profile.match_roster[0][1]);
  MdView v;manager_dummy_view(&v);assert(v.history_week==1 && v.archive_count==1);
  for(uint32_t i=0;i<v.count;i++)assert(v.rows[i].phase==2);
  manager_dummy_pad(A);assert(page==MD_WATCH && replay);manager_dummy_view(&v);
  assert(v.elapsed_ms==0 && v.watching_replay && v.duration_ms==manager_dummy_duration(&history.save.fixtures[0]));
  manager_dummy_pad(RIGHT);manager_dummy_view(&v);assert(v.elapsed_ms==15000);
  manager_dummy_pad(B);assert(page==MD_SCHEDULE && history_week==1);
  manager_dummy_pad(R);assert(!history_week);manager_dummy_pad(L);assert(history_week==1);
  manager_dummy_pad(B);assert(page==MD_DASHBOARD && !history_week);
}
int main(int argc,char **argv) {
  assert(argc==2);
  if(!strcmp(argv[1],"legacy")){write_legacy();return 0;}
  if(!strcmp(argv[1],"import")){assert_import();return 0;}
  if(!strcmp(argv[1],"rollover-legacy")){assert_import();result_time();assert(manager_dummy_next_week());assert_history();return 0;}
  if(!strcmp(argv[1],"recover")) {
    MdArchive prepared;assert(archive_read(MD_PENDING_FILE,&prepared));
    epoch_now=1793015700000ULL;load_once();assert(!blocked && md.week_id==2 && profile_ready);
    authenticated=1;
    assert(!memcmp(&prepared.save,&md,sizeof(md)));
    assert(!file_exists(MD_PENDING_FILE));assert_history();return 0;
  }
  new_club();assert_timing();
  if(!strcmp(argv[1],"new")) {
    assert(!manager_dummy_next_week());
    MdSave bad=md;bad.fixtures[0].events[49].at_ms+=1;bad.checksum=checksum(&bad);assert(!manager_dummy_valid(&bad));
    bad=md;bad.fixtures[0].event_count=100;bad.checksum=checksum(&bad);assert(!manager_dummy_valid(&bad));
    bad=md;bad.fixtures[0].events[49].kind=MD_PASS;bad.checksum=checksum(&bad);assert(!manager_dummy_valid(&bad));
    bad=md;
    for(uint32_t i=1;i<MD_FIXTURES;i++)if(bad.fixtures[i].round!=bad.fixtures[0].round &&
        (bad.fixtures[i].home==bad.fixtures[0].home || bad.fixtures[i].away==bad.fixtures[0].home)) {
      bad.fixtures[i].kickoff_ms=bad.fixtures[0].kickoff_ms+599999;break;
    }
    bad.checksum=checksum(&bad);assert(!manager_dummy_valid(&bad));
    return 0;
  }
  result_time();
  if(!strcmp(argv[1],"interrupt")) {
    assert(!mkdir(MD_FILE ".tmp",0700));assert(!manager_dummy_next_week());
    assert(blocked && file_exists(MD_PENDING_FILE));return 0;
  }
  if(!strcmp(argv[1],"interrupt-profile")) {
    assert(!mkdir(MD_PROFILE_FILE ".tmp",0700));assert(!manager_dummy_next_week());
    assert(blocked && file_exists(MD_PENDING_FILE));return 0;
  }
  assert(manager_dummy_next_week());assert_history();return 0;
}

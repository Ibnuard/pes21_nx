#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "manager_league_catalog_fixture.inc"
#include "../source/manager_league_dummy.c"
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#c);exit(97);}}while(0)

/* Fixed UTC instants, independently checked against the agreed WIB calendar. */
#define MONDAY UINT64_C(1792947600000)
#define TUESDAY UINT64_C(1793034000000)
#define THURSDAY UINT64_C(1793206800000)
static MdView view(void){MdView v;manager_dummy_view(&v);return v;}
static void setup_unjoined(void) {
  epoch_now=MONDAY+9*UINT64_C(3600000);loaded=authenticated=1;
  memset(&md,0,sizeof(md));md.balance=5000;md.seed=1729;md.club=100;md.week_id=1;
  strcpy(md.name,"Calendar United");assert(profile_create());strcpy(profile.user_id,"calendar_manager");
  profile.tutorials=7;assert(profile_save());assert(persist());
}
static void setup(void) {
  setup_unjoined();md.created=md.joined=1;make_fixtures();assert(persist());
  assert(grant_entry_locked(NULL));assert(profile.balance==6500);
  page=MD_DASHBOARD;focus=0;notice[0]=0;
}
static void calendar_checks(void) {
  assert(md.fixtures[0].kickoff_ms==TUESDAY+12*UINT64_C(3600000));
  assert(md.day_ms==MD_CALENDAR_DAY_MS && manager_dummy_valid(&md));
  uint32_t days[8]={0};
  for(uint32_t n=0;n<MD_FIXTURES;n++) {
    const MdFixture *f=&md.fixtures[n];days[calendar_weekday(f->kickoff_ms)]++;
    assert(f->duration_ms==600000 && f->event_count==99);
    for(uint32_t j=0;j<n;j++) {
      const MdFixture *g=&md.fixtures[j];
      if(f->home==g->home || f->home==g->away || f->away==g->home || f->away==g->away)
        assert(f->kickoff_ms>=g->kickoff_ms+g->duration_ms || g->kickoff_ms>=f->kickoff_ms+f->duration_ms);
    }
  }
  assert(days[2]==12 && days[3]==9 && !days[1] && !days[4] && !days[5] && !days[6] && !days[7]);
  assert(manager_dummy_week(&md,TUESDAY-1).state==MD_PRE_LEAGUE);
  assert(manager_dummy_week(&md,TUESDAY).state==MD_MATCH_DAY);
  assert(manager_dummy_week(&md,TUESDAY+UINT64_C(86400000)+18*UINT64_C(3600000)+599999).state==MD_MATCH_DAY);
  epoch_now=TUESDAY+UINT64_C(86400000)+18*UINT64_C(3600000)+600000;
  assert(manager_dummy_week(&md,epoch_now).state==MD_RESULT);
  uint32_t prize=league_prize(&md,0,NULL);
  assert(manager_dummy_next_week());assert(md.week_id==2 && md.balance==8000+prize && profile.balance==8000+prize);
  assert(md.fixtures[0].kickoff_ms==THURSDAY+MD_CALENDAR_DAY_MS+12*UINT64_C(3600000));
  assert(!manager_dummy_next_week() && profile.balance==8000+prize);
  for(uint32_t n=0;n<MD_FIXTURES;n++)assert(calendar_weekday(md.fixtures[n].kickoff_ms)==(md.fixtures[n].round<4 ? 5u : 6u));
  epoch_now=manager_dummy_week(&md,UINT64_MAX).result_ms;prize+=league_prize(&md,0,NULL);assert(manager_dummy_next_week());
  assert(md.fixtures[0].kickoff_ms==TUESDAY+7*UINT64_C(86400000)+12*UINT64_C(3600000));
  assert(profile.balance==9500+prize);
}
static void club_checks(void) {
  page=MD_CLUB_PROFILE;team_choice=1;team_return=MD_TEAMS_PAGE;team_return_focus=1;focus=0;
  MdView v=view();assert(v.total==6 && v.count==5 && v.badge && v.club_power && v.club_rank);
  MdProfile before=profile;
  for(uint32_t i=0;i<4;i++)manager_dummy_pad(DOWN);manager_dummy_pad(A);
  assert(page==MD_CLUB_PLAN && !editor && !action);v=view();assert(v.plan_players[0].identity);
  manager_dummy_pad(A|X|Y|LEFT|RIGHT|DOWN);assert(!memcmp(&profile,&before,sizeof(profile)));
  manager_dummy_pad(B);assert(page==MD_CLUB_PROFILE && focus==4);
  manager_dummy_pad(UP);manager_dummy_pad(UP);manager_dummy_pad(A);assert(page==MD_TEAM_HISTORY);
  v=view();assert(v.total==6 && v.count==6);
  for(uint32_t i=0;i<v.count;i++)assert(strstr(v.rows[i].label,team_name(1)));
  manager_dummy_pad(B);assert(page==MD_CLUB_PROFILE && focus==2);
  manager_dummy_pad(B);assert(page==MD_TEAMS_PAGE && focus==1);
  page=MD_DASHBOARD;focus=0;strcpy(notice,"This player is already registered.");
  v=view();assert(v.modal.open && v.modal.information && strstr(v.modal.body,"already registered"));
  manager_dummy_pad(RIGHT);assert(!focus && notice[0]);manager_dummy_pad(A);assert(!notice[0] && page==MD_DASHBOARD);
  manager_dummy_pad(RIGHT);assert(focus==1);
  epoch_now=manager_dummy_week(&md,UINT64_MAX).result_ms;v=view();
  MdRow table[7];table_rows(table);for(uint32_t i=0;i<7;i++)if(!table[i].team_id)assert(v.league_points==table[i].stats.points);
  assert(v.balance==6500 && v.league_points<=18);
}
static void dev_checks(void) {
  const MdSave before=md;
  manager_dummy_pad(Y);
#if MANAGER_LEAGUE_DEV_CLOCK
  assert(now()==md.fixtures[0].kickoff_ms && md.clock_offset_ms>0);
  manager_dummy_pad(Y);assert(now()==md.fixtures[0].kickoff_ms+600000);
  epoch_now=manager_dummy_week(&md,UINT64_MAX).result_ms-md.clock_offset_ms;
  assert(manager_dummy_next_week());page=MD_DASHBOARD;focus=0;manager_dummy_pad(Y);
  assert(now()==md.fixtures[0].kickoff_ms && md.week_id==2);
#else
  assert(!memcmp(&before,&md,sizeof(md)));
  MdView v=view();for(uint32_t i=0;i<v.helper_count;i++)assert(strcmp(v.helper_label[i],"DEMO TIME"));
#endif
  (void)before;
}
static void controlled_result(uint32_t position) {
  uint32_t strength[7],at=0;
  for(uint32_t t=1;t<7;t++)strength[t]=at++;
  strength[0]=position-1;
  for(uint32_t t=1;t<7;t++)if(strength[t]>=strength[0])strength[t]++;
  for(uint32_t f=0;f<MD_FIXTURES;f++) {
    MdFixture *match=&md.fixtures[f];
    for(uint32_t i=0;i<MD_EVENTS;i++)if(match->events[i].kind==MD_GOAL){match->events[i].kind=MD_PASS;match->events[i].goal=0;}
    MdEvent *e=&match->events[11];e->kind=MD_GOAL;e->goal=1;e->other=0;e->player=7;
    e->side=strength[match->home]<strength[match->away] ? 0u : 1u;
  }
  assert(persist());epoch_now=manager_dummy_week(&md,UINT64_MAX).result_ms;
  MdRow ranked[7];table_rows(ranked);assert(!ranked[position-1].team_id);
}
static void reward_checks(uint32_t position) {
  controlled_result(position);uint32_t award=position==1 ? 5000u : position==2 ? 4000u : position==3 ? 3000u : 0u;
  manager_dummy_tick_at(epoch_now);assert(!blocked && profile.balance==6500+award && (md.purchased_mask&MD_REWARD_SETTLED));
  assert(!file_exists(MD_WALLET_FILE));MdSave paid=md;MdProfile players=profile;
  manager_dummy_tick_at(epoch_now+10000u);assert(!memcmp(&paid,&md,sizeof(md)) && !memcmp(&players,&profile,sizeof(profile)));
}
int main(int argc,char **argv) {
  assert(argc==2);
  if(!strcmp(argv[1],"money-reject")) {
    MdSave saved;MdProfile players;assert(read_file(MD_FILE,&saved));
    FILE *f=fopen(MD_PROFILE_FILE,"rb");assert(f && fread(&players,1,sizeof(players),f)==sizeof(players));fclose(f);
    epoch_now=MONDAY;load_once();assert(blocked && file_exists(MD_WALLET_FILE));
    MdSave checked;MdProfile checked_players;assert(read_file(MD_FILE,&checked));
    f=fopen(MD_PROFILE_FILE,"rb");assert(f && fread(&checked_players,1,sizeof(checked_players),f)==sizeof(checked_players));fclose(f);
    assert(!memcmp(&saved,&checked,sizeof(saved)) && !memcmp(&players,&checked_players,sizeof(players)));return 0;
  }
  if(!strcmp(argv[1],"money-recover")) {
    MdCashJournal *j=calloc(1,sizeof(*j));assert(j && cash_journal_read(MD_WALLET_FILE,j));
    epoch_now=j->observed_ms;load_once();assert(!blocked && profile_ready && !file_exists(MD_WALLET_FILE));
    assert(!memcmp(&md,&j->after.save,sizeof(md)) && !memcmp(&profile,&j->after.players,sizeof(profile)));
    authenticated=1;assert(grant_entry_locked(NULL));uint32_t cash=profile.balance;
    if(j->kind==MD_CASH_REWARD){assert(settle_rewards_locked());assert(profile.balance==cash);}
    free(j);return 0;
  }
  if(!strncmp(argv[1],"entry-",6)) {
    setup_unjoined();MdSave before=md;MdProfile players=profile;
    const int preflight=!strcmp(argv[1],"entry-preflight");
    const char *failure=preflight ? MD_WALLET_FILE ".tmp" :
        !strcmp(argv[1],"entry-save") ? MD_FILE ".tmp" : MD_PROFILE_FILE ".tmp";
    assert(!mkdir(failure,0700));md.created=md.joined=1;make_fixtures();
    assert(!grant_entry_locked(&before));
    if(preflight) {
      assert(!blocked && !memcmp(&md,&before,sizeof(md)) && !memcmp(&profile,&players,sizeof(profile)));
      assert(!file_exists(MD_WALLET_FILE));
    } else assert(blocked && file_exists(MD_WALLET_FILE));
    return 0;
  }
  setup();
  if(!strcmp(argv[1],"calendar"))calendar_checks();
  else if(!strcmp(argv[1],"clubs"))club_checks();
  else if(!strcmp(argv[1],"dev"))dev_checks();
  else if(!strncmp(argv[1],"money-",6) && argv[1][6]>='1' && argv[1][6]<='4')reward_checks((uint32_t)(argv[1][6]-'0'));
  else if(!strcmp(argv[1],"money-interrupt")) {
    controlled_result(1);assert(profile_save());assert(!mkdir(MD_PROFILE_FILE ".tmp",0700));manager_dummy_tick_at(epoch_now);
    assert(blocked && file_exists(MD_WALLET_FILE));
  }
  else if(!strcmp(argv[1],"money-stale")) {
    controlled_result(1);MdCashJournal *j=calloc(1,sizeof(*j));assert(j);
    j->before.save=md;j->before.players=profile;assert(settle_rewards_locked());
    j->after.save=md;j->after.players=profile;j->kind=MD_CASH_REWARD;j->amount=5000;j->observed_ms=now();
    /* Restoring an already-finished journal must not undo a later purchase. */
    packs_build();pack_choice=0;pack_buy();pack_selected=3;pack_confirm();
    assert(profile.receipts==1 && profile.balance==10500);
    assert(cash_journal_write(j));free(j);
  }
  else assert(0);
  return 0;
}

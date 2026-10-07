/* Fictional compact career competitions, not official real-world calendars.
 * Public category IDs/names select the already paired playable pools. */
#include "exhibition_team_catalog.h"
#include "fl26_league_catalog_generated.h"
static uint32_t ml_pick_nations(uint32_t region,uint32_t own,uint32_t *teams,uint32_t limit,uint32_t seed);

int ml_event_is_national(uint32_t kind) {return kind>=ML_EVENT_FRIENDLY && kind<=ML_EVENT_WORLD_CUP;}
int ml_event_is_match(uint32_t kind) {return kind==ML_EVENT_LEAGUE || kind==ML_EVENT_CUP ||
  kind==ML_EVENT_CONTINENTAL || ml_event_is_national(kind);}
int ml_event_is_knockout(uint32_t kind) {return kind==ML_EVENT_CUP || kind==ML_EVENT_CONTINENTAL ||
  kind==ML_EVENT_REGIONAL || kind==ML_EVENT_WORLD_CUP;}
uint32_t ml_event_manager_team(const MasterLeague *c,uint32_t kind) {
  return ml_event_is_national(kind) ? c->world.national_team : c->settings.club;
}
const CupTournament *ml_event_cup(const MasterLeague *c,uint32_t kind) {
  if(kind==ML_EVENT_CUP)return &c->cup;
  if(kind==ML_EVENT_CONTINENTAL)return &c->world.continental;
  if(kind==ML_EVENT_REGIONAL)return &c->world.regional;
  if(kind==ML_EVENT_WORLD_CUP)return &c->world.world_cup;
  return NULL;
}
static uint32_t ml_national_region(uint32_t team) {
  for(uint32_t i=0;i<EXHIBITION_TEAM_CATEGORY_COUNT;i++) {
    const ExhibitionTeamCategory *cat=&exhibition_team_categories[i];
    if(!strstr(cat->label,"NATIONAL"))continue;
    for(uint32_t j=0;j<cat->team_count;j++)if(cat->teams[j]==team)return i+1u;
  }
  return 0u;
}
static uint32_t ml_club_region(uint32_t competition) {
  /* Domestic competitions currently in the curated playable catalog. */
  if(competition==21u)return 2u; /* South America */
  if(competition==41u || competition==120u)return 3u; /* Asia */
  for(uint32_t i=0;i<FL26_LEAGUE_CATALOG_COUNT;i++)
    if(fl26_league_catalog[i].competition_id==competition && competition)return 1u;
  return 0u;
}
static void ml_world_office_schedule(const MasterLeague *c,MlEvent *event) {
  if(!c->world.version)return;
  const uint32_t national_day=48u+c->seed%16u;
  if(!c->world.national_checked && national_day>=c->day && national_day<=event->day)
    *event=(MlEvent){ML_EVENT_BOARD,national_day,2u,0u,0u,0u};
  for(uint32_t i=0;i<3u;i++) {
    const uint32_t day=142u+i*42u+(c->seed+i*7u)%12u;
    if(!(c->world.job_checks&(1u<<i)) && day>=c->day && day<=event->day)
      *event=(MlEvent){ML_EVENT_BOARD,day,3u+i,0u,0u,0u};
  }
}
static void ml_world_board_check(MasterLeague *c) {
  MlWorldState *w=&c->world;MlOfficeState *o=&c->office;
  if(!w->national_checked && c->day>=48u+c->seed%16u) {
    w->national_checked=1u;
    if(!w->national_team && c->day<=76u) {
      uint32_t roll=c->seed^c->season*173u;
      const uint32_t target=2u+ml_random(&roll)%(ML_MAX_NATIONAL_OFFERS-1u);
      uint32_t pool[128];const uint32_t n=ml_pick_nations(0u,0u,pool,128u,roll);
      /* Federation interest is independent of manager nationality. Each
       * country gets its own persistent reply and read receipt. */
      for(uint32_t i=0;i<n && w->national_count<target;i++) {
        const uint32_t team=pool[i];
        const uint32_t region=ml_national_region(team);
        if(region && exhibition_team_categories[region-1u].team_count>=4u) {
          w->national_offers[w->national_count++]=(MlNationalOffer){team,76u,ML_OFFER_WAITING,0u};
        }
      }
      if(w->national_count)ml_notice(c,ML_NOTICE_JOB,"National federations offered parallel manager roles. Review each offer in Manager / National Team.");
    }
  }
  for(uint32_t check=0;check<3u;check++) {
    const uint32_t day=142u+check*42u+(c->seed+check*7u)%12u;
    if((w->job_checks&(1u<<check)) || c->day<day)continue;
    w->job_checks|=1u<<check;
    uint32_t roll=c->seed^c->season*919u^check*137u;
    if(ml_random(&roll)%100u>=75u || ml_rank(c)>c->target_rank+3u)continue;
    const uint32_t start=ml_random(&roll)%c->league.team_count;
    for(uint32_t i=0;i<c->league.team_count;i++) {
      const uint32_t team=c->league.standings[(start+i)%c->league.team_count].team;
      if(team==c->settings.club || ml_find_club(c,team)->cash<0)continue;
      int eligible=!c->cup_enabled;
      for(uint32_t j=0;c->cup_enabled && j<cup_tournament_fixture_count(&c->cup,0u);j++)
        eligible|=c->cup.fixtures[0][j].home==team || c->cup.fixtures[0][j].away==team;
      if(!eligible)continue;
      o->job_team=team;o->job_expiry=c->day+14u;
      ml_notice(c,ML_NOTICE_JOB,"A club has offered you a fresh start with its current squad and budget. Reply within 14 days.");break;
    }
  }
}
const char *ml_world_name(const MasterLeague *c,uint32_t kind) {
  if(kind==ML_EVENT_CONTINENTAL)return c->world.continental_id==1u ? "UEFA CHAMPIONS LEAGUE" :
    c->world.continental_id==2u ? "SOUTH AMERICAN CHAMPIONS CUP" : "ASIAN CHAMPIONS CUP";
  if(kind==ML_EVENT_FRIENDLY)return "INTERNATIONAL FRIENDLY";
  if(kind==ML_EVENT_QUALIFIER)return "WORLD CUP QUALIFIERS";
  if(kind==ML_EVENT_WORLD_CUP)return "WORLD CUP";
  if(kind==ML_EVENT_REGIONAL && c->world.national_region) {
    const char *label=exhibition_team_categories[c->world.national_region-1u].label;
    if(strstr(label,"EUROPE"))return "EUROPEAN NATIONS CUP";
    if(strstr(label,"ASIA"))return "ASIAN NATIONS CUP";
    if(strstr(label,"AFRICA"))return "AFRICAN NATIONS CUP";
    if(strstr(label,"S AMERICA"))return "SOUTH AMERICAN NATIONS CUP";
    if(strstr(label,"N AMERICA"))return "NORTH AMERICAN NATIONS CUP";
  }
  return "REGIONAL NATIONS CUP";
}
uint32_t ml_world_day(const MasterLeague *c,uint32_t kind,uint32_t index) {
  static const uint32_t continental[]={78u,117u,156u,222u,306u};
  static const uint32_t qualifiers[]={96u,125u,154u,183u,242u,270u};
  uint32_t day=kind==ML_EVENT_CONTINENTAL ? continental[index<5u ? index : 4u] :
    kind==ML_EVENT_FRIENDLY ? (index ? 213u : 84u) :
    kind==ML_EVENT_QUALIFIER ? qualifiers[index<6u ? index : 5u] :
    kind==ML_EVENT_REGIONAL ? 285u+index*6u : 334u+index*6u;
  int busy;
  do {
    busy=0;
    for(uint32_t i=0;i<c->league.matchday_count;i++)busy|=ml_league_day(c,i)==day;
    for(uint32_t i=0;c->cup_enabled && i<c->cup.round_count;i++)busy|=ml_cup_day(c,i)==day;
    if(kind!=ML_EVENT_CONTINENTAL)for(uint32_t i=0;i<c->world.continental.round_count;i++)
      busy|=ml_world_day(c,ML_EVENT_CONTINENTAL,i)==day;
    if(busy)day++;
  }while(busy);
  return day;
}
static uint32_t ml_pick_nations(uint32_t region,uint32_t own,uint32_t *teams,uint32_t limit,uint32_t seed) {
  uint32_t pool[128],n=0u,count=0u;
  if(own)teams[count++]=own;
  for(uint32_t i=0;i<EXHIBITION_TEAM_CATEGORY_COUNT;i++) {
    const ExhibitionTeamCategory *cat=&exhibition_team_categories[i];
    if((region && i+1u!=region) || !strstr(cat->label,"NATIONAL"))continue;
    for(uint32_t j=0;j<cat->team_count && n<128u;j++)if(cat->teams[j]!=own)pool[n++]=cat->teams[j];
  }
  for(uint32_t i=n;i>1u;i--) {const uint32_t j=ml_random(&seed)%i,tmp=pool[i-1u];pool[i-1u]=pool[j];pool[j]=tmp;}
  for(uint32_t i=0;i<n && count<limit;i++)teams[count++]=pool[i];
  return count;
}
static void ml_national_start(MasterLeague *c) {
  MlWorldState *w=&c->world;const uint32_t own=w->national_team;
  memset(w->friendlies,0,sizeof(w->friendlies));w->friendly_mask=w->finals_started=0u;
  memset(&w->qualifiers,0,sizeof(w->qualifiers));memset(&w->regional,0,sizeof(w->regional));memset(&w->world_cup,0,sizeof(w->world_cup));
  if(!own)return;
  uint32_t teams[8];w->national_region=ml_national_region(own);
  uint32_t count=ml_pick_nations(w->national_region,own,teams,8u,c->seed^c->season);
  if(count<4u)return;
  league_tournament_init(&w->qualifiers,teams,4u,&own,1u,1,c->seed^c->season*31u);
  league_tournament_set_system(&w->qualifiers,LEAGUE_SYSTEM_STANDINGS);
  cup_tournament_init(&w->regional,teams,count,&own,1u,c->seed^c->season*51u);
  ml_pick_nations(0u,own,teams,4u,c->seed^c->season*71u);
  w->friendlies[0]=(LeagueFixture){own,teams[1],0,0,0,0};
  w->friendlies[1]=(LeagueFixture){teams[2],own,0,0,0,0};
}
static void ml_world_start(MasterLeague *c) {
  MlWorldState *w=&c->world;w->version=1u;w->job_checks=0u;
  w->national_count=w->national_checked=0u;
  memset(w->national_offers,0,sizeof(w->national_offers));
  w->continental_id=ml_club_region(c->settings.competition_id);
  memset(&w->continental,0,sizeof(w->continental));
  uint32_t teams[32],count=0u;
  /* Up to four qualifiers per supported league. Current league uses last
   * season's ranking for the managed club, seeded strength in season one. */
  for(uint32_t l=0;l<FL26_LEAGUE_CATALOG_COUNT && count<32u;l++) {
    const Fl26LeagueCatalogEntry *entry=&fl26_league_catalog[l];
    if(!entry->competition_id || ml_club_region(entry->competition_id)!=w->continental_id ||
       entry->competition_id==66u || entry->competition_id==67u || entry->competition_id==68u)continue;
    uint32_t best[4]={0};
    for(uint32_t j=0;j<entry->pool_count;j++) {
      const uint32_t team=entry->team_ids[j];if(!ml_find_club(c,team))continue;
      if(team==c->settings.club && c->season>1u && c->last_rank>4u)continue;
      uint32_t at=0u;
      const uint32_t strength=team==c->settings.club && c->season>1u ? 100u : ml_strength(c,team);
      while(at<4u && best[at] && ml_strength(c,best[at])>=strength)at++;
      if(at==4u)continue;
      for(uint32_t k=3u;k>at;k--)best[k]=best[k-1u];
      best[at]=team;
    }
    if(c->season>1u && c->last_rank<=4u) {
      int belongs=0,present=0;
      for(uint32_t j=0;j<entry->pool_count;j++)belongs|=entry->team_ids[j]==c->settings.club;
      for(uint32_t j=0;j<4u;j++)present|=best[j]==c->settings.club;
      if(belongs && !present)best[3]=c->settings.club;
    }
    for(uint32_t j=0;j<4u && count<32u;j++)if(best[j])teams[count++]=best[j];
  }
  if(count>=2u) {
    uint32_t human=0u;for(uint32_t i=0;i<count;i++)human|=teams[i]==c->settings.club;
    cup_tournament_init(&w->continental,teams,count,&c->settings.club,human,c->seed^c->season*101u);
  }
  ml_national_start(c);
}
void ml_world_enable(MasterLeague *c) {
  if(!c || c->world.version)return;
  ml_world_start(c);
  /* Never backfill a user's already elapsed competition with invented results. */
  if(c->day>=78u)memset(&c->world.continental,0,sizeof(c->world.continental));
  if(c->day>76u)c->world.national_checked=1u;
  for(uint32_t i=0;i<3u;i++)if(c->day>142u+i*42u+(c->seed+i*7u)%12u)c->world.job_checks|=1u<<i;
}
static void ml_world_cup_event(const MasterLeague *c,const CupTournament *cup,uint32_t kind,MlEvent *event) {
  if(!cup->team_count || cup->champion)return;
  const uint32_t day=ml_world_day(c,kind,cup->active_round);
  if(day<c->day || day>=event->day)return;
  *event=(MlEvent){kind,day,ML_INVALID_INDEX,cup->active_round,0u,0u};
  uint32_t r,i;
  if(cup_tournament_next_human(cup,&r,&i)) {
    const CupFixture *f=&cup->fixtures[r][i];event->index=i;event->home=f->home;event->away=f->away;
  }
}
static void ml_world_schedule(const MasterLeague *c,MlEvent *event) {
  const MlWorldState *w=&c->world;if(!w->version)return;
  ml_world_cup_event(c,&w->continental,ML_EVENT_CONTINENTAL,event);
  if(!w->national_team)return;
  ml_world_cup_event(c,&w->regional,ML_EVENT_REGIONAL,event);
  ml_world_cup_event(c,&w->world_cup,ML_EVENT_WORLD_CUP,event);
  for(uint32_t i=0;i<2u;i++) {
    const uint32_t day=ml_world_day(c,ML_EVENT_FRIENDLY,i);
    if(!(w->friendly_mask&(1u<<i)) && day>=c->day && day<event->day)
      *event=(MlEvent){ML_EVENT_FRIENDLY,day,i,0u,w->friendlies[i].home,w->friendlies[i].away};
  }
  const LeagueTournament *q=&w->qualifiers;
  if(q->team_count && q->active_matchday<q->matchday_count) {
    const uint32_t day=ml_world_day(c,ML_EVENT_QUALIFIER,q->active_matchday);
    if(day>=c->day && day<event->day)for(uint32_t i=0;i<q->matchday_fixture_count[q->active_matchday];i++) {
      const uint32_t at=q->matchday_first[q->active_matchday]+i;
      const LeagueFixture *f=&q->fixtures[at];
      if(f->home==w->national_team || f->away==w->national_team)
        *event=(MlEvent){ML_EVENT_QUALIFIER,day,at,q->active_matchday,f->home,f->away};
    }
  }
}
uint32_t ml_national_offer_status(const MasterLeague *c,uint32_t index) {
  if(!c || index>=c->world.national_count)return 0u;
  const MlNationalOffer *o=&c->world.national_offers[index];
  return o->status==ML_OFFER_WAITING && c->day>o->expiry ? ML_OFFER_EXPIRED : o->status;
}
int ml_national_offer_unread(const MasterLeague *c,uint32_t index) {
  return c && index<c->world.national_count &&
    c->world.national_offers[index].seen!=ml_national_offer_status(c,index);
}
void ml_national_offer_mark_read(MasterLeague *c,uint32_t index) {
  if(ml_national_offer_unread(c,index)) {
    c->world.national_offers[index].seen=ml_national_offer_status(c,index);c->transaction_sequence++;
  }
}
const char *ml_accept_national_job(MasterLeague *c,uint32_t index) {
  if(!c || c->office.dismissed || c->world.national_team || ml_national_offer_status(c,index)!=ML_OFFER_WAITING ||
      c->day>76u || !ml_national_region(c->world.national_offers[index].team))return "NATIONAL OFFER UNAVAILABLE";
  c->world.national_team=c->world.national_offers[index].team;
  for(uint32_t i=0;i<c->world.national_count;i++) {
    MlNationalOffer *o=&c->world.national_offers[i];
    if(o->status==ML_OFFER_WAITING)o->status=i==index ? ML_OFFER_ACCEPTED : ML_OFFER_CANCELLED;
    o->seen=ml_national_offer_status(c,i);
  }
  ml_national_start(c);c->transaction_sequence++;
  ml_notice(c,ML_NOTICE_JOB,"National appointment accepted. Your club career continues; no national transfers or wages.");
  return "";
}
const char *ml_reject_national_job(MasterLeague *c,uint32_t index) {
  if(!c || c->office.dismissed || ml_national_offer_status(c,index)!=ML_OFFER_WAITING)return "NATIONAL OFFER UNAVAILABLE";
  MlNationalOffer *o=&c->world.national_offers[index];o->status=o->seen=ML_OFFER_REJECTED;
  c->transaction_sequence++;return "";
}
static int ml_world_record(MasterLeague *c,const MlEvent *e,uint32_t hg,uint32_t ag,int simulated,uint32_t winner) {
  if(!ml_event_matches(c,e) || !ml_event_is_match(e->kind) || hg>99u || ag>99u ||
      (!simulated && ml_event_is_knockout(e->kind) && e->home && e->away && hg==ag && winner!=e->home && winner!=e->away))return 0;
  if(!ml_advance_date(c,e))return 0;
  MlWorldState *w=&c->world;
  if(e->kind==ML_EVENT_FRIENDLY) {
    LeagueFixture *f=&w->friendlies[e->index];
    if(simulated)ml_simulate_score(c,f->home,f->away,e->day,&hg,&ag);
    f->home_goals=hg;f->away_goals=ag;f->complete=1u;f->simulated=simulated!=0;
    w->friendly_mask|=1u<<e->index;
  }else if(e->kind==ML_EVENT_QUALIFIER) {
    LeagueTournament *q=&w->qualifiers;
    for(uint32_t i=0;i<q->matchday_fixture_count[q->active_matchday];i++) {
      const uint32_t at=q->matchday_first[q->active_matchday]+i;const LeagueFixture *f=&q->fixtures[at];
      uint32_t h=hg,a=ag;const int ai=simulated || at!=e->index;
      if(ai)ml_simulate_score(c,f->home,f->away,e->day+i,&h,&a);
      league_tournament_record_table_fixture(q,at,h,a,ai);
    }
    league_tournament_commit_matchday(q);
    if(q->phase==LEAGUE_PHASE_COMPLETE && !w->finals_started) {
      w->finals_started=1u;uint8_t ranked[LEAGUE_MAX_TEAMS];league_tournament_ranked_slots(q,ranked);
      if(q->standings[ranked[0]].team==w->national_team || q->standings[ranked[1]].team==w->national_team) {
        uint32_t teams[8];ml_pick_nations(0u,w->national_team,teams,8u,c->seed^c->season*131u);
        cup_tournament_init(&w->world_cup,teams,8u,&w->national_team,1u,c->seed^c->season*151u);
        ml_notice(c,ML_NOTICE_JOB,"Your national team qualified for the World Cup finals.");
      }else ml_notice(c,ML_NOTICE_JOB,"World Cup qualification ended. Your national appointment continues next season.");
    }
  }else {
    CupTournament *cup=(CupTournament *)ml_event_cup(c,e->kind);
    if(!cup)return 0;
    for(uint32_t i=0;i<cup_tournament_fixture_count(cup,e->round);i++) {
      CupFixture *f=&cup->fixtures[e->round][i];if(f->complete)continue;
      uint32_t h=hg,a=ag;const int ai=simulated || i!=e->index;
      if(ai)ml_simulate_score(c,f->home,f->away,e->day+i,&h,&a);
      cup_tournament_record_deferred(cup,e->round,i,h,a);f->simulated=ai;
      if(!ai && h==a)f->winner=winner;
      if(e->kind==ML_EVENT_CONTINENTAL) {
        MlClub *club=ml_club(c,f->home);if(club)club->cash+=800000;
        club=ml_club(c,f->away);if(club)club->cash+=400000;
        if(f->home==c->settings.club)c->match_income+=800000;
        if(f->away==c->settings.club)c->match_income+=400000;
        ml_board_result(c,f->home,f->away,h,a);
      }
    }
    cup_tournament_commit_round(cup);
  }
  ml_board_check(c);return 1;
}
static int ml_world_cup_valid(const MasterLeague *c,const CupTournament *cup,uint32_t team,int national) {
  if(!cup->team_count)return !cup->round_count && !cup->champion;
  if(cup->team_count<2u || cup->team_count>32u || cup->human_count>1u ||
      (cup->human_count && cup->human_teams[0]!=team) || cup->home_away || cup->third_place_enabled)return 0;
  uint32_t teams[32],count=0u,bracket=2u,rounds=1u;
  while(bracket<cup->team_count){bracket*=2u;rounds++;}
  if(cup->bracket_size!=bracket || cup->round_count!=rounds || cup->active_round>=rounds)return 0;
  for(uint32_t i=0;i<bracket/2u;i++) {
    const CupFixture *f=&cup->fixtures[0][i];
    if(f->home)teams[count++]=f->home;
    if(f->away)teams[count++]=f->away;
  }
  if(count!=cup->team_count)return 0;
  for(uint32_t i=0;i<count;i++) {
    if(national ? !ml_national_region(teams[i]) : !ml_find_club(c,teams[i]))return 0;
    for(uint32_t j=0;j<i;j++)if(teams[i]==teams[j])return 0;
  }
  for(uint32_t r=0;r<rounds;r++)for(uint32_t i=0;i<bracket>>(r+1u);i++) {
    const CupFixture *f=&cup->fixtures[r][i];
    if(f->complete>1u || f->simulated>1u || f->home_goals>99u || f->away_goals>99u ||
        (f->home && f->home==f->away) || (r<cup->active_round && !f->complete) ||
        (f->complete && (!f->winner || (f->winner!=f->home && f->winner!=f->away))) ||
        (!f->complete && (f->winner || f->home_goals || f->away_goals)))return 0;
    for(uint32_t s=0;s<2u;s++) {
      const uint32_t t=s ? f->away : f->home;int found=!t;
      for(uint32_t j=0;j<count;j++)found|=teams[j]==t;
      if(!found)return 0;
      if(r && t && t!=cup->fixtures[r-1u][i*2u+s].winner)return 0;
    }
  }
  return cup->champion==cup->fixtures[rounds-1u][0].winner && cup->history_count<=32u;
}
static int ml_world_valid(const MasterLeague *c) {
  const MlWorldState *w=&c->world;
  if(!w->version) {const unsigned char *p=(const unsigned char *)w;for(size_t i=0;i<sizeof(*w);i++)if(p[i])return 0;return 1;}
  if(w->version!=1u || w->continental_id>3u || w->job_checks>7u || w->national_checked>1u ||
      w->national_count>ML_MAX_NATIONAL_OFFERS || w->friendly_mask>3u || w->finals_started>1u ||
      !ml_world_cup_valid(c,&w->continental,c->settings.club,0))return 0;
  for(uint32_t i=0;i<ML_MAX_NATIONAL_OFFERS;i++) {
    const MlNationalOffer *o=&w->national_offers[i];
    if(i>=w->national_count) {if(o->team || o->expiry || o->status || o->seen)return 0;continue;}
    if(!w->national_checked || !ml_national_region(o->team) || o->expiry!=76u ||
        (o->status!=ML_OFFER_WAITING && o->status!=ML_OFFER_ACCEPTED && o->status!=ML_OFFER_REJECTED && o->status!=ML_OFFER_CANCELLED) ||
        (o->seen && o->seen!=ML_OFFER_WAITING && o->seen!=o->status && o->seen!=ML_OFFER_EXPIRED) ||
        (o->status==ML_OFFER_ACCEPTED && o->team!=w->national_team) ||
        (o->status==ML_OFFER_WAITING && w->national_team))return 0;
    for(uint32_t j=0;j<i;j++)if(w->national_offers[j].team==o->team)return 0;
  }
  if(!w->national_team)return !w->qualifiers.team_count && !w->regional.team_count && !w->world_cup.team_count && !w->national_region;
  if(!ml_national_region(w->national_team) || w->national_region!=ml_national_region(w->national_team) ||
      !ml_world_cup_valid(c,&w->regional,w->national_team,1) || !ml_world_cup_valid(c,&w->world_cup,w->national_team,1))return 0;
  for(uint32_t i=0;i<2u;i++) {
    const LeagueFixture *f=&w->friendlies[i];
    if(!ml_national_region(f->home) || !ml_national_region(f->away) || f->home==f->away ||
       (f->home!=w->national_team && f->away!=w->national_team) || f->complete!=((w->friendly_mask>>i)&1u) ||
       f->simulated>1u || f->home_goals>99u || f->away_goals>99u || (!f->complete && (f->home_goals || f->away_goals)))return 0;
  }
  const LeagueTournament *q=&w->qualifiers;
  if(q->team_count!=4u || q->active_matchday>6u || q->matchday_count!=6u || q->fixture_count!=12u || q->scorer_count)return 0;
  uint32_t teams[4];for(uint32_t i=0;i<4u;i++){teams[i]=q->standings[i].team;if(!ml_national_region(teams[i]))return 0;}
  LeagueTournament *check=malloc(sizeof(*check));if(!check)return 0;
  int valid=league_tournament_init(check,teams,4u,&w->national_team,1u,1,q->seed);
  if(valid) {
    league_tournament_set_system(check,LEAGUE_SYSTEM_STANDINGS);
    /* init stores an evolved seed: use fixture identity below, not regenerated
     * random schedule, while rebuilding every standing from completed games. */
    memset(check->standings,0,sizeof(check->standings));
    for(uint32_t i=0;i<4u;i++)check->standings[i].team=teams[i];
    uint8_t pairs[4][4]={{0}};
    for(uint32_t d=0;valid && d<6u;d++) {
      if(q->matchday_first[d]!=d*2u || q->matchday_fixture_count[d]!=2u){valid=0;break;}
      uint32_t day_teams=0u;
      for(uint32_t j=0;valid && j<2u;j++) {
        const LeagueFixture *f=&q->fixtures[d*2u+j];uint32_t h=4u,a=4u;
        for(uint32_t i=0;i<4u;i++){if(teams[i]==f->home)h=i;if(teams[i]==f->away)a=i;}
        if(h==4u || a==4u || h==a || pairs[h][a]++ || (day_teams&((1u<<h)|(1u<<a))) ||
            f->complete!=(d<q->active_matchday) || f->simulated>1u || f->home_goals>99u || f->away_goals>99u){valid=0;break;}
        day_teams|=(1u<<h)|(1u<<a);check->fixtures[d*2u+j]=*f;check->fixtures[d*2u+j].complete=0u;
        if(f->complete)league_tournament_record_table_fixture(check,d*2u+j,f->home_goals,f->away_goals,f->simulated);
        else if(f->home_goals || f->away_goals)valid=0;
      }
      if(d<q->active_matchday)league_tournament_commit_matchday(check);
    }
    if(memcmp(check->standings,q->standings,4u*sizeof(LeagueStanding)) || q->human_count!=1u ||
       q->human_teams[0]!=w->national_team || q->home_away!=1u || q->reserved[0]!=LEAGUE_SYSTEM_STANDINGS ||
       q->phase!=(q->active_matchday==6u ? LEAGUE_PHASE_COMPLETE : LEAGUE_PHASE_TABLE))valid=0;
  }
  free(check);return valid;
}

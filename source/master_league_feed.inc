/* Read-only feed projection from the canonical fixtures. No second result
 * ledger, save migration, random roll or implicit simulation in this path. */
typedef struct {
  uint32_t day,kind,home,away,hg,ag,winner,team;
} MlFeedMatch;
static MlFeedMatch feed_seen;
static uint32_t feed_seen_season;

static void ml_feed_insert(MlFeedMatch recent[3],uint32_t *count,MlFeedMatch match) {
  if(!match.home || !match.away || !match.team || match.day>career.day ||
      (match.home!=match.team && match.away!=match.team))return;
  uint32_t at=0u;
  while(at<*count && (recent[at].day>match.day ||
      (recent[at].day==match.day && recent[at].kind>=match.kind)))at++;
  if(at>=3u)return;
  if(*count<3u)(*count)++;
  for(uint32_t i=*count-1u;i>at;i--)recent[i]=recent[i-1u];
  recent[at]=match;
}
static uint32_t ml_feed_recent(MlFeedMatch recent[3]) {
  uint32_t count=0u;
  for(uint32_t kind=ML_EVENT_LEAGUE;kind<=ML_EVENT_WORLD_CUP;kind++) {
    if(!ml_event_is_match(kind))continue;
    const uint32_t team=ml_event_manager_team(&career,kind);if(!team)continue;
    const CupTournament *cup=ml_event_cup(&career,kind);
    if(cup) {
      for(uint32_t r=0;r<cup->round_count;r++) {
        const uint32_t day=kind==ML_EVENT_CUP ? ml_cup_day(&career,r) : ml_world_day(&career,kind,r);
        for(uint32_t j=0;j<cup_tournament_fixture_count(cup,r);j++) {
          const CupFixture *f=&cup->fixtures[r][j];
          if(f->complete)ml_feed_insert(recent,&count,(MlFeedMatch){day,kind,f->home,f->away,f->home_goals,f->away_goals,f->winner,team});
        }
      }
    }else if(kind==ML_EVENT_FRIENDLY) {
      for(uint32_t i=0;i<2u;i++) {
        const LeagueFixture *f=&career.world.friendlies[i];
        if(f->complete)ml_feed_insert(recent,&count,(MlFeedMatch){ml_world_day(&career,kind,i),kind,f->home,f->away,f->home_goals,f->away_goals,0u,team});
      }
    }else {
      const LeagueTournament *league=kind==ML_EVENT_LEAGUE ? &career.league : &career.world.qualifiers;
      for(uint32_t r=0;r<league->matchday_count;r++) {
        const uint32_t day=kind==ML_EVENT_LEAGUE ? ml_league_day(&career,r) : ml_world_day(&career,kind,r);
        for(uint32_t j=0;j<league->matchday_fixture_count[r];j++) {
          const LeagueFixture *f=league_tournament_matchday_fixture(league,r,j);
          if(f && f->complete)ml_feed_insert(recent,&count,(MlFeedMatch){day,kind,f->home,f->away,f->home_goals,f->away_goals,0u,team});
        }
      }
    }
  }
  return count;
}
static const char *ml_feed_competition(uint32_t kind) {
  return kind==ML_EVENT_LEAGUE ? ml_competition_name() : kind==ML_EVENT_CUP ? ml_cup_name() : ml_world_name(&career,kind);
}
static const char *ml_feed_result(const MlFeedMatch *m) {
  if(m->hg==m->ag) {
    if(m->winner)return m->winner==m->team ? "WIN ON PENS" : "LOSS ON PENS";
    return "DRAW";
  }
  return (m->hg>m->ag ? m->home : m->away)==m->team ? "WIN" : "LOSS";
}
static void ml_feed_enter(void) {
  MlFeedMatch recent[3]={0};const uint32_t count=ml_feed_recent(recent);
  if(count && (feed_seen_season!=career.season || memcmp(&feed_seen,&recent[0],sizeof(feed_seen))))feed_index=1u;
  if(count)feed_seen=recent[0];else memset(&feed_seen,0,sizeof(feed_seen));
  feed_seen_season=career.season;feed_elapsed=feed_rotated=0u;
}
static void ml_story_view(MlView *v) {
  MlStoryView *s=&v->story;
  s->club_badge=exhibition_team_catalog_badge(career.settings.club);
  s->nation_badge=exhibition_team_catalog_badge(career.manager_nationality);
  snprintf(v->club_name,64,"%s",exhibition_team_catalog_name(career.settings.club));
  snprintf(s->headline,64,"%s",feed_index==0u ? career.manager_name : feed_index==1u ? "MATCH CENTRE" :
    feed_index==2u ? "THE SEASON SO FAR" : "TRANSFER DESK");
  snprintf(s->summary,112,"%s",feed_index==0u ? exhibition_team_catalog_name(career.manager_nationality) :
    feed_index==1u ? "Latest results / all competitions" : feed_index==2u ? ml_competition_name() : "Your club's transfer activity");
  if(feed_index==1u) {
    MlFeedMatch recent[3]={0};s->history_count=ml_feed_recent(recent);
    for(uint32_t i=0;i<s->history_count;i++) {
      const MlFeedMatch *m=&recent[i];const int home=m->home==m->team;
      if(!i) {
        s->has_result=1u;s->home_badge=exhibition_team_catalog_badge(m->home);s->away_badge=exhibition_team_catalog_badge(m->away);
        snprintf(s->home,64,"%s",exhibition_team_catalog_name(m->home));snprintf(s->away,64,"%s",exhibition_team_catalog_name(m->away));
        s->home_goals=m->hg;s->away_goals=m->ag;s->result_kind=m->kind;s->result_day=m->day;s->result_team=m->team;
        snprintf(s->competition,64,"%s",ml_feed_competition(m->kind));snprintf(s->result,32,"%s",ml_feed_result(m));
      }
      MlViewRow *r=&s->history[i];const uint32_t other=home ? m->away : m->home;
      r->enabled=1;r->badge=exhibition_team_catalog_badge(other);
      snprintf(r->label,64,"%s",exhibition_team_catalog_name(other));
      snprintf(r->detail,96,"%s / DAY %u / %.55s",ml_feed_result(m),m->day+1u,ml_feed_competition(m->kind));
      /* History has one opponent label: scores are always manager : opponent. */
      snprintf(r->value,48,"%u - %u",home ? m->hg : m->ag,home ? m->ag : m->hg);
    }
  }
  const MlClub *own=ml_find_club(&career,career.settings.club);
  const uint32_t squad=own ? own->count : 0u;
  const char *labels[3]={feed_index==2u ? "LEAGUE POSITION" : feed_index==3u ? "WINDOW" : "SEASON",
    feed_index==2u ? "BOARD TARGET" : feed_index==3u ? "COMPLETED DEALS" : "SQUAD",
    feed_index==2u ? "SEASONS COMPLETED" : feed_index==3u ? "SQUAD" : "BOARD TARGET"};
  for(uint32_t i=0;i<3u;i++)snprintf(s->stat_label[i],32,"%s",labels[i]);
  snprintf(s->stat_value[0],48,"%u",feed_index==2u ? ml_rank(&career) : career.season);
  snprintf(s->stat_value[1],48,feed_index==2u ? "TOP %u" : "%u PLAYERS",feed_index==2u ? career.target_rank : squad);
  snprintf(s->stat_value[2],48,feed_index==2u ? "%u" : "TOP %u",feed_index==2u ? career.seasons_completed : career.target_rank);
  if(feed_index==3u) {
    uint32_t deals=0u;
    for(uint32_t i=career.office.offer_count;i>0u;i--) {
      const MlOffer *o=&career.office.offers[i-1u];deals+=o->status==ML_OFFER_COMPLETED;
      if(s->history_count>=3u)continue;
      MlViewRow *r=&s->history[s->history_count++];r->enabled=1;
      const uint32_t other=o->incoming ? o->to : o->from;
      r->badge=exhibition_team_catalog_badge(other);
      snprintf(r->label,64,"%s",career.players[o->player].name);
      static const char *status[]={"","WAITING","APPROVED","COUNTEROFFER","REJECTED","COMPLETED","CANCELLED","OFFER EXPIRED"};
      snprintf(r->detail,96,"%s / %.48s",status[o->status],other ? exhibition_team_catalog_name(other) : "FREE AGENT");
      ml_money(r->value,48,o->fee);
    }
    snprintf(s->stat_value[0],48,"%s",ml_window_open(&career) ? "OPEN" : "CLOSED");
    snprintf(s->stat_value[1],48,"%u",deals);snprintf(s->stat_value[2],48,"%u / 40",squad);
  }
}

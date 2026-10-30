static void ranking_view(MdView *v) {
  uint64_t end=md_season_end(now());
  struct tm local;time_t seconds=(time_t)((end+MD_LEAGUE_TIMEZONE_MS)/1000u);gmtime_r(&seconds,&local);
  char date[32];strftime(date,sizeof(date),"%d %b %Y",&local);
  snprintf(v->caption,sizeof(v->caption),"RESETS %s 00:00 WIB - MONTHLY SEASON",date);
  copy(v->summary,sizeof(v->summary),ranking_section?"ONE CHAMPION PER COMPLETED MONTH":"PARTICIPATION AND PODIUM POINTS ACCUMULATE THIS MONTH");
  md_season_text(now(),v->season_label,sizeof(v->season_label),0);
  v->rank_reset_ms=end;
}
static void champions_view(MdView *v) {
  copy(v->headline,sizeof(v->headline),"LEAGUE RANKING HISTORY");
  copy(v->caption,sizeof(v->caption),"EVERY CHAMPION IS REMEMBERED AFTER RANKING RESETS");
  v->total=champion_total();if(focus>=v->total)focus=v->total ? v->total-1u : 0;
  v->focus=focus;v->first=focus/5u*5u;v->count=v->total-v->first;if(v->count>5)v->count=5;
  static MdRow cards[5];static uint32_t first=UINT32_MAX,total=UINT32_MAX,seed,hash;
  if(first!=v->first || total!=v->total || seed!=md.seed || hash!=md.checksum) {
    memset(cards,0,sizeof(cards));MdArchive *a=calloc(1,sizeof(*a));
    for(uint32_t i=0;i<v->count;i++) {
      uint32_t week=v->total-v->first-i;MdRow *r=&cards[i];
      snprintf(r->value,sizeof(r->value),"LEAGUE %02u",week);
      if(a && champion_read(week,a)) {
        uint32_t team=champion_team(&a->save);r->badge=exhibition_team_catalog_badge(a->players.clubs[team]);r->enabled=1;
        copy(r->label,sizeof(r->label),team ? exhibition_team_catalog_name(a->players.clubs[team]) : a->save.name);
        uint64_t result=manager_dummy_week(&a->save,UINT64_MAX).result_ms;
        struct tm date;time_t seconds=(time_t)((result+MD_LEAGUE_TIMEZONE_MS)/1000u);gmtime_r(&seconds,&date);
        char stamp[32];strftime(stamp,sizeof(stamp),"%d %b %Y",&date);
        snprintf(r->detail,sizeof(r->detail),"W%u CHAMPION - %s",md_hub_weekday(a->save.fixtures[0].kickoff_ms)<3?1:2,stamp);
      } else copy(r->label,sizeof(r->label),"Archive unavailable");
    }
    free(a);first=v->first;total=v->total;seed=md.seed;hash=md.checksum;
  }
  memcpy(v->rows,cards,v->count*sizeof(*cards));
  if(!v->count)copy(v->summary,sizeof(v->summary),"The first champion will appear after the league is complete.");
  helper(v,"LS","SCROLL");if(v->count)helper(v,"A","VIEW CHAMPION");
}
static void champion_view(MdView *v) {
  uint32_t team=champion_team(&champion.save),points=0,wins=0,draws=0,losses=0,gf=0,ga=0;
  for(uint32_t i=0;i<MD_FIXTURES;i++) {
    const MdFixture *f=&champion.save.fixtures[i];if(f->home!=team && f->away!=team)continue;
    uint32_t score[2];manager_dummy_score(f,manager_dummy_duration(f),score);uint32_t side=f->home==team ? 0u : 1u;
    gf+=score[side];ga+=score[1-side];wins+=score[side]>score[1-side];draws+=score[side]==score[1-side];losses+=score[side]<score[1-side];
  }
  points=wins*3+draws;v->badge=exhibition_team_catalog_badge(champion.players.clubs[team]);
  copy(v->headline,sizeof(v->headline),team ? exhibition_team_catalog_name(champion.players.clubs[team]) : champion.save.name);
  snprintf(v->caption,sizeof(v->caption),"LEAGUE %02u CHAMPION - PERMANENT HONOURS",champion_choice);
  v->count=4;char value[40];
  row(v,0,"LEAGUE CHAMPION","This title remains after the Overall Rank reset",v->headline,v->badge);
  snprintf(value,sizeof(value),"%u LEAGUE POINT",points);row(v,1,"FINAL POINTS","Official completed league results",value,0);
  snprintf(value,sizeof(value),"%u W - %u D - %u L",wins,draws,losses);row(v,2,"SEASON RECORD","Six matches in the seven-team league",value,0);
  snprintf(value,sizeof(value),"%u FOR - %u AGAINST",gf,ga);row(v,3,"GOALS","From the saved match event records",value,0);
}
static void touchline_view(MdView *v,const MdFixture *f) {
  uint32_t count=0,index[MD_EVENTS];
  for(uint32_t i=0;i<manager_dummy_event_count(f);i++)if(f->events[i].at_ms<=v->elapsed_ms)index[count++]=i;
  v->touchline_total=count;v->touchline_open=touchline_open;
  if(!touchline_open)return;
  if(touchline_focus>=count)touchline_focus=count ? count-1u : 0;
  v->touchline_first=touchline_focus>2u ? touchline_focus-2u : 0;
  if(count>5u && v->touchline_first>count-5u)v->touchline_first=count-5u;
  v->touchline_count=count-v->touchline_first;if(v->touchline_count>5)v->touchline_count=5;
  for(uint32_t i=0;i<v->touchline_count;i++) {
    const MdEvent *e=&f->events[index[count-1-v->touchline_first-i]];MdRow *r=&v->touchline[i];
    uint32_t club=e->side ? f->away : f->home;const MlCatalogPlayer *p=e->player && e->player<=18 ?
      ml_catalog_find_identity(broadcast_profile()->match_roster[club][e->player-1]) : NULL;
    uint32_t seconds=manager_dummy_game_seconds(f,e->at_ms);uint32_t score[2];manager_dummy_score(f,e->at_ms,score);
    snprintf(r->label,sizeof(r->label),"%02u:%02u  %s",seconds/60u,seconds%60u,event_name(e->kind));
    copy(r->detail,sizeof(r->detail),e->kind==MD_HALF ? "The first half is complete." : p ? p->name : "Team event");
    if(e->kind==MD_SUB) {
      const MlCatalogPlayer *on=e->other && e->other<=18 ? ml_catalog_find_identity(broadcast_profile()->match_roster[club][e->other-1]) : NULL;
      snprintf(r->detail,sizeof(r->detail),"OFF %.36s  /  ON %.36s",p ? p->name : "Player",on ? on->name : "Player");
    } else if(e->kind==MD_PASS && e->other) {
      const MlCatalogPlayer *to=ml_catalog_find_identity(broadcast_profile()->match_roster[club][e->other-1]);
      snprintf(r->detail,sizeof(r->detail),"%.38s  TO  %.38s",p ? p->name : "Player",to ? to->name : "Player");
    }
    if(e->kind==MD_GOAL)snprintf(r->value,sizeof(r->value),"%u - %u",score[0],score[1]);
    else snprintf(r->value,sizeof(r->value),"%.39s",broadcast_team_name(club));
    r->badge=e->kind==MD_HALF ? 0 : broadcast_badge(club);r->phase=e->kind;r->enabled=1;
    r->selected=v->touchline_first+i==touchline_focus;
  }
  v->helper_count=0;helper(v,"B","CLOSE");helper(v,"LS","SCROLL");helper(v,"L","PREV PAGE");helper(v,"R","NEXT PAGE");
}

static void calendar_time(uint64_t stamp,struct tm *out) {
  time_t seconds=(time_t)((stamp+MD_LEAGUE_TIMEZONE_MS)/1000u);gmtime_r(&seconds,out);
}
static void calendar_view(MdView *v) {
  static const char *const names[]={"MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"};
  copy(v->headline,sizeof(v->headline),"WEEKLY SCHEDULE");
  copy(v->caption,sizeof(v->caption),"TWO LEAGUES EACH WEEK - ALL TIMES WIB (UTC+7)");
  v->total=7;v->first=focus ? focus-1u : 0u;
  if(v->first>7u-MD_WEEK_VISIBLE)v->first=7u-MD_WEEK_VISIBLE;
  v->count=MD_WEEK_VISIBLE;
  const uint64_t monday=calendar_monday(&md);
  for(uint32_t i=0;i<v->count;i++) {
    const uint32_t d=v->first+i+1u;const uint64_t stamp=monday+(d-1u)*(uint64_t)MD_CALENDAR_DAY_MS;
    MdScheduleDay *tile=&v->schedule[i];struct tm date;calendar_time(stamp,&date);
    char label[64],detail[96],date_text[40];strftime(date_text,sizeof(date_text),"%d %b %Y",&date);
    const int preparation=d==1 || d==4,overview=d==7;
    const int today=calendar_local_day(now())==calendar_local_day(stamp);
    snprintf(label,sizeof(label),"%s - %s%s",names[d-1],preparation ? "PREPARATION" : overview ? "OVERVIEW" : "MATCH DAY",today ? " - TODAY" : "");
    copy(tile->period,sizeof(tile->period),"00:00 - 24:00 WIB");
    copy(detail,sizeof(detail),preparation ? "Shop, register your squad and prepare your Game Plan" : overview ? "Day off. Review both leagues, standings and replays." : "Fixtures are available after joining this league season.");
    for(uint32_t n=0;n<MD_FIXTURES;n++) {
      const MdFixture *f=&md.fixtures[n];
      if(fixture_day(&md,f)!=d || (f->home && f->away) || tile->match_count>=4)continue;
      MdRow *match=&tile->matches[tile->match_count++];uint32_t opponent=f->home ? f->home : f->away;
      struct tm kickoff;calendar_time(f->kickoff_ms,&kickoff);
      snprintf(match->label,sizeof(match->label),"Vs %.60s",team_name(opponent));
      snprintf(match->value,sizeof(match->value),"%02d:%02d",kickoff.tm_hour,kickoff.tm_min);
      copy(match->detail,sizeof(match->detail),f->home ? "AWAY" : "HOME");
      match->badge=badge(opponent);match->team_id=opponent;match->phase=manager_dummy_phase(f,now());
    }
    row(v,i,label,detail,date_text,0);
  }
  helper(v,"LS","SCROLL");helper(v,"A",focus==6 ? "OVERVIEW" : focus==0 || focus==3 ? "GAME PLAN" : "VIEW MATCHES");
}

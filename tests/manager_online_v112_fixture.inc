static void monthly_mock(const MoHttpRequest *q,MoHttpResponse *r){
  assert(online.monthly_capable&&q->environment==online.environment&&!strcmp(q->method,"GET"));
  unsigned page=strstr(q->path,"page=2")?2:1;int past=strstr(q->path,"/past?")!=NULL;
  if(page==2)assert(strstr(q->path,"snapshot_id=stable_112"));
  char body[24000];size_t n=(size_t)snprintf(body,sizeof(body),"{\"period\":\"CALENDAR_MONTH\",\"scope\":\"%s\",\"snapshot_id\":\"stable_112\",\"page\":%u,\"page_size\":50,\"total\":%u,\"season\":{\"season_id\":\"2026-11\",\"starts_at_ms\":1793466000000,\"ends_at_ms\":1796058000000},\"items\":[",past?"PAST":"CURRENT",page,past?1:53);
  if(past)n+=(size_t)snprintf(body+n,sizeof(body)-n,"{\"rank\":1,\"club_id\":84,\"club_name\":\"October Winner\",\"presentation_team_id\":108,\"points\":7500,\"season\":{\"season_id\":\"2026-10\",\"starts_at_ms\":1790787600000,\"ends_at_ms\":1793466000000}}");
  else for(unsigned i=(page-1)*50;i<(page==1?50:53);i++)n+=(size_t)snprintf(body+n,sizeof(body)-n,"%s{\"rank\":%u,\"club_id\":%u,\"club_name\":\"Club %u\",\"presentation_team_id\":108,\"points\":2500,\"participation_points\":500,\"podium_points\":2000}",i==(page-1)*50?"":",",i+1,i+84,i+1);
  snprintf(body+n,sizeof(body)-n,"]}");response(r,200,body);
}
static void monthly_flow(void){
  fake_now=1793565960000ULL;login();online.tab=2;online.focus=1;unsigned before=calls;
  manager_online_pad(A);assert(online.notice[0]&&calls==before&&!monthly_calls);manager_online_pad(A);
  online.monthly_capable=1;manager_online_pad(A);idle();MdView v;manager_online_view(&v);
  assert(v.page==MD_OVERALL&&v.total==53&&v.count==5&&!strcmp(v.rows[0].value,"2500 PTS")&&v.rows[0].badge&&v.rows[0].selected);
  assert(v.ranking_section==0&&v.rank_reset_ms==1796058000000ULL&&strstr(v.season_label,"November"));
  for(unsigned i=0;i<50;i++)manager_online_pad(DOWN);
  idle();manager_online_view(&v);
  assert(monthly_calls==2&&v.ranking_offset==50&&v.count==3&&v.total==53&&strstr(v.rows[0].label,"51."));
  manager_online_pad(UP);idle();assert(online.rank_page==1&&online.focus==49); /* Previous network page keeps its last row focused. */
  manager_online_pad(R);idle();manager_online_view(&v);assert(v.ranking_section==1&&v.total==1&&strstr(v.rows[0].detail,"October 2026 - CHAMPION"));
  manager_online_pad(A);assert(online.page==MD_OVERALL&&!online.busy); /* Past honours are immutable summaries. */
  manager_online_pad(L);idle();manager_online_view(&v);assert(v.ranking_section==0&&v.first==0);
  manager_online_pad(B);assert(online.page==MD_DASHBOARD&&online.focus==1&&online.tab==2);
}
static void monthly_validation(void){
  assert(md_season_start(1793465999999ULL)==1790787600000ULL);
  assert(md_season_start(1793466000000ULL)==1793466000000ULL);
  assert(md_season_end(1793466000000ULL)==1796058000000ULL);
  assert(md_season_end(1796058000000ULL)==1798736400000ULL);
  assert(md_season_end(1706720400000ULL)==1709226000000ULL); /* Leap February. */
  assert(md_season_prize(1)==2000&&md_season_prize(2)==1500&&md_season_prize(3)==1000&&!md_season_prize(4));
  fake_now=1793565960000ULL;login();online.monthly_capable=1;online.rank_request_page=1;
  const char *base="{\"period\":\"CALENDAR_MONTH\",\"scope\":\"CURRENT\",\"snapshot_id\":\"good\",\"page\":1,\"page_size\":50,\"total\":1,\"season\":{\"season_id\":\"2026-11\",\"starts_at_ms\":1793466000000,\"ends_at_ms\":1796058000000},\"items\":[{\"rank\":1,\"club_id\":84,\"club_name\":\"Alpha\",\"presentation_team_id\":108,\"points\":2500,\"participation_points\":500,\"podium_points\":2000}]}";
  json(base);assert(parse_monthly(&doc,0)&&online.row_count==1);
  char mutated[1024];strcpy(mutated,base);char *p=strstr(mutated,"\"points\":2500");assert(p);memcpy(p+9,"9000",4);json(mutated);assert(!parse_monthly(&doc,0)&&!strcmp(online.rows[0].value,"2500 PTS"));
  strcpy(mutated,base);p=strstr(mutated,"2026-11");memcpy(p,"2026-10",7);json(mutated);assert(!parse_monthly(&doc,0));
  strcpy(mutated,base);p=strstr(mutated,"good");memcpy(p,"a&=b",4);json(mutated);assert(!parse_monthly(&doc,0));
  online.rank_request_section=1;json(base);assert(!parse_monthly(&doc,0));online.rank_request_section=0;
  online.rank_request_page=2;json(base);assert(!parse_monthly(&doc,0));online.rank_request_page=1;
  online.server_anchor=1796058000000ULL;online.mono_anchor=online.mono;json(base);assert(!parse_monthly(&doc,0)); /* Stale season cannot appear after reset. */
  json("[{\"account_id\":42,\"ranking_points\":8000}]");assert(!parse_monthly(&doc,0));
  online.page=MD_OVERALL;MdView v;manager_online_view(&v);assert(!v.count&&strstr(v.empty_detail,"new season"));
  online.profile_season[0]=0;online.rank_refresh_end=0;online.notice[0]=0;
  unsigned before=monthly_calls;manager_online_tick(++host_ms);idle();
  assert(monthly_calls==before+1&&online.rank_refresh_end==1796058000000ULL);
  online.notice[0]=0;for(unsigned i=0;i<10;i++)manager_online_tick(++host_ms);
  assert(monthly_calls==before+1); /* A stale server season cannot create a refresh storm. */
}
static void hub_live_badge(void){
  fake_now=1793768400000ULL;login();online.page=MD_DASHBOARD;online.tab=online.focus=0;
  online.phase_ends=fake_now+86400000;copy(online.phase,sizeof(online.phase),"MATCH_DAY");
  json("[{\"fixture_id\":55,\"state\":\"LIVE\",\"broadcast_start_ms\":1793768400000,\"broadcast_end_ms\":1793769060000},{\"fixture_id\":56,\"state\":\"SCHEDULED\",\"broadcast_start_ms\":1793772000000}]");
  assert(parse_matches(&doc,0));MdView v;manager_online_view(&v);assert(v.hub_live==1);
  online.server_anchor=fake_now-1;manager_online_view(&v);assert(!v.hub_live);
  online.server_anchor=fake_now+660000;manager_online_view(&v);assert(!v.hub_live);
  online.server_anchor=fake_now;online.match_cycle++;manager_online_view(&v);assert(!v.hub_live);online.match_cycle=online.cycle;
  copy(online.phase,sizeof(online.phase),"PREPARATION");manager_online_view(&v);assert(!v.hub_live);
  copy(online.phase,sizeof(online.phase),"SETTLED");manager_online_view(&v);assert(!v.hub_live);
  copy(online.phase,sizeof(online.phase),"MATCH_DAY");online.mono=online.schedule_seen+90000;manager_online_view(&v);assert(!v.hub_live);
  online.mono=host_ms;online.mono_anchor=host_ms;online.schedule_refresh=host_ms;unsigned before=schedule_calls;
  manager_online_tick(++host_ms);idle();assert(schedule_calls==before+1&&online.page==MD_DASHBOARD&&!online.modal_busy);
  manager_online_view(&v);assert(!v.hub_live); /* Empty refresh clears the old badge. */
  before=schedule_calls;for(unsigned i=0;i<10;i++)manager_online_tick(++host_ms);assert(schedule_calls==before);
}

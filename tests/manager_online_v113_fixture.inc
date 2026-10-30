/* Regression cases from the four-mode audit; only synthetic HTTP and saves. */
static void compat_recheck(void){
  login();assert(request(J_LOGOUT,"POST","/auth/logout","{}",1));idle();
  assert(!online.authenticated&&online.page==MD_REGISTER);online.notice[0]=0;
  wrong_version=1;manager_online_pad(X);assert(!online.compatible);idle();
  assert(!online.compatible&&online.notice[0]);manager_online_pad(A);manager_online_pad(A);
  assert(online.page==MD_REGISTER&&!online.authenticated);
  idle();online.notice[0]=0;wrong_version=0;manager_online_pad(X);idle();assert(online.compatible);
  const char *bad[]={
    "{\"required_online_version\":\"1.0.0\",\"required_catalog_content_sha256\":\"" MANAGER_ONLINE_CATALOG "\",\"required_runtime_pair_id\":\"" MANAGER_ONLINE_PAIR "\",\"api_schema_version\":1,\"maintenance\":true}",
    "{\"required_online_version\":\"1.0.0\",\"required_catalog_content_sha256\":\"" MANAGER_ONLINE_CATALOG "\",\"required_runtime_pair_id\":\"" MANAGER_ONLINE_PAIR "\",\"api_schema_version\":1}",
    "{\"required_online_version\":\"1.0.0\",\"required_catalog_content_sha256\":\"bad hash\",\"required_runtime_pair_id\":\"" MANAGER_ONLINE_PAIR "\",\"api_schema_version\":1,\"maintenance\":false}",
    "{\"required_online_version\":\"1.0.0\",\"required_catalog_content_sha256\":\"" MANAGER_ONLINE_CATALOG "\",\"required_runtime_pair_id\":\"wrong pair\",\"api_schema_version\":1,\"maintenance\":false}",
    "null"};
  for(unsigned i=0;i<sizeof(bad)/sizeof(*bad)+3;i++){
    online.compatible=1;MoResult r={.generation=generation,.kind=J_COMPAT,.page=MD_REGISTER};
    if(i<sizeof(bad)/sizeof(*bad))response(&r.http,200,bad[i]);
    else if(i==sizeof(bad)/sizeof(*bad))r.http.transport_error=1;
    else if(i==sizeof(bad)/sizeof(*bad)+1)raw_response(&r.http,"{");
    else response(&r.http,503,"null");
    consume(&r);mo_http_free(&r.http);assert(!online.compatible&&online.notice[0]);
    manager_online_pad(A);manager_online_pad(A);assert(online.page==MD_REGISTER);
    idle();online.notice[0]=0;
  }
}
static void badge_navigation(void){
  login();assert(request(J_HUB_LIVE,"GET","/league/schedule",NULL,0));
  manager_online_pad(R);assert(online.tab==1);online.page=MD_RULES;
  manager_online_pad(B);assert(online.page==MD_DASHBOARD);
  char oversized[12289];memset(oversized,'x',sizeof(oversized)-1);oversized[sizeof(oversized)-1]=0;
  assert(!request(J_SAVE_PLAN,"PUT","/club/gameplan",oversized,1));
  assert(!online.queued.kind&&online.busy_kind==J_HUB_LIVE);manager_online_pad(A);
  /* API-dependent A is queued with loading rather than ignored or duplicated. */
  online.tab=1;online.focus=2;manager_online_pad(A);
  assert(online.queued.kind==J_OFFERS&&online.modal_busy&&online.busy_kind==J_OFFERS);
  manager_online_pad(A);manager_online_pad(B);assert(online.queued.kind==J_OFFERS);
  idle();assert(online.page==MD_SHOP_CLUBS&&!online.busy&&!online.queued.kind);
  /* Choose club, then size before payment. The original journal still sends once. */
  manager_online_pad(A);manager_online_pad(A);manager_online_pad(A);manager_online_pad(LEFT);
  assert(online.page==MD_PACK_BUY&&request(J_HUB_LIVE,"GET","/league/schedule",NULL,0));
  manager_online_pad(A);assert(online.queued.kind==J_PAY&&online.pay_uncertain&&!payments);
  char key[37];copy(key,sizeof(key),online.queued.http.key);assert(!strcmp(key,online.pay_key));
  idle();assert(payments==1&&!strcmp(payment_key,key)&&online.page==MD_PACK_OPENING);
}
static void badge_stale_response(void){
  login();online.match_count=1;online.matches[0].id=999;
  for(unsigned i=0;i<6;i++){
    MoResult r={.generation=generation,.kind=J_HUB_LIVE,.scope={.generation=generation,.cycle=online.cycle,.environment=online.environment}};
    copy(r.scope.account,sizeof(r.scope.account),online.account);
    response(&r.http,i==3?401:200,"[]");
    if(i==0)r.scope.cycle++;else if(i==1)r.scope.environment=MO_TEST;
    else if(i==2)copy(r.scope.account,sizeof(r.scope.account),"999");
    else if(i==4){mo_http_free(&r.http);raw_response(&r.http,"{");}
    else if(i==5){mo_http_free(&r.http);response(&r.http,200,"[{\"fixture_id\":55},{\"fixture_id\":0}]");}
    consume(&r);mo_http_free(&r.http);
    assert(online.match_count==1&&online.matches[0].id==999&&!online.notice[0]&&!refreshes);
  }
}
static void cache_scope(void){
  login();
  for(unsigned account_change=0;account_change<2;account_change++){
    online.standing_count=online.news_count=online.activity_count=online.match_count=online.player_feed_count[0]=1;
    online.club_rank=1;online.league_points=9;
    online.calendar_conflict=1;online.phase_refresh_end=server_now();
    online.standings[0].selected=1;copy(online.standings[0].label,sizeof(online.standings[0].label),"PREVIOUS CYCLE");
    online.plan_dirty=1;copy(online.plan_key,sizeof(online.plan_key),"draft-key-kept");
    char body[1000];snprintf(body,sizeof(body),"{\"account\":{\"id\":%u,\"user_id\":\"qa_cycle\"},\"club\":{\"id\":84,\"name\":\"Current FC\",\"presentation_team_id\":108},\"wallet\":{\"balance\":5000,\"currency\":\"NX_CASH\",\"version\":2},\"league\":{\"cycle_id\":2,\"label\":\"W2\",\"state\":\"PREPARATION\",\"user_joined\":true,\"waiting_entry_count\":4,\"minimum_entries\":4,\"remaining_needed\":0}}",account_change?43:42);
    json(body);assert(parse_bootstrap(&doc,0));
    assert(!online.standing_count&&!online.news_count&&!online.activity_count&&!online.match_count&&!online.player_feed_count[0]&&!online.club_rank&&!online.league_points);
    assert(!online.calendar_conflict&&!online.phase_refresh_end);
    assert(online.plan_dirty&&!strcmp(online.plan_key,"draft-key-kept"));
    MoResult failed={.generation=generation,.kind=J_HUB_TABLE};failed.http.transport_error=1;consume(&failed);manager_online_pad(A);
    online.page=MD_DASHBOARD;online.tab=0;MdView v;manager_online_view(&v);assert(!v.table_preview_count);
    /* Same-scope bootstrap keeps the last successful presentation snapshot. */
    online.standing_count=1;json(body);assert(parse_bootstrap(&doc,0)&&online.standing_count==1);
  }
  /* TEST and PRODUCTION may reuse both numeric IDs. Auth has already changed
   * its realm when bootstrap arrives; the cache must retain its own scope. */
  online.environment=MO_TEST;online.clock_revision=1;
  json("{\"environment\":\"TEST\",\"capabilities\":{\"demo_time\":true},\"test_clock\":{\"revision\":1},\"account\":{\"id\":43,\"user_id\":\"test_scope\"},\"club\":{\"id\":84,\"name\":\"TEST FC\",\"presentation_team_id\":108},\"wallet\":{\"balance\":5000,\"currency\":\"NX_CASH\",\"version\":2},\"league\":{\"cycle_id\":2,\"label\":\"W2\",\"state\":\"PREPARATION\",\"user_joined\":true,\"waiting_entry_count\":4,\"minimum_entries\":4,\"remaining_needed\":0}}");
  assert(online.standing_count==1&&parse_bootstrap(&doc,0)&&!online.standing_count);
  online.standing_count=1;
  json("{\"cycle_id\":3,\"label\":\"W1\",\"state\":\"PREPARATION\",\"user_joined\":true,\"waiting_entry_count\":4,\"minimum_entries\":4,\"remaining_needed\":0}");
  assert(parse_league_status(&doc,0)&&!online.standing_count&&online.cycle==3);
}
static void stale_phase_label(void){
  login();uint64_t now=server_now();online.league_known=1;copy(online.phase,sizeof(online.phase),"PREPARATION");
  online.match_day_start=now-1000;online.match_day_end=now+660000;online.next_registration=now+86400000;
  online.phase_ends=online.match_day_end;assert(hub_phase()==MH_MATCH&&hub_phase_end()==online.match_day_end);
  online.server_anchor=online.match_day_end;online.mono_anchor=online.mono;
  assert(hub_phase()==MH_END&&hub_phase_end()==online.next_registration);
  online.server_anchor=online.next_registration;assert(hub_phase()==MH_PREPARATION); /* Never infer a new cycle. */
}

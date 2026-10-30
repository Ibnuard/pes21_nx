/* Hub Back exits the mode, without logging out or bypassing a modal action. */
static MoSession saved_session_v119(void){
  MoSession saved;FILE *file=fopen(MO_SESSION_FILE,"rb");assert(file);
  assert(fread(&saved,1,sizeof(saved),file)==sizeof(saved));
  assert(fgetc(file)==EOF);fclose(file);return saved;
}
static void hub_exit_v119(void){
  login();
  for(unsigned tab=0;tab<3;tab++){
    for(unsigned i=0;i<tab;i++)manager_online_pad(R);
    assert(online.page==MD_DASHBOARD&&online.tab==tab);
    MoSession before=saved_session_v119();unsigned requests=http_calls;
    manager_online_sample(B,B,0,0);
    assert(manager_online_take_action()==MD_ACTION_EXIT);
    assert(manager_online_take_action()==MD_ACTION_NONE);
    manager_online_close();idle();
    assert(!online.active&&!online.authenticated&&http_calls==requests);
    MoSession after=saved_session_v119();assert(!memcmp(&before,&after,sizeof(before)));
    manager_online_open();idle();
    assert(online.active&&online.authenticated&&online.page==MD_DASHBOARD);
    assert(logins==1&&refreshes==tab+1);
  }
}
static void hub_exit_background_v119(void){
  login();
  const int jobs[]={J_HUB_TABLE,J_HUB_SCHEDULE,J_HUB_NEWS,J_HUB_LIVE};
  const char *paths[]={"/league/standings","/league/schedule","/news","/league/schedule"};
  for(unsigned i=0;i<sizeof(jobs)/sizeof(*jobs);i++){
    MoSession before=saved_session_v119();unsigned requests=http_calls;
    uint64_t old_generation=generation;
    assert(request(jobs[i],"GET",paths[i],NULL,0));
    manager_online_sample(B,B,0,0);
    assert(manager_online_take_action()==MD_ACTION_EXIT);
    manager_online_close();idle();
    assert(!online.active&&!online.busy&&!online.notice[0]);
    /* Discard the old result; do not chain further hub requests after exit. */
    assert(generation>old_generation&&http_calls==requests+1);
    MoSession after=saved_session_v119();assert(!memcmp(&before,&after,sizeof(before)));
    manager_online_open();idle();
    assert(online.authenticated&&online.page==MD_DASHBOARD&&logins==1);
    MoResult late={.generation=old_generation,.kind=jobs[i],.page=MD_DASHBOARD};
    response(&late.http,401,"null");consume(&late);mo_http_free(&late.http);
    assert(online.authenticated&&!online.notice[0]&&!online.busy);
  }
}
static void hub_exit_context_v119(void){
  login();
  manager_online_pad(32u);assert(online.notice[0]);
  manager_online_pad(B);assert(!online.notice[0]&&!manager_online_take_action());
  online.join_confirm=1;
  manager_online_pad(B);assert(!online.join_confirm&&!manager_online_take_action());
  /* Modal API work must complete before Back can be handled. */
  read_cache_clear();online.focus=4;manager_online_pad(A);assert(online.busy&&online.modal_busy);
  manager_online_pad(B);assert(!manager_online_take_action());
  idle();assert(online.page==MD_CLUB_PROFILE);
  manager_online_pad(B);idle();
  assert(online.page==MD_DASHBOARD&&!manager_online_take_action());
  online.focus=2;manager_online_pad(A);assert(online.page==MD_WEEK_SCHEDULE);
  manager_online_pad(B);assert(online.page==MD_DASHBOARD&&!manager_online_take_action());
  manager_online_pad(B);assert(manager_online_take_action()==MD_ACTION_EXIT);
}

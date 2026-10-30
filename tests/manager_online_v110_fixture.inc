/* Synthetic regression coverage for editable plans and recorded playback. */
static unsigned plan_puts,plan_gets,recording_gets,watch_gets;
static int plan_fixture,plan_lose_ack,plan_conflict,zero_fixture,bundle_fixture;
static char saved_plan[10000],put_plan[10000],put_key[37];
static uint32_t saved_revision=7;

static void recording_header(char *out,size_t size,unsigned watermark){
  snprintf(out,size,"{\"fixture_id\":7,\"recording_hash\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",\"recording_version\":1,\"duration_ms\":660000,\"chunk_duration_ms\":30000,\"chunk_count\":22,\"broadcast_start_ms\":1700000000000,\"current_watermark_ms\":%u,\"state\":\"LIVE\"}",watermark);
}
static int extended_http(const MoHttpRequest *q,MoHttpResponse *r){
  if(strstr(q->path,"/matches/"))watch_gets++;
  if(plan_fixture&&!strcmp(q->path,"/club/gameplan")){
    if(!strcmp(q->method,"PUT")){
      assert(strlen(q->key)==36&&strlen(q->body)<sizeof(put_plan)&&strlen(q->body)<sizeof(saved_plan));plan_puts++;
      if(put_key[0]){assert(!strcmp(put_key,q->key));assert(!strcmp(put_plan,q->body));}
      else {copy(put_key,sizeof(put_key),q->key);memcpy(put_plan,q->body,strlen(q->body)+1);}
      if(plan_conflict){response(r,409,"{}");return 1;}
      memcpy(saved_plan,q->body,strlen(q->body)+1);saved_revision=8;
      if(plan_lose_ack){plan_lose_ack=0;r->transport_error=1;}else response(r,200,"{\"revision\":8}");
    }else{char data[10500];plan_gets++;snprintf(data,sizeof(data),"{\"revision\":%u,\"plan\":%s}",saved_revision,saved_plan);response(r,200,data);}
    return 1;
  }
  if(zero_fixture&&strstr(q->path,"/recording/header")){char header[600];recording_header(header,sizeof(header),0);response(r,200,header);return 1;}
  if(zero_fixture&&strstr(q->path,"/events")){response(r,200,"[{\"at_ms\":0,\"game_second\":0,\"kind\":\"KICKOFF\",\"side\":\"HOME\"}]");return 1;}
  if(bundle_fixture&&strstr(q->path,"/playback")){
    char data[18000],header[600];recording_header(header,sizeof(header),0);recording_gets++;
    size_t n=(size_t)snprintf(data,sizeof(data),"{\"playback_policy\":\"FULL_RECORDING\",\"header\":%s,\"chunks\":[",header);
    for(unsigned i=0;i<22;i++)n+=(size_t)snprintf(data+n,sizeof(data)-n,"%s{\"index\":%u,\"frames\":[{\"at_ms\":%u,\"bx\":20000,\"by\":34000,\"h\":[{\"x\":10000,\"y\":34000}],\"a\":[{\"x\":95000,\"y\":34000}]}]}",i?",":"",i,i*30000+(i==12?1000:0));
    snprintf(data+n,sizeof(data)-n,"],\"events\":[{\"at_ms\":190000,\"game_second\":1710,\"kind\":\"GOAL\",\"side\":\"HOME\",\"actor_name\":\"Alpha\"},{\"at_ms\":210000,\"game_second\":1890,\"kind\":\"GOAL\",\"side\":\"AWAY\",\"actor_name\":\"Future scorer\"}]}");
    response(r,200,data);return 1;
  }
  return 0;
}
static void own_plan_flow(int error){
  login();plan_fixture=1;online.player_count=18;
  for(unsigned i=0;i<18;i++){
    MoPlayer *p=&online.players[i];p->instance=i+101;snprintf(p->key,sizeof(p->key),"ef:%u",i+1);snprintf(p->row.label,sizeof(p->row.label),"Player %u",i+1);
    p->row.role=i==0||i==11?0:1;p->row.rating=68;online.plan.ids[i]=p->instance;
  }
  plan_formation(0);online.plan.auto_subs=1;online.plan_revision=7;assert(plan_encode(saved_plan,sizeof(saved_plan)));
  get(J_PLAN,"/club/gameplan");idle();assert(!online.plan_dirty&&online.page==MD_CLUB_PLAN&&plan_gets==1);
  MdView v;manager_online_view(&v);assert(v.plan_editable&&!v.plan_pending&&v.helper_count==4&&!strcmp(v.helper_key[3],"ZL")&&online.plan_focus==MO_PLAYERS);
  manager_online_pad(UP);assert(online.plan_focus==MO_PLAYERS+3);
  manager_online_pad(RIGHT);assert(online.plan_focus==MO_PLAYERS);
  manager_online_pad(A);assert(online.plan_focus==0);
  manager_online_pad(B);assert(online.plan_focus==MO_PLAYERS);
  manager_online_pad(B);assert(online.page==MD_DASHBOARD&&!plan_puts);
  get(J_PLAN,"/club/gameplan");idle();
  online.plan_focus=0;manager_online_pad(A);online.plan_focus=12;manager_online_pad(A);
  assert(online.notice[0]&&online.plan.ids[0]==101&&!online.plan_dirty);manager_online_pad(A);
  online.plan_focus=1;manager_online_pad(A);online.plan_focus=12;manager_online_pad(A);
  assert(online.plan.ids[1]==113&&online.plan.ids[12]==102&&online.plan_dirty&&!plan_puts);
  online.plan_focus=1;uint32_t before=online.plan.x[1];manager_online_pad(X);assert(!online.plan_move&&online.page==MD_PLAN_RESERVES);manager_online_pad(B);
  manager_online_sample(A,A,0,0);assert(online.plan_move==2&&online.plan_pick==UINT32_MAX);
  online.mono+=219;manager_online_sample(A|UP,UP,0,0);assert(online.plan_move==2&&online.plan_focus==1&&online.plan.x[1]==before);
  online.mono++;manager_online_sample(A|UP,0,0,0);assert(online.plan_move==1);
  for(unsigned i=0;i<10;i++){online.mono+=16;manager_online_sample(A|UP,UP,0,0);}
  manager_online_sample(0,0,0,0);assert(online.plan.x[1]>before&&!online.plan_move&&!plan_puts&&online.plan_focus==1);
  manager_online_sample(A,A,0,0);online.mono+=100;manager_online_sample(0,0,0,0);assert(online.plan_pick==1&&!online.plan_move);
  manager_online_sample(A,A,0,0);manager_online_sample(B,B,0,0);assert(!online.plan_move&&online.plan_pick==1);
  manager_online_sample(0,0,0,0);manager_online_pad(B);assert(online.plan_pick==UINT32_MAX);
  manager_online_pad(R);assert(online.plan_condition);manager_online_pad(R);assert(!online.plan_condition);
  manager_online_pad(B);assert(online.plan_focus==MO_PLAYERS);
  manager_online_pad(LEFT);manager_online_pad(A);assert(online.page==MD_PLAN_SETTINGS&&online.plan_menu==3);
  manager_online_pad(RIGHT);assert(!online.plan_picker);manager_online_pad(A);manager_online_view(&v);
  assert(v.total==11&&strcmp(v.plan_rows[0].label,"NONE"));manager_online_pad(A);assert(online.plan.duties[0]==101);
  for(unsigned i=0;i<6;i++)manager_online_pad(DOWN);
  manager_online_pad(A);manager_online_view(&v);
  assert(v.total==11&&!strcmp(v.plan_rows[0].label,"NONE"));
  for(unsigned i=1;i<plan_picker_count();i++)assert(plan_picker_id(i)!=101);
  manager_online_pad(DOWN);manager_online_pad(A);assert(online.plan.duties[6]==online.plan.ids[1]);
  manager_online_pad(B);manager_online_pad(LEFT);manager_online_pad(LEFT);manager_online_pad(A);
  assert(online.page==MD_PLAN_SETTINGS);manager_online_pad(DOWN);manager_online_pad(A);assert(online.plan_picker);
  manager_online_pad(DOWN);manager_online_pad(A);assert(!online.plan_picker);
  manager_online_pad(DOWN);manager_online_pad(A);assert(online.plan.offside);
  manager_online_pad(DOWN);manager_online_pad(A);assert(!online.plan.auto_subs);manager_online_pad(B);
  assert(online.page==MD_CLUB_PLAN&&online.plan.formation==1&&!plan_puts);
  plan_lose_ack=error==1;plan_conflict=error==2;manager_online_pad(B);idle();
  assert(plan_puts==1&&strstr(put_plan,"\"expected_revision\":7")&&strstr(put_plan,"\"formation\":\"4-2-3-1\""));
  if(error==1){
    assert(online.page==MD_CLUB_PLAN&&online.plan_dirty&&online.plan_save_pending&&online.notice[0]);
    manager_online_pad(A);manager_online_pad(B);idle();assert(plan_puts==2); /* Exact UUID and body asserted in transport. */
  }else if(error==2){
    assert(online.page==MD_CLUB_PLAN&&online.plan_dirty&&online.plan_save_pending&&online.notice[0]);
    manager_online_pad(A);manager_online_pad(X);manager_online_pad(A);assert(!online.plan_discard&&online.plan_dirty); /* Cancel. */
    manager_online_pad(X);manager_online_pad(LEFT);manager_online_pad(A);idle();assert(!online.plan_dirty&&!online.plan_save_pending&&online.plan.formation==0);
    manager_online_pad(B);assert(plan_puts==1);
  }
  assert(online.page==MD_DASHBOARD&&!online.plan_dirty&&!online.plan_save_pending&&!online.plan_key[0]);
}
static void zero_watch(void){
  fake_test=zero_fixture=1;fake_now=1700000000000;login();
  MoMatch m={.id=7,.phase=1,.kickoff=1700000000000};change_page(MD_SCHEDULE);watch_open(&m);idle();
  MdView v;manager_online_view(&v);assert(v.watch_ready&&!online.notice[0]&&online.chunks[0].valid&&!online.watermark);
  host_ms+=16000;idle();manager_online_view(&v);assert(v.watch_ready&&online.watch_stalled&&strstr(v.empty_detail,"TEST CLOCK IS PAUSED"));
  manager_online_pad(B);assert(online.page==MD_SCHEDULE);
}
static void bundle_watch(void){
  login();online.bundle_capable=bundle_fixture=1;MoMatch m={.id=7,.phase=1,.kickoff=1700000000000,.row={.badge=2,.away_badge=3}};
  copy(m.home,sizeof(m.home),"Alpha FC");copy(m.away,sizeof(m.away),"Beta FC");change_page(MD_SCHEDULE);watch_open(&m);idle();
  MdView v;manager_online_view(&v);assert(online.bundle_ready&&v.watch_ready&&v.home_goals==1&&!v.away_goals&&v.touchline_total==1&&v.home_badge==2&&v.away_badge==3);
  assert(recording_gets==1&&watch_gets==1);for(unsigned i=0;i<22;i++)assert(online.chunks[i].valid);
  manager_online_pad(X);idle();assert(watch_gets==1);manager_online_pad(B);
  host_ms+=11000;idle();manager_online_view(&v);assert(v.away_goals==1&&watch_gets==1);
  online.replay=1;online.paused=1;online.play_ms=0;manager_online_view(&v);assert(!v.home_goals&&!v.away_goals&&!v.touchline_total&&v.watch_ready);
  online.play_ms=360000;manager_online_view(&v);assert(v.watch_ready); /* Half-time boundary with no exact frame. */
  online.play_ms=659999;manager_online_view(&v);assert(v.watch_ready&&v.home_goals==1&&v.away_goals==1&&watch_gets==1);
  manager_online_pad(B);assert(online.page==MD_SCHEDULE);
}
static void presentation_data(void){
  login();json("[{\"club_id\":84,\"presentation_team_id\":108,\"club_name\":\"Synthetic FC\",\"played\":1,\"won\":1,\"drawn\":0,\"lost\":0,\"goals_for\":2,\"goals_against\":0,\"league_points\":3},{\"club_id\":900,\"presentation_team_id\":101,\"club_name\":\"Rival FC\",\"league_points\":0}]");
  assert(parse_rows(&doc,0,J_STANDINGS)&&online.row_count==2&&online.rows[0].selected&&!online.rows[1].selected);
  assert(online.rows[0].badge==exhibition_team_catalog_badge(108)&&online.rows[1].team_id==900&&online.rows[1].badge==exhibition_team_catalog_badge(101));
  online.standing_count=2;memcpy(online.standings,online.rows,sizeof(online.rows));
  json("[{\"id\":8,\"home_club_id\":84,\"away_club_id\":900,\"home_presentation_team_id\":108,\"away_presentation_team_id\":101,\"home_club_name\":\"Synthetic FC\",\"away_club_name\":\"Rival FC\",\"kickoff_ms\":1700000000000,\"round_number\":1,\"state\":\"ENDED\",\"home_goals\":2,\"away_goals\":1}]");
  assert(parse_matches(&doc,0));MdView v;manager_online_view(&v);assert(v.table_preview_count==2&&online.match_count==1&&online.matches[0].row.away_badge==exhibition_team_catalog_badge(101));
  assert(strstr(online.matches[0].row.detail,"WIB")&&!strcmp(online.matches[0].row.value,"2 - 1"));
  online.tab=1;manager_online_view(&v);assert(!strcmp(v.rows[0].label,"GAME PLAN"));
  online.tab=2;manager_online_view(&v);assert(v.count==4&&!strcmp(v.rows[0].label,"LEAGUE RANKING HISTORY"));
  json("[{\"account_id\":42,\"club_name\":\"Synthetic FC\",\"ranking_points\":8000},{\"account_id\":84,\"club_name\":\"Synthetic FC\",\"ranking_points\":2}]");
  assert(parse_rows(&doc,0,J_RANKING)&&online.rows[0].team_id==84&&online.rows[0].badge==exhibition_team_catalog_badge(108)&&online.rows[0].selected&&!online.rows[1].team_id&&!online.rows[1].selected&&!strcmp(online.rows[0].value,"8000 RP"));
  online.ranking_count=online.row_count;memcpy(online.rankings,online.rows,sizeof(online.rows));
  online.page=MD_CLUB_PROFILE;manager_online_view(&v);assert(v.club_rank==1&&!v.rank&&!v.season_label[0]); /* Legacy RP is not monthly points. */
  online.opponent=1;online.opponent_team=101;copy(online.opponent_name,sizeof(online.opponent_name),"Rival FC");online.page=MD_CLUB_PLAN;manager_online_view(&v);
  assert(!v.plan_editable&&v.helper_count==2&&v.badge==exhibition_team_catalog_badge(101)&&!strcmp(v.headline,"Rival FC"));online.opponent=0;
  json("[{\"id\":8,\"home_club_id\":84,\"away_club_id\":900,\"home_presentation_team_id\":108,\"away_presentation_team_id\":101,\"kickoff_ms\":1700000000000,\"state\":\"ENDED\"}]");
  online.phase[0]=0;copy(online.phase,sizeof(online.phase),"REGISTRATION");online.joined=0;online.page=MD_DASHBOARD;online.tab=online.focus=0;
  assert(parse_matches(&doc,0)&&online.calendar_conflict);manager_online_pad(A);idle();assert(online.page==MD_SCHEDULE&&!join_posts);
  online.page=MD_TEAMS_PAGE;manager_online_pad(Y);idle();assert(online.page==MD_TEAMS_PAGE);
  online.page=MD_TABLE;online.row_count=0;manager_online_view(&v);assert(!v.count&&v.summary[0]&&v.empty_detail[0]);
}

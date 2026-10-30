/* Synthetic controller and wire-contract regressions for the revised hub. */
static void hub_flow(void){
  fake_test=1;login();MdView v;
  online.phase_started=server_now()-1000;online.phase_ends=server_now()+72840000;
  online.registration_close=online.phase_ends;manager_online_view(&v);
  assert(!strcmp(v.rows[0].label,"REGISTRATION DAY W1")&&!strcmp(v.rows[0].detail,"ENDS IN 20H 14M")&&strstr(v.rows[0].value,"NOT REGISTERED"));
  manager_online_pad(A);manager_online_view(&v);assert(online.join_confirm&&v.modal.open&&!v.modal.information&&v.modal.selected==1&&!join_posts);
  manager_online_pad(A);assert(!online.join_confirm&&!join_posts); /* Default Cancel. */
  manager_online_pad(A);manager_online_pad(B);assert(!online.join_confirm&&!join_posts);
  manager_online_pad(A);manager_online_pad(LEFT);manager_online_pad(A);idle();assert(join_posts==1&&online.joined&&online.cash==6500);
  manager_online_pad(A);manager_online_view(&v);assert(v.modal.information&&!online.join_confirm&&join_posts==1);manager_online_pad(A);assert(!online.notice[0]&&join_posts==1);
  online.focus=3;manager_online_pad(A);assert(online.notice[0]&&online.page==MD_DASHBOARD);manager_online_pad(A);
  copy(online.phase,sizeof(online.phase),"PREPARATION");online.focus=0;manager_online_pad(A);manager_online_view(&v);assert(v.modal.information&&strstr(v.modal.body,"Game Plan"));manager_online_pad(A);
  online.tab=1;online.focus=1;manager_online_pad(A);assert(online.notice[0]&&online.page==MD_DASHBOARD);manager_online_pad(A);
  manager_online_view(&v);assert(v.count==4&&!strcmp(v.rows[2].label,"SHOP")&&!strcmp(v.rows[3].label,"TRADE HISTORY"));
  manager_online_pad(DOWN);assert(online.focus==3);manager_online_pad(A);manager_online_view(&v);assert(v.modal.information&&strstr(v.modal.title,"UPCOMING"));manager_online_pad(A);
  online.tab=2;online.focus=0;manager_online_view(&v);assert(v.count==4&&!strcmp(v.rows[2].label,"LOGOUT")&&!strcmp(v.rows[3].label,"LEAGUE GUIDE"));
  manager_online_pad(DOWN);assert(online.focus==2);manager_online_pad(RIGHT);assert(online.focus==3);manager_online_pad(A);assert(online.page==MD_RULES);manager_online_pad(B);manager_online_pad(LEFT);assert(online.focus==2);
  manager_online_pad(A);assert(online.page==MD_LOGOUT);manager_online_pad(B);assert(online.page==MD_DASHBOARD&&online.focus==2&&online.tab==2);
  copy(online.phase,sizeof(online.phase),"MATCH_DAY");online.tab=0;online.focus=0;manager_online_pad(A);idle();assert(online.page==MD_SCHEDULE);
  manager_online_pad(B);copy(online.phase,sizeof(online.phase),"SETTLED");manager_online_pad(A);idle();assert(online.page==MD_SCHEDULE);
  manager_online_pad(B);copy(online.phase,sizeof(online.phase),"REGISTRATION");online.joined=0;online.registration_close=server_now()+1000;
  manager_online_pad(A);manager_online_pad(LEFT);online.mono+=2000;manager_online_pad(A);idle();assert(join_posts==1); /* Expired consent cannot join again. */
}
static void hub_calendar_and_navigation(void){
  MdView v={0};char text[64];
  uint64_t monday=1793552400000ULL; /* 2026-11-02 00:00 WIB. */
  md_hub_calendar(&v,monday);assert(v.count==7&&v.rows[0].selected&&strstr(v.rows[0].label,"02 Nov 2026")&&strstr(v.rows[6].label,"08 Nov 2026"));
  for(unsigned day=0;day<7;day++){
    md_hub_calendar(&v,monday+day*86400000ULL+123000);
    unsigned marked=0;for(unsigned j=0;j<7;j++)marked+=v.rows[j].selected;
    assert(marked==1&&v.rows[day].selected&&strstr(v.rows[day].value,day<3?"W1":"W2"));
  }
  md_hub_calendar(&v,monday-1);assert(v.rows[6].selected&&strstr(v.rows[0].label,"26 Oct 2026"));
  md_hub_countdown(text,sizeof(text),1000,0);assert(!strcmp(text,"TIME TO BE CONFIRMED"));
  md_hub_countdown(text,sizeof(text),1000,1000);assert(!strcmp(text,"UPDATING PHASE..."));
  md_hub_countdown(text,sizeof(text),1000,1001);assert(!strcmp(text,"ENDS IN 0H 01M"));
  md_hub_fill(&v,MH_UNKNOWN,monday,0,"");assert(strstr(v.rows[0].value,"PENDING"));
  const uint32_t keys[]={UP,DOWN,LEFT,RIGHT,L,R};
  for(unsigned tab=0;tab<3;tab++)for(unsigned focus=0;focus<(tab?4u:5u);focus++)for(unsigned k=0;k<6;k++){
    uint32_t t=tab,f=focus;md_hub_navigate(keys[k],&t,&f);assert(t<3&&f<(t?4u:5u));
  }
  uint32_t t=0,f=4;md_hub_navigate(RIGHT,&t,&f);assert(t==1&&f==2);
  md_hub_navigate(RIGHT,&t,&f);assert(t==1&&f==3);
  md_hub_navigate(RIGHT,&t,&f);assert(t==2&&f==2);
  md_hub_navigate(LEFT,&t,&f);assert(t==1&&f==3);
  md_hub_navigate(LEFT,&t,&f);md_hub_navigate(LEFT,&t,&f);assert(t==0&&f==4);
  login();online.page=MD_DASHBOARD;online.focus=2;manager_online_pad(A);manager_online_view(&v);assert(v.page==MD_WEEK_SCHEDULE&&v.count==7);
  for(unsigned i=0;i<10;i++)manager_online_pad(DOWN);
  manager_online_view(&v);assert(v.focus==6);
  manager_online_pad(A);assert(online.page==MD_WEEK_SCHEDULE);manager_online_pad(B);assert(online.page==MD_DASHBOARD&&online.focus==2);
}
static void hub_feed_data(void){
  login();json("{\"items\":[{\"type\":\"PLAYER_SIGNED\",\"league_label\":\"W1\",\"occurred_at_ms\":1700000000000,\"parameters\":{\"club_id\":84,\"presentation_team_id\":108,\"club_name\":\"Alpha FC\",\"player_key\":\"ef:1\",\"player_name\":\"Alpha Player\"}},{\"type\":\"MATCH_RESULT\",\"occurred_at_ms\":1700000100000,\"parameters\":{\"home_club_name\":\"Alpha FC\",\"away_club_name\":\"Beta FC\",\"home_presentation_team_id\":108,\"away_presentation_team_id\":101,\"home_goals\":2,\"away_goals\":1}},{\"type\":\"LEAGUE_LEADER\",\"occurred_at_ms\":1700000110000,\"parameters\":{\"club_name\":\"Alpha FC\",\"presentation_team_id\":108,\"league_points\":3}},{\"type\":\"MATCH_RESULT\",\"occurred_at_ms\":1900000000000,\"parameters\":{}}]}");
  assert(parse_rows(&doc,0,J_NEWS)&&online.activity_count==3&&online.news_count==3);
  assert(!strcmp(online.activity[0].row.label,"LEAGUE LEADER")&&strstr(online.activity[0].body,"3 League Points"));
  assert(strstr(online.activity[1].body,"2 - 1")&&online.activity[1].row.away_badge==exhibition_team_catalog_badge(101));
  assert(strstr(online.activity[2].body,"Alpha Player")&&online.activity[2].row.identity==1&&online.activity[2].row.portrait==901);
  online.page=MD_NEWS;MdView v;manager_online_view(&v);assert(v.count==3&&v.feed[2].context[0]);
  json("{\"items\":[]}");assert(parse_club_feed(&doc,0)&&!online.activity_count&&!online.news_count);
  json("null");assert(parse_club_feed(&doc,0));
  json("{\"cycle_id\":1,\"published_through_ms\":1700000000000,\"top_scorers\":[{\"player_key\":\"ef:1\",\"player_name\":\"Alpha Player\",\"club_name\":\"Alpha FC\",\"presentation_team_id\":108,\"snapshot_ovr\":68,\"goals\":2,\"assists\":1}],\"rising_stars\":[{\"player_key\":\"ef:1\",\"player_name\":\"Alpha Player\",\"club_name\":\"Alpha FC\",\"presentation_team_id\":108,\"snapshot_ovr\":68,\"goals\":2,\"assists\":1}]}");
  assert(parse_player_feed(&doc,0)&&online.player_feed_count[0]==1&&online.player_feed_count[1]==1);
  online.page=MD_PLAYER_FEED;manager_online_view(&v);assert(v.count==1&&v.feed[0].row.portrait==901);
  assert(v.feed[0].goals==2&&v.feed[0].assists==1&&v.feed[0].assists_known&&!strcmp(v.feed[0].body,"Alpha FC"));
  manager_online_pad(R);manager_online_view(&v);assert(v.feed_section==1&&strstr(v.feed[0].context,"RISING STAR"));
  json("{\"cycle_id\":2,\"published_through_ms\":1700000000000,\"top_scorers\":[],\"rising_stars\":[]}");assert(!parse_player_feed(&doc,0)&&online.player_feed_count[0]==1);
  json("{\"cycle_id\":1,\"published_through_ms\":1900000000000,\"top_scorers\":[],\"rising_stars\":[]}");assert(!parse_player_feed(&doc,0));
  json("{\"cycle_id\":1,\"published_through_ms\":1700000000000,\"top_scorers\":[],\"rising_stars\":[{\"player_key\":\"ef:1\",\"player_name\":\"Alpha Player\",\"club_name\":\"Alpha FC\",\"snapshot_ovr\":70,\"goals\":2,\"assists\":1}]}");assert(!parse_player_feed(&doc,0));
  json("{\"cycle_id\":1,\"published_through_ms\":1700000000000,\"top_scorers\":[],\"rising_stars\":[]}");assert(parse_player_feed(&doc,0)&&!online.player_feed_count[0]);
  online.page=MD_DASHBOARD;online.tab=1;online.focus=1;copy(online.phase,sizeof(online.phase),"MATCH_DAY");unsigned before=calls;manager_online_pad(A);assert(online.notice[0]&&calls==before); /* No advertised capability: no speculative request. */
  manager_online_pad(A);online.player_feed_capable=1;manager_online_pad(A);idle();assert(online.page==MD_PLAYER_FEED);manager_online_view(&v);assert(!v.count&&v.empty_detail[0]);
}

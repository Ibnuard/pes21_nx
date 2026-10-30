static void routes_v115(void){
  login();online.tab=0;online.focus=3;change_page(MD_TABLE);online.focus=2;
  get(J_PROFILE,"/club/profile");idle();assert(online.page==MD_CLUB_PROFILE);
  manager_online_pad(B);idle();assert(online.page==MD_TABLE&&online.focus==2);
  manager_online_pad(B);assert(online.page==MD_DASHBOARD&&online.focus==3);
  online.tab=0;online.focus=3;change_page(MD_TABLE);online.focus=2;
  online.opponent=1;online.opponent_id=900;change_page(MD_OPPONENT_PROFILE);online.focus=1;
  change_page(MD_CLUB_PLAN);assert(online.route_count==3);
  /* A failed asynchronous Back keeps the path and current opponent intact. */
  online.route_restore=1;online.route_origin=(MoRoute){MD_CLUB_PLAN,0,1,900};
  message("CONNECTION INTERRUPTED","synthetic failure");assert(online.route_count==3&&!online.route_restore&&online.opponent_id==900);
  online.notice[0]=0;online.route_restore=1;online.route_focus=1;change_page(MD_OPPONENT_PROFILE);
  assert(online.route_count==2&&online.focus==1);
  manager_online_pad(B);idle();assert(online.page==MD_TABLE&&online.focus==2);
  manager_online_pad(B);assert(online.page==MD_DASHBOARD&&online.tab==0&&online.focus==3);
}
static void history_v115(void){
  login();online.history_request=2;online.history_snapshot=1234;online.match_count=1;online.matches[0].id=77;
  const char *wire="{\"page\":2,\"page_size\":5,\"total\":6,\"snapshot_id\":1234,\"items\":[{\"fixture_id\":10,\"cycle_id\":99,\"home_club_id\":84,\"away_club_id\":900,\"state\":\"ENDED\",\"home_goals\":2,\"away_goals\":1}]}";
  json(wire);assert(parse_history(&doc,0)&&online.history_page==2&&online.history_count==1&&online.history_total==6);
  assert(online.match_count==1&&online.matches[0].id==77);
  online.history_snapshot=9999;json(wire);assert(!parse_history(&doc,0)&&online.history_matches[0].id==10);
  online.page=MD_TEAM_HISTORY;online.focus=0;MdView v;manager_online_view(&v);
  assert(v.first==5&&v.count==1&&v.total==6&&!strcmp(v.helper_key[1],"L")&&!strcmp(v.helper_key[2],"R"));
  /* SAVE belongs to the keeper; the opposing side gets the shot on target. */
  online.event_count=1;online.events[0]=(MoEvent){.kind=MD_SAVE,.side=1,.at=0};online.page=MD_WATCH;online.duration=660000;
  manager_online_view(&v);assert(v.shots[0]==1&&v.on_target[0]==1&&!v.shots[1]);
}
static void offers_v115(void){
  login();shop();online.offers[0].available=0;copy(online.offers[0].unavailable,sizeof(online.offers[0].unavailable),"CATALOG_NOT_READY");
  manager_online_pad(A);assert(online.page==MD_SHOP&&online.notice[0]&&!payments&&!online.pay_uncertain);
  manager_online_pad(A);online.offers[0].available=1;pay();assert(payments==1);
}

static void shop_clubs_v116(void){
 login();shop();MoOffer base=online.offers[0];
 online.offer_count=6;for(unsigned i=0;i<6;i++){online.offers[i]=base;online.offers[i].id=100+i;online.offers[i].team=i%2?108:100;online.offers[i].price=1000+i*100;}
 online.page=MD_SHOP_CLUBS;online.shop_focus=0;MdView v;manager_online_view(&v);
 assert(v.count==2&&v.rows[0].team_id==100&&v.rows[1].team_id==108&&!strcmp(v.headline,"CHOOSE CLUB PACK"));
 manager_online_pad(RIGHT);manager_online_pad(A);assert(online.page==MD_SHOP&&online.shop_team==108&&online.offer_focus==1);
 manager_online_view(&v);assert(v.count==3&&v.rows[0].team_id==108&&v.rows[2].team_id==108);
 manager_online_pad(RIGHT);assert(online.offer_focus==3);manager_online_pad(A);assert(online.page==MD_PACK&&!payments);
 manager_online_pad(B);assert(online.page==MD_SHOP&&online.offer_focus==3);manager_online_pad(B);assert(online.page==MD_SHOP_CLUBS&&online.shop_focus==1);
 manager_online_pad(B);assert(online.page==MD_DASHBOARD&&!payments);
}

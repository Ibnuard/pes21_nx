/* Local choice, owned reserves, bounded reads and screen-space drag regressions. */
static int v117_fixture;
static unsigned v117_collection_gets;
static char v117_collection[18000];
static int v117_http(const MoHttpRequest *q,MoHttpResponse *r){
  if(!v117_fixture)return 0;
  if(!strcmp(q->path,"/club/collection")){v117_collection_gets++;response(r,200,v117_collection);return 1;}
  if(!strcmp(q->path,"/club/gameplan")&&!strcmp(q->method,"PUT")){
    plan_puts++;assert(strlen(q->body)<sizeof(saved_plan));memcpy(saved_plan,q->body,strlen(q->body)+1);saved_revision++;
    char data[11000];snprintf(data,sizeof(data),"{\"revision\":%u,\"plan\":%s}",saved_revision,saved_plan);response(r,200,data);return 1;
  }
  return 0;
}
static void v117_setup(void){
  login();v117_fixture=plan_fixture=1;online.player_count=26;
  size_t used=0;v117_collection[used++]='[';
  for(unsigned i=0;i<26;i++){
    MoPlayer *p=&online.players[i];p->instance=101+i;snprintf(p->key,sizeof(p->key),"ef:%u",i+1);
    snprintf(p->row.label,sizeof(p->row.label),"Player %u",i+1);p->row.role=i==0||i==11?0:1;p->row.rating=68;
    if(i<18)online.plan.ids[i]=p->instance;
    used+=(size_t)snprintf(v117_collection+used,sizeof(v117_collection)-used,"%s{\"instance_id\":%llu,\"player_key\":\"%s\",\"display_name\":\"%s\",\"position\":\"%s\",\"display_ovr\":68,\"origin\":\"%s\",\"acquired_at\":\"2026-10-%02uT12:00:00Z\"}",i?",":"",(unsigned long long)p->instance,p->key,p->row.label,role_names[p->row.role],i>=18?"PACK":"STARTER",i+1);
  }
  snprintf(v117_collection+used,sizeof(v117_collection)-used,"]");
  plan_formation(0);online.plan_revision=7;assert(plan_encode(saved_plan,sizeof(saved_plan)));
}
static void local_selection_v117(void){
  v117_setup();shop();pay();manager_online_tick(host_ms+=MD_PACK_OPEN_MS+1);
  unsigned before=http_calls;manager_online_pad(A);manager_online_pad(RIGHT);manager_online_pad(A);
  assert(online.selected==3&&!fake_selected&&http_calls==before&&!online.busy&&!nx_loading_active());
  manager_online_pad(Y);idle();assert(online.page==MD_PURCHASE_HISTORY&&v117_collection_gets==1&&online.selected==3);
  MdView v;manager_online_view(&v);assert(v.total==8&&v.count==5&&!strcmp(v.rows[0].label,"Player 26"));
  manager_online_pad(R);manager_online_view(&v);assert(v.first==5&&v.count==3);manager_online_pad(L);
  manager_online_pad(B);assert(online.page==MD_PACK_SELECT&&online.focus==1&&online.selected==3);
  before=http_calls;manager_online_pad(Y);idle();manager_online_pad(B);assert(http_calls==before&&online.selected==3);
  manager_online_pad(DOWN);manager_online_pad(DOWN);manager_online_pad(A);idle();
  assert(http_calls==before+1&&grants==1&&online.page==MD_PACK_RESULT&&payments==1);
  manager_online_pad(A);idle();manager_online_pad(Y);idle();assert(v117_collection_gets==2); /* Grant invalidates ownership. */
}
static void reserves_v117(void){
  v117_setup();open_squad(1);idle();assert(online.page==MD_CLUB_PLAN&&online.player_count==26&&plan_gets==1&&v117_collection_gets==1);
  manager_online_pad(A);online.plan_focus=12;unsigned before=http_calls;
  manager_online_pad(X);assert(online.page==MD_PLAN_RESERVES);
  MdView v;manager_online_view(&v);assert(v.total==8&&v.count==5&&!strcmp(v.rows[0].label,"Player 19"));
  manager_online_pad(A);assert(online.page==MD_CLUB_PLAN&&online.plan.ids[12]==119&&online.plan_dirty&&http_calls==before);
  manager_online_pad(B);manager_online_pad(B);idle();
  assert(plan_puts==1&&plan_gets==1&&http_calls==before+1&&!online.plan_dirty&&!online.plan_save_pending);
  before=http_calls;open_squad(1);idle();assert(http_calls==before&&online.plan.ids[12]==119&&online.player_count==26);
  manager_online_pad(B);assert(plan_puts==1);
  /* New outfield purchases cannot replace the only keeper. */
  open_squad(1);idle();manager_online_pad(A);online.plan_focus=0;manager_online_pad(X);manager_online_pad(A);
  assert(online.notice[0]&&online.plan.ids[0]==101&&!online.plan_dirty);
}
static void analog_drag_v117(void){
  v117_setup();open_squad(1);idle();manager_online_pad(A);online.plan_focus=1;
  const int axes[6][3]={{UP,0,-24000},{UP,0,24000},{DOWN,0,24000},{DOWN,0,-24000},{LEFT,-24000,0},{RIGHT,24000,0}};
  unsigned before=http_calls;
  for(unsigned n=0;n<6;n++){
    float x=online.plan_dots[1].x,y=online.plan_dots[1].y;
    manager_online_sample(A,A,0,0);online.mono+=220;manager_online_sample(A,0,0,0);
    for(unsigned i=0;i<10;i++){online.mono+=16;manager_online_sample(A|axes[n][0],0,axes[n][1],axes[n][2]);}
    manager_online_sample(0,0,0,0);
    if(n<2)assert(online.plan_dots[1].y<y);
    else if(n<4)assert(online.plan_dots[1].y>y);
    else if(n==4)assert(online.plan_dots[1].x<x);
    else assert(online.plan_dots[1].x>x);
    assert(!online.plan_move&&online.plan_focus==1&&http_calls==before);
  }
}
static void read_cache_v117(void){
  v117_setup();get(J_COLLECTION,"/club/collection");idle();assert(v117_collection_gets==1);
  uint64_t anchor=online.server_anchor;host_ms+=1000;idle();uint64_t now=server_now();
  get(J_COLLECTION,"/club/collection");assert(!online.modal_busy&&!nx_loading_active());idle();
  assert(v117_collection_gets==1&&online.server_anchor==anchor&&server_now()>=now);
  host_ms+=120001;idle();get(J_COLLECTION,"/club/collection");idle();assert(v117_collection_gets==2);
  set_cache_scope(43,2);assert(!read_cache_get(J_COLLECTION,"/club/collection"));
  get(J_COLLECTION,"/club/collection");idle();assert(v117_collection_gets==3);
  auth_clear();assert(!read_cache_get(J_COLLECTION,"/club/collection"));
}
static void promotion_amount_v117(void){
  promo_enabled=1;login();promo_enter("ABCD1234EFGH5678");MdView v;manager_online_view(&v);
  for(unsigned i=0;i<v.count;i++)assert(!strstr(v.rows[i].value,"5000")&&!strstr(v.rows[i].detail,"5,000"));
  copy(online.promo_intent.key,sizeof(online.promo_intent.key),"00000000-0000-4000-8000-000000000001");
  MoResult result={.generation=generation,.kind=J_PROMO};response(&result.http,200,"{\"state\":\"SUCCEEDED\",\"redemption_id\":1,\"environment\":\"PRODUCTION\",\"account_id\":42,\"idempotency_key\":\"00000000-0000-4000-8000-000000000001\",\"currency\":\"NX_CASH\",\"amount\":2500,\"wallet\":{\"balance\":7500,\"version\":3}}");
  unsigned before=http_calls;consume(&result);mo_http_free(&result.http);
  assert(online.cash==7500&&strstr(online.notice,"2500 NX Cash")&&!online.busy&&http_calls==before);
}

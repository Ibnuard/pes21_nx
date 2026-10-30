/* Synthetic wire fixtures only. No production accounts, player data or calls. */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
static int fail_payment_rename;
static int test_rename(const char *a,const char *b){if(fail_payment_rename&&strstr(a,"manager-online-pay")){errno=EIO;return -1;}return rename(a,b);}
#define rename test_rename
#include "manager_league_online.c"
#undef rename
#include "manager_dev_shortcut.h"

static uint64_t host_ms=1000;
static unsigned http_calls;
static unsigned calls,logins,refreshes,payments,grants;
static unsigned monthly_calls,schedule_calls;
static void monthly_mock(const MoHttpRequest *request,MoHttpResponse *response);
static int reject_pool;
static int pending_pack,lose_payment,payment_not_committed,delay_header;
static int wrong_version,collection_401,collection_reads;
static int lose_selection_response,lose_grant_response;
static int fake_test,promo_enabled,missing_test_context,bootstrap_wrong_realm;
static int no_bootstrap_league,closed_registration;
static int lose_clock_reply,lose_promo_reply,promo_not_committed,bad_promo_receipt,hold_clock_running;
static unsigned clock_posts,clock_applied,clock_reads,promo_posts,promo_credits,join_posts;
static uint32_t fake_clock_revision=1,fake_wallet_revision=2;
static uint64_t fake_now=1700000200000;
static uint32_t clock_final_revision;static uint64_t clock_final_now;
static char clock_key[37],clock_body[256],promo_key[37],promo_body[256];
static char payment_key[37],payment_body[256];
static int v117_http(const MoHttpRequest *q,MoHttpResponse *r);
static int extended_http(const MoHttpRequest *q,MoHttpResponse *r);
static int receipt_completed;
static const char *login_user="synthetic_qa";
static uint32_t fake_revision=1,fake_selected;
static uint64_t fake_cash=5000;
static const char fake_access[]="synthetic-access-not-a-real-token";
static const char fake_refresh[]="synthetic-refresh-not-a-real-token";
const char *ml_catalog_pair_id(void){return MANAGER_ONLINE_PAIR;}
const char *ml_catalog_manager_binding_id(void){return "synthetic-paired-binding";}
const MlCatalogPlayer *ml_catalog_find_identity(uint32_t id){static const MlCatalogPlayer binding={.identity=1,.native_id=91,.portrait_id=901};return id==1?&binding:NULL;}
void mo_wipe(void *p,size_t n){volatile unsigned char *b=p;while(n--)*b++=0;}
int mo_random_key(char out[37]){snprintf(out,37,"00000000-0000-4000-8000-%012u",++calls);return 1;}
void mo_http_free(MoHttpResponse *r){free(r->body);memset(r,0,sizeof(*r));}
static void response(MoHttpResponse *r,int status,const char *data){
  size_t n=strlen(data)+256;r->body=malloc(n);assert(r->body);
  snprintf(r->body,n,"{\"data\":%s,\"meta\":{\"environment\":\"%s\",\"server_now_ms\":%llu,\"online_version\":\"1.0.0\",\"api_schema_version\":1}}",data,fake_test?"TEST":"PRODUCTION",(unsigned long long)fake_now);
  r->size=strlen(r->body);r->status=status;
}
static void raw_response(MoHttpResponse *r,const char *data){r->body=strdup(data);assert(r->body);r->size=strlen(data);r->status=200;}
static void purchase_response(MoHttpResponse *r){
  char data[2800],keys[64]="";
  if(fake_selected&1)strcat(keys,"\"ef:1\"");
  if(fake_selected&2)strcat(keys,fake_selected&1?",\"ef:2\"":"\"ef:2\"");
  snprintf(data,sizeof(data),"{\"purchase_id\":9,\"offer_id\":1001,\"tier\":\"LITE\",\"state\":\"PAID_PENDING_SELECTION\",\"paid_amount\":1000,\"select_count\":2,\"selection_revision\":%u,\"selected_player_keys\":[%s],\"pool\":["
      "{\"slot\":1,\"player_key\":\"ef:1\",\"display_name\":\"Alpha Player\",\"position\":\"GK\",\"display_ovr\":67},"
      "{\"slot\":2,\"player_key\":\"ef:2\",\"display_name\":\"Beta Player\",\"position\":\"CB\",\"display_ovr\":66},"
      "{\"slot\":3,\"player_key\":\"ef:3\",\"display_name\":\"Gamma Player\",\"position\":\"CMF\",\"display_ovr\":65},"
      "{\"slot\":4,\"player_key\":\"ef:4\",\"display_name\":\"Delta Player\",\"position\":\"CF\",\"display_ovr\":64},"
      "{\"slot\":5,\"player_key\":\"fl26:5\",\"display_name\":\"Epsilon Player\",\"position\":\"RB\",\"display_ovr\":63}]}",fake_revision,keys);
  response(r,200,data);
}
static void clock_response(MoHttpResponse *r,int complete){
  char data[500];
  snprintf(data,sizeof(data),"{\"environment\":\"TEST\",\"account_id\":42,\"state\":\"%s\",\"idempotency_key\":\"%s\",\"clock_revision\":%u,\"test_now_ms\":%llu}",complete?"SUCCEEDED":"RUNNING",clock_key,complete?clock_final_revision:fake_clock_revision,(unsigned long long)(complete?clock_final_now:fake_now));
  response(r,complete?200:202,data);
}
static void promo_response(MoHttpResponse *r){
  char data[500];snprintf(data,sizeof(data),"{\"state\":\"SUCCEEDED\",\"redemption_id\":71,\"environment\":\"%s\",\"account_id\":42,\"idempotency_key\":\"%s\",\"currency\":\"NX_CASH\",\"amount\":%u,\"wallet\":{\"balance\":%llu,\"version\":%u}}",fake_test?"TEST":"PRODUCTION",promo_key,bad_promo_receipt?0:5000,(unsigned long long)fake_cash,fake_wallet_revision);response(r,200,data);
}
void mo_http_perform(const MoHttpRequest *q,MoHttpResponse *r){
  memset(r,0,sizeof(*r));http_calls++;
  if(!strcmp(q->path,"/league/schedule"))schedule_calls++;
  if(v117_http(q,r)||extended_http(q,r))return;
  if(!strcmp(q->path,"/compatibility")){
    if(wrong_version)response(r,200,"{\"required_online_version\":\"2.0.0\"}");
    else response(r,200,"{\"required_online_version\":\"1.0.0\",\"required_catalog_content_sha256\":\"" MANAGER_ONLINE_CATALOG "\",\"required_runtime_pair_id\":\"" MANAGER_ONLINE_PAIR "\",\"api_schema_version\":1,\"maintenance\":false}");
  }
  else if(!strcmp(q->path,"/auth/login")||!strcmp(q->path,"/auth/refresh")){
    if(!strcmp(q->path,"/auth/login")){assert(strstr(q->body,"\"pin\":\"0042\""));logins++;}
    else {assert(strstr(q->body,fake_refresh));refreshes++;}
    char data[600];snprintf(data,sizeof(data),"{\"access_token\":\"synthetic-access-not-a-real-token\",\"refresh_token\":\"synthetic-refresh-not-a-real-token\",\"expires_in_seconds\":900,\"environment\":\"%s\",\"capabilities\":{\"demo_time\":%s,\"promotion_codes\":%s},\"test_clock\":{\"revision\":%u}}",fake_test?"TEST":"PRODUCTION",fake_test&&!missing_test_context?"true":"false",promo_enabled?"true":"false",missing_test_context?0:fake_clock_revision);response(r,200,data);
  }else if(!strcmp(q->path,"/me/bootstrap")){
    assert(!strcmp(q->access,fake_access));char data[1000];
    snprintf(data,sizeof(data),"{\"environment\":\"%s\",\"capabilities\":{\"demo_time\":%s,\"promotion_codes\":%s},\"test_clock\":{\"revision\":%u},\"account\":{\"id\":\"42\",\"user_id\":\"%s\"},\"club\":{\"id\":\"84\",\"name\":\"Synthetic FC\",\"presentation_team_id\":108},\"wallet\":{\"balance\":%llu,\"currency\":\"NX_CASH\",\"version\":%u},\"league\":{\"cycle_id\":1,\"label\":\"W1\",\"state\":\"%s\",\"waiting_entry_count\":4,\"minimum_entries\":4,\"remaining_needed\":0,\"user_joined\":%s},\"pending_pack\":%s}",bootstrap_wrong_realm?"PRODUCTION":fake_test?"TEST":"PRODUCTION",fake_test?"true":"false",promo_enabled?"true":"false",fake_clock_revision,login_user,(unsigned long long)fake_cash,fake_wallet_revision,fake_test?"REGISTRATION":"PREPARATION",join_posts?"true":"false",pending_pack?"{}":"null");
    if(no_bootstrap_league){
      char *league=strstr(data,"\"league\":{");assert(league);char *tail=strstr(league,"},\"pending_pack\"");assert(tail);
      memmove(league+13,tail+1,strlen(tail+1)+1);memcpy(league,"\"league\":null",13);
    }
    response(r,200,data);
  }else if(!strcmp(q->path,"/league/status")){
    response(r,200,closed_registration?"{\"cycle_id\":2,\"label\":\"W2\",\"state\":\"PREPARATION\",\"user_joined\":false,\"waiting_entry_count\":0,\"minimum_entries\":4,\"remaining_needed\":4}":"{\"cycle_id\":2,\"label\":\"W2\",\"state\":\"REGISTRATION\",\"user_joined\":false,\"waiting_entry_count\":0,\"minimum_entries\":4,\"remaining_needed\":4}");
  }else if(!strcmp(q->path,"/league/standings")||!strcmp(q->path,"/league/schedule")||!strcmp(q->path,"/news")||!strcmp(q->path,"/ranking/overall")){
    response(r,200,"[]");
  }else if(!strncmp(q->path,"/ranking/monthly/",17)){
    monthly_calls++;monthly_mock(q,r);
  }else if(!strcmp(q->path,"/league/player-feed")){
    assert(online.player_feed_capable&&q->environment==online.environment);
    char body[256];snprintf(body,sizeof(body),"{\"cycle_id\":%llu,\"published_through_ms\":%llu,\"top_scorers\":[],\"rising_stars\":[]}",(unsigned long long)online.cycle,(unsigned long long)fake_now);response(r,200,body);
  }else if(!strcmp(q->path,"/league/join")){
    assert(fake_test&&q->environment==MO_TEST);join_posts++;fake_cash+=1500;fake_wallet_revision++;response(r,201,"{}");
  }else if(!strcmp(q->path,"/dev/clock/advance")){
    assert(fake_test&&q->environment==MO_TEST&&online.demo_time);clock_posts++;
    if(clock_key[0]){assert(!strcmp(clock_key,q->key));assert(!strcmp(clock_body,q->body));}
    else {copy(clock_key,sizeof(clock_key),q->key);assert(strlen(q->body)<sizeof(clock_body));memcpy(clock_body,q->body,strlen(q->body)+1);}
    char path[160];assert(account_path(path,"clock"));FILE *f=fopen(path,"rb");assert(f);fclose(f);
    if(lose_clock_reply){lose_clock_reply=0;clock_applied++;fake_now+=604800000;fake_clock_revision++;clock_final_revision=fake_clock_revision;clock_final_now=fake_now;r->transport_error=1;}
    else clock_response(r,clock_applied!=0);
  }else if(strstr(q->path,"/dev/clock/operations/")){
    assert(q->environment==MO_TEST);assert(strstr(q->path,clock_key));clock_reads++;
    if(hold_clock_running){clock_response(r,0);return;}
    if(!clock_applied){clock_applied++;fake_now+=604800000;fake_clock_revision++;clock_final_revision=fake_clock_revision;clock_final_now=fake_now;}clock_response(r,1);
  }else if(!strcmp(q->path,"/promotions/redeem")){
    assert(promo_enabled&&q->environment==(fake_test?MO_TEST:MO_PRODUCTION));promo_posts++;
    if(promo_key[0]){assert(!strcmp(promo_key,q->key));assert(!strcmp(promo_body,q->body));}
    else {copy(promo_key,sizeof(promo_key),q->key);assert(strlen(q->body)<sizeof(promo_body));memcpy(promo_body,q->body,strlen(q->body)+1);}
    if(strstr(q->body,"INVALIDCODE000")){raw_response(r,"{\"error\":{\"code\":\"CODE_UNAVAILABLE\",\"message\":\"Code unavailable\"}}");r->status=422;return;}
    if(!promo_credits&&!promo_not_committed){promo_credits++;fake_cash+=5000;fake_wallet_revision++;}
    if(lose_promo_reply){lose_promo_reply=0;r->transport_error=1;}else promo_response(r);
  }else if(strstr(q->path,"/promotions/operations/")){
    assert(strstr(q->path,promo_key));if(promo_credits)promo_response(r);
    else {raw_response(r,"{\"error\":{\"code\":\"OPERATION_NOT_FOUND\",\"message\":\"Retry the saved operation\"}}");r->status=404;}
  }else if(!strcmp(q->path,"/club/profile"))response(r,200,"{\"registered_players\":18,\"total_collection\":20}");
  else if(!strcmp(q->path,"/club/collection")){
    collection_reads++;
    if(collection_401){collection_401=0;raw_response(r,"{\"error\":{\"code\":\"UNAUTHORIZED\",\"message\":\"Expired\"}}");r->status=401;}
    else response(r,200,"[]");
  }
  else if(!strcmp(q->path,"/shop/offers"))response(r,200,"[{\"offer_id\":1001,\"version\":1,\"team_id\":108,\"team_name\":\"Synthetic FC\",\"tier\":\"LITE\",\"price\":1000,\"pool_count\":5,\"select_count\":2}]");
  else if(!strcmp(q->path,"/shop/pending")){if(pending_pack)purchase_response(r);else response(r,200,"null");}
  else if(!strcmp(q->path,"/shop/purchases")){
    assert(!strcmp(q->method,"POST")&&strlen(q->key)==36);assert(strstr(q->body,"\"accepted_price_nx_cash\":1000"));
    char path[160];assert(payment_path(path));FILE *f=fopen(path,"rb");assert(f);fclose(f);payments++;
    if(reject_pool){raw_response(r,"{\"error\":{\"code\":\"PACK_POOL_UNAVAILABLE\",\"message\":\"No NX Cash was charged.\"}}");r->status=422;return;}
    if(payment_key[0]){assert(!strcmp(q->key,payment_key));assert(!strcmp(q->body,payment_body));}
    else {copy(payment_key,sizeof(payment_key),q->key);assert(strlen(q->body)<sizeof(payment_body));memcpy(payment_body,q->body,strlen(q->body)+1);}
    if(!payment_not_committed&&!pending_pack){pending_pack=1;fake_cash-=1000;}
    if(lose_payment)r->transport_error=1;else purchase_response(r);
  }else if(strstr(q->path,"/shop/operations/")){
    assert(strstr(q->path,payment_key));
    if(receipt_completed){
      MoHttpResponse paid={0};purchase_response(&paid);MjToken storage[300];MjDoc d;char payload[3000],result[3300];
      assert(mj_parse(&d,paid.body,paid.size,storage,300)&&mj_copy(&d,mj_get(&d,0,"data"),payload,sizeof(payload)));
      snprintf(result,sizeof(result),"{\"idempotency_key\":\"%s\",\"status\":\"COMPLETED\",\"operation\":\"SHOP_PURCHASE\",\"response\":%s}",payment_key,payload);
      response(r,200,result);mo_http_free(&paid);
    }else {char result[256];snprintf(result,sizeof(result),"{\"idempotency_key\":\"%s\",\"status\":\"NOT_FOUND\"}",payment_key);response(r,200,result);}
  }else if(!strcmp(q->path,"/shop/purchases/9/selection")){
    assert(!strcmp(q->method,"PUT"));fake_selected=(strstr(q->body,"ef:1")?1:0)|(strstr(q->body,"ef:2")?2:0);fake_revision++;
    if(lose_selection_response){lose_selection_response=0;r->transport_error=1;}else response(r,200,"{\"message\":\"saved\"}");
  }else if(!strcmp(q->path,"/shop/purchases/9/grant")){
    assert(!strcmp(q->method,"POST")&&strstr(q->body,"ef:1")&&strstr(q->body,"ef:2"));fake_selected=3;grants++;pending_pack=0;
    if(lose_grant_response){lose_grant_response=0;r->transport_error=1;}else response(r,200,"{\"granted_player_keys\":[\"ef:2\",\"ef:1\"]}");
  }else if(strstr(q->path,"/recording/chunks/")&&!strstr(q->path,"/recording/chunks/6")){
    unsigned index=(unsigned)strtoul(strrchr(q->path,'/')+1,NULL,10);char data[300];
    snprintf(data,sizeof(data),"[{\"at_ms\":%u,\"bx\":20000,\"by\":34000,\"h\":[{\"id\":1,\"x\":10000,\"y\":34000}],\"a\":[{\"id\":12,\"x\":95000,\"y\":34000}]}]",index*30000);raw_response(r,data);
  }else if(strstr(q->path,"/recording/header")){
    if(delay_header){struct timespec pause={0,70000000};nanosleep(&pause,NULL);}
    response(r,200,"{\"fixture_id\":7,\"recording_hash\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",\"recording_version\":1,\"duration_ms\":660000,\"chunk_duration_ms\":30000,\"chunk_count\":22,\"broadcast_start_ms\":1700000000000,\"current_watermark_ms\":220000,\"state\":\"LIVE\"}");
  }else if(strstr(q->path,"/recording/chunks/6"))raw_response(r,"[{\"at_ms\":180000,\"bx\":20000,\"by\":34000,\"h\":[{\"id\":1,\"x\":10000,\"y\":34000}],\"a\":[{\"id\":12,\"x\":95000,\"y\":34000}]},{\"at_ms\":200000,\"bx\":40000,\"by\":34000,\"h\":[{\"id\":1,\"x\":12000,\"y\":34000}],\"a\":[{\"id\":12,\"x\":93000,\"y\":34000}]}]");
  else if(strstr(q->path,"/events"))response(r,200,"[{\"sequence\":1,\"at_ms\":1000,\"game_second\":9,\"kind\":\"PASS\",\"side\":\"HOME\"},{\"sequence\":2,\"at_ms\":190000,\"game_second\":1710,\"kind\":\"GOAL\",\"side\":\"HOME\",\"actor_name\":\"Alpha Player\"},{\"sequence\":3,\"at_ms\":210000,\"game_second\":1890,\"kind\":\"GOAL\",\"side\":\"AWAY\",\"actor_name\":\"Future Player\"}]");
  else if(!strcmp(q->path,"/auth/logout")){r->transport_error=1;}
  else {fprintf(stderr,"Unexpected synthetic route %s\n",q->path);assert(0);}
}
static void idle(void){
  for(unsigned i=0;i<3000;i++){
    manager_online_tick(++host_ms);
    pthread_mutex_lock(&worker.mutex);int done=!worker.running&&!worker.pending&&!worker.ready;pthread_mutex_unlock(&worker.mutex);
    if(!online.busy&&done)return;
    struct timespec pause={0,1000000};nanosleep(&pause,NULL);
  }assert(!"worker did not settle");
}
static void enter_key(unsigned target){
  while(pin_cursor/3>target/3)manager_online_pad(UP);
  while(pin_cursor/3<target/3)manager_online_pad(DOWN);
  while(pin_cursor%3>target%3)manager_online_pad(LEFT);
  while(pin_cursor%3<target%3)manager_online_pad(RIGHT);
  manager_online_pad(A);
}
static void login(void){
  manager_online_open();idle();assert(online.compatible&&!online.authenticated);
  manager_online_pad(A);assert(online.page==MD_LOGIN);manager_online_name_result(login_user);
  manager_online_pad(DOWN);manager_online_pad(A);assert(pin_active);
  enter_key(10);enter_key(10);enter_key(3);enter_key(1);enter_key(11);assert(pin_confirmed);
  MdView v;manager_online_view(&v);assert(!v.pin_open&&!strstr(v.rows[1].value,"0042"));
  manager_online_pad(DOWN);manager_online_pad(A);idle();
  assert(logins==1&&online.authenticated&&online.cash==5000&&online.roster_count==18&&online.page==MD_DASHBOARD);
}
static void shop(void){open_shop();idle();if(online.page==MD_SHOP_CLUBS)manager_online_pad(A);assert(online.page==MD_SHOP||(online.page==MD_PAYMENT_RECOVERY&&online.pay_uncertain));}
static void pay(void){
  unsigned before=payments;
  manager_online_pad(A);assert(online.page==MD_PACK);manager_online_pad(A);assert(online.page==MD_PACK_BUY&&payments==before);
  manager_online_pad(LEFT);manager_online_pad(A);idle();assert(payments==before+1);
}
static void pack_flow(void){
  login();shop();pay();assert(online.page==MD_PACK_OPENING&&online.cash==4000);
  manager_online_tick(host_ms+=MD_PACK_OPEN_MS+1);assert(online.page==MD_PACK_SELECT);
  manager_online_pad(B);assert(online.page==MD_PACK_SELECT);
  manager_online_pad(DOWN);manager_online_pad(DOWN);assert(online.focus<online.pool_count);
  unsigned requests=http_calls;online.focus=0;manager_online_pad(A);idle();assert(!fake_selected&&online.selected==1&&http_calls==requests);
  manager_online_pad(RIGHT);manager_online_pad(A);idle();assert(!fake_selected&&online.selected==3&&http_calls==requests);
  manager_online_pad(DOWN);manager_online_pad(DOWN);assert(online.focus==online.pool_count);
  manager_online_pad(A);idle();assert(grants==1&&payments==1&&online.cash==4000&&online.page==MD_PACK_RESULT);
  manager_online_close();manager_online_open();idle();assert(logins==1&&refreshes==1&&online.authenticated&&online.page==MD_DASHBOARD);
  FILE *f=fopen(MO_SESSION_FILE,"rb");assert(f);char data[2048]={0};assert(fread(data,1,sizeof(data)-1,f)>0);fclose(f);
  for(size_t i=0;i+4<=sizeof(data);i++)assert(memcmp(data+i,"0042",4));
  for(size_t i=0;i+sizeof(fake_access)-1<=sizeof(data);i++)assert(memcmp(data+i,fake_access,sizeof(fake_access)-1));
}
static void unavailable_pool(void){
  login();shop();reject_pool=1;pay();assert(payments==1&&online.cash==5000&&!online.pay_uncertain&&online.page==MD_SHOP&&online.notice[0]&&!online.busy&&!nx_loading_active());
  manager_online_pad(A);manager_online_pad(B);shop();assert(!online.pay_uncertain);reject_pool=0;pay();assert(payments==2&&online.cash==4000&&online.page==MD_PACK_OPENING);
}
static void uncertain_payment(int committed){
  login();shop();lose_payment=1;payment_not_committed=!committed;pay();assert(online.pay_uncertain&&online.notice[0]);
  manager_online_pad(A);manager_online_close();manager_online_open();idle();
  if(committed){assert(online.page==MD_PACK_SELECT&&online.cash==4000&&!online.pay_uncertain&&payments==1);}
  else {assert(online.pay_uncertain&&online.cash==5000);shop();assert(online.notice[0]&&online.page==MD_PAYMENT_RECOVERY);manager_online_pad(A);manager_online_pad(B);assert(online.page==MD_SHOP_CLUBS);manager_online_pad(A);assert(online.page==MD_PAYMENT_RECOVERY&&payments==1);
    payment_not_committed=lose_payment=0;manager_online_pad(DOWN);manager_online_pad(A);idle();assert(payments==2&&online.cash==4000&&!online.pay_uncertain&&online.page==MD_PACK_OPENING);}
}
static void watch(void){
  login();MoMatch m={.id=7,.phase=1,.kickoff=1700000000000};copy(m.row.label,sizeof(m.row.label),"Alpha FC Vs Beta FC");
  change_page(MD_SCHEDULE);watch_open(&m);idle();assert(online.page==MD_WATCH&&online.play_ms>=200000&&online.play_ms<201000);
  MdView v;manager_online_view(&v);assert(v.watch_ready&&v.home_goals==1&&v.away_goals==0&&v.touchline_total==2);
  assert(v.dots[1].x<0&&v.dots[22].x>.37f);assert(!strstr(v.event_feed[0].detail,"Future"));
  ManagerLeagueAudioFrame audio;manager_online_audio_frame(&audio,host_ms);assert(audio.visible_watch&&audio.event_kind==MD_GOAL);
  manager_online_pad(X);idle();manager_online_view(&v);assert(v.touchline_open&&v.touchline_total==2);
  manager_online_pad(B);delay_header=1;queue_watch_header();manager_online_pad(B);assert(online.page==MD_SCHEDULE);idle();assert(online.page==MD_SCHEDULE);
  delay_header=0;host_ms+=12345;change_page(MD_SCHEDULE);watch_open(&m);idle();assert(online.play_ms>=200000&&online.play_ms<201000);
}
static MjToken tokens[1024];static MjDoc doc;
static void json(const char *text){assert(mj_parse(&doc,text,strlen(text),tokens,1024));}
static void validation(void){
  mo_wipe(&online,sizeof(online));online.fixture=7;online.duration=660000;online.chunk_ms=30000;online.chunk_count=22;online.watermark=30000;
  json("[{\"at_ms\":0,\"bx\":0,\"by\":0,\"h\":[{\"id\":1,\"x\":0}],\"a\":[]}]");assert(!parse_chunk(&doc,"/chunks/0"));
  json("[{\"at_ms\":0,\"bx\":0,\"by\":0,\"h\":[],\"a\":[]}]");assert(!parse_chunk(&doc,"/chunks/1"));assert(parse_chunk(&doc,"/chunks/0"));
  /* A released chunk may contain later frames; the playback cursor hides them. */
  json("[{\"at_ms\":30001,\"bx\":0,\"by\":0,\"h\":[],\"a\":[]}]");assert(parse_chunk(&doc,"/chunks/1"));
  json("[{\"at_ms\":60000,\"bx\":0,\"by\":0,\"h\":[],\"a\":[]}]");assert(!parse_chunk(&doc,"/chunks/2"));
  online.event_count=1;online.events[0].kind=MD_GOAL;
  json("[{\"at_ms\":0,\"game_second\":0,\"kind\":\"PASS\"},{\"at_ms\":30001,\"game_second\":0,\"kind\":\"GOAL\"}]");assert(!parse_events(&doc,0)&&online.event_count==1&&online.events[0].kind==MD_GOAL);
  assert(event_kind("RED_CARD")!=MD_YELLOW&&event_kind("KICKOFF")==MLA_KICKOFF);
  assert(!identity("ef:01")&&!identity("ef:+1")&&!identity("ef: 1")&&identity("ef:1")==1);
}
static void shortcut(void){
  NxManagerDevShortcut s={0};const uint32_t key=32|64|4;
  assert(!nx_manager_dev_shortcut(&s,key,0,100));assert(nx_manager_dev_shortcut(&s,key,1,100)==1);
  assert(nx_manager_dev_shortcut(&s,key,1,2099)==1);assert(nx_manager_dev_shortcut(&s,key,1,2100)==2);
  assert(nx_manager_dev_shortcut(&s,key,1,2200)==1);assert(!nx_manager_dev_shortcut(&s,0,1,2300));
  assert(nx_manager_dev_shortcut(&s,key,1,2400)==1);assert(nx_manager_dev_shortcut(&s,key,1,4400)==2);
}
static void json_bounds(void){
  char out[128],tiny[3],quoted[128];uint64_t n;
  json("{\"items\":[{\"n\":\"18446744073709551615\"},true,null],\"pin\":\"0042\",\"name\":\"A \\uD83D\\uDE00\"}");
  int items=mj_get(&doc,0,"items");assert(mj_u64(&doc,mj_get(&doc,mj_at(&doc,items,0),"n"),&n)&&n==UINT64_MAX);
  assert(mj_text(&doc,mj_get(&doc,0,"pin"),out,sizeof(out))&&!strcmp(out,"0042"));
  assert(!mj_text(&doc,mj_get(&doc,0,"pin"),tiny,sizeof(tiny))&&!tiny[0]);
  assert(mj_text(&doc,mj_get(&doc,0,"name"),out,sizeof(out))&&!strcmp(out,"A \xf0\x9f\x98\x80"));
  assert(mj_quote("0042\n\"",quoted,sizeof(quoted))&&!strcmp(quoted,"\"0042\\u000a\\\"\""));
  const char *invalid[]={"{", "[1,]", "{\"a\":true,}","01","true false","[1 2]","{\"a\" 1}","\"\\x\""};
  for(unsigned i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++)assert(!mj_parse(&doc,invalid[i],strlen(invalid[i]),tokens,1024));
  const char nul[]={'[','0',0,']'};assert(!mj_parse(&doc,nul,sizeof(nul),tokens,1024));
  assert(!mj_parse(&doc,"[1,2]",5,tokens,2));
  const char *bad_numbers[]={"18446744073709551616","-1","1.0","1e2","\"\"","\"12a\""};
  for(unsigned i=0;i<sizeof(bad_numbers)/sizeof(bad_numbers[0]);i++){json(bad_numbers[i]);assert(!mj_u64(&doc,0,&n));}
  const char *bad_strings[]={"\"\\u0000\"","\"\\uD800\"","\"\\uDC00\"","\"\xc0\x80\"","\"\xf4\x90\x80\x80\""};
  for(unsigned i=0;i<sizeof(bad_strings)/sizeof(bad_strings[0]);i++){json(bad_strings[i]);assert(!mj_text(&doc,0,out,sizeof(out)));}
  json("{\"a\":1,\"a\":2}");assert(mj_get(&doc,0,"a")==-1);
}
static void auth_recovery(void){
  login();collection_401=1;get(J_COLLECTION,"/club/collection");idle();
  assert(refreshes==1&&collection_reads==2&&online.page==MD_COLLECTION_PAGE&&online.authenticated);
  change_page(MD_DASHBOARD);online.tab=2;online.focus=2;manager_online_pad(A);assert(online.page==MD_LOGOUT);manager_online_pad(LEFT);manager_online_pad(A);idle();
  assert(!online.authenticated&&online.page==MD_REGISTER);FILE *f=fopen(MO_SESSION_FILE,"rb");assert(!f);
}
static void gate(void){
  wrong_version=1;manager_online_open();idle();assert(!online.compatible&&online.notice[0]&&logins==0);
  manager_online_pad(A);manager_online_pad(A);idle();assert(!online.authenticated&&logins==0&&online.page==MD_REGISTER);
}
static void interrupted_selection(void){
  login();shop();pay();manager_online_tick(host_ms+=MD_PACK_OPEN_MS+1);
  unsigned requests=http_calls;manager_online_pad(A);idle();assert(!online.notice[0]&&!fake_selected&&online.selected==1&&http_calls==requests);
  manager_online_pad(Y);idle();assert(online.page==MD_PURCHASE_HISTORY&&online.selected==1);
  manager_online_pad(B);assert(online.page==MD_PACK_SELECT&&online.selected==1);
  manager_online_pad(RIGHT);manager_online_pad(A);idle();manager_online_pad(DOWN);manager_online_pad(DOWN);
  lose_grant_response=1;manager_online_pad(A);idle();assert(online.notice[0]&&grants==1);
  char key[37];copy(key,sizeof(key),online.grant_key);manager_online_pad(A);
  manager_online_pad(UP);manager_online_pad(A);assert(online.selected==3&&online.focus==online.pool_count&&online.notice[0]);
  manager_online_pad(A);assert(!strcmp(key,online.grant_key));manager_online_pad(A);idle();
  assert(online.page==MD_PACK_RESULT&&payments==1&&grants==2&&!online.grant_uncertain);
}
static void finish_clock(void){
  for(unsigned i=0;i<5&&online.clock_active;i++){host_ms+=1001;idle();}
  assert(!online.clock_active&&!online.clock_intent.magic&&clock_applied==1);
}
static void onlinedev(void){
  fake_test=promo_enabled=1;login();assert(online.environment==MO_TEST&&online.demo_time);
  MdView v;manager_online_view(&v);assert(v.online_test&&strstr(v.caption,"REGISTRATION & PREP")&&strstr(v.caption,"WIB")&&strstr(v.rows[0].value,"NOT REGISTERED"));
  manager_online_pad(A);assert(online.join_confirm&&!join_posts);manager_online_pad(LEFT);manager_online_pad(A);idle();assert(join_posts==1&&online.joined&&online.cash==6500);
  manager_online_pad(Y);assert(online.page==MD_ONLINEDEV);
  manager_online_pad(DOWN);manager_online_pad(A);assert(online.clock_confirm==2);
  manager_online_pad(A);assert(!clock_posts); /* Cancel is selected by default. */
  manager_online_pad(A);manager_online_pad(LEFT);manager_online_pad(A);idle();
  assert(online.clock_active&&clock_posts==1&&strstr(clock_body,"FINISH_WEEK"));
  manager_online_pad(A);assert(clock_posts==1);finish_clock();
  assert(online.page==MD_DASHBOARD&&online.cash==6500&&refreshes==0&&!online.event_count&&!online.match_count);
  assert(server_now()>=1700000200000ULL+604800000ULL); /* Real API clock receipt. */
  char production[160],test[160];assert(payment_path(test));online.environment=MO_PRODUCTION;assert(payment_path(production));assert(strcmp(test,production));online.environment=MO_TEST;
  manager_online_close();manager_online_open();idle();assert(online.environment==MO_TEST&&online.demo_time&&refreshes==1);
}
static void production_guard(void){
  login_user="dev";login();assert(online.environment==MO_PRODUCTION&&!online.demo_time);
  manager_online_pad(Y);idle();assert(online.page==MD_DASHBOARD&&!clock_posts);
  online.demo_time=1;assert(!request(J_CLOCK,"POST","/dev/clock/advance","{}",1)&&!clock_posts);
  manager_online_pad(A);shop();MdView v;manager_online_view(&v);int helper_found=0;
  for(unsigned i=0;i<v.helper_count;i++)if(!strcmp(v.helper_label[i],"PROMOTION CODE"))helper_found=1;
  assert(helper_found);manager_online_pad(X);assert(online.page==MD_SHOP&&online.notice[0]&&!promo_posts);
}
static void clock_recovery(int newer){
  fake_test=1;login();lose_clock_reply=1;clock_submit(0);idle();
  assert(online.clock_intent.magic&&!online.clock_active&&online.notice[0]&&clock_applied==1);
  manager_online_close();if(newer){fake_clock_revision++;fake_now+=86400000;}
  manager_online_open();idle();finish_clock();
  assert(clock_posts==1&&clock_reads==1&&refreshes==1&&online.clock_revision==(newer?3u:2u));
  assert(!online.notice[0]);
}
static void clock_timeout(void){
  fake_test=hold_clock_running=1;login();clock_submit(0);idle();assert(online.clock_active&&online.clock_intent.magic);
  host_ms+=60001;idle();assert(!online.clock_active&&online.notice[0]&&online.clock_intent.magic&&!clock_applied);
  manager_online_pad(A);manager_online_pad(Y);assert(online.page==MD_ONLINEDEV);
  hold_clock_running=0;manager_online_pad(A);idle();finish_clock();assert(clock_posts==1&&clock_reads==1);
}
static void unjoined_calendar(int closed){
  fake_test=no_bootstrap_league=1;closed_registration=closed;login();
  assert(online.league_known&&online.cycle==2&&!strcmp(online.league_label,"W2"));
  manager_online_pad(A);idle();assert(!join_posts);
  if(closed)assert(online.page==MD_DASHBOARD&&online.notice[0]&&!strcmp(online.phase,"PREPARATION"));
  else {assert(online.join_confirm);manager_online_pad(LEFT);manager_online_pad(A);idle();assert(join_posts==1);}
}
static void environment_guard(int mode){
  fake_test=1;
  if(mode==1){missing_test_context=1;manager_online_open();idle();copy(online.login_id,sizeof(online.login_id),"synthetic_qa");
    copy(pin_value,sizeof(pin_value),"0042");pin_confirmed=1;auth_submit();idle();assert(!online.authenticated&&!online.demo_time&&online.notice[0]);}
  else if(mode==2){bootstrap_wrong_realm=1;manager_online_open();idle();copy(online.login_id,sizeof(online.login_id),"synthetic_qa");
    copy(pin_value,sizeof(pin_value),"0042");pin_confirmed=1;auth_submit();idle();assert(!online.cash_known&&!online.account[0]&&online.notice[0]);}
  else {login();manager_online_close();fake_test=0;manager_online_open();idle();assert(!online.authenticated&&!online.demo_time&&online.page==MD_LOGIN);}
  assert(!clock_posts&&!promo_posts);
}
static void promo_enter(const char *code){
  shop();manager_online_pad(X);idle();assert(online.page==MD_PROMOTION);
  manager_online_pad(A);assert(manager_online_take_action()==MD_ACTION_NAME&&manager_online_input_promotion());
  manager_online_name_result(code);assert(!manager_online_input_promotion());
}
static void promotion(int mode){
  promo_enabled=1;login();promo_enter(mode==3?"INVALIDCODE000":"abcd-1234 efgh-5678");
  assert(!online.notice[0]);MdView v;manager_online_view(&v);assert(!strstr(v.rows[0].value,"ABCD"));
  if(mode==1||mode==2)lose_promo_reply=1;
  if(mode==2)promo_not_committed=1;
  if(mode==4)bad_promo_receipt=1;
  manager_online_pad(DOWN);manager_online_pad(A);idle();assert(promo_posts==1);
  if(mode==3){assert(online.cash==5000&&!online.promo_intent.magic&&online.notice[0]&&!promo_credits);return;}
  if(mode==4){assert(online.cash==5000&&online.promo_intent.magic&&online.notice[0]);return;}
  if(mode==1||mode==2){
    assert(online.cash==5000&&online.promo_intent.magic&&online.notice[0]);
    manager_online_close();manager_online_open();idle();assert(online.authenticated);
    shop();manager_online_pad(X);idle();
    if(mode==2){assert(online.promo_intent.magic&&online.notice[0]);manager_online_pad(A);promo_not_committed=0;manager_online_pad(DOWN);manager_online_pad(A);idle();assert(promo_posts==2);}
    else assert(promo_posts==1);
  }
  assert(online.cash==10000&&promo_credits==1&&!online.promo_intent.magic&&online.notice[0]);
  char path[160];assert(account_path(path,"promotion"));FILE *f=fopen(path,"rb");assert(!f);
}
static void promo_validation(void){
  char code[33];assert(normalize_promo(" abcd-1234 efgh-5678 ",code)&&!strcmp(code,"ABCD1234EFGH5678"));
  assert(!normalize_promo("ABCD\n1234EFGH",code)&&!code[0]);assert(!normalize_promo("ABCD+1234EFGH",code));
  assert(!normalize_promo("ABCD",code));assert(!normalize_promo("123456789012345678901234567890123",code));
  promo_enabled=1;login();char path[160];assert(account_path(path,"promotion"));FILE *f=fopen(path,"wb");assert(f);fputs("partial",f);fclose(f);
  refresh_bootstrap();idle();assert(online.promo_corrupt);promo_enter("ABCD1234EFGH5678");manager_online_pad(DOWN);manager_online_pad(A);idle();assert(!promo_posts&&online.notice[0]);
}
static void test_watch(void){fake_test=1;watch();assert(!online.notice[0]&&online.environment==MO_TEST);}
static void wrong_realm_error(void){
  fake_test=promo_enabled=1;login();MoResult result={.generation=generation,.kind=J_PROMO};
  online.promo_intent.magic=MO_INTENT_MAGIC;copy(online.promo_intent.key,sizeof(online.promo_intent.key),"00000000-0000-4000-8000-000000000001");
  raw_response(&result.http,"{\"error\":{\"code\":\"INVALID_CODE\"},\"meta\":{\"environment\":\"PRODUCTION\"}}");result.http.status=422;
  consume(&result);mo_http_free(&result.http);assert(online.promo_intent.magic&&online.notice[0]&&online.cash==5000);
}
static void payment_write_failure(void){
  login();shop();fail_payment_rename=1;
  manager_online_pad(A);manager_online_pad(A);manager_online_pad(LEFT);manager_online_pad(A);idle();
  assert(!payments&&!online.pay_uncertain&&!online.busy&&online.notice[0]&&!nx_loading_active());
  manager_online_pad(A);manager_online_pad(B);manager_online_pad(B);assert(online.page==MD_SHOP);
  shop();assert(!online.notice[0]&&!online.pay_uncertain);fail_payment_rename=0;pay();assert(payments==1&&online.cash==4000);
}
static void profile_navigation(void){
  login();online.monthly_capable=1;MoResult r={.generation=generation,.kind=J_PROFILE};response(&r.http,200,"{\"registered_players\":18,\"total_collection\":24,\"league_standing\":{\"rank\":2,\"points\":7},\"monthly_ranking\":{\"season_id\":\"2023-11\",\"points\":2500,\"rank\":4}}");
  consume(&r);mo_http_free(&r.http);MdView v;manager_online_view(&v);
  assert(v.page==MD_CLUB_PROFILE&&v.total==6&&v.badge&&v.club_rank==2&&v.league_points==7&&v.rank==4&&v.club_reputation==2500);
  for(int i=0;i<5;i++)manager_online_pad(DOWN);
  manager_online_view(&v);assert(v.focus==5&&v.first==1&&!strcmp(v.rows[4].label,"LEAGUE REWARDS"));
  manager_online_pad(A);assert(online.page==MD_REWARDS);manager_online_pad(DOWN);manager_online_view(&v);assert(v.focus==1&&!strcmp(v.rows[1].value,"1,500 NX CASH"));
  manager_online_pad(B);idle();assert(online.page==MD_CLUB_PROFILE&&online.focus==5);
}
static void portrait_binding(void){
  MjToken tokens[128];MjDoc d;MoPlayer player;
  const char *wire="{\"instance_id\":12,\"player_key\":\"ef:1\",\"display_name\":\"Alpha\",\"position\":\"GK\",\"display_ovr\":68,\"portrait_id\":999}";
  assert(mj_parse(&d,wire,strlen(wire),tokens,128)&&parse_player(&d,0,&player));
  assert(player.row.identity==1&&player.row.native_id==91&&player.row.portrait==901);
  online.active=1;online.page=MD_TEAM_INFO;online.player_count=1;online.players[0]=player;MdView v;manager_online_view(&v);assert(v.rows[0].portrait==901);
  online.page=MD_CLUB_PLAN;online.plan_players[0].portrait=player.row.portrait;manager_online_view(&v);assert(v.plan_players[0].portrait==901);
}
static void unpublished_calendar(void){
  login();MjToken tokens[8];MjDoc d;assert(mj_parse(&d,"null",4,tokens,8)&&parse_league_status(&d,0));
  MdView v;manager_online_view(&v);assert(!online.league_known&&!online.notice[0]&&strstr(v.caption,"CALENDAR NOT PUBLISHED"));
  online.league_known=1;copy(online.phase,sizeof(online.phase),"SETTLED");manager_online_view(&v);assert(strstr(v.caption,"RESULTS & REWARDS"));
}
static void completed_payment_receipt(void){
  login();shop();lose_payment=1;pay();assert(payments==1&&online.pay_uncertain);
  manager_online_pad(A);receipt_completed=1;payment_lookup();idle();
  assert(online.page==MD_PACK_SELECT&&!online.pay_uncertain&&payments==1&&online.purchase==9&&online.cash==4000);
}
#include "manager_online_v110_fixture.inc"
#include "manager_online_v111_fixture.inc"
#include "manager_online_v112_fixture.inc"
#include "manager_online_v113_fixture.inc"
#include "manager_online_v115_fixture.inc"
#include "manager_online_v117_fixture.inc"
#include "manager_online_v118_fixture.inc"
#include "manager_online_v119_fixture.inc"
#include "manager_online_v120_fixture.inc"
int main(int argc,char **argv){
  assert(argc==2);
  if(!strcmp(argv[1],"registration-clubs-v120")){registration_clubs_v120();return 0;}
  if(!strcmp(argv[1],"owned-plan-v118")){owned_plan_v118();return 0;}
  if(!strcmp(argv[1],"hub-exit-v119")){hub_exit_v119();return 0;}
  if(!strcmp(argv[1],"hub-exit-background-v119")){hub_exit_background_v119();return 0;}
  if(!strcmp(argv[1],"hub-exit-context-v119")){hub_exit_context_v119();return 0;}
  if(!strcmp(argv[1],"owned-plan-boundary-v118")){owned_plan_boundary_v118();return 0;}
  if(!strcmp(argv[1],"local-selection-v117")){local_selection_v117();return 0;}
  else if(!strcmp(argv[1],"reserves-v117")){reserves_v117();return 0;}
  else if(!strcmp(argv[1],"analog-drag-v117")){analog_drag_v117();return 0;}
  else if(!strcmp(argv[1],"read-cache-v117")){read_cache_v117();return 0;}
  else if(!strcmp(argv[1],"promotion-amount-v117")){promotion_amount_v117();return 0;}
  else if(!strcmp(argv[1],"routes-v115")){routes_v115();return 0;}
  if(!strcmp(argv[1],"history-v115")){history_v115();return 0;}
  if(!strcmp(argv[1],"shop-clubs-v116")){shop_clubs_v116();return 0;}
  if(!strcmp(argv[1],"offers-v115")){offers_v115();return 0;}
  if(!strcmp(argv[1],"compat-recheck")){compat_recheck();return 0;}
  if(!strcmp(argv[1],"badge-navigation")){badge_navigation();return 0;}
  if(!strcmp(argv[1],"badge-stale")){badge_stale_response();return 0;}
  if(!strcmp(argv[1],"cache-scope")){cache_scope();return 0;}
  if(!strcmp(argv[1],"stale-phase")){stale_phase_label();return 0;}
  if(!strcmp(argv[1],"monthly-ranking")){monthly_flow();return 0;}
  if(!strcmp(argv[1],"monthly-validation")){monthly_validation();return 0;}
  if(!strcmp(argv[1],"hub-live-badge")){hub_live_badge();return 0;}
  if(!strcmp(argv[1],"hub-flow")){hub_flow();return 0;}
  if(!strcmp(argv[1],"hub-calendar")){hub_calendar_and_navigation();return 0;}
  if(!strcmp(argv[1],"hub-feed")){hub_feed_data();return 0;}
  if(!strcmp(argv[1],"pack"))pack_flow();
  else if(!strcmp(argv[1],"pool-unavailable"))unavailable_pool();
  else if(!strcmp(argv[1],"lost-committed"))uncertain_payment(1);
  else if(!strcmp(argv[1],"lost-not-committed"))uncertain_payment(0);
  else if(!strcmp(argv[1],"watch"))watch();
  else if(!strcmp(argv[1],"test-watch"))test_watch();
  else if(!strcmp(argv[1],"wrong-realm-error"))wrong_realm_error();
  else if(!strcmp(argv[1],"payment-write-fail"))payment_write_failure();
  else if(!strcmp(argv[1],"profile-navigation"))profile_navigation();
  else if(!strcmp(argv[1],"portrait-binding"))portrait_binding();
  else if(!strcmp(argv[1],"unpublished-calendar"))unpublished_calendar();
  else if(!strcmp(argv[1],"payment-receipt"))completed_payment_receipt();
  else if(!strcmp(argv[1],"validate"))validation();
  else if(!strcmp(argv[1],"shortcut"))shortcut();
  else if(!strcmp(argv[1],"json"))json_bounds();
  else if(!strcmp(argv[1],"auth-recovery"))auth_recovery();
  else if(!strcmp(argv[1],"gate"))gate();
  else if(!strcmp(argv[1],"interrupted-selection"))interrupted_selection();
  else if(!strcmp(argv[1],"onlinedev"))onlinedev();
  else if(!strcmp(argv[1],"production-guard"))production_guard();
  else if(!strcmp(argv[1],"clock-recovery"))clock_recovery(0);
  else if(!strcmp(argv[1],"clock-newer"))clock_recovery(1);
  else if(!strcmp(argv[1],"clock-timeout"))clock_timeout();
  else if(!strcmp(argv[1],"unjoined-open"))unjoined_calendar(0);
  else if(!strcmp(argv[1],"unjoined-closed"))unjoined_calendar(1);
  else if(!strcmp(argv[1],"test-context"))environment_guard(1);
  else if(!strcmp(argv[1],"bootstrap-realm"))environment_guard(2);
  else if(!strcmp(argv[1],"refresh-realm"))environment_guard(3);
  else if(!strcmp(argv[1],"promotion"))promotion(0);
  else if(!strcmp(argv[1],"promotion-lost"))promotion(1);
  else if(!strcmp(argv[1],"promotion-retry"))promotion(2);
  else if(!strcmp(argv[1],"promotion-invalid"))promotion(3);
  else if(!strcmp(argv[1],"promotion-receipt"))promotion(4);
  else if(!strcmp(argv[1],"promotion-validation"))promo_validation();
  else if(!strcmp(argv[1],"own-plan"))own_plan_flow(0);
  else if(!strcmp(argv[1],"plan-lost"))own_plan_flow(1);
  else if(!strcmp(argv[1],"plan-conflict"))own_plan_flow(2);
  else if(!strcmp(argv[1],"watch-zero"))zero_watch();
  else if(!strcmp(argv[1],"watch-bundle"))bundle_watch();
  else if(!strcmp(argv[1],"presentation"))presentation_data();
  else if(!strcmp(argv[1],"context-info")){
    login();const unsigned before=calls;const uint64_t cash=online.cash;
    const MdPage pages[]={MD_DASHBOARD,MD_WEEK_SCHEDULE,MD_CLUB_PLAN,MD_SHOP,MD_PAYMENT_RECOVERY,MD_TEAMS_PAGE,MD_OVERALL};
    for(unsigned i=0;i<sizeof(pages)/sizeof(pages[0]);i++){
      online.page=pages[i];manager_online_pad(32u);assert(online.page==pages[i]&&!strcmp(online.notice_title,"INFO")&&online.notice[0]);
      manager_online_pad(A);assert(!online.notice[0]&&online.page==pages[i]&&online.cash==cash&&calls==before);
    }
  }
  else assert(0);
  return 0;
}

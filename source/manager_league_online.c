#define _POSIX_C_SOURCE 200809L
#include "manager_league_online.h"
#include "manager_online_json.h"
#include "manager_online_http.h"
#include "manager_league_auth.h"
#include "master_league_catalog.h"
#include "exhibition_team_catalog.h"
#include "manager_club_picker.h"
#include "loading_popup.h"
#include "competition_hub_navigation.h"
#include "manager_league_hub.h"
#include "manager_league_info.h"
#include "gameplan_layout.h"
#include "gameplan_shapes.h"
#include "gameplan_gesture.h"
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

enum {B=1,A=2,Y=4,X=8,L=16,R=128,UP=1024,DOWN=2048,LEFT=4096,RIGHT=8192};
enum {MO_PLAYERS=MD_PLAN_PLAYERS,MO_OFFERS=128,MO_MATCHES=256,MO_EVENTS=512,MO_TOKENS=32768,MO_FRAMES=128,MO_CHUNKS=22,MO_BUNDLE_TOKENS=360000};
enum {J_COMPAT=1,J_REGISTER,J_LOGIN,J_REFRESH,J_BOOTSTRAP,J_PROFILE,J_COLLECTION,J_SQUAD,J_PLAN,
      J_OFFERS,J_PENDING,J_PAY,J_SELECT,J_GRANT,J_STATUS,J_SCHEDULE,J_STANDINGS,J_RANKING,J_CHAMPIONS,
      J_NEWS,J_LOGOUT,J_HEADER,J_CHUNK,J_EVENTS,J_REPORT,J_SAVE_PLAN,J_JOIN,
      J_CLOCK,J_CLOCK_STATUS,J_PROMO,J_PROMO_STATUS,J_LEAGUE_STATUS,J_PAY_STATUS,
      J_HUB_TABLE,J_HUB_SCHEDULE,J_HUB_NEWS,J_HUB_RANKING,J_PLAN_VERIFY,J_OPPONENT,J_RECORDING,J_PLAYER_FEED,J_MONTHLY,J_HUB_LIVE,J_HISTORY};

enum {MO_PRODUCTION=1,MO_TEST=2};
typedef struct {
  uint32_t magic,version,environment,kind,base_revision;
  char origin[96],account[32],key[37],body[256];
} MoIntent;
typedef struct {uint64_t instance;char key[64],acquired[40];uint32_t purchased;MdRow row;} MoPlayer;
typedef struct {uint64_t id;uint32_t version,team,price,pool,draw,available;char name[64],tier[12],unavailable[40];} MoOffer;
typedef struct {uint64_t id,kickoff,ends,home_club,away_club;uint32_t phase;char home[64],away[64];MdRow row;} MoMatch;
typedef struct {MdPage page;uint32_t focus,opponent;uint64_t opponent_id;} MoRoute;
typedef struct {uint64_t ids[18],duties[9];uint32_t roles[11],x[11],y[11],formation,tactics[4],offside,auto_subs;} MoPlan;
typedef struct {uint32_t at;MdDot dots[23];} MoFrame;
typedef struct {int valid;uint32_t index,count;MoFrame frames[MO_FRAMES];} MoChunk;
typedef struct {uint32_t at,second,kind,side;char name[48],other[48];MdRow row;} MoEvent;
typedef struct {uint64_t generation,cycle;uint32_t environment;char account[32];} MoScope;
typedef struct {uint64_t generation,loading;int kind;MdPage page;MoScope scope;MoHttpRequest http;} MoJob;
typedef struct {uint64_t generation;int kind,safe_get,cached;MdPage page;MoScope scope;char path[192];MoHttpResponse http;} MoResult;
static struct {
  pthread_mutex_t mutex;pthread_cond_t cond;int started,pending,running,ready;MoJob job;MoResult result;
} worker={.mutex=PTHREAD_MUTEX_INITIALIZER,.cond=PTHREAD_COND_INITIALIZER};
static pthread_mutex_t ui_mutex=PTHREAD_MUTEX_INITIALIZER;
static uint64_t generation=1;
static struct {
  int active,busy,modal_busy,compatible,compat_checked,authenticated,cash_known,auth_register,want_plan,force_read;
  int resume_kind,refreshed_retry,busy_kind;MdPage resume_page;char resume_path[192];MoJob queued;
  MdPage page,return_page;uint32_t focus,tab,action,serial,category,club_choice,team;
  char login_id[32],club_name[32],account[32],club_id[32],access[MO_TOKEN_SIZE],refresh[MO_TOKEN_SIZE],register_pin[5];
  char notice[256],notice_title[64],phase[32],league_label[8];
  uint64_t cash,server_anchor,mono_anchor,mono,access_until,cycle,purchase;
  uint32_t wallet_revision,roster_count,joined,waiting,remaining,minimum;
  uint32_t collection_count,club_rank,league_points,overall_rank,reputation,profile_focus,profile_child,history;
  uint32_t plan_revision,plan_focus,plan_picker,plan_menu_focus,plan_field_focus,plan_bench_focus;char plan_json[10000];
  uint32_t plan_buttons,plan_condition;uint64_t plan_hold_at,plan_drag_at;float plan_drag_x,plan_drag_y;
  MoPlan plan,plan_saved;uint32_t plan_dirty,plan_pick,plan_move,plan_menu,plan_save_pending,plan_leave,plan_discard;
  char plan_key[37],plan_body[10000];
  MdPlanPlayer plan_players[MO_PLAYERS];MdDot plan_dots[11];
  uint64_t plan_roster[MO_PLAYERS];uint32_t plan_count;
  MoPlayer players[MO_PLAYERS];uint32_t player_count;
  MdRow purchases[MO_PLAYERS];uint32_t purchases_count,purchases_focus;MdPage purchases_return;
  MoOffer offers[MO_OFFERS];uint32_t offer_count,offer_focus,shop_team,shop_focus,shop_sizes;
  MoPlayer pool[8];uint32_t pool_count,draw,selected,selection_revision,paid_amount,pending_offer;
  uint32_t pending_known,pack_granted;uint64_t pending_at;
  uint64_t opening_at;
  uint32_t pay_uncertain,pay_corrupt,grant_uncertain;char pay_key[37],pay_body[256],grant_key[37];
  MoRoute routes[16],route_origin;uint32_t route_count,route_restore,route_focus;
  MoMatch history_matches[5];uint32_t history_count,history_page,history_total,history_request;uint64_t history_snapshot;
  MoMatch matches[MO_MATCHES];uint32_t match_count,match_group;
  uint32_t cache_environment;uint64_t cache_account,cache_cycle;
  uint64_t match_cycle,schedule_seen,schedule_refresh;
  MdRow rows[MO_MATCHES];uint32_t row_count;
  MdRow standings[MO_MATCHES],rankings[MO_MATCHES],news[MO_MATCHES];uint32_t standing_count,ranking_count,news_count,hub_step,hub_ready;
  MdFeedItem activity[MO_MATCHES],player_feed[2][32];
  uint32_t activity_count,player_feed_count[2],feed_section,player_feed_capable;
  uint32_t monthly_capable,rank_section,rank_page,rank_total,rank_request_section,rank_request_page,rank_tail;
  char rank_snapshot[65],rank_season[40],profile_season[8];
  uint64_t rank_ends,rank_refresh_end;
  uint32_t join_confirm,join_choice,hub_focus,schedule_auto;
  uint64_t join_cycle;
  uint32_t home_badge,away_badge,watch_fail,watch_stalled;uint64_t watch_wait,watermark_changed,next_watch_request;
  uint64_t registration_open,registration_close,match_day_start,match_day_end,rewards_at,next_registration;
  uint64_t phase_started,phase_ends,phase_refresh_end;
  uint32_t calendar_conflict,opponent,opponent_team,opponent_rating,opponent_rank,opponent_points,want_teams;uint64_t opponent_id;char opponent_name[64];
  uint64_t fixture,kickoff;uint32_t duration,chunk_ms,chunk_count,watermark,ended,replay,paused,play_ms;
  uint64_t watch_tick,last_header,last_events;uint32_t timeline_serial;char recording_hash[65],home[64],away[64];
  MoChunk chunks[MO_CHUNKS];MoEvent events[MO_EVENTS];uint32_t event_count,touchline,touchline_focus;
  uint32_t bundle_capable,bundle_ready;
  uint32_t score[2],shots[2],on_target[2];
  uint32_t environment,environment_known,demo_time,promotion_codes,clock_revision,league_known;
  uint32_t input_promo,clock_active,clock_corrupt,promo_corrupt,clock_confirm,clock_choice,bootstrap_shop;
  uint64_t clock_poll_at,clock_loading,clock_wait_started;
  char promo_code[33];MoIntent clock_intent,promo_intent;
} online;
/* The same controller-only keypad as offline; no PIN digits reach a render DTO. */
static char notice[112];
#include "manager_league_pin.inc"
static const char *const role_names[]={"GK","CB","LB","RB","DMF","CMF","LMF","RMF","AMF","LWF","RWF","SS","CF"};
static void copy(char *out,size_t n,const char *in){snprintf(out,n,"%s",in?in:"");}
#include "manager_league_online_cache.inc"
static void message(const char *title,const char *text){if(online.route_restore){online.opponent=online.route_origin.opponent;online.opponent_id=online.route_origin.opponent_id;online.route_restore=0;}copy(online.notice_title,sizeof(online.notice_title),title);copy(online.notice,sizeof(online.notice),text);}
static uint64_t field_u64(const MjDoc *d,int obj,const char *key){uint64_t n=0;mj_u64(d,mj_get(d,obj,key),&n);return n;}
static int required_u32(const MjDoc *d,int obj,const char *key,uint32_t *out){
  uint64_t n;if(!mj_u64(d,mj_get(d,obj,key),&n)||n>UINT32_MAX)return 0;
  *out=(uint32_t)n;return 1;
}
static int field_text(const MjDoc *d,int obj,const char *key,char *out,size_t n){return mj_text(d,mj_get(d,obj,key),out,n);}
static int field_bool(const MjDoc *d,int obj,const char *key){int n=0;mj_bool(d,mj_get(d,obj,key),&n);return n;}
static uint64_t server_now(void){return online.server_anchor+(online.mono>=online.mono_anchor?online.mono-online.mono_anchor:0);}
static int route_page(MdPage p){return p==MD_DASHBOARD||p==MD_TABLE||p==MD_TEAMS_PAGE||p==MD_CLUB_PROFILE||p==MD_OPPONENT_PROFILE||p==MD_TEAM_INFO||p==MD_COLLECTION_PAGE||p==MD_TEAM_HISTORY||p==MD_CLUB_PLAN||p==MD_OVERALL||p==MD_SCHEDULE||p==MD_WATCH||p==MD_REWARDS;}
static void change_page(MdPage page){
  if(online.route_restore){online.focus=online.route_focus;online.route_restore=0;if(online.route_count)online.route_count--;}
  else {if(page!=online.page&&route_page(page)&&route_page(online.page)&&page!=MD_DASHBOARD&&online.route_count<16){
    online.routes[online.route_count++]=(MoRoute){online.page,online.focus,online.opponent,online.opponent_id};}online.focus=0;}
  if(page==MD_DASHBOARD)online.route_count=0;
  online.page=page;online.serial++;
}
static void route_back(void);
static void history_open(uint32_t page,int reset);
static uint32_t role(const char *name){for(uint32_t i=0;i<13;i++)if(!strcmp(name,role_names[i]))return i;return 13;}
static uint32_t identity(const char *key){
  char *end=NULL;const char *p;uint32_t flag=0;
  if(!strncmp(key,"ef:",3))p=key+3;else if(!strncmp(key,"fl26:",5)){p=key+5;flag=0x80000000u;}else return 0;
  if(!*p||*p=='0')return 0;
  for(const char *c=p;*c;c++)if(*c<'0'||*c>'9')return 0;
  errno=0;unsigned long n=strtoul(p,&end,10);return !errno && end!=p && !*end && n && n<0x80000000ul?(uint32_t)n|flag:0;
}
static int parse_player(const MjDoc *d,int object,MoPlayer *p){
  memset(p,0,sizeof(*p));
  if(!mj_u64(d,mj_get(d,object,"instance_id"),&p->instance))p->instance=0;
  if(!field_text(d,object,"player_key",p->key,sizeof(p->key))||!identity(p->key))return 0;
  char origin[24];p->purchased=field_text(d,object,"origin",origin,sizeof(origin))&&!strcmp(origin,"PACK");
  field_text(d,object,"acquired_at",p->acquired,sizeof(p->acquired));
  if(!field_text(d,object,"display_name",p->row.label,sizeof(p->row.label)))copy(p->row.label,sizeof(p->row.label),"PLAYER");
  char position[16];if(!field_text(d,object,"position",position,sizeof(position)))return 0;
  p->row.role=role(position);p->row.rating=(uint32_t)field_u64(d,object,"display_ovr");
  if(p->row.role>=13||!p->row.rating||p->row.rating>99)return 0;
  p->row.identity=identity(p->key);p->row.enabled=1;
  const MlCatalogPlayer *binding=ml_catalog_find_identity(p->row.identity);
  if(binding){p->row.native_id=binding->native_id;p->row.portrait=binding->portrait_id;}
  copy(p->row.detail,sizeof(p->row.detail),position);snprintf(p->row.value,sizeof(p->row.value),"%u",p->row.rating);return 1;
}
static int payment_intent_write(const MoHttpRequest *request);
static void payment_intent_clear(void);
static int service_intent_prepare(int kind,MoHttpRequest *request);
static void *http_worker(void *unused){
  (void)unused;
  for(;;){
    pthread_mutex_lock(&worker.mutex);while(!worker.pending)pthread_cond_wait(&worker.cond,&worker.mutex);
    MoJob job=worker.job;mo_wipe(&worker.job,sizeof(worker.job));worker.pending=0;worker.running=1;pthread_mutex_unlock(&worker.mutex);
    MoResult result={.generation=job.generation,.kind=job.kind,.page=job.page,.scope=job.scope,.safe_get=!strcmp(job.http.method,"GET")};
    copy(result.path,sizeof(result.path),job.http.path);mo_http_perform(&job.http,&result.http);
    mo_wipe(&job.http,sizeof(job.http));
    pthread_mutex_lock(&worker.mutex);
    if(worker.ready)mo_http_free(&worker.result.http);
    worker.result=result;worker.ready=1;worker.running=0;pthread_mutex_unlock(&worker.mutex);
    if(job.loading)nx_loading_finish(job.loading);
  }
  return NULL;
}
static int request(int kind,const char *method,const char *path,const char *body,int modal){
  /* One foreground action may wait behind a badge GET. Prepare its exact
   * request/journal now, and dispatch only after the worker releases its slot. */
  int queue=online.busy&&online.busy_kind==J_HUB_LIVE&&kind!=J_HUB_LIVE&&!online.queued.kind;
  if(online.busy&&!queue)return 0;
  if(!online.compatible&&kind!=J_COMPAT&&kind!=J_LOGOUT){message("UPDATE REQUIRED","Reconnect to check the online version and player catalog before continuing.");return 0;}
  if((kind==J_CLOCK||kind==J_CLOCK_STATUS)&&
      (!online.authenticated||online.environment!=MO_TEST||!online.demo_time)){
    message("ONLINEDEV UNAVAILABLE","Demo time is available only for the server-authorized DEV account in TEST.");return 0;
  }
  if((kind==J_PROMO||kind==J_PROMO_STATUS)&&(!online.authenticated||!online.promotion_codes)){
    message("PROMOTION CODES","Promotion-code redemption is not enabled by this server yet.");return 0;
  }
  pthread_mutex_lock(&worker.mutex);
  if(!queue&&(worker.running||worker.pending||worker.ready)){pthread_mutex_unlock(&worker.mutex);return 0;}
  if(!worker.started){pthread_t thread;if(pthread_create(&thread,NULL,http_worker,NULL)){
      pthread_mutex_unlock(&worker.mutex);message("CONNECTION UNAVAILABLE","The online worker could not start. Please try again.");return 0;
    }pthread_detach(thread);worker.started=1;}
  MoJob *j=queue?&online.queued:&worker.job;memset(j,0,sizeof(*j));j->kind=kind;j->generation=generation;j->page=online.page;
  j->scope.generation=generation;j->scope.cycle=online.cycle;j->scope.environment=online.environment;
  copy(j->scope.account,sizeof(j->scope.account),online.account);
  copy(j->http.method,sizeof(j->http.method),method);copy(j->http.path,sizeof(j->http.path),path);
  if(body && strlen(body)>=sizeof(j->http.body)){mo_wipe(j,sizeof(*j));pthread_mutex_unlock(&worker.mutex);message("REQUEST TOO LARGE","This operation cannot be sent safely.");return 0;}
  copy(j->http.body,sizeof(j->http.body),body);copy(j->http.access,sizeof(j->http.access),online.access);
  j->http.environment=online.authenticated?online.environment:0;
  if(strcmp(method,"GET") && !mo_random_key(j->http.key)){
    mo_wipe(j,sizeof(*j));pthread_mutex_unlock(&worker.mutex);message("PLEASE TRY AGAIN","A secure request ID could not be created.");return 0;
  }
  if(kind==J_PAY&&online.pay_uncertain){
    copy(j->http.key,sizeof(j->http.key),online.pay_key);copy(j->http.body,sizeof(j->http.body),online.pay_body);
  }
  if(kind==J_SAVE_PLAN&&online.plan_key[0])copy(j->http.key,sizeof(j->http.key),online.plan_key);
  if(kind==J_SAVE_PLAN&&!online.plan_key[0])copy(online.plan_key,sizeof(online.plan_key),j->http.key);
  if(kind==J_GRANT){if(online.grant_key[0])copy(j->http.key,sizeof(j->http.key),online.grant_key);else copy(online.grant_key,sizeof(online.grant_key),j->http.key);}
  if(kind==J_PAY&&!payment_intent_write(&j->http)){
    mo_wipe(j,sizeof(*j));pthread_mutex_unlock(&worker.mutex);
    message("PURCHASE NOT SENT","The payment recovery record could not be saved. Check the SD card and try again.");return 0;
  }
  if((kind==J_CLOCK||kind==J_PROMO)&&!service_intent_prepare(kind,&j->http)){
    mo_wipe(j,sizeof(*j));pthread_mutex_unlock(&worker.mutex);
    message("REQUEST NOT SENT","The recovery record could not be saved. Check the SD card and try again.");return 0;
  }
  if(modal||queue)j->loading=nx_loading_begin("CONNECTING","Contacting the FootballNX server...");
  if(kind==J_COMPAT){online.compatible=0;online.compat_checked=0;}
  online.busy=1;online.busy_kind=kind;online.modal_busy=modal||queue;
  if(!queue){worker.pending=1;pthread_cond_signal(&worker.cond);}
  pthread_mutex_unlock(&worker.mutex);return 1;
}
static int get(int kind,const char *path){return (!online.force_read&&read_cache_get(kind,path))||request(kind,"GET",path,NULL,1);}
static void refresh_bootstrap(void){get(J_BOOTSTRAP,"/me/bootstrap");}
static void auth_clear(void){
  read_cache_clear();
  if(online.queued.loading)nx_loading_finish(online.queued.loading);
  mo_wipe(&online.queued,sizeof(online.queued));
  if(online.clock_loading)nx_loading_finish(online.clock_loading);
  online.clock_loading=0;online.clock_active=0;
  pin_clear();mo_wipe(online.access,sizeof(online.access));mo_wipe(online.refresh,sizeof(online.refresh));
  mo_wipe(online.promo_code,sizeof(online.promo_code));mo_wipe(&online.clock_intent,sizeof(online.clock_intent));mo_wipe(&online.promo_intent,sizeof(online.promo_intent));
  online.authenticated=online.cash_known=online.environment_known=online.demo_time=online.promotion_codes=online.input_promo=0;
  online.environment=MO_PRODUCTION;online.resume_kind=online.refreshed_retry=0;online.pay_uncertain=online.grant_uncertain=0;
}
static void auth_submit(void){
  char normalized[32];
  if(!md_auth_id(normalized,online.login_id)||!pin_confirmed){message("ACCOUNT DETAILS","Enter your User ID and four-digit PIN first.");return;}
  copy(online.login_id,sizeof(online.login_id),normalized);
  char id[80],pin[16],club[100],body[512];
  if(!mj_quote(online.login_id,id,sizeof(id))||!mj_quote(pin_value,pin,sizeof(pin)))return;
  if(online.auth_register){
    if(strlen(online.club_name)<3||!manager_club_team_allowed(online.team)){message("CLUB DETAILS","Choose a club and enter a team name of at least three characters.");return;}
    if(!mj_quote(online.club_name,club,sizeof(club)))return;
    snprintf(body,sizeof(body),"{\"user_id\":%s,\"pin\":%s,\"club_name\":%s,\"presentation_team_id\":%u}",id,pin,club,online.team);
    memcpy(online.register_pin,pin_value,sizeof(online.register_pin));
    if(!request(J_REGISTER,"POST","/auth/register",body,1))mo_wipe(online.register_pin,sizeof(online.register_pin));
  }else{snprintf(body,sizeof(body),"{\"user_id\":%s,\"pin\":%s,\"device_label\":\"Nintendo Switch\"}",id,pin);request(J_LOGIN,"POST","/auth/login",body,1);}
  mo_wipe(body,sizeof(body));mo_wipe(pin,sizeof(pin));pin_clear();
}
static int parse_purchase(const MjDoc *d,int object){
  uint64_t purchase=0;int pool=mj_get(d,object,"pool");char state[40];
  if(!field_text(d,object,"state",state,sizeof(state))||strcmp(state,"PAID_PENDING_SELECTION"))return 0;
  if(!mj_u64(d,mj_get(d,object,"purchase_id"),&purchase)||!purchase||!mj_is(d,pool,MJ_ARRAY))return 0;
  uint32_t n=(uint32_t)d->tokens[pool].count,draw=(uint32_t)field_u64(d,object,"select_count");
  if(!((n==5&&draw==2)||(n==6&&draw==4)||(n==8&&draw==5)))return 0;
  MoPlayer players[8];for(uint32_t i=0;i<n;i++){
    if(!parse_player(d,mj_at(d,pool,i),&players[i]))return 0;
    for(uint32_t k=0;k<i;k++)if(!strcmp(players[i].key,players[k].key))return 0;
  }
  uint32_t selected=0;int list=mj_get(d,object,"selected_player_keys");
  if(!mj_is(d,list,MJ_ARRAY)||d->tokens[list].count>(int)draw)return 0;
  for(int i=0;i<d->tokens[list].count;i++){
    char key[64];if(!mj_text(d,mj_at(d,list,i),key,sizeof(key)))return 0;
    uint32_t k=0;while(k<n&&strcmp(key,players[k].key))k++;
    if(k==n||(selected&(1u<<k)))return 0;
    selected|=1u<<k;
  }
  uint32_t revision,amount,offer;
  if(!required_u32(d,object,"selection_revision",&revision)||!revision||
      !required_u32(d,object,"paid_amount",&amount)||!required_u32(d,object,"offer_id",&offer)||!offer)return 0;
  online.purchase=purchase;online.pending_offer=offer;online.pack_granted=0;online.pending_known=1;online.pending_at=online.mono;
  online.pool_count=n;online.draw=draw;online.selected=selected;online.selection_revision=revision;
  online.paid_amount=amount;memcpy(online.pool,players,sizeof(players));return 1;
}
static uint32_t selected_count(void){uint32_t n=0;for(uint32_t i=0;i<online.pool_count;i++)if(online.selected&(1u<<i))n++;return n;}
static void selection_submit(void){
  char list[1024]="",body[1200],path[160];size_t used=0;
  for(uint32_t i=0;i<online.pool_count;i++)if(online.selected&(1u<<i)){
    char quoted[140];if(!mj_quote(online.pool[i].key,quoted,sizeof(quoted)))return;
    int written=snprintf(list+used,sizeof(list)-used,"%s%s",used?",":"",quoted);
    if(written<0||(size_t)written>=sizeof(list)-used)return;
    used+=(size_t)written;
  }
  snprintf(body,sizeof(body),"{\"selected_player_keys\":[%s],\"selection_revision\":%u}",list,online.selection_revision);
  snprintf(path,sizeof(path),"/shop/purchases/%llu/grant",(unsigned long long)online.purchase);
  if(request(J_GRANT,"POST",path,body,1))online.grant_uncertain=1;
}
/* Response handlers and the view/controller are kept below; network requests
 * never mutate an offline save or run a local match simulator. */
#include "manager_league_online_services.inc"
static uint32_t hub_phase(void);
static uint64_t hub_phase_end(void);
#include "manager_league_online_state.inc"
#include "manager_league_online_view.inc"

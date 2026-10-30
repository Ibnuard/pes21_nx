/* Session-only, bounded read cache. Writes, receipts, auth and live recordings
 * always reach the server. Cached responses never re-anchor the server clock.
 * Account/realm/cycle changes and successful writes invalidate this cache. */
typedef struct {int kind;char path[192];char *body;size_t size;uint64_t at;} MoReadCache;
static MoReadCache read_cache[16];
static int read_cache_kind(int kind){
  switch(kind){
    case J_HUB_TABLE:return J_STANDINGS;
    case J_HUB_NEWS:return J_NEWS;
    case J_HUB_SCHEDULE:case J_HUB_LIVE:return J_SCHEDULE;
    case J_STATUS:return J_PROFILE;
    case J_PLAN_VERIFY:return J_PLAN;
    default:return kind;
  }
}
static uint64_t read_cache_ttl(int kind){
  switch(read_cache_kind(kind)){
    case J_COLLECTION:case J_SQUAD:case J_PLAN:return 120000;
    case J_OFFERS:return 60000;
    case J_PROFILE:case J_STANDINGS:case J_NEWS:case J_SCHEDULE:case J_OPPONENT:return 30000;
    default:return 0;
  }
}
static void read_cache_clear(void){
  for(unsigned i=0;i<16;i++){free(read_cache[i].body);memset(&read_cache[i],0,sizeof(read_cache[i]));}
}
static void read_cache_drop(int kind){
  for(unsigned i=0;i<16;i++)if(read_cache[i].kind==read_cache_kind(kind)){free(read_cache[i].body);memset(&read_cache[i],0,sizeof(read_cache[i]));}
}
static int read_cache_get(int kind,const char *path){
  if(online.busy||!online.authenticated||!online.compatible||kind==J_PLAN_VERIFY||!read_cache_ttl(kind))return 0;
  for(unsigned i=0;i<16;i++){
    MoReadCache *c=&read_cache[i];
    if(c->kind!=read_cache_kind(kind)||strcmp(c->path,path)||online.mono<c->at||online.mono-c->at>=read_cache_ttl(kind))continue;
    char *body=malloc(c->size+1);if(!body)return 0;memcpy(body,c->body,c->size+1);
    pthread_mutex_lock(&worker.mutex);
    if(worker.running||worker.pending||worker.ready){pthread_mutex_unlock(&worker.mutex);free(body);return 0;}
    worker.result=(MoResult){.generation=generation,.kind=kind,.safe_get=1,.cached=1,.page=online.page};
    copy(worker.result.path,sizeof(worker.result.path),path);
    worker.result.http.body=body;worker.result.http.size=c->size;worker.result.http.status=200;
    worker.ready=1;online.busy=1;online.busy_kind=kind;online.modal_busy=0;
    pthread_mutex_unlock(&worker.mutex);return 1;
  }
  return 0;
}
static void read_cache_store(const MoResult *result){
  if(result->cached||!result->safe_get||!read_cache_ttl(result->kind)||result->http.size>131072)return;
  int kind=read_cache_kind(result->kind);unsigned at=0;
  for(unsigned i=0;i<16;i++){
    if(read_cache[i].kind==kind&&!strcmp(read_cache[i].path,result->path)){at=i;break;}
    if(!read_cache[i].body||read_cache[i].at<read_cache[at].at)at=i;
  }
  char *body=malloc(result->http.size+1);if(!body)return;
  memcpy(body,result->http.body,result->http.size);body[result->http.size]=0;
  free(read_cache[at].body);read_cache[at]=(MoReadCache){.kind=kind,.body=body,.size=result->http.size,.at=online.mono};
  copy(read_cache[at].path,sizeof(read_cache[at].path),result->path);
}

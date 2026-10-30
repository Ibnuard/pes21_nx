/* Account-authorized TEST clock and CDK. No local clock/balance mutation. */
#define MO_INTENT_MAGIC 0x4d4f4931u
static const char *environment_name(uint32_t environment){return environment==MO_TEST?"TEST":"PRODUCTION";}
static int parse_environment(const MjDoc *d,int object,uint32_t *out,int required){
  int token=mj_get(d,object,"environment");char value[24];
  if(token<0&&!required){*out=MO_PRODUCTION;return 1;}
  if(!mj_text(d,token,value,sizeof(value)))return 0;
  if(!strcmp(value,"TEST"))*out=MO_TEST;
  else if(!strcmp(value,"PRODUCTION"))*out=MO_PRODUCTION;
  else return 0;
  return 1;
}
static int account_path(char out[160],const char *service){
  if(!online.account[0]||!online.environment_known)return 0;
  for(const char *p=online.account;*p;p++)if(*p<'0'||*p>'9')return 0;
  return snprintf(out,160,"SaveData/manager-online-%s-%s-%s.dat",service,environment_name(online.environment),online.account)<160;
}
static MoIntent *service_intent(int kind){return kind==J_CLOCK||kind==J_CLOCK_STATUS?&online.clock_intent:&online.promo_intent;}
static const char *service_name(int kind){return kind==J_CLOCK||kind==J_CLOCK_STATUS?"clock":"promotion";}
static uint32_t *service_corrupt(int kind){return kind==J_CLOCK||kind==J_CLOCK_STATUS?&online.clock_corrupt:&online.promo_corrupt;}
static int intent_valid(const MoIntent *intent,int kind){
  if(intent->magic!=MO_INTENT_MAGIC||intent->version!=1||intent->kind!=(uint32_t)kind||intent->environment!=online.environment||
      !memchr(intent->origin,0,sizeof(intent->origin))||strcmp(intent->origin,MANAGER_ONLINE_BASE)||
      !memchr(intent->account,0,sizeof(intent->account))||strcmp(intent->account,online.account)||
      !memchr(intent->key,0,sizeof(intent->key))||strlen(intent->key)!=36||
      !memchr(intent->body,0,sizeof(intent->body))||!intent->body[0])return 0;
  for(unsigned i=0;i<36;i++)if(i==8||i==13||i==18||i==23){if(intent->key[i]!='-')return 0;}
    else if(!((intent->key[i]>='0'&&intent->key[i]<='9')||(intent->key[i]>='a'&&intent->key[i]<='f')))return 0;
  return 1;
}
static void service_intent_load(int kind){
  char path[160],temporary[168];MoIntent value={0};MoIntent *intent=service_intent(kind);
  mo_wipe(intent,sizeof(*intent));*service_corrupt(kind)=0;
  if(!account_path(path,service_name(kind)))return;
  snprintf(temporary,sizeof(temporary),"%s.tmp",path);
  FILE *f=fopen(path,"rb");if(!f)f=fopen(temporary,"rb");if(!f)return;
  int ok=fread(&value,1,sizeof(value),f)==sizeof(value)&&fgetc(f)==EOF;fclose(f);
  if(ok&&intent_valid(&value,kind))*intent=value;else *service_corrupt(kind)=1;
  mo_wipe(&value,sizeof(value));
}
static int service_intent_prepare(int kind,MoHttpRequest *request){
  MoIntent *intent=service_intent(kind);if(*service_corrupt(kind))return 0;
  if(intent->magic){
    if(!intent_valid(intent,kind))return 0;
    copy(request->key,sizeof(request->key),intent->key);copy(request->body,sizeof(request->body),intent->body);return 1;
  }
  char path[160],temporary[168];if(!account_path(path,service_name(kind))||strlen(request->body)>=sizeof(intent->body))return 0;
  MoIntent value={.magic=MO_INTENT_MAGIC,.version=1,.environment=online.environment,.kind=(uint32_t)kind,
    .base_revision=kind==J_CLOCK?online.clock_revision:0};
  copy(value.origin,sizeof(value.origin),MANAGER_ONLINE_BASE);copy(value.account,sizeof(value.account),online.account);
  copy(value.key,sizeof(value.key),request->key);copy(value.body,sizeof(value.body),request->body);
  snprintf(temporary,sizeof(temporary),"%s.tmp",path);mkdir("SaveData",0700);FILE *f=fopen(temporary,"wb");int ok=0;
  if(f){ok=fwrite(&value,1,sizeof(value),f)==sizeof(value)&&!fflush(f)&&!fsync(fileno(f));if(fclose(f))ok=0;}
  if(ok&&rename(temporary,path))ok=0;
  if(ok)*intent=value;else remove(temporary);
  mo_wipe(&value,sizeof(value));return ok;
}
static void service_intent_clear(int kind){
  char path[160],temporary[168];
  if(account_path(path,service_name(kind))){snprintf(temporary,sizeof(temporary),"%s.tmp",path);remove(path);remove(temporary);}
  mo_wipe(service_intent(kind),sizeof(MoIntent));*service_corrupt(kind)=0;
}
static int parse_service_context(const MjDoc *d,int data,int login){
  uint32_t environment;
  if(!parse_environment(d,data,&environment,0))return 0;
  if((!login||online.authenticated)&&online.environment_known&&environment!=online.environment)return 0;
  int capabilities=mj_get(d,data,"capabilities"),demo=field_bool(d,capabilities,"demo_time"),promo=field_bool(d,capabilities,"promotion_codes");
  uint32_t revision=0;
  if(environment==MO_TEST){
    if(!mj_is(d,capabilities,MJ_OBJECT)||!required_u32(d,mj_get(d,data,"test_clock"),"revision",&revision)||!revision)return 0;
    if(online.environment_known&&revision<online.clock_revision)return 0;
  }else if(demo)return 0;
  online.environment=environment;online.environment_known=1;online.demo_time=(uint32_t)demo;online.promotion_codes=(uint32_t)promo;online.clock_revision=revision;
  return 1;
}
static void clock_finish_loading(void){
  if(online.clock_loading)nx_loading_finish(online.clock_loading);
  online.clock_loading=0;online.clock_active=0;
}
static void clock_begin_loading(void){
  if(!online.clock_active)online.clock_wait_started=online.mono;
  online.clock_active=1;
  if(!online.clock_loading)online.clock_loading=nx_loading_begin("ADVANCING TEST TIME","Processing TEST fixtures, results and rewards on the server...");
}
static void service_lookup(int kind){
  MoIntent *intent=service_intent(kind);if(!intent->magic)return;
  char path[160];snprintf(path,sizeof(path),"%s/%s",kind==J_CLOCK_STATUS?"/dev/clock/operations":"/promotions/operations",intent->key);
  if(request(kind,"GET",path,NULL,kind!=J_CLOCK_STATUS)&&kind==J_CLOCK_STATUS)clock_begin_loading();
}
static void clock_submit(uint32_t action){
  if(online.environment!=MO_TEST||!online.demo_time){message("ONLINEDEV UNAVAILABLE","The server has not authorized TEST demo time for this account.");return;}
  if(online.clock_corrupt){message("RECOVERY RECORD","The TEST clock recovery record cannot be read. Keep it for support before advancing again.");return;}
  char body[160];snprintf(body,sizeof(body),"{\"action\":\"%s\",\"expected_revision\":%u}",action==1?"FINISH_WEEK":"NEXT_MILESTONE",online.clock_revision);
  if(request(J_CLOCK,"POST","/dev/clock/advance",online.clock_intent.magic?online.clock_intent.body:body,0))clock_begin_loading();
}
static int clock_consume(const MjDoc *d,int data){
  char state[24];uint32_t environment,revision;uint64_t now;
  if(!parse_environment(d,data,&environment,1)||environment!=MO_TEST||!online.demo_time||
      !field_text(d,data,"state",state,sizeof(state))||field_u64(d,data,"account_id")!=strtoull(online.account,NULL,10))return 0;
  char key[37];if(!field_text(d,data,"idempotency_key",key,sizeof(key))||strcmp(key,online.clock_intent.key))return 0;
  if(!strcmp(state,"PENDING")||!strcmp(state,"RUNNING")){clock_begin_loading();online.clock_poll_at=online.mono+1000;return 1;}
  if(!strcmp(state,"FAILED")){
    service_intent_clear(J_CLOCK);clock_finish_loading();message("TEST TIME STOPPED","The server stopped this TEST operation. Refresh the league before advancing again.");return 1;
  }
  if(strcmp(state,"SUCCEEDED")||!required_u32(d,data,"clock_revision",&revision)||revision<=online.clock_intent.base_revision||
      !mj_u64(d,mj_get(d,data,"test_now_ms"),&now)||!now)return 0;
  if(revision>online.clock_revision)online.clock_revision=revision;
  if(now>online.server_anchor){online.server_anchor=now;online.mono_anchor=online.mono;}
  service_intent_clear(J_CLOCK);clock_finish_loading();
  online.timeline_serial++;online.fixture=online.event_count=online.touchline=online.match_count=online.row_count=0;
  online.watermark=online.play_ms=0;online.recording_hash[0]=0;memset(online.chunks,0,sizeof(online.chunks));
  change_page(MD_DASHBOARD);refresh_bootstrap();return 1;
}
static int normalize_promo(const char *text,char out[33]){
  unsigned n=0;if(!text)return 0;
  for(const unsigned char *p=(const unsigned char *)text;*p;p++){
    unsigned char c=*p;if(c==' '||c=='-')continue;if(c>='a'&&c<='z')c=(unsigned char)(c-'a'+'A');
    if(!((c>='A'&&c<='Z')||(c>='0'&&c<='9'))||n>=32){mo_wipe(out,33);return 0;}out[n++]=(char)c;
  }
  out[n]=0;if(n<12){mo_wipe(out,33);return 0;}return 1;
}
static void promotion_submit(void){
  if(online.promo_corrupt){message("RECOVERY RECORD","The promotion recovery record cannot be read. Keep it for support before redeeming another code.");return;}
  if(!online.promo_intent.magic&&!online.promo_code[0]){message("PROMOTION CODE","Enter your promotion code first.");return;}
  char body[100];snprintf(body,sizeof(body),"{\"code\":\"%s\"}",online.promo_code);
  if(request(J_PROMO,"POST","/promotions/redeem",online.promo_intent.magic?online.promo_intent.body:body,1))mo_wipe(online.promo_code,sizeof(online.promo_code));
  mo_wipe(body,sizeof(body));
}
static int promotion_consume(const MjDoc *d,int data){
  char state[24],currency[24],key[37];uint32_t environment,version;uint64_t balance,amount;
  if(!field_text(d,data,"state",state,sizeof(state))||!parse_environment(d,data,&environment,1)||environment!=online.environment||
      field_u64(d,data,"account_id")!=strtoull(online.account,NULL,10)||
      !field_text(d,data,"idempotency_key",key,sizeof(key))||strcmp(key,online.promo_intent.key))return 0;
  if(!strcmp(state,"PENDING")){message("REDEMPTION PENDING","The server is checking your code. Press Y to check the same redemption again.");return 1;}
  int wallet=mj_get(d,data,"wallet");
  if(strcmp(state,"SUCCEEDED")||!field_u64(d,data,"redemption_id")||
      !field_text(d,data,"currency",currency,sizeof(currency))||strcmp(currency,"NX_CASH")||!mj_u64(d,mj_get(d,data,"amount"),&amount)||!amount||amount>INT64_MAX||
      !required_u32(d,wallet,"version",&version)||!version||!mj_u64(d,mj_get(d,wallet,"balance"),&balance)||balance>INT64_MAX)return 0;
  if(version==online.wallet_revision&&online.cash_known&&balance!=online.cash)return 0;
  if(!online.cash_known||version>online.wallet_revision){online.cash=balance;online.wallet_revision=version;online.cash_known=1;}
  service_intent_clear(J_PROMO);mo_wipe(online.promo_code,sizeof(online.promo_code));
  char text[128];snprintf(text,sizeof(text),"%llu NX Cash received.",(unsigned long long)amount);
  change_page(online.shop_sizes?MD_SHOP:MD_SHOP_CLUBS);message("PROMOTION REDEEMED",text);
  return 1;
}

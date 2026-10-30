/* Bounded API response -> immutable client display state. */
#define MO_SESSION_FILE "SaveData/manager-online-session-v2.dat"
typedef struct {uint32_t magic,version;char origin[96],refresh[MO_TOKEN_SIZE],user[32];uint32_t environment;} MoSession;
/* Keep the original UUID/body so recovery never creates a second payment. */
static int payment_path(char path[160]){
  if(!online.account[0])return 0;
  for(const char *p=online.account;*p;p++)if(*p<'0'||*p>'9')return 0;
  /* Keep legacy production intents discoverable; TEST IDs can overlap safely. */
  snprintf(path,160,online.environment==MO_TEST?"SaveData/manager-online-pay-TEST-%s.dat":"SaveData/manager-online-pay-%s.dat",online.account);return 1;
}
static int payment_intent_write(const MoHttpRequest *request){
  if(online.pay_uncertain)return !online.pay_corrupt&&!strcmp(request->key,online.pay_key)&&!strcmp(request->body,online.pay_body);
  char path[160],temporary[168];if(!payment_path(path))return 0;
  snprintf(temporary,sizeof(temporary),"%s.tmp",path);mkdir("SaveData",0700);
  /* Never replace an older payment record, even if its in-memory flag was lost. */
  struct stat old;if(!stat(path,&old)||!stat(temporary,&old))return 0;
  FILE *f=fopen(temporary,"wb");if(!f)return 0;
  int ok=fwrite(request->key,1,36,f)==36&&fwrite(request->body,1,strlen(request->body),f)==strlen(request->body)&&!fflush(f)&&!fsync(fileno(f));
  if(fclose(f))ok=0;
  if(ok&&rename(temporary,path))ok=0;
  if(!ok)remove(temporary);
  if(ok){copy(online.pay_key,sizeof(online.pay_key),request->key);copy(online.pay_body,sizeof(online.pay_body),request->body);}
  return ok;
}
static void payment_intent_load(void){
  online.pay_uncertain=online.pay_corrupt=0;online.pay_key[0]=online.pay_body[0]=0;
  char path[160],temporary[168];if(!payment_path(path))return;
  snprintf(temporary,sizeof(temporary),"%s.tmp",path);
  FILE *f=fopen(path,"rb");if(!f)f=fopen(temporary,"rb");
  if(f){
    online.pay_uncertain=1;char record[293]={0};size_t n=fread(record,1,sizeof(record)-1,f);int complete=fgetc(f)==EOF;fclose(f);
    if(n<=36||n-36>=sizeof(online.pay_body)||!complete){online.pay_corrupt=1;return;}
    memcpy(online.pay_key,record,36);memcpy(online.pay_body,record+36,n-36);online.pay_body[n-36]=0;
    MoIntent check={.magic=MO_INTENT_MAGIC,.version=1,.environment=online.environment,.kind=J_PAY};
    copy(check.origin,sizeof(check.origin),MANAGER_ONLINE_BASE);copy(check.account,sizeof(check.account),online.account);
    copy(check.key,sizeof(check.key),online.pay_key);copy(check.body,sizeof(check.body),online.pay_body);
    MjToken tokens[32];MjDoc body;
    if(!intent_valid(&check,J_PAY)||!mj_parse(&body,online.pay_body,strlen(online.pay_body),tokens,32)||
        !field_u64(&body,0,"offer_id")||!field_u64(&body,0,"offer_version")||!field_u64(&body,0,"accepted_price_nx_cash"))online.pay_corrupt=1;
    mo_wipe(record,sizeof(record));mo_wipe(&check,sizeof(check));
  }
}
static void payment_intent_clear(void){
  char path[160],temporary[168];if(!payment_path(path))return;
  snprintf(temporary,sizeof(temporary),"%s.tmp",path);remove(path);remove(temporary);online.pay_uncertain=online.pay_corrupt=0;online.pay_key[0]=online.pay_body[0]=0;
}
static void payment_lookup(void){
  if(!online.pay_uncertain)return;
  if(online.pay_corrupt){message("PAYMENT RECOVERY","The saved payment record is damaged. Keep the SD card record for support. You can leave Shop and use the rest of your club.");return;}
  char path[160];snprintf(path,sizeof(path),"/shop/operations/%s",online.pay_key);get(J_PAY_STATUS,path);
}
static int token_valid(const char *s){size_t n=strlen(s);if(n<16||n>=MO_TOKEN_SIZE)return 0;for(size_t i=0;i<n;i++)if((unsigned char)s[i]<33||(unsigned char)s[i]>126)return 0;return 1;}
static int session_write(void){
  MoSession session={.magic=0x4d4f5331u,.version=2,.environment=online.environment};
  copy(session.origin,sizeof(session.origin),MANAGER_ONLINE_BASE);copy(session.refresh,sizeof(session.refresh),online.refresh);copy(session.user,sizeof(session.user),online.login_id);
  mkdir("SaveData",0700);FILE *f=fopen(MO_SESSION_FILE ".tmp","wb");int ok=0;
  if(f){ok=fwrite(&session,1,sizeof(session),f)==sizeof(session)&&!fflush(f);if(fclose(f))ok=0;}
  if(ok){remove(MO_SESSION_FILE ".bak");FILE *old=fopen(MO_SESSION_FILE,"rb");if(old){fclose(old);if(rename(MO_SESSION_FILE,MO_SESSION_FILE ".bak"))ok=0;}
    if(ok&&rename(MO_SESSION_FILE ".tmp",MO_SESSION_FILE)){rename(MO_SESSION_FILE ".bak",MO_SESSION_FILE);ok=0;}}
  if(!ok)remove(MO_SESSION_FILE ".tmp");
  mo_wipe(&session,sizeof(session));return ok;
}
static int session_load(void){
  const char *paths[]={MO_SESSION_FILE,MO_SESSION_FILE ".bak"};
  for(unsigned i=0;i<2;i++){
    MoSession session={0};FILE *f=fopen(paths[i],"rb");if(!f)continue;
    int ok=fread(&session,1,sizeof(session),f)==sizeof(session)&&fgetc(f)==EOF;fclose(f);
    if(ok && session.magic==0x4d4f5331u&&session.version==2&&(session.environment==MO_PRODUCTION||session.environment==MO_TEST)&&memchr(session.origin,0,sizeof(session.origin))&&
        memchr(session.refresh,0,sizeof(session.refresh))&&memchr(session.user,0,sizeof(session.user))&&
        !strcmp(session.origin,MANAGER_ONLINE_BASE)&&token_valid(session.refresh)){
      online.environment=session.environment;online.environment_known=1;
      copy(online.refresh,sizeof(online.refresh),session.refresh);copy(online.login_id,sizeof(online.login_id),session.user);mo_wipe(&session,sizeof(session));return 1;
    }mo_wipe(&session,sizeof(session));
  }return 0;
}
static void session_remove(void){remove(MO_SESSION_FILE);remove(MO_SESSION_FILE ".bak");remove(MO_SESSION_FILE ".tmp");
  /* Old release sessions require a fresh login, and cannot restore after logout. */
  remove("SaveData/manager-online-session-v1.dat");remove("SaveData/manager-online-session-v1.dat.bak");remove("SaveData/manager-online-session-v1.dat.tmp");}
static int refresh_submit(void){
  if(!token_valid(online.refresh))return 0;
  char token[1100],body[1200];if(!mj_quote(online.refresh,token,sizeof(token)))return 0;
  snprintf(body,sizeof(body),"{\"refresh_token\":%s}",token);int ok=request(J_REFRESH,"POST","/auth/refresh",body,!online.authenticated);
  mo_wipe(token,sizeof(token));mo_wipe(body,sizeof(body));return ok;
}
static void parse_calendar(const MjDoc *d,int data){
  online.phase_started=field_u64(d,data,"phase_started_at_ms");online.phase_ends=field_u64(d,data,"phase_ends_at_ms");
  if(online.phase_ends&&online.phase_ends<=online.phase_started)online.phase_ends=0;
  online.registration_open=field_u64(d,data,"registration_open_ms");online.registration_close=field_u64(d,data,"registration_close_ms");
  online.match_day_start=field_u64(d,data,"first_kickoff_ms");online.match_day_end=field_u64(d,data,"last_full_time_ms");
  online.rewards_at=field_u64(d,data,"rewards_at_ms");online.next_registration=field_u64(d,data,"next_registration_at_ms");
}
static void format_date(uint64_t ms,char *out,size_t capacity){
  if(!ms){copy(out,capacity,"TIME TO BE ANNOUNCED");return;}
  time_t seconds=(time_t)(ms/1000+7*3600);struct tm date;
  if(!gmtime_r(&seconds,&date)){copy(out,capacity,"TIME TO BE ANNOUNCED");return;}
  strftime(out,capacity,"%d %b %H:%M WIB",&date);
}
/* Presentation caches belong to one account, realm and league cycle. Recovery
 * journals and an unsaved Game Plan remain separate from these display caches. */
static void clear_league_cache(void){
  read_cache_clear();online.pending_known=0;
  online.row_count=online.standing_count=online.ranking_count=online.news_count=0;
  online.activity_count=online.player_feed_count[0]=online.player_feed_count[1]=0;
  online.match_count=online.match_group=0;online.match_cycle=online.schedule_seen=online.schedule_refresh=0;
  online.club_rank=online.league_points=online.overall_rank=online.reputation=0;
  online.profile_season[0]=online.rank_season[0]=online.rank_snapshot[0]=0;
  online.rank_ends=online.rank_refresh_end=online.rank_total=online.rank_page=0;
  online.opponent=online.opponent_rank=online.opponent_points=online.want_teams=online.history=0;
  online.player_count=online.roster_count=online.collection_count=0;
  online.event_count=online.bundle_ready=online.touchline=0;
  online.calendar_conflict=online.profile_child=0;online.phase_refresh_end=0;
  online.phase_started=online.phase_ends=online.registration_open=online.registration_close=0;
  online.match_day_start=online.match_day_end=online.rewards_at=online.next_registration=0;
  memset(online.chunks,0,sizeof(online.chunks));
  online.hub_ready=online.hub_step=0;
}
static void set_cache_scope(uint64_t account,uint64_t cycle){
  /* Authentication can switch realms before bootstrap arrives. Compare with
   * the scope that produced the cache, rather than the current auth realm. */
  if(online.cache_environment!=online.environment||online.cache_account!=account||online.cache_cycle!=cycle)clear_league_cache();
  online.cache_environment=online.environment;online.cache_account=account;online.cache_cycle=cycle;
}
static int parse_bootstrap(const MjDoc *d,int data){
  int account=mj_get(d,data,"account"),club=mj_get(d,data,"club"),wallet=mj_get(d,data,"wallet"),league=mj_get(d,data,"league");
  uint64_t cash=0,id=0,clubid=0,cycle=0;uint32_t version,team,waiting=0,minimum=4,remaining=0;
  char currency[24],name[32],user[32],phase[32]="NOT JOINED",label[8]="";int joined=0;
  if(!mj_u64(d,mj_get(d,account,"id"),&id)||!id||!mj_u64(d,mj_get(d,club,"id"),&clubid)||!clubid||
      !field_text(d,club,"name",name,sizeof(name))||!field_text(d,account,"user_id",user,sizeof(user))||
      !field_text(d,wallet,"currency",currency,sizeof(currency))||strcmp(currency,"NX_CASH")||
      !mj_u64(d,mj_get(d,wallet,"balance"),&cash)||cash>INT64_MAX||
      !required_u32(d,wallet,"version",&version)||!version||
      !required_u32(d,club,"presentation_team_id",&team)||!team)return 0;
  if(!mj_is(d,league,MJ_NULL)){
    if(!mj_u64(d,mj_get(d,league,"cycle_id"),&cycle)||
        !mj_bool(d,mj_get(d,league,"user_joined"),&joined)||
        !required_u32(d,league,"waiting_entry_count",&waiting)||
        !required_u32(d,league,"minimum_entries",&minimum)||minimum!=4||
        !required_u32(d,league,"remaining_needed",&remaining)||
        !field_text(d,league,"state",phase,sizeof(phase))||
        !field_text(d,league,"label",label,sizeof(label)))return 0;
  }
  /* Validate the whole snapshot before publishing its wallet or club identity. */
  if(!parse_service_context(d,data,0))return 0;
  set_cache_scope(id,cycle);
  snprintf(online.account,sizeof(online.account),"%llu",(unsigned long long)id);
  snprintf(online.club_id,sizeof(online.club_id),"%llu",(unsigned long long)clubid);
  copy(online.club_name,sizeof(online.club_name),name);copy(online.login_id,sizeof(online.login_id),user);
  online.cash=cash;online.cash_known=1;online.wallet_revision=version;online.team=team;
  online.bundle_capable=field_bool(d,mj_get(d,data,"capabilities"),"match_recording_bundle");
  online.player_feed_capable=field_bool(d,mj_get(d,data,"capabilities"),"player_feed_v1");
  online.monthly_capable=field_bool(d,mj_get(d,data,"capabilities"),"monthly_ranking_v1");
  payment_intent_load();
  service_intent_load(J_CLOCK);service_intent_load(J_PROMO);
  online.cycle=cycle;online.joined=(uint32_t)joined;online.waiting=waiting;online.minimum=minimum;online.remaining=remaining;
  online.league_known=!mj_is(d,league,MJ_NULL)&&league>=0;
  parse_calendar(d,league);online.hub_ready=0;online.hub_step=0;
  if(strcmp(online.phase,phase))read_cache_clear();
  copy(online.phase,sizeof(online.phase),phase);copy(online.league_label,sizeof(online.league_label),label);return 1;
}
static int parse_league_status(const MjDoc *d,int data){
  if(mj_is(d,data,MJ_NULL)){clear_league_cache();online.cycle=online.league_known=0;copy(online.phase,sizeof(online.phase),"CALENDAR UNAVAILABLE");return 1;}
  uint64_t cycle;uint32_t waiting,minimum,remaining;int joined;char phase[32],label[8];
  if(!mj_u64(d,mj_get(d,data,"cycle_id"),&cycle)||!cycle||
      !mj_bool(d,mj_get(d,data,"user_joined"),&joined)||
      !required_u32(d,data,"waiting_entry_count",&waiting)||
      !required_u32(d,data,"minimum_entries",&minimum)||minimum!=4||
      !required_u32(d,data,"remaining_needed",&remaining)||
      !field_text(d,data,"state",phase,sizeof(phase))||!field_text(d,data,"label",label,sizeof(label)))return 0;
  set_cache_scope(strtoull(online.account,NULL,10),cycle);
  online.cycle=cycle;online.joined=(uint32_t)joined;online.waiting=waiting;online.minimum=minimum;online.remaining=remaining;online.league_known=1;
  parse_calendar(d,data);
  if(strcmp(online.phase,phase))read_cache_clear();
  copy(online.phase,sizeof(online.phase),phase);copy(online.league_label,sizeof(online.league_label),label);return 1;
}
static int parse_profile(const MjDoc *d,int data){
  uint32_t registered,collection;
  if(!required_u32(d,data,"registered_players",&registered)||registered>MO_PLAYERS||!required_u32(d,data,"total_collection",&collection))return 0;
  online.roster_count=registered;online.collection_count=collection;
  int standing=mj_get(d,data,"league_standing");
  online.club_rank=(uint32_t)field_u64(d,standing,"rank");online.league_points=(uint32_t)field_u64(d,standing,"points");
  online.overall_rank=online.reputation=0;online.profile_season[0]=0;
  int ranking=mj_get(d,data,"monthly_ranking");char season[8],expected[8];uint32_t rank,points;
  md_season_text(server_now(),expected,sizeof(expected),1);
  if(online.monthly_capable&&field_text(d,ranking,"season_id",season,sizeof(season))&&!strcmp(season,expected)&&
      required_u32(d,ranking,"rank",&rank)&&required_u32(d,ranking,"points",&points)){
    online.overall_rank=rank;online.reputation=points;copy(online.profile_season,sizeof(online.profile_season),season);
  }return 1;
}
/* Group by server club ID; offer ordering and size count are not assumed. */
static unsigned shop_clubs(unsigned out[MO_OFFERS]){
  unsigned count=0;
  for(unsigned i=0;i<online.offer_count;i++){
    unsigned j=0;while(j<count&&online.offers[out[j]].team!=online.offers[i].team)j++;
    if(j==count)out[count++]=i;
  }return count;
}
static unsigned shop_sizes(unsigned out[MO_OFFERS]){
  unsigned count=0;for(unsigned i=0;i<online.offer_count;i++)if(online.offers[i].team==online.shop_team)out[count++]=i;return count;
}
static MdPage shop_page(void){return online.shop_sizes?MD_SHOP:MD_SHOP_CLUBS;}
static int parse_offers(const MjDoc *d,int data){
  if(!mj_is(d,data,MJ_ARRAY)||d->tokens[data].count>MO_OFFERS)return 0;
  online.offer_count=0;
  for(int i=0;i<d->tokens[data].count;i++){
    int object=mj_at(d,data,i);MoOffer offer={0};offer.id=field_u64(d,object,"offer_id");
    offer.version=(uint32_t)field_u64(d,object,"version");offer.team=(uint32_t)field_u64(d,object,"team_id");
    uint64_t price=field_u64(d,object,"price");if(price>UINT32_MAX)return 0;offer.price=(uint32_t)price;
    offer.pool=(uint32_t)field_u64(d,object,"pool_count");offer.draw=(uint32_t)field_u64(d,object,"select_count");
    if(!offer.id||!offer.version||!field_text(d,object,"team_name",offer.name,sizeof(offer.name))||!field_text(d,object,"tier",offer.tier,sizeof(offer.tier)))return 0;
    if(!((offer.pool==5&&offer.draw==2)||(offer.pool==6&&offer.draw==4)||(offer.pool==8&&offer.draw==5)))return 0;
    offer.available=mj_get(d,object,"available")<0?1:field_bool(d,object,"available");
    field_text(d,object,"unavailable_reason",offer.unavailable,sizeof(offer.unavailable));
    online.offers[online.offer_count++]=offer;
  }
  if(online.offer_focus>=online.offer_count)online.offer_focus=0;
  unsigned group[MO_OFFERS];if(!shop_sizes(group))online.shop_sizes=0;
  return 1;
}
static int parse_players(const MjDoc *d,int data){
  if(!mj_is(d,data,MJ_ARRAY)||d->tokens[data].count>MO_PLAYERS)return 0;
  MoPlayer *players=calloc(MO_PLAYERS,sizeof(*players));if(!players)return 0;int ok=1;
  for(int i=0;i<d->tokens[data].count;i++){
    if(!parse_player(d,mj_at(d,data,i),&players[i])||!players[i].instance){ok=0;break;}
    for(int j=0;j<i;j++)if(players[j].instance==players[i].instance||!strcmp(players[j].key,players[i].key)){ok=0;break;}
  }
  if(ok){online.player_count=(uint32_t)d->tokens[data].count;memcpy(online.players,players,sizeof(online.players));}
  free(players);return ok;
}
static MoPlayer *find_instance(uint64_t instance){for(uint32_t i=0;i<online.player_count;i++)if(online.players[i].instance==instance)return &online.players[i];return NULL;}
static int purchase_wallet(const MjDoc *d,int data){
  uint64_t balance;uint32_t version;
  if(!mj_u64(d,mj_get(d,data,"wallet_balance_after"),&balance)||balance>INT64_MAX||
      !required_u32(d,data,"wallet_revision_after",&version)||!version)return 0;
  if(online.cash_known&&version==online.wallet_revision&&balance!=online.cash)return 0;
  if(!online.cash_known||version>online.wallet_revision){online.cash=balance;online.wallet_revision=version;online.cash_known=1;}
  return 1;
}
static void purchases_display(void){
  unsigned indices[MO_PLAYERS],count=0;
  for(unsigned i=0;i<online.player_count;i++)if(online.players[i].purchased){
    unsigned at=count;
    while(at){MoPlayer *a=&online.players[i],*b=&online.players[indices[at-1]];int cmp=strcmp(a->acquired,b->acquired);
      if(cmp<0||(!cmp&&a->instance<b->instance))break;
      indices[at]=indices[at-1];at--;
    }indices[at]=i;count++;
  }
  online.purchases_count=count;
  for(unsigned i=0;i<count;i++){
    const MoPlayer *p=&online.players[indices[i]];online.purchases[i]=p->row;
    if(p->acquired[0])snprintf(online.purchases[i].detail,sizeof(online.purchases[i].detail),"BOUGHT %.10s",p->acquired);
  }
  change_page(MD_PURCHASE_HISTORY);
}
#include "manager_league_online_plan.inc"
static int parse_opponent(const MjDoc *d,int data){
  uint32_t team;char name[64];int squad=mj_get(d,data,"squad"),plan=mj_get(d,data,"published_gameplan"),xi=mj_get(d,plan,"xi");
  if(field_u64(d,data,"club_id")!=online.opponent_id||!required_u32(d,data,"presentation_team_id",&team)||!field_text(d,data,"club_name",name,sizeof(name))||
      !mj_is(d,squad,MJ_ARRAY)||d->tokens[squad].count<11||d->tokens[squad].count>MO_PLAYERS||!mj_is(d,xi,MJ_ARRAY)||d->tokens[xi].count!=11)return 0;
  MoPlayer *players=calloc(MO_PLAYERS,sizeof(*players));if(!players)return 0;
  int ok=1;for(int i=0;i<d->tokens[squad].count;i++)if(!parse_player(d,mj_at(d,squad,i),&players[i])){ok=0;break;}
  MdPlanPlayer display[18]={0};MdDot dots[11]={0};uint32_t used[MO_PLAYERS]={0};
  for(int i=0;i<11&&ok;i++){
    int actor=mj_at(d,xi,i);char key[64],assigned[16];uint32_t x,y;
    if(!field_text(d,actor,"player_key",key,sizeof(key))||!field_text(d,actor,"role",assigned,sizeof(assigned))||role(assigned)>=13||
        !required_u32(d,actor,"x",&x)||!required_u32(d,actor,"y",&y)||x>105000||y>68000){ok=0;break;}
    int j=0;while(j<d->tokens[squad].count&&strcmp(players[j].key,key))j++;if(j==d->tokens[squad].count||used[j]){ok=0;break;}used[j]=1;
    MdRow *r=&players[j].row;copy(display[i].label,sizeof(display[i].label),r->label);display[i].portrait=r->portrait;display[i].identity=r->identity;display[i].rating=r->rating;display[i].role=role(assigned);
    dots[i]=(MdDot){(float)y/68000.f,1.f-(float)x/105000.f,0,(uint32_t)i+1};
  }
  unsigned bench=11;for(int i=0;i<d->tokens[squad].count&&bench<18;i++)if(!used[i]){MdRow *r=&players[i].row;MdPlanPlayer *v=&display[bench++];copy(v->label,sizeof(v->label),r->label);v->portrait=r->portrait;v->identity=r->identity;v->rating=r->rating;v->role=r->role;}
  if(ok){char formation[16];field_text(d,plan,"formation",formation,sizeof(formation));online.plan.formation=0;for(unsigned i=0;i<FNX_GAMEPLAN_SHAPE_COUNT;i++)if(!strcmp(formation,fnx_gameplan_shapes[i].label))online.plan.formation=i;
    online.opponent=1;online.opponent_team=team;copy(online.opponent_name,sizeof(online.opponent_name),name);
    online.opponent_rating=(uint32_t)field_u64(d,data,"team_rating_ovr");int standing=mj_get(d,data,"standing");online.opponent_rank=(uint32_t)field_u64(d,standing,"rank_number");online.opponent_points=(uint32_t)field_u64(d,standing,"points");
    online.player_count=(uint32_t)d->tokens[squad].count;memcpy(online.players,players,sizeof(online.players));memset(online.plan_players,0,sizeof(online.plan_players));memcpy(online.plan_players,display,sizeof(display));online.plan_count=18;memcpy(online.plan_dots,dots,sizeof(dots));}
  free(players);return ok;
}
#include "manager_league_online_feed.inc"
#include "manager_league_online_ranking.inc"
static int parse_rows(const MjDoc *d,int data,int kind){
  if(kind==J_NEWS)return parse_club_feed(d,data);
  online.row_count=0;if(mj_is(d,data,MJ_NULL))return 1;
  if(!mj_is(d,data,MJ_ARRAY)||d->tokens[data].count>MO_MATCHES)return 0;
  for(int i=0;i<d->tokens[data].count;i++){
    int obj=mj_at(d,data,i);MdRow *row=&online.rows[online.row_count++];memset(row,0,sizeof(*row));row->enabled=1;
    if(kind==J_NEWS){
      char type[48];field_text(d,obj,"type",type,sizeof(type));
      copy(row->label,sizeof(row->label),!strcmp(type,"PACK_PURCHASE")?"PLAYER SIGNING":!strcmp(type,"MATCH_RESULT")?"MATCH RESULT":"LEAGUE NEWS");
      int params=mj_get(d,obj,"parameters");if(!field_text(d,params,"club_name",row->detail,sizeof(row->detail)))copy(row->detail,sizeof(row->detail),"News from across the league");
    }else{
      char name[56];if(!field_text(d,obj,"club_name",name,sizeof(name))&&!field_text(d,obj,"name",name,sizeof(name)))copy(name,sizeof(name),"CLUB");
      snprintf(row->label,sizeof(row->label),"%u. %.49s",(unsigned)i+1,name);
      row->team_id=(uint32_t)field_u64(d,obj,"club_id");row->badge=exhibition_team_catalog_badge((uint32_t)field_u64(d,obj,"presentation_team_id"));
      /* Older ranking DTOs identify accounts, not clubs. Only our authenticated
       * account has a proven account -> club mapping in bootstrap. */
      if(kind==J_RANKING&&!row->team_id&&online.account[0]&&field_u64(d,obj,"account_id")==strtoull(online.account,NULL,10)){
        row->team_id=(uint32_t)strtoull(online.club_id,NULL,10);row->badge=exhibition_team_catalog_badge(online.team);
      }
      row->selected=row->team_id&&row->team_id==strtoull(online.club_id,NULL,10);
      if(kind==J_STANDINGS){
        row->stats.played=(uint32_t)field_u64(d,obj,"played");row->stats.wins=(uint32_t)field_u64(d,obj,"won");row->stats.draws=(uint32_t)field_u64(d,obj,"drawn");row->stats.losses=(uint32_t)field_u64(d,obj,"lost");
        row->stats.goals_for=(uint32_t)field_u64(d,obj,"goals_for");row->stats.goals_against=(uint32_t)field_u64(d,obj,"goals_against");row->stats.points=(uint32_t)field_u64(d,obj,"league_points");
        snprintf(row->value,sizeof(row->value),"%u",row->stats.points);
      }else if(kind==J_CHAMPIONS){
        uint64_t cycle=field_u64(d,obj,"cycle_id");char settled[64],week[8];field_text(d,obj,"settled_at",settled,sizeof(settled));field_text(d,obj,"league_label",week,sizeof(week));
        snprintf(row->detail,sizeof(row->detail),"%s%sLEAGUE %llu%s%.10s",!strcmp(week,"W1")||!strcmp(week,"W2")?week:"",!strcmp(week,"W1")||!strcmp(week,"W2")?" - ":"",(unsigned long long)cycle,settled[0]?" - ":"",settled);
        copy(row->label,sizeof(row->label),name);copy(row->value,sizeof(row->value),"CHAMPION");
      }else {uint64_t rp=field_u64(d,obj,mj_get(d,obj,"ranking_points")>=0?"ranking_points":"rp");snprintf(row->value,sizeof(row->value),"%llu RP",(unsigned long long)rp);}
    }
  }return 1;
}
static int parse_match_list(const MjDoc *d,int data,int history){
  if(!mj_is(d,data,MJ_ARRAY)||d->tokens[data].count>MO_MATCHES)return 0;
  uint32_t count=(uint32_t)d->tokens[data].count;
  MoMatch *matches=calloc(count?count:1,sizeof(*matches));if(!matches)return 0;
  for(int i=0;i<d->tokens[data].count;i++){
    int obj=mj_at(d,data,i);MoMatch *m=&matches[i];
    m->id=field_u64(d,obj,"fixture_id");if(!m->id)m->id=field_u64(d,obj,"id");
    uint64_t cycle;
    if(!m->id||(mj_get(d,obj,"cycle_id")>=0&&(!mj_u64(d,mj_get(d,obj,"cycle_id"),&cycle)||(!history&&cycle!=online.cycle)))){free(matches);return 0;}
    m->home_club=field_u64(d,obj,"home_club_id");m->away_club=field_u64(d,obj,"away_club_id");
    m->kickoff=field_u64(d,obj,"broadcast_start_ms");if(!m->kickoff)m->kickoff=field_u64(d,obj,"kickoff_ms");
    m->ends=field_u64(d,obj,"broadcast_end_ms");
    uint64_t duration=field_u64(d,obj,"duration_ms");if(!duration)duration=660000;
    if(m->kickoff&&m->ends<=m->kickoff&&duration<=86400000&&m->kickoff<=UINT64_MAX-duration)m->ends=m->kickoff+duration;
    char phase[32],home[64],away[64];field_text(d,obj,"state",phase,sizeof(phase));
    m->phase=!strcmp(phase,"LIVE")?1:!strcmp(phase,"ENDED")?2:0;
    if(!field_text(d,obj,"home_club_name",home,sizeof(home))&&!field_text(d,obj,"home_name",home,sizeof(home)))copy(home,sizeof(home),"HOME CLUB");
    if(!field_text(d,obj,"away_club_name",away,sizeof(away))&&!field_text(d,obj,"away_name",away,sizeof(away)))copy(away,sizeof(away),"AWAY CLUB");
    copy(m->home,sizeof(m->home),home);copy(m->away,sizeof(m->away),away);
    m->row.badge=exhibition_team_catalog_badge((uint32_t)field_u64(d,obj,"home_presentation_team_id"));
    m->row.away_badge=exhibition_team_catalog_badge((uint32_t)field_u64(d,obj,"away_presentation_team_id"));
    snprintf(m->row.label,sizeof(m->row.label),"%.27s Vs %.27s",home,away);m->row.phase=m->phase;m->row.enabled=1;
    copy(m->row.value,sizeof(m->row.value),m->phase==1?"LIVE":m->phase==2?"FULL TIME":"SCHEDULED");
    if(history&&(m->phase!=2||(m->home_club!=(online.opponent?online.opponent_id:strtoull(online.club_id,NULL,10))&&m->away_club!=(online.opponent?online.opponent_id:strtoull(online.club_id,NULL,10))))){free(matches);return 0;}
    if(m->phase==2)snprintf(m->row.value,sizeof(m->row.value),"%llu - %llu",(unsigned long long)field_u64(d,obj,"home_goals"),(unsigned long long)field_u64(d,obj,"away_goals"));
    char date[48];format_date(m->kickoff,date,sizeof(date));
    snprintf(m->row.detail,sizeof(m->row.detail),"%s - ROUND %llu",date,(unsigned long long)field_u64(d,obj,"round_number"));
  }
  if(history){if(count>5){free(matches);return 0;}memcpy(online.history_matches,matches,count*sizeof(*matches));online.history_count=count;free(matches);return 1;}
  memcpy(online.matches,matches,count*sizeof(*matches));online.match_count=count;free(matches);
  for(uint32_t i=0;i<online.match_count;i++)for(uint32_t j=i+1;j<online.match_count;j++){
    MoMatch *a=&online.matches[i],*b=&online.matches[j];unsigned ga=a->phase==1?0:a->phase==0?1:2,gb=b->phase==1?0:b->phase==0?1:2;
    if(gb<ga||(ga==gb&&(ga==2?b->kickoff>a->kickoff:b->kickoff<a->kickoff))){MoMatch tmp=*a;*a=*b;*b=tmp;}
  }
  /* A published fixture is evidence of this club's participation, even when
   * /league/status accidentally returns an older registration cycle. Never
   * enable JOIN from that conflicting response. Preserve the server IDs. */
  online.calendar_conflict=0;
  const uint64_t now=server_now(),day=(now+7u*3600000u)/86400000u;
  const unsigned weekday=(unsigned)((day+4)%7),offset=(weekday+6)%7;
  uint64_t first_day=day-offset+(offset>=3?3:0),end_day=first_day+(offset>=3?4:3);
  uint64_t start=first_day*86400000u-7u*3600000u,end=end_day*86400000u-7u*3600000u,first=0,last=0;
  uint64_t own=strtoull(online.club_id,NULL,10);
  for(unsigned i=0;i<online.match_count;i++){
    MoMatch *m=&online.matches[i];if((m->home_club!=own&&m->away_club!=own)||m->kickoff<start||m->kickoff>=end)continue;
    if(!first||m->kickoff<first)first=m->kickoff;
    if(m->kickoff+660000>last)last=m->kickoff+660000;
  }
  if(first){
    online.match_day_start=first;online.match_day_end=last;
    if(!online.joined||(!strcmp(online.phase,"REGISTRATION")&&weekday!=1&&weekday!=4))online.calendar_conflict=1;
  }
  online.match_cycle=online.cycle;online.schedule_seen=online.mono;online.schedule_refresh=online.mono+30000;
  for(unsigned i=0;i<online.match_count;i++){
    uint64_t boundaries[]={online.matches[i].kickoff,online.matches[i].ends};
    for(unsigned j=0;j<2;j++)if(boundaries[j]>now&&boundaries[j]-now<online.schedule_refresh-online.mono)
      online.schedule_refresh=online.mono+(boundaries[j]-now);
  }
  return 1;
}
static int parse_matches(const MjDoc *d,int data){return parse_match_list(d,data,0);}
static int parse_history(const MjDoc *d,int data){
  uint32_t page,total,size;uint64_t snap=field_u64(d,data,"snapshot_id");
  if(!required_u32(d,data,"page",&page)||page!=online.history_request||!required_u32(d,data,"total",&total)||!required_u32(d,data,"page_size",&size)||size!=5||!snap||(online.history_snapshot&&snap!=online.history_snapshot))return 0;
  int items=mj_get(d,data,"items");
  if(!mj_is(d,items,MJ_ARRAY)||d->tokens[items].count>5||(uint32_t)d->tokens[items].count>total||!parse_match_list(d,items,1))return 0;
  online.history_page=page;online.history_total=total;online.history_snapshot=snap;return 1;
}
static int parse_header(const MjDoc *d,int data){
  char hash[65],state[24];uint64_t fixture=field_u64(d,data,"fixture_id"),kickoff;
  uint32_t duration,chunk,count,watermark;
  if(!required_u32(d,data,"duration_ms",&duration)||!required_u32(d,data,"chunk_duration_ms",&chunk)||
      !required_u32(d,data,"chunk_count",&count)||!required_u32(d,data,"current_watermark_ms",&watermark)||
      !mj_u64(d,mj_get(d,data,"broadcast_start_ms"),&kickoff)||!kickoff||
      !field_text(d,data,"state",state,sizeof(state))||
      fixture!=online.fixture||duration!=660000||chunk!=30000||count!=MO_CHUNKS||
      count!=(duration+chunk-1)/chunk||watermark>duration||
      !field_text(d,data,"recording_hash",hash,sizeof(hash))||strlen(hash)!=64)return 0;
  for(unsigned i=0;i<64;i++)if(!((hash[i]>='0'&&hash[i]<='9')||(hash[i]>='a'&&hash[i]<='f')))return 0;
  if(online.recording_hash[0]&&(strcmp(online.recording_hash,hash)||online.kickoff!=kickoff||
      online.chunk_ms!=chunk||online.chunk_count!=count||watermark<online.watermark))return 0;
  if(strcmp(state,"LIVE")&&strcmp(state,"ENDED"))return 0;
  if(!strcmp(state,"ENDED")&&watermark!=duration)return 0;
  if(!online.ended&&!strcmp(state,"ENDED"))online.last_events=0;
  copy(online.recording_hash,sizeof(online.recording_hash),hash);online.duration=duration;online.chunk_ms=chunk;online.chunk_count=count;
  if(watermark!=online.watermark){online.watermark_changed=online.mono;online.watch_stalled=0;}
  online.kickoff=kickoff;online.watermark=watermark;online.ended=!strcmp(state,"ENDED");online.last_header=online.mono;return 1;
}
static int parse_chunk_data(const MjDoc *d,int list,uint32_t requested){
  if(requested>=MO_CHUNKS||!mj_is(d,list,MJ_ARRAY)||d->tokens[list].count<1||d->tokens[list].count>MO_FRAMES)return 0;
  MoChunk *chunk=calloc(1,sizeof(*chunk));if(!chunk)return 0;chunk->count=(uint32_t)d->tokens[list].count;int ok=1;
  for(uint32_t i=0;i<chunk->count&&ok;i++){
    int obj=mj_at(d,list,(int)i);MoFrame *frame=&chunk->frames[i];
    if(!required_u32(d,obj,"at_ms",&frame->at)||frame->at/online.chunk_ms!=requested){ok=0;break;}
    /* The server releases a whole chunk at its start. Future frames in that
     * chunk may be cached, but the renderer still clamps to the live cursor. */
    if(frame->at>online.duration||(i&&frame->at<=chunk->frames[i-1].at)){ok=0;break;}
    for(int side=0;side<2;side++){
      int list=mj_get(d,obj,side?"a":"h");if(!mj_is(d,list,MJ_ARRAY)||d->tokens[list].count>11){ok=0;break;}
      for(int k=0;k<11;k++){
        MdDot *dot=&frame->dots[side*11+k];dot->side=(uint32_t)side;
        /* Instance IDs and array indexes are not shirt numbers. */
        dot->number=0;
        if(k>=d->tokens[list].count){dot->x=-1;dot->y=-1;continue;}
        int actor=mj_at(d,list,k);uint32_t x,y;
        if(!required_u32(d,actor,"x",&x)||!required_u32(d,actor,"y",&y)||x>105000||y>68000){ok=0;break;}dot->x=(float)x/105000.f;dot->y=(float)y/68000.f;
        uint32_t number=(uint32_t)field_u64(d,actor,"shirt_number");if(number<=99)dot->number=number;
      }
    }
    uint32_t x,y;if(!required_u32(d,obj,"bx",&x)||!required_u32(d,obj,"by",&y)||x>105000||y>68000){ok=0;break;}
    frame->dots[22]=(MdDot){(float)x/105000.f,(float)y/68000.f,2,0};
  }
  if(ok){chunk->index=requested;chunk->valid=1;online.chunks[requested]=*chunk;online.watch_fail=0;}
  free(chunk);return ok;
}
static int parse_chunk(const MjDoc *d,const char *path){
  const char *suffix=strrchr(path,'/');if(!suffix||!online.chunk_ms||!online.chunk_count)return 0;
  char *end;unsigned long requested=strtoul(suffix+1,&end,10);
  if(end==suffix+1||*end||requested>=online.chunk_count||requested*online.chunk_ms>online.watermark)return 0;
  return parse_chunk_data(d,0,(uint32_t)requested);
}
static uint32_t event_kind(const char *kind){
  if(!strcmp(kind,"GOAL"))return MD_GOAL;
  if(!strcmp(kind,"FOUL"))return MD_FOUL;
  if(!strcmp(kind,"YELLOW_CARD"))return MD_YELLOW;
  if(!strcmp(kind,"SUBSTITUTION"))return MD_SUB;
  if(!strcmp(kind,"OFFSIDE"))return MD_OFFSIDE;
  if(!strcmp(kind,"CORNER"))return MD_CORNER;
  if(!strcmp(kind,"SAVE"))return MD_SAVE;
  if(!strcmp(kind,"HALF_TIME"))return MD_HALF;
  if(strstr(kind,"SHOT"))return MD_SHOT;
  if(!strcmp(kind,"PASS")||!strcmp(kind,"PASSING_MOVE")||!strcmp(kind,"CROSS"))return MD_PASS;
  if(!strcmp(kind,"KICKOFF"))return MLA_KICKOFF;
  if(!strcmp(kind,"FULL_TIME"))return MLA_FULL_TIME;
  return UINT32_MAX;
}
static int parse_events(const MjDoc *d,int data){
  if(!mj_is(d,data,MJ_ARRAY)||d->tokens[data].count>MO_EVENTS)return 0;
  MoEvent *events=calloc(MO_EVENTS,sizeof(*events));if(!events)return 0;
  int ok=1;uint32_t count=(uint32_t)d->tokens[data].count;
  for(uint32_t i=0;i<count;i++){
    int obj=mj_at(d,data,(int)i);MoEvent *e=&events[i];
    if(!required_u32(d,obj,"at_ms",&e->at)||!required_u32(d,obj,"game_second",&e->second)||
        e->at>(online.bundle_ready?online.duration:online.watermark)||e->second>5400||(i&&e->at<events[i-1].at)){ok=0;break;}
    char kind[48],side[12];if(!field_text(d,obj,"kind",kind,sizeof(kind))){ok=0;break;}
    e->kind=event_kind(kind);field_text(d,obj,"side",side,sizeof(side));e->side=!strcmp(side,"AWAY");
    field_text(d,obj,"actor_name",e->name,sizeof(e->name));field_text(d,obj,"recipient_name",e->other,sizeof(e->other));
    for(char *ch=kind;*ch;ch++)if(*ch=='_')*ch=' ';
    snprintf(e->row.label,sizeof(e->row.label),"%02u:%02u %.40s",e->second/60,e->second%60,kind);
    char detail[96];snprintf(detail,sizeof(detail),"%.45s%s%.30s",e->name,e->other[0]?" TO ":"",e->other);
    copy(e->row.detail,sizeof(e->row.detail),detail);
    if(!e->row.detail[0])copy(e->row.detail,sizeof(e->row.detail),e->side?online.away:online.home);
    e->row.enabled=1;
    e->row.badge=e->side?online.away_badge:online.home_badge;
  }
  if(ok){memcpy(online.events,events,count*sizeof(*events));online.event_count=count;}
  free(events);return ok;
}
static int parse_recording(const MjDoc *d,int data){
  char policy[32];int header=mj_get(d,data,"header"),chunks=mj_get(d,data,"chunks");
  if(!field_text(d,data,"playback_policy",policy,sizeof(policy))||strcmp(policy,"FULL_RECORDING")||
      !parse_header(d,header)||!mj_is(d,chunks,MJ_ARRAY)||d->tokens[chunks].count!=MO_CHUNKS)return 0;
  memset(online.chunks,0,sizeof(online.chunks));online.bundle_ready=1;
  for(unsigned i=0;i<MO_CHUNKS;i++){int part=mj_at(d,chunks,(int)i);uint32_t index;
    if(!required_u32(d,part,"index",&index)||index!=i||!parse_chunk_data(d,mj_get(d,part,"frames"),i))goto fail;}
  if(!parse_events(d,mj_get(d,data,"events")))goto fail;
  online.last_events=online.mono;return 1;
fail:online.bundle_ready=0;online.event_count=0;memset(online.chunks,0,sizeof(online.chunks));return 0;
}
static void queue_watch_header(void){char path[160];snprintf(path,sizeof(path),"/matches/%llu/recording/header",(unsigned long long)online.fixture);request(J_HEADER,"GET",path,NULL,online.page!=MD_WATCH);}
static void hub_fetch(unsigned step){
  static const int jobs[]={J_HUB_TABLE,J_HUB_SCHEDULE,J_HUB_NEWS};
  static const char *const paths[]={"/league/standings","/league/schedule","/news"};
  online.hub_step=step;
  if(step<3){if(!read_cache_get(jobs[step],paths[step]))request(jobs[step],"GET",paths[step],NULL,0);}else online.hub_ready=1;
}
static void consume(MoResult *result){
  if(result->generation!=generation||!online.active)return;
  if(result->kind!=J_HUB_LIVE||!online.queued.kind)online.busy=online.modal_busy=online.busy_kind=0;
  /* Badge refresh is advisory. Never redirect pages, refresh authentication,
   * show a popup or publish a response captured for a previous cache scope. */
  if(result->kind==J_HUB_LIVE){
    const MoScope *s=&result->scope;MoHttpResponse *r=&result->http;
    if(!online.authenticated||s->generation!=generation||s->cycle!=online.cycle||
        s->environment!=online.environment||strcmp(s->account,online.account)||r->transport_error||!r->body||r->status!=200)return;
    MjToken *tokens=calloc(MO_TOKENS,sizeof(*tokens));MjDoc d;uint32_t environment;
    if(tokens&&mj_parse(&d,r->body,r->size,tokens,MO_TOKENS)&&
        parse_environment(&d,mj_get(&d,0,"meta"),&environment,online.environment==MO_TEST)&&environment==online.environment)
      if(parse_matches(&d,mj_get(&d,0,"data")))read_cache_store(result);
    free(tokens);return;
  }
  if(result->page==MD_WATCH&&online.page!=MD_WATCH&&
      (result->kind==J_HEADER||result->kind==J_CHUNK||result->kind==J_EVENTS||result->kind==J_RECORDING))return;
  if(result->kind==J_COMPAT){online.compatible=0;online.compat_checked=1;}
  MoHttpResponse *r=&result->http;
  if(result->kind==J_LOGOUT){
    auth_clear();session_remove();change_page(MD_REGISTER);
    if(r->transport_error||r->status<200||r->status>=300)message("LOGGED OUT ON THIS DEVICE","The saved session was removed. The server could not confirm session revocation.");
    return;
  }
  if(r->transport_error||!r->body){
    if(result->kind==J_HUB_LIVE)return; /* Background badge refresh must not interrupt navigation. */
    if(result->kind==J_HEADER||result->kind==J_CHUNK||result->kind==J_EVENTS||result->kind==J_RECORDING)online.watch_fail=1;
    if(result->kind==J_CLOCK||result->kind==J_CLOCK_STATUS)clock_finish_loading();
    mo_wipe(online.register_pin,sizeof(online.register_pin));
    message("CONNECTION INTERRUPTED",result->kind==J_SAVE_PLAN?"Your Game Plan draft is kept. Y checks whether it was saved; B retries the same request. No changes have been discarded.":result->kind==J_CLOCK||result->kind==J_CLOCK_STATUS?"TEST time could not be confirmed. Open Demo Time to recover the same operation.":result->kind==J_PROMO||result->kind==J_PROMO_STATUS?"Redemption could not be confirmed. Reopen Promotion Code to check the saved transaction before using another code.":result->kind==J_PAY?"Payment could not be confirmed. Reopen Shop to recover your paid pack before trying another purchase.":result->kind==J_GRANT||result->kind==J_SELECT?"The saved pack status could not be confirmed. Confirm again to recover the same selection. Your paid pack is kept; NX Cash will not be charged again.":"Could not reach FootballNX. Check your internet connection and try again.");return;
  }
  unsigned capacity=result->kind==J_RECORDING?MO_BUNDLE_TOKENS:MO_TOKENS;
  MjToken *tokens=calloc(capacity,sizeof(*tokens));MjDoc d;
  if(!tokens||!mj_parse(&d,r->body,r->size,tokens,capacity)){
    if(result->kind==J_RECORDING||result->kind==J_CHUNK)online.watch_fail=1;
    free(tokens);clock_finish_loading();message("SERVER RESPONSE","The server response could not be read safely. Please try again.");return;
  }
  int data=mj_get(&d,0,"data"),meta=mj_get(&d,0,"meta");uint64_t server=field_u64(&d,meta,"server_now_ms");
  /* Frame chunks are authenticated raw arrays, not JSON envelopes. Error
   * envelopes still require their realm before any recovery record is cleared. */
  int raw_chunk=result->kind==J_CHUNK&&r->status>=200&&r->status<300&&mj_is(&d,0,MJ_ARRAY);
  if(online.authenticated&&result->kind!=J_LOGIN&&result->kind!=J_REFRESH&&!raw_chunk){
    uint32_t environment;
    if(!parse_environment(&d,meta,&environment,online.environment==MO_TEST)||environment!=online.environment){
      clock_finish_loading();message("ENVIRONMENT MISMATCH","The server response belongs to a different environment. Log out and reconnect.");free(tokens);return;
    }
  }
  if(r->status<200||r->status>=300){
    if(result->kind==J_CHUNK||result->kind==J_RECORDING)online.watch_fail=1;
    if(result->kind==J_CLOCK||result->kind==J_CLOCK_STATUS)clock_finish_loading();
    int error=mj_get(&d,0,"error");char code[80],text[256];field_text(&d,error,"code",code,sizeof(code));
    if(!field_text(&d,error,"message",text,sizeof(text)))copy(text,sizeof(text),"The server could not complete this request.");
    if(r->status==401&&result->kind!=J_LOGIN&&result->kind!=J_REFRESH&&online.refresh[0]&&!online.refreshed_retry){
      online.refreshed_retry=1;
      if(result->safe_get){online.resume_kind=result->kind;online.resume_page=online.page;copy(online.resume_path,sizeof(online.resume_path),result->path);}
      else message("SESSION REFRESHED","Reopen this page to check the saved server status before trying the action again.");
      free(tokens);refresh_submit();return;
    }
    if(r->status==401){auth_clear();session_remove();change_page(MD_LOGIN);}
    if(r->status==426||!strcmp(code,"CATALOG_SYNC_REQUIRED")){online.compatible=0;online.compat_checked=1;}
    if(result->kind==J_PAY&&(!strcmp(code,"INSUFFICIENT_FUNDS")||!strcmp(code,"OFFER_NOT_FOUND")||
        !strcmp(code,"OFFER_VERSION_MISMATCH")||!strcmp(code,"PRICE_CHANGED")||!strcmp(code,"PACK_POOL_UNAVAILABLE")||!strcmp(code,"OFFER_ALREADY_PURCHASED")))payment_intent_clear();
    if(result->kind==J_PAY&&(!strcmp(code,"PACK_POOL_UNAVAILABLE")||!strcmp(code,"OFFER_ALREADY_PURCHASED"))){change_page(shop_page());}
    if(result->kind==J_PAY&&!strcmp(code,"PENDING_PURCHASE_EXISTS")){free(tokens);get(J_OFFERS,"/shop/offers");return;}
    if((result->kind==J_PROMO||result->kind==J_PROMO_STATUS)&&(!strcmp(code,"CODE_UNAVAILABLE")||!strcmp(code,"CODE_EXPIRED")||
        !strcmp(code,"CODE_NOT_ACTIVE")||!strcmp(code,"INVALID_CODE")))service_intent_clear(J_PROMO);
    if(result->kind==J_CLOCK&&!strcmp(code,"REVISION_CONFLICT"))service_intent_clear(J_CLOCK);
    if(result->kind==J_SAVE_PLAN){online.plan_leave=0;
      if(r->status==409){copy(text,sizeof(text),"Your draft is kept. The saved revision changed or the squad is locked. Y checks the server plan; X discards the draft and reloads it.");}}
    mo_wipe(online.register_pin,sizeof(online.register_pin));message(r->status==426?"UPDATE REQUIRED":"CLUB MESSAGE",text);free(tokens);return;
  }
  if(server&&!result->cached){online.server_anchor=server;online.mono_anchor=online.mono;}
  if(result->kind!=J_REFRESH)online.refreshed_retry=0;
  int ok=1;
  switch(result->kind){
    case J_COMPAT:{
      char version[24],hash[65],pair[24];int maintenance=0;
      ok=field_text(&d,data,"required_online_version",version,sizeof(version))&&!strcmp(version,MANAGER_ONLINE_VERSION)&&
        field_text(&d,data,"required_catalog_content_sha256",hash,sizeof(hash))&&!strcmp(hash,MANAGER_ONLINE_CATALOG)&&
        field_text(&d,data,"required_runtime_pair_id",pair,sizeof(pair))&&!strcmp(pair,MANAGER_ONLINE_PAIR)&&field_u64(&d,data,"api_schema_version")==1&&
        mj_bool(&d,mj_get(&d,data,"maintenance"),&maintenance);
      if(!ok){message("UPDATE REQUIRED","This client does not match the server's online version or player catalog.");ok=1;break;}
      if(maintenance){message("SERVER MAINTENANCE","Online League is temporarily unavailable. Your offline modes remain available.");break;}
      if(strcmp(ml_catalog_pair_id(),MANAGER_ONLINE_PAIR)||!strcmp(ml_catalog_manager_binding_id(),"unpaired")){
        message("PLAYER DATA UPDATE","This game build does not contain the paired online player catalog. Install the matching FootballNX update.");break;
      }
      online.compatible=1;if(online.refresh[0])refresh_submit();break;
    }
    case J_REGISTER:{
      char recovery[80];if(field_text(&d,data,"recovery_code",recovery,sizeof(recovery))){char text[256];snprintf(text,sizeof(text),"Your recovery code is:\n%s\nKeep it somewhere safe. It can reset your PIN.",recovery);message("SAVE YOUR RECOVERY CODE",text);mo_wipe(recovery,sizeof(recovery));}
      online.auth_register=0;change_page(MD_LOGIN);
      if(online.register_pin[0]){
        char id[80],pin[16],body[256];mj_quote(online.login_id,id,sizeof(id));mj_quote(online.register_pin,pin,sizeof(pin));
        snprintf(body,sizeof(body),"{\"user_id\":%s,\"pin\":%s,\"device_label\":\"Nintendo Switch\"}",id,pin);
        request(J_LOGIN,"POST","/auth/login",body,1);mo_wipe(body,sizeof(body));mo_wipe(pin,sizeof(pin));mo_wipe(online.register_pin,sizeof(online.register_pin));
      }break;
    }
    case J_LOGIN:case J_REFRESH:{
      char access[MO_TOKEN_SIZE],refresh[MO_TOKEN_SIZE];
      uint64_t ttl=field_u64(&d,data,"expires_in_seconds");int was_authenticated=online.authenticated;
      ok=field_text(&d,data,"access_token",access,sizeof(access))&&field_text(&d,data,"refresh_token",refresh,sizeof(refresh))&&token_valid(access)&&token_valid(refresh)&&ttl>=60&&ttl<=86400;
      if(ok){uint32_t environment;
        ok=parse_environment(&d,data,&environment,0)&&parse_environment(&d,meta,&environment,environment==MO_TEST)&&
          parse_service_context(&d,data,result->kind==J_LOGIN)&&environment==online.environment;
      }
      if(ok){copy(online.access,sizeof(online.access),access);copy(online.refresh,sizeof(online.refresh),refresh);online.authenticated=1;
        /* Authentication TTL uses real monotonic time, never TEST league time. */
        online.access_until=online.mono+ttl*1000;
        if(!session_write()&&!online.notice[0])message("SESSION NOT SAVED","You are logged in, but will need to enter your PIN again after closing the game.");
        if(result->kind==J_LOGIN||!was_authenticated)refresh_bootstrap();
        else if(online.resume_kind){int kind=online.resume_kind;online.resume_kind=0;
          if(online.page==online.resume_page)request(kind,"GET",online.resume_path,NULL,0);}}
      else {auth_clear();session_remove();change_page(MD_LOGIN);}
      mo_wipe(access,sizeof(access));mo_wipe(refresh,sizeof(refresh));break;
    }
    case J_BOOTSTRAP:
      ok=parse_bootstrap(&d,data);
      if(ok){int pending=mj_get(&d,data,"pending_pack");
        if(mj_is(&d,pending,MJ_NULL)){online.pending_known=1;online.pending_at=online.mono;}
        else if(pending>=0&&online.page!=MD_PACK_OPENING&&online.page!=MD_PACK_SELECT&&online.page!=MD_PACK_RESULT){
          if(!parse_purchase(&d,pending))online.pending_known=0;
        }
        if(online.page==MD_PACK_OPENING||online.page==MD_PACK_SELECT||online.page==MD_PACK_RESULT){/* Preserve the current paid/granted flow and opening animation. */}
        else if(!mj_is(&d,pending,MJ_NULL)&&pending>=0){get(J_OFFERS,"/shop/offers");}
        else if(online.bootstrap_shop){online.bootstrap_shop=0;change_page(MD_SHOP_CLUBS);}
        else {change_page(MD_DASHBOARD);online.tab=0;
          if(online.clock_intent.magic&&online.environment==MO_TEST&&online.demo_time)service_lookup(J_CLOCK_STATUS);
          else if(!online.league_known)request(J_LEAGUE_STATUS,"GET","/league/status",NULL,0);
          else request(J_STATUS,"GET","/club/profile",NULL,0);}}
      break;
    case J_LEAGUE_STATUS:
      ok=parse_league_status(&d,data);if(ok)request(J_STATUS,"GET","/club/profile",NULL,0);break;
    case J_STATUS:ok=parse_profile(&d,data);if(ok&&online.page==MD_DASHBOARD&&!online.hub_ready)hub_fetch(0);break;
    case J_PROFILE:
      ok=parse_profile(&d,data);if(ok){online.profile_child=0;change_page(MD_CLUB_PROFILE);}break;
    case J_OFFERS:ok=parse_offers(&d,data);if(ok){
      if(online.pending_known&&online.mono-online.pending_at<30000&&!online.pay_uncertain&&!online.grant_uncertain)
        change_page(online.purchase&&!online.pack_granted?MD_PACK_SELECT:shop_page());
      else get(J_PENDING,"/shop/pending");
    }break;
    case J_PENDING:
      if(mj_is(&d,data,MJ_NULL)){online.pending_known=1;online.pending_at=online.mono;online.pack_granted=online.purchase!=0;online.grant_uncertain=0;online.grant_key[0]=0;change_page(shop_page());if(online.pay_uncertain)payment_lookup();}
      else {ok=parse_purchase(&d,data);if(ok){payment_intent_clear();if(online.page!=MD_PACK_SELECT)change_page(MD_PACK_SELECT);
        else if(online.focus>online.pool_count||(online.focus==online.pool_count&&selected_count()!=online.draw))online.focus=0;}}
      break;
    case J_PAY_STATUS:{
      char key[37],state[24];ok=field_text(&d,data,"idempotency_key",key,sizeof(key))&&!strcmp(key,online.pay_key)&&field_text(&d,data,"status",state,sizeof(state));
      if(!ok)break;
      change_page(MD_PAYMENT_RECOVERY);
      if(!strcmp(state,"NOT_FOUND"))message("PURCHASE NOT COMPLETED","No completed purchase was found. Resume Purchase safely sends your original request again. If the pack is unavailable, return to Shop and choose another pack.");
      else if(!strcmp(state,"PROCESSING"))message("PAYMENT PROCESSING","The server is processing the saved payment. Check its status again shortly. You can leave this page.");
      else if(!strcmp(state,"COMPLETED")){
        char operation[32];int receipt=mj_get(&d,data,"response");
        if(field_text(&d,data,"operation",operation,sizeof(operation))&&!strcmp(operation,"SHOP_PURCHASE")&&parse_purchase(&d,receipt)){payment_intent_clear();change_page(MD_PACK_SELECT);if(!purchase_wallet(&d,receipt))refresh_bootstrap();}
        else message("PAYMENT RECEIPT","The payment completed, but its paid pack could not be read. Check status again to recover it. Keep the saved record for support.");
      }else ok=0;
      break;
    }
    case J_PAY:ok=parse_purchase(&d,data);if(ok){read_cache_drop(J_OFFERS);online.grant_key[0]=0;payment_intent_clear();online.opening_at=online.mono;change_page(MD_PACK_OPENING);if(!purchase_wallet(&d,data))refresh_bootstrap();}break;
    case J_SELECT:get(J_PENDING,"/shop/pending");break;
    case J_GRANT:
      {int keys=mj_get(&d,data,"granted_player_keys");uint32_t seen=0;
        if(mj_get(&d,data,"purchase_id")>=0&&field_u64(&d,data,"purchase_id")!=online.purchase){ok=0;break;}
        if(!mj_is(&d,keys,MJ_ARRAY)||d.tokens[keys].count!=(int)online.draw){ok=0;break;}
        for(int i=0;i<d.tokens[keys].count;i++){char key[64];if(!mj_text(&d,mj_at(&d,keys,i),key,sizeof(key))){ok=0;break;}
          uint32_t k=0;while(k<online.pool_count&&strcmp(key,online.pool[k].key))k++;
          if(k==online.pool_count||(seen&(1u<<k))){ok=0;break;}seen|=1u<<k;}
        if(!ok)break;
        /* A different device may already have confirmed this purchase. Its
         * immutable receipt is authoritative; never attempt a second grant. */
        online.selected=seen;}
      read_cache_clear();online.collection_count+=online.draw;online.grant_uncertain=0;online.grant_key[0]=0;
      online.pack_granted=online.pending_known=1;online.pending_at=online.mono;change_page(MD_PACK_RESULT);break;
    case J_SQUAD:case J_COLLECTION:
      ok=parse_players(&d,data);if(ok){if(result->kind==J_SQUAD)online.roster_count=online.player_count;
        if(online.want_plan==2){online.want_plan=0;purchases_display();}
        else if(online.want_plan){online.want_plan=0;get(J_PLAN,"/club/gameplan");}else change_page(result->kind==J_SQUAD?MD_TEAM_INFO:MD_COLLECTION_PAGE);}
      break;
    case J_PLAN:ok=parse_plan(&d,data);if(ok)change_page(MD_CLUB_PLAN);break;
    case J_SAVE_PLAN:
      read_cache_drop(J_PLAN);read_cache_drop(J_SQUAD);read_cache_drop(J_PROFILE);
      if(mj_is(&d,mj_get(&d,data,"plan"),MJ_OBJECT)){
        ok=plan_verify(&d,data);
        if(ok&&!online.plan_save_pending){MoResult saved=*result;saved.kind=J_PLAN;saved.safe_get=1;copy(saved.path,sizeof(saved.path),"/club/gameplan");read_cache_store(&saved);}
      }else get(J_PLAN_VERIFY,"/club/gameplan");
      break;
    case J_PLAN_VERIFY:ok=plan_verify(&d,data);break;
    case J_STANDINGS:case J_RANKING:case J_CHAMPIONS:case J_NEWS:
      ok=parse_rows(&d,data,result->kind);if(ok){
        if(result->kind==J_STANDINGS){online.standing_count=online.row_count;memcpy(online.standings,online.rows,sizeof(online.rows));}
        if(result->kind==J_RANKING){online.ranking_count=online.row_count;memcpy(online.rankings,online.rows,sizeof(online.rows));}
        change_page(result->kind==J_STANDINGS?(online.want_teams?MD_TEAMS_PAGE:MD_TABLE):result->kind==J_RANKING?MD_OVERALL:result->kind==J_CHAMPIONS?MD_CHAMPIONS:MD_NEWS);online.want_teams=0;}break;
    case J_OPPONENT:ok=parse_opponent(&d,data);if(ok)change_page(MD_OPPONENT_PROFILE);break;
    case J_PLAYER_FEED:ok=parse_player_feed(&d,data);if(ok){online.feed_section=0;change_page(MD_PLAYER_FEED);}break;
    case J_MONTHLY:ok=parse_monthly(&d,data);if(ok){change_page(MD_OVERALL);if(online.rank_tail&&online.row_count)online.focus=online.row_count-1;}break;
    case J_HUB_TABLE:case J_HUB_NEWS:case J_HUB_RANKING:{
      int kind=result->kind==J_HUB_TABLE?J_STANDINGS:result->kind==J_HUB_NEWS?J_NEWS:J_RANKING;
      ok=parse_rows(&d,data,kind);if(ok){
        MdRow *rows=kind==J_STANDINGS?online.standings:kind==J_NEWS?online.news:online.rankings;
        uint32_t *count=kind==J_STANDINGS?&online.standing_count:kind==J_NEWS?&online.news_count:&online.ranking_count;
        *count=online.row_count;memcpy(rows,online.rows,sizeof(online.rows));hub_fetch(online.hub_step+1);
      }break;
    }
    case J_HUB_SCHEDULE:ok=parse_matches(&d,data);if(ok)hub_fetch(online.hub_step+1);break;
    case J_HUB_LIVE:ok=parse_matches(&d,data);break;
    case J_SCHEDULE:ok=parse_matches(&d,data);if(ok){
      if(online.schedule_auto&&!online.history&&online.match_count)online.match_group=online.matches[0].phase==1?0:online.matches[0].phase==0?1:2;
      online.schedule_auto=0;change_page(online.history?MD_TEAM_HISTORY:MD_SCHEDULE);
    }break;
    case J_HISTORY:ok=parse_history(&d,data);if(ok)change_page(MD_TEAM_HISTORY);break;
    case J_HEADER:ok=parse_header(&d,data);if(ok&&online.page!=MD_WATCH){online.watch_tick=online.mono;change_page(MD_WATCH);}break;
    case J_RECORDING:ok=parse_recording(&d,data);if(ok){online.watch_tick=online.mono;change_page(MD_WATCH);}break;
    case J_CHUNK:ok=parse_chunk(&d,result->path);break;
    case J_EVENTS:ok=parse_events(&d,data);online.last_events=online.mono;break;
    case J_JOIN:refresh_bootstrap();break;
    case J_CLOCK:case J_CLOCK_STATUS:ok=clock_consume(&d,data);break;
    case J_PROMO:case J_PROMO_STATUS:ok=promotion_consume(&d,data);break;
    default:break;
  }
  if(!ok){if(result->kind==J_HEADER||result->kind==J_CHUNK||result->kind==J_RECORDING)online.watch_fail=1;
    clock_finish_loading();message("SERVER DATA UPDATE","The server returned data this client cannot use safely. Please update the game or try again later.");}
  if(ok)read_cache_store(result);
  free(tokens);
}
void manager_online_open(void){
  pthread_mutex_lock(&ui_mutex);generation++;read_cache_clear();mo_wipe(&online,sizeof(online));pin_clear();online.active=1;online.page=MD_REGISTER;online.minimum=4;
  online.environment=MO_PRODUCTION;online.team=108;online.duration=660000;online.chunk_ms=30000;online.serial=1;session_load();get(J_COMPAT,"/compatibility");pthread_mutex_unlock(&ui_mutex);
}
void manager_online_close(void){
  pthread_mutex_lock(&ui_mutex);generation++;online.active=0;online.busy=0;auth_clear();mo_wipe(online.register_pin,sizeof(online.register_pin));pthread_mutex_unlock(&ui_mutex);
}
void manager_online_tick(uint64_t ms){
  pthread_mutex_lock(&ui_mutex);online.mono=ms;
  MoResult result={0};int ready=0;
  pthread_mutex_lock(&worker.mutex);if(worker.ready){result=worker.result;memset(&worker.result,0,sizeof(worker.result));worker.ready=0;ready=1;}pthread_mutex_unlock(&worker.mutex);
  if(ready){consume(&result);mo_http_free(&result.http);}
  if(online.queued.kind){
    pthread_mutex_lock(&worker.mutex);
    if(!worker.running&&!worker.pending&&!worker.ready){
      worker.job=online.queued;mo_wipe(&online.queued,sizeof(online.queued));worker.pending=1;pthread_cond_signal(&worker.cond);
    }
    pthread_mutex_unlock(&worker.mutex);
  }
  if(online.active&&!online.busy&&!online.compat_checked&&!online.notice[0])get(J_COMPAT,"/compatibility");
  if(online.active&&online.authenticated&&!online.busy&&!online.notice[0]&&!online.clock_active&&online.access_until&&online.mono+60000>=online.access_until)refresh_submit();
  if(online.active&&online.authenticated&&online.page==MD_DASHBOARD&&!online.busy&&!online.notice[0]&&!online.clock_active&&!online.join_confirm){
    uint64_t end=hub_phase_end();
    if(end&&server_now()>=end&&online.phase_refresh_end!=end){online.phase_refresh_end=end;refresh_bootstrap();}
    else if(!online.tab&&online.hub_ready&&hub_phase()==MH_MATCH&&ms>=online.schedule_refresh){
      online.schedule_refresh=ms+30000;request(J_HUB_LIVE,"GET","/league/schedule",NULL,0);
    }
  }
  if(online.active&&online.authenticated&&online.page==MD_OVERALL&&!online.busy&&!online.notice[0]&&online.rank_ends&&
      server_now()>=online.rank_ends&&online.rank_refresh_end!=online.rank_ends){
    online.rank_refresh_end=online.rank_ends;monthly_open(online.rank_section,1,0);
  }
  if(online.active&&online.clock_active){
    if(ms-online.clock_wait_started>=60000){clock_finish_loading();message("TEST OPERATION RUNNING","The server operation is taking longer. Open Demo Time to check the saved operation again.");}
    else if(!online.busy&&ms>=online.clock_poll_at)service_lookup(J_CLOCK_STATUS);
  }
  if(online.active&&online.page==MD_PACK_OPENING&&ms-online.opening_at>=MD_PACK_OPEN_MS)change_page(MD_PACK_SELECT);
  if(online.active&&online.page==MD_WATCH){
    uint64_t delta=online.watch_tick&&ms>=online.watch_tick?ms-online.watch_tick:0;online.watch_tick=ms;
    uint32_t current=online.play_ms/online.chunk_ms;if(current>=MO_CHUNKS)current=MO_CHUNKS-1;
    if(online.replay&&!online.paused&&online.chunks[current].valid){uint64_t elapsed=online.play_ms+delta;online.play_ms=elapsed>online.duration?online.duration:(uint32_t)elapsed;}
    if(!online.replay){uint64_t elapsed=server_now()>online.kickoff?server_now()-online.kickoff:0;online.play_ms=elapsed>online.duration?online.duration:(uint32_t)elapsed;
      if(online.bundle_ready){online.ended=online.play_ms==online.duration;}
      else if(online.ended)online.play_ms=online.duration;
      else if(online.play_ms>online.watermark)online.play_ms=online.watermark;}
    if(!online.bundle_ready&&!online.replay&&!online.ended&&ms-online.watermark_changed>15000)online.watch_stalled=1;
    if(!online.busy&&!online.notice[0]&&!online.watch_fail&&ms>=online.next_watch_request&&!online.bundle_ready){
      uint32_t index=online.play_ms/online.chunk_ms;if(index>=MO_CHUNKS)index=MO_CHUNKS-1;
      if(index&&online.chunks[index].valid&&online.chunks[index].count&&online.chunks[index].frames[0].at>online.play_ms&&!online.chunks[index-1].valid)index--;
      if(!online.chunks[index].valid){char path[192];snprintf(path,sizeof(path),"/matches/%llu/recording/chunks/%u",(unsigned long long)online.fixture,index);request(J_CHUNK,"GET",path,NULL,0);}
      else if(!online.last_events||(!online.ended&&ms-online.last_events>=4000)){char path[160];snprintf(path,sizeof(path),"/matches/%llu/events",(unsigned long long)online.fixture);request(J_EVENTS,"GET",path,NULL,0);}
      else if(!online.ended&&ms-online.last_header>=2000)queue_watch_header();
      else { /* Cache each released chunk once; ended matches prefetch the full tape. */
        uint32_t next=0;while(next<MO_CHUNKS&&(online.chunks[next].valid||(!online.ended&&next*online.chunk_ms>online.watermark)))next++;
        if(next<MO_CHUNKS){char path[192];snprintf(path,sizeof(path),"/matches/%llu/recording/chunks/%u",(unsigned long long)online.fixture,next);request(J_CHUNK,"GET",path,NULL,0);}
      }
    }
  }
  pthread_mutex_unlock(&ui_mutex);
}

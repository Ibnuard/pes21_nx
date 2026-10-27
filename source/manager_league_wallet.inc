/* Account cash transactions. The full before/after pair is journaled before
 * either live file is changed. No PIN or credential enters this record. */
#define MD_WALLET_FILE "SaveData/manager-league-wallet-v98.dat"
enum { MD_CASH_ENTRY=1, MD_CASH_REWARD=2 };
typedef struct {
  uint32_t magic,version,bytes,checksum,kind,amount;
  uint64_t observed_ms;
  MdArchive before,after;
} MdCashJournal;
static uint64_t cash_retry_at;
static int cash_sync_profile(void) {
  /* Journal the actual durable starting profile, including any pending lineup
   * lock or tutorial acknowledgement, before changing its wallet. */
  profile_prepare(&profile,&md,now());
  MdProfile prior;FILE *f=fopen(MD_PROFILE_FILE,"rb");
  if(!f)f=fopen(MD_PROFILE_FILE ".bak","rb");
  int same=f && fread(&prior,1,sizeof(prior),f)==sizeof(prior) && fgetc(f)==EOF &&
      !memcmp(&prior,&profile,sizeof(prior));
  if(f)fclose(f);
  if(same || profile_save())return 1;
  snprintf(notice,sizeof(notice),"NX Cash is pending while your club data is saved. Please retry.");return 0;
}
static uint32_t league_prize(const MdSave *save,uint32_t team,uint32_t *rank) {
  uint32_t points[7]={0},goals[7]={0},order[7]={0,1,2,3,4,5,6};int difference[7]={0};
  for(uint32_t i=0;i<MD_FIXTURES;i++) {
    const MdFixture *f=&save->fixtures[i];uint32_t g[2];manager_dummy_score(f,manager_dummy_duration(f),g);
    goals[f->home]+=g[0];goals[f->away]+=g[1];
    difference[f->home]+=(int)g[0]-(int)g[1];difference[f->away]+=(int)g[1]-(int)g[0];
    points[f->home]+=g[0]>g[1] ? 3u : g[0]==g[1];
    points[f->away]+=g[1]>g[0] ? 3u : g[0]==g[1];
  }
  for(uint32_t i=0;i<7;i++)for(uint32_t j=i+1;j<7;j++) {
    uint32_t a=order[i],b=order[j];
    if(points[b]>points[a] || (points[b]==points[a] &&
       (difference[b]>difference[a] || (difference[b]==difference[a] && goals[b]>goals[a])))) {
      order[i]=b;order[j]=a;
    }
  }
  for(uint32_t i=0;i<7;i++)if(order[i]==team) {
    if(rank)*rank=i+1;
    return i==0 ? 5000u : i==1 ? 4000u : i==2 ? 3000u : 0u;
  }
  return 0;
}
static int cash_journal_valid(const MdCashJournal *j) {
  if(j->magic!=0x4d434a39u || j->version!=98 || j->bytes!=sizeof(*j) ||
     j->checksum!=record_hash(j,sizeof(*j),offsetof(MdCashJournal,checksum)) ||
     !archive_pair_valid(&j->before) || !archive_valid(&j->after))return 0;
  const MdSave *before=&j->before.save,*after=&j->after.save;
  MdSave expected=*before;MdProfile players=j->before.players;
  if(j->kind==MD_CASH_ENTRY) {
    if((before->purchased_mask&MD_ENTRY_GRANTED) || j->amount!=MD_ENTRY_CASH)return 0;
    if(!before->joined) {
      expected.created=expected.joined=1;expected.day_ms=after->day_ms;
      memcpy(expected.fixtures,after->fixtures,sizeof(expected.fixtures));
      if(expected.day_ms!=MD_CALENDAR_DAY_MS)return 0;
    }
    expected.purchased_mask|=MD_ENTRY_GRANTED;
  } else if(j->kind==MD_CASH_REWARD) {
    if(!before->joined || !(before->purchased_mask&MD_ENTRY_GRANTED) ||
       (before->purchased_mask&MD_REWARD_SETTLED) ||
       manager_dummy_week(before,j->observed_ms).state!=MD_RESULT ||
       j->amount!=league_prize(before,0,NULL))return 0;
    expected.purchased_mask|=MD_REWARD_SETTLED;
  } else return 0;
  if(UINT32_MAX-expected.balance<j->amount || UINT32_MAX-players.balance<j->amount)return 0;
  expected.balance+=j->amount;expected.checksum=checksum(&expected);
  players.balance+=j->amount;profile_prepare(&players,&expected,j->observed_ms);
  return !memcmp(&expected,after,sizeof(expected)) && !memcmp(&players,&j->after.players,sizeof(players));
}
static int cash_journal_read(const char *path,MdCashJournal *j) {
  FILE *f=fopen(path,"rb");if(!f)return 0;
  int ok=fread(j,1,sizeof(*j),f)==sizeof(*j) && fgetc(f)==EOF;fclose(f);
  return ok && cash_journal_valid(j);
}
static int cash_journal_write(MdCashJournal *j) {
  archive_seal(&j->before);archive_seal(&j->after);
  j->magic=0x4d434a39u;j->version=98;j->bytes=sizeof(*j);
  j->checksum=record_hash(j,sizeof(*j),offsetof(MdCashJournal,checksum));
  if(!cash_journal_valid(j) || file_exists(MD_WALLET_FILE) || file_exists(MD_PENDING_FILE))return 0;
  FILE *f=fopen(MD_WALLET_FILE ".tmp","wb");int ok=0;
  if(f){ok=fwrite(j,1,sizeof(*j),f)==sizeof(*j) && !fflush(f);if(fclose(f))ok=0;}
  MdCashJournal *check=calloc(1,sizeof(*check));
  if(!check)return 0;
  ok=ok && cash_journal_read(MD_WALLET_FILE ".tmp",check) && !memcmp(check,j,sizeof(*j));free(check);
  return ok && !rename(MD_WALLET_FILE ".tmp",MD_WALLET_FILE);
}
static int cash_finish(void) {
  return !remove(MD_WALLET_FILE) && !file_exists(MD_WALLET_FILE);
}
static int cash_promote(uint32_t kind,uint32_t amount,const MdSave *before,const MdProfile *players) {
  MdCashJournal *j=calloc(1,sizeof(*j));
  if(!j){md=*before;profile=*players;snprintf(notice,sizeof(notice),"NX Cash could not be saved. Please try again.");return 0;}
  j->kind=kind;j->amount=amount;j->observed_ms=now();
  profile_prepare(&profile,&md,j->observed_ms);
  j->before.save=*before;j->before.players=*players;j->after.save=md;j->after.players=profile;
  int ok=cash_journal_write(j);
  if(!ok) {
    md=*before;profile=*players;profile_cache();
    snprintf(notice,sizeof(notice),"NX Cash could not be saved. Your previous balance is preserved.");
  } else {
    md=j->after.save;profile=j->after.players;profile_cache();
    ok=persist() && profile_save() && active_pair_verified() && cash_finish();
    if(!ok){blocked=1;snprintf(notice,sizeof(notice),"Your NX Cash transaction needs recovery. Restart to finish saving it.");}
  }
  free(j);return ok;
}
/* Called before ordinary season loading. A valid wallet journal may represent
 * first entry or a same-season payout, unlike the successor-season journal. */
static int cash_recover(void) {
  if(!file_exists(MD_WALLET_FILE))return 0;
  MdCashJournal *j=calloc(1,sizeof(*j));MdSave *prior=calloc(1,sizeof(*prior));
  MdProfile *players=calloc(1,sizeof(*players));
  int ok=j && prior && players && !file_exists(MD_PENDING_FILE) && cash_journal_read(MD_WALLET_FILE,j);
  if(ok)ok=(read_file(MD_FILE,prior) || read_file(MD_FILE ".bak",prior)) &&
      (!memcmp(prior,&j->before.save,sizeof(*prior)) || !memcmp(prior,&j->after.save,sizeof(*prior)));
  if(ok) {
    FILE *f=fopen(MD_PROFILE_FILE,"rb");
    if(!f)f=fopen(MD_PROFILE_FILE ".bak","rb");
    ok=f && fread(players,1,sizeof(*players),f)==sizeof(*players) && fgetc(f)==EOF;
    if(f)fclose(f);
    MdProfile normalized=j->after.players;
    int64_t at=(int64_t)epoch_now+j->after.save.clock_offset_ms;
    profile_prepare(&normalized,&j->after.save,at<0 ? 0u : (uint64_t)at);
    ok=ok && (!memcmp(players,&j->before.players,sizeof(*players)) ||
              !memcmp(players,&j->after.players,sizeof(*players)) || !memcmp(players,&normalized,sizeof(*players)));
  }
  if(ok) {
    md=j->after.save;profile=j->after.players;profile_ready=1;profile_cache();
    ok=persist() && profile_save() && active_pair_verified() && cash_finish();
  }
  if(!ok){blocked=1;snprintf(notice,sizeof(notice),"NX Cash recovery is unavailable. Existing account files are preserved.");}
  else notice[0]=0;
  free(players);free(prior);free(j);return 1;
}
static int grant_entry_locked(const MdSave *registration_before) {
  if(!profile_ready || !md.joined || blocked || profile_blocked)return 0;
  if(md.purchased_mask&MD_ENTRY_GRANTED)return 1;
  if(!cash_sync_profile())return 0;
  MdSave before=registration_before ? *registration_before : md;MdProfile players=profile;
  md.purchased_mask|=MD_ENTRY_GRANTED;md.balance+=MD_ENTRY_CASH;profile.balance+=MD_ENTRY_CASH;
  return cash_promote(MD_CASH_ENTRY,MD_ENTRY_CASH,&before,&players);
}
static int settle_rewards_locked(void) {
  if(blocked || profile_blocked || !profile_ready || !md.joined)return 0;
  if((md.purchased_mask&MD_REWARD_SETTLED) || manager_dummy_week(&md,now()).state!=MD_RESULT)return 1;
  if(!grant_entry_locked(NULL))return 0;
  if(!cash_sync_profile())return 0;
  MdSave before=md;MdProfile players=profile;uint32_t rank;
  uint32_t amount=league_prize(&md,0,&rank);
  md.purchased_mask|=MD_REWARD_SETTLED;md.balance+=amount;profile.balance+=amount;
  if(!cash_promote(MD_CASH_REWARD,amount,&before,&players))return 0;
  if(amount)snprintf(notice,sizeof(notice),"League position %u: %u NX Cash added to your wallet.",rank,amount);
  return 1;
}

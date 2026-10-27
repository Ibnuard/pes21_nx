/* One paid, resumable pack at a time. The journal is durable before debit or
 * grant; immutable canonical pool IDs survive process exit and catalog order. */
#define MD_PACK_FILE "SaveData/manager-league-pack-v99.dat"
enum { MD_PACK_DEBIT=1, MD_PACK_PAID=2, MD_PACK_GRANT=3 };
typedef struct {
  uint32_t magic,version,bytes,checksum,phase,offer,selected,pool[8];
  uint64_t observed_ms;
  MdArchive before,after;
} MdPackPurchase;
static MdPackPurchase purchase;
static uint32_t pack_pending;
static uint32_t pack_pending_bit(uint32_t k){return 1u<<(k+MD_PACK_PENDING_SHIFT);}
static int pack_apply(MdProfile *p,const MdPackPurchase *j) {
  uint32_t count=0;
  if(j->selected>=(1u<<pack_pools[j->offer]))return 0;
  for(uint32_t i=0;i<8;i++)count+=(j->selected>>i)&1u;
  if(count!=pack_draws[j->offer] || p->collection_count+count>MD_COLLECTION)return 0;
  uint32_t n=0;
  for(uint32_t i=0;i<pack_pools[j->offer];i++)if(j->selected&(1u<<i)) {
    uint32_t id=j->pool[i];
    for(uint32_t k=0;k<p->collection_count;k++)if(p->collection[k]==id)return 0;
    p->receipt_players[j->offer][n++]=id;p->collection[p->collection_count++]=id;
    if(p->counts[0]<MD_REGISTERED)p->roster[0][p->counts[0]++]=id;
  }
  p->has_current_plan=0;memset(&p->current_plan,0,sizeof(p->current_plan));
  p->receipts=(p->receipts&~pack_pending_bit(j->offer))|(1u<<j->offer);
  return 1;
}
static int purchase_valid(const MdPackPurchase *j) {
  if(j->magic!=0x4d504b39u || j->version!=99 || j->bytes!=sizeof(*j) || j->offer>=3 ||
     j->phase<MD_PACK_DEBIT || j->phase>MD_PACK_GRANT ||
     j->checksum!=record_hash(j,sizeof(*j),offsetof(MdPackPurchase,checksum)) ||
     !archive_valid(&j->before) || !archive_valid(&j->after) ||
     memcmp(&j->before.save,&j->after.save,sizeof(MdSave)))return 0;
  uint32_t chosen=0;
  for(uint32_t i=0;i<8;i++) {
    chosen+=(j->selected>>i)&1u;
    if(i>=pack_pools[j->offer]){if(j->pool[i])return 0;continue;}
    const MlCatalogPlayer *p=ml_catalog_find_identity(j->pool[i]);
    if(!p || p->club!=pack_clubs[j->offer])return 0;
    for(uint32_t k=0;k<i;k++)if(j->pool[i]==j->pool[k])return 0;
  }
  if(j->selected>=(1u<<pack_pools[j->offer]) || chosen>pack_draws[j->offer])return 0;
  MdProfile expected=j->before.players;
  const uint32_t bit=pack_pending_bit(j->offer);
  if(j->phase==MD_PACK_GRANT) {
    if(!(expected.receipts&bit) || (expected.receipts&(1u<<j->offer)) || !pack_apply(&expected,j))return 0;
  } else {
    if(expected.receipts&(MD_PACK_PENDING_MASK|(1u<<j->offer)) || expected.balance<pack_prices[j->offer] ||
       expected.collection_count+pack_draws[j->offer]>MD_COLLECTION)return 0;
    expected.balance-=pack_prices[j->offer];expected.receipts|=bit;
  }
  profile_prepare(&expected,&j->after.save,j->observed_ms);
  return !memcmp(&expected,&j->after.players,sizeof(expected));
}
static int purchase_read(const char *path,MdPackPurchase *j) {
  FILE *f=fopen(path,"rb");if(!f)return 0;
  int ok=fread(j,1,sizeof(*j),f)==sizeof(*j) && fgetc(f)==EOF;fclose(f);
  return ok && purchase_valid(j);
}
static int purchase_write(MdPackPurchase *j) {
  archive_seal(&j->before);archive_seal(&j->after);
  j->magic=0x4d504b39u;j->version=99;j->bytes=sizeof(*j);
  j->checksum=record_hash(j,sizeof(*j),offsetof(MdPackPurchase,checksum));
  if(!purchase_valid(j) || file_exists(MD_WALLET_FILE) || file_exists(MD_PENDING_FILE))return 0;
  FILE *f=fopen(MD_PACK_FILE ".tmp","wb");int ok=0;
  if(f){ok=fwrite(j,1,sizeof(*j),f)==sizeof(*j) && !fflush(f);if(fclose(f))ok=0;}
  MdPackPurchase *check=calloc(1,sizeof(*check));if(!check)return 0;
  ok=ok && purchase_read(MD_PACK_FILE ".tmp",check) && !memcmp(j,check,sizeof(*j));free(check);
  if(!ok)return 0;
  remove(MD_PACK_FILE ".bak");
  if(rename(MD_PACK_FILE,MD_PACK_FILE ".bak") && file_exists(MD_PACK_FILE))return 0;
  if(rename(MD_PACK_FILE ".tmp",MD_PACK_FILE)){rename(MD_PACK_FILE ".bak",MD_PACK_FILE);return 0;}
  return 1;
}
static int pack_finish(void) {
  if(remove(MD_PACK_FILE) || file_exists(MD_PACK_FILE))return 0;
  remove(MD_PACK_FILE ".bak");pack_pending=0;memset(&purchase,0,sizeof(purchase));return 1;
}
static int purchase_promote(void) {
  profile=purchase.after.players;profile_cache();
  if(!profile_save() || !active_pair_verified())goto failed;
  if(purchase.phase==MD_PACK_GRANT) {
    if(!pack_finish())goto failed;
    return 1;
  }
  purchase.phase=MD_PACK_PAID;
  if(!purchase_write(&purchase))goto failed;
  pack_pending=1;return 1;
failed:
  blocked=1;snprintf(notice,sizeof(notice),"Your paid pack needs recovery. Restart to finish saving it.");return 0;
}
static void pack_recover(void) {
  const uint32_t pending=profile.receipts&MD_PACK_PENDING_MASK;
  if(!file_exists(MD_PACK_FILE)) {
    if(!pending)return;
    if(!purchase_read(MD_PACK_FILE ".bak",&purchase))goto failed;
    /* Re-establish the primary before any later selection write rotates the
     * backup. A crash between the previous two renames must stay resumable. */
    if(rename(MD_PACK_FILE ".bak",MD_PACK_FILE))goto failed;
  } else if(!purchase_read(MD_PACK_FILE,&purchase))goto failed;
  if(purchase.after.save.seed!=md.seed || purchase.after.save.club!=md.club ||
     strcmp(purchase.after.players.user_id,profile.user_id))goto failed;
  if(purchase.phase==MD_PACK_PAID) {
    if(pending!=pack_pending_bit(purchase.offer) || (profile.receipts&(1u<<purchase.offer)))goto failed;
    pack_pending=1;return;
  }
  if(memcmp(&md,&purchase.before.save,sizeof(md)))goto failed;
  MdProfile normalized=purchase.after.players;profile_prepare(&normalized,&md,now());
  if(memcmp(&profile,&purchase.before.players,sizeof(profile)) &&
     memcmp(&profile,&purchase.after.players,sizeof(profile)) && memcmp(&profile,&normalized,sizeof(profile)))goto failed;
  if(!purchase_promote())return;
  return;
failed:
  blocked=1;snprintf(notice,sizeof(notice),"Paid pack data is unavailable. Your wallet and collection are preserved.");
}
static int pack_resume(void) {
  if(!pack_pending || !profile_ready || blocked || profile_blocked)return 0;
  pack_choice=purchase.offer;pack_selected=purchase.selected;
  for(uint32_t i=0;i<pack_pools[pack_choice];i++)pack_pool[pack_choice][i]=ml_catalog_find_identity(purchase.pool[i]);
  page=MD_PACK_SELECT;focus=0;return 1;
}
static int pack_can_buy(void) {
  if(pack_resume())return 0;
  if(shop_locked()){snprintf(notice,sizeof(notice),"The shop is closed during Match Day.");return 0;}
  if(!profile_ready || !pack_pool[pack_choice][pack_pools[pack_choice]-1]) {
    snprintf(notice,sizeof(notice),"This pack is unavailable. Please try again.");return 0;
  }
  if(profile.balance<pack_prices[pack_choice]){snprintf(notice,sizeof(notice),"Not enough NX Cash to open this pack.");return 0;}
  if(profile.collection_count+pack_draws[pack_choice]>MD_COLLECTION) {
    snprintf(notice,sizeof(notice),"Your collection is full. This pack has not been charged.");return 0;
  }
  return 1;
}
static void pack_open(void) {
  if(profile.receipts&(1u<<pack_choice)){page=MD_PACK_RESULT;focus=0;return;}
  if(pack_can_buy()){page=MD_PACK_BUY;focus=1;}
}
static void pack_buy(void) {
  if(!pack_can_buy() || !cash_sync_profile())return;
  memset(&purchase,0,sizeof(purchase));purchase.offer=pack_choice;purchase.phase=MD_PACK_DEBIT;purchase.observed_ms=now();
  for(uint32_t i=0;i<pack_pools[pack_choice];i++)purchase.pool[i]=pack_pool[pack_choice][i]->identity;
  purchase.before.save=purchase.after.save=md;purchase.before.players=purchase.after.players=profile;
  purchase.after.players.balance-=pack_prices[pack_choice];purchase.after.players.receipts|=pack_pending_bit(pack_choice);
  profile_prepare(&purchase.after.players,&md,purchase.observed_ms);
  if(!purchase_write(&purchase)) {
    memset(&purchase,0,sizeof(purchase));snprintf(notice,sizeof(notice),"Pack purchase was not saved. No NX Cash was charged.");return;
  }
  if(!purchase_promote())return;
  page=MD_PACK_OPENING;pack_selected=0;pack_opened_at=epoch_now;focus=0;notice[0]=0;
}
static void pack_save_selection(uint32_t before) {
  const uint32_t previous=purchase.selected;purchase.selected=pack_selected;
  if(!purchase_write(&purchase)) {
    pack_selected=before;purchase.selected=previous;
    snprintf(notice,sizeof(notice),"Your selection could not be saved. Please try again.");
  }
}
static void pack_confirm(void) {
  if(!pack_pending || pack_choice!=purchase.offer || selected_count()!=pack_draws[pack_choice]) {
    snprintf(notice,sizeof(notice),"Complete your player selection first.");return;
  }
  if(!cash_sync_profile())return;
  MdPackPurchase *grant=calloc(1,sizeof(*grant));if(!grant)return;
  *grant=purchase;grant->phase=MD_PACK_GRANT;grant->selected=pack_selected;grant->observed_ms=now();
  grant->before.save=grant->after.save=md;grant->before.players=grant->after.players=profile;
  if(!pack_apply(&grant->after.players,grant))goto failed;
  profile_prepare(&grant->after.players,&md,grant->observed_ms);
  if(!purchase_write(grant))goto failed;
  purchase=*grant;free(grant);
  if(!purchase_promote())return;
  page=MD_PACK_RESULT;focus=0;notice[0]=0;return;
failed:
  free(grant);snprintf(notice,sizeof(notice),"Your paid pack is safe. The players could not be saved; please retry.");
}

/* Fixed two-real-week ranking windows, Monday 00:00 WIB. Local projections
 * read immutable league archives; the champion record outlives RP resets. */
#define MD_RANK_EPOCH UINT64_C(1792947600000) /* 26 Oct 2026 00:00 WIB */
static uint64_t ranking_start(uint64_t stamp) {
  int64_t delta=(int64_t)calendar_local_day(stamp)-(int64_t)calendar_local_day(MD_RANK_EPOCH);
  int64_t window=delta>=0 ? delta/14 : -((-delta+13)/14);
  int64_t first=(int64_t)calendar_local_day(MD_RANK_EPOCH)+window*14;
  return first>0 ? calendar_midnight((uint64_t)first) : 0;
}
static uint32_t ranking_cached[7],ranking_seed,ranking_week,ranking_hash,ranking_done;
static uint64_t ranking_window=UINT64_MAX;
static void ranking_add(const MdSave *save,const MdProfile *players,uint32_t rp[7]) {
  for(uint32_t t=0;t<7;t++) {
    uint32_t rank=7;league_prize(save,t,&rank);
    for(uint32_t current=0;current<7;current++)
      if(players->clubs[t]==profile.clubs[current])rp[current]+=700u-(rank-1u)*100u;
  }
}
static void ranking_points(uint32_t rp[7]) {
  if(!md.joined || !md.week_id){memset(rp,0,sizeof(uint32_t)*7);return;}
  uint64_t start=ranking_start(now()),end=start+14u*(uint64_t)MD_CALENDAR_DAY_MS;
  const uint32_t finished=manager_dummy_week(&md,now()).state==MD_RESULT;
  if(ranking_window!=start || ranking_seed!=md.seed || ranking_week!=md.week_id ||
     ranking_hash!=md.checksum || ranking_done!=finished) {
    memset(ranking_cached,0,sizeof(ranking_cached));
    if(finished) {
      uint64_t result=manager_dummy_week(&md,UINT64_MAX).result_ms;
      if(result>=start && result<end)ranking_add(&md,&profile,ranking_cached);
    }
    MdArchive *a=calloc(1,sizeof(*a));
    if(a)for(uint32_t week=md.week_id-1;week;week--) {
      char path[96];archive_path(path,week);
      if(!archive_read(path,a) || a->save.seed!=md.seed || a->save.club!=md.club || a->save.week_id!=week)continue;
      uint64_t result=manager_dummy_week(&a->save,UINT64_MAX).result_ms;
      if(result<start)break;
      if(result<end)ranking_add(&a->save,&a->players,ranking_cached);
    }
    free(a);ranking_window=start;ranking_seed=md.seed;ranking_week=md.week_id;
    ranking_hash=md.checksum;ranking_done=finished;
  }
  memcpy(rp,ranking_cached,sizeof(ranking_cached));
}
static MdArchive champion;
static uint32_t champion_choice,champion_return_focus;
static int champion_read(uint32_t week,MdArchive *out) {
  if(week==md.week_id) {
    if(manager_dummy_week(&md,now()).state!=MD_RESULT)return 0;
    out->save=md;out->players=profile;archive_seal(out);return archive_valid(out);
  }
  char path[96];archive_path(path,week);
  return week && week<md.week_id && archive_read(path,out) && out->save.week_id==week &&
      out->save.seed==md.seed && out->save.club==md.club;
}
static uint32_t champion_team(const MdSave *save) {
  for(uint32_t t=0;t<7;t++){uint32_t rank=7;league_prize(save,t,&rank);if(rank==1)return t;}
  return 0;
}
static uint32_t champion_total(void) {
  return md.joined && md.week_id ? md.week_id-1u+(manager_dummy_week(&md,now()).state==MD_RESULT) : 0;
}

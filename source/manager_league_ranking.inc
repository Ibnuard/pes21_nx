/* DEV OFFLINE projection from immutable archives; no save schema change.
 * Archived tapes predate entry timestamps, so registration dates are inferred
 * from their fixture calendar. Online points are always server ledger data. */
typedef struct {uint64_t start;uint32_t points[7],participation[7],podium[7][3];} MdRankMonth;
static MdRankMonth *ranking_months;
static uint32_t ranking_count,ranking_seed,ranking_week,ranking_hash,ranking_done,ranking_section;
static uint64_t ranking_window=UINT64_MAX;
static MdRankMonth *ranking_month(uint64_t stamp,int create) {
  uint64_t start=md_season_start(stamp);
  for(uint32_t i=0;i<ranking_count;i++)if(ranking_months[i].start==start)return &ranking_months[i];
  if(!create)return NULL;
  MdRankMonth *grown=realloc(ranking_months,(ranking_count+1u)*sizeof(*grown));if(!grown)return NULL;
  ranking_months=grown;MdRankMonth *month=&grown[ranking_count++];memset(month,0,sizeof(*month));month->start=start;return month;
}
static void ranking_credit(const MdSave *save,const MdProfile *players,uint64_t stamp,int podium) {
  if(stamp>now())return;
  MdRankMonth *month=ranking_month(stamp,1);if(!month)return;
  for(uint32_t t=0;t<7;t++)for(uint32_t current=0;current<7;current++)if(players->clubs[t]==profile.clubs[current]){
    if(!podium){month->points[current]+=500;month->participation[current]+=500;}
    else {uint32_t rank=7;league_prize(save,t,&rank);month->points[current]+=md_season_prize(rank);if(rank<=3)month->podium[current][rank-1]++;}
  }
}
static void ranking_add(const MdSave *save,const MdProfile *players) {
  if(!save->joined)return;
  uint64_t first=manager_dummy_week(save,UINT64_MAX).first_kickoff_ms;uint32_t day=md_hub_weekday(first);
  uint64_t entry=md_hub_midnight(first)-(day<3?day:day<6?day-3:3)*UINT64_C(86400000);
  ranking_credit(save,players,entry,0);
  ranking_credit(save,players,manager_dummy_week(save,UINT64_MAX).result_ms,1);
}
static void ranking_update(void) {
  uint64_t start=md_season_start(now());
  const uint32_t finished=manager_dummy_week(&md,now()).state==MD_RESULT;
  if(ranking_window!=start || ranking_seed!=md.seed || ranking_week!=md.week_id ||
     ranking_hash!=md.checksum || ranking_done!=finished) {
    ranking_count=0;
    if(md.joined&&md.week_id)ranking_add(&md,&profile);
    MdArchive *a=calloc(1,sizeof(*a));
    if(a)for(uint32_t week=md.week_id?md.week_id-1:0;week;week--) {
      char path[96];archive_path(path,week);
      if(!archive_read(path,a) || a->save.seed!=md.seed || a->save.club!=md.club || a->save.week_id!=week)continue;
      ranking_add(&a->save,&a->players);
    }
    for(uint32_t i=0;i<ranking_count;i++)for(uint32_t j=i+1;j<ranking_count;j++)if(ranking_months[j].start>ranking_months[i].start){MdRankMonth swap=ranking_months[i];ranking_months[i]=ranking_months[j];ranking_months[j]=swap;}
    free(a);ranking_window=start;ranking_seed=md.seed;ranking_week=md.week_id;
    ranking_hash=md.checksum;ranking_done=finished;
  }
}
static int ranking_better(const MdRankMonth *month,uint32_t a,uint32_t b) {
  if(month){if(month->points[a]!=month->points[b])return month->points[a]>month->points[b];
    for(unsigned i=0;i<3;i++)if(month->podium[a][i]!=month->podium[b][i])return month->podium[a][i]>month->podium[b][i];}
  return profile.clubs[a]<profile.clubs[b];
}
static void ranking_points(uint32_t rp[7]) {
  ranking_update();MdRankMonth *month=ranking_month(now(),0);if(month)memcpy(rp,month->points,sizeof(month->points));else memset(rp,0,7*sizeof(*rp));
}
static uint32_t ranking_past_total(void){ranking_update();uint32_t count=0;for(uint32_t i=0;i<ranking_count;i++)if(ranking_months[i].start<ranking_window)count++;return count;}
static void ranking_past_row(uint32_t index,MdRow *row) {
  memset(row,0,sizeof(*row));uint32_t at=0;
  for(uint32_t i=0;i<ranking_count;i++)if(ranking_months[i].start<ranking_window){
    if(at++!=index)continue;
    MdRankMonth *month=&ranking_months[i];uint32_t winner=0;for(uint32_t t=1;t<7;t++)if(ranking_better(month,t,winner))winner=t;
    char label[40];md_season_text(month->start,label,sizeof(label),0);
    row->badge=badge(winner);row->team_id=winner;row->enabled=1;
    snprintf(row->label,sizeof(row->label),"%s",team_name(winner));snprintf(row->detail,sizeof(row->detail),"%s - CHAMPION",label);
    snprintf(row->value,sizeof(row->value),"%u PTS",month->points[winner]);break;
  }
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

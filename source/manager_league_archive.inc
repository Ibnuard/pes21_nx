/* v1 is imported read-only. v2 has explicit timing, and completed weeks retain
 * the roster used by their replay rather than borrowing a later squad. */
typedef struct {
  uint64_t kickoff_ms;
  uint32_t home,away,round,seed;
  MdEvent events[MD_LEGACY_EVENTS];
} MdFixtureV1;
typedef struct {
  uint32_t magic,version,bytes,checksum,created,joined,club;
  uint32_t balance,formation,mentality,tempo,seed,purchased_mask;
  int64_t clock_offset_ms;
  char name[MD_NAME_SIZE];
  MdFixtureV1 fixtures[MD_FIXTURES];
} MdSaveV1;
_Static_assert(sizeof(MdFixtureV1)==720,"Legacy fixture ABI changed");
_Static_assert(sizeof(MdSaveV1)==15216,"Legacy archive ABI changed");
typedef struct {
  uint32_t magic,version,bytes,checksum;
  MdSave save;
  MdProfile players;
} MdArchive;
#define MD_PENDING_FILE "SaveData/manager-league-transition-v2.dat"
static MdArchive history;
static uint32_t history_week;
static uint32_t record_hash(const void *record,size_t bytes,size_t hash_offset) {
  const unsigned char *p=record;uint32_t h=2166136261u;
  for(size_t i=0;i<bytes;i++)h=(h^(i>=hash_offset && i<hash_offset+4 ? 0 : p[i]))*16777619u;
  return h;
}
static int read_legacy(const char *path,MdSave *out) {
  MdSaveV1 *old=calloc(1,sizeof(*old));if(!old)return 0;
  FILE *f=fopen(path,"rb");int ok=f && fread(old,1,sizeof(*old),f)==sizeof(*old) && fgetc(f)==EOF;
  if(f)fclose(f);
  if(!ok || old->magic!=MD_MAGIC || old->version!=1 || old->bytes!=sizeof(*old) ||
     old->checksum!=record_hash(old,sizeof(*old),offsetof(MdSaveV1,checksum))) {free(old);return 0;}
  memset(out,0,sizeof(*out));
  memcpy(out,old,offsetof(MdSaveV1,fixtures));
  out->version=2;out->bytes=sizeof(*out);out->week_id=1;out->day_ms=MD_LEGACY_DAY_MS;
  for(uint32_t i=0;i<MD_FIXTURES;i++) {
    MdFixture *to=&out->fixtures[i];const MdFixtureV1 *from=&old->fixtures[i];
    to->kickoff_ms=from->kickoff_ms;to->home=from->home;to->away=from->away;
    to->round=from->round;to->seed=from->seed;
    to->duration_ms=MD_LEGACY_DURATION;to->event_count=MD_LEGACY_EVENTS;
    memcpy(to->events,from->events,sizeof(from->events));
  }
  out->checksum=checksum(out);free(old);return manager_dummy_valid(out);
}
static int file_exists(const char *path) {
  FILE *f=fopen(path,"rb");if(!f)return 0;fclose(f);return 1;
}
static void archive_path(char path[96],uint32_t week) {
  snprintf(path,96,"SaveData/manager-league-week-%04u.dat",week);
}
static int archive_valid(const MdArchive *a) {
  if(a->magic!=0x4d4c4132u || a->version!=2 || a->bytes!=sizeof(*a) ||
     a->checksum!=record_hash(a,sizeof(*a),offsetof(MdArchive,checksum)) ||
     !manager_dummy_valid(&a->save) || !a->save.joined)return 0;
  /* Profile validation depends only on these three account bindings. Never
   * replace the active season to inspect a historical immutable record. */
  uint32_t seed=md.seed,club=md.club,balance=md.balance;
  md.seed=a->save.seed;md.club=a->save.club;md.balance=a->save.balance;
  int ok=profile_valid(&a->players);
  md.seed=seed;md.club=club;md.balance=balance;return ok;
}
static int archive_read(const char *path,MdArchive *out) {
  FILE *f=fopen(path,"rb");if(!f)return 0;
  int ok=fread(out,1,sizeof(*out),f)==sizeof(*out) && fgetc(f)==EOF;fclose(f);
  return ok && archive_valid(out);
}
static void archive_seal(MdArchive *a) {
  a->magic=0x4d4c4132u;a->version=2;a->bytes=sizeof(*a);
  a->save.magic=MD_MAGIC;a->save.version=2;a->save.bytes=sizeof(a->save);
  a->save.checksum=checksum(&a->save);
  a->players.checksum=profile_hash(&a->players);
  a->checksum=record_hash(a,sizeof(*a),offsetof(MdArchive,checksum));
}
static int archive_write(const char *path,MdArchive *a) {
  archive_seal(a);if(!archive_valid(a))return 0;
  char temp[112],backup[112];snprintf(temp,sizeof(temp),"%s.tmp",path);
  snprintf(backup,sizeof(backup),"%s.bak",path);
  FILE *f=fopen(temp,"wb");int ok=0;
  if(f){ok=fwrite(a,1,sizeof(*a),f)==sizeof(*a) && !fflush(f);if(fclose(f))ok=0;}
  MdArchive *check=calloc(1,sizeof(*check));
  if(!check)return 0;
  ok=ok && archive_read(temp,check) && !memcmp(a,check,sizeof(*a));free(check);
  if(!ok)return 0;
  remove(backup);
  if(rename(path,backup) && file_exists(path))return 0;
  if(rename(temp,path)){rename(backup,path);return 0;}
  return 1;
}
static const MdSave *broadcast_save(void) {return history_week ? &history.save : &md;}
static const MdProfile *broadcast_profile(void) {return history_week ? &history.players : &profile;}
static uint64_t broadcast_now(void) {
  return history_week ? manager_dummy_week(&history.save,UINT64_MAX).result_ms : now();
}
static const char *broadcast_team_name(uint32_t team) {
  return team ? exhibition_team_catalog_name(broadcast_profile()->clubs[team]) : broadcast_save()->name;
}
static uint32_t broadcast_badge(uint32_t team) {
  return exhibition_team_catalog_badge(broadcast_profile()->clubs[team]);
}
static const MdFixture *watch_fixture(void) {return &broadcast_save()->fixtures[fixture_choice];}
void manager_dummy_history_reset(void) {
  pthread_mutex_lock(&md_mutex);history_week=0;pthread_mutex_unlock(&md_mutex);
}
static int history_select(uint32_t week) {
  if(!week){history_week=0;focus=schedule_day=0;timeline_serial++;return 1;}
  if(week>=md.week_id)return 0;
  char path[96];archive_path(path,week);
  if(!archive_read(path,&history) || history.save.week_id!=week ||
     history.save.seed!=md.seed || history.save.club!=md.club)return 0;
  history_week=week;focus=schedule_day=0;timeline_serial++;return 1;
}
int manager_dummy_history_select(uint32_t week) {
  pthread_mutex_lock(&md_mutex);int ok=authenticated && page==MD_SCHEDULE && history_select(week);
  pthread_mutex_unlock(&md_mutex);return ok;
}

#define _POSIX_C_SOURCE 200809L
#include "manager_league_dummy.h"
#include "competition_hub_navigation.h"
#include "exhibition_team_catalog.h"
#include "master_league_catalog.h"
#include <math.h>
#include <errno.h>
#include <stddef.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#ifdef __SWITCH__
#include <switch.h>
#endif

#define MD_MAGIC 0x4d4c4431u
#define MD_FILE "SaveData/manager-league-dummy-v2.dat"
#define MD_LEGACY_FILE "SaveData/manager-league-dummy-v1.dat"
enum {
  B = 1u,
  A = 2u,
  Y = 4u,
  X = 8u,
  L = 16u,
  R = 128u,
  UP = 1024u,
  DOWN = 2048u,
  LEFT = 4096u,
  RIGHT = 8192u
};
static pthread_mutex_t md_mutex = PTHREAD_MUTEX_INITIALIZER;
static MdSave md;
static MdPage page = MD_REGISTER;
static uint32_t focus, dashboard_focus, hub_section, category, club_choice, team_choice,
    player_choice, fixture_choice, action;
static uint32_t navigation_serial;
static int slide_direction;
static MdPage shop_return = MD_DASHBOARD;
static MdPage team_return = MD_TEAMS_PAGE;
static uint32_t team_return_focus;
static uint32_t club_menu_focus,club_child;
static MdPage editor_return_page=MD_DASHBOARD;
static uint32_t editor_return_focus,editor_return_section;
static uint32_t replay, paused, replay_ms, loaded, blocked;
static MdPage watch_return=MD_SCHEDULE;
static uint32_t watch_return_focus;
static uint64_t epoch_now = 1, last_tick;
static char notice[112];
static const uint32_t shop_prices[3] = {2200, 2200, 4500};
#ifdef __SWITCH__
static int32_t manager_timezone_offset;
static int manager_timezone_ready;
#endif
static void manager_local_time(uint64_t milliseconds, struct tm *out) {
  time_t seconds = (time_t)(milliseconds / 1000u);
#ifdef __SWITCH__
  if (manager_timezone_ready) {
    seconds += manager_timezone_offset;
    gmtime_r(&seconds, out);
    return;
  }
#endif
  localtime_r(&seconds, out);
}
static uint64_t now(void);
static uint64_t competition_start(const MdSave *save);
static int shop_locked(void) {
  return md.joined && manager_dummy_week(&md, now()).state == MD_MATCH_DAY;
}
static uint32_t rng(uint32_t *s) {
  *s = *s * 1664525u + 1013904223u;
  return *s;
}
#include "manager_league_profile.inc"
#include "manager_league_auth.h"
#define MD_AUTH_FILE "SaveData/manager-league-account-v1.dat"
static MdCredential credential;
static int credential_state;
static uint32_t authenticated,login_failures;
static uint64_t login_retry_at;
static char login_id[32],legacy_password[64];
static uint32_t migration_verified;
static int grant_entry_locked(const MdSave *registration_before);
static int settle_rewards_locked(void);
static int pack_resume(void);
static void pack_recover(void);
static uint32_t touchline_open,touchline_focus;
#include "manager_league_pin.inc"
static int auth_read(const char *path) {
  MdCredential c;FILE *f=fopen(path,"rb");if(!f)return 0;
  int ok=fread(&c,1,sizeof(c),f)==sizeof(c) && fgetc(f)==EOF;fclose(f);
  if(ok && md_auth_valid(&c,md.seed,profile.user_id)){credential=c;md_auth_wipe(&c,sizeof(c));return 1;}
  md_auth_wipe(&c,sizeof(c));return 0;
}
static void auth_load(void) {
  credential_state=0;md_auth_wipe(&credential,sizeof(credential));
  if(!md.joined || !profile_ready)return;
  if(auth_read(MD_AUTH_FILE) || auth_read(MD_AUTH_FILE ".bak")){credential_state=1;return;}
  struct stat state;
  const int first_missing=stat(MD_AUTH_FILE,&state) && errno==ENOENT;
  const int backup_missing=stat(MD_AUTH_FILE ".bak",&state) && errno==ENOENT;
  if(!first_missing || !backup_missing)credential_state=-1;
}
static int auth_store(void) {
  uint8_t salt[16];
#ifdef __SWITCH__
  randomGet(salt,sizeof(salt));
#else
  FILE *random=fopen("/dev/urandom","rb");if(!random)return 0;
  int random_ok=fread(salt,1,sizeof(salt),random)==sizeof(salt);fclose(random);if(!random_ok)return 0;
#endif
  if(credential_state==1 && credential.version==1 && !migration_verified) {md_auth_wipe(salt,sizeof(salt));return 0;}
  MdCredential c;int ok=pin_confirmed && md_auth_create(&c,md.seed,profile.user_id,pin_value,salt);md_auth_wipe(salt,sizeof(salt));
  if(!ok)return 0;
  FILE *f=fopen(MD_AUTH_FILE ".tmp","wb");ok=0;
  if(f){ok=fwrite(&c,1,sizeof(c),f)==sizeof(c) && !fflush(f);if(fclose(f))ok=0;}
  if(ok){remove(MD_AUTH_FILE ".bak");FILE *old=fopen(MD_AUTH_FILE,"rb");if(old){fclose(old);if(rename(MD_AUTH_FILE,MD_AUTH_FILE ".bak"))ok=0;}
    if(ok && rename(MD_AUTH_FILE ".tmp",MD_AUTH_FILE)){rename(MD_AUTH_FILE ".bak",MD_AUTH_FILE);ok=0;}}
  if(ok){credential=c;credential_state=1;}else remove(MD_AUTH_FILE ".tmp");md_auth_wipe(&c,sizeof(c));return ok;
}
static void auth_clear_inputs(void) {
  pin_clear();md_auth_wipe(legacy_password,sizeof(legacy_password));
}
static void auth_enter_hub(void) {
  authenticated=1;auth_clear_inputs();page=MD_DASHBOARD;focus=dashboard_focus=hub_section=0;
  login_failures=0;login_retry_at=0;migration_verified=0;notice[0]=0;
  tutorial=profile.tutorials==7 ? 0 : 1;
  while(tutorial && (profile.tutorials&(1u<<(tutorial-1))))tutorial=tutorial<3 ? tutorial+1 : 0;
  if(grant_entry_locked(NULL))settle_rewards_locked();
  if(!tutorial)pack_resume();
}
static void auth_logout(void) {
  authenticated=0;migration_verified=0;auth_clear_inputs();md_auth_wipe(login_id,sizeof(login_id));
  page=MD_REGISTER;focus=0;replay=paused=editor=restore_pending=tutorial=action=touchline_open=0;
  notice[0]=0;
}
static uint32_t timeline_serial;
static uint32_t schedule_group,schedule_group_auto=1;
static uint32_t schedule_groups[3];
static uint64_t roster_lock_attempt;
static uint32_t calendar_day = 1, schedule_day;
static uint32_t checksum(const MdSave *s) {
  MdSave copy = *s;
  copy.checksum = 0;
  const unsigned char *p = (const unsigned char *)&copy;
  uint32_t h = 2166136261u;
  for (size_t i = 0; i < sizeof(copy); i++)
    h = (h ^ p[i]) * 16777619u;
  return h;
}
static uint32_t day_duration(const MdSave *save) {
  return save && save->day_ms ? save->day_ms : MD_DEMO_DAY_MS;
}
#include "manager_league_calendar.inc"
uint32_t manager_dummy_elapsed(const MdFixture *f, uint64_t now) {
  if (now <= f->kickoff_ms)
    return 0;
  const uint64_t delta = now - f->kickoff_ms;
  const uint32_t duration=manager_dummy_duration(f);
  return delta >= duration ? duration : (uint32_t)delta;
}
uint32_t manager_dummy_phase(const MdFixture *f, uint64_t now) {
  return now < f->kickoff_ms ? 0u : now - f->kickoff_ms < manager_dummy_duration(f) ? 1u : 2u;
}
MdWeek manager_dummy_week(const MdSave *save, uint64_t stamp) {
  MdWeek week = {MD_PRE_LEAGUE, 1, 0, 0};
  if (!save || !save->joined)
    return week;
  uint64_t first = UINT64_MAX, last_end = 0;
  const uint32_t day_ms=day_duration(save);
  for (uint32_t i = 0; i < MD_FIXTURES; i++) {
    const uint64_t kickoff = save->fixtures[i].kickoff_ms;
    if (kickoff < first)
      first = kickoff;
    const uint64_t end=kickoff+manager_dummy_duration(&save->fixtures[i]);
    if (end > last_end)
      last_end = end;
  }
  week.first_kickoff_ms = first;
  if(save->day_ms==MD_CALENDAR_DAY_MS) {
    week.result_ms=last_end;week.day=calendar_weekday(stamp);
    week.state=stamp<competition_start(save) ? MD_PRE_LEAGUE : stamp<last_end ? MD_MATCH_DAY : MD_RESULT;
    return week;
  }
  week.result_ms = first + 3u * (uint64_t)day_ms;
  /* A postponed fixture keeps the cycle open; day seven cannot fabricate a
   * completed table. No outcome is read before the final broadcast ends. */
  if (last_end > week.result_ms)
    week.result_ms = last_end;
  if (stamp < first) {
    const uint64_t remaining = first - stamp;
    week.day = remaining > 2u * MD_PREPARATION_DAY_MS ? 1u : remaining > MD_PREPARATION_DAY_MS ? 2u : 3u;
  } else if (stamp < week.result_ms) {
    week.state = MD_MATCH_DAY;
    const uint64_t day = (stamp - first) / day_ms;
    week.day = 4u + (day > 2u ? 2u : (uint32_t)day);
  } else {
    week.state = MD_RESULT;
    week.day = 7;
  }
  return week;
}
void manager_dummy_score(const MdFixture *f, uint32_t elapsed, uint32_t out[2]) {
  out[0] = out[1] = 0;
  for (uint32_t i = 0; i < manager_dummy_event_count(f); i++)
    if (f->events[i].at_ms <= elapsed && f->events[i].goal && f->events[i].side < 2u)
      out[f->events[i].side]++;
}
int manager_dummy_valid(const MdSave *s) {
  if (s->magic != MD_MAGIC || s->version != 2 || s->bytes != sizeof(*s) ||
      s->checksum != checksum(s) || s->created > 1 || s->joined > 1 || s->joined > s->created ||
      s->week_id < 1 || s->week_id > 9999 ||
      (s->day_ms != MD_DEMO_DAY_MS && s->day_ms != MD_LEGACY_DAY_MS && s->day_ms!=MD_CALENDAR_DAY_MS) ||
      (s->purchased_mask & ~(MD_LEGACY_PURCHASES|MD_ENTRY_GRANTED|MD_REWARD_SETTLED)) ||
      ((s->purchased_mask&(MD_ENTRY_GRANTED|MD_REWARD_SETTLED)) && !s->joined) ||
      ((s->purchased_mask&MD_REWARD_SETTLED) && !(s->purchased_mask&MD_ENTRY_GRANTED)) ||
      s->formation > 2 || s->mentality > 2 || s->tempo > 2 ||
      !memchr(s->name, 0, sizeof(s->name)) || (s->club && !exhibition_team_catalog_find(s->club)) ||
      (s->created && !s->club) || s->clock_offset_ms < -INT64_C(315360000000) ||
      s->clock_offset_ms > INT64_C(315360000000))
    return 0;
  uint32_t spent = 0;
  for (uint32_t i = 0; i < 3; i++)
    if (s->purchased_mask & (1u << i))
      spent += shop_prices[i];
  /* Older weeks had only the onboarding grant. New joins add one grant in
   * the durable season/profile transition; do not retroactively mint cash. */
  const uint64_t granted=(uint64_t)s->balance+spent;
  if (spent > 5000 || granted<MD_STARTING_CASH || granted%500 ||
      granted>MD_STARTING_CASH+(uint64_t)s->week_id*(MD_ENTRY_CASH+5000u))
    return 0;
  if (!s->joined)
    return 1;
  uint32_t pairs[MD_TEAMS][MD_TEAMS] = {{0}};
  for (uint32_t i = 0; i < MD_FIXTURES; i++) {
    const MdFixture *f = &s->fixtures[i];
    if (f->home >= MD_TEAMS || f->away >= MD_TEAMS || f->home == f->away || f->round >= 7 ||
        f->kickoff_ms < 1000000000000ULL || f->kickoff_ms > 5000000000000ULL ||
        !((f->duration_ms==MD_DURATION && f->event_count==MD_EVENTS) ||
          (f->duration_ms==MD_LEGACY_DURATION && f->event_count==MD_LEGACY_EVENTS)))
      return 0;
    uint32_t a = f->home < f->away ? f->home : f->away, b = f->home ^ f->away ^ a;
    if (pairs[a][b]++)
      return 0;
    for (uint32_t j = 0; j < i; j++) {
      const MdFixture *other=&s->fixtures[j];
      if (other->home == f->home || other->away == f->home ||
          other->home == f->away || other->away == f->away) {
        if (other->round == f->round ||
            (other->kickoff_ms < f->kickoff_ms+f->duration_ms &&
             f->kickoff_ms < other->kickoff_ms+manager_dummy_duration(other)))return 0;
      }
    }
    uint32_t active[2][11];
    for (uint32_t a = 0; a < 2; a++)
      for (uint32_t n = 0; n < 11; n++)
        active[a][n] = n + 1;
    uint32_t used[2] = {0};
    uint32_t halves=0;
    for (uint32_t j = 0; j < f->event_count; j++) {
      const MdEvent *e = &f->events[j];
      if (e->side > 1 || e->kind > MD_HALF || e->goal != (e->kind == MD_GOAL) ||
          e->at_ms != (j + 1) * 6000u || e->at_ms>=f->duration_ms || e->player < 1 || e->player > 18 ||
          (e->kind==MD_HALF && (++halves!=1 || e->at_ms!=f->duration_ms/2u)))
        return 0;
      uint32_t n = 0;
      while (n < 11 && active[e->side][n] != e->player)
        n++;
      if (n == 11)
        return 0;
      if (e->kind == MD_SUB) {
        if (!n || e->other < 12 || e->other > 18 || (used[e->side] & (1u << e->other)))
          return 0;
        used[e->side] |= 1u << e->other;
        active[e->side][n] = e->other;
      } else if(e->kind==MD_PASS && e->other) {
        uint32_t receiver=0;while(receiver<11 && active[e->side][receiver]!=e->other)receiver++;
        if(receiver==11 || e->other==e->player)return 0;
      } else if (e->other)
        return 0;
    }
    if(halves!=1)return 0;
    for(uint32_t j=f->event_count;j<MD_EVENTS;j++) {
      static const MdEvent zero={0};if(memcmp(&f->events[j],&zero,sizeof(zero)))return 0;
    }
  }
  return 1;
}
static int read_file(const char *path, MdSave *out) {
  FILE *f = fopen(path, "rb");
  if (!f)
    return 0;
  const int ok = fread(out, 1, sizeof(*out), f) == sizeof(*out) && fgetc(f) == EOF;
  fclose(f);
  return ok && manager_dummy_valid(out);
}
#include "manager_league_archive.inc"
static int persist(void) {
  if (blocked)
    return 0;
  md.magic = MD_MAGIC;
  md.version = 2;
  md.bytes = sizeof(md);
  if(!md.week_id)md.week_id=1;
  if(!md.day_ms)md.day_ms=MD_DEMO_DAY_MS;
  md.checksum = checksum(&md);
  mkdir("SaveData", 0700);
  FILE *f = fopen(MD_FILE ".tmp", "wb");
  int ok = 0;
  if (f) {
    ok = fwrite(&md, 1, sizeof(md), f) == sizeof(md) && fflush(f) == 0;
    if (fclose(f) != 0)
      ok = 0;
  }
  if (ok) {
    /* Keep the last valid record until the new temporary record is complete.
     * Only these three dedicated dummy paths are ever touched. */
    remove(MD_FILE ".bak");
    if (rename(MD_FILE, MD_FILE ".bak") != 0) {
      FILE *old = fopen(MD_FILE, "rb");
      if (old) {
        fclose(old);
        ok = 0;
      }
    }
    if (ok && rename(MD_FILE ".tmp", MD_FILE) != 0) {
      rename(MD_FILE ".bak", MD_FILE);
      ok = 0;
    }
  }
  snprintf(notice, sizeof(notice), "%s",
           ok ? "" : "Could not save your club. Please try again.");
  return ok;
}
static int active_pair_verified(void) {
  MdSave *saved=calloc(1,sizeof(*saved));MdProfile *players=calloc(1,sizeof(*players));
  int ok=saved && players && read_file(MD_FILE,saved) && !memcmp(saved,&md,sizeof(md));
  FILE *f=ok ? fopen(MD_PROFILE_FILE,"rb") : NULL;
  ok=f && fread(players,1,sizeof(*players),f)==sizeof(*players) && fgetc(f)==EOF;
  if(f)fclose(f);
  ok=ok && profile_valid(players) && !memcmp(players,&profile,sizeof(profile));
  free(saved);free(players);return ok;
}
static int finish_transition(void) {
  /* Never permit later purchases while a prepared journal can still restore
   * an older wallet on restart. Failure to clear it keeps editing blocked. */
  if(remove(MD_PENDING_FILE) || file_exists(MD_PENDING_FILE))return 0;
  remove(MD_PENDING_FILE ".bak");return 1;
}
#include "manager_league_wallet.inc"
#include "manager_league_pack.inc"
static void load_once(void) {
  if (loaded)
    return;
  loaded = 1;
  if(cash_recover()){if(!blocked && profile_ready)pack_recover();return;}
  /* A durable two-record journal finishes an interrupted season rollover.
   * It is removed only after both active files have been verified on disk. */
  if(file_exists(MD_PENDING_FILE)) {
    MdArchive *pending=calloc(1,sizeof(*pending));
    if(pending && archive_read(MD_PENDING_FILE,pending)) {
      char previous_path[96];archive_path(previous_path,pending->save.week_id-1u);
      MdArchive *previous=calloc(1,sizeof(*previous));
      int ok=pending->save.week_id>1u && previous && archive_read(previous_path,previous) &&
             previous->save.week_id+1u==pending->save.week_id && previous->save.seed==pending->save.seed &&
             previous->save.club==pending->save.club;
      if(ok){md=pending->save;profile=pending->players;profile_ready=1;profile_cache();
        ok=persist() && profile_save() && active_pair_verified();}
      free(previous);
      if(ok)ok=finish_transition();
      if(ok)notice[0]=0;
      else {blocked=1;snprintf(notice,sizeof(notice),"Could not finish saving the next week. Restart to retry.");}
    } else {blocked=1;snprintf(notice,sizeof(notice),"Season recovery is unavailable. Existing files are preserved.");}
    free(pending);if(!blocked && profile_ready)pack_recover();return;
  }
  if (read_file(MD_FILE, &md)) {
    if (md.joined)
      profile_load();
    if(profile_ready)pack_recover();
    return;
  }
  if (read_file(MD_FILE ".bak", &md)) {
    if (md.joined)
      profile_load();
    if(profile_ready)pack_recover();
    snprintf(notice, sizeof(notice), "RECOVERED LAST VALID OFFLINE PROFILE");
    return;
  }
  FILE *f = fopen(MD_FILE, "rb"), *b = fopen(MD_FILE ".bak", "rb");
  if (f || b) {
    if (f)
      fclose(f);
    if (b)
      fclose(b);
    blocked = 1;
    snprintf(notice, sizeof(notice), "OFFLINE SAVE INVALID - ORIGINAL FILES PRESERVED");
  }
  if(!blocked) {
    if(read_legacy(MD_LEGACY_FILE,&md) || read_legacy(MD_LEGACY_FILE ".bak",&md)) {
      if(!persist()){blocked=1;snprintf(notice,sizeof(notice),"Could not import your league. Original files are preserved.");}
      if(md.joined)profile_load();
      if(profile_ready)pack_recover();
      return;
    }
    if(file_exists(MD_LEGACY_FILE) || file_exists(MD_LEGACY_FILE ".bak")) {
      blocked=1;snprintf(notice,sizeof(notice),"OFFLINE SAVE INVALID - ORIGINAL FILES PRESERVED");
    }
  }
  memset(&md, 0, sizeof(md));
  md.balance = 5000;
  md.week_id=1;md.day_ms=MD_DEMO_DAY_MS;
  md.seed = (uint32_t)(epoch_now ^ (epoch_now >> 32)) | 1u;
}
static uint64_t now(void) {
  int64_t t = (int64_t)epoch_now + md.clock_offset_ms;
  return t < 0 ? 0u : (uint64_t)t;
}
static const char *team_name(uint32_t team) {
  return !team           ? (md.name[0] ? md.name : "YOUR CLUB")
         : profile_ready ? exhibition_team_catalog_name(profile.clubs[team])
                         : "CLUB";
}
static uint32_t badge(uint32_t team) {
  return exhibition_team_catalog_badge(!team ? md.club : profile_ready ? profile.clubs[team] : 0);
}
enum { MD_NEWS_MAX=MD_FIXTURES+MD_TEAMS+MD_PACKS };
/* A projection of saved receipts, immutable fixture results and actual club
 * registrations. A future API journal can supply the same typed rows; opening
 * News never invents a transfer or changes another club's roster. */
static uint32_t news_rows(MdRow out[MD_NEWS_MAX]) {
  uint32_t n=0;memset(out,0,MD_NEWS_MAX*sizeof(*out));
  for(uint32_t k=0;k<MD_PACKS;k++)if(profile.receipts&(1u<<k)) {
    MdRow *r=&out[n++];r->badge=badge(0);r->enabled=1;r->team_id=0;
    snprintf(r->label,sizeof(r->label),"%.40s STRENGTHENS ITS SQUAD",team_name(0));
    snprintf(r->detail,sizeof(r->detail),"%u players confirmed from %.35s. View your collection.",pack_draws[k],exhibition_team_catalog_name(pack_clubs[k]));
    snprintf(r->value,sizeof(r->value),"TRANSFER");
  }
  /* Reverse order groups the newest round first. Only full-time scores are
   * published, so a scheduled result can never leak through the news desk. */
  for(uint32_t i=MD_FIXTURES;i;i--) {
    const MdFixture *f=&md.fixtures[i-1];if(manager_dummy_phase(f,now())!=2)continue;
    uint32_t g[2];manager_dummy_score(f,MD_DURATION,g);MdRow *r=&out[n++];
    uint32_t winner=g[0]>g[1] ? f->home : f->away;
    r->badge=badge(g[0]==g[1] ? f->home : winner);r->enabled=1;r->team_id=winner;
    r->identity=i; /* one-based immutable fixture index for Watch Replay */
    if(g[0]==g[1])snprintf(r->label,sizeof(r->label),"POINTS SHARED IN ROUND %u",f->round+1);
    else snprintf(r->label,sizeof(r->label),"%.43s TAKES THREE POINTS",team_name(winner));
    snprintf(r->detail,sizeof(r->detail),"%.32s %u - %u %.32s",team_name(f->home),g[0],g[1],team_name(f->away));
    snprintf(r->value,sizeof(r->value),"RESULT");
  }
  for(uint32_t t=0;t<MD_TEAMS;t++) {
    MdRow *r=&out[n++];r->badge=badge(t);r->enabled=1;r->team_id=t;
    snprintf(r->label,sizeof(r->label),"%.40s JOINS THE TITLE RACE",team_name(t));
    snprintf(r->detail,sizeof(r->detail),"%u registered players. Open club and player profiles.",profile.counts[t]);
    snprintf(r->value,sizeof(r->value),"LEAGUE");
  }
  return n;
}
static void table_rows(MdRow out[7]) {
  uint32_t pts[7] = {0}, gf[7] = {0}, played[7] = {0}, wins[7] = {0}, draws[7] = {0},
           losses[7] = {0}, order[7] = {0, 1, 2, 3, 4, 5, 6};
  int diff[7] = {0};
  for (uint32_t i = 0; i < 21; i++) {
    const MdFixture *f = &md.fixtures[i];
    if (manager_dummy_phase(f, now()) != 2)
      continue;
    uint32_t g[2];
    manager_dummy_score(f, MD_DURATION, g);
    uint32_t a = f->home, b = f->away;
    played[a]++;
    played[b]++;
    gf[a] += g[0];
    gf[b] += g[1];
    diff[a] += (int)g[0] - (int)g[1];
    diff[b] -= (int)g[0] - (int)g[1];
    pts[a] += g[0] > g[1] ? 3 : g[0] == g[1];
    pts[b] += g[1] > g[0] ? 3 : g[0] == g[1];
    if (g[0] > g[1]) {
      wins[a]++;
      losses[b]++;
    } else if (g[1] > g[0]) {
      wins[b]++;
      losses[a]++;
    } else {
      draws[a]++;
      draws[b]++;
    }
  }
  for (uint32_t i = 0; i < 7; i++)
    for (uint32_t j = i + 1; j < 7; j++) {
      uint32_t a = order[i], b = order[j];
      if (pts[b] > pts[a] ||
          (pts[b] == pts[a] && (diff[b] > diff[a] || (diff[b] == diff[a] && gf[b] > gf[a])))) {
        order[i] = b;
        order[j] = a;
      }
    }
  memset(out, 0, sizeof(MdRow) * 7);
  for (uint32_t i = 0; i < 7; i++) {
    uint32_t t = order[i];
    out[i].team_id = t;
    out[i].badge = badge(t);
    out[i].enabled = 1;
    out[i].stats = (LeagueStanding){
        t,     played[t], wins[t], draws[t], losses[t], gf[t], (uint32_t)((int)gf[t] - diff[t]),
        pts[t]};
    snprintf(out[i].label, sizeof(out[i].label), "%u  %s", i + 1, team_name(t));
    snprintf(out[i].value, sizeof(out[i].value), "%u  %+d  %u", played[t], diff[t], pts[t]);
  }
}
#include "manager_league_ranking.inc"
static void overall_rows(MdRow out[7]) {
  uint32_t rp[7], order[7] = {0, 1, 2, 3, 4, 5, 6};
  ranking_points(rp);
  for (uint32_t i = 0; i < 7; i++)
    for (uint32_t j = i + 1; j < 7; j++)
      if (rp[order[j]] > rp[order[i]]) {
        uint32_t t = order[i];
        order[i] = order[j];
        order[j] = t;
      }
  for (uint32_t i = 0; i < 7; i++) {
    uint32_t t = order[i];
    char name[64], value[40];
    snprintf(name, sizeof(name), "%u  %.56s", i + 1, team_name(t));
    snprintf(value, sizeof(value), "%u RP", rp[t]);
    memset(&out[i], 0, sizeof(out[i]));
    out[i].team_id = t;
    out[i].badge = badge(t);
    out[i].enabled = 1;
    snprintf(out[i].label, sizeof(out[i].label), "%s", name);
    snprintf(out[i].value, sizeof(out[i].value), "%s", value);
    snprintf(out[i].detail, sizeof(out[i].detail), "%s",
             "Earned in the current 14-day ranking period");
  }
}
static void make_fixtures(void) {
  const uint64_t prior=md.week_id>1 ? md.fixtures[0].kickoff_ms : 0;
  md.day_ms=MD_CALENDAR_DAY_MS;
  const uint64_t kickoff=calendar_preparation(now(),prior)+MD_CALENDAR_DAY_MS+12u*3600000u;
  uint32_t ring[8] = {0, 1, 2, 3, 4, 5, 6, 7}, n = 0;
  /* Keep account identity stable while each successor week owns a different
   * deterministic tape. Week one retains its existing seed stream. */
  uint32_t seed=md.seed^((md.week_id ? md.week_id : 1u)-1u)*0x9e3779b9u;
  for (uint32_t round = 0; round < 7; round++) {
    for (uint32_t i = 0; i < 4; i++) {
      uint32_t a = ring[i], b = ring[7 - i];
      if (a == 7 || b == 7)
        continue;
      if ((b + 7 - a) % 7 > 3u) {
        uint32_t t = a;
        a = b;
        b = t;
      }
      MdFixture *f = &md.fixtures[n++];
      memset(f, 0, sizeof(*f));
      f->home = a;
      f->away = b;
      f->round = round;
      static const uint32_t slot_hours[]={0,3,6,8,24,27,30};
      const uint64_t offset=slot_hours[round]*UINT64_C(3600000);
      f->kickoff_ms = kickoff + offset;
      f->seed = rng(&seed);
      f->duration_ms=MD_DURATION;f->event_count=MD_EVENTS;
      uint32_t s = f->seed, active[2][11];
      for (uint32_t side = 0; side < 2; side++)
        for (uint32_t p = 0; p < 11; p++)
          active[side][p] = p + 1;
      static const uint32_t kinds[24] = {
          MD_PASS,MD_PASS,MD_PASS,MD_SHOT,MD_SAVE,MD_PASS,MD_PASS,MD_FOUL,
          MD_PASS,MD_PASS,MD_CORNER,MD_PASS,MD_PASS,MD_SHOT,MD_PASS,MD_OFFSIDE,
          MD_PASS,MD_PASS,MD_SAVE,MD_PASS,MD_YELLOW,MD_PASS,MD_PASS,MD_PASS};
      /* Outcomes belong to the immutable fixture tape. Prefer ordinary low
       * scoring games, including goalless draws, without forcing every game
       * to contain the same number of goals. The legal opportunity slots are
       * separated from half-time/substitutions and allow full goal restarts. */
      static const uint8_t goal_weights[16]={0,0,1,1,1,2,2,2,2,3,3,3,3,4,4,5};
      uint32_t goal_seed=f->seed^(f->seed>>16);
      goal_seed*=0x7feb352du;goal_seed^=goal_seed>>15;
      const uint32_t goal_count=goal_weights[goal_seed&15u];
      uint32_t goal_slots[9]={11,21,33,41,57,68,74,83,95};
      for(uint32_t j=8;j;j--) {
        uint32_t k=(rng(&goal_seed)>>16)%(j+1u),swap=goal_slots[j];
        goal_slots[j]=goal_slots[k];goal_slots[k]=swap;
      }
      uint32_t substitutes[2]={12,12},possession=0,carrier=8;
      for (uint32_t j = 0; j < MD_EVENTS; j++) {
        MdEvent *e = &f->events[j];
        e->at_ms = (j + 1) * 6000u;
        uint32_t choice=rng(&s)>>16;
        e->side = possession;
        e->kind = kinds[j%24u];
        for(uint32_t g=0;g<goal_count;g++)if(j==goal_slots[g])e->kind=MD_GOAL;
        if(j==49)e->kind=MD_HALF;
        if(j==65 || j==79 || j==87 || j==93) {
          e->kind=MD_SUB;e->side=(j==65 || j==87) ? 0u : 1u;
        }
        e->goal = e->kind == MD_GOAL;
        uint32_t slot = 1 + (rng(&s) >> 16) % 10u;
        if(e->kind==MD_PASS) {
          if(j && (choice%12u)==0){possession^=1u;carrier=active[possession][4+choice%4u];}
          e->side=possession;slot=0;while(slot<11 && active[possession][slot]!=carrier)slot++;
          if(slot>=11)slot=6;
          /* Pass to a neighbouring support lane rather than alternating the
           * attacking team and choosing a distant random actor each event. */
          uint32_t receiver=slot==0 ? 2u : slot<5 ? 5u+choice%3u : slot<8 ? 5u+choice%6u : 5u+choice%3u;
          if(receiver==slot)receiver=slot==10 ? 7u : slot+1u;
          e->other=active[possession][receiver];carrier=e->other;
        } else if(e->kind==MD_FOUL || e->kind==MD_YELLOW) {
          e->side=1u-possession;slot=1u+choice%7u;carrier=active[possession][5u+choice%3u];
        } else if(e->kind!=MD_SUB && e->kind!=MD_HALF)slot=8u+choice%3u;
        e->player = active[e->side][slot];
        if (e->kind == MD_SUB) {
          e->other = substitutes[e->side]++;
          active[e->side][slot] = e->other;
          if(e->side==possession && carrier==e->player)carrier=e->other;
        }
        if(e->kind==MD_GOAL){possession^=1u;carrier=active[possession][7];}
        else if(e->kind==MD_SHOT || e->kind==MD_SAVE || e->kind==MD_OFFSIDE){possession^=1u;carrier=active[possession][0];}
        else if(e->kind==MD_HALF){possession=1;carrier=active[1][7];}
        else if(e->kind==MD_CORNER)carrier=active[possession][8u+choice%3u];
      }
    }
    const uint32_t last = ring[7];
    for (uint32_t j = 7; j > 1; j--)
      ring[j] = ring[j - 1];
    ring[1] = last;
  }
}
static int next_week_locked(void) {
  int ok=0;MdArchive *previous=NULL,*next=NULL;
  if(blocked || profile_blocked || !profile_ready || !md.joined || md.week_id>=9999 ||
     manager_dummy_week(&md,now()).state!=MD_RESULT)goto done;
  if(pack_pending){snprintf(notice,sizeof(notice),"Choose the players from your paid pack before joining the next league.");goto done;}
  if(!settle_rewards_locked())goto done;
  previous=calloc(1,sizeof(*previous));next=calloc(1,sizeof(*next));
  if(!previous || !next)goto done;
  previous->save=md;previous->players=profile;
  char path[96];archive_path(path,md.week_id);
  if(!archive_write(path,previous))goto done;
  md.week_id++;md.balance+=MD_ENTRY_CASH;profile.balance+=MD_ENTRY_CASH;
  md.purchased_mask=(md.purchased_mask&MD_LEGACY_PURCHASES)|MD_ENTRY_GRANTED;
  make_fixtures();profile.roster_locked=0;roster_lock_pending=0;
  for(uint32_t t=0;t<MD_TEAMS;t++)memcpy(profile.match_roster[t],profile.roster[t],18*sizeof(uint32_t));
  next->save=md;next->players=profile;
  if(!archive_write(MD_PENDING_FILE,next)) {
    md=previous->save;profile=previous->players;profile_cache();goto done;
  }
  /* Both complete records and the prior replay snapshot are now durable.
   * On interruption load_once finishes this same transition, never rerolls. */
  md=next->save;profile=next->players;
  if(!persist() || !profile_save()) {
    blocked=1;snprintf(notice,sizeof(notice),"Could not finish saving the next week. Restart to retry.");goto done;
  }
  if(!active_pair_verified()) {blocked=1;snprintf(notice,sizeof(notice),"Next week needs save recovery. Restart to retry.");goto done;}
  if(!finish_transition()){blocked=1;snprintf(notice,sizeof(notice),"Next week needs save recovery. Restart to retry.");goto done;}
  history_week=0;timeline_serial++;
  profile_cache();notice[0]=0;ok=1;
done:
  free(previous);free(next);
  if(!ok && !notice[0])snprintf(notice,sizeof(notice),"Could not start the next week. Your existing league is preserved.");
  return ok;
}
int manager_dummy_next_week(void) {
  pthread_mutex_lock(&md_mutex);int ok=authenticated && next_week_locked();pthread_mutex_unlock(&md_mutex);return ok;
}
void manager_dummy_tick_at(uint64_t ms) {
  pthread_mutex_lock(&md_mutex);
  const uint64_t delta = last_tick && ms >= last_tick ? ms - last_tick : 0;
  last_tick = ms;
  epoch_now = ms;
  if (profile_ready && md.joined && !profile.roster_locked &&
      now() >= competition_start(&md)) {
    profile.roster_locked = 1;
    roster_lock_pending = 1;
  }
  if (roster_lock_pending && (!roster_lock_attempt || ms - roster_lock_attempt >= 5000u)) {
    roster_lock_attempt = ms;
    if (profile_save())
      roster_lock_pending = 0;
    else
      snprintf(notice, sizeof(notice), "MATCH LINEUP LOCKED - SAVE RETRY PENDING");
  }
  if (page == MD_PACK_OPENING && ms >= pack_opened_at && ms - pack_opened_at >= MD_PACK_OPEN_MS) {
    page = MD_PACK_SELECT;
    focus = 0;
  }
  if (page == MD_WATCH && replay && !paused)
    replay_ms = (uint32_t)fmin((double)manager_dummy_duration(watch_fixture()), (double)replay_ms + (double)delta);
  if(authenticated && profile_ready && md.joined && !blocked && (!cash_retry_at || ms>=cash_retry_at)) {
    cash_retry_at=ms+5000u;
    if(grant_entry_locked(NULL))settle_rewards_locked();
  }
  pthread_mutex_unlock(&md_mutex);
}
void manager_dummy_tick(uint64_t monotonic_ms) {
  (void)monotonic_ms;
  struct timespec ts;
  if (clock_gettime(CLOCK_REALTIME, &ts) == 0 && ts.tv_sec > 0)
    manager_dummy_tick_at((uint64_t)ts.tv_sec * 1000u + (uint64_t)ts.tv_nsec / 1000000u);
}
void manager_dummy_open(void) {
  manager_dummy_tick(0);
#ifdef __SWITCH__
  TimeCalendarTime calendar;
  TimeCalendarAdditionalInfo info;
  if (R_SUCCEEDED(timeToCalendarTimeWithMyRule(epoch_now / 1000u, &calendar, &info))) {
    manager_timezone_offset = info.offset;
    manager_timezone_ready = 1;
  }
#endif
  pthread_mutex_lock(&md_mutex);
  load_once();
  auth_load();
  page=authenticated && md.joined && profile_ready ? MD_DASHBOARD : MD_REGISTER;
  if(authenticated && credential_state==1 && credential.version==1) {
    migration_verified=1;page=MD_SECURE;
  }
  focus = dashboard_focus = hub_section = 0;
  if(page==MD_REGISTER && !md.joined)focus=1;
  navigation_serial++;
  slide_direction = 0;
  action = 0;
  replay = paused = 0;
  timeline_serial++;
  if (page == MD_DASHBOARD && profile.tutorials != 7) {
    tutorial = 1;
    while (tutorial <= 3 && (profile.tutorials & (1u << (tutorial - 1))))
      tutorial++;
    if (tutorial > 3)
      tutorial = 0;
  }
  pthread_mutex_unlock(&md_mutex);
}
const char *manager_dummy_name(void) {
  if(page==MD_LOGIN || page==MD_MIGRATE)return focus==0 ? login_id : "";
  if(page==MD_SECURE)return "";
  return focus == 1 ? profile.user_id : focus == 2 ? "" : md.name;
}
const char *manager_dummy_input_label(void) {
  if(page==MD_MIGRATE)return focus==0 ? "USER ID" : "OLD PASSWORD";
  if(page==MD_LOGIN)return focus==0 ? "USER ID" : "PIN";
  if(page==MD_SECURE)return "PIN";
  return focus == 1 ? "USER ID" : focus == 2 ? "PIN" : "TEAM NAME";
}
int manager_dummy_input_password(void) {
  return page==MD_MIGRATE && focus==1;
}
static void clear_password(void) {
  auth_clear_inputs();
}
void manager_dummy_name_result(const char *text) {
  pthread_mutex_lock(&md_mutex);
  if((page==MD_LOGIN || page==MD_MIGRATE) && text) {
    if(focus==0) {
      if(!md_auth_id(login_id,text))snprintf(notice,sizeof(notice),"Use 3-24 letters, numbers, dots or underscores.");
    } else if(page==MD_MIGRATE && focus==1) {
      md_auth_wipe(legacy_password,sizeof(legacy_password));
      size_t bytes=strlen(text);int valid=bytes>=8 && bytes<=63;
      for(size_t i=0;i<bytes && valid;i++)if((unsigned char)text[i]<32 || (unsigned char)text[i]>126)valid=0;
      if(valid)memcpy(legacy_password,text,bytes);
      else snprintf(notice,sizeof(notice),"Enter your previous password to replace it with a PIN.");
    }
    pthread_mutex_unlock(&md_mutex);return;
  }
  if (page == MD_NAME && text) {
    char clean[64] = {0};
    uint32_t n = 0;
    for (const unsigned char *p = (const unsigned char *)text; *p && n < sizeof(clean) - 1; p++)
      if (*p >= 32 && *p <= 126)
        clean[n++] = (char)*p;
    while (n && clean[n - 1] == ' ')
      clean[--n] = 0;
    uint32_t first = 0;
    while (clean[first] == ' ')
      first++;
    const char *value = clean + first;
    if (focus == 1) {
      int valid = strlen(value) >= 3 && strlen(value) <= 24;
      for (const char *p = value; *p; p++)
        if (!((*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') || (*p >= '0' && *p <= '9') ||
              *p == '_' || *p == '.'))
          valid = 0;
      if (valid)
        snprintf(profile.user_id, sizeof(profile.user_id), "%.24s", value);
      else
        snprintf(notice, sizeof(notice), "USER ID: 3-24 LETTERS, NUMBERS, DOT OR UNDERSCORE");
    } else if (!focus && *value) {
      snprintf(md.name, sizeof(md.name), "%.31s", value);
      persist();
    }
    volatile char *wipe = clean;
    for (size_t i = 0; i < sizeof(clean); i++)
      wipe[i] = 0;
  }
  pthread_mutex_unlock(&md_mutex);
}
uint32_t manager_dummy_take_action(void) {
  pthread_mutex_lock(&md_mutex);
  uint32_t value = action;
  action = 0;
  pthread_mutex_unlock(&md_mutex);
  return value;
}
void manager_dummy_copy_save(MdSave *out) {
  pthread_mutex_lock(&md_mutex);
  *out = md;
  pthread_mutex_unlock(&md_mutex);
}
static uint32_t schedule_indices(uint32_t out[MD_FIXTURES]) {
  uint32_t n = 0;memset(schedule_groups,0,sizeof(schedule_groups));
  for (uint32_t i = 0; i < MD_FIXTURES; i++) {
    const MdFixture *f=&broadcast_save()->fixtures[i];
    if(page==MD_TEAM_HISTORY && f->home!=team_choice && f->away!=team_choice)continue;
    uint32_t day = fixture_day(broadcast_save(),f);
    if(schedule_day && day!=schedule_day)continue;
    uint32_t phase=manager_dummy_phase(f,broadcast_now()),group=phase==1 ? 0u : phase==0 ? 1u : 2u;
    schedule_groups[group]++;
  }
  if(schedule_group_auto)schedule_group=schedule_groups[0] ? 0u : schedule_groups[1] ? 1u : 2u;
  for(uint32_t i=0;i<MD_FIXTURES;i++) {
    const MdFixture *f=&broadcast_save()->fixtures[i];
    if(page==MD_TEAM_HISTORY && f->home!=team_choice && f->away!=team_choice)continue;
    if(schedule_day && fixture_day(broadcast_save(),f)!=schedule_day)continue;
    uint32_t phase=manager_dummy_phase(f,broadcast_now()),group=phase==1 ? 0u : phase==0 ? 1u : 2u;
    if(group==schedule_group)out[n++]=i;
  }
  /* Finished games are newest first; upcoming/live games remain chronological. */
  for(uint32_t i=0;i<n;i++)for(uint32_t j=i+1;j<n;j++) {
    uint64_t a=broadcast_save()->fixtures[out[i]].kickoff_ms,b=broadcast_save()->fixtures[out[j]].kickoff_ms;
    if(schedule_group==2 ? b>a : b<a){uint32_t tmp=out[i];out[i]=out[j];out[j]=tmp;}
  }
  if(focus>=n)focus=n ? n-1u : 0;
  return n;
}
static void open_plan(void) {
  if (!profile_ready || profile_blocked) {
    snprintf(notice, sizeof(notice), "PLAYER PROFILE UNAVAILABLE");
    return;
  }
  if (shop_locked()) {
    snprintf(notice, sizeof(notice), "GAME PLAN LOCKED FOR THIS COMPETITION");
    return;
  }
  editor = 1;
  editor_return_page=page;editor_return_focus=focus;editor_return_section=hub_section;
  restore_pending = 0;
  action = MD_ACTION_PLAN;
}
uint32_t manager_dummy_cash(void) {
  pthread_mutex_lock(&md_mutex);uint32_t cash=profile_ready ? profile.balance : md.balance;
  pthread_mutex_unlock(&md_mutex);return cash;
}
static void advance_development_clock(void) {
  if(!development_clock_enabled() || !md.joined)return;
  const uint64_t stamp=now();uint64_t target=UINT64_MAX;
  for(uint32_t i=0;i<MD_FIXTURES;i++) {
    const MdFixture *f=&md.fixtures[i];uint32_t p=manager_dummy_phase(f,stamp);
    uint64_t candidate=p==0 ? f->kickoff_ms : p==1 ? f->kickoff_ms+manager_dummy_duration(f) : UINT64_MAX;
    if(candidate<target)target=candidate;
  }
  if(target==UINT64_MAX || target<=stamp || target-stamp>INT64_C(315360000000))return;
  const int64_t previous=md.clock_offset_ms;
  if(md.clock_offset_ms>INT64_C(315360000000)-(int64_t)(target-stamp))return;
  md.clock_offset_ms+=(int64_t)(target-stamp);
  if(!persist())md.clock_offset_ms=previous;
  timeline_serial++;
}
void manager_dummy_pad(uint32_t key) {
  pthread_mutex_lock(&md_mutex);
  const MdPage previous_page=page;
  /* Notices own input until acknowledged; the same press must never activate
   * the page underneath. Intro/confirmation errors belong to their modal. */
  if(notice[0] && !tutorial && page!=MD_LOGOUT && page!=MD_NEXT_WEEK) {
    if(key&(A|B))notice[0]=0;
    goto done;
  }
  if (blocked || profile_blocked) {
    if (key & B)
      action = MD_ACTION_EXIT;
    goto done;
  }
  if(pin_active){pin_pad(key);goto done;}
  if(touchline_open) {
    if(key&(B|Y)){touchline_open=0;goto done;}
    if((key&UP) && touchline_focus)touchline_focus--;
    else if((key&DOWN) && touchline_focus<MD_EVENTS)touchline_focus++;
    else if(key&R)touchline_focus=touchline_focus+5u>MD_EVENTS ? MD_EVENTS : touchline_focus+5u;
    else if(key&L)touchline_focus=touchline_focus>5 ? touchline_focus-5 : 0;
    goto done;
  }
  if (tutorial) {
    if (key & A) {
      MdProfile before = profile;
      profile.tutorials |= 1u << (tutorial - 1);
      if (profile_save()) {
        tutorial = tutorial < 3 ? tutorial + 1 : 0;
        while (tutorial && (profile.tutorials & (1u << (tutorial - 1))))
          tutorial = tutorial < 3 ? tutorial + 1 : 0;
        notice[0] = 0;
      } else {
        profile = before;
        snprintf(notice, sizeof(notice), "INTRODUCTION NOT SAVED - PRESS A TO RETRY");
      }
    }
    if(!tutorial)pack_resume();
    goto done;
  }
  if (key & B) {
    if(pack_pending && (page==MD_PACK_OPENING || page==MD_PACK_SELECT))goto done;
    timeline_serial++;
    if (page == MD_REGISTER || page == MD_DASHBOARD) {
      clear_password();
      action = MD_ACTION_EXIT;
    } else if(page==MD_LOGIN || page==MD_SECURE || page==MD_MIGRATE) {
      auth_clear_inputs();migration_verified=0;page=MD_REGISTER;focus=md.joined ? 0 : 1;notice[0]=0;
    } else if(page==MD_LOGOUT || page==MD_NEXT_WEEK) {
      page=MD_DASHBOARD;focus=dashboard_focus;notice[0]=0;
    } else if (page == MD_LEAGUES)
      page = MD_REGISTER;
    else if (page == MD_CLUB) {
      page = MD_LEAGUES;
      focus = category;
    } else if (page == MD_NAME) {
      clear_password();
      page = md.joined ? MD_REGISTER : MD_CLUB;
      focus = club_choice;
    } else if (page == MD_PLAYER_INFO) {
      page = MD_TEAM_INFO;
      focus = player_choice;
    } else if (page == MD_COLLECTION_PAGE) {
      page = MD_TEAM_INFO;
      focus = 0;
    } else if (page == MD_REPLACE_PLAYER) {
      page = MD_COLLECTION_PAGE;
      focus = collection_choice;
    } else if(page==MD_CLUB_PROFILE) {
      page=team_return;focus=team_return_focus;club_child=0;
    } else if(page==MD_CHAMPION){page=MD_CHAMPIONS;focus=champion_return_focus;}
    else if(page==MD_TEAM_HISTORY || page==MD_CLUB_PLAN || page==MD_REWARDS ||
              (club_child && (page==MD_TEAM_INFO || page==MD_TABLE || page==MD_OVERALL))) {
      history_week=0;schedule_day=0;page=MD_CLUB_PROFILE;focus=club_menu_focus;club_child=0;
    } else if (page == MD_TEAM_INFO) {
      page = team_return;focus = team_return_focus;
    } else if(page==MD_PACK_BUY) {
      page=MD_PACK;focus=0;
    } else if (page == MD_PACK_OPENING) {
      page = MD_SHOP;
      focus = pack_choice;
      pack_selected = 0;
    } else if (page == MD_PACK_SELECT) {
      page = MD_SHOP;
      focus = pack_choice;
      pack_selected = 0;
    } else if (page == MD_PACK_RESULT || page == MD_PACK) {
      page = MD_SHOP;
      focus = pack_choice;
    } else if (page == MD_WATCH) {
      page = watch_return;
      focus = watch_return_focus;
    }
    else if (page == MD_SCHEDULE && schedule_day) {
      history_week=0;
      page = MD_CALENDAR;
      focus = calendar_day - 1;
    } else {
      if(page==MD_SCHEDULE)history_week=0;
      page = MD_DASHBOARD;
      focus = dashboard_focus;
    }
    goto done;
  }
  if (page == MD_REGISTER) {
    if(key&(UP|DOWN|LEFT|RIGHT))focus^=1u;
    if (key & A) {
      notice[0]=0;auth_clear_inputs();
      if(focus==0) {
        if(!md.joined || !profile_ready)snprintf(notice,sizeof(notice),"No club is stored on this device. Choose Register.");
        else if(credential_state<0)snprintf(notice,sizeof(notice),"Account data could not be read. Your club has been preserved.");
        else {page=credential_state ? (credential.version==1 ? MD_MIGRATE : MD_LOGIN) : MD_SECURE;focus=0;md_auth_id(login_id,profile.user_id);}
      } else if(md.joined)snprintf(notice,sizeof(notice),"A club is already registered on this device. Choose Login.");
      else {page = MD_LEAGUES;category = club_choice = focus = 0;}
    }
    goto done;
  }
  if(page==MD_LOGIN || page==MD_SECURE || page==MD_MIGRATE) {
    const uint32_t last=page==MD_SECURE ? 1u : 2u;
    if((key&UP) && focus)focus--;
    else if((key&DOWN) && focus<last)focus++;
    else if((key&A) && focus<last) {
      if(page==MD_SECURE || (page==MD_LOGIN && focus==1))pin_open(page==MD_SECURE);
      else action=MD_ACTION_NAME;
    } else if(((key&A) && focus==last) || (key&X)) {
      if(page==MD_SECURE) {
        if(!pin_confirmed || !md_auth_pin_valid(pin_value))snprintf(notice,sizeof(notice),"Create and confirm your four-digit PIN.");
        else if(auth_store())auth_enter_hub();
        else snprintf(notice,sizeof(notice),"Could not save account details. Please try again.");
      } else if(epoch_now<login_retry_at)snprintf(notice,sizeof(notice),"Please wait before trying to log in again.");
      else if(md_auth_verify(&credential,md.seed,login_id,page==MD_MIGRATE ? legacy_password : pin_value)) {
        if(page==MD_MIGRATE) {
          auth_clear_inputs();migration_verified=1;page=MD_SECURE;focus=0;notice[0]=0;
        } else auth_enter_hub();
      }
      else {
        auth_clear_inputs();snprintf(notice,sizeof(notice),"%s",page==MD_MIGRATE ? "User ID or previous password is incorrect." : "User ID or PIN is incorrect.");
        if(++login_failures>=5){login_retry_at=epoch_now+30000u;login_failures=0;}
      }
    }
    goto done;
  }
  if(page==MD_LOGOUT || page==MD_NEXT_WEEK) {
    if(key&(UP|DOWN|LEFT|RIGHT))focus^=1u;
    if(key&A) {
      if(focus){page=MD_DASHBOARD;focus=dashboard_focus;}
      else if(page==MD_LOGOUT){auth_logout();history_week=0;timeline_serial++;}
      else if(next_week_locked()){page=MD_DASHBOARD;focus=dashboard_focus=hub_section=0;notice[0]=0;}
    }
    goto done;
  }
  if (page == MD_LEAGUES) {
    if ((key & UP) && focus)
      focus--;
    else if ((key & DOWN) && focus + 1 < EXHIBITION_TEAM_CATEGORY_COUNT)
      focus++;
    else if (key & A) {
      category = focus;
      club_choice = focus = 0;
      page = MD_CLUB;
    }
    goto done;
  }
  if (page == MD_CLUB) {
    const ExhibitionTeamCategory *c = &exhibition_team_categories[category];
    if ((key & UP) && club_choice)
      club_choice--;
    else if ((key & DOWN) && club_choice + 1 < c->team_count)
      club_choice++;
    else if ((key & A) && club_choice < c->team_count) {
      if (!ml_catalog_has_team(c->teams[club_choice])) {
        snprintf(notice, sizeof(notice), "CLUB PLAYER CATALOG UNAVAILABLE");
        goto done;
      }
      md.club = c->teams[club_choice];
      persist();
      profile_ready = 0;
      profile_load();
      packs_build();
      page = MD_NAME;
      focus = 0;
      notice[0] = 0;
    }
    goto done;
  }
  if (page == MD_NAME) {
    if ((key & UP) && focus)
      focus--;
    else if ((key & DOWN) && focus < 3)
      focus++;
    else if ((key & A) && focus < 3) {
      if(focus==2)pin_open(1);else action = MD_ACTION_NAME;
    }
    else if (((key & A) && focus == 3) || (key & X)) {
      if (!md.name[0] || !profile.user_id[0] || !pin_confirmed || !md_auth_pin_valid(pin_value)) {
        snprintf(notice, sizeof(notice), "COMPLETE TEAM NAME, USER ID AND PIN");
        goto done;
      }
      if (!profile_ready || now() < 1000000000000ULL || now() > 4999996000000ULL) {
        snprintf(notice, sizeof(notice), "CHECK CATALOG AND DEVICE DATE");
        goto done;
      }
      if (!profile_save()) {
        snprintf(notice, sizeof(notice), "PROFILE SAVE FAILED - PLEASE RETRY");
        goto done;
      }
      MdSave before_registration=md;
      if (!md.joined) {
        md.created = md.joined = 1;
        make_fixtures();
      }
      if (grant_entry_locked(&before_registration)) {
        if(auth_store())auth_enter_hub();
        else {page=MD_SECURE;focus=0;auth_clear_inputs();snprintf(notice,sizeof(notice),"Your club is saved. Set a PIN to finish registration.");}
      } else if(!blocked)md=before_registration;
    }
    goto done;
  }
  if (page == MD_DASHBOARD) {
    const uint32_t old = hub_section;
    if (key & (UP | DOWN | L | R | LEFT | RIGHT))
      fnx_hub_navigate_count(key, &hub_section, &focus, 3u);
    else if (key & A) {
      static const MdPage destinations[3][5] = {
          {MD_SCHEDULE, MD_NEWS, MD_CALENDAR, MD_TABLE, MD_CLUB_PROFILE},
          {MD_TEAM_INFO, MD_STRATEGY, MD_SHOP, MD_TEAM_INFO, MD_TEAMS_PAGE},
          {MD_TABLE, MD_CHAMPIONS, MD_SCHEDULE, MD_OVERALL, MD_RULES}};
      dashboard_focus = focus;
      MdPage dest = destinations[hub_section][focus];
      if (!hub_section && !focus) {
        const uint32_t stage = manager_dummy_week(&md, now()).state;
        if (stage == MD_PRE_LEAGUE)
          dest = MD_TEAM_INFO;
        else if (stage == MD_RESULT)
          dest = MD_TABLE;
      }
      if (dest == MD_STRATEGY) {
        open_plan();
        goto done;
      }
      page = dest;
      history_week=0;
      focus = 0;
      schedule_day = 0;
      club_child=0;
      if (page == MD_TEAM_INFO || page==MD_CLUB_PROFILE) {
        team_choice = 0;
        team_return = MD_DASHBOARD;
        team_return_focus = dashboard_focus;
      }
      if (page == MD_CALENDAR) {
        calendar_day = manager_dummy_week(&md, now()).day;
        focus = calendar_day - 1;
      }
      if (page == MD_SHOP) {
        shop_return = MD_DASHBOARD;
        packs_build();
      }
    } else if (key & X) {page=MD_LOGOUT;dashboard_focus=focus;focus=1;}
    else if((key&Y) && manager_dummy_week(&md,now()).state==MD_RESULT) {page=MD_NEXT_WEEK;dashboard_focus=focus;focus=1;}
    else if(key&Y)advance_development_clock();
    if (old != hub_section) {
      slide_direction = hub_section > old ? 1 : -1;
      navigation_serial++;
    }
    goto done;
  }
  if (page == MD_TABLE || page == MD_TEAMS_PAGE || page == MD_OVERALL) {
    if ((key & UP) && focus)
      focus--;
    else if ((key & DOWN) && focus < 6)
      focus++;
    else if (key & A) {
      MdRow ranked[7];
      if (page == MD_OVERALL)
        overall_rows(ranked);
      else
        table_rows(ranked);
      team_return = page;
      team_return_focus = focus;
      team_choice = page == MD_TEAMS_PAGE ? focus : ranked[focus].team_id;
      page = MD_CLUB_PROFILE;club_child=0;
      focus = 0;
    }
    goto done;
  }
  if(page==MD_CLUB_PROFILE) {
    if((key&UP) && focus)focus--;
    else if((key&DOWN) && focus<5)focus++;
    else if(key&A) {
      static const MdPage dest[]={MD_TEAM_INFO,MD_TABLE,MD_TEAM_HISTORY,MD_OVERALL,MD_CLUB_PLAN,MD_REWARDS};
      club_menu_focus=focus;club_child=1;page=dest[focus];focus=0;history_week=0;schedule_day=0;
      if(page==MD_CLUB_PLAN && !team_choice){page=MD_CLUB_PROFILE;focus=club_menu_focus;club_child=0;open_plan();}
    }
    goto done;
  }
  if(page==MD_REWARDS) {
    if((key&UP) && focus)focus--;
    else if((key&DOWN) && focus<4)focus++;
    goto done;
  }
  if(page==MD_CLUB_PLAN)goto done;
  if (page == MD_TEAM_INFO) {
    if ((key & X) && !team_choice) {
      page = MD_COLLECTION_PAGE;
      focus = 0;
      goto done;
    }
    if ((key & UP) && focus)
      focus--;
    else if ((key & DOWN) && focus + 1 < profile.counts[team_choice])
      focus++;
    else if (key & A) {
      player_choice = focus;
      page = MD_PLAYER_INFO;
      focus = 0;
    }
    goto done;
  }
  if (page == MD_COLLECTION_PAGE) {
    if ((key & UP) && focus)
      focus--;
    else if ((key & DOWN) && focus + 1 < profile.collection_count)
      focus++;
    else if (key & A) {
      uint32_t i = 0;
      while (i < profile.counts[0] && profile.roster[0][i] != profile.collection[focus])
        i++;
      if (i < profile.counts[0])
        snprintf(notice, sizeof(notice), "THIS PLAYER IS ALREADY REGISTERED");
      else if (shop_locked())
        snprintf(notice, sizeof(notice), "SQUAD LOCKED DURING MATCH DAY");
      else {
        collection_choice = focus;
        page = MD_REPLACE_PLAYER;
        focus = 0;
      }
    }
    goto done;
  }
  if (page == MD_REPLACE_PLAYER) {
    if ((key & UP) && focus)
      focus--;
    else if ((key & DOWN) && focus + 12 < profile.counts[0])
      focus++;
    else if ((key & A) && !shop_locked()) {
      MdProfile before = profile;
      profile.roster[0][11 + focus] = profile.collection[collection_choice];
      profile.has_current_plan = 0;
      memset(&profile.current_plan, 0, sizeof(profile.current_plan));
      if (profile_save()) {
        profile_cache();
        page = MD_TEAM_INFO;
        focus = 0;
        snprintf(notice, sizeof(notice), "PLAYER REGISTERED - UPDATE YOUR GAME PLAN");
      } else {
        profile = before;
        snprintf(notice, sizeof(notice), "SQUAD NOT SAVED - PLEASE RETRY");
      }
    }
    goto done;
  }
  if (page == MD_PLAYER_INFO)
    goto done;
  if (page == MD_NEWS) {
    MdRow items[MD_NEWS_MAX];uint32_t count=news_rows(items);
    if ((key & UP) && focus)focus--;
    else if ((key & DOWN) && focus+1<count)focus++;
    else if ((key & A) && focus<count) {
      const MdRow *item=&items[focus];
      if(item->identity) {
        history_week=0;
        watch_return=MD_NEWS;watch_return_focus=focus;
        fixture_choice=item->identity-1;replay=1;replay_ms=paused=0;page=MD_WATCH;timeline_serial++;
      } else {
        team_choice=item->team_id;team_return=MD_NEWS;team_return_focus=focus;page=MD_CLUB_PROFILE;club_child=0;focus=0;
      }
    }
    goto done;
  }
  if (page == MD_RULES) {
    if ((key & UP) && focus)
      focus--;
    else if ((key & DOWN) && focus < 6)
      focus++;
    goto done;
  }
  if (page == MD_SHOP) {
    if ((key & LEFT) && focus)
      focus--;
    else if ((key & RIGHT) && focus < 2)
      focus++;
    else if (key & A) {
      pack_choice = focus;
      page = MD_PACK;
      focus = 0;
    }
    goto done;
  }
  if (page == MD_PACK) {
    if (key & A)
      pack_open();
    goto done;
  }
  if(page==MD_CHAMPIONS) {
    uint32_t count=champion_total();
    if((key&UP) && focus)focus--;
    else if((key&DOWN) && focus+1u<count)focus++;
    else if((key&A) && focus<count) {
      uint32_t week=count-focus;
      if(champion_read(week,&champion)){champion_choice=week;champion_return_focus=focus;page=MD_CHAMPION;focus=0;}
      else snprintf(notice,sizeof(notice),"This league's champion archive is unavailable. Existing records are preserved.");
    }
    goto done;
  }
  if(page==MD_CHAMPION)goto done;
  if(page==MD_PACK_BUY) {
    if(key&(LEFT|RIGHT|UP|DOWN))focus^=1u;
    if(key&A){if(focus){page=MD_PACK;focus=0;}else pack_buy();}
    goto done;
  }
  if (page == MD_PACK_OPENING) {
    if ((key & A) && epoch_now - pack_opened_at >= MD_PACK_OPEN_MS) {
      page = MD_PACK_SELECT;
      focus = 0;
    }
    goto done;
  }
  if (page == MD_PACK_SELECT) {
    uint32_t count = pack_pools[pack_choice];
    if (key & LEFT) {
      if (focus < count && focus % 4)
        focus--;
    } else if (key & RIGHT) {
      if (focus < count && focus % 4 < 3 && focus + 1 < count)
        focus++;
    } else if (key & UP) {
      if (focus == count)
        focus = count > 4 ? 4 : 0;
      else if (focus >= 4)
        focus -= 4;
    } else if (key & DOWN) {
      if (focus < count) {
        if (focus + 4 < count) focus += 4;
        else if(focus<4 && count>4)focus=count-1;
        else if (selected_count() == pack_draws[pack_choice]) focus = count;
      }
    } else if (key & A) {
      const uint32_t previous=pack_selected;
      if (focus == count)
        pack_confirm();
      else if (pack_selected & (1u << focus))
        pack_selected &= ~(1u << focus);
      else if (selected_count() < pack_draws[pack_choice])
        pack_selected |= 1u << focus;
      else
        snprintf(notice, sizeof(notice), "DESELECT A PLAYER TO CHANGE YOUR CHOICE");
      if(page==MD_PACK_SELECT && previous!=pack_selected)pack_save_selection(previous);
    }
    goto done;
  }
  if (page == MD_PACK_RESULT) {
    if (key & A) {
      page = MD_SHOP;
      focus = pack_choice;
    }
    goto done;
  }
  if (page == MD_CALENDAR) {
    if ((key & (LEFT | UP)) && focus)
      focus--;
    else if ((key & (RIGHT | DOWN)) && focus < 6)
      focus++;
    calendar_day = focus + 1;
    if(md.day_ms==MD_CALENDAR_DAY_MS) {
      if(key&A) {
        if(calendar_day==1 || calendar_day==4)open_plan();
        else if(calendar_day==7){page=MD_TABLE;focus=0;club_child=0;}
        else {
          uint32_t matches=0;
          for(uint32_t i=0;i<MD_FIXTURES;i++)if(fixture_day(&md,&md.fixtures[i])==calendar_day)matches++;
          if(matches){schedule_day=calendar_day;page=MD_SCHEDULE;history_week=0;focus=0;}
          else snprintf(notice,sizeof(notice),"Open Match Centre for earlier seasons, or join the next league for its fixtures.");
        }
      }
      goto done;
    }
    if ((key & A) && calendar_day >= 4 && calendar_day <= 6) {
      schedule_day = calendar_day;
      page = MD_SCHEDULE;
      focus = 0;
    }
    if ((key & A) && calendar_day <= 3) {
      if (calendar_day == 3) {
        open_plan();
        goto done;
      }
      if (calendar_day == 2) {
        page = MD_SHOP;
        focus = 0;
        packs_build();
      } else {
        page = MD_TEAM_INFO;
        team_choice = 0;
        team_return = MD_CALENDAR;
        team_return_focus = 0;
        focus = 0;
      }
    } else if ((key & A) && calendar_day == 7) {
      page = MD_TABLE;
      focus = 0;
    }
    goto done;
  }
  if (page == MD_SCHEDULE || page==MD_TEAM_HISTORY) {
    uint32_t indices[MD_FIXTURES], count = schedule_indices(indices);
    if(key&(L|R)) {
      schedule_group=(schedule_group+((key&R) ? 1u : 2u))%3u;schedule_group_auto=0;focus=0;
    } else if(key & (X|Y)) {
      uint32_t wanted=history_week;
      if(key & X)wanted=history_week ? history_week-1u : md.week_id-1u;
      else wanted=history_week && history_week+1u<md.week_id ? history_week+1u : 0;
      if(!history_select(wanted))snprintf(notice,sizeof(notice),"This week's replay archive is unavailable.");
      schedule_group_auto=1;
    } else if ((key & LEFT) && focus % 2)
      focus--;
    else if ((key & RIGHT) && !(focus % 2) && focus + 1 < count)
      focus++;
    else if ((key & UP) && focus >= 2)
      focus -= 2;
    else if ((key & DOWN) && focus + 2 < count)
      focus += 2;
    else if ((key & DOWN) && focus + 1 < count)
      focus++;
    else if ((key & A) && focus < count) {
      watch_return=page;watch_return_focus=focus;
      fixture_choice = indices[focus];
      replay = manager_dummy_phase(watch_fixture(), broadcast_now()) == 2;
      replay_ms = 0;
      paused = 0;
      page = MD_WATCH;
      timeline_serial++;
    }
    goto done;
  }
  if (page == MD_WATCH) {
    if(key&Y){touchline_open=1;touchline_focus=0;goto done;}
    const uint32_t duration=manager_dummy_duration(watch_fixture());
    const uint32_t finished = manager_dummy_phase(watch_fixture(), broadcast_now()) == 2;
    if (finished && (key & A)) {
      if (!replay) {
        replay = 1;
        replay_ms = 0;
        paused = 0;
        timeline_serial++;
      } else
        paused = !paused;
    }
    if (finished && replay) {
      if (key & LEFT) {
        replay_ms = replay_ms < 15000 ? 0 : replay_ms - 15000;
        timeline_serial++;
      }
      if (key & RIGHT) {
        replay_ms = replay_ms > duration - 15000 ? duration : replay_ms + 15000;
        timeline_serial++;
      }
      if (key & X) {
        replay_ms = 0;
        timeline_serial++;
      }
    }
  }
done:
  if(previous_page!=page && previous_page!=MD_WATCH && (page==MD_SCHEDULE || page==MD_TEAM_HISTORY)) {
    schedule_group_auto=1;focus=0;
  }
  if(page==MD_SHOP && !notice[0])pack_resume();
  pthread_mutex_unlock(&md_mutex);
}
static void copy(char *to, size_t cap, const char *text) { snprintf(to, cap, "%s", text); }
static void row(MdView *v, uint32_t i, const char *label, const char *detail, const char *value,
                uint32_t b) {
  MdRow *r = &v->rows[i];
  copy(r->label, sizeof(r->label), label);
  copy(r->detail, sizeof(r->detail), detail);
  copy(r->value, sizeof(r->value), value);
  r->badge = b;
  r->enabled = !blocked;
  r->selected = v->focus == v->first + i;
}
static void helper(MdView *v, const char *key, const char *label) {
  if (v->helper_count < 6) {
    v->helper_key[v->helper_count] = key;
    v->helper_label[v->helper_count++] = label;
  }
}
static const char *event_name(uint32_t kind) {
  static const char *const names[] = {"PASSING MOVE", "SHOT WIDE", "GOAL",   "FOUL", "YELLOW CARD",
                                      "SUBSTITUTION", "OFFSIDE",   "CORNER", "SAVE", "HALF TIME"};
  return kind <= MD_HALF ? names[kind] : "KICKOFF";
}
#include "manager_league_review_view.inc"
#include "manager_league_club_view.inc"
#include "manager_league_calendar_view.inc"
void manager_dummy_view(MdView *v) {
  pthread_mutex_lock(&md_mutex);
  memset(v, 0, sizeof(*v));
  v->page = page;
  v->pin_open=pin_active;v->pin_cursor=pin_cursor;v->pin_length=pin_length;
  v->pin_confirming=pin_confirming;v->pin_creating=pin_creating;
  v->focus = focus;
  v->balance = profile_ready ? profile.balance : md.balance;
  v->joined = md.joined;
  v->now_ms = now();
  v->navigation_serial = navigation_serial;
  v->slide_direction = slide_direction;
  v->timeline_serial = timeline_serial;
  v->tab = hub_section;
  v->week_id=md.week_id;v->history_week=history_week;v->archive_count=md.week_id ? md.week_id-1u : 0;
  v->roster_size = profile_ready ? profile.counts[0] : 0;
  v->shop_locked = shop_locked();
  v->week = manager_dummy_week(&md, now());
  static const char *const phase_names[] = {"PRE-LEAGUE", "MATCH DAY", "RESULT"};
  copy(v->phase_label, sizeof(v->phase_label), phase_names[v->week.state]);
  if(md.day_ms==MD_CALENDAR_DAY_MS && calendar_weekday(now())==7)
    copy(v->phase_label,sizeof(v->phase_label),"SUNDAY OVERVIEW");
  v->event_kind = UINT32_MAX;
  v->event_age_ms = UINT32_MAX;
  copy(v->title, sizeof(v->title), "ONLINE LEAGUE");
  copy(v->subtitle, sizeof(v->subtitle), "YOUR CLUB. YOUR LEAGUE.");
  copy(v->name, sizeof(v->name), md.name[0] ? md.name : "YOUR CLUB");
  v->placeholder = !md.club;
  copy(v->user_id, sizeof(v->user_id), profile.user_id);
  v->account_field = focus;
  copy(v->club, sizeof(v->club), exhibition_team_catalog_name(md.club));
  if(page!=MD_WATCH)copy(v->status, sizeof(v->status), notice);
  v->badge = badge(0);
  club_summary(v);
  v->tutorial = tutorial;
  helper(v, "B", "BACK");
  if (page == MD_REGISTER) {
    copy(v->headline, sizeof(v->headline), "YOUR CLUB. YOUR LEAGUE.");
    copy(v->summary, sizeof(v->summary),
         "Choose a club. Create your manager profile. Join the league.");
    v->count=2;
    row(v,0,"LOGIN","Continue with your club","",0);
    row(v,1,"REGISTER","Create a manager profile and choose a club","",0);
    helper(v,"A","SELECT");
  } else if (page == MD_LEAGUES) {
    copy(v->headline, sizeof(v->headline), "SELECT LEAGUE");
    v->total = EXHIBITION_TEAM_CATEGORY_COUNT;
    v->first = focus / 5 * 5;
    v->count = v->total - v->first;
    if (v->count > 5)
      v->count = 5;
    for (uint32_t i = 0; i < v->count; i++) {
      const ExhibitionTeamCategory *c = &exhibition_team_categories[v->first + i];
      row(v, i, c->label, "Choose a club identity", "", c->badge_slot);
    }
    helper(v, "A", "SELECT");
  } else if (page == MD_CLUB) {
    const ExhibitionTeamCategory *c = &exhibition_team_categories[category];
    copy(v->headline, sizeof(v->headline), "SELECT CLUB");
    copy(v->caption, sizeof(v->caption), c->label);
    if (club_choice < c->team_count) {
      v->badge = exhibition_team_catalog_badge(c->teams[club_choice]);
      copy(v->club, sizeof(v->club), exhibition_team_catalog_name(c->teams[club_choice]));
    }
    v->focus = club_choice;
    v->total = c->team_count;
    v->first = club_choice / 5 * 5;
    v->count = v->total - v->first;
    if (v->count > 5)
      v->count = 5;
    for (uint32_t i = 0; i < v->count; i++)
      row(v, i, exhibition_team_catalog_name(c->teams[v->first + i]), "", "",
          exhibition_team_catalog_badge(c->teams[v->first + i]));
    helper(v, "A", "SELECT");
  } else if (page == MD_NAME) {
    copy(v->headline, sizeof(v->headline), "CREATE YOUR PROFILE");
    copy(v->caption, sizeof(v->caption), "YOUR MANAGER ACCOUNT");
    v->count = 4;
    row(v, 0, "TEAM NAME", "Your club name in the league", md.name[0] ? md.name : "ENTER NAME", 0);
    row(v, 1, "USER ID", "3-24 letters, numbers, dot or underscore",
        profile.user_id[0] ? profile.user_id : "ENTER USER ID", 0);
    row(v, 2, "4-DIGIT PIN", "Your quick login code", pin_confirmed ? "PIN SET" : "CREATE PIN",
        0);
    row(v, 3, "CREATE CLUB", "Join the league with your own team", "CONTINUE", 0);
    helper(v, "A", focus == 3 ? "CONTINUE" : "EDIT");
  } else if(page==MD_LOGIN || page==MD_SECURE || page==MD_MIGRATE) {
    const int secure=page==MD_SECURE,migrate=page==MD_MIGRATE;
    v->count=secure ? 2 : 3;
    copy(v->headline,sizeof(v->headline),secure ? "SET YOUR PIN" : migrate ? "SWITCH TO A PIN" : "WELCOME BACK");
    copy(v->caption,sizeof(v->caption),secure ? "Create and confirm a four-digit login code" : migrate ? "Verify your previous password once. Future logins use a PIN." : "LOG IN WITH YOUR USER ID AND PIN");
    if(!secure) {
      row(v,0,"USER ID","Your registered manager ID",login_id[0] ? login_id : "ENTER USER ID",0);
      row(v,1,migrate ? "PREVIOUS PASSWORD" : "4-DIGIT PIN",migrate ? "One-time verification" : "",migrate ? (legacy_password[0] ? "********" : "ENTER PASSWORD") : (pin_confirmed ? "****" : "ENTER PIN"),0);
    } else {
      row(v,0,"4-DIGIT PIN","Create your code, then enter it again",pin_confirmed ? "PIN SET" : "CREATE PIN",0);
    }
    row(v,secure ? 1 : 2,secure ? "SAVE & CONTINUE" : migrate ? "VERIFY & SET PIN" : "LOGIN","","",0);
    helper(v,"A",focus==(secure ? 1u : 2u) ? "CONTINUE" : "EDIT");
  } else if (page == MD_DASHBOARD || page==MD_LOGOUT || page==MD_NEXT_WEEK) {
    static const char *const labels[3][5] = {
        {"NEXT BROADCAST", "CLUB FEED", "WEEKLY SCHEDULE", "LEAGUE STANDINGS", "CLUB PROFILE"},
        {"MY SQUAD", "GAME PLAN", "PLAYER SHOP", "MY SQUAD", "OTHER TEAMS"},
        {"LEAGUE STANDINGS", "LEAGUE CHAMPIONS", "MATCH CENTRE", "OVERALL RANKING", "LEAGUE GUIDE"}};
    static const char *const details[3][5] = {
        {"Watch the scheduled broadcast", "News, results and club stories",
         "All fixtures and full replays", "This league's title race",
         "Your squad and player profiles"},
        {"Players, portraits and squad roles", "Open your team Game Plan",
         "Build your squad with NX Cash", "Registered players", "Meet your six opponents"},
        {"League points from this season", "Previous champions, always remembered",
         "Live, scheduled and completed games", "Resets every two real weeks",
         "Calendar and competition rules"}};
    static const char *const news_titles[] = {"PREPARE FOR THE LEAGUE AHEAD",
                                              "THE TITLE RACE", "LEAGUE SEASON COMPLETE"};
    static const char *const news_details[] = {
        "Build your squad, shop and prepare your Game Plan before Match Day.",
        "Follow every scheduled game. The player shop is closed during competition.",
        "The final standings and every match replay are available."};
    copy(v->headline, sizeof(v->headline), news_titles[v->week.state]);
    copy(v->summary, sizeof(v->summary), news_details[v->week.state]);
    snprintf(v->caption, sizeof(v->caption), "%s - DAY %u OF 7 - WEEK %02u", v->phase_label,
             v->week.day,v->week_id);
    if(md.day_ms==MD_CALENDAR_DAY_MS)snprintf(v->caption,sizeof(v->caption),"%s - LEAGUE %02u - TWO LEAGUES PER WEEK",v->phase_label,v->week_id);
    v->count = 5;
    for (uint32_t i = 0; i < 5; i++)
      row(v, i, labels[hub_section][i], details[hub_section][i], "OPEN", 0);
    if (!hub_section && v->week.state == MD_PRE_LEAGUE)
      row(v, 0, "PREPARE YOUR CLUB", "Shop, squad and Game Plan before the first broadcast.",
          "7 CLUBS REGISTERED", 0);
    else if (!hub_section && v->week.state == MD_RESULT)
      row(v, 0, "SEASON RESULTS", "The final league table is ready.", "VIEW FINAL STANDINGS", 0);
    if (hub_section == 1 && v->shop_locked)
      row(v, 2, "PLAYER SHOP - CLOSED", "Opens on Result day. Existing offers can be inspected.",
          "CLOSED", 0);
    helper(v, "L", "PREV PAGE");
    helper(v, "R", "NEXT PAGE");
    helper(v, "A", "OPEN");
    helper(v,"X","LOGOUT");
    if(v->week.state==MD_RESULT)helper(v,"Y","NEXT LEAGUE");
    else if(development_clock_enabled())helper(v,"Y","DEMO TIME");
    MdRow ranked[7];
    table_rows(ranked);
    for (uint32_t i = 0; i < 7; i++)
      if (!ranked[i].team_id)
        v->rank = i + 1;
    if (v->week.state == MD_RESULT) {
      snprintf(v->summary, sizeof(v->summary),
               "Champion: %.48s. All 21 matches have finished.",
               team_name(ranked[0].team_id));
      if (!hub_section)
        snprintf(v->rows[0].detail, sizeof(v->rows[0].detail), "Champion: %.54s",
                 team_name(ranked[0].team_id));
    }
    if (hub_section == 2)
      overall_rows(ranked);
    memcpy(v->table_preview, ranked, sizeof(v->table_preview));
    for (uint32_t i = 0; i < MD_FIXTURES; i++)
      if (manager_dummy_phase(&md.fixtures[i], now()) == 2) {
        const MdFixture *f = &md.fixtures[i];
        uint32_t score[2];
        manager_dummy_score(f, MD_DURATION, score);
        v->last_complete = 1;
        v->last_hg = score[0];
        v->last_ag = score[1];
        v->last_home_badge = badge(f->home);
        v->last_away_badge = badge(f->away);
        copy(v->last_home, sizeof(v->last_home), team_name(f->home));
        copy(v->last_away, sizeof(v->last_away), team_name(f->away));
      }
    uint32_t next = 0;
    while (next + 1 < MD_FIXTURES && manager_dummy_phase(&md.fixtures[next], now()) == 2)
      next++;
    const MdFixture *broadcast = &md.fixtures[next];
    copy(v->home, sizeof(v->home), team_name(broadcast->home));
    copy(v->away, sizeof(v->away), team_name(broadcast->away));
    v->home_badge = badge(broadcast->home);
    v->away_badge = badge(broadcast->away);
    const uint32_t preview_first = v->week.state == MD_RESULT ? MD_FIXTURES - 3u : next;
    for (uint32_t i = 0; i < 3; i++) {
      const uint32_t index = preview_first + i;
      const MdFixture *f = &md.fixtures[index < MD_FIXTURES ? index : MD_FIXTURES - 1];
      MdRow *r = &v->fixture_preview[i];
      uint32_t p = manager_dummy_phase(f, now());
      r->phase=p;r->badge=badge(f->home);r->away_badge=badge(f->away);
      snprintf(r->label, sizeof(r->label), "%.20s Vs %.20s", team_name(f->home),
               team_name(f->away));
      uint32_t g[2];
      manager_dummy_score(f, manager_dummy_elapsed(f, now()), g);
      if (p)
        snprintf(r->value, sizeof(r->value), "%s %u-%u", p == 1 ? "LIVE" : "FT", g[0], g[1]);
      else
        snprintf(r->value, sizeof(r->value), "UPCOMING");
    }
  } else if (page == MD_TABLE) {
    copy(v->headline, sizeof(v->headline),
         v->week.state == MD_RESULT ? "FINAL LEAGUE STANDINGS" : "LEAGUE STANDINGS");
    v->total = 7;
    v->first = focus / ML_TABLE_PAGE_ROWS * ML_TABLE_PAGE_ROWS;
    v->count = 7 - v->first;
    if (v->count > ML_TABLE_PAGE_ROWS)
      v->count = ML_TABLE_PAGE_ROWS;
    MdRow all[7];
    table_rows(all);
    memcpy(v->rows, all + v->first, v->count * sizeof(MdRow));
    helper(v, "A", "TEAM INFO");
  } else if (page == MD_TEAMS_PAGE) {
    copy(v->headline, sizeof(v->headline), "LEAGUE CLUBS");
    v->total = 7;
    v->first = focus / 5 * 5;
    v->count = 7 - v->first;
    if (v->count > 5)
      v->count = 5;
    for (uint32_t i = 0; i < v->count; i++) {
      uint32_t t = v->first + i;
      row(v, i, team_name(t), t ? "LEAGUE CLUB" : "YOUR CLUB", "PROFILE", badge(t));
    }
    helper(v, "A", "TEAM INFO");
  } else if(page==MD_CLUB_PROFILE) {
    club_profile_view(v);
  } else if(page==MD_CLUB_PLAN) {
    club_plan_view(v);
  } else if(page==MD_REWARDS) {
    club_rewards_view(v);
  } else if (page == MD_TEAM_INFO) {
    copy(v->headline, sizeof(v->headline), team_name(team_choice));
    copy(v->caption, sizeof(v->caption), "REGISTERED SQUAD");
    v->badge = badge(team_choice);
    v->total = profile_ready ? profile.counts[team_choice] : 0;
    v->first = focus / 5 * 5;
    v->count = v->total - v->first;
    if (v->count > 5)
      v->count = 5;
    for (uint32_t i = 0; i < v->count; i++) {
      const MlCatalogPlayer *p = squad[team_choice][v->first + i];
      if (!p)
        continue;
      char rating[24], detail[64];
      snprintf(rating, sizeof(rating), "%u", p->overall);
      static const char *const roles[] = {"GK",  "CB",  "LB",  "RB",  "DMF", "CMF", "LMF",
                                          "RMF", "AMF", "LWF", "RWF", "SS",  "CF"};
      snprintf(detail, sizeof(detail), "%s", p->position < 13 ? roles[p->position] : "PLAYER");
      row(v, i, p->name, detail, rating, 0);
      v->rows[i].portrait = p->portrait_id;
      v->rows[i].identity = p->identity;
      v->rows[i].native_id = p->native_id;
      v->rows[i].rating = p->overall;
      v->rows[i].role = p->position;
    }
    helper(v, "A", "PLAYER PROFILE");
    if (!team_choice)
      helper(v, "X", "COLLECTION");
  } else if (page == MD_COLLECTION_PAGE || page == MD_REPLACE_PLAYER) {
    copy(v->headline, sizeof(v->headline),
         page == MD_COLLECTION_PAGE ? "PLAYER COLLECTION" : "REPLACE A RESERVE");
    copy(v->caption, sizeof(v->caption),
         page == MD_COLLECTION_PAGE
             ? "All owned players. Register a player before opening Game Plan."
             : "The replaced player stays in your collection.");
    v->total = page == MD_COLLECTION_PAGE ? profile.collection_count : profile.counts[0] - 11;
    v->first = focus / 5 * 5;
    v->count = v->total - v->first;
    if (v->count > 5)
      v->count = 5;
    for (uint32_t i = 0; i < v->count; i++) {
      uint32_t n = v->first + i;
      const MlCatalogPlayer *p = page == MD_COLLECTION_PAGE ? collection[n] : squad[0][n + 11];
      if (!p)
        continue;
      char text[32];
      uint32_t j = 0;
      while (j < profile.counts[0] && profile.roster[0][j] != p->identity)
        j++;
      snprintf(text, sizeof(text), "%s", j < profile.counts[0] ? "REGISTERED" : "COLLECTION");
      row(v, i, p->name, text, "", 0);
      v->rows[i].portrait = p->portrait_id;
      v->rows[i].identity = p->identity;
      v->rows[i].rating = p->overall;
      v->rows[i].role = p->position;
    }
    helper(v, "A", page == MD_COLLECTION_PAGE ? "REGISTER" : "REPLACE");
  } else if (page == MD_PLAYER_INFO) {
    const MlCatalogPlayer *p = profile_ready ? squad[team_choice][player_choice] : NULL;
    if (p) {
      copy(v->headline, sizeof(v->headline), p->name);
      v->portrait = p->portrait_id;
      v->badge = badge(team_choice);
      copy(v->caption, sizeof(v->caption), team_name(team_choice));
      v->count = 3;
      char text[64];
      snprintf(text, sizeof(text), "%u", p->overall);
      row(v, 0, p->name, "Catalog simulation strength", text, 0);
      v->rows[0].portrait = p->portrait_id;
      v->rows[0].rating = p->overall;
      v->rows[0].role = p->position;
      static const char *const roles[] = {"GK",  "CB",  "LB",  "RB",  "DMF", "CMF", "LMF",
                                          "RMF", "AMF", "LWF", "RWF", "SS",  "CF"};
      row(v, 1, "POSITION", "Natural role", p->position < 13 ? roles[p->position] : "PLAYER", 0);
      row(v, 2, "CLUB", "Registered team", team_name(team_choice), badge(team_choice));
    }
  } else if (page == MD_SHOP) {
    copy(v->headline, sizeof(v->headline), "CLUB PACKS");
    snprintf(v->caption, sizeof(v->caption), "%s",
             shop_locked() ? "SHOP CLOSED" : "AVAILABLE PACKS");
    v->count = 3;
    static const char *const tiers[] = {"LITE", "MEDIUM", "JUMBO"};
    for (uint32_t i = 0; i < 3; i++) {
      char detail[96], value[40];
      snprintf(detail, sizeof(detail), "%u PLAYERS FROM A POOL OF %u", pack_draws[i],
               pack_pools[i]);
      snprintf(value, sizeof(value), profile.receipts & (1u << i) ? "OPENED" : "%u NX CASH",
               pack_prices[i]);
      row(v, i, tiers[i], detail, value, exhibition_team_catalog_badge(pack_clubs[i]));
      v->rows[i].team_id = pack_clubs[i];
    }
    helper(v, "LEFT", "SELECT");
    helper(v, "A", "VIEW PACK");
  } else if (page == MD_PACK || page == MD_PACK_BUY || page == MD_PACK_RESULT || page == MD_PACK_OPENING ||
             page == MD_PACK_SELECT) {
    const uint32_t k = pack_choice;
    v->pack_draw = pack_draws[k];
    v->pack_pool = pack_pools[k];
    v->pack_price = pack_prices[k];
    v->badge = exhibition_team_catalog_badge(pack_clubs[k]);
    copy(v->headline, sizeof(v->headline), exhibition_team_catalog_name(pack_clubs[k]));
    copy(v->caption, sizeof(v->caption),
         page == MD_PACK_RESULT ? "YOUR CONFIRMED PLAYERS" : "CLUB SELECTION PACK");
    v->pack_selected = pack_selected;
    v->pack_selection_count = selected_count();
    v->pack_opening_ms = epoch_now >= pack_opened_at ? (uint32_t)(epoch_now - pack_opened_at) : 0;
    /* The sealed offer contains no player rows. After Open, the native owner
     * can prefetch portraits during the foil animation, before their reveal. */
    v->pack_count = page == MD_PACK_RESULT ? pack_draws[k]
                   : page == MD_PACK_SELECT || page == MD_PACK_OPENING
                         ? pack_pools[k] : 0;
    for (uint32_t i = 0; i < v->pack_count; i++) {
      const MlCatalogPlayer *p = pack_pool[k][i];
      if (page == MD_PACK_RESULT) {
        p = NULL;
        for (uint32_t j = 0; j < pack_pools[k]; j++)
          if (pack_pool[k][j] && pack_pool[k][j]->identity == profile.receipt_players[k][i])
            p = pack_pool[k][j];
      }
      if (!p)
        continue;
      MdRow *r = &v->pack_players[i];
      copy(r->label, sizeof(r->label), p->name);
      r->portrait = p->portrait_id;
      r->rating = p->overall;
      r->identity = p->identity;
      r->role = p->position;
    }
    helper(v, "A",
           page == MD_PACK           ? profile.receipts & (1u << k) ? "VIEW RECEIPT" : "OPEN PACK"
           : page == MD_PACK_SELECT  ? focus == pack_pools[k] ? "CONFIRM" : "SELECT"
           : page == MD_PACK_OPENING ? "OPENING"
                                     : "CONTINUE");
    if(pack_pending && (page==MD_PACK_SELECT || page==MD_PACK_OPENING)) {
      v->helper_key[0]=v->helper_key[1];v->helper_label[0]=v->helper_label[1];v->helper_count=1;
    }
  } else if (page == MD_NEWS) {
    copy(v->headline, sizeof(v->headline), "LEAGUE NEWS");
    copy(v->caption, sizeof(v->caption), "Results, transfers and stories from every club");
    MdRow items[MD_NEWS_MAX];v->total=news_rows(items);v->first=focus/5*5;
    v->count=v->total-v->first;if(v->count>5)v->count=5;
    memcpy(v->rows,items+v->first,v->count*sizeof(*items));
    helper(v,"A","VIEW STORY");
  } else if (page == MD_RULES) {
    copy(v->headline, sizeof(v->headline), "LEAGUE GUIDE");
    v->total = 7;
    v->first = focus / 5 * 5;
    v->count = 7 - v->first;
    if (v->count > 5)
      v->count = 5;
    static const char *const labels[] = {"TWO LEAGUES PER WEEK", "SEVEN CLUBS",     "LEAGUE POINTS",
                                         "NX CASH", "OVERALL RANKING", "LIVE AND REPLAY",
                                         "YOUR ACCOUNT"};
    static const char *const details[] = {
        "Prep Mon/Thu. Matches Tue-Wed/Fri-Sat. Sunday overview. Times WIB.",
        "Six opponents. One round robin. 21 matches.",
        "Win 3, draw 1, lose 0. Then goal difference and goals scored.",
        "5,000 starting NX Cash. Every league entry adds 1,500. Shop outside Match Day.",
        "Overall Rank resets every two real weeks. League Champions remain in the honours list.",
        "Two five-minute halves. Join in progress or watch a replay.",
        "Log in with your User ID. Log out from the club hub."};
    for (uint32_t i = 0; i < v->count; i++)
      row(v, i, labels[v->first + i], details[v->first + i], "", 0);
  } else if (page == MD_OVERALL) {
    copy(v->headline, sizeof(v->headline), "OVERALL RANKING");
    ranking_view(v);
    v->total = 7;
    v->first = focus / 5 * 5;
    v->count = 7 - v->first;
    if (v->count > 5)
      v->count = 5;
    MdRow all[7];
    overall_rows(all);
    memcpy(v->rows, all + v->first, v->count * sizeof(MdRow));
    helper(v, "A", "TEAM INFO");
  } else if (page == MD_CALENDAR) {
    if(md.day_ms==MD_CALENDAR_DAY_MS)calendar_view(v);
    else {
    copy(v->headline, sizeof(v->headline), "WEEKLY SCHEDULE");
    copy(v->caption, sizeof(v->caption), "PREPARATION. MATCH DAY. RESULT.");
    v->total = 7;
    /* Keep the focused day visible in a three-tile viewport. Adjacent presses
     * scroll one day
     * at a time; the ends retain a full viewport. */
    v->first = focus ? focus - 1u : 0;
    if (v->first > v->total - MD_WEEK_VISIBLE)
      v->first = v->total - MD_WEEK_VISIBLE;
    v->count = MD_WEEK_VISIBLE;
    const uint64_t first = v->week.first_kickoff_ms;
    for (uint32_t i = 0; i < v->count; i++) {
      const uint32_t d = v->first + i + 1u;
      MdScheduleDay *tile = &v->schedule[i];
      const uint32_t day_ms=day_duration(&md);
      const uint64_t day_start = d <= 3   ? first - (4u - d) * (uint64_t)MD_PREPARATION_DAY_MS
                                 : d <= 6 ? first + (d - 4u) * (uint64_t)day_ms
                                          : v->week.result_ms;
      struct tm local, end;
      manager_local_time(day_start, &local);
      manager_local_time(day_start + (d<=3 ? MD_PREPARATION_DAY_MS : day_ms), &end);
      char label[64], detail[96] = {0}, date[32];
      strftime(date, sizeof(date), "%d %b %Y", &local);
      const char *kind = d <= 3 ? "PREPARATION" : d <= 6 ? "MATCH DAY" : "RESULT";
      snprintf(label, sizeof(label), "DAY %u - %s%s", d, kind, d == v->week.day ? " - TODAY" : "");
      snprintf(tile->period, sizeof(tile->period), "%02d:%02d - %02d:%02d", local.tm_hour,
               local.tm_min, end.tm_hour, end.tm_min);
      if (d <= 3)
        copy(detail, sizeof(detail),
             d == 1   ? "Meet your players and prepare your squad"
             : d == 2 ? "Explore club packs and register players"
                      : "Set your Game Plan before Match Day");
      else if (d == 7) {
        snprintf(tile->period, sizeof(tile->period), "%02d:%02d onwards", local.tm_hour,
                 local.tm_min);
        copy(detail, sizeof(detail), "Final standings and match replays");
      } else {
        for (uint32_t n = 0; n < MD_FIXTURES; n++) {
          const MdFixture *f = &md.fixtures[n];
          uint32_t day = f->round < 3 ? 4 : f->round < 5 ? 5 : 6;
          if (day == d && (f->home == 0 || f->away == 0) && tile->match_count < 3) {
            struct tm kickoff;
            manager_local_time(f->kickoff_ms, &kickoff);
            MdRow *match = &tile->matches[tile->match_count++];
            const uint32_t opponent = f->home ? f->home : f->away;
            snprintf(match->label, sizeof(match->label), "Vs %.60s", team_name(opponent));
            snprintf(match->value, sizeof(match->value), "%02d:%02d", kickoff.tm_hour,
                     kickoff.tm_min);
            copy(match->detail, sizeof(match->detail), f->home == 0 ? "HOME" : "AWAY");
            match->badge = badge(opponent);
            match->team_id = opponent;
            match->phase=manager_dummy_phase(f,now());
          }
        }
        snprintf(detail, sizeof(detail), "%u MATCHES", tile->match_count);
      }
      row(v, i, label, detail, date, 0);
    }
    helper(v, "LS", "SCROLL");
    helper(v, "A",
           focus >= 3 && focus <= 5 ? "VIEW MATCHES"
           : focus == 6             ? "STANDINGS"
                                    : "PREPARE");
    }
  } else if(page==MD_CHAMPIONS)champions_view(v);
  else if(page==MD_CHAMPION)champion_view(v);
  else if (page == MD_SCHEDULE || page==MD_TEAM_HISTORY) {
    copy(v->headline, sizeof(v->headline), "MATCH CENTRE");
    snprintf(v->caption,sizeof(v->caption),"LEAGUE %02u%s",history_week ? history_week : md.week_id,
             history_week ? " - ARCHIVED REPLAYS" : "");
    uint32_t indices[MD_FIXTURES];
    v->total = schedule_indices(indices);
    v->focus=focus;v->match_group=schedule_group;memcpy(v->match_groups,schedule_groups,sizeof(schedule_groups));
    v->first = focus / MD_MATCH_VISIBLE * MD_MATCH_VISIBLE;
    v->count = v->total - v->first;
    if (v->count > MD_MATCH_VISIBLE)
      v->count = MD_MATCH_VISIBLE;
    for (uint32_t i = 0; i < v->count; i++) {
      const MdFixture *f = &broadcast_save()->fixtures[indices[v->first + i]];
      char label[64], detail[96], text[40];
      snprintf(label, sizeof(label), "%.26s Vs %.26s", broadcast_team_name(f->home), broadcast_team_name(f->away));
      uint32_t phase = manager_dummy_phase(f, broadcast_now());
      uint32_t goals[2];
      manager_dummy_score(f, manager_dummy_elapsed(f, broadcast_now()), goals);
      struct tm local;
      if(broadcast_save()->day_ms==MD_CALENDAR_DAY_MS)calendar_time(f->kickoff_ms,&local);
      else manager_local_time(f->kickoff_ms, &local);
      char date[32];
      strftime(date, sizeof(date), "%d %b %Y", &local);
      snprintf(detail, sizeof(detail), "%s - %02d:%02d - ROUND %u - %s", date, local.tm_hour,
               local.tm_min, f->round + 1,
               phase == 0   ? "UPCOMING"
               : phase == 1 ? "LIVE"
                            : "REPLAY");
      if (!phase)
        copy(text, sizeof(text), "SCHEDULED");
      else
        snprintf(text, sizeof(text), "%u - %u", goals[0], goals[1]);
      row(v, i, label, detail, text, broadcast_badge(f->home));
      v->rows[i].away_badge = broadcast_badge(f->away);
      v->rows[i].phase = phase;
      v->rows[i].identity=indices[v->first+i]+1u;
    }
    helper(v, "A", "WATCH MATCH");
    helper(v,"L","PREV");helper(v,"R","NEXT");
    if(v->archive_count){helper(v,"X","PREV LEAGUE");helper(v,"Y","NEXT LEAGUE");}
  } else if (page == MD_WATCH) {
    const MdFixture *f = watch_fixture();
    v->phase = manager_dummy_phase(f, broadcast_now());
    v->fixture = fixture_choice;
    v->round = f->round + 1;
    v->home_badge = broadcast_badge(f->home);
    v->away_badge = broadcast_badge(f->away);
    v->watching_replay = replay;
    v->paused = paused;
    v->kickoff_ms = f->kickoff_ms;
    v->duration_ms=manager_dummy_duration(f);
    v->elapsed_ms = replay ? replay_ms : manager_dummy_elapsed(f, broadcast_now());
    const uint32_t game_seconds=manager_dummy_game_seconds(f,v->elapsed_ms);
    v->minute = game_seconds/60u;
    uint32_t goals[2];
    manager_dummy_score(f, v->elapsed_ms, goals);
    v->home_goals = goals[0];
    v->away_goals = goals[1];
    snprintf(v->score, sizeof(v->score), "%u - %u", goals[0], goals[1]);
    snprintf(v->clock, sizeof(v->clock), "%02u:%02u",game_seconds/60u,game_seconds%60u);
    copy(v->home, sizeof(v->home), broadcast_team_name(f->home));
    copy(v->away, sizeof(v->away), broadcast_team_name(f->away));
    copy(v->headline, sizeof(v->headline),
         replay          ? "MATCH REPLAY"
         : v->phase == 1 ? "LIVE SIMULATION"
         : v->phase == 0 ? "BROADCAST STARTS SOON"
                         : "FULL TIME");
    copy(v->caption, sizeof(v->caption), "MANAGER LEAGUE - MATCH BROADCAST");
    copy(v->summary, sizeof(v->summary),
         v->phase == 0 ? "The teams are getting ready for kickoff."
                       : "Kickoff. Both teams begin their title chase.");
    uint32_t active[2][11];
    for (uint32_t side = 0; side < 2; side++)
      for (uint32_t n = 0; n < 11; n++)
        active[side][n] = n + 1;
    for (uint32_t i = 0; i < manager_dummy_event_count(f); i++)
      if (f->events[i].at_ms <= v->elapsed_ms) {
        const MdEvent *e = &f->events[i];
        uint32_t side = e->side;
        v->event_serial = i + 1;
        v->event_at_ms = e->at_ms;
        v->event_kind = e->kind;
        v->event_age_ms = v->elapsed_ms - e->at_ms;
        v->event_side = side;
        v->event_player = e->player;
        v->event_other = e->other;
        uint32_t club = side ? f->away : f->home;
        const MlCatalogPlayer *player =
            profile_ready && e->player <= 18 ? ml_catalog_find_identity(broadcast_profile()->match_roster[club][e->player - 1]) : NULL;
        const MlCatalogPlayer *incoming =
            profile_ready && e->other && e->other <= 18 ? ml_catalog_find_identity(broadcast_profile()->match_roster[club][e->other - 1]) : NULL;
        if (player)
          copy(v->event_name, sizeof(v->event_name), player->name);
        if (incoming)
          copy(v->event_other_name, sizeof(v->event_other_name), incoming->name);
        if (e->kind == MD_GOAL || e->kind == MD_SHOT || e->kind == MD_SAVE)
          v->shots[side]++;
        if (e->kind == MD_GOAL || e->kind == MD_SAVE)
          v->on_target[side]++;
        if (e->kind == MD_FOUL || e->kind == MD_YELLOW)
          v->fouls[side]++;
        if (e->kind == MD_YELLOW)
          v->cards[side]++;
        if (e->kind == MD_CORNER)
          v->corners[side]++;
        if (e->kind == MD_SUB) {
          v->substitutions[side]++;
          for (uint32_t n = 0; n < 11; n++)
            if (active[side][n] == e->player)
              active[side][n] = e->other;
        }
        if (e->kind == MD_GOAL || e->kind == MD_YELLOW || e->kind == MD_SUB || e->kind == MD_HALF)
          v->timeline[v->timeline_count++] = (MdTimelineMark){e->at_ms, e->kind, e->side};
        snprintf(v->summary, sizeof(v->summary), "%02u' %s - %.48s", manager_dummy_game_seconds(f,e->at_ms)/60u,
                 event_name(e->kind), broadcast_team_name(side ? f->away : f->home));
        v->event_feed[2] = v->event_feed[1];
        v->event_feed[1] = v->event_feed[0];
        snprintf(v->event_feed[0].label, sizeof(v->event_feed[0].label), "%02u' %s",
                 manager_dummy_game_seconds(f,e->at_ms)/60u, event_name(e->kind));
        snprintf(v->event_feed[0].detail, sizeof(v->event_feed[0].detail), "%.30s - %.40s",
                 broadcast_team_name(club), player ? player->name : "PLAYER");
        if (e->kind == MD_SUB)
          snprintf(v->event_feed[0].detail, sizeof(v->event_feed[0].detail), "#%u OFF - #%u ON",
                   e->player, e->other);
      }
    manager_dummy_sample(f, v->elapsed_ms, v->dots);
    for (uint32_t i = 0; i < 5; i++) {
      MdDot sampled[23];
      manager_dummy_sample(f, v->elapsed_ms < (i + 1) * 130u ? 0u : v->elapsed_ms - (i + 1) * 130u,
                           sampled);
      v->ball_trail[i] = sampled[22];
    }
    if (v->phase == 2) {
      helper(v, "A", replay ? "PLAY-PAUSE" : "REPLAY");
      if (replay) {
        helper(v, "LEFT", "SEEK -15S");
        helper(v, ">", "SEEK +15S");
        helper(v, "X", "RESTART");
      }
    }
    helper(v,"Y","TOUCHLINE");touchline_view(v,f);
  }
  for (uint32_t i = 0; i < 3; i++)
    if (profile_ready && squad[0][i]) {
      const MlCatalogPlayer *p = squad[0][i];
      MdRow *r = &v->squad_preview[i];
      copy(r->label, sizeof(r->label), p->name);
      r->portrait = p->portrait_id;
      r->rating = p->overall;
      snprintf(r->value, sizeof(r->value), "%u", p->overall);
    }
  if (tutorial) {
    static const char *const titles[] = {"WELCOME, MANAGER", "YOUR FIRST LEAGUE",
                                         "BUILD YOUR SQUAD"};
    static const char *const bodies[] = {
        "Start with 5,000 NX Cash. Each league entry adds 1,500, including your first league. Spend it in the player shop.",
        "Prepare Monday and Thursday. Play Tuesday-Wednesday and Friday-Saturday. Sunday is your overview day. Every match has a broadcast and replay.",
        "Open Squad for your players and Game Plan. Open club packs in the shop, choose your "
        "players, then Confirm to add them to your collection."};
    v->modal.open = 1;
    v->modal.information = 1;
    v->helper_count=0;helper(v,"A",tutorial==3 ? "LET'S BEGIN" : "CONTINUE");
    copy(v->modal.title, sizeof(v->modal.title), titles[tutorial - 1]);
    copy(v->modal.body, sizeof(v->modal.body), bodies[tutorial - 1]);
    copy(v->modal.accept, sizeof(v->modal.accept), tutorial == 3 ? "LET'S BEGIN" : "CONTINUE");
    copy(v->modal.error,sizeof(v->modal.error),notice);
  }
  if(pin_active) {
    v->helper_count=0;helper(v,"B","CANCEL");helper(v,"X","DELETE");helper(v,"A","SELECT");
  }
  if(page==MD_LOGOUT || page==MD_NEXT_WEEK) {
    v->modal.open=1;v->modal.selected=focus;v->modal.destructive=page==MD_LOGOUT;
    copy(v->modal.title,sizeof(v->modal.title),page==MD_LOGOUT ? "LOG OUT OF YOUR CLUB?" : "JOIN THE NEXT LEAGUE?");
    copy(v->modal.body,sizeof(v->modal.body),page==MD_LOGOUT ? "Your club, players and progress will stay saved on this device." : "This week's results and replays will be archived. Keep your club and players for the next league.");
    copy(v->modal.accept,sizeof(v->modal.accept),page==MD_LOGOUT ? "LOGOUT" : "NEXT LEAGUE");
    v->focus=dashboard_focus;v->helper_count=0;helper(v,"B","CANCEL");helper(v,"A","SELECT");
    copy(v->modal.error,sizeof(v->modal.error),notice);
  }
  if(page==MD_PACK_BUY) {
    v->modal.open=1;v->modal.selected=focus;
    copy(v->modal.title,sizeof(v->modal.title),"OPEN THIS PACK?");
    snprintf(v->modal.body,sizeof(v->modal.body),"%u NX Cash will be deducted now. Choose %u from %u players after opening. Your paid pack will resume if the app closes.",pack_prices[pack_choice],pack_draws[pack_choice],pack_pools[pack_choice]);
    copy(v->modal.accept,sizeof(v->modal.accept),"PAY & OPEN");
    copy(v->modal.error,sizeof(v->modal.error),notice);
    v->helper_count=0;helper(v,"B","CANCEL");helper(v,"A","SELECT");
  }
  if(authenticated && profile_ready && md.joined) {
    MdRow items[MD_NEWS_MAX];uint32_t n=news_rows(items);
    if(n)v->news_preview=items[(now()/20000u)%n];
  }
  if(notice[0] && !v->modal.open) {
    v->modal.open=1;v->modal.information=1;
    copy(v->modal.title,sizeof(v->modal.title),"CLUB MESSAGE");
    copy(v->modal.body,sizeof(v->modal.body),notice);
    copy(v->modal.accept,sizeof(v->modal.accept),"OK");
    v->helper_count=0;helper(v,"A","OK");
  }
  pthread_mutex_unlock(&md_mutex);
}

void manager_dummy_audio_frame(ManagerLeagueAudioFrame *out, uint64_t monotonic_ms) {
  if (!out)
    return;
  pthread_mutex_lock(&md_mutex);
  memset(out, 0, sizeof(*out));
  out->monotonic_ms = monotonic_ms;
  out->timeline_serial = timeline_serial;
  if (page == MD_WATCH && md.joined && !editor) {
    const MdFixture *f = watch_fixture();
    const uint32_t phase = manager_dummy_phase(f, broadcast_now());
    out->fixture_token = ((uint64_t)f->seed << 32) ^ f->kickoff_ms ^ (fixture_choice + 1u);
    out->visible_watch = phase != 0;
    out->replay = replay;
    out->paused = paused;
    out->position_ms = replay ? replay_ms : manager_dummy_elapsed(f, broadcast_now());
    for (uint32_t i = 0; i < manager_dummy_event_count(f); i++)
      if (f->events[i].at_ms <= out->position_ms) {
        out->event_serial = i + 1;
        out->event_at_ms = f->events[i].at_ms;
        out->event_kind = f->events[i].kind;
        out->event_side = f->events[i].side;
      }
    if (out->position_ms >= manager_dummy_duration(f)) {
      out->event_serial = manager_dummy_event_count(f) + 1;
      out->event_at_ms = manager_dummy_duration(f);
      out->event_kind = MLA_FULL_TIME;
    }
  }
  pthread_mutex_unlock(&md_mutex);
}

int manager_dummy_plan_editor(void) {
  pthread_mutex_lock(&md_mutex);
  int v = editor;
  pthread_mutex_unlock(&md_mutex);
  return v;
}
int manager_dummy_plan_teams(uint32_t *home, uint32_t *away) {
  pthread_mutex_lock(&md_mutex);
  int ok = editor && profile_ready && !profile_blocked;
  if (ok) {
    if (home)
      *home = profile.clubs[0];
    if (away)
      *away = profile.clubs[1];
  }
  pthread_mutex_unlock(&md_mutex);
  return ok;
}
void manager_dummy_plan_handoff_result(int opened) {
  pthread_mutex_lock(&md_mutex);
  if (opened)
    restore_pending = 1;
  else {
    editor = 0;
    restore_pending = 0;
    snprintf(notice, sizeof(notice), "GAME PLAN COULD NOT OPEN - CLUB DATA PRESERVED");
  }
  pthread_mutex_unlock(&md_mutex);
}
void manager_dummy_plan_error(void) {
  pthread_mutex_lock(&md_mutex);
  snprintf(notice, sizeof(notice), "GAME PLAN COULD NOT BE SAVED");
  pthread_mutex_unlock(&md_mutex);
}
int manager_dummy_restore(void) {
  pthread_mutex_lock(&md_mutex);
  int ok = editor && restore_pending;
  if (ok) {
    editor = restore_pending = 0;
    page=editor_return_page;hub_section=editor_return_section;focus=editor_return_focus;
    if(page==MD_DASHBOARD)dashboard_focus=focus;
    navigation_serial++;
  }
  pthread_mutex_unlock(&md_mutex);
  return ok;
}
int manager_dummy_roster(uint32_t team, uint32_t players[40], uint8_t shirts[40], uint32_t *count) {
  pthread_mutex_lock(&md_mutex);
  uint32_t t = 0;
  while (t < 2 && profile.clubs[t] != team)
    t++;
  int ok = editor && profile_ready && t < 2;
  if (ok) {
    *count = profile.counts[t];
    for (uint32_t n = 0; n < *count; n++) {
      players[n] = squad[t][n]->native_id;
      shirts[n] = (uint8_t)(n + 1);
    }
  }
  pthread_mutex_unlock(&md_mutex);
  return ok;
}
int manager_dummy_player_allowed(uint32_t team, uint32_t native) {
  pthread_mutex_lock(&md_mutex);
  int allowed = -1;
  if (editor && profile_ready) {
    allowed = 0;
    for (uint32_t t = 0; t < 2; t++)
      if (profile.clubs[t] == team) {
        for (uint32_t n = 0; n < profile.counts[t]; n++)
          if (squad[t][n]->native_id == native)
            allowed = 1;
      }
  }
  pthread_mutex_unlock(&md_mutex);
  return allowed;
}
int manager_dummy_plan_scope(ManagerLeaguePlanScope *out) {
  if (!out)
    return 0;
  pthread_mutex_lock(&md_mutex);
  int ok = editor && profile_ready;
  if (ok)
    ok = profile_scope(&profile, out);
  pthread_mutex_unlock(&md_mutex);
  return ok;
}
int manager_dummy_preset_read(uint32_t team, uint32_t slot, GameplanPreset *out) {
  ManagerLeaguePlanScope scope;
  if (!out || !manager_dummy_plan_scope(&scope) || team != scope.team_id)
    return 0;
  if (slot == MANAGER_LEAGUE_CURRENT_PLAN_SLOT) {
    pthread_mutex_lock(&md_mutex);
    int ok =
        profile.has_current_plan && manager_league_plan_compatible(&scope, &profile.current_plan);
    if (ok)
      *out = profile.current_plan;
    pthread_mutex_unlock(&md_mutex);
    return ok;
  }
  return manager_league_plan_read(&scope, slot, out);
}
int manager_dummy_preset_write(uint32_t team, uint32_t slot, const GameplanPreset *plan) {
  ManagerLeaguePlanScope scope;
  if (!manager_dummy_plan_scope(&scope) || team != scope.team_id)
    return 0;
  if (slot == MANAGER_LEAGUE_CURRENT_PLAN_SLOT)
    return manager_dummy_store_current_plan(plan);
  return manager_league_plan_write(&scope, slot, plan);
}
int manager_dummy_store_current_plan(const GameplanPreset *plan) {
  pthread_mutex_lock(&md_mutex);
  ManagerLeaguePlanScope scope;
  if (!editor || !profile_ready || !profile_scope(&profile, &scope) ||
      !manager_league_plan_compatible(&scope, plan)) {
    pthread_mutex_unlock(&md_mutex);
    return 0;
  }
  MdProfile before = profile;
  uint32_t roster[MD_REGISTERED] = {0};
  int valid = 1;
  for (uint32_t i = 0; i < plan->player_count; i++) {
    uint32_t native = 0;
    memcpy(&native, plan->players[i].player_id, sizeof(native));
    uint32_t n = 0;
    while (n < profile.counts[0] && squad[0][n]->native_id != native)
      n++;
    uint32_t order = plan->players[i].order_no;
    if (n == profile.counts[0] || order >= profile.counts[0] || roster[order]) {
      valid = 0;
      break;
    }
    roster[order] = squad[0][n]->identity;
  }
  for (uint32_t i = 0; i < profile.counts[0]; i++)
    if (!roster[i])
      valid = 0;
  if (valid) {
    memcpy(profile.roster[0], roster, profile.counts[0] * sizeof(uint32_t));
    profile.current_plan = *plan;
    profile.has_current_plan = 1;
    valid = profile_save();
  }
  if (!valid) {
    profile = before;
    snprintf(notice, sizeof(notice), "GAME PLAN NOT SAVED - PLEASE RETRY");
  } else
    profile_cache();
  pthread_mutex_unlock(&md_mutex);
  return valid;
}

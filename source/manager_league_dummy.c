#define _POSIX_C_SOURCE 200809L
#include "manager_league_dummy.h"
#include "competition_hub_navigation.h"
#include "exhibition_team_catalog.h"
#include "master_league_catalog.h"
#include <math.h>
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
#define MD_FILE "SaveData/manager-league-dummy-v1.dat"
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
static int shop_locked(void) {
  return md.joined && manager_dummy_week(&md, now()).state == MD_MATCH_DAY;
}
static uint32_t rng(uint32_t *s) {
  *s = *s * 1664525u + 1013904223u;
  return *s;
}
#include "manager_league_profile.inc"
static uint32_t timeline_serial;
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
uint32_t manager_dummy_elapsed(const MdFixture *f, uint64_t now) {
  if (now <= f->kickoff_ms)
    return 0;
  const uint64_t delta = now - f->kickoff_ms;
  return delta >= MD_DURATION ? MD_DURATION : (uint32_t)delta;
}
uint32_t manager_dummy_phase(const MdFixture *f, uint64_t now) {
  return now < f->kickoff_ms ? 0u : now - f->kickoff_ms < MD_DURATION ? 1u : 2u;
}
MdWeek manager_dummy_week(const MdSave *save, uint64_t stamp) {
  MdWeek week = {MD_PRE_LEAGUE, 1, 0, 0};
  if (!save || !save->joined)
    return week;
  uint64_t first = UINT64_MAX, last = 0;
  for (uint32_t i = 0; i < MD_FIXTURES; i++) {
    const uint64_t kickoff = save->fixtures[i].kickoff_ms;
    if (kickoff < first)
      first = kickoff;
    if (kickoff > last)
      last = kickoff;
  }
  week.first_kickoff_ms = first;
  week.result_ms = first + 3u * (uint64_t)MD_DEMO_DAY_MS;
  /* A postponed fixture keeps the cycle open; day seven cannot fabricate a
   * completed table. No outcome is read before the final broadcast ends. */
  if (last + MD_DURATION > week.result_ms)
    week.result_ms = last + MD_DURATION;
  if (stamp < first) {
    const uint64_t remaining = first - stamp;
    week.day = remaining > 2u * MD_DEMO_DAY_MS ? 1u : remaining > MD_DEMO_DAY_MS ? 2u : 3u;
  } else if (stamp < week.result_ms) {
    week.state = MD_MATCH_DAY;
    const uint64_t day = (stamp - first) / MD_DEMO_DAY_MS;
    week.day = 4u + (day > 2u ? 2u : (uint32_t)day);
  } else {
    week.state = MD_RESULT;
    week.day = 7;
  }
  return week;
}
void manager_dummy_score(const MdFixture *f, uint32_t elapsed, uint32_t out[2]) {
  out[0] = out[1] = 0;
  for (uint32_t i = 0; i < MD_EVENTS; i++)
    if (f->events[i].at_ms <= elapsed && f->events[i].goal && f->events[i].side < 2u)
      out[f->events[i].side]++;
}
int manager_dummy_valid(const MdSave *s) {
  if (s->magic != MD_MAGIC || s->version != 1 || s->bytes != sizeof(*s) ||
      s->checksum != checksum(s) || s->created > 1 || s->joined > 1 || s->joined > s->created ||
      s->purchased_mask > 7 || s->formation > 2 || s->mentality > 2 || s->tempo > 2 ||
      !memchr(s->name, 0, sizeof(s->name)) || (s->club && !exhibition_team_catalog_find(s->club)) ||
      (s->created && !s->club) || s->clock_offset_ms < -INT64_C(315360000000) ||
      s->clock_offset_ms > INT64_C(315360000000))
    return 0;
  uint32_t spent = 0;
  for (uint32_t i = 0; i < 3; i++)
    if (s->purchased_mask & (1u << i))
      spent += shop_prices[i];
  if (spent > 5000 || s->balance != 5000 - spent)
    return 0;
  if (!s->joined)
    return 1;
  uint32_t pairs[MD_TEAMS][MD_TEAMS] = {{0}};
  for (uint32_t i = 0; i < MD_FIXTURES; i++) {
    const MdFixture *f = &s->fixtures[i];
    if (f->home >= MD_TEAMS || f->away >= MD_TEAMS || f->home == f->away || f->round >= 7 ||
        f->kickoff_ms < 1000000000000ULL || f->kickoff_ms > 5000000000000ULL)
      return 0;
    uint32_t a = f->home < f->away ? f->home : f->away, b = f->home ^ f->away ^ a;
    if (pairs[a][b]++)
      return 0;
    for (uint32_t j = 0; j < i; j++)
      if (s->fixtures[j].round == f->round &&
          (s->fixtures[j].home == f->home || s->fixtures[j].away == f->home ||
           s->fixtures[j].home == f->away || s->fixtures[j].away == f->away))
        return 0;
    uint32_t active[2][11];
    for (uint32_t a = 0; a < 2; a++)
      for (uint32_t n = 0; n < 11; n++)
        active[a][n] = n + 1;
    uint32_t used[2] = {0};
    for (uint32_t j = 0; j < MD_EVENTS; j++) {
      const MdEvent *e = &f->events[j];
      if (e->side > 1 || e->kind > MD_HALF || e->goal != (e->kind == MD_GOAL) ||
          e->at_ms != (j + 1) * 6000u || e->player < 1 || e->player > 18)
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
      } else if (e->other)
        return 0;
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
static int persist(void) {
  if (blocked)
    return 0;
  md.magic = MD_MAGIC;
  md.version = 1;
  md.bytes = sizeof(md);
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
           ok ? "PROFILE SAVED" : "SAVE FAILED - X TO RETRY; KEEP THIS SESSION OPEN");
  return ok;
}
static void load_once(void) {
  if (loaded)
    return;
  loaded = 1;
  if (read_file(MD_FILE, &md)) {
    if (md.joined)
      profile_load();
    return;
  }
  if (read_file(MD_FILE ".bak", &md)) {
    if (md.joined)
      profile_load();
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
  memset(&md, 0, sizeof(md));
  md.balance = 5000;
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
static void overall_rows(MdRow out[7]) {
  uint32_t rp[7] = {0, 1240, 1150, 980, 830, 710, 620}, order[7] = {0, 1, 2, 3, 4, 5, 6};
  MdRow ranked[7];
  table_rows(ranked);
  if (manager_dummy_week(&md, now()).state == MD_RESULT)
    for (uint32_t i = 0; i < 7; i++)
      rp[ranked[i].team_id] += 700 - i * 100;
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
             t ? "Sample history for this dummy opponent" : "Your club's first demo season");
  }
}
static void make_fixtures(void) {
  const uint64_t kickoff = ((now() / 60000u) + 1u) * 60000u + 3u * (uint64_t)MD_DEMO_DAY_MS;
  uint32_t ring[8] = {0, 1, 2, 3, 4, 5, 6, 7}, n = 0, seed = md.seed;
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
      const uint64_t offset = round < 3   ? round * 180000u
                              : round < 5 ? MD_DEMO_DAY_MS + (round - 3) * 240000u
                                          : 2u * MD_DEMO_DAY_MS + (round - 5) * 240000u;
      f->kickoff_ms = kickoff + offset;
      f->seed = rng(&seed);
      uint32_t s = f->seed, active[2][11];
      for (uint32_t side = 0; side < 2; side++)
        for (uint32_t p = 0; p < 11; p++)
          active[side][p] = p + 1;
      static const uint32_t kinds[MD_EVENTS] = {
          MD_PASS, MD_SHOT,    MD_SAVE,    MD_FOUL, MD_PASS, MD_GOAL, MD_CORNER, MD_YELLOW,
          MD_SHOT, MD_PASS,    MD_OFFSIDE, MD_SAVE, MD_FOUL, MD_PASS, MD_HALF,   MD_PASS,
          MD_SHOT, MD_CORNER,  MD_GOAL,    MD_SUB,  MD_FOUL, MD_SAVE, MD_SHOT,   MD_PASS,
          MD_SUB,  MD_OFFSIDE, MD_CORNER,  MD_SAVE, MD_SHOT};
      for (uint32_t j = 0; j < MD_EVENTS; j++) {
        MdEvent *e = &f->events[j];
        e->at_ms = (j + 1) * 6000u;
        e->side = (rng(&s) >> 16) & 1u;
        e->kind = kinds[j];
        e->goal = e->kind == MD_GOAL;
        uint32_t slot = 1 + (rng(&s) >> 16) % 10u;
        e->player = active[e->side][slot];
        if (e->kind == MD_SUB) {
          e->other = j == 19 ? 12 : 13;
          active[e->side][slot] = e->other;
        }
      }
    }
    const uint32_t last = ring[7];
    for (uint32_t j = 7; j > 1; j--)
      ring[j] = ring[j - 1];
    ring[1] = last;
  }
}
void manager_dummy_tick_at(uint64_t ms) {
  pthread_mutex_lock(&md_mutex);
  const uint64_t delta = last_tick && ms >= last_tick ? ms - last_tick : 0;
  last_tick = ms;
  epoch_now = ms;
  if (profile_ready && md.joined && !profile.roster_locked &&
      now() >= manager_dummy_week(&md, now()).first_kickoff_ms) {
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
    replay_ms = (uint32_t)fmin((double)MD_DURATION, (double)replay_ms + (double)delta);
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
  page = md.joined && profile_ready && profile.user_id[0] ? MD_DASHBOARD
         : md.joined                                      ? MD_NAME
                                                          : MD_REGISTER;
  focus = dashboard_focus = hub_section = 0;
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
  return focus == 1 ? profile.user_id : focus == 2 ? "" : md.name;
}
const char *manager_dummy_input_label(void) {
  return focus == 1 ? "USER ID" : focus == 2 ? "PASSWORD" : "TEAM NAME";
}
int manager_dummy_input_password(void) { return page == MD_NAME && focus == 2; }
static void clear_password(void) {
  volatile char *p = password;
  for (size_t i = 0; i < sizeof(password); i++)
    p[i] = 0;
}
void manager_dummy_name_result(const char *text) {
  pthread_mutex_lock(&md_mutex);
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
    if (focus == 2) {
      clear_password();
      if (strlen(value) >= 8 && strlen(value) < sizeof(password))
        snprintf(password, sizeof(password), "%s", value);
      else
        snprintf(notice, sizeof(notice), "PASSWORD: AT LEAST 8 CHARACTERS");
    } else if (focus == 1) {
      int valid = strlen(value) >= 3 && strlen(value) <= 24;
      for (const char *p = value; *p; p++)
        if (!((*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') || (*p >= '0' && *p <= '9') ||
              *p == '_' || *p == '.'))
          valid = 0;
      if (valid)
        snprintf(profile.user_id, sizeof(profile.user_id), "%.24s", value);
      else
        snprintf(notice, sizeof(notice), "USER ID: 3-24 LETTERS, NUMBERS, DOT OR UNDERSCORE");
    } else if (*value) {
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
  uint32_t n = 0;
  for (uint32_t i = 0; i < MD_FIXTURES; i++) {
    uint32_t day = md.fixtures[i].round < 3 ? 4 : md.fixtures[i].round < 5 ? 5 : 6;
    if (!schedule_day || day == schedule_day)
      out[n++] = i;
  }
  return n;
}
static void open_plan(void) {
  if (!profile_ready || profile_blocked) {
    snprintf(notice, sizeof(notice), "PLAYER PROFILE UNAVAILABLE");
    return;
  }
  if (shop_locked()) {
    snprintf(notice, sizeof(notice), "STRATEGY LOCKED FOR THIS COMPETITION");
    return;
  }
  editor = 1;
  restore_pending = 0;
  action = MD_ACTION_PLAN;
}
void manager_dummy_pad(uint32_t key) {
  pthread_mutex_lock(&md_mutex);
  if (blocked || profile_blocked) {
    if (key & B)
      action = MD_ACTION_EXIT;
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
    goto done;
  }
  if (key & B) {
    timeline_serial++;
    if (page == MD_REGISTER || page == MD_DASHBOARD) {
      clear_password();
      action = MD_ACTION_EXIT;
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
    } else if (page == MD_TEAM_INFO) {
      page = team_return;
      focus = team_return_focus;
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
      page = MD_CALENDAR;
      focus = calendar_day - 1;
    } else {
      page = MD_DASHBOARD;
      focus = dashboard_focus;
    }
    goto done;
  }
  if (page == MD_REGISTER) {
    if (key & A) {
      page = MD_LEAGUES;
      category = club_choice = focus = 0;
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
    else if ((key & A) && focus < 3)
      action = MD_ACTION_NAME;
    else if (((key & A) && focus == 3) || (key & X)) {
      if (!md.name[0] || !profile.user_id[0] || !password[0]) {
        snprintf(notice, sizeof(notice), "COMPLETE TEAM NAME, USER ID AND PASSWORD");
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
      if (!md.joined) {
        md.created = md.joined = 1;
        make_fixtures();
      }
      if (persist()) {
        clear_password();
        page = MD_DASHBOARD;
        focus = dashboard_focus = 0;
        tutorial = profile.tutorials == 7 ? 0 : 1;
        notice[0] = 0;
      }
    }
    goto done;
  }
  if (page == MD_DASHBOARD) {
    const uint32_t old = hub_section;
    if (key & (UP | DOWN | L | R | LEFT | RIGHT))
      fnx_hub_navigate_count(key, &hub_section, &focus, 3u);
    else if (key & A) {
      static const MdPage destinations[3][5] = {
          {MD_SCHEDULE, MD_NEWS, MD_CALENDAR, MD_TABLE, MD_TEAM_INFO},
          {MD_TEAM_INFO, MD_STRATEGY, MD_SHOP, MD_TEAM_INFO, MD_TEAMS_PAGE},
          {MD_TABLE, MD_OVERALL, MD_CALENDAR, MD_SCHEDULE, MD_RULES}};
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
      focus = 0;
      schedule_day = 0;
      if (page == MD_TEAM_INFO) {
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
    } else if (key & X) {
      static const int64_t offsets[] = {
          -3 * MD_DEMO_DAY_MS, 60000, 90000, 200000, MD_DEMO_DAY_MS, 2 * MD_DEMO_DAY_MS,
          3 * MD_DEMO_DAY_MS};
      static uint32_t clock_step;
      uint32_t step = clock_step++ % 7u;
      md.clock_offset_ms = (int64_t)md.fixtures[0].kickoff_ms + offsets[step] - (int64_t)epoch_now;
      timeline_serial++;
      persist();
    }
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
      page = MD_TEAM_INFO;
      focus = 0;
    }
    goto done;
  }
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
        watch_return=MD_NEWS;watch_return_focus=focus;
        fixture_choice=item->identity-1;replay=1;replay_ms=paused=0;page=MD_WATCH;timeline_serial++;
      } else {
        team_choice=item->team_id;team_return=MD_NEWS;team_return_focus=focus;page=MD_TEAM_INFO;focus=0;
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
        focus = focus + 4 < count ? focus + 4 : count;
      }
    } else if (key & A) {
      if (focus == count)
        pack_confirm();
      else if (pack_selected & (1u << focus))
        pack_selected &= ~(1u << focus);
      else if (selected_count() < pack_draws[pack_choice])
        pack_selected |= 1u << focus;
      else
        snprintf(notice, sizeof(notice), "DESELECT A PLAYER TO CHANGE YOUR CHOICE");
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
  if (page == MD_SCHEDULE) {
    uint32_t indices[MD_FIXTURES], count = schedule_indices(indices);
    if ((key & LEFT) && focus % 2)
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
      watch_return=MD_SCHEDULE;watch_return_focus=focus;
      fixture_choice = indices[focus];
      replay = manager_dummy_phase(&md.fixtures[fixture_choice], now()) == 2;
      replay_ms = 0;
      paused = 0;
      page = MD_WATCH;
      timeline_serial++;
    }
    goto done;
  }
  if (page == MD_WATCH) {
    const uint32_t finished = manager_dummy_phase(&md.fixtures[fixture_choice], now()) == 2;
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
        replay_ms = replay_ms > MD_DURATION - 15000 ? MD_DURATION : replay_ms + 15000;
        timeline_serial++;
      }
      if (key & X) {
        replay_ms = 0;
        timeline_serial++;
      }
    }
  }
done:
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
  if (v->helper_count < 5) {
    v->helper_key[v->helper_count] = key;
    v->helper_label[v->helper_count++] = label;
  }
}
static const char *event_name(uint32_t kind) {
  static const char *const names[] = {"PASSING MOVE", "SHOT WIDE", "GOAL",   "FOUL", "YELLOW CARD",
                                      "SUBSTITUTION", "OFFSIDE",   "CORNER", "SAVE", "HALF TIME"};
  return kind <= MD_HALF ? names[kind] : "KICKOFF";
}
void manager_dummy_view(MdView *v) {
  pthread_mutex_lock(&md_mutex);
  memset(v, 0, sizeof(*v));
  v->page = page;
  v->focus = focus;
  v->balance = profile_ready ? profile.balance : md.balance;
  v->joined = md.joined;
  v->now_ms = now();
  v->navigation_serial = navigation_serial;
  v->slide_direction = slide_direction;
  v->timeline_serial = timeline_serial;
  v->tab = hub_section;
  v->roster_size = profile_ready ? profile.counts[0] : 0;
  v->shop_locked = shop_locked();
  v->week = manager_dummy_week(&md, now());
  static const char *const phase_names[] = {"PRE-LEAGUE", "MATCH DAY", "RESULT"};
  copy(v->phase_label, sizeof(v->phase_label), phase_names[v->week.state]);
  v->event_kind = UINT32_MAX;
  v->event_age_ms = UINT32_MAX;
  copy(v->title, sizeof(v->title), "ONLINE LEAGUE");
  copy(v->subtitle, sizeof(v->subtitle), "YOUR CLUB. YOUR LEAGUE.");
  copy(v->name, sizeof(v->name), md.name[0] ? md.name : "YOUR CLUB");
  v->placeholder = !md.club;
  copy(v->user_id, sizeof(v->user_id), profile.user_id);
  v->account_field = focus;
  copy(v->club, sizeof(v->club), exhibition_team_catalog_name(md.club));
  copy(v->status, sizeof(v->status), notice);
  v->badge = badge(0);
  v->tutorial = tutorial;
  helper(v, "B", "BACK");
  if (page == MD_REGISTER) {
    copy(v->headline, sizeof(v->headline), "BUILD YOUR CLUB");
    copy(v->summary, sizeof(v->summary),
         "Choose a club. Create your manager profile. Join the league.");
    v->count = 1;
    row(v, 0, "CREATE YOUR CLUB", "A new week. A new football story.", "START", 0);
    helper(v, "A", "START");
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
    copy(v->caption, sizeof(v->caption), "LOCAL PROFILE");
    v->count = 4;
    row(v, 0, "TEAM NAME", "Your club name in the league", md.name[0] ? md.name : "ENTER NAME", 0);
    row(v, 1, "USER ID", "3-24 letters, numbers, dot or underscore",
        profile.user_id[0] ? profile.user_id : "ENTER USER ID", 0);
    row(v, 2, "PASSWORD", "8 characters minimum", password[0] ? "PASSWORD SET" : "ENTER PASSWORD",
        0);
    row(v, 3, "CREATE CLUB", "Password is not saved by this local preview", "CONTINUE", 0);
    helper(v, "A", focus == 3 ? "CONTINUE" : "EDIT");
  } else if (page == MD_DASHBOARD) {
    static const char *const labels[3][5] = {
        {"NEXT BROADCAST", "CLUB FEED", "MATCH SCHEDULE", "WEEKLY STANDINGS", "CLUB PROFILE"},
        {"MY SQUAD", "STRATEGY", "PLAYER SHOP", "MY SQUAD", "OTHER TEAMS"},
        {"WEEKLY STANDINGS", "OVERALL RANKING", "MATCH CENTRE", "OVERALL RANKING", "LEAGUE GUIDE"}};
    static const char *const details[3][5] = {
        {"Watch the scheduled broadcast", "News, results and club stories",
         "All fixtures and full replays", "This week's title race",
         "Your squad and player profiles"},
        {"Players, portraits and squad roles", "Open your team Game Plan",
         "Build your squad with points", "Registered players", "Meet your six opponents"},
        {"League points from this season", "Reputation across seasons",
         "Every live game and full replay", "Sample career reputation",
         "Calendar and competition rules"}};
    static const char *const news_titles[] = {"PREPARE FOR THE WEEK AHEAD",
                                              "THE THREE-DAY TITLE RACE", "WEEK 01 IS COMPLETE"};
    static const char *const news_details[] = {
        "Build your squad, shop and prepare your strategy before Match Day.",
        "Follow every scheduled game. The player market is closed for all three days.",
        "Final standings and every replay are available. Demo rewards are not credited."};
    copy(v->headline, sizeof(v->headline), news_titles[v->week.state]);
    copy(v->summary, sizeof(v->summary), news_details[v->week.state]);
    snprintf(v->caption, sizeof(v->caption), "%s - DAY %u OF 7 - WEEK 01", v->phase_label,
             v->week.day);
    v->count = 5;
    for (uint32_t i = 0; i < 5; i++)
      row(v, i, labels[hub_section][i], details[hub_section][i], "OPEN", 0);
    if (!hub_section && v->week.state == MD_PRE_LEAGUE)
      row(v, 0, "PREPARE YOUR CLUB", "Shop, squad and strategy before the first broadcast.",
          "7 CLUBS REGISTERED", 0);
    else if (!hub_section && v->week.state == MD_RESULT)
      row(v, 0, "SEASON RESULTS", "The final weekly table is ready.", "VIEW FINAL STANDINGS", 0);
    if (hub_section == 1 && v->shop_locked)
      row(v, 2, "PLAYER SHOP - CLOSED", "Opens on Result day. Existing offers can be inspected.",
          "CLOSED", 0);
    helper(v, "L", "PREV PAGE");
    helper(v, "R", "NEXT PAGE");
    helper(v, "A", "OPEN");
    helper(v, "X", "DEMO CLOCK");
    MdRow ranked[7];
    table_rows(ranked);
    for (uint32_t i = 0; i < 7; i++)
      if (!ranked[i].team_id)
        v->rank = i + 1;
    if (v->week.state == MD_RESULT) {
      snprintf(v->summary, sizeof(v->summary),
               "Champion: %.48s. All 21 matches finished. No demo reward payout.",
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
         v->week.state == MD_RESULT ? "FINAL WEEKLY STANDINGS" : "WEEKLY STANDINGS");
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
      row(v, i, team_name(t), t ? "LEAGUE CLUB" : "YOUR CLUB", "SQUAD", badge(t));
    }
    helper(v, "A", "TEAM INFO");
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
    snprintf(v->caption, sizeof(v->caption), "%u POINTS - %s", v->balance,
             shop_locked() ? "SHOP CLOSED" : "DEMO OFFERS");
    v->count = 3;
    static const char *const tiers[] = {"LITE", "MEDIUM", "JUMBO"};
    for (uint32_t i = 0; i < 3; i++) {
      char detail[96], value[40];
      snprintf(detail, sizeof(detail), "%u PLAYERS FROM A POOL OF %u", pack_draws[i],
               pack_pools[i]);
      snprintf(value, sizeof(value), profile.receipts & (1u << i) ? "OPENED" : "%u POINTS",
               pack_prices[i]);
      row(v, i, tiers[i], detail, value, exhibition_team_catalog_badge(pack_clubs[i]));
      v->rows[i].team_id = pack_clubs[i];
    }
    helper(v, "LEFT", "SELECT");
    helper(v, "A", "VIEW PACK");
  } else if (page == MD_PACK || page == MD_PACK_RESULT || page == MD_PACK_OPENING ||
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
    }
    helper(v, "A",
           page == MD_PACK           ? profile.receipts & (1u << k) ? "VIEW RECEIPT" : "OPEN PACK"
           : page == MD_PACK_SELECT  ? focus == pack_pools[k] ? "CONFIRM" : "SELECT"
           : page == MD_PACK_OPENING ? "OPENING"
                                     : "CONTINUE");
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
    static const char *const labels[] = {"WEEKLY SEASON", "SEVEN CLUBS",     "LEAGUE POINTS",
                                         "WALLET POINTS", "OVERALL RANKING", "LIVE AND REPLAY",
                                         "LOCAL PREVIEW"};
    static const char *const details[] = {
        "Pre-League days 1-3. Match Day days 4-6. Result on day 7.",
        "Six opponents. One round robin. 21 matches.",
        "Win 3, draw 1, lose 0. Then goal difference and goals scored.",
        "5,000 starting points. Shop in Pre-League and Result.",
        "Reputation is separate from spendable points.",
        "Three-minute broadcasts. Join in progress or watch a replay.",
        "One preview day is 9 minutes. X in the hub advances time."};
    for (uint32_t i = 0; i < v->count; i++)
      row(v, i, labels[v->first + i], details[v->first + i], "", 0);
  } else if (page == MD_OVERALL) {
    copy(v->headline, sizeof(v->headline), "OVERALL RANKING");
    copy(v->caption, sizeof(v->caption), "Preview reputation across seasons");
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
      const uint64_t day_start = d <= 3   ? first - (4u - d) * (uint64_t)MD_DEMO_DAY_MS
                                 : d <= 6 ? first + (d - 4u) * (uint64_t)MD_DEMO_DAY_MS
                                          : v->week.result_ms;
      struct tm local, end;
      manager_local_time(day_start, &local);
      manager_local_time(day_start + MD_DEMO_DAY_MS, &end);
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
  } else if (page == MD_SCHEDULE) {
    copy(v->headline, sizeof(v->headline), "MATCH CENTRE");
    uint32_t indices[MD_FIXTURES];
    v->total = schedule_indices(indices);
    v->first = focus / MD_MATCH_VISIBLE * MD_MATCH_VISIBLE;
    v->count = v->total - v->first;
    if (v->count > MD_MATCH_VISIBLE)
      v->count = MD_MATCH_VISIBLE;
    for (uint32_t i = 0; i < v->count; i++) {
      const MdFixture *f = &md.fixtures[indices[v->first + i]];
      char label[64], detail[96], text[40];
      snprintf(label, sizeof(label), "%.26s Vs %.26s", team_name(f->home), team_name(f->away));
      uint32_t phase = manager_dummy_phase(f, now());
      uint32_t goals[2];
      manager_dummy_score(f, manager_dummy_elapsed(f, now()), goals);
      struct tm local;
      manager_local_time(f->kickoff_ms, &local);
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
      row(v, i, label, detail, text, badge(f->home));
      v->rows[i].away_badge = badge(f->away);
      v->rows[i].phase = phase;
    }
    helper(v, "A", "WATCH MATCH");
  } else if (page == MD_WATCH) {
    const MdFixture *f = &md.fixtures[fixture_choice];
    v->phase = manager_dummy_phase(f, now());
    v->fixture = fixture_choice;
    v->round = f->round + 1;
    v->home_badge = badge(f->home);
    v->away_badge = badge(f->away);
    v->watching_replay = replay;
    v->paused = paused;
    v->kickoff_ms = f->kickoff_ms;
    v->elapsed_ms = replay ? replay_ms : manager_dummy_elapsed(f, now());
    v->minute = v->elapsed_ms / 2000u;
    uint32_t goals[2];
    manager_dummy_score(f, v->elapsed_ms, goals);
    v->home_goals = goals[0];
    v->away_goals = goals[1];
    snprintf(v->score, sizeof(v->score), "%u - %u", goals[0], goals[1]);
    snprintf(v->clock, sizeof(v->clock), "%02u:%02u", v->elapsed_ms / 2000u,
             (v->elapsed_ms % 2000u) * 60u / 2000u);
    copy(v->home, sizeof(v->home), team_name(f->home));
    copy(v->away, sizeof(v->away), team_name(f->away));
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
    for (uint32_t i = 0; i < MD_EVENTS; i++)
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
            profile_ready && e->player <= 18 ? match_squad[club][e->player - 1] : NULL;
        const MlCatalogPlayer *incoming =
            profile_ready && e->other && e->other <= 18 ? match_squad[club][e->other - 1] : NULL;
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
        snprintf(v->summary, sizeof(v->summary), "%02u' %s - %.48s", e->at_ms / 2000u,
                 event_name(e->kind), team_name(side ? f->away : f->home));
        v->event_feed[2] = v->event_feed[1];
        v->event_feed[1] = v->event_feed[0];
        snprintf(v->event_feed[0].label, sizeof(v->event_feed[0].label), "%02u' %s",
                 e->at_ms / 2000u, event_name(e->kind));
        snprintf(v->event_feed[0].detail, sizeof(v->event_feed[0].detail), "%.30s - %.40s",
                 team_name(club), player ? player->name : "PLAYER");
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
        "Your club starts with 5,000 points. Use them in the player shop to strengthen your squad.",
        "Prepare for three days, follow three Match Days, then see the weekly results on day "
        "seven. Every match has a scheduled broadcast and replay.",
        "Open Squad for your players and Game Plan. The shop offers club packs. In this local "
        "preview, X in the hub advances the demo clock."};
    v->modal.open = 1;
    v->modal.information = 1;
    v->helper_count=0;helper(v,"A",tutorial==3 ? "LET'S BEGIN" : "CONTINUE");
    copy(v->modal.title, sizeof(v->modal.title), titles[tutorial - 1]);
    copy(v->modal.body, sizeof(v->modal.body), bodies[tutorial - 1]);
    copy(v->modal.accept, sizeof(v->modal.accept), tutorial == 3 ? "LET'S BEGIN" : "CONTINUE");
    copy(v->modal.error,sizeof(v->modal.error),notice);
  }
  if(profile_ready && md.joined) {
    MdRow items[MD_NEWS_MAX];uint32_t n=news_rows(items);
    if(n)v->news_preview=items[(now()/20000u)%n];
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
    const MdFixture *f = &md.fixtures[fixture_choice];
    const uint32_t phase = manager_dummy_phase(f, now());
    out->fixture_token = ((uint64_t)f->seed << 32) ^ f->kickoff_ms ^ (fixture_choice + 1u);
    out->visible_watch = phase != 0;
    out->replay = replay;
    out->paused = paused;
    out->position_ms = replay ? replay_ms : manager_dummy_elapsed(f, now());
    for (uint32_t i = 0; i < MD_EVENTS; i++)
      if (f->events[i].at_ms <= out->position_ms) {
        out->event_serial = i + 1;
        out->event_at_ms = f->events[i].at_ms;
        out->event_kind = f->events[i].kind;
        out->event_side = f->events[i].side;
      }
    if (out->position_ms >= MD_DURATION) {
      out->event_serial = MD_EVENTS + 1;
      out->event_at_ms = MD_DURATION;
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
    page = MD_DASHBOARD;
    hub_section = 1;
    focus = dashboard_focus = 1;
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

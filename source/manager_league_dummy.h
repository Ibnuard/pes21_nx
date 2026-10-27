#ifndef PESNX_MANAGER_LEAGUE_DUMMY_H
#define PESNX_MANAGER_LEAGUE_DUMMY_H
#include <stdint.h>
#include "master_league_frontend.h"
#include "manager_league_plan.h"
#include "manager_league_audio.h"

/* Local fixture archive; player bindings live in a separately versioned profile. */
enum { MD_TEAMS=7, MD_FIXTURES=21, MD_EVENTS=99, MD_DURATION=600000,
       MD_LEGACY_EVENTS=29, MD_LEGACY_DURATION=180000, MD_LEGACY_DAY_MS=540000, MD_PREPARATION_DAY_MS=540000,
       MD_NAME_SIZE=32, MD_ROWS=7, MD_WEEK_VISIBLE=3, MD_DEMO_DAY_MS=1800000,
       MD_PACK_UNSEAL_MS=2400, MD_PACK_OPEN_MS=3400, MD_MATCH_VISIBLE=6 };
enum { MD_CALENDAR_DAY_MS=86400000, MD_LEAGUE_TIMEZONE_MS=25200000 };
enum { MD_LEGACY_PURCHASES=7u, MD_ENTRY_GRANTED=256u, MD_REWARD_SETTLED=512u,
       MD_STARTING_CASH=5000u, MD_ENTRY_CASH=1500u };
enum { MD_PRE_LEAGUE, MD_MATCH_DAY, MD_RESULT };
typedef struct {
  uint32_t state,day;
  uint64_t first_kickoff_ms,result_ms;
} MdWeek;
typedef enum { MD_REGISTER, MD_CLUB, MD_NAME, MD_STRATEGY, MD_JOIN,
               MD_DASHBOARD, MD_TABLE, MD_SCHEDULE, MD_TEAMS_PAGE,
               MD_TEAM_INFO, MD_WATCH, MD_PLAYER_INFO, MD_SHOP, MD_NEWS,
               MD_OVERALL, MD_RULES, MD_LEAGUES, MD_CALENDAR, MD_PACK,
               MD_PACK_RESULT, MD_COLLECTION_PAGE, MD_REPLACE_PLAYER, MD_PACK_OPENING, MD_PACK_SELECT,
               MD_LOGIN, MD_SECURE, MD_LOGOUT, MD_NEXT_WEEK, MD_MIGRATE,
               MD_CLUB_PROFILE, MD_TEAM_HISTORY, MD_CLUB_PLAN, MD_REWARDS,
               MD_PACK_BUY, MD_CHAMPIONS, MD_CHAMPION } MdPage;
enum { MD_ACTION_NONE, MD_ACTION_NAME, MD_ACTION_EXIT, MD_ACTION_PLAN };
enum { MD_PASS, MD_SHOT, MD_GOAL, MD_FOUL, MD_YELLOW, MD_SUB,
       MD_OFFSIDE, MD_CORNER, MD_SAVE, MD_HALF };
typedef struct { uint32_t at_ms, side, goal,kind,player,other; } MdEvent;
typedef struct {
  uint64_t kickoff_ms;
  uint32_t home, away, round, seed;
  uint32_t duration_ms,event_count;
  MdEvent events[MD_EVENTS];
} MdFixture;
/* Old host tapes omit metadata; infer their populated prefix without reading
 * beyond the fixed capacity. Persisted v2 records require explicit metadata. */
static inline uint32_t manager_dummy_event_count(const MdFixture *f) {
  if(!f)return 0;
  if(f->event_count && f->event_count<=MD_EVENTS)return f->event_count;
  uint32_t n=0;while(n<MD_EVENTS && f->events[n].at_ms)n++;return n;
}
static inline uint32_t manager_dummy_duration(const MdFixture *f) {
  if(f && f->duration_ms)return f->duration_ms;
  const uint32_t n=manager_dummy_event_count(f);
  return n && n<=MD_LEGACY_EVENTS ? MD_LEGACY_DURATION : MD_DURATION;
}
static inline uint32_t manager_dummy_game_seconds(const MdFixture *f,uint32_t elapsed) {
  const uint32_t duration=manager_dummy_duration(f);
  return (uint32_t)((uint64_t)(elapsed<duration ? elapsed : duration)*5400u/duration);
}
typedef struct {
  uint32_t magic, version, bytes, checksum, created, joined, club;
  uint32_t balance, formation, mentality, tempo, seed, purchased_mask;
  int64_t clock_offset_ms;
  char name[MD_NAME_SIZE];
  uint32_t week_id,day_ms;
  MdFixture fixtures[MD_FIXTURES];
} MdSave;
typedef struct {
  char label[64], detail[96], value[40];
  uint32_t badge, selected, enabled, team_id;
  uint32_t portrait,identity,native_id,rating,role,league_logo,away_badge,phase;
  LeagueStanding stats;
} MdRow;

typedef struct {
  char period[40];
  uint32_t match_count;
  MdRow matches[4];
} MdScheduleDay;
typedef struct {
  float x,y; uint32_t side,number;
} MdDot;
typedef struct { uint32_t at_ms,kind,side; } MdTimelineMark;
typedef struct {char label[64];uint32_t portrait,rating,role,identity;} MdPlanPlayer;
typedef struct {
  MdPage page;
  char title[64], subtitle[96], status[112], club[64], name[MD_NAME_SIZE];
  char headline[96], summary[112], caption[96], score[20], clock[24];
  char home[64],away[64],team_detail[96];
  uint32_t count, focus, first, total, badge, balance, tab, joined;
  uint32_t navigation_serial,home_badge,away_badge,rank;
  uint32_t week_id,history_week,archive_count;
  MdWeek week;
  char phase_label[24];
  int slide_direction;
  uint32_t home_goals,away_goals,shots[2],on_target[2],minute;
  uint32_t phase, elapsed_ms, duration_ms, watching_replay, paused, fixture;
  uint32_t round,timeline_count;
  uint32_t event_kind,event_age_ms,event_side,event_player,event_other;
  uint32_t event_serial,timeline_serial,event_at_ms;
  uint32_t fouls[2],corners[2],cards[2],substitutions[2],roster_size,shop_locked;
  uint64_t now_ms,kickoff_ms;
  /* Watch's modal and ordinary list pages are mutually exclusive. */
  union { MdRow rows[MD_ROWS]; MdRow touchline[MD_ROWS]; };
  MdScheduleDay schedule[MD_WEEK_VISIBLE];
  MdRow table_preview[3],fixture_preview[3];
  MdRow event_feed[3];
  MdRow news_preview;
  uint32_t last_complete,last_hg,last_ag,last_home_badge,last_away_badge;
  char last_home[64],last_away[64];
  MdDot dots[23];
  MdDot ball_trail[5];
  MdTimelineMark timeline[MD_EVENTS];
  const char *helper_key[6], *helper_label[6];
  uint32_t helper_count;
  uint32_t portrait,account_field,placeholder,tutorial,pack_pool,pack_draw,pack_price;
  char user_id[32],event_name[48],event_other_name[48];
  MlModalView modal;
  MlCalendarCell calendar[42];
  MdRow squad_preview[3],pack_players[8];
  uint32_t pack_count,pack_selected,pack_selection_count,pack_opening_ms;
  /* Controller PIN presentation exposes counts only, never entered digits. */
  uint32_t pin_open,pin_cursor,pin_length,pin_confirming,pin_creating;
  uint32_t league_points,club_team,club_power,club_rating,club_rank,club_reputation;
  MdPlanPlayer plan_players[18];
  uint32_t touchline_open,touchline_first,touchline_count,touchline_total;
  uint32_t match_group,match_groups[3],match_group_first;
  uint64_t rank_reset_ms;
} MdView;

void manager_dummy_open(void);
void manager_dummy_pad(uint32_t pressed);
void manager_dummy_tick(uint64_t monotonic_ms);
void manager_dummy_tick_at(uint64_t epoch_ms); /* Injected clock for host QA. */
void manager_dummy_view(MdView *out);
uint32_t manager_dummy_cash(void);
void manager_dummy_audio_frame(ManagerLeagueAudioFrame *out,uint64_t monotonic_ms);
uint32_t manager_dummy_take_action(void);
const char *manager_dummy_name(void);
const char *manager_dummy_input_label(void);
int manager_dummy_input_password(void);
void manager_dummy_name_result(const char *text);
/* Shared pure timeline/record readers. Clock is never elapsed viewing time. */
uint32_t manager_dummy_elapsed(const MdFixture *fixture,uint64_t now_ms);
uint32_t manager_dummy_phase(const MdFixture *fixture,uint64_t now_ms);
/* Imported archives keep their original timing; new matches last 2 x 5 real minutes. */
MdWeek manager_dummy_week(const MdSave *save,uint64_t now_ms);
void manager_dummy_score(const MdFixture *fixture,uint32_t elapsed,uint32_t out[2]);
int manager_dummy_valid(const MdSave *save);
void manager_dummy_copy_save(MdSave *out);
/* At Result only. Archives the finished week before scheduling its successor. */
int manager_dummy_next_week(void);
int manager_dummy_history_select(uint32_t week_id); /* Match Centre only; 0=current. */
void manager_dummy_history_reset(void);
/* Deterministic tape sampler. Every position is continuous across action boundaries. */
void manager_dummy_sample(const MdFixture *fixture,uint32_t elapsed_ms,MdDot out[23]);
int manager_dummy_plan_editor(void);
int manager_dummy_plan_teams(uint32_t *home,uint32_t *away);
void manager_dummy_plan_handoff_result(int opened);
void manager_dummy_plan_error(void);
int manager_dummy_restore(void);
int manager_dummy_roster(uint32_t team,uint32_t players[40],uint8_t shirts[40],uint32_t *count);
int manager_dummy_player_allowed(uint32_t team,uint32_t native);
int manager_dummy_plan_scope(ManagerLeaguePlanScope *out);
int manager_dummy_preset_read(uint32_t team,uint32_t slot,GameplanPreset *out);
int manager_dummy_preset_write(uint32_t team,uint32_t slot,const GameplanPreset *plan);
int manager_dummy_store_current_plan(const GameplanPreset *plan);
#endif

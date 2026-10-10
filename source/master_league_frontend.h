#ifndef PES21_MASTER_LEAGUE_FRONTEND_H
#define PES21_MASTER_LEAGUE_FRONTEND_H
#include "master_league.h"

enum { ML_ACTION_NONE, ML_ACTION_MATCH, ML_ACTION_NAME_INPUT, ML_ACTION_EXIT };
enum { ML_VIEW_MAX_HELPERS = 5 };
/* Shared standings pagination for Master League and standalone League. */
enum { ML_TABLE_PAGE_ROWS = 6 };
/* A fixed settings value keeps the selector's centered well without arrows. */
enum { ML_VALUE_FIXED = 3 };
/* One-based cells in the reusable generated 4x4 header atlas; zero is none. */
typedef enum {
  ML_HEADER_NONE,ML_HEADER_CALENDAR,ML_HEADER_RANKING,ML_HEADER_SAVE,ML_HEADER_SQUAD,
  ML_HEADER_TACTICS,ML_HEADER_TRANSFER,ML_HEADER_CONTRACT,ML_HEADER_FINANCE,
  ML_HEADER_TROPHY,ML_HEADER_INTERNATIONAL,ML_HEADER_MANAGER,ML_HEADER_MESSAGES,
  ML_HEADER_NEWS,ML_HEADER_SETTINGS,ML_HEADER_STATISTICS,ML_HEADER_MATCH
} MlHeaderIcon;
typedef enum {
  ML_PAGE_LANDING, ML_PAGE_SETTINGS, ML_PAGE_MANAGER, ML_PAGE_NATIONALITY,
  ML_PAGE_CLUBS, ML_PAGE_HUB, ML_PAGE_SLOTS, ML_PAGE_SQUAD, ML_PAGE_OFFICE,
  ML_PAGE_MARKET_CLUBS, ML_PAGE_MARKET_PLAYERS, ML_PAGE_CONTRACTS,
  ML_PAGE_FINANCES, ML_PAGE_TABLE, ML_PAGE_NEXT, ML_PAGE_CONFIRM,
  ML_PAGE_NEWS, ML_PAGE_CALENDAR, ML_PAGE_CUP, ML_PAGE_OFFERS,
  ML_PAGE_MANAGER_OFFICE, ML_PAGE_MESSAGES, ML_PAGE_JOBS, ML_PAGE_ADVANCE,
  ML_PAGE_MY_TEAM, ML_PAGE_MY_PLAYERS, ML_PAGE_COMPETITIONS,
  ML_PAGE_NATIONAL, ML_PAGE_QUALIFIERS, ML_PAGE_INTERNATIONAL_SCHEDULE, ML_PAGE_NATIONAL_OFFERS
} MlPage;

typedef struct {
  char label[64], detail[96], value[48];
  uint32_t badge, portrait, league_logo; /* catalog index + 1, zero means none */
  int enabled;
  uint32_t rating, role, adjustable, unread, emblem;
} MlViewRow;
/* Small, read-only dashboard projections. Never substitute these display rows
 * for the canonical fixture/roster state used by the match adapter. */
typedef struct {
  char home[64], away[64], competition[64], day[32];
  uint32_t home_badge, away_badge;
} MlMatchPreview;
typedef struct {
  char title[64], subtitle[96], detail[96], value[96];
  char body[256],confirm_label[32];
  MlViewRow rows[5];
  uint32_t count, first, total, selected, serial, badge, portrait;
  int open, confirm, confirm_selected, modal;
} MlDrawerView;
typedef struct {
  uint32_t day, badge, kind, current, selected, transfer;
  char label[16], detail[24];
} MlCalendarCell;

typedef struct { char name[64]; uint32_t badge, rank, own; int rank_change; LeagueStanding stats; } MlTableRow;
typedef struct { char home[64],away[64]; uint32_t home_badge,away_badge,hg,ag,complete,own,round,index; } MlBracketMatch;
typedef struct {
  char title[64],body[256],accept[32],error[112];
  uint32_t open,selected,destructive;
} MlModalView;
typedef struct {
  uint32_t club_badge,nation_badge,home_badge,away_badge,has_result,home_goals,away_goals;
  char headline[64],summary[112],home[64],away[64];
  uint32_t result_kind,result_day,result_team;
  char competition[64],result[32];
  char stat_label[3][32],stat_value[3][48];
  MlViewRow history[3];uint32_t history_count;
} MlStoryView;
typedef struct {
  MlPage page;
  char title[64], caption[96], left_title[64], right_title[64];
  MlViewRow rows[8];
  char info[8][96], status[112];
  char action[4][32];
  const char *helper_key[ML_VIEW_MAX_HELPERS], *helper_label[ML_VIEW_MAX_HELPERS];
  uint32_t count, selected, first, total, action_count, action_focus, helper_count;
  uint32_t badge, portrait;
  int action_selected, action_enabled[4];
  uint32_t section, section_count, feed_index, feed_count;
  float feed_progress,feed_opacity;
  uint32_t navigation_serial;
  int slide_direction;
  char club_name[64], competition[64], balance[32], season_summary[64];
  MlMatchPreview next;
  MlViewRow fixtures[3], ranking[3], squad[3];
  uint32_t fixture_count, ranking_count, squad_count;
  uint32_t rank, squad_size, board_target;
  char annual_budget[32], transfer_budget[32];
  MlDrawerView drawer;
  MlModalView modal;
  MlStoryView story;
  MlCalendarCell calendar[42];
  char calendar_month[48], calendar_detail[112];
  uint32_t calendar_count;
  float advance_progress, advance_fraction;
  char empty[96],toast[64];uint32_t toast_serial;
  uint32_t transfer_unread;
  MlTableRow table[8];uint32_t table_count;
  MlBracketMatch bracket[7];uint32_t bracket_count,bracket_round,bracket_page,bracket_pages;
  char bracket_titles[3][32];
} MlView;

void ml_frontend_open(void);
void ml_frontend_close(void);
void ml_frontend_pad(uint32_t pressed);
/* Called on the input/update thread, never from the renderer. */
void ml_frontend_tick(uint64_t milliseconds);
void ml_frontend_view(MlView *view);
uint32_t ml_frontend_take_action(void);
const MasterLeague *ml_frontend_career(void);
int ml_frontend_match_active(void);
uint32_t ml_frontend_scoreboard(void);
int ml_frontend_plan_editor(void);
void ml_frontend_plan_error(void);
int ml_frontend_match_is_cup(void);
int ml_frontend_match_teams(uint32_t *home, uint32_t *away);
void ml_frontend_handoff_result(int opened);
void ml_frontend_penalty_result(uint32_t home, uint32_t away);
void ml_frontend_result(uint32_t home, uint32_t away,
                        const LeagueScorer *scorers, uint32_t count);
int ml_frontend_restore(void);
const char *ml_frontend_manager_name(void);
void ml_frontend_name_result(const char *text);
int ml_frontend_roster(uint32_t team, uint32_t players[40], uint8_t shirts[40],
                        uint32_t *count);
int ml_frontend_player_allowed(uint32_t team, uint32_t native);
int ml_frontend_preset_read(uint32_t team, uint32_t slot, GameplanPreset *out);
int ml_frontend_preset_write(uint32_t team, uint32_t slot, const GameplanPreset *plan);
int ml_frontend_store_current_plan(const GameplanPreset *plan);
/* Slot 3 is the implicit current career lineup, never a global preset file. */
#define ML_CURRENT_PLAN_SLOT GAMEPLAN_PRESET_SLOTS

#endif

#ifndef PES21_MASTER_LEAGUE_FRONTEND_H
#define PES21_MASTER_LEAGUE_FRONTEND_H
#include "master_league.h"

enum { ML_ACTION_NONE, ML_ACTION_MATCH, ML_ACTION_NAME_INPUT, ML_ACTION_EXIT };
typedef enum {
  ML_PAGE_LANDING, ML_PAGE_SETTINGS, ML_PAGE_MANAGER, ML_PAGE_NATIONALITY,
  ML_PAGE_CLUBS, ML_PAGE_HUB, ML_PAGE_SLOTS, ML_PAGE_SQUAD, ML_PAGE_OFFICE,
  ML_PAGE_MARKET_CLUBS, ML_PAGE_MARKET_PLAYERS, ML_PAGE_CONTRACTS,
  ML_PAGE_FINANCES, ML_PAGE_TABLE, ML_PAGE_NEXT, ML_PAGE_CONFIRM,
  ML_PAGE_NEWS, ML_PAGE_CALENDAR, ML_PAGE_CUP
} MlPage;

typedef struct {
  char label[64], detail[96], value[48];
  uint32_t badge, portrait;
  int enabled;
} MlViewRow;
/* Small, read-only dashboard projections. Never substitute these display rows
 * for the canonical fixture/roster state used by the match adapter. */
typedef struct {
  char home[64], away[64], competition[64], day[32];
  uint32_t home_badge, away_badge;
} MlMatchPreview;
typedef struct {
  MlPage page;
  char title[64], caption[96], left_title[64], right_title[64];
  MlViewRow rows[5];
  char info[8][96], status[112];
  char action[4][32];
  const char *helper_key[4], *helper_label[4];
  uint32_t count, selected, first, total, action_count, action_focus, helper_count;
  uint32_t badge, portrait;
  int action_selected, action_enabled[4];
  uint32_t section, section_count, feed_index, feed_count;
  uint32_t navigation_serial;
  int slide_direction;
  char club_name[64], competition[64], balance[32], season_summary[64];
  MlMatchPreview next;
  MlViewRow fixtures[3], ranking[3], squad[3];
  uint32_t fixture_count, ranking_count, squad_count;
  uint32_t rank, squad_size, board_target;
} MlView;

void ml_frontend_open(void);
void ml_frontend_close(void);
void ml_frontend_pad(uint32_t pressed);
void ml_frontend_view(MlView *view);
uint32_t ml_frontend_take_action(void);
const MasterLeague *ml_frontend_career(void);
int ml_frontend_match_active(void);
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

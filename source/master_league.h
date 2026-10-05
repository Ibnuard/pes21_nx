#ifndef PES21_MASTER_LEAGUE_H
#define PES21_MASTER_LEAGUE_H

#include <stdint.h>
#include "league_tournament.h"
#include "gameplan_preset.h"

#define ML_MAX_CLUBS 384u
#define ML_MAX_PLAYERS (ML_MAX_CLUBS * 40u)
#define ML_SQUAD_SIZE 40u
#define ML_SAVE_SLOTS 3u
#define ML_NAME_SIZE 32u
#define ML_CONTENT_ID_SIZE 65u
#define ML_INVALID_INDEX UINT32_MAX

/* identity is BaseId, or the existing disjoint FL26 provenance namespace.
 * Native IDs are immutable engine storage keys, not ownership or identity. */
typedef struct {
  uint32_t identity, native_id, portrait_id, club;
  uint32_t wage, contract_end;
  uint8_t overall, position, shirt, reserved;
  char name[48];
} MlPlayer;

typedef struct {
  uint32_t team, count;
  uint32_t players[ML_SQUAD_SIZE]; /* indices into the canonical player array */
  int64_t cash;
  uint32_t wage_budget;
} MlClub;

typedef struct {
  uint32_t competition_id, club, difficulty, match_minutes;
  uint32_t condition, injuries, max_substitutions;
  uint32_t cup_id;
} MlSettings;

typedef struct {
  uint32_t seed, season, day, transaction_sequence;
  uint32_t club_count, player_count, target_rank, last_rank, seasons_completed;
  uint32_t wage_week, cup_enabled;
  int64_t wages_paid, match_income, prize_income;
  char content_id[ML_CONTENT_ID_SIZE];
  char manager_name[ML_NAME_SIZE];
  uint32_t manager_nationality;
  MlSettings settings;
  MlClub clubs[ML_MAX_CLUBS];
  MlPlayer players[ML_MAX_PLAYERS];
  LeagueTournament league;
  CupTournament cup;
  GameplanPreset current_plan;
  GameplanPreset presets[GAMEPLAN_PRESET_SLOTS];
} MasterLeague;

typedef enum { ML_EVENT_LEAGUE = 1, ML_EVENT_CUP, ML_EVENT_SEASON_END } MlEventKind;
typedef struct {
  uint32_t kind, day, index, round, home, away;
} MlEvent;

int ml_manager_name_valid(const char *name);
int ml_init(MasterLeague *career, const char *content_id, const MlSettings *settings,
            const char *manager, uint32_t nationality, uint32_t seed);
int ml_add_player(MasterLeague *career, uint32_t club, const MlPlayer *player);
int ml_start_season(MasterLeague *career, const uint32_t *teams, uint32_t count,
                    const uint32_t *cup_teams, uint32_t cup_count);
int ml_valid(const MasterLeague *career);
MlClub *ml_club(MasterLeague *career, uint32_t team);
const MlClub *ml_find_club(const MasterLeague *career, uint32_t team);
const MlPlayer *ml_find_native(const MasterLeague *career, uint32_t native_id);
uint32_t ml_weekly_wage(const MasterLeague *career, uint32_t club);
uint32_t ml_transfer_value(const MlPlayer *player);
int ml_window_open(const MasterLeague *career);
/* Returns an explanatory message; empty means success. No partial writes. */
const char *ml_transfer(MasterLeague *career, uint32_t player_index,
                        uint32_t destination, uint32_t years);
const char *ml_renew(MasterLeague *career, uint32_t player_index, uint32_t years);
int ml_swap(MasterLeague *career, uint32_t team, uint32_t first, uint32_t second);
int ml_next_event(const MasterLeague *career, MlEvent *event);
int ml_advance_date(MasterLeague *career, const MlEvent *event);
int ml_record_event(MasterLeague *career, const MlEvent *event,
                     uint32_t home_goals, uint32_t away_goals,
                     const LeagueScorer *scorers, uint32_t scorer_count,
                     int simulated);
/* A played cup draw requires the actual shootout winner, never a random pick. */
int ml_record_event_decided(MasterLeague *career, const MlEvent *event,
                     uint32_t home_goals, uint32_t away_goals,
                     const LeagueScorer *scorers, uint32_t scorer_count,
                     int simulated, uint32_t shootout_winner);
int ml_simulate_event(MasterLeague *career, const MlEvent *event);
int ml_next_season(MasterLeague *career);
uint32_t ml_rank(const MasterLeague *career);
int ml_plan_compatible(const MasterLeague *career, const GameplanPreset *plan);
int ml_store_plan(MasterLeague *career, const GameplanPreset *plan);
int ml_save_read(uint32_t slot, const char *content_id, MasterLeague *out);
int ml_save_write(uint32_t slot, const MasterLeague *career);

#endif

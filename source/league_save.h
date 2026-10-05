#ifndef PES21_LEAGUE_SAVE_H
#define PES21_LEAGUE_SAVE_H

#include <stdint.h>

#include "competition_entry_draft.h"
#include "league_tournament.h"

#define LEAGUE_SAVE_SLOTS 3u

typedef struct {
  uint32_t player_count, team_count, com_level, home_away;
  uint32_t game_time, extra_time, max_substitutions;
  uint32_t injuries, ball_index, var_enabled;
  uint32_t tournament_valid;
  CompetitionEntryDraft draft;
  LeagueTournament tournament;
  /* Appended in v3 so v1/v2 save payloads retain their original layout. */
  uint32_t league_competition_id, league_system;
  /* v4 append: 5 = random, 2 = normal. */
  uint32_t player_condition;
} LeagueSaveState;

int league_save_read(uint32_t slot, LeagueSaveState *state);
int league_save_write(uint32_t slot, const LeagueSaveState *state);

#endif

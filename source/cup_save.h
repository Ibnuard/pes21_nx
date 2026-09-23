#ifndef PES21_CUP_SAVE_H
#define PES21_CUP_SAVE_H

#include <stdint.h>

#include "competition_entry_draft.h"
#include "cup_tournament.h"

#define CUP_SAVE_SLOTS 3u

typedef struct {
  uint32_t cup_select;
  uint32_t player_count;
  uint32_t team_count;
  uint32_t com_level;
  uint32_t home_away;
  uint32_t third_place;
  uint32_t game_time;
  uint32_t extra_time;
  uint32_t max_substitutions;
  uint32_t injuries;
  uint32_t ball_index;
  uint32_t var_enabled;
  uint32_t tournament_valid;
  uint32_t first_match_started;
  CompetitionEntryDraft draft;
  CupTournament tournament;
} CupSaveState;

/* Each slot has two alternating checksummed copies. An interrupted write
 * leaves the previously valid copy loadable. */
int cup_save_read(uint32_t slot, CupSaveState *state);
int cup_save_write(uint32_t slot, const CupSaveState *state);

#endif

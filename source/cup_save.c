#include "cup_save.h"

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#ifdef _WIN32
#include <direct.h>
#endif

#define CUP_SAVE_MAGIC 0x32584346u /* FCX2 */
#define CUP_SAVE_VERSION 3u
#define CUP_SAVE_LEGACY_VERSION 2u

typedef struct {
  uint32_t magic, version, payload_size, sequence, checksum;
} CupSaveHeader;

/* The exact v1 layout remains readable after adding two-leg ties and bronze. */
typedef struct {
  uint32_t home, away, winner;
  uint8_t home_goals, away_goals, complete, simulated;
} CupFixtureV1;
typedef struct {
  CupFixtureV1 fixtures[CUP_MAX_ROUNDS][CUP_MAX_TEAMS / 2u];
  uint8_t history_round[31], history_index[31];
  uint32_t seed, team_count, bracket_size, round_count, active_round;
  uint32_t human_count, human_teams[8], history_count, champion;
} CupTournamentV1;
typedef struct {
  uint32_t cup_select, player_count, team_count, com_level, match_mode;
  uint32_t game_time, extra_time, max_substitutions;
  uint32_t tournament_valid, first_match_started;
  CompetitionEntryDraft draft;
  CupTournamentV1 tournament;
} CupSaveStateV1;
typedef struct {
  uint32_t sequence;
  CupSaveState state;
} CupSaveCopy;

static void cup_save_path(uint32_t slot, uint32_t copy, char path[64]) {
  snprintf(path, 64, "SaveData/footballnx_cup_%u_%c.bin",
           slot + 1u, copy ? 'b' : 'a');
}

static uint32_t cup_save_checksum(const void *payload, size_t size) {
  const uint8_t *bytes = (const uint8_t *)payload;
  uint32_t hash = 2166136261u;
  for (size_t i = 0; i < size; i++) {
    hash ^= bytes[i];
    hash *= 16777619u;
  }
  return hash;
}

/* v2's expanded selector stored custom, FA, Italia, Del Rey, then Cups
 * removed from the visible catalog; v1 used only its first entries. Keep old brackets playable by
 * interpreting a removed preset as unrestricted FootballNX Cup. */
static uint32_t cup_save_migrate_selector(uint32_t old_index) {
  switch (old_index) {
    case 1u: return 0u; /* FA Cup */
    case 3u: return 1u; /* Copa del Rey */
    case 2u: return 2u; /* Coppa Italia */
    default: return 6u; /* FootballNX or retired preset */
  }
}

static void cup_save_migrate_v1(CupSaveState *state,
                                 const CupSaveStateV1 *old) {
  memset(state, 0, sizeof(*state));
  state->cup_select = cup_save_migrate_selector(old->cup_select);
  state->player_count = old->player_count;
  state->team_count = old->team_count;
  state->com_level = old->com_level;
  /* v1 exposed Home Away (mode 0) but played one-leg fixtures. Preserve the
   * selection only for an untouched bracket; never reinterpret past scores. */
  state->home_away = old->match_mode == 0u &&
                     !old->first_match_started &&
                     !old->tournament.history_count &&
                     !old->tournament.active_round;
  state->game_time = old->game_time;
  state->extra_time = old->extra_time;
  state->max_substitutions = old->max_substitutions;
  state->injuries = 1u;
  state->var_enabled = 1u;
  state->tournament_valid = old->tournament_valid;
  state->first_match_started = old->first_match_started;
  state->draft = old->draft;
  CupTournament *cup = &state->tournament;
  const CupTournamentV1 *previous = &old->tournament;
  for (uint32_t round = 0; round < CUP_MAX_ROUNDS; round++) {
    for (uint32_t index = 0; index < CUP_MAX_TEAMS / 2u; index++) {
      const CupFixtureV1 *src = &previous->fixtures[round][index];
      CupFixture *dst = &cup->fixtures[round][index];
      dst->home = src->home;
      dst->away = src->away;
      dst->winner = src->winner;
      dst->home_goals = src->home_goals;
      dst->away_goals = src->away_goals;
      dst->complete = src->complete;
      dst->simulated = src->simulated;
    }
  }
  memcpy(cup->history_round, previous->history_round, 31u);
  memcpy(cup->history_index, previous->history_index, 31u);
  cup->seed = previous->seed;
  cup->team_count = previous->team_count;
  cup->bracket_size = previous->bracket_size;
  cup->round_count = previous->round_count;
  cup->active_round = previous->active_round;
  cup->human_count = previous->human_count;
  memcpy(cup->human_teams, previous->human_teams,
         sizeof(cup->human_teams));
  cup->history_count = previous->history_count;
  cup->champion = previous->champion;
  cup->home_away = state->home_away;
}

static int cup_save_read_copy(uint32_t slot, uint32_t copy,
                              CupSaveCopy *out) {
  char path[64];
  cup_save_path(slot, copy, path);
  FILE *stream = fopen(path, "rb");
  if (!stream) return 0;
  CupSaveHeader header;
  const int has_header = fread(&header, 1, sizeof(header), stream) ==
                         sizeof(header);
  if (!has_header || header.magic != CUP_SAVE_MAGIC ||
      !(((header.version == CUP_SAVE_VERSION ||
          header.version == CUP_SAVE_LEGACY_VERSION) &&
         header.payload_size == sizeof(CupSaveState)) ||
        (header.version == 1u &&
         header.payload_size == sizeof(CupSaveStateV1)))) {
    fclose(stream);
    return 0;
  }
  union {
    CupSaveState current;
    CupSaveStateV1 old;
  } payload;
  memset(&payload, 0, sizeof(payload));
  const int read = fread(&payload, 1, header.payload_size, stream) ==
                   header.payload_size;
  const int end = fgetc(stream) == EOF;
  const int closed = fclose(stream) == 0;
  if (!read || !end || !closed ||
      header.checksum != cup_save_checksum(&payload, header.payload_size))
    return 0;
  out->sequence = header.sequence;
  if (header.version == 1u)
    cup_save_migrate_v1(&out->state, &payload.old);
  else {
    out->state = payload.current;
    if (header.version == CUP_SAVE_LEGACY_VERSION)
      out->state.cup_select =
          cup_save_migrate_selector(out->state.cup_select);
  }
  return 1;
}

int cup_save_read(uint32_t slot, CupSaveState *state) {
  if (slot >= CUP_SAVE_SLOTS || !state) return 0;
  CupSaveCopy first, second;
  const int a = cup_save_read_copy(slot, 0u, &first);
  const int b = cup_save_read_copy(slot, 1u, &second);
  if (!a && !b) return 0;
  *state = !a ? second.state : !b || first.sequence >= second.sequence
               ? first.state : second.state;
  return 1;
}

int cup_save_write(uint32_t slot, const CupSaveState *state) {
  if (slot >= CUP_SAVE_SLOTS || !state) return 0;
#ifdef _WIN32
  if (_mkdir("SaveData") != 0 && errno != EEXIST) return 0;
#else
  if (mkdir("SaveData", 0777) != 0 && errno != EEXIST) return 0;
#endif
  CupSaveCopy first, second;
  const int a = cup_save_read_copy(slot, 0u, &first);
  const int b = cup_save_read_copy(slot, 1u, &second);
  const uint32_t latest = a && (!b || first.sequence >= second.sequence)
                              ? first.sequence : b ? second.sequence : 0u;
  const uint32_t target = !a ? 0u : !b ? 1u
                          : first.sequence <= second.sequence ? 0u : 1u;
  CupSaveHeader header = {CUP_SAVE_MAGIC, CUP_SAVE_VERSION,
                          sizeof(*state), latest + 1u,
                          cup_save_checksum(state, sizeof(*state))};
  char path[64];
  cup_save_path(slot, target, path);
  FILE *stream = fopen(path, "wb");
  if (!stream) return 0;
  const int written = fwrite(&header, 1, sizeof(header), stream) ==
                          sizeof(header) &&
                      fwrite(state, 1, sizeof(*state), stream) ==
                          sizeof(*state);
  const int flushed = fflush(stream) == 0;
  const int closed = fclose(stream) == 0;
  CupSaveCopy verify;
  return written && flushed && closed &&
         cup_save_read_copy(slot, target, &verify) &&
         verify.sequence == header.sequence;
}

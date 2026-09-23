#include "cup_tournament.h"

#include <string.h>

static int cup_is_human(const CupTournament *cup, uint32_t team) {
  for (uint32_t i = 0; i < cup->human_count; i++)
    if (cup->human_teams[i] == team)
      return 1;
  return 0;
}

uint32_t cup_tournament_fixture_count(const CupTournament *cup,
                                      uint32_t round) {
  return cup && round < cup->round_count
             ? cup->bracket_size >> (round + 1u) : 0u;
}

const CupFixture *cup_tournament_fixture(const CupTournament *cup,
                                         uint32_t round, uint32_t index) {
  if (cup && cup->third_place_enabled && cup->team_count >= 4u &&
      round + 1u == cup->round_count && index == CUP_THIRD_PLACE_INDEX)
    return &cup->fixtures[round][CUP_THIRD_PLACE_INDEX];
  return index < cup_tournament_fixture_count(cup, round)
             ? &cup->fixtures[round][index] : NULL;
}

const CupFixture *cup_tournament_third_place_fixture(
    const CupTournament *cup) {
  return cup && cup->round_count
      ? cup_tournament_fixture(cup, cup->round_count - 1u,
                               CUP_THIRD_PLACE_INDEX) : NULL;
}

void cup_tournament_set_rules(CupTournament *cup, int home_away,
                              int third_place) {
  if (!cup || cup->active_round || cup->history_count) return;
  cup->home_away = home_away != 0;
  cup->third_place_enabled = third_place != 0 && cup->team_count >= 4u;
}

static int cup_has_second_leg(const CupTournament *cup, uint32_t round,
                              uint32_t index) {
  /* The final and bronze match remain single-game deciders. */
  return cup->home_away && round + 1u < cup->round_count &&
         index < cup_tournament_fixture_count(cup, round);
}

static void cup_complete(CupTournament *cup, uint32_t round, uint32_t index,
                         uint32_t home_goals, uint32_t away_goals,
                         int simulated) {
  CupFixture *fixture = &cup->fixtures[round][index];
  fixture->home_goals = (uint8_t)(home_goals > 99u ? 99u : home_goals);
  fixture->away_goals = (uint8_t)(away_goals > 99u ? 99u : away_goals);
  fixture->winner = home_goals > away_goals ? fixture->home
                    : away_goals > home_goals ? fixture->away
                    : ((cup->seed ^ fixture->home ^ fixture->away ^
                        (round << 8) ^ index) & 1u) ? fixture->home
                                                     : fixture->away;
  fixture->complete = 1;
  fixture->simulated = simulated != 0;
  if (cup->history_count < CUP_MAX_FIXTURES) {
    cup->history_round[cup->history_count] = (uint8_t)round;
    cup->history_index[cup->history_count] = (uint8_t)index;
    cup->history_count++;
  }
}

int cup_tournament_init(CupTournament *cup, const uint32_t *participants,
                        uint32_t team_count, const uint32_t *human_teams,
                        uint32_t human_count, uint32_t seed) {
  if (!cup || !participants || !human_teams || team_count < 3u ||
      team_count > CUP_MAX_TEAMS || human_count > 8u || !human_count)
    return 0;
  memset(cup, 0, sizeof(*cup));
  cup->seed = seed ? seed : 1u;
  cup->team_count = team_count;
  cup->human_count = human_count;
  memcpy(cup->human_teams, human_teams,
         human_count * sizeof(cup->human_teams[0]));
  cup->bracket_size = 4u;
  while (cup->bracket_size < team_count)
    cup->bracket_size <<= 1u;
  for (uint32_t n = cup->bracket_size; n > 1u; n >>= 1u)
    cup->round_count++;

  /* Put one entrant in every opening fixture, then distribute the rest.
   * This creates real byes without ever pairing two empty seed slots. */
  const uint32_t opening = cup->bracket_size / 2u;
  for (uint32_t i = 0; i < team_count; i++) {
    CupFixture *fixture = &cup->fixtures[0][i % opening];
    if (i < opening)
      fixture->home = participants[i];
    else
      fixture->away = participants[i];
  }
  for (uint32_t i = 0; i < opening; i++) {
    CupFixture *fixture = &cup->fixtures[0][i];
    if (!fixture->away) {
      fixture->winner = fixture->home;
      fixture->complete = 1;
      /* A bye is visible in the opening stage only. The next stage stays
       * completely unresolved until this round is advanced after play. */
    }
  }
  return 1;
}

int cup_tournament_next_human(const CupTournament *cup, uint32_t *round,
                              uint32_t *index) {
  if (!cup || cup->champion)
    return 0;
  for (uint32_t r = cup->active_round; r < cup->round_count; r++) {
    if (r + 1u == cup->round_count) {
      const CupFixture *bronze = cup_tournament_third_place_fixture(cup);
      if (bronze && !bronze->complete && bronze->home && bronze->away &&
          (cup_is_human(cup, bronze->home) ||
           cup_is_human(cup, bronze->away))) {
        if (round) *round = r;
        if (index) *index = CUP_THIRD_PLACE_INDEX;
        return 1;
      }
    }
    const uint32_t count = cup_tournament_fixture_count(cup, r);
    for (uint32_t i = 0; i < count; i++) {
      const CupFixture *fixture = &cup->fixtures[r][i];
      if (!fixture->complete && fixture->home && fixture->away &&
          (cup_is_human(cup, fixture->home) ||
           cup_is_human(cup, fixture->away))) {
        if (round) *round = r;
        if (index) *index = i;
        return 1;
      }
    }
    /* The next round is not ready until this round is complete. */
    break;
  }
  return 0;
}

int cup_tournament_record(CupTournament *cup, uint32_t round, uint32_t index,
                          uint32_t home_goals, uint32_t away_goals) {
  if (!cup || round != cup->active_round)
    return 0;
  const CupFixture *target = cup_tournament_fixture(cup, round, index);
  if (!target) return 0;
  CupFixture *fixture = &cup->fixtures[round][index];
  if (fixture->complete || !fixture->home || !fixture->away)
    return 0;
  if (cup_has_second_leg(cup, round, index)) {
    if (!fixture->first_leg_complete) {
      fixture->first_leg_home_goals = (uint8_t)(home_goals > 99u ? 99u : home_goals);
      fixture->first_leg_away_goals = (uint8_t)(away_goals > 99u ? 99u : away_goals);
      fixture->first_leg_complete = 1u;
      return 1;
    }
    home_goals += fixture->first_leg_home_goals;
    away_goals += fixture->first_leg_away_goals;
  }
  cup_complete(cup, round, index, home_goals, away_goals, 0);
  cup_tournament_advance(cup);
  return 1;
}

void cup_tournament_advance(CupTournament *cup) {
  if (!cup || cup->champion)
    return;
  while (cup->active_round < cup->round_count) {
    const uint32_t round = cup->active_round;
    const uint32_t count = cup_tournament_fixture_count(cup, round);
    uint32_t human_pending = 0;
    for (uint32_t i = 0; i < count; i++) {
      const CupFixture *fixture = &cup->fixtures[round][i];
      if (!fixture->complete &&
          (cup_is_human(cup, fixture->home) ||
           cup_is_human(cup, fixture->away)))
        human_pending++;
    }
    if (round + 1u == cup->round_count) {
      const CupFixture *bronze = cup_tournament_third_place_fixture(cup);
      if (bronze && !bronze->complete && bronze->home && bronze->away &&
          (cup_is_human(cup, bronze->home) ||
           cup_is_human(cup, bronze->away)))
        human_pending++;
    }
    if (human_pending)
      return;
    for (uint32_t i = 0; i < count; i++) {
      CupFixture *fixture = &cup->fixtures[round][i];
      if (fixture->complete)
        continue;
      /* Deterministic COM simulation runs only after every playable human
       * fixture in this round, or when all human entrants have a bye. */
      const uint32_t roll = cup->seed ^ fixture->home * 1664525u ^
                            fixture->away * 1013904223u ^
                            (round * 97u + i * 31u);
      uint32_t home_goals = (roll >> 5) % 4u;
      uint32_t away_goals = (roll >> 13) % 4u;
      if (cup_has_second_leg(cup, round, i)) {
        if (!fixture->first_leg_complete) {
          fixture->first_leg_home_goals = (uint8_t)home_goals;
          fixture->first_leg_away_goals = (uint8_t)away_goals;
          fixture->first_leg_complete = 1u;
        }
        home_goals = fixture->first_leg_home_goals + ((roll >> 17) % 4u);
        away_goals = fixture->first_leg_away_goals + ((roll >> 23) % 4u);
      }
      cup_complete(cup, round, i, home_goals, away_goals, 1);
    }
    if (round + 1u >= cup->round_count) {
      CupFixture *bronze = &cup->fixtures[round][CUP_THIRD_PLACE_INDEX];
      if (cup->third_place_enabled && bronze->home && bronze->away) {
        if (!bronze->complete) {
          const uint32_t roll = cup->seed ^ bronze->home * 2246822519u ^
                                bronze->away * 3266489917u;
          cup_complete(cup, round, CUP_THIRD_PLACE_INDEX,
                       (roll >> 6) % 4u, (roll >> 14) % 4u, 1);
        }
        cup->third_place = bronze->winner;
      }
      cup->champion = cup->fixtures[round][0].winner;
      return;
    }
    const uint32_t next_count = cup_tournament_fixture_count(cup, round + 1u);
    for (uint32_t i = 0; i < next_count; i++) {
      CupFixture *next = &cup->fixtures[round + 1u][i];
      next->home = cup->fixtures[round][i * 2u].winner;
      next->away = cup->fixtures[round][i * 2u + 1u].winner;
    }
    if (round + 2u == cup->round_count && cup->third_place_enabled) {
      CupFixture *bronze = &cup->fixtures[round + 1u][CUP_THIRD_PLACE_INDEX];
      const CupFixture *semi_home = &cup->fixtures[round][0];
      const CupFixture *semi_away = &cup->fixtures[round][1];
      bronze->home = semi_home->winner == semi_home->home
                         ? semi_home->away : semi_home->home;
      bronze->away = semi_away->winner == semi_away->home
                         ? semi_away->away : semi_away->home;
    }
    cup->active_round++;
  }
}

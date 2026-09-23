#ifndef PES21_CUP_TOURNAMENT_H
#define PES21_CUP_TOURNAMENT_H

#include <stdint.h>

#define CUP_MAX_TEAMS 32u
#define CUP_MAX_ROUNDS 5u
#define CUP_MAX_FIXTURES 32u
#define CUP_THIRD_PLACE_INDEX 1u

typedef struct {
  uint32_t home;
  uint32_t away;
  uint32_t winner;
  uint8_t home_goals;
  uint8_t away_goals;
  uint8_t complete;
  uint8_t simulated;
  uint8_t first_leg_home_goals;
  uint8_t first_leg_away_goals;
  uint8_t first_leg_complete;
  uint8_t reserved;
} CupFixture;

typedef struct {
  CupFixture fixtures[CUP_MAX_ROUNDS][CUP_MAX_TEAMS / 2u];
  uint8_t history_round[CUP_MAX_FIXTURES];
  uint8_t history_index[CUP_MAX_FIXTURES];
  uint32_t seed;
  uint32_t team_count;
  uint32_t bracket_size;
  uint32_t round_count;
  uint32_t active_round;
  uint32_t human_count;
  uint32_t human_teams[8];
  uint32_t history_count;
  uint32_t champion;
  uint32_t third_place;
  uint32_t home_away;
  uint32_t third_place_enabled;
} CupTournament;

int cup_tournament_init(CupTournament *cup, const uint32_t *participants,
                        uint32_t team_count, const uint32_t *human_teams,
                        uint32_t human_count, uint32_t seed);
const CupFixture *cup_tournament_fixture(const CupTournament *cup,
                                         uint32_t round, uint32_t index);
uint32_t cup_tournament_fixture_count(const CupTournament *cup,
                                      uint32_t round);
int cup_tournament_next_human(const CupTournament *cup, uint32_t *round,
                              uint32_t *index);
int cup_tournament_record(CupTournament *cup, uint32_t round, uint32_t index,
                          uint32_t home_goals, uint32_t away_goals);
void cup_tournament_advance(CupTournament *cup);
const CupFixture *cup_tournament_third_place_fixture(
    const CupTournament *cup);
void cup_tournament_set_rules(CupTournament *cup, int home_away,
                              int third_place);

#endif

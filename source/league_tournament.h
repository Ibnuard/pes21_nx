#ifndef PES21_LEAGUE_TOURNAMENT_H
#define PES21_LEAGUE_TOURNAMENT_H

#include <stdint.h>

#include "cup_tournament.h"

#define LEAGUE_MAX_TEAMS 32u
#define LEAGUE_MAX_MATCHDAYS 62u
#define LEAGUE_MAX_FIXTURES 992u
#define LEAGUE_MAX_SCORERS 768u

typedef enum {
  LEAGUE_PHASE_TABLE = 0,
  LEAGUE_PHASE_KNOCKOUT = 1,
  LEAGUE_PHASE_COMPLETE = 2,
} LeaguePhase;

typedef struct {
  uint32_t home, away;
  uint8_t home_goals, away_goals, complete, simulated;
} LeagueFixture;

typedef struct {
  uint32_t team;
  uint16_t played, wins, draws, losses;
  uint16_t goals_for, goals_against, points;
} LeagueStanding;

typedef struct {
  uint32_t base_id, portrait_id, team;
  uint16_t goals;
  char name[48];
} LeagueScorer;

typedef struct {
  uint32_t seed, team_count, human_count, home_away;
  uint32_t human_teams[8];
  uint32_t matchday_count, active_matchday, fixture_count;
  uint32_t matchday_first[LEAGUE_MAX_MATCHDAYS];
  uint8_t matchday_fixture_count[LEAGUE_MAX_MATCHDAYS];
  LeagueFixture fixtures[LEAGUE_MAX_FIXTURES];
  LeagueStanding standings[LEAGUE_MAX_TEAMS];
  uint8_t phase;
  uint8_t first_match_started;
  uint8_t reserved[2];
  CupTournament knockout;
  uint32_t scorer_count;
  LeagueScorer scorers[LEAGUE_MAX_SCORERS];
} LeagueTournament;

uint32_t league_tournament_qualifier_count(uint32_t team_count);
int league_tournament_init(LeagueTournament *league,
                           const uint32_t *teams, uint32_t team_count,
                           const uint32_t *human_teams, uint32_t human_count,
                           int home_away, uint32_t seed);
const LeagueFixture *league_tournament_matchday_fixture(
    const LeagueTournament *league, uint32_t matchday, uint32_t offset);
int league_tournament_next_human(const LeagueTournament *league,
                                  uint32_t *fixture_index,
                                  uint32_t *knockout_round,
                                  uint32_t *knockout_index);
int league_tournament_record(LeagueTournament *league,
                              uint32_t fixture_index,
                              uint32_t knockout_round,
                              uint32_t knockout_index,
                              uint32_t home_goals, uint32_t away_goals);
void league_tournament_advance(LeagueTournament *league);
/* Returns team slots in standing order, up to team_count. */
void league_tournament_ranked_slots(const LeagueTournament *league,
                                     uint8_t slots[LEAGUE_MAX_TEAMS]);
int league_tournament_credit_goals(LeagueTournament *league,
                                    uint32_t team, uint32_t base_id,
                                    uint32_t portrait_id, const char *name,
                                    uint32_t goals);
uint32_t league_tournament_top_scorers(const LeagueTournament *league,
                                        uint16_t slots[4]);
uint32_t league_tournament_base_id_for_portrait(uint32_t portrait_id);

#endif

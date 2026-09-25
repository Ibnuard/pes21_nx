#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "league_tournament.h"

static LeagueTournament league;

static void check_schedule(uint32_t count, int home_away) {
  uint32_t teams[LEAGUE_MAX_TEAMS];
  uint32_t opponents[LEAGUE_MAX_TEAMS][LEAGUE_MAX_TEAMS] = {{0}};
  uint32_t home_counts[LEAGUE_MAX_TEAMS][LEAGUE_MAX_TEAMS] = {{0}};
  for (uint32_t i = 0; i < count; i++) teams[i] = 100u + i;
  assert(league_tournament_init(&league, teams, count, teams, 1u,
                                 home_away, 0x1234u));
  const uint32_t days = ((count + 1u) & ~1u) - 1u;
  assert(league.matchday_count == days * (home_away ? 2u : 1u));
  assert(league.fixture_count == count * (count - 1u) / 2u *
                                  (home_away ? 2u : 1u));
  for (uint32_t day = 0; day < league.matchday_count; day++) {
    uint8_t seen[LEAGUE_MAX_TEAMS] = {0};
    for (uint32_t i = 0; i < league.matchday_fixture_count[day]; i++) {
      const LeagueFixture *fixture =
          league_tournament_matchday_fixture(&league, day, i);
      assert(fixture);
      const uint32_t home = fixture->home - 100u;
      const uint32_t away = fixture->away - 100u;
      assert(home < count && away < count && home != away);
      assert(!seen[home] && !seen[away]);
      seen[home] = seen[away] = 1u;
      opponents[home][away]++;
      home_counts[home][away]++;
    }
  }
  for (uint32_t home = 0; home < count; home++)
    for (uint32_t away = 0; away < count; away++)
      if (home != away) {
        assert(opponents[home][away] + opponents[away][home] ==
               (home_away ? 2u : 1u));
        if (home_away) assert(home_counts[home][away] == 1u);
      }
}

static void check_full_progression(void) {
  const uint32_t teams[4] = {101u, 102u, 103u, 104u};
  assert(league_tournament_init(&league, teams, 4u, teams, 1u, 0, 7u));
  for (uint32_t attempts = 0; attempts < 8u; attempts++) {
    uint32_t fixture = UINT32_MAX, round = UINT32_MAX, index = UINT32_MAX;
    if (league.phase != LEAGUE_PHASE_TABLE) break;
    league_tournament_advance(&league);
    if (league.phase != LEAGUE_PHASE_TABLE) break;
    assert(league_tournament_next_human(&league, &fixture, &round, &index));
    assert(fixture < league.fixture_count);
    assert(league_tournament_record(&league, fixture, 0u, 0u,
        league.fixtures[fixture].home == 101u ? 2u : 0u,
        league.fixtures[fixture].away == 101u ? 2u : 0u));
  }
  assert(league.phase == LEAGUE_PHASE_KNOCKOUT);
  assert(league.standings[0].played == 3u);
  assert(league.standings[0].points == 9u);
  uint8_t ranked[LEAGUE_MAX_TEAMS] = {0};
  league_tournament_ranked_slots(&league, ranked);
  assert(ranked[0] == 0u);
  assert(league.knockout.team_count == 4u);
  for (uint32_t attempts = 0; attempts < 4u; attempts++) {
    uint32_t fixture = 0, round = 0, index = 0;
    if (league.phase == LEAGUE_PHASE_COMPLETE) break;
    assert(league_tournament_next_human(&league, &fixture, &round, &index));
    const CupFixture *match = cup_tournament_fixture(&league.knockout,
                                                       round, index);
    assert(match);
    assert(league_tournament_record(&league, fixture, round, index,
        match->home == 101u ? 1u : 0u,
        match->away == 101u ? 1u : 0u));
  }
  assert(league.phase == LEAGUE_PHASE_COMPLETE);
  assert(league.knockout.champion == 101u);
}

static void check_knockout_seeding(void) {
  const uint32_t teams[8] = {101u, 102u, 103u, 104u,
                              105u, 106u, 107u, 108u};
  assert(league_tournament_init(&league, teams, 8u, teams, 1u, 0, 13u));
  for (uint32_t i = 0; i < 8u; i++)
    league.standings[i].points = (uint16_t)(8u - i);
  league.active_matchday = league.matchday_count;
  league_tournament_advance(&league);
  assert(league.phase == LEAGUE_PHASE_KNOCKOUT);
  static const uint32_t seeded[8] = {101u, 108u, 104u, 105u,
                                      102u, 107u, 103u, 106u};
  for (uint32_t i = 0; i < 4u; i++) {
    const CupFixture *fixture = cup_tournament_fixture(&league.knockout,
                                                        0u, i);
    assert(fixture);
    assert(fixture->home == seeded[2u * i]);
    assert(fixture->away == seeded[2u * i + 1u]);
  }
}

static void check_simulated_opening_locks_teams(void) {
  const uint32_t teams[3] = {101u, 102u, 103u};
  assert(league_tournament_init(&league, teams, 3u, teams, 1u, 0, 17u));
  assert(!league.first_match_started);
  /* Team 101 has the opening bye; the 102-vs-103 COM match still starts
   * the season and must make team assignments immutable. */
  league_tournament_advance(&league);
  assert(league.fixtures[0].complete);
  assert(league.fixtures[0].simulated);
  assert(league.first_match_started);
  uint32_t credited = 0u;
  for (uint32_t i = 0; i < league.scorer_count; i++) {
    assert(league.scorers[i].base_id);
    assert(league.scorers[i].name[0]);
    credited += league.scorers[i].goals;
  }
  assert(credited == league.fixtures[0].home_goals +
                     league.fixtures[0].away_goals);
  assert(credited > 0u);
  uint16_t top[4] = {0};
  const uint32_t top_count = league_tournament_top_scorers(&league, top);
  assert(top_count > 0u && top_count <= 4u);
  for (uint32_t i = 1; i < top_count; i++)
    assert(league.scorers[top[i - 1u]].goals >=
           league.scorers[top[i]].goals);
  assert(league_tournament_base_id_for_portrait(541062u) == 4039u);
}

static void check_simulated_knockout_scorers(void) {
  const uint32_t teams[4] = {101u, 102u, 103u, 104u};
  const uint32_t no_human = UINT32_MAX;
  assert(league_tournament_init(&league, teams, 4u, teams, 1u, 0, 23u));
  assert(cup_tournament_init(&league.knockout, teams, 4u,
                             &no_human, 1u, 23u));
  league.phase = LEAGUE_PHASE_KNOCKOUT;
  league_tournament_advance(&league);
  assert(league.phase == LEAGUE_PHASE_COMPLETE);
  uint32_t simulated_goals = 0u, credited = 0u;
  for (uint32_t i = 0; i < league.knockout.history_count; i++) {
    const CupFixture *fixture = cup_tournament_fixture(&league.knockout,
        league.knockout.history_round[i], league.knockout.history_index[i]);
    assert(fixture && fixture->simulated);
    simulated_goals += fixture->home_goals + fixture->away_goals;
  }
  for (uint32_t i = 0; i < league.scorer_count; i++)
    credited += league.scorers[i].goals;
  assert(simulated_goals == credited);
}

int main(void) {
  for (uint32_t teams = 2u; teams <= 32u; teams++) {
    check_schedule(teams, 0);
    check_schedule(teams, 1);
  }
  assert(league_tournament_qualifier_count(2u) == 2u);
  assert(league_tournament_qualifier_count(3u) == 2u);
  assert(league_tournament_qualifier_count(4u) == 4u);
  assert(league_tournament_qualifier_count(7u) == 4u);
  assert(league_tournament_qualifier_count(8u) == 8u);
  check_full_progression();
  check_knockout_seeding();
  check_simulated_opening_locks_teams();
  check_simulated_knockout_scorers();
  puts("league tournament tests passed");
  return 0;
}

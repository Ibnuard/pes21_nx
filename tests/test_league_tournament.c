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
    if (day == 0u) assert(seen[0]); /* P1 never opens on a bye. */
  }
  for (uint32_t home = 0; home < count; home++)
    for (uint32_t away = 0; away < count; away++)
      if (home != away) {
        assert(opponents[home][away] + opponents[away][home] ==
               (home_away ? 2u : 1u));
        if (home_away) assert(home_counts[home][away] == 1u);
      }
}

static void check_all_opening_players(void) {
  uint32_t teams[LEAGUE_MAX_TEAMS], humans[8];
  for (uint32_t i = 0; i < LEAGUE_MAX_TEAMS; i++) teams[i] = 100u + i;
  for (uint32_t count = 2u; count <= LEAGUE_MAX_TEAMS; count++) {
    for (uint32_t players = 1u; players <= 8u && players <= count; players++) {
      for (uint32_t offset = 0u; offset < count; offset++) {
        for (uint32_t i = 0; i < players; i++) humans[i] = teams[(i + offset) % count];
        const int possible = !(count & 1u) || players < count;
        assert(league_tournament_init(&league, teams, count, humans, players,
                                       0, 1u) == possible);
        if (!possible) continue;
        for (uint32_t p = 0; p < players; p++) {
          uint32_t appearances = 0u;
          for (uint32_t f = 0; f < league.matchday_fixture_count[0]; f++)
            appearances += league.fixtures[f].home == humans[p] ||
                           league.fixtures[f].away == humans[p];
          assert(appearances == 1u);
        }
        for (uint32_t i = 0; i < count; i++) assert(league.standings[i].team == teams[i]);
        static LeagueTournament snapshot;
        snapshot = league;
        uint32_t day = UINT32_MAX, fixture = UINT32_MAX;
        assert(league_tournament_upcoming_human(&league, &fixture, &day, NULL, NULL));
        assert(day == 0u && fixture < league.matchday_fixture_count[0]);
        assert(!memcmp(&snapshot, &league, sizeof(league)));
      }
    }
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

static void check_standings_champion_without_knockout(void) {
  const uint32_t teams[4] = {101u, 102u, 103u, 104u};
  assert(league_tournament_init(&league, teams, 4u, teams, 1u, 0, 29u));
  league_tournament_set_system(&league, LEAGUE_SYSTEM_STANDINGS);
  assert(league.reserved[0] == LEAGUE_SYSTEM_STANDINGS);
  for (uint32_t i = 0; i < 4u; i++)
    league.standings[i].points = (uint16_t)(12u - i * 3u);
  league.active_matchday = league.matchday_count;
  league_tournament_advance(&league);
  assert(league.phase == LEAGUE_PHASE_COMPLETE);
  assert(league.knockout.champion == 101u);
  assert(league.knockout.round_count == 0u);
  assert(!league_tournament_next_human(&league, NULL, NULL, NULL));
}

static void check_knockout_seeding(void) {
  const uint32_t teams[8] = {101u, 102u, 103u, 104u,
                              105u, 106u, 107u, 108u};
  assert(league_tournament_init(&league, teams, 8u, teams, 1u, 1, 13u));
  for (uint32_t i = 0; i < 8u; i++)
    league.standings[i].points = (uint16_t)(8u - i);
  league.active_matchday = league.matchday_count;
  league_tournament_advance(&league);
  assert(league.phase == LEAGUE_PHASE_KNOCKOUT);
  assert(league.knockout.home_away);
  static const uint32_t seeded[8] = {101u, 108u, 104u, 105u,
                                      102u, 107u, 103u, 106u};
  for (uint32_t i = 0; i < 4u; i++) {
    const CupFixture *fixture = cup_tournament_fixture(&league.knockout,
                                                        0u, i);
    assert(fixture);
    assert(fixture->home == seeded[2u * i]);
    assert(fixture->away == seeded[2u * i + 1u]);
  }
  assert(league_tournament_record(&league, 0u, 0u, 0u, 3u, 1u));
  assert(league.knockout.fixtures[0][0].first_leg_complete);
  assert(!league.knockout.fixtures[0][0].complete);
  assert(league_tournament_record(&league, 0u, 0u, 0u, 1u, 1u));
  assert(league.knockout.fixtures[0][0].home_goals == 4u);
  assert(league.knockout.fixtures[0][0].away_goals == 2u);
  assert(league.knockout.fixtures[0][0].winner == seeded[0]);
}

static void check_simulated_opening_locks_teams(void) {
  const uint32_t teams[3] = {101u, 102u, 103u};
  assert(league_tournament_init(&league, teams, 3u, teams + 1u, 1u, 0, 17u));
  /* Reproduce a legacy saved schedule. New schedules cannot give P1 a bye,
   * but the core must still safely progress historical/later-day COM rounds. */
  league.human_teams[0] = teams[0];
  assert(!league.first_match_started);
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

static void check_rank_changes(uint32_t count) {
  uint32_t teams[LEAGUE_MAX_TEAMS];
  for (uint32_t i = 0; i < count; i++) teams[i] = 100u + count - i;
  assert(league_tournament_init(&league, teams, count, teams, 1u, 1, 37u));
  league_tournament_set_system(&league, LEAGUE_SYSTEM_STANDINGS);
  int8_t changes[LEAGUE_MAX_TEAMS];
  league_tournament_rank_changes(&league, changes);
  for (uint32_t i = 0; i < LEAGUE_MAX_TEAMS; i++) assert(!changes[i]);
  uint32_t rises = 0u, falls = 0u, unchanged = 0u;
  static LeagueTournament frozen;
  for (uint32_t day = 0; day < league.matchday_count; day++) {
    uint8_t before[LEAGUE_MAX_TEAMS], after[LEAGUE_MAX_TEAMS];
    league_tournament_ranked_slots(&league, before);
    for (uint32_t i = 0; i < league.matchday_fixture_count[day]; i++) {
      const uint32_t index = league.matchday_first[day] + i;
      /* Includes draws, partial multiplayer matchdays and odd-team byes. */
      assert(league_tournament_record_table_fixture(&league, index,
          (day + i) % 4u, (day * 2u + i) % 3u, i % 2u));
      frozen = league;
      league_tournament_rank_changes(&league, changes);
      assert(!memcmp(&frozen, &league, sizeof(league)));
      league_tournament_ranked_slots(&league, after);
      for (uint32_t rank = 0; rank < count; rank++) {
        uint32_t old = 0u;
        while (before[old] != after[rank]) old++;
        assert(changes[after[rank]] == (int)old - (int)rank);
        rises += changes[after[rank]] > 0;
        falls += changes[after[rank]] < 0;
        unchanged += changes[after[rank]] == 0;
      }
    }
    int8_t completed[LEAGUE_MAX_TEAMS];memcpy(completed,changes,sizeof(changes));
    assert(league_tournament_commit_matchday(&league));
    league_tournament_rank_changes(&league, changes);
    assert(!memcmp(changes, completed, sizeof(changes)));
  }
  assert(league.phase == LEAGUE_PHASE_COMPLETE && rises && falls && unchanged);
}

int main(void) {
  check_all_opening_players();
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
  check_standings_champion_without_knockout();
  check_knockout_seeding();
  check_simulated_opening_locks_teams();
  check_simulated_knockout_scorers();
  check_rank_changes(2u);
  check_rank_changes(3u);
  check_rank_changes(4u);
  check_rank_changes(32u);
  puts("league tournament tests passed");
  return 0;
}

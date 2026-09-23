#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "cup_tournament.h"

static void run_size(uint32_t teams) {
  uint32_t ids[CUP_MAX_TEAMS];
  for (uint32_t i = 0; i < teams; i++) ids[i] = 100u + i;
  CupTournament cup;
  assert(cup_tournament_init(&cup, ids, teams, ids, 1u, 0x261u));
  assert(cup.bracket_size >= teams);
  assert(cup_tournament_fixture_count(&cup, 0u) == cup.bracket_size / 2u);
  uint32_t played = 0;
  while (!cup.champion) {
    uint32_t round = 0, index = 0;
    assert(cup_tournament_next_human(&cup, &round, &index));
    const CupFixture *fixture = cup_tournament_fixture(&cup, round, index);
    assert(fixture && !fixture->complete);
    /* Keep the user-controlled entrant alive in this test. */
    const uint32_t home_goals = fixture->home == ids[0] ? 2u : 0u;
    const uint32_t away_goals = fixture->away == ids[0] ? 2u : 0u;
    assert(cup_tournament_record(&cup, round, index,
                                 home_goals, away_goals));
    assert(!cup_tournament_record(&cup, round, index, 9u, 0u));
    played++;
    assert(played <= CUP_MAX_ROUNDS);
  }
  assert(cup.champion == ids[0]);
  assert(cup.history_count <= CUP_MAX_FIXTURES);
  assert(!cup_tournament_next_human(&cup, NULL, NULL));
}

static void com_waits_for_player(void) {
  uint32_t ids[8];
  for (uint32_t i = 0; i < 8u; i++) ids[i] = 200u + i;
  CupTournament cup;
  assert(cup_tournament_init(&cup, ids, 8u, ids, 1u, 0x55u));
  assert(cup.history_count == 0u);
  assert(!cup.fixtures[0][1].complete);
  assert(cup_tournament_record(&cup, 0u, 0u, 2u, 0u));
  assert(cup.fixtures[0][1].complete);
  assert(cup.fixtures[0][1].simulated);
  assert(cup.history_count == 4u);
}

static void com_waits_for_all_human_fixtures(void) {
  uint32_t ids[8];
  for (uint32_t i = 0; i < 8u; i++) ids[i] = 300u + i;
  CupTournament cup;
  assert(cup_tournament_init(&cup, ids, 8u, ids, 2u, 0x56u));
  assert(cup_tournament_record(&cup, 0u, 0u, 2u, 0u));
  assert(!cup.fixtures[0][1].complete);
  assert(!cup.fixtures[0][2].complete);
  assert(cup_tournament_record(&cup, 0u, 1u, 2u, 0u));
  assert(cup.fixtures[0][2].complete && cup.fixtures[0][2].simulated);
  assert(cup.fixtures[0][3].complete && cup.fixtures[0][3].simulated);
}

static void future_final_is_unresolved_not_bye(void) {
  const uint32_t ids[3] = {400u, 401u, 402u};
  CupTournament cup;
  assert(cup_tournament_init(&cup, ids, 3u, ids, 1u, 0x57u));
  const CupFixture *future = cup_tournament_fixture(&cup, 1u, 0u);
  assert(future && !future->complete && !future->home && !future->away);
  assert(cup_tournament_record(&cup, 0u, 0u, 2u, 0u));
  future = cup_tournament_fixture(&cup, 1u, 0u);
  assert(future && !future->complete && future->home && future->away);
}

int main(void) {
  run_size(3u);
  run_size(7u);
  run_size(20u);
  run_size(32u);
  com_waits_for_player();
  com_waits_for_all_human_fixtures();
  future_final_is_unresolved_not_bye();
  puts("cup tournament tests passed");
  return 0;
}

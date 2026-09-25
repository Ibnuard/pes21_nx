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

static void two_team_final_has_no_bye_or_second_leg(void) {
  const uint32_t ids[2] = {710u, 711u};
  CupTournament cup;
  assert(cup_tournament_init(&cup, ids, 2u, ids, 1u, 0x60u));
  cup_tournament_set_rules(&cup, 1, 1);
  assert(cup.bracket_size == 2u && cup.round_count == 1u);
  assert(!cup.third_place_enabled);
  assert(cup_tournament_fixture_count(&cup, 0u) == 1u);
  assert(cup.fixtures[0][0].home == ids[0]);
  assert(cup.fixtures[0][0].away == ids[1]);
  assert(!cup.fixtures[0][0].complete);
  assert(cup_tournament_record(&cup, 0u, 0u, 2u, 0u));
  assert(cup.champion == ids[0]);
  assert(cup.history_count == 1u);
  assert(!cup.fixtures[0][0].first_leg_complete);
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
  uint32_t schedule_home = 0u, schedule_away = 0u;
  cup_tournament_schedule_teams(&cup, 1u, 0u,
                                &schedule_home, &schedule_away);
  assert(schedule_home == ids[1] && !schedule_away);
  assert(!future->home && !future->away); /* preview must not advance Final */
  assert(cup_tournament_record(&cup, 0u, 0u, 2u, 0u));
  future = cup_tournament_fixture(&cup, 1u, 0u);
  assert(future && !future->complete && future->home && future->away);
  cup_tournament_schedule_teams(&cup, 1u, 0u,
                                &schedule_home, &schedule_away);
  assert(schedule_home == ids[0] && schedule_away == ids[1]);
}

static void no_eager_com_simulation_for_human_bye(void) {
  const uint32_t ids[3] = {500u, 501u, 502u};
  CupTournament cup;
  assert(cup_tournament_init(&cup, ids, 3u, ids + 1u, 1u, 0x58u));
  assert(cup.history_count == 0u && !cup.fixtures[0][0].complete);
  const CupFixture *future = cup_tournament_fixture(&cup, 1u, 0u);
  assert(future && !future->home && !future->away);
  uint32_t round = 0, index = 0;
  assert(!cup_tournament_next_human(&cup, &round, &index));
  cup_tournament_advance(&cup); /* only after the user presses Next */
  assert(cup.history_count == 1u && cup.fixtures[0][0].simulated);
  assert(cup_tournament_next_human(&cup, &round, &index));
  assert(round == 1u && index == 0u);
}

static void home_away_and_bronze_before_final(void) {
  const uint32_t ids[4] = {600u, 601u, 602u, 603u};
  CupTournament cup;
  assert(cup_tournament_init(&cup, ids, 4u, ids, 1u, 0x59u));
  cup_tournament_set_rules(&cup, 1, 1);
  assert(cup.home_away && cup.third_place_enabled);
  assert(cup_tournament_record(&cup, 0u, 0u, 0u, 2u));
  assert(cup.fixtures[0][0].first_leg_complete);
  assert(!cup.fixtures[0][0].complete && cup.history_count == 0u);
  assert(!cup.fixtures[0][1].complete); /* COM waits for player's second leg. */
  uint32_t round = UINT32_MAX, index = UINT32_MAX;
  assert(cup_tournament_next_human(&cup, &round, &index));
  assert(round == 0u && index == 0u);
  assert(cup_tournament_record(&cup, 0u, 0u, 0u, 1u));
  assert(cup.fixtures[0][0].complete && cup.fixtures[0][1].simulated);
  assert(cup.active_round == 1u);
  const CupFixture *bronze = cup_tournament_third_place_fixture(&cup);
  assert(bronze && bronze->home == ids[0] && bronze->away);
  assert(cup_tournament_next_human(&cup, &round, &index));
  assert(round == 1u && index == CUP_THIRD_PLACE_INDEX);
  assert(!cup.champion); /* COM final waits until human bronze is played. */
  assert(cup_tournament_record(&cup, round, index, 2u, 0u));
  assert(cup.third_place == ids[0] && cup.champion);
  assert(cup.history_count == 4u);
  assert(cup.history_index[2] == CUP_THIRD_PLACE_INDEX);
}

int main(void) {
  run_size(2u);
  run_size(3u);
  run_size(7u);
  run_size(20u);
  run_size(32u);
  two_team_final_has_no_bye_or_second_leg();
  com_waits_for_player();
  com_waits_for_all_human_fixtures();
  future_final_is_unresolved_not_bye();
  no_eager_com_simulation_for_human_bye();
  home_away_and_bronze_before_final();
  puts("cup tournament tests passed");
  return 0;
}

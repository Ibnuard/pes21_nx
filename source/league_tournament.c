#include "league_tournament.h"

#include <string.h>

#include "league_scorer_pool_generated.inc"

static int league_is_human(const LeagueTournament *league, uint32_t team) {
  for (uint32_t i = 0; i < league->human_count; i++)
    if (league->human_teams[i] == team) return 1;
  return 0;
}

uint32_t league_tournament_qualifier_count(uint32_t team_count) {
  if (team_count < 2u) return 0u;
  if (team_count < 4u) return 2u;
  if (team_count < 8u) return 4u;
  return 8u;
}

static int league_fixture_add(LeagueTournament *league, uint32_t day,
                               uint32_t home, uint32_t away) {
  if (day >= LEAGUE_MAX_MATCHDAYS ||
      league->fixture_count >= LEAGUE_MAX_FIXTURES ||
      league->matchday_fixture_count[day] >= LEAGUE_MAX_TEAMS / 2u)
    return 0;
  LeagueFixture *fixture = &league->fixtures[league->fixture_count++];
  fixture->home = home;
  fixture->away = away;
  league->matchday_fixture_count[day]++;
  return 1;
}

int league_tournament_init(LeagueTournament *league,
                           const uint32_t *teams, uint32_t team_count,
                           const uint32_t *human_teams, uint32_t human_count,
                           int home_away, uint32_t seed) {
  if (!league || !teams || !human_teams || team_count < 2u ||
      team_count > LEAGUE_MAX_TEAMS || human_count < 1u ||
      human_count > 8u || human_count > team_count)
    return 0;
  for (uint32_t i = 0; i < team_count; i++) {
    if (!teams[i]) return 0;
    for (uint32_t j = 0; j < i; j++)
      if (teams[i] == teams[j]) return 0;
  }
  memset(league, 0, sizeof(*league));
  league->seed = seed ? seed : 1u;
  league->team_count = team_count;
  league->human_count = human_count;
  league->home_away = home_away != 0;
  memcpy(league->human_teams, human_teams,
         human_count * sizeof(human_teams[0]));
  for (uint32_t i = 0; i < team_count; i++)
    league->standings[i].team = teams[i];

  const uint32_t rotation_count = (team_count + 1u) & ~1u;
  const uint32_t rounds = rotation_count - 1u;
  league->matchday_count = rounds * (league->home_away ? 2u : 1u);
  uint32_t rotation[LEAGUE_MAX_TEAMS];
  for (uint32_t i = 0; i < rotation_count; i++)
    rotation[i] = i < team_count ? i : UINT32_MAX;

  for (uint32_t round = 0; round < rounds; round++) {
    league->matchday_first[round] = league->fixture_count;
    for (uint32_t pair = 0; pair < rotation_count / 2u; pair++) {
      const uint32_t first = rotation[pair];
      const uint32_t second = rotation[rotation_count - 1u - pair];
      if (first == UINT32_MAX || second == UINT32_MAX) continue;
      const int reverse = ((round + pair) & 1u) != 0;
      const uint32_t home = teams[reverse ? second : first];
      const uint32_t away = teams[reverse ? first : second];
      if (!league_fixture_add(league, round, home, away)) return 0;
    }
    const uint32_t last = rotation[rotation_count - 1u];
    for (uint32_t i = rotation_count - 1u; i > 1u; i--)
      rotation[i] = rotation[i - 1u];
    rotation[1] = last;
  }
  if (league->home_away) {
    const uint32_t first_leg_count = league->fixture_count;
    for (uint32_t round = 0; round < rounds; round++) {
      const uint32_t return_day = round + rounds;
      league->matchday_first[return_day] = league->fixture_count;
      for (uint32_t i = 0; i < league->matchday_fixture_count[round]; i++) {
        const LeagueFixture *first = &league->fixtures[
            league->matchday_first[round] + i];
        if (!league_fixture_add(league, return_day,
                                first->away, first->home)) return 0;
      }
    }
    if (league->fixture_count != first_leg_count * 2u) return 0;
  }
  return 1;
}

const LeagueFixture *league_tournament_matchday_fixture(
    const LeagueTournament *league, uint32_t matchday, uint32_t offset) {
  if (!league || matchday >= league->matchday_count ||
      offset >= league->matchday_fixture_count[matchday]) return NULL;
  return &league->fixtures[league->matchday_first[matchday] + offset];
}

static LeagueStanding *league_find_standing(LeagueTournament *league,
                                            uint32_t team) {
  for (uint32_t i = 0; i < league->team_count; i++)
    if (league->standings[i].team == team) return &league->standings[i];
  return NULL;
}

int league_tournament_credit_goals(LeagueTournament *league,
                                    uint32_t team, uint32_t base_id,
                                    uint32_t portrait_id, const char *name,
                                    uint32_t goals) {
  if (!league || !team || !base_id || !name || !name[0] || !goals ||
      !league_find_standing(league, team)) return 0;
  for (uint32_t i = 0; i < league->scorer_count; i++) {
    LeagueScorer *scorer = &league->scorers[i];
    if (scorer->base_id != base_id || scorer->team != team) continue;
    scorer->goals = (uint16_t)(goals > (uint32_t)UINT16_MAX - scorer->goals
        ? UINT16_MAX : scorer->goals + goals);
    return 1;
  }
  if (league->scorer_count >= LEAGUE_MAX_SCORERS) return 0;
  LeagueScorer *scorer = &league->scorers[league->scorer_count++];
  memset(scorer, 0, sizeof(*scorer));
  scorer->base_id = base_id;
  scorer->portrait_id = portrait_id;
  scorer->team = team;
  scorer->goals = (uint16_t)(goals > UINT16_MAX ? UINT16_MAX : goals);
  strncpy(scorer->name, name, sizeof(scorer->name) - 1u);
  return 1;
}

uint32_t league_tournament_top_scorers(const LeagueTournament *league,
                                        uint16_t slots[4]) {
  if (!league || !slots) return 0u;
  uint32_t count = 0u;
  for (uint32_t i = 0; i < league->scorer_count &&
                       i < LEAGUE_MAX_SCORERS; i++) {
    const LeagueScorer *candidate = &league->scorers[i];
    if (!candidate->goals) continue;
    uint32_t insert = count;
    while (insert > 0u) {
      const LeagueScorer *above = &league->scorers[slots[insert - 1u]];
      if (above->goals > candidate->goals ||
          (above->goals == candidate->goals &&
           above->base_id <= candidate->base_id)) break;
      insert--;
    }
    if (insert >= 4u) continue;
    if (count < 4u) count++;
    for (uint32_t move = count - 1u; move > insert; move--)
      slots[move] = slots[move - 1u];
    slots[insert] = (uint16_t)i;
  }
  return count;
}

uint32_t league_tournament_base_id_for_portrait(uint32_t portrait_id) {
  uint32_t low = 0u;
  uint32_t high = (uint32_t)(sizeof(league_scorer_identities) /
                             sizeof(league_scorer_identities[0]));
  while (low < high) {
    const uint32_t mid = low + (high - low) / 2u;
    if (league_scorer_identities[mid].portrait_id < portrait_id)
      low = mid + 1u;
    else high = mid;
  }
  return low < (uint32_t)(sizeof(league_scorer_identities) /
                           sizeof(league_scorer_identities[0])) &&
         league_scorer_identities[low].portrait_id == portrait_id
      ? league_scorer_identities[low].base_id : 0u;
}

static const LeagueScorerPoolTeam *league_scorer_pool(uint32_t team) {
  uint32_t low = 0u;
  uint32_t high = (uint32_t)(sizeof(league_scorer_pool_teams) /
                             sizeof(league_scorer_pool_teams[0]));
  while (low < high) {
    const uint32_t mid = low + (high - low) / 2u;
    if (league_scorer_pool_teams[mid].team < team) low = mid + 1u;
    else high = mid;
  }
  return low < (uint32_t)(sizeof(league_scorer_pool_teams) /
                           sizeof(league_scorer_pool_teams[0])) &&
         league_scorer_pool_teams[low].team == team
      ? &league_scorer_pool_teams[low] : NULL;
}

static void league_simulate_scorers(LeagueTournament *league,
                                    uint32_t team, uint32_t goals,
                                    uint32_t fixture_index) {
  const LeagueScorerPoolTeam *pool = league_scorer_pool(team);
  if (!pool || !pool->count) return;
  uint32_t roll = league->seed ^ (team * 2654435761u) ^
      (fixture_index * 2246822519u);
  for (uint32_t goal = 0; goal < goals; goal++) {
    roll ^= roll << 13;
    roll ^= roll >> 17;
    roll ^= roll << 5;
    const uint32_t choice = pool->count == 1u || (roll & 3u) == 0u
        ? 0u : 1u + (roll >> 3u) % (pool->count - 1u);
    const LeagueScorerPoolPlayer *player =
        &league_scorer_pool_players[pool->first + choice];
    league_tournament_credit_goals(league, team, player->base_id,
                                    player->portrait_id, player->name, 1u);
  }
}

static void league_credit_knockout_simulations(LeagueTournament *league,
                                                uint32_t history_before) {
  const CupTournament *cup = &league->knockout;
  for (uint32_t h = history_before; h < cup->history_count; h++) {
    const uint32_t round = cup->history_round[h];
    const uint32_t index = cup->history_index[h];
    const CupFixture *fixture = cup_tournament_fixture(cup, round, index);
    if (!fixture || !fixture->simulated) continue;
    const uint32_t seed_index = LEAGUE_MAX_FIXTURES + round * 16u + index;
    league_simulate_scorers(league, fixture->home,
        fixture->home_goals, seed_index);
    league_simulate_scorers(league, fixture->away,
        fixture->away_goals, seed_index);
  }
}

static void league_apply_result(LeagueTournament *league,
                                 LeagueFixture *fixture,
                                 uint32_t home_goals, uint32_t away_goals,
                                 int simulated) {
  fixture->home_goals = (uint8_t)(home_goals > 99u ? 99u : home_goals);
  fixture->away_goals = (uint8_t)(away_goals > 99u ? 99u : away_goals);
  fixture->complete = 1u;
  fixture->simulated = simulated != 0;
  league->first_match_started = 1u;
  LeagueStanding *home = league_find_standing(league, fixture->home);
  LeagueStanding *away = league_find_standing(league, fixture->away);
  if (!home || !away) return;
  home->played++; away->played++;
  home->goals_for += fixture->home_goals;
  home->goals_against += fixture->away_goals;
  away->goals_for += fixture->away_goals;
  away->goals_against += fixture->home_goals;
  if (home_goals > away_goals) {
    home->wins++; home->points += 3u; away->losses++;
  } else if (away_goals > home_goals) {
    away->wins++; away->points += 3u; home->losses++;
  } else {
    home->draws++; away->draws++;
    home->points++; away->points++;
  }
}

static int league_better(const LeagueStanding *first,
                         const LeagueStanding *second) {
  if (first->points != second->points)
    return first->points > second->points;
  const int first_difference = (int)first->goals_for - first->goals_against;
  const int second_difference = (int)second->goals_for - second->goals_against;
  if (first_difference != second_difference)
    return first_difference > second_difference;
  if (first->goals_for != second->goals_for)
    return first->goals_for > second->goals_for;
  return first->team < second->team;
}

void league_tournament_ranked_slots(const LeagueTournament *league,
                                     uint8_t slots[LEAGUE_MAX_TEAMS]) {
  if (!league || !slots) return;
  for (uint32_t i = 0; i < league->team_count; i++)
    slots[i] = (uint8_t)i;
  for (uint32_t i = 1; i < league->team_count; i++) {
    const uint8_t moving = slots[i];
    uint32_t j = i;
    while (j && league_better(&league->standings[moving],
                               &league->standings[slots[j - 1u]])) {
      slots[j] = slots[j - 1u];
      j--;
    }
    slots[j] = moving;
  }
}

static void league_begin_knockout(LeagueTournament *league) {
  uint8_t slots[LEAGUE_MAX_TEAMS] = {0};
  league_tournament_ranked_slots(league, slots);
  const uint32_t qualified = league_tournament_qualifier_count(
      league->team_count);
  uint32_t participants[8] = {0};
  /* Cup pairs first-half participants with second-half participants.
   * Resulting fixtures: 1-vs-8, 4-vs-5, 2-vs-7, 3-vs-6. */
  static const uint8_t seed8[8] = {0u, 3u, 1u, 2u, 7u, 4u, 6u, 5u};
  static const uint8_t seed4[4] = {0u, 1u, 3u, 2u};
  for (uint32_t i = 0; i < qualified; i++) {
    const uint32_t rank = qualified == 8u ? seed8[i]
        : qualified == 4u ? seed4[i] : i;
    participants[i] = league->standings[slots[rank]].team;
  }
  uint32_t qualified_humans[8] = {0};
  uint32_t human_count = 0;
  for (uint32_t i = 0; i < qualified; i++)
    if (league_is_human(league, participants[i]))
      qualified_humans[human_count++] = participants[i];
  if (!human_count) qualified_humans[human_count++] = UINT32_MAX;
  if (!cup_tournament_init(&league->knockout, participants, qualified,
                           qualified_humans, human_count,
                           league->seed ^ 0x4c454147u)) return;
  league->phase = LEAGUE_PHASE_KNOCKOUT;
  cup_tournament_advance(&league->knockout);
  league_credit_knockout_simulations(league, 0u);
  if (league->knockout.champion)
    league->phase = LEAGUE_PHASE_COMPLETE;
}

int league_tournament_next_human(const LeagueTournament *league,
                                  uint32_t *fixture_index,
                                  uint32_t *knockout_round,
                                  uint32_t *knockout_index) {
  if (!league) return 0;
  if (league->phase == LEAGUE_PHASE_TABLE) {
    if (league->active_matchday >= league->matchday_count) return 0;
    const uint32_t first = league->matchday_first[league->active_matchday];
    const uint32_t count =
        league->matchday_fixture_count[league->active_matchday];
    for (uint32_t i = 0; i < count; i++) {
      const LeagueFixture *fixture = &league->fixtures[first + i];
      if (!fixture->complete &&
          (league_is_human(league, fixture->home) ||
           league_is_human(league, fixture->away))) {
        if (fixture_index) *fixture_index = first + i;
        return 1;
      }
    }
    return 0;
  }
  return league->phase == LEAGUE_PHASE_KNOCKOUT &&
      cup_tournament_next_human(&league->knockout,
                                 knockout_round, knockout_index);
}

void league_tournament_advance(LeagueTournament *league) {
  if (!league) return;
  if (league->phase == LEAGUE_PHASE_KNOCKOUT) {
    const uint32_t history_before = league->knockout.history_count;
    cup_tournament_advance(&league->knockout);
    league_credit_knockout_simulations(league, history_before);
    if (league->knockout.champion)
      league->phase = LEAGUE_PHASE_COMPLETE;
    return;
  }
  while (league->phase == LEAGUE_PHASE_TABLE &&
         league->active_matchday < league->matchday_count) {
    if (league_tournament_next_human(league, NULL, NULL, NULL)) return;
    const uint32_t first = league->matchday_first[league->active_matchday];
    const uint32_t count =
        league->matchday_fixture_count[league->active_matchday];
    for (uint32_t i = 0; i < count; i++) {
      LeagueFixture *fixture = &league->fixtures[first + i];
      if (fixture->complete) continue;
      const uint32_t roll = league->seed ^ fixture->home * 1664525u ^
          fixture->away * 1013904223u ^
          (league->active_matchday * 97u + i * 31u);
      league_apply_result(league, fixture,
                           (roll >> 5) % 4u, (roll >> 13) % 4u, 1);
      league_simulate_scorers(league, fixture->home,
          fixture->home_goals, first + i);
      league_simulate_scorers(league, fixture->away,
          fixture->away_goals, first + i);
    }
    league->active_matchday++;
  }
  if (league->phase == LEAGUE_PHASE_TABLE &&
      league->active_matchday == league->matchday_count)
    league_begin_knockout(league);
}

int league_tournament_record(LeagueTournament *league,
                              uint32_t fixture_index,
                              uint32_t knockout_round,
                              uint32_t knockout_index,
                              uint32_t home_goals, uint32_t away_goals) {
  if (!league) return 0;
  if (league->phase == LEAGUE_PHASE_KNOCKOUT) {
    const uint32_t history_before = league->knockout.history_count;
    if (!cup_tournament_record(&league->knockout,
                               knockout_round, knockout_index,
                               home_goals, away_goals)) return 0;
    league_credit_knockout_simulations(league, history_before);
    league_tournament_advance(league);
    return 1;
  }
  if (league->phase != LEAGUE_PHASE_TABLE ||
      league->active_matchday >= league->matchday_count) return 0;
  const uint32_t first = league->matchday_first[league->active_matchday];
  const uint32_t count =
      league->matchday_fixture_count[league->active_matchday];
  if (fixture_index < first || fixture_index >= first + count) return 0;
  LeagueFixture *fixture = &league->fixtures[fixture_index];
  if (fixture->complete ||
      (!league_is_human(league, fixture->home) &&
       !league_is_human(league, fixture->away))) return 0;
  league_apply_result(league, fixture, home_goals, away_goals, 0);
  league_tournament_advance(league);
  return 1;
}

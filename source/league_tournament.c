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
  for (uint32_t i = 0; i < human_count; i++) {
    uint32_t found = 0u;
    for (uint32_t j = 0; j < team_count; j++)
      found |= human_teams[i] == teams[j];
    if (!found) return 0;
    for (uint32_t j = 0; j < i; j++)
      if (human_teams[i] == human_teams[j]) return 0;
  }
  /* An odd field needs one bye every matchday. All human owners must play
   * on day one, so a completely human-owned odd field is not schedulable. */
  if ((team_count & 1u) && human_count == team_count) return 0;
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
  if ((team_count & 1u) && league_is_human(league, teams[rotation[0]])) {
    /* Slot zero meets the sentinel on day one. Give that bye to a COM
     * team without moving owners, changing standings order or skipping days. */
    for (uint32_t i = 1u; i < team_count; i++) {
      if (league_is_human(league, teams[rotation[i]])) continue;
      rotation[0] = i;
      rotation[i] = 0u;
      break;
    }
  }

  for (uint32_t round = 0; round < rounds; round++) {
    league->matchday_first[round] = league->fixture_count;
    for (uint32_t pair = 0; pair < rotation_count / 2u; pair++) {
      const uint32_t first = rotation[pair];
      const uint32_t second = rotation[rotation_count - 1u - pair];
      if (first == UINT32_MAX || second == UINT32_MAX) continue;
      /* Berger rotation: alternate only the fixed pairing. Alternating every
       * pair leaves a moving entrant away for the entire first half-season. */
      const int reverse = pair == 0u && (round & 1u);
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
  uint16_t identities[2048] = {0}; /* slot + 1; no heap/cache lifetime */
  uint32_t totals[LEAGUE_MAX_SCORERS] = {0};
  const uint32_t limit = league->scorer_count < LEAGUE_MAX_SCORERS
      ? league->scorer_count : LEAGUE_MAX_SCORERS;
  for (uint32_t i = 0; i < limit; i++) {
    const LeagueScorer *s = &league->scorers[i];
    if (!s->base_id || !s->goals) continue;
    uint32_t bucket = (s->base_id * 2654435761u) & 2047u;
    while (identities[bucket] &&
           league->scorers[identities[bucket] - 1u].base_id != s->base_id)
      bucket = (bucket + 1u) & 2047u;
    if (!identities[bucket]) identities[bucket] = (uint16_t)(i + 1u);
    totals[identities[bucket] - 1u] += s->goals;
  }
  uint32_t count = 0u;
  for (uint32_t i = 0; i < limit; i++) {
    const LeagueScorer *candidate = &league->scorers[i];
    if (!totals[i]) continue;
    uint32_t insert = count;
    while (insert > 0u) {
      const LeagueScorer *above = &league->scorers[slots[insert - 1u]];
      if (totals[slots[insert - 1u]] > totals[i] ||
          (totals[slots[insert - 1u]] == totals[i] &&
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

uint32_t league_tournament_scorer_goals(const LeagueTournament *league, uint32_t slot) {
  if (!league || slot >= league->scorer_count || slot >= LEAGUE_MAX_SCORERS) return 0u;
  uint32_t goals = 0u;
  for (uint32_t i = 0; i < league->scorer_count && i < LEAGUE_MAX_SCORERS; i++)
    if (league->scorers[i].base_id == league->scorers[slot].base_id)
      goals += league->scorers[i].goals;
  return goals;
}
uint32_t league_tournament_scorer_clubs(const LeagueTournament *league, uint32_t slot) {
  if (!league || slot >= league->scorer_count || slot >= LEAGUE_MAX_SCORERS) return 0u;
  uint32_t clubs = 0u;
  for (uint32_t i = 0; i < league->scorer_count && i < LEAGUE_MAX_SCORERS; i++)
    clubs += league->scorers[i].base_id == league->scorers[slot].base_id && league->scorers[i].goals;
  return clubs;
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

int league_tournament_record_table_fixture(LeagueTournament *league,
    uint32_t index, uint32_t home_goals, uint32_t away_goals, int simulated) {
  if (!league || league->phase != LEAGUE_PHASE_TABLE ||
      league->active_matchday >= league->matchday_count ||
      home_goals > 99u || away_goals > 99u) return 0;
  const uint32_t first = league->matchday_first[league->active_matchday];
  const uint32_t count = league->matchday_fixture_count[league->active_matchday];
  if (index < first || index >= first + count ||
      league->fixtures[index].complete) return 0;
  league_apply_result(league, &league->fixtures[index], home_goals, away_goals,
                       simulated);
  return 1;
}

int league_tournament_commit_matchday(LeagueTournament *league) {
  if (!league || league->phase != LEAGUE_PHASE_TABLE ||
      league->reserved[0] != LEAGUE_SYSTEM_STANDINGS ||
      league->active_matchday >= league->matchday_count) return 0;
  const uint32_t first = league->matchday_first[league->active_matchday];
  const uint32_t count = league->matchday_fixture_count[league->active_matchday];
  for (uint32_t i = 0; i < count; i++)
    if (!league->fixtures[first + i].complete) return 0;
  if (++league->active_matchday == league->matchday_count) {
    uint8_t order[LEAGUE_MAX_TEAMS];
    league_tournament_ranked_slots(league, order);
    league->knockout.champion = league->standings[order[0]].team;
    league->phase = LEAGUE_PHASE_COMPLETE;
  }
  return 1;
}

static void league_rank_table(const LeagueTournament *league,
    const LeagueStanding *table, uint32_t fixture_limit,
    uint8_t slots[LEAGUE_MAX_TEAMS]) {
  if (!league || !slots) return;
  LeagueStanding mini[LEAGUE_MAX_TEAMS] = {{0}};
  const int head_to_head = league->reserved[1] == LEAGUE_TIEBREAK_HEAD_TO_HEAD;
  if (head_to_head) {
    /* One mini-table for each equal-points group, including 3+ clubs. Pairwise
     * H2H comparisons can cycle; group totals keep the ordering transitive.
     * Only completed fixtures in the requested snapshot contribute. */
    for (uint32_t i = 0; i < fixture_limit && i < league->fixture_count; i++) {
      const LeagueFixture *f = &league->fixtures[i];
      if (!f->complete) continue;
      uint32_t home = league->team_count, away = league->team_count;
      for (uint32_t j = 0; j < league->team_count; j++) {
        if (table[j].team == f->home) home = j;
        if (table[j].team == f->away) away = j;
      }
      if (home == league->team_count || away == league->team_count ||
          table[home].points != table[away].points) continue;
      mini[home].goals_for += f->home_goals;
      mini[home].goals_against += f->away_goals;
      mini[away].goals_for += f->away_goals;
      mini[away].goals_against += f->home_goals;
      mini[home].points += f->home_goals > f->away_goals ? 3u : f->home_goals == f->away_goals;
      mini[away].points += f->away_goals > f->home_goals ? 3u : f->home_goals == f->away_goals;
    }
  }
  for (uint32_t i = 0; i < league->team_count; i++)
    slots[i] = (uint8_t)i;
  for (uint32_t i = 1; i < league->team_count; i++) {
    const uint8_t moving = slots[i];
    uint32_t j = i;
    while (j) {
      const uint32_t above = slots[j - 1u];
      int better = league_better(&table[moving], &table[above]);
      if (head_to_head && table[moving].points == table[above].points) {
        if (league_better(&mini[moving], &mini[above])) better = 1;
        else if (league_better(&mini[above], &mini[moving])) better = 0;
      }
      if (!better) break;
      slots[j] = slots[j - 1u];
      j--;
    }
    slots[j] = moving;
  }
}

void league_tournament_ranked_slots(const LeagueTournament *league,
                                     uint8_t slots[LEAGUE_MAX_TEAMS]) {
  if (!league || league->team_count > LEAGUE_MAX_TEAMS) return;
  league_rank_table(league, league->standings, league->fixture_count, slots);
}

void league_tournament_rank_changes(const LeagueTournament *league,
                                     int8_t changes[LEAGUE_MAX_TEAMS]) {
  if (!changes) return;
  memset(changes, 0, LEAGUE_MAX_TEAMS * sizeof(*changes));
  if (!league || !league->team_count || league->team_count > LEAGUE_MAX_TEAMS ||
      league->matchday_count > LEAGUE_MAX_MATCHDAYS ||
      league->fixture_count > LEAGUE_MAX_FIXTURES) return;
  uint32_t latest = UINT32_MAX;
  for (uint32_t day = 0; day < league->matchday_count; day++) {
    const uint32_t first = league->matchday_first[day];
    const uint32_t count = league->matchday_fixture_count[day];
    if (first > league->fixture_count || count > league->fixture_count - first) return;
    for (uint32_t i = 0; i < count; i++)
      if (league->fixtures[first + i].complete) latest = day;
  }
  if (latest == UINT32_MAX) return;
  LeagueStanding previous[LEAGUE_MAX_TEAMS] = {{0}};
  for (uint32_t slot = 0; slot < league->team_count; slot++)
    previous[slot].team = league->standings[slot].team;
  /* Only points and goals take part in the canonical ranking comparator. */
  for (uint32_t day = 0; day < latest; day++) {
    for (uint32_t i = 0; i < league->matchday_fixture_count[day]; i++) {
      const LeagueFixture *f = &league->fixtures[league->matchday_first[day] + i];
      if (!f->complete) continue;
      for (uint32_t slot = 0; slot < league->team_count; slot++) {
        LeagueStanding *s = &previous[slot];
        if (s->team != f->home && s->team != f->away) continue;
        const uint32_t gf = s->team == f->home ? f->home_goals : f->away_goals;
        const uint32_t ga = s->team == f->home ? f->away_goals : f->home_goals;
        s->goals_for += gf; s->goals_against += ga;
        s->points += gf > ga ? 3u : gf == ga ? 1u : 0u;
      }
    }
  }
  uint8_t order[LEAGUE_MAX_TEAMS], before[LEAGUE_MAX_TEAMS];
  league_tournament_ranked_slots(league, order);
  league_rank_table(league, previous, league->matchday_first[latest], before);
  for (uint32_t rank = 0; rank < league->team_count; rank++) {
    const uint32_t slot = order[rank];
    uint32_t old_rank = 0u;
    while (old_rank < league->team_count && before[old_rank] != slot) old_rank++;
    changes[slot] = (int8_t)((int)old_rank - (int)rank);
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
  /* The standalone League setting governs every knockout tie, including
   * the final. Career competitions select their own rules independently. */
  cup_tournament_set_rules(&league->knockout, league->home_away, 0);
  cup_tournament_set_final_two_legs(&league->knockout, league->home_away);
  league->phase = LEAGUE_PHASE_KNOCKOUT;
  cup_tournament_advance(&league->knockout);
  league_credit_knockout_simulations(league, 0u);
  if (league->knockout.champion)
    league->phase = LEAGUE_PHASE_COMPLETE;
}

void league_tournament_set_system(LeagueTournament *league,
                                  LeagueSystem system) {
  if (!league || league->first_match_started) return;
  league->reserved[0] = system == LEAGUE_SYSTEM_STANDINGS
      ? LEAGUE_SYSTEM_STANDINGS : LEAGUE_SYSTEM_KNOCKOUT;
}

void league_tournament_set_tiebreak(LeagueTournament *league, LeagueTiebreak rule) {
  if (league && !league->first_match_started && (unsigned)rule <= LEAGUE_TIEBREAK_HEAD_TO_HEAD)
    league->reserved[1] = (uint8_t)rule;
}
const char *league_tournament_tiebreak_label(LeagueTiebreak rule) {
  return rule == LEAGUE_TIEBREAK_HEAD_TO_HEAD ? "HEAD-TO-HEAD" : "GOAL DIFFERENCE";
}
const char *league_tournament_tiebreak_rules(LeagueTiebreak rule) {
  return rule == LEAGUE_TIEBREAK_HEAD_TO_HEAD
      ? "PTS > H2H PTS/GD/GF > GD > GF > TEAM ID"
      : "PTS > GD > GF > TEAM ID";
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

int league_tournament_upcoming_human(const LeagueTournament *league,
    uint32_t *fixture_index, uint32_t *matchday,
    uint32_t *knockout_round, uint32_t *knockout_index) {
  if (!league) return 0;
  if (league->phase != LEAGUE_PHASE_TABLE)
    return league_tournament_next_human(league, fixture_index,
        knockout_round, knockout_index);
  for (uint32_t day = league->active_matchday; day < league->matchday_count; day++) {
    const uint32_t first = league->matchday_first[day];
    for (uint32_t i = 0; i < league->matchday_fixture_count[day]; i++) {
      const LeagueFixture *fixture = &league->fixtures[first + i];
      if (!fixture->complete && (league_is_human(league, fixture->home) ||
                                league_is_human(league, fixture->away))) {
        if (fixture_index) *fixture_index = first + i;
        if (matchday) *matchday = day;
        return 1;
      }
    }
  }
  return 0;
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
      league->active_matchday == league->matchday_count) {
    if (league->reserved[0] == LEAGUE_SYSTEM_STANDINGS) {
      uint8_t ranked[LEAGUE_MAX_TEAMS] = {0};
      league_tournament_ranked_slots(league, ranked);
      league->knockout.champion = league->standings[ranked[0]].team;
      league->phase = LEAGUE_PHASE_COMPLETE;
    } else {
      league_begin_knockout(league);
    }
  }
}

int league_tournament_record(LeagueTournament *league,
                              uint32_t fixture_index,
                              uint32_t knockout_round,
                              uint32_t knockout_index,
                              uint32_t home_goals, uint32_t away_goals) {
  return league_tournament_record_decided(league, fixture_index, knockout_round,
      knockout_index, home_goals, away_goals, 0u);
}

int league_tournament_record_decided(LeagueTournament *league,
    uint32_t fixture_index, uint32_t knockout_round, uint32_t knockout_index,
    uint32_t home_goals, uint32_t away_goals, uint32_t shootout_winner) {
  if (!league || home_goals > 99u || away_goals > 99u) return 0;
  if (league->phase == LEAGUE_PHASE_KNOCKOUT) {
    const uint32_t history_before = league->knockout.history_count;
    if (!cup_tournament_record_decided(&league->knockout,
                               knockout_round, knockout_index,
                               home_goals, away_goals, shootout_winner)) return 0;
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

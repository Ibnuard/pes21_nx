#include "master_league.h"

#include <stdlib.h>
#include <stdio.h>
#include <string.h>

static uint32_t ml_random(uint32_t *seed) {
  uint32_t x = *seed ? *seed : 1u;
  x ^= x << 13; x ^= x >> 17; x ^= x << 5;
  return *seed = x;
}

int ml_manager_name_valid(const char *name) {
  if (!name) return 0;
  uint32_t letters = 0;
  for (uint32_t i = 0; i < ML_NAME_SIZE; i++) {
    const unsigned char ch = (unsigned char)name[i];
    if (!ch) return letters != 0u && i > 0u && name[0] != ' ' && name[i-1] != ' ';
    /* The shared custom font has a Latin ASCII glyph set. Do not silently
     * accept unsupported glyphs and display a different manager identity. */
    if ((ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z')) letters++;
    else if (ch != ' ' && ch != '-' && ch != '.' && ch != '\'') return 0;
  }
  return 0;
}

MlClub *ml_club(MasterLeague *c, uint32_t team) {
  if (!c || !team) return NULL;
  for (uint32_t i = 0; i < c->club_count; i++)
    if (c->clubs[i].team == team) return &c->clubs[i];
  return NULL;
}
const MlClub *ml_find_club(const MasterLeague *c, uint32_t team) {
  if (!c || !team) return NULL;
  for (uint32_t i = 0; i < c->club_count; i++)
    if (c->clubs[i].team == team) return &c->clubs[i];
  return NULL;
}
const MlPlayer *ml_find_native(const MasterLeague *c, uint32_t native_id) {
  if (!c || !native_id) return NULL;
  for (uint32_t i = 0; i < c->player_count; i++)
    if (c->players[i].native_id == native_id) return &c->players[i];
  return NULL;
}
uint32_t ml_weekly_wage(const MasterLeague *c, uint32_t team) {
  const MlClub *club = ml_find_club(c, team);
  uint32_t sum = 0;
  if (club) for (uint32_t i = 0; i < club->count; i++)
    sum += c->players[club->players[i]].wage;
  return sum;
}
uint32_t ml_transfer_value(const MlPlayer *p) {
  if (!p || !p->club) return 0u;
  const uint32_t rating = p->overall > 40u ? p->overall - 40u : 1u;
  return 100000u + rating * rating * 7500u;
}
static uint32_t ml_wage_for(const MlPlayer *p) {
  const uint32_t rating = p->overall > 40u ? p->overall - 40u : 1u;
  return 1000u + rating * rating * 15u;
}
static uint32_t ml_strength(const MasterLeague *c, uint32_t team) {
  const MlClub *club = ml_find_club(c, team);
  if (!club || club->count < 11u) return 1u;
  uint32_t sum = 0;
  for (uint32_t i = 0; i < 11u; i++) sum += c->players[club->players[i]].overall;
  return sum / 11u;
}
static int ml_has_keeper(const MasterLeague *c, const MlClub *club,
                          uint32_t excluding) {
  for (uint32_t i = 0; i < club->count; i++)
    if (club->players[i] != excluding &&
        c->players[club->players[i]].position == 0u) return 1;
  return 0;
}

int ml_init(MasterLeague *c, const char *content_id, const MlSettings *settings,
            const char *manager, uint32_t nationality, uint32_t seed) {
  if (!c || !settings || !settings->club || !settings->competition_id ||
      !ml_manager_name_valid(manager) || !nationality || !content_id ||
      !content_id[0] || strlen(content_id) >= ML_CONTENT_ID_SIZE ||
      settings->difficulty > 6u || settings->match_minutes < 5u ||
      settings->match_minutes > 30u || settings->condition > 5u ||
      settings->injuries > 1u || settings->max_substitutions > 12u) return 0;
  memset(c, 0, sizeof(*c));
  c->settings = *settings;
  c->seed = seed ? seed : 1u;
  c->season = 1u;
  strcpy(c->content_id, content_id);
  strcpy(c->manager_name, manager);
  c->manager_nationality = nationality;
  return 1;
}

int ml_add_player(MasterLeague *c, uint32_t team, const MlPlayer *player) {
  if (!c || !player || !team || c->league.team_count ||
      c->player_count >= ML_MAX_PLAYERS || !player->identity ||
      !player->native_id || player->overall > 99u || !player->overall ||
      player->position > 12u || player->shirt > 99u ||
      !player->name[0] || !memchr(player->name, 0, sizeof(player->name))) return 0;
  MlClub *club = ml_club(c, team);
  if ((club && club->count >= ML_SQUAD_SIZE) ||
      (!club && c->club_count >= ML_MAX_CLUBS)) return 0;
  for (uint32_t i = 0; i < c->player_count; i++)
    if (c->players[i].identity == player->identity ||
        c->players[i].native_id == player->native_id) return 0;
  if (!club) { club = &c->clubs[c->club_count++]; club->team = team; }
  const uint32_t index = c->player_count++;
  c->players[index] = *player;
  c->players[index].club = team;
  c->players[index].wage = ml_wage_for(player);
  c->players[index].contract_end = c->season + 2u;
  club->players[club->count++] = index;
  return 1;
}

static void ml_seed_clubs(MasterLeague *c) {
  for (uint32_t i = 0; i < c->club_count; i++) {
    MlClub *club = &c->clubs[i];
    int64_t value = 0;
    for (uint32_t p = 0; p < club->count; p++)
      value += ml_transfer_value(&c->players[club->players[p]]);
    club->cash = 10000000 + value / 4;
    club->wage_budget = ml_weekly_wage(c, club->team) * 14u / 10u + 10000u;
  }
}

int ml_start_season(MasterLeague *c, const uint32_t *teams, uint32_t count,
                    const uint32_t *cup_teams, uint32_t cup_count) {
  if (!c || !teams || count < 2u || count > LEAGUE_MAX_TEAMS ||
      (cup_count && (!cup_teams || cup_count < 2u || cup_count > CUP_MAX_TEAMS)))
    return 0;
  uint32_t found = 0;
  for (uint32_t i = 0; i < count; i++) {
    const MlClub *club = ml_find_club(c, teams[i]);
    if (!club || club->count < 11u || !ml_has_keeper(c, club, ML_INVALID_INDEX))
      return 0;
    for (uint32_t j = 0; j < i; j++) if (teams[i] == teams[j]) return 0;
    found += teams[i] == c->settings.club;
  }
  if (found != 1u) return 0;
  found = 0u;
  for (uint32_t i = 0; i < cup_count; i++) {
    const MlClub *club = ml_find_club(c, cup_teams[i]);
    if (!club || club->count < 11u || !ml_has_keeper(c, club, ML_INVALID_INDEX))
      return 0;
    for (uint32_t j = 0; j < i; j++) if (cup_teams[i] == cup_teams[j]) return 0;
    found += cup_teams[i] == c->settings.club;
  }
  if (cup_count && found != 1u) return 0;
  if (!league_tournament_init(&c->league, teams, count, &c->settings.club,
        1u, 1, c->seed ^ c->season)) return 0;
  league_tournament_set_system(&c->league, LEAGUE_SYSTEM_STANDINGS);
  c->cup_enabled = cup_count != 0u;
  memset(&c->cup, 0, sizeof(c->cup));
  if (cup_count && !cup_tournament_init(&c->cup, cup_teams, cup_count,
        &c->settings.club, 1u, c->seed ^ (c->season * 97u))) return 0;
  c->day = c->wage_week = 0u;
  c->wages_paid = c->match_income = c->prize_income = 0;
  if (c->season == 1u) ml_seed_clubs(c);
  uint32_t stronger = 0u;
  for (uint32_t i = 0; i < count; i++)
    stronger += ml_strength(c, teams[i]) > ml_strength(c, c->settings.club);
  c->target_rank = stronger + 3u < count ? stronger + 3u : count;
  return 1;
}

int ml_window_open(const MasterLeague *c) {
  return c && (c->day < 31u || (c->day >= 183u && c->day < 214u));
}

/* Replace a sold starter with a matching bench role; never shift an entire
 * starting XI and accidentally put a goalkeeper in the attacker's position. */
static void ml_remove_member(MasterLeague *c, MlClub *club, uint32_t slot) {
  const uint32_t position = c->players[club->players[slot]].position;
  if (slot < 11u && club->count > 11u) {
    uint32_t replacement = ML_INVALID_INDEX, best = 0u;
    for (uint32_t i = 11u; i < club->count; i++) {
      const MlPlayer *p = &c->players[club->players[i]];
      if ((position == 0u) != (p->position == 0u)) continue;
      const uint32_t score = p->overall + (p->position == position ? 100u : 0u);
      if (replacement == ML_INVALID_INDEX || score > best) {
        replacement = i; best = score;
      }
    }
    if (replacement != ML_INVALID_INDEX) {
      club->players[slot] = club->players[replacement];
      slot = replacement;
    }
  }
  memmove(&club->players[slot], &club->players[slot + 1u],
          (club->count - slot - 1u) * sizeof(club->players[0]));
  club->players[--club->count] = 0u;
}

const char *ml_transfer(MasterLeague *c, uint32_t index,
                        uint32_t destination, uint32_t years) {
  if (!c || index >= c->player_count || years < 1u || years > 5u)
    return "INVALID TRANSFER";
  if (!ml_window_open(c)) return "TRANSFER WINDOW CLOSED";
  MlPlayer *p = &c->players[index];
  MlClub *from = ml_club(c, p->club), *to = ml_club(c, destination);
  if (!to || p->club == destination) return "SELECT ANOTHER CLUB";
  if (p->club != c->settings.club && destination != c->settings.club)
    return "ONLY YOUR CLUB CAN NEGOTIATE";
  if (to->count >= ML_SQUAD_SIZE) return "DESTINATION SQUAD IS FULL";
  uint32_t slot = 0u;
  if (from) {
    if (from->count <= 18u) return "SELLING CLUB NEEDS AT LEAST 18 PLAYERS";
    while (slot < from->count && from->players[slot] != index) slot++;
    if (slot == from->count) return "ROSTER IDENTITY MISMATCH";
    if (!ml_has_keeper(c, from, index)) return "CANNOT SELL THE LAST GOALKEEPER";
    if (slot < 11u) {
      int replacement = 0;
      for (uint32_t i = 11u; i < from->count; i++)
        replacement |= (c->players[from->players[i]].position == 0u) ==
                       (p->position == 0u);
      if (!replacement) return "NO SUITABLE STARTER REPLACEMENT";
    }
  }
  const uint32_t fee = ml_transfer_value(p), wage = ml_wage_for(p);
  if (to->cash < (int64_t)fee) return "INSUFFICIENT TRANSFER BUDGET";
  if ((uint64_t)ml_weekly_wage(c, destination) + wage > to->wage_budget)
    return "WAGE BUDGET EXCEEDED";
  uint8_t shirt_used[100] = {0};
  for (uint32_t i = 0; i < to->count; i++)
    shirt_used[c->players[to->players[i]].shirt] = 1u;
  uint32_t shirt = p->shirt;
  if (!shirt || shirt_used[shirt])
    for (shirt = 1u; shirt < 100u && shirt_used[shirt]; shirt++) {}
  if (shirt >= 100u) return "NO AVAILABLE SHIRT NUMBER";
  /* All checks precede the mutation. Native records/assets are never edited. */
  if (from) { ml_remove_member(c, from, slot); from->cash += fee; }
  to->cash -= fee;
  to->players[to->count++] = index;
  p->club = destination; p->shirt = (uint8_t)shirt;
  p->wage = wage; p->contract_end = c->season + years - 1u;
  c->transaction_sequence++;
  memset(&c->current_plan, 0, sizeof(c->current_plan));
  return "";
}

const char *ml_renew(MasterLeague *c, uint32_t index, uint32_t years) {
  if (!c || index >= c->player_count || years < 1u || years > 5u ||
      c->players[index].club != c->settings.club) return "INVALID CONTRACT";
  MlPlayer *p = &c->players[index];
  const MlClub *club = ml_find_club(c, p->club);
  const uint32_t wage = ml_wage_for(p);
  if (!club || (uint64_t)ml_weekly_wage(c, p->club) - p->wage + wage >
                   club->wage_budget) return "WAGE BUDGET EXCEEDED";
  p->contract_end = c->season + years; p->wage = wage;
  c->transaction_sequence++;
  return "";
}

int ml_swap(MasterLeague *c, uint32_t team, uint32_t first, uint32_t second) {
  MlClub *club = ml_club(c, team);
  if (!club || team != c->settings.club || first >= club->count ||
      second >= club->count) return 0;
  const uint32_t first_role=c->players[club->players[first]].position;
  const uint32_t second_role=c->players[club->players[second]].position;
  if ((first==0u && second_role!=0u) || (second==0u && first_role!=0u) ||
      (first>0u && first<11u && second_role==0u) ||
      (second>0u && second<11u && first_role==0u)) return 0;
  const uint32_t tmp = club->players[first];
  club->players[first] = club->players[second]; club->players[second] = tmp;
  memset(&c->current_plan, 0, sizeof(c->current_plan));
  return 1;
}

static uint32_t ml_league_day(const MasterLeague *c, uint32_t matchday) {
  return 42u + (c->league.matchday_count > 1u
      ? matchday * 280u / (c->league.matchday_count - 1u) : 0u);
}
static uint32_t ml_cup_day(const MasterLeague *c, uint32_t round) {
  uint32_t day = 70u + round * (259u / (c->cup.round_count > 1u
                                    ? c->cup.round_count - 1u : 1u));
  for (uint32_t i = 0; i < c->league.matchday_count; i++)
    if (ml_league_day(c, i) == day) { day++; i = 0u; }
  return day;
}
int ml_next_event(const MasterLeague *c, MlEvent *event) {
  if (!c || !event || !c->league.team_count) return 0;
  *event = (MlEvent){ML_EVENT_SEASON_END, 350u, ML_INVALID_INDEX, 0u, 0u, 0u};
  if (c->league.active_matchday < c->league.matchday_count) {
    event->kind = ML_EVENT_LEAGUE;
    event->day = ml_league_day(c, c->league.active_matchday);
    const uint32_t first = c->league.matchday_first[c->league.active_matchday];
    const uint32_t count = c->league.matchday_fixture_count[c->league.active_matchday];
    for (uint32_t i = 0; i < count; i++) {
      const LeagueFixture *f = &c->league.fixtures[first + i];
      if (!f->complete && (f->home == c->settings.club || f->away == c->settings.club)) {
        event->index = first + i; event->home = f->home; event->away = f->away;
        break;
      }
    }
  }
  if (c->cup_enabled && !c->cup.champion &&
      ml_cup_day(c, c->cup.active_round) < event->day) {
    *event = (MlEvent){ML_EVENT_CUP, ml_cup_day(c, c->cup.active_round),
                      ML_INVALID_INDEX, c->cup.active_round, 0u, 0u};
    uint32_t round, index;
    if (cup_tournament_next_human(&c->cup, &round, &index)) {
      const CupFixture *f = cup_tournament_fixture(&c->cup, round, index);
      event->index = index; event->home = f->home; event->away = f->away;
    }
  }
  return 1;
}
static int ml_event_matches(const MasterLeague *c, const MlEvent *event) {
  MlEvent actual;
  return event && ml_next_event(c, &actual) &&
      event->kind == actual.kind && event->day == actual.day &&
      event->index == actual.index && event->round == actual.round &&
      event->home == actual.home && event->away == actual.away;
}
int ml_advance_date(MasterLeague *c, const MlEvent *event) {
  if (!ml_event_matches(c, event) || event->day < c->day || event->day > 365u)
    return 0;
  const uint32_t week = event->day / 7u;
  for (uint32_t i = 0; i < c->club_count; i++) {
    MlClub *club = &c->clubs[i];
    const int64_t wages = (int64_t)(week - c->wage_week) * ml_weekly_wage(c, club->team);
    club->cash -= wages;
    if (club->team == c->settings.club) c->wages_paid += wages;
  }
  c->wage_week = week; c->day = event->day;
  return 1;
}

static void ml_simulate_score(const MasterLeague *c, uint32_t home, uint32_t away,
                               uint32_t salt, uint32_t *hg, uint32_t *ag) {
  uint32_t roll = c->seed ^ (c->season * 2654435761u) ^ (home * 97u) ^
                  (away * 193u) ^ (salt * 2246822519u);
  int difference = (int)ml_strength(c, home) - (int)ml_strength(c, away);
  if (difference > 25) difference = 25;
  if (difference < -25) difference = -25;
  *hg = *ag = 0u;
  for (uint32_t chance = 0; chance < 6u; chance++) {
    *hg += (int)(ml_random(&roll) % 100u) < 24 + difference / 2;
    *ag += (int)(ml_random(&roll) % 100u) < 20 - difference / 2;
  }
}
static void ml_simulated_goals(MasterLeague *c, uint32_t team, uint32_t goals,
                                uint32_t salt) {
  const MlClub *club = ml_find_club(c, team);
  if (!club || !club->count) return;
  uint32_t roll = c->seed ^ salt ^ (team * 2654435761u) ^ c->season;
  uint32_t total_weight = 0u;
  const uint32_t count = club->count < 18u ? club->count : 18u;
  for (uint32_t i = 0; i < count; i++) {
    const uint32_t role = c->players[club->players[i]].position;
    total_weight += role == 0u ? 0u : role >= 7u ? 6u : 1u;
  }
  if (!total_weight) return;
  for (uint32_t goal = 0; goal < goals; goal++) {
    uint32_t choice = ml_random(&roll) % total_weight;
    for (uint32_t i = 0; i < count; i++) {
      const MlPlayer *p = &c->players[club->players[i]];
      const uint32_t weight = p->position == 0u ? 0u : p->position >= 7u ? 6u : 1u;
      if (choice < weight) {
        league_tournament_credit_goals(&c->league, team, p->identity,
                                       p->portrait_id, p->name, 1u);
        break;
      }
      choice -= weight;
    }
  }
}
uint32_t ml_rank(const MasterLeague *c) {
  if (!c) return 0u;
  uint8_t order[LEAGUE_MAX_TEAMS];
  league_tournament_ranked_slots(&c->league, order);
  for (uint32_t i = 0; i < c->league.team_count; i++)
    if (c->league.standings[order[i]].team == c->settings.club) return i + 1u;
  return 0u;
}
int ml_record_event_decided(MasterLeague *c, const MlEvent *event,
                     uint32_t hg, uint32_t ag, const LeagueScorer *scorers,
                     uint32_t scorer_count, int simulated, uint32_t shootout_winner) {
  if (!ml_event_matches(c, event) || event->kind == ML_EVENT_SEASON_END ||
      hg > 99u || ag > 99u || scorer_count > 80u ||
      (scorer_count && !scorers)) return 0;
  if (!simulated && event->kind == ML_EVENT_CUP && event->home && event->away &&
      hg == ag && shootout_winner != event->home && shootout_winner != event->away)
    return 0;
  if (!ml_advance_date(c, event)) return 0;
  const uint32_t count = event->kind == ML_EVENT_LEAGUE
      ? c->league.matchday_fixture_count[c->league.active_matchday]
      : cup_tournament_fixture_count(&c->cup, event->round);
  const uint32_t first = event->kind == ML_EVENT_LEAGUE
      ? c->league.matchday_first[c->league.active_matchday] : 0u;
  for (uint32_t i = 0; i < count; i++) {
    uint32_t home, away, h = hg, a = ag;
    if (event->kind == ML_EVENT_LEAGUE) {
      const LeagueFixture *f = &c->league.fixtures[first+i];
      if (f->complete) continue;
      home = f->home; away = f->away;
    } else {
      const CupFixture *f = &c->cup.fixtures[event->round][i];
      if (f->complete) continue;
      home = f->home; away = f->away;
    }
    const int played = first+i == event->index && !simulated;
    const uint32_t salt = event->day * 100u + i;
    if (!played) ml_simulate_score(c, home, away, salt, &h, &a);
    if (event->kind == ML_EVENT_LEAGUE) {
      if (!league_tournament_record_table_fixture(&c->league, first+i, h, a, !played))
        return 0;
      if (!played) {
        ml_simulated_goals(c, home, h, salt);
        ml_simulated_goals(c, away, a, salt ^ 0x1234u);
      }
    } else {
      if (!cup_tournament_record_deferred(&c->cup, event->round, i, h, a)) return 0;
      c->cup.fixtures[event->round][i].simulated = !played;
      if (played && h == a) c->cup.fixtures[event->round][i].winner = shootout_winner;
    }
    MlClub *home_club = ml_club(c, home), *away_club = ml_club(c, away);
    if (home_club) home_club->cash += 600000;
    if (away_club) away_club->cash += 200000;
    if (home == c->settings.club) c->match_income += 600000;
    if (away == c->settings.club) c->match_income += 200000;
  }
  /* Native scorer events must resolve to the current registered identity and
   * cannot add more goals than the actual played result on either side. */
  if (!simulated && event->kind == ML_EVENT_LEAGUE) {
    uint32_t remaining[2] = {hg, ag};
    for (uint32_t i = 0; i < scorer_count; i++) {
      const LeagueScorer *s = &scorers[i];
      const uint32_t side = s->team == event->home ? 0u : 1u;
      if (s->team != event->home && s->team != event->away) continue;
      for (uint32_t p = 0; p < c->player_count; p++) {
        const MlPlayer *player = &c->players[p];
        if (player->identity != s->base_id || player->club != s->team) continue;
        const uint32_t goals = s->goals < remaining[side] ? s->goals : remaining[side];
        if (goals) league_tournament_credit_goals(&c->league, player->club,
            player->identity, player->portrait_id, player->name, goals);
        remaining[side] -= goals;
        break;
      }
    }
  }
  if (event->kind == ML_EVENT_LEAGUE) league_tournament_commit_matchday(&c->league);
  else cup_tournament_commit_round(&c->cup);
  MlEvent next;
  ml_next_event(c, &next);
  if (next.kind == ML_EVENT_SEASON_END) {
    c->last_rank = ml_rank(c);
    const int64_t prize = (int64_t)(c->league.team_count + 1u - c->last_rank) * 500000;
    ml_club(c, c->settings.club)->cash += prize;
    c->prize_income += prize;
  }
  return 1;
}
int ml_record_event(MasterLeague *c, const MlEvent *event,
                     uint32_t hg, uint32_t ag, const LeagueScorer *scorers,
                     uint32_t scorer_count, int simulated) {
  return ml_record_event_decided(c,event,hg,ag,scorers,scorer_count,simulated,0u);
}
int ml_simulate_event(MasterLeague *c, const MlEvent *event) {
  return ml_record_event(c, event, 0u, 0u, NULL, 0u, 1);
}

int ml_next_season(MasterLeague *c) {
  MlEvent event;
  if (!ml_next_event(c, &event) || event.kind != ML_EVENT_SEASON_END ||
      c->season >= 100u) return 0;
  const MlClub *managed = ml_find_club(c, c->settings.club);
  uint32_t staying = 0u, keepers = 0u;
  for (uint32_t i = 0; i < managed->count; i++) {
    const MlPlayer *p = &c->players[managed->players[i]];
    if (p->contract_end > c->season) { staying++; keepers += p->position == 0u; }
  }
  if (staying < 18u || !keepers) return 0; /* Renew before leaving this season. */
  if (!ml_advance_date(c, &event)) return 0;
  uint32_t teams[LEAGUE_MAX_TEAMS], cup_teams[CUP_MAX_TEAMS], cup_count = 0u;
  const uint32_t count = c->league.team_count;
  for (uint32_t i = 0; i < count; i++) teams[i] = c->league.standings[i].team;
  if (c->cup_enabled) {
    const uint32_t opening = cup_tournament_fixture_count(&c->cup, 0u);
    for (uint32_t i = 0; i < opening; i++) {
      const CupFixture *f = &c->cup.fixtures[0][i];
      if (f->home) cup_teams[cup_count++] = f->home;
      if (f->away) cup_teams[cup_count++] = f->away;
    }
  }
  for (uint32_t i = 0; i < c->player_count; i++) {
    MlPlayer *p = &c->players[i];
    if (!p->club || p->contract_end > c->season) continue;
    if (p->club != c->settings.club) { p->contract_end = c->season + 2u; continue; }
    MlClub *club = ml_club(c, p->club);
    uint32_t slot = 0u;
    while (slot < club->count && club->players[slot] != i) slot++;
    ml_remove_member(c, club, slot);
    p->club = p->wage = p->contract_end = 0u;
  }
  c->seasons_completed++; c->season++;
  memset(&c->current_plan, 0, sizeof(c->current_plan));
  /* Modest annual operating grant; AI finances cannot become an unbounded
   * negative transfer sink after many unattended seasons. */
  for (uint32_t i = 0; i < c->club_count; i++) {
    c->clubs[i].cash += 5000000;
    if (c->clubs[i].team != c->settings.club && c->clubs[i].cash < 5000000)
      c->clubs[i].cash = 5000000;
  }
  return ml_start_season(c, teams, count, cup_teams, cup_count);
}

int ml_plan_compatible(const MasterLeague *c, const GameplanPreset *plan) {
  if (!c || !gameplan_preset_valid(plan) || plan->team_id != c->settings.club) return 0;
  const MlClub *club = ml_find_club(c, plan->team_id);
  if (!club || plan->player_count != club->count) return 0;
  for (uint32_t i = 0; i < plan->player_count; i++) {
    uint32_t native;
    memcpy(&native, plan->players[i].player_id, sizeof(native));
    /* Career presets contain canonical native IDs, never match-local,
     * XOR-protected tmpdb locators. The native adapter translates at entry. */
    const MlPlayer *p = ml_find_native(c, native);
    if (!p || p->club != plan->team_id) return 0;
    for (uint32_t j=0; j<i; j++) {
      uint32_t previous;
      memcpy(&previous, plan->players[j].player_id, sizeof(previous));
      if (previous == native) return 0;
    }
  }
  return 1;
}
int ml_store_plan(MasterLeague *c, const GameplanPreset *plan) {
  if (!ml_plan_compatible(c, plan)) return 0;
  MlClub *club = ml_club(c, plan->team_id);
  uint32_t ordered[ML_SQUAD_SIZE] = {0};
  for (uint32_t i = 0; i < plan->player_count; i++) {
    uint32_t native;
    memcpy(&native, plan->players[i].player_id, sizeof(native));
    const MlPlayer *p = ml_find_native(c, native);
    ordered[plan->players[i].order_no] = (uint32_t)(p - c->players);
  }
  memcpy(club->players, ordered, sizeof(ordered));
  c->current_plan = *plan;
  return 1;
}

static int ml_u32_compare(const void *a, const void *b) {
  const uint32_t x = *(const uint32_t *)a, y = *(const uint32_t *)b;
  return x < y ? -1 : x > y;
}
int ml_valid(const MasterLeague *c) {
  if (!c || c->club_count < 2u || c->club_count > ML_MAX_CLUBS ||
      !c->player_count || c->player_count > ML_MAX_PLAYERS ||
      !c->season || c->season > 100u || c->day > 365u || c->wage_week != c->day/7u ||
      !c->settings.club || !c->settings.competition_id || c->settings.difficulty>6u ||
      c->settings.match_minutes<5u || c->settings.match_minutes>30u ||
      (c->settings.condition!=2u && c->settings.condition!=5u) ||
      c->settings.injuries>1u || c->settings.max_substitutions>12u ||
      c->seasons_completed!=c->season-1u || c->wages_paid<0 ||
      c->match_income<0 || c->prize_income<0 ||
      !ml_manager_name_valid(c->manager_name) || !c->manager_nationality ||
      !c->content_id[0] || !memchr(c->content_id, 0, sizeof(c->content_id)) ||
      c->league.team_count < 2u || c->league.team_count > LEAGUE_MAX_TEAMS ||
      c->league.matchday_count > LEAGUE_MAX_MATCHDAYS ||
      c->league.active_matchday > c->league.matchday_count ||
      c->league.fixture_count > LEAGUE_MAX_FIXTURES ||
      c->league.scorer_count > LEAGUE_MAX_SCORERS ||
      c->league.human_count!=1u || c->league.human_teams[0]!=c->settings.club ||
      c->league.home_away!=1u || c->league.first_match_started>1u ||
      (c->league.phase!=LEAGUE_PHASE_TABLE && c->league.phase!=LEAGUE_PHASE_COMPLETE) ||
      c->league.reserved[0] != LEAGUE_SYSTEM_STANDINGS ||
      c->cup_enabled > 1u || c->cup.round_count > CUP_MAX_ROUNDS ||
      c->cup.active_round >= CUP_MAX_ROUNDS || c->cup.history_count > CUP_MAX_FIXTURES ||
      !ml_find_club(c, c->settings.club)) return 0;
  uint8_t *seen = calloc(c->player_count, 1u);
  uint32_t *ids = malloc(c->player_count * sizeof(*ids));
  if (!seen || !ids) { free(seen); free(ids); return 0; }
  int valid = 1;
  for (uint32_t i = 0; valid && i < c->club_count; i++) {
    const MlClub *club = &c->clubs[i];
    if (!club->team || club->count < 11u || club->count > ML_SQUAD_SIZE ||
        club->cash < -INT64_C(1000000000000) || club->cash>INT64_C(1000000000000) ||
        club->wage_budget>100000000u) { valid=0; break; }
    for (uint32_t j = 0; j < i; j++) if (club->team == c->clubs[j].team) valid=0;
    for (uint32_t p = 0; valid && p < club->count; p++) {
      const uint32_t index = club->players[p];
      if (index >= c->player_count || seen[index] || c->players[index].club != club->team)
        valid = 0;
      else seen[index] = 1u;
    }
  }
  for (uint32_t i = 0; valid && i < c->player_count; i++) {
    const MlPlayer *p = &c->players[i];
    if (!p->identity || !p->native_id || !p->name[0] ||
        !memchr(p->name,0,sizeof(p->name)) || !p->overall || p->overall > 99u ||
        p->position > 12u || p->shirt > 99u || (p->club && !seen[i]) ||
        p->wage > 1000000u || p->contract_end > c->season + 5u) valid=0;
    ids[i] = p->identity;
  }
  if (valid) {
    qsort(ids, c->player_count, sizeof(*ids), ml_u32_compare);
    for (uint32_t i=1; i<c->player_count; i++) if (ids[i] == ids[i-1]) valid=0;
    for (uint32_t i=0; i<c->player_count; i++) ids[i]=c->players[i].native_id;
    qsort(ids, c->player_count, sizeof(*ids), ml_u32_compare);
    for (uint32_t i=1; i<c->player_count; i++) if (ids[i] == ids[i-1]) valid=0;
  }
  const uint32_t n=c->league.team_count;
  if(c->league.fixture_count!=n*(n-1u) || c->league.matchday_count!=(((n+1u)&~1u)-1u)*2u ||
      (c->league.phase==LEAGUE_PHASE_COMPLETE)!=(c->league.active_matchday==c->league.matchday_count) ||
      !c->target_rank || c->target_rank>n || c->last_rank>n) valid=0;
  uint32_t cursor=0u;
  for (uint32_t d=0; valid && d<c->league.matchday_count; d++) {
    if (c->league.matchday_first[d]!=cursor || c->league.matchday_fixture_count[d]!=n/2u) valid=0;
    cursor+=c->league.matchday_fixture_count[d];
    if(cursor>c->league.fixture_count) valid=0;
  }
  uint8_t pairs[LEAGUE_MAX_TEAMS][LEAGUE_MAX_TEAMS]={{0}};
  LeagueStanding expected[LEAGUE_MAX_TEAMS]={{0}};
  for(uint32_t i=0;valid && i<n;i++) {
    expected[i].team=c->league.standings[i].team;
    if(!ml_find_club(c,expected[i].team)) valid=0;
    for(uint32_t j=0;j<i;j++) if(expected[i].team==expected[j].team) valid=0;
  }
  for (uint32_t i=0; valid && i<c->league.fixture_count; i++) {
    const LeagueFixture *f=&c->league.fixtures[i];
    if (!ml_find_club(c,f->home) || !ml_find_club(c,f->away) || f->home==f->away ||
        f->home_goals>99u || f->away_goals>99u || f->complete>1u || f->simulated>1u) { valid=0; break; }
    uint32_t h=n,a=n;
    for(uint32_t j=0;j<n;j++) { if(expected[j].team==f->home)h=j;if(expected[j].team==f->away)a=j; }
    if(h==n || a==n || pairs[h][a]++) { valid=0;break; }
    const uint32_t d=i/(n/2u);
    if((f->complete!=0u)!=(d<c->league.active_matchday)) { valid=0;break; }
    if(f->complete) {
      LeagueStanding *home=&expected[h],*away=&expected[a];
      home->played++;away->played++;
      home->goals_for+=f->home_goals;home->goals_against+=f->away_goals;
      away->goals_for+=f->away_goals;away->goals_against+=f->home_goals;
      if(f->home_goals>f->away_goals){home->wins++;away->losses++;home->points+=3u;}
      else if(f->away_goals>f->home_goals){away->wins++;home->losses++;away->points+=3u;}
      else{home->draws++;away->draws++;home->points++;away->points++;}
    } else if(f->home_goals || f->away_goals || f->simulated) valid=0;
  }
  if(valid && memcmp(expected,c->league.standings,n*sizeof(*expected)))valid=0;
  for(uint32_t i=0;valid && i<c->league.scorer_count;i++) {
    const LeagueScorer *s=&c->league.scorers[i];
    if(!s->base_id || !s->goals || !ml_find_club(c,s->team) || !memchr(s->name,0,sizeof(s->name)))valid=0;
  }
  if(valid && c->cup_enabled) {
    const CupTournament *cup=&c->cup;
    uint32_t bracket=2u,rounds=1u;
    while(bracket<cup->team_count && bracket<CUP_MAX_TEAMS){bracket*=2u;rounds++;}
    if(cup->team_count<2u || cup->team_count>CUP_MAX_TEAMS || cup->bracket_size!=bracket ||
       cup->round_count!=rounds || cup->active_round>=rounds || cup->human_count!=1u ||
       cup->human_teams[0]!=c->settings.club || cup->home_away || cup->third_place_enabled) valid=0;
    for(uint32_t r=0;valid && r<rounds;r++)for(uint32_t i=0;i<(bracket>>(r+1u));i++) {
      const CupFixture *f=&cup->fixtures[r][i];
      if((f->home && !ml_find_club(c,f->home)) || (f->away && !ml_find_club(c,f->away)) ||
         (f->home && f->home==f->away) || f->complete>1u || f->home_goals>99u || f->away_goals>99u ||
         (f->complete && (!f->winner || (f->winner!=f->home && f->winner!=f->away))) ||
         (!f->complete && f->winner) || (r<cup->active_round && !f->complete)) valid=0;
    }
    if(cup->champion && (cup->champion!=cup->fixtures[rounds-1u][0].winner ||
        !cup->fixtures[rounds-1u][0].complete))valid=0;
  }
  for(uint32_t i=0;valid && i<GAMEPLAN_PRESET_SLOTS;i++) {
    if(c->presets[i].player_count && (!gameplan_preset_valid(&c->presets[i]) ||
        c->presets[i].team_id!=c->settings.club)) valid=0;
  }
  if(valid && c->current_plan.player_count && !ml_plan_compatible(c,&c->current_plan))valid=0;
  free(seen); free(ids);
  return valid;
}

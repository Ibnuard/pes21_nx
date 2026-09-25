#include "competition_frontend.h"

#include <stdio.h>
#include <string.h>

#include "exhibition_team_catalog.h"
#include "fl26_cup_catalog_generated.h"
#include "ue4_hooks.h"
#include "cup_tournament.h"
#include "cup_save.h"
#include "league_save.h"

#define COMPETITION_MAX_PLAYER_SLOTS 8u
#define COMPETITION_SAVE_SLOT_COUNT 3u
#define COMPETITION_BUTTON_B (1u << 0)
#define COMPETITION_BUTTON_A (1u << 1)
#define COMPETITION_BUTTON_Y (1u << 2)
#define COMPETITION_BUTTON_X (1u << 3)
#define COMPETITION_BUTTON_L (1u << 4)
#define COMPETITION_BUTTON_R (1u << 7)
#define COMPETITION_BUTTON_UP (1u << 10)
#define COMPETITION_BUTTON_DOWN (1u << 11)
#define COMPETITION_BUTTON_LEFT (1u << 12)
#define COMPETITION_BUTTON_RIGHT (1u << 13)

static CompetitionFrontendState frontend_state;
static uint32_t frontend_focus;
static uint32_t frontend_pending_action;
static uint32_t frontend_controller_gate_request;
static uint32_t frontend_input_consumed;
static uint32_t frontend_skip_input_tick;
static uint32_t frontend_buttons_latched;
static uint32_t frontend_closing;
static char frontend_status[96];

static uint32_t cup_player_count = 1;
static uint32_t cup_team_count = 16;
static uint32_t cup_select = 0;
static uint32_t cup_com_level = 3;
static uint32_t cup_home_away;
static uint32_t cup_third_place;
static uint32_t cup_game_time = 10;
static uint32_t cup_extra_time = 1;
static uint32_t cup_max_substitutions = 5;
static uint32_t cup_injuries = 1;
static uint32_t cup_ball_index;
static uint32_t cup_var = 1;
static uint32_t cup_general_open;
static uint32_t cup_general_focus;
static uint32_t cup_team_catalog_index[COMPETITION_MAX_PLAYER_SLOTS];
static uint8_t cup_team_selected[COMPETITION_MAX_PLAYER_SLOTS];
static uint32_t cup_team_picker_active;
static uint32_t cup_team_picker_category;
static uint32_t cup_team_picker_phase;
static uint32_t cup_team_picker_focus;
static uint32_t cup_team_picker_scroll;
static uint8_t cup_slot_valid[COMPETITION_SAVE_SLOT_COUNT];
static uint8_t cup_slot_completed[COMPETITION_SAVE_SLOT_COUNT];
static uint32_t cup_slot_round[COMPETITION_SAVE_SLOT_COUNT];
static CupTournament cup_tournament;
static uint32_t cup_tournament_valid;
static uint32_t cup_pending_round;
static uint32_t cup_pending_index;
static uint32_t cup_match_active;
static uint32_t cup_match_result_received;
static uint32_t cup_champion_presentation_pending;
static uint32_t cup_match_swapped;
static uint32_t cup_bracket_stage;
static uint32_t cup_bracket_page;
static CompetitionEntryDraft cup_draft;
static uint32_t cup_bracket_editing;
static uint32_t cup_opening_rule_popup;
static uint32_t cup_bracket_slot_focus;
static uint32_t cup_bracket_swap_source = UINT32_MAX;
static uint32_t cup_first_match_started;
static uint32_t cup_slots_saving;
static uint32_t cup_active_slot = UINT32_MAX;

static uint32_t league_player_count = 1u;
static uint32_t league_team_count = 16u;
static uint32_t league_home_away;
static CompetitionEntryDraft league_draft;
static LeagueTournament league_tournament;
static uint32_t league_tournament_valid;
static uint32_t league_table_page;
static uint32_t league_schedule_page;
static uint32_t league_bracket_round;
static uint32_t league_bracket_page;
static uint32_t league_scorers_open;
static uint32_t league_teams_editing;
static uint32_t league_team_slot_focus;
static uint32_t league_match_active;
static uint32_t league_match_result_received;
static uint32_t league_match_swapped;
static uint32_t league_pending_fixture;
static uint32_t league_pending_round;
static uint32_t league_pending_index;
static uint32_t league_slots_saving;
static uint32_t league_active_slot = UINT32_MAX;
static uint8_t league_slot_valid[LEAGUE_SAVE_SLOTS];
static uint8_t league_slot_completed[LEAGUE_SAVE_SLOTS];

enum {
  CUP_HUB_ACTION_TEAMS = 0,
  CUP_HUB_ACTION_NEXT = 1,
  CUP_HUB_ACTION_GENERAL = 2,
  CUP_HUB_ACTION_SAVE = 3,
};

static uint32_t competition_bracket_stage_count(void) {
  /* The last match stage shows semi-final -> final; champion gets a page.
   * A two-team Cup has a single Final, so add its Champion page explicitly. */
  return cup_tournament.round_count == 1u ? 2u
      : cup_tournament.round_count;
}

static uint32_t competition_bracket_stage_pages(uint32_t stage) {
  const uint32_t stages = competition_bracket_stage_count();
  if (stage >= stages) return 0u;
  if (stage + 2u >= stages) return 1u;
  const uint32_t fixtures = cup_tournament_fixture_count(&cup_tournament,
                                                          stage);
  return (fixtures + 1u) / 2u;
}

static uint32_t competition_bracket_view_count(void) {
  uint32_t views = 0;
  for (uint32_t stage = 0; stage < competition_bracket_stage_count(); stage++)
    views += competition_bracket_stage_pages(stage);
  return views;
}

static void competition_bracket_view_active(void) {
  const uint32_t stages = competition_bracket_stage_count();
  cup_bracket_stage = !stages ? 0u
      : cup_tournament.champion ? stages - 1u
      : cup_tournament.active_round < stages - 1u
          ? cup_tournament.active_round : stages - 2u;
  cup_bracket_page = 0u;
  uint32_t next_round = 0, next_index = 0;
  if (cup_tournament_next_human(&cup_tournament, &next_round, &next_index) &&
      next_round == cup_bracket_stage &&
      competition_bracket_stage_pages(cup_bracket_stage) > 1u)
    cup_bracket_page = next_index / 2u;
}

static void competition_clear_status(void) {
  frontend_status[0] = '\0';
}

static void competition_set_status(const char *status) {
  if (!status)
    status = "";
  snprintf(frontend_status, sizeof(frontend_status), "%s", status);
}

static void competition_reset_cup_setup(void) {
  memset(&cup_tournament, 0, sizeof(cup_tournament));
  cup_tournament_valid = 0;
  cup_bracket_stage = 0;
  cup_bracket_page = 0;
  cup_match_active = 0;
  cup_match_result_received = 0;
  cup_champion_presentation_pending = 0;
  memset(&cup_draft, 0, sizeof(cup_draft));
  cup_bracket_editing = 0;
  cup_opening_rule_popup = 0;
  cup_bracket_slot_focus = 0;
  cup_bracket_swap_source = UINT32_MAX;
  cup_first_match_started = 0;
  cup_slots_saving = 0;
  cup_active_slot = UINT32_MAX;
  cup_player_count = 1;
  cup_team_count = 16;
  cup_select = 0;
  cup_com_level = 3;
  cup_home_away = 0;
  cup_third_place = 0;
  cup_game_time = 10;
  cup_extra_time = 1;
  cup_max_substitutions = 5;
  cup_injuries = 1;
  cup_ball_index = 0;
  cup_var = 1;
  cup_general_open = 0;
  cup_general_focus = 0;
  cup_team_picker_active = 0;
  cup_team_picker_category = 0;
  cup_team_picker_phase = 1;
  cup_team_picker_focus = 0;
  cup_team_picker_scroll = 0;
  for (uint32_t index = 0; index < COMPETITION_MAX_PLAYER_SLOTS; index++) {
    cup_team_catalog_index[index] = 0;
    cup_team_selected[index] = 0;
  }
  competition_clear_status();
}

static void competition_reset_league_setup(void) {
  memset(&league_draft, 0, sizeof(league_draft));
  memset(&league_tournament, 0, sizeof(league_tournament));
  league_player_count = 1u;
  league_team_count = 16u;
  league_home_away = 0u;
  league_tournament_valid = 0u;
  league_table_page = 0u;
  league_schedule_page = 0u;
  league_bracket_round = 0u;
  league_bracket_page = 0u;
  league_scorers_open = 0u;
  league_teams_editing = 0u;
  league_team_slot_focus = 0u;
  league_match_active = 0u;
  league_match_result_received = 0u;
  league_match_swapped = 0u;
  league_pending_fixture = 0u;
  league_pending_round = 0u;
  league_pending_index = 0u;
  league_slots_saving = 0u;
  league_active_slot = UINT32_MAX;
  cup_general_open = 0u;
  cup_general_focus = 0u;
  cup_team_picker_active = 0u;
  cup_team_picker_category = 0u;
  cup_team_picker_phase = 1u;
  cup_team_picker_focus = 0u;
  cup_team_picker_scroll = 0u;
  cup_com_level = 3u;
  cup_game_time = 10u;
  cup_extra_time = 1u;
  cup_max_substitutions = 5u;
  cup_injuries = 1u;
  cup_ball_index = 0u;
  cup_var = 1u;
  competition_clear_status();
}

static int competition_cup_is_custom(void) {
  return cup_select == FL26_CUP_CUSTOM_INDEX;
}

static int competition_picker_unrestricted(void) {
  return frontend_state == COMPETITION_FRONTEND_LEAGUE_HUB ||
         competition_cup_is_custom();
}

static const Fl26CupCatalogEntry *competition_cup_entry(void) {
  return &fl26_cup_catalog[cup_select < FL26_CUP_CATALOG_COUNT
                               ? cup_select : FL26_CUP_CUSTOM_INDEX];
}

static uint32_t competition_cup_effective_team_count(void) {
  return cup_team_count;
}

static uint32_t competition_cup_default_team_count(void) {
  if (competition_cup_is_custom()) return 8u;
  return cup_select == 5u ? 32u : 16u;
}

static int competition_cup_setting_visible(uint32_t row) {
  return row < 5u;
}

static int competition_cup_teams_complete(void) {
  return competition_draft_ready(&cup_draft);
}

static int competition_cup_opening_has_player_match(
    const CompetitionEntryDraft *draft) {
  if (!draft || !draft->team_count) return 0;
  uint32_t opening = 1u;
  while (opening * 2u < draft->team_count) opening *= 2u;
  for (uint32_t fixture = 0; fixture < opening; fixture++) {
    const uint32_t home = competition_draft_fixture_slot(draft, fixture, 0u);
    const uint32_t away = competition_draft_fixture_slot(draft, fixture, 1u);
    if (home == UINT32_MAX || away == UINT32_MAX) continue;
    if (draft->owners[home] || draft->owners[away]) return 1;
  }
  return 0;
}

static void competition_set_state(CompetitionFrontendState state,
                                  uint32_t focus) {
  frontend_state = state;
  frontend_focus = focus;
  if (state != COMPETITION_FRONTEND_CUP_BRACKET &&
      state != COMPETITION_FRONTEND_LEAGUE_HUB)
    cup_general_open = 0u;
  cup_opening_rule_popup = 0u;
  frontend_pending_action = COMPETITION_ACTION_NONE;
  competition_clear_status();
}

static uint32_t competition_item_count_for_state(void) {
  switch (frontend_state) {
    case COMPETITION_FRONTEND_MATCH_MODE:
      return 2;
    case COMPETITION_FRONTEND_MODES:
      return 3;
    case COMPETITION_FRONTEND_CUP_LANDING:
      return 2;
    case COMPETITION_FRONTEND_CUP_SLOTS:
      return COMPETITION_SAVE_SLOT_COUNT;
    case COMPETITION_FRONTEND_CUP_SETTINGS:
      /* Five Cup rule rows plus the floating Next action. Back is the
       * global B affordance, matching the Hub Settings page. */
      return 6;
    case COMPETITION_FRONTEND_CUP_TEAMS:
      /* Team rows plus the floating Next action; B backs out of the page. */
      return cup_player_count + 1u;
    case COMPETITION_FRONTEND_CUP_BRACKET:
      return cup_tournament.champion ? 1u : 4u;
    case COMPETITION_FRONTEND_LEAGUE_LANDING:
      return 2u;
    case COMPETITION_FRONTEND_LEAGUE_SLOTS:
      return LEAGUE_SAVE_SLOTS;
    case COMPETITION_FRONTEND_LEAGUE_SETTINGS:
      return 5u;
    case COMPETITION_FRONTEND_LEAGUE_HUB:
      return league_tournament.phase == LEAGUE_PHASE_COMPLETE ? 1u : 4u;
    case COMPETITION_FRONTEND_CUP_CHECKPOINT:
    case COMPETITION_FRONTEND_NOTICE:
      return 1;
    default:
      return 0;
  }
}

static int competition_team_is_allowed(uint32_t team_id) {
  if (!exhibition_team_catalog_find(team_id))
    return 0;
  if (competition_picker_unrestricted())
    return 1;
  const Fl26CupCatalogEntry *cup = competition_cup_entry();
  for (uint32_t index = 0; index < cup->pool_count; index++)
    if (cup->team_ids[index] == team_id)
      return 1;
  return 0;
}

static uint32_t competition_cup_picker_count(void) {
  if (cup_team_picker_phase == 1)
    return competition_picker_unrestricted()
        ? EXHIBITION_TEAM_CATEGORY_COUNT : 1u;
  if (cup_team_picker_phase == 2 && !competition_picker_unrestricted())
    return competition_cup_entry()->pool_count;
  if (cup_team_picker_phase == 2 &&
      cup_team_picker_category < EXHIBITION_TEAM_CATEGORY_COUNT)
    return exhibition_team_categories[cup_team_picker_category].team_count;
  return 0;
}

static void competition_cup_picker_center_scroll(void) {
  const uint32_t count = competition_cup_picker_count();
  if (count <= 5u || cup_team_picker_focus <= 2u) {
    cup_team_picker_scroll = 0;
  } else if (cup_team_picker_focus + 2u >= count) {
    cup_team_picker_scroll = count - 5u;
  } else {
    cup_team_picker_scroll = cup_team_picker_focus - 2u;
  }
}

static void competition_adjust_setting(int direction) {
  if (!direction) return;
  if (frontend_state == COMPETITION_FRONTEND_LEAGUE_SETTINGS) {
    switch (frontend_focus) {
      case 1u:
        if (direction > 0 && league_player_count <
                                 COMPETITION_MAX_PLAYER_SLOTS &&
            league_player_count < league_team_count)
          league_player_count++;
        else if (direction < 0 && league_player_count > 1u)
          league_player_count--;
        break;
      case 2u:
        if (direction > 0 && league_team_count < LEAGUE_MAX_TEAMS)
          league_team_count++;
        else if (direction < 0 && league_team_count > 2u)
          league_team_count--;
        if (league_player_count > league_team_count)
          league_player_count = league_team_count;
        break;
      case 3u: league_home_away = !league_home_away; break;
      default: break;
    }
    competition_clear_status();
    return;
  }
  if (frontend_state != COMPETITION_FRONTEND_CUP_SETTINGS) return;
  switch (frontend_focus) {
    case 0:
      cup_select = direction > 0
          ? (cup_select + 1u) % FL26_CUP_CATALOG_COUNT
          : (cup_select + FL26_CUP_CATALOG_COUNT - 1u) %
                FL26_CUP_CATALOG_COUNT;
      cup_player_count = 1;
      cup_team_selected[0] = 0;
      cup_team_count = competition_cup_default_team_count();
      break;
    case 1:
      if (direction > 0) {
        if (cup_player_count < COMPETITION_MAX_PLAYER_SLOTS &&
            cup_player_count < competition_cup_effective_team_count()) {
          cup_team_selected[cup_player_count] = 0;
          cup_player_count++;
        }
      } else if (cup_player_count > 1) {
        cup_player_count--;
      }
      if (cup_player_count < 1)
        cup_player_count = 1;
      break;
    case 2:
      if (!competition_cup_is_custom() && cup_select >= 3u)
        break;
      if (!competition_cup_is_custom()) {
        const uint32_t maximum = competition_cup_entry()->bracket_limit;
        if (direction > 0)
          cup_team_count = cup_team_count >= maximum ? 8u
              : cup_team_count == 8u ? 16u : maximum;
        else
          cup_team_count = cup_team_count <= 8u ? maximum
              : cup_team_count == maximum ? 16u : 8u;
      } else if (direction > 0) {
        if (cup_team_count < 32)
          cup_team_count++;
      } else if (cup_team_count > 2) {
        cup_team_count--;
      }
      if (cup_player_count > cup_team_count)
        cup_player_count = cup_team_count;
      if (cup_team_count < 4u)
        cup_third_place = 0u;
      break;
    case 3:
      cup_home_away = !cup_home_away;
      break;
    case 4:
      if (competition_cup_effective_team_count() >= 4u)
        cup_third_place = !cup_third_place;
      break;
    default:
      break;
  }
  competition_clear_status();
}

static uint32_t competition_general_first_row(void) {
  const uint32_t players = frontend_state == COMPETITION_FRONTEND_LEAGUE_HUB
      ? league_player_count : cup_player_count;
  const uint32_t teams = frontend_state == COMPETITION_FRONTEND_LEAGUE_HUB
      ? league_team_count : competition_cup_effective_team_count();
  return players >= teams
      ? 1u : 0u;
}

static uint32_t competition_general_row(uint32_t visible_index) {
  uint32_t row = visible_index + competition_general_first_row();
  return row >= 3u ? row + 1u : row; /* Penalties are always ON in Cup. */
}

static void competition_adjust_general(int direction) {
  if (!direction) return;
  const uint32_t row = competition_general_row(cup_general_focus);
  switch (row) {
    case 0:
      cup_com_level = direction > 0 ? (cup_com_level + 1u) % 7u
                                    : (cup_com_level + 6u) % 7u;
      break;
    case 1:
      if (direction < 0)
        cup_game_time = cup_game_time <= 3u ? 10u
                            : cup_game_time <= 5u ? 3u : cup_game_time - 1u;
      else
        cup_game_time = cup_game_time >= 10u ? 3u
                            : cup_game_time < 5u ? 5u : cup_game_time + 1u;
      break;
    case 2: cup_extra_time = !cup_extra_time; break;
    case 4:
      cup_max_substitutions = direction > 0
          ? (cup_max_substitutions >= 5u ? 3u : cup_max_substitutions + 1u)
          : (cup_max_substitutions <= 3u ? 5u : cup_max_substitutions - 1u);
      break;
    case 5: cup_injuries = !cup_injuries; break;
    case 6:
      cup_ball_index = direction > 0 ? (cup_ball_index + 1u) % 10u
                                     : (cup_ball_index + 9u) % 10u;
      break;
    case 7: cup_var = !cup_var; break;
  }
}

static void competition_move_focus(int direction) {
  const uint32_t count = competition_item_count_for_state();
  if (!count || !direction)
    return;
  for (uint32_t attempt = 0; attempt < count; attempt++) {
    uint32_t candidate = direction == 1
                             ? (frontend_focus ? frontend_focus - 1u
                                                : count - 1u)
                             : (frontend_focus + 1u) % count;
    frontend_focus = candidate;
    if (frontend_state == COMPETITION_FRONTEND_CUP_SETTINGS &&
        candidate < 5u && !competition_cup_setting_visible(candidate))
      continue;
    return;
  }
}

static void competition_back(void) {
  if (cup_opening_rule_popup) {
    cup_opening_rule_popup = 0u;
    return;
  }
  if (cup_general_open) {
    cup_general_open = 0u;
    return;
  }
  switch (frontend_state) {
    case COMPETITION_FRONTEND_MATCH_MODE:
    case COMPETITION_FRONTEND_MODES:
      competition_frontend_close();
      return;
    case COMPETITION_FRONTEND_CUP_LANDING:
      competition_set_state(COMPETITION_FRONTEND_MODES, 0);
      return;
    case COMPETITION_FRONTEND_CUP_SLOTS:
      if (cup_slots_saving) {
        competition_set_state(COMPETITION_FRONTEND_CUP_BRACKET,
                              CUP_HUB_ACTION_SAVE);
        return;
      }
      competition_set_state(COMPETITION_FRONTEND_CUP_LANDING, 0);
      return;
    case COMPETITION_FRONTEND_CUP_SETTINGS:
      competition_set_state(COMPETITION_FRONTEND_CUP_LANDING, 0);
      return;
    case COMPETITION_FRONTEND_LEAGUE_LANDING:
      competition_set_state(COMPETITION_FRONTEND_MODES, 1u);
      return;
    case COMPETITION_FRONTEND_LEAGUE_SLOTS:
      if (league_slots_saving) {
        competition_set_state(COMPETITION_FRONTEND_LEAGUE_HUB, 3u);
        return;
      }
      competition_set_state(COMPETITION_FRONTEND_LEAGUE_LANDING, 0u);
      return;
    case COMPETITION_FRONTEND_LEAGUE_SETTINGS:
      competition_set_state(COMPETITION_FRONTEND_LEAGUE_LANDING, 0u);
      return;
    case COMPETITION_FRONTEND_LEAGUE_HUB:
      if (league_tournament.phase == LEAGUE_PHASE_COMPLETE) return;
      if (league_teams_editing) {
        league_teams_editing = 0u;
        frontend_focus = 0u;
        return;
      }
      competition_frontend_close();
      return;
    case COMPETITION_FRONTEND_CUP_TEAMS:
      if (cup_team_picker_active) {
        cup_team_picker_active = 0;
        competition_clear_status();
        return;
      }
      competition_set_state(COMPETITION_FRONTEND_CUP_SETTINGS, 0);
      return;
    case COMPETITION_FRONTEND_CUP_BRACKET:
      if (cup_tournament.champion) return;
      if (cup_bracket_editing) {
        if (cup_bracket_swap_source != UINT32_MAX) {
          cup_bracket_swap_source = UINT32_MAX;
          competition_clear_status();
          return;
        }
        cup_bracket_editing = 0;
        frontend_focus = CUP_HUB_ACTION_TEAMS;
        return;
      }
      competition_frontend_close();
      return;
    case COMPETITION_FRONTEND_CUP_CHECKPOINT:
      competition_set_state(COMPETITION_FRONTEND_CUP_BRACKET, 0);
      return;
    case COMPETITION_FRONTEND_NOTICE:
      competition_set_state(COMPETITION_FRONTEND_MODES, 0);
      return;
    default:
      competition_frontend_close();
      return;
  }
}

static void competition_sync_human_teams(void) {
  memset(cup_team_catalog_index, 0, sizeof(cup_team_catalog_index));
  memset(cup_team_selected, 0, sizeof(cup_team_selected));
  for (uint32_t slot = 0; slot < cup_draft.team_count; slot++) {
    const uint32_t owner = cup_draft.owners[slot];
    if (!owner || owner > COMPETITION_MAX_PLAYER_SLOTS) continue;
    cup_team_catalog_index[owner - 1u] = cup_draft.teams[slot];
    cup_team_selected[owner - 1u] = cup_draft.teams[slot] != 0u;
  }
}

static void competition_rebuild_cup_bracket(void) {
  const uint32_t target = cup_draft.team_count;
  cup_tournament_valid = 0;
  memset(&cup_tournament, 0, sizeof(cup_tournament));
  if (!target) return;
  uint32_t bracket_size = 2u;
  while (bracket_size < target) bracket_size <<= 1u;
  const uint32_t opening = bracket_size / 2u;
  cup_tournament.team_count = target;
  cup_tournament.bracket_size = bracket_size;
  cup_tournament.human_count = cup_draft.player_count;
  cup_tournament.seed = cup_draft.seed;
  for (uint32_t n = bracket_size; n > 1u; n >>= 1u)
    cup_tournament.round_count++;
  for (uint32_t fixture = 0; fixture < opening; fixture++) {
    CupFixture *entry = &cup_tournament.fixtures[0][fixture];
    const uint32_t home_slot = competition_draft_fixture_slot(
        &cup_draft, fixture, 0u);
    const uint32_t away_slot = competition_draft_fixture_slot(
        &cup_draft, fixture, 1u);
    entry->home = home_slot < target ? cup_draft.teams[home_slot] : 0u;
    entry->away = away_slot < target ? cup_draft.teams[away_slot] : 0u;
    if (away_slot == UINT32_MAX) {
      entry->winner = entry->home;
      entry->complete = 1u;
    }
  }
  if (competition_draft_ready(&cup_draft)) {
    uint32_t participants[CUP_MAX_TEAMS] = {0};
    uint32_t humans[COMPETITION_MAX_PLAYER_SLOTS] = {0};
    for (uint32_t fixture = 0; fixture < opening; fixture++) {
      const uint32_t home_slot = competition_draft_fixture_slot(
          &cup_draft, fixture, 0u);
      const uint32_t away_slot = competition_draft_fixture_slot(
          &cup_draft, fixture, 1u);
      participants[fixture] = cup_draft.teams[home_slot];
      if (away_slot != UINT32_MAX)
        participants[opening + fixture] = cup_draft.teams[away_slot];
    }
    competition_sync_human_teams();
    for (uint32_t i = 0; i < cup_player_count; i++)
      humans[i] = cup_team_catalog_index[i];
    cup_tournament_valid = cup_tournament_init(
        &cup_tournament, participants, target, humans, cup_player_count,
        cup_draft.seed);
    if (cup_tournament_valid)
      cup_tournament_set_rules(&cup_tournament, cup_home_away,
                               cup_third_place);
  } else {
    competition_sync_human_teams();
  }
  if (!cup_tournament_valid)
    cup_tournament_set_rules(&cup_tournament, cup_home_away,
                             cup_third_place);
  competition_bracket_view_active();
}

static void competition_open_bracket(void) {
  const uint32_t target = competition_cup_effective_team_count();
  if (!competition_draft_init(&cup_draft, target, cup_player_count,
                               0x26f00d21u ^ target ^ (cup_select << 16))) {
    competition_set_status("CUP BRACKET COULD NOT BE CREATED");
    return;
  }
  competition_rebuild_cup_bracket();
  cup_bracket_editing = 0;
  cup_opening_rule_popup = 0;
  cup_bracket_slot_focus = 0;
  cup_bracket_swap_source = UINT32_MAX;
  cup_first_match_started = 0;
  cup_champion_presentation_pending = 0;
  competition_set_state(COMPETITION_FRONTEND_CUP_BRACKET, 0);
}

static int competition_cup_save_valid(const CupSaveState *save) {
  return save && save->cup_select < FL26_CUP_CATALOG_COUNT &&
      save->team_count >= 2u && save->team_count <= CUP_MAX_TEAMS &&
      save->player_count >= 1u &&
      save->player_count <= COMPETITION_MAX_PLAYER_SLOTS &&
      save->player_count <= save->team_count && save->com_level <= 6u &&
      save->game_time >= 3u && save->game_time <= 10u &&
      save->max_substitutions >= 3u &&
      save->max_substitutions <= 5u &&
      save->home_away <= 1u && save->third_place <= 1u &&
      save->injuries <= 1u && save->ball_index < 10u &&
      save->var_enabled <= 1u &&
      save->tournament.home_away == save->home_away &&
      save->tournament.third_place_enabled ==
          (save->third_place && save->team_count >= 4u) &&
      save->draft.team_count == save->team_count &&
      save->draft.player_count == save->player_count &&
      save->tournament.team_count == save->team_count &&
      save->tournament.bracket_size >= 2u &&
      save->tournament.bracket_size <= CUP_MAX_TEAMS &&
      (!save->tournament_valid || competition_draft_ready(&save->draft));
}

static void competition_scan_cup_saves(void) {
  CupSaveState save;
  for (uint32_t slot = 0; slot < COMPETITION_SAVE_SLOT_COUNT; slot++) {
    cup_slot_valid[slot] = cup_save_read(slot, &save) &&
                           competition_cup_save_valid(&save);
    cup_slot_completed[slot] = cup_slot_valid[slot] &&
                               save.tournament.champion != 0u;
    cup_slot_round[slot] = cup_slot_valid[slot]
                               ? save.tournament.active_round : 0u;
  }
}

static int competition_load_cup_slot(uint32_t slot) {
  CupSaveState save;
  if (!cup_save_read(slot, &save) || !competition_cup_save_valid(&save))
    return 0;
  cup_select = save.cup_select;
  cup_player_count = save.player_count;
  cup_team_count = save.team_count;
  cup_com_level = save.com_level;
  cup_home_away = save.home_away;
  cup_third_place = save.third_place;
  cup_game_time = save.game_time;
  cup_extra_time = save.extra_time;
  cup_max_substitutions = save.max_substitutions;
  cup_injuries = save.injuries;
  cup_ball_index = save.ball_index;
  cup_var = save.var_enabled;
  cup_draft = save.draft;
  cup_tournament = save.tournament;
  cup_tournament_valid = save.tournament_valid;
  cup_first_match_started = save.first_match_started;
  cup_active_slot = slot;
  cup_bracket_editing = 0;
  cup_opening_rule_popup = 0;
  cup_bracket_slot_focus = 0;
  cup_bracket_swap_source = UINT32_MAX;
  cup_team_picker_active = 0;
  cup_match_active = 0;
  cup_champion_presentation_pending = 0;
  competition_sync_human_teams();
  competition_bracket_view_active();
  competition_set_state(COMPETITION_FRONTEND_CUP_BRACKET,
                        CUP_HUB_ACTION_TEAMS);
  return 1;
}

static int competition_save_cup_slot(uint32_t slot) {
  if (slot >= COMPETITION_SAVE_SLOT_COUNT || !cup_draft.team_count)
    return 0;
  CupSaveState save;
  memset(&save, 0, sizeof(save));
  save.cup_select = cup_select;
  save.player_count = cup_player_count;
  save.team_count = cup_team_count;
  save.com_level = cup_com_level;
  save.home_away = cup_home_away;
  save.third_place = cup_third_place;
  save.game_time = cup_game_time;
  save.extra_time = cup_extra_time;
  save.max_substitutions = cup_max_substitutions;
  save.injuries = cup_injuries;
  save.ball_index = cup_ball_index;
  save.var_enabled = cup_var;
  save.tournament_valid = cup_tournament_valid;
  save.first_match_started = cup_first_match_started;
  save.draft = cup_draft;
  save.tournament = cup_tournament;
  if (!cup_save_write(slot, &save)) return 0;
  cup_active_slot = slot;
  cup_slot_valid[slot] = 1;
  cup_slot_completed[slot] = cup_tournament.champion != 0u;
  cup_slot_round[slot] = cup_tournament.active_round;
  return 1;
}

static int competition_random_fill_cup(void) {
  uint32_t pool[COMPETITION_DRAFT_MAX_POOL];
  uint32_t count = 0;
  if (competition_cup_is_custom()) {
    for (uint32_t i = 0; i < EXHIBITION_TEAM_CATALOG_COUNT &&
                         count < COMPETITION_DRAFT_MAX_POOL; i++)
      pool[count++] = exhibition_team_catalog[i].team_id;
  } else {
    const Fl26CupCatalogEntry *cup = competition_cup_entry();
    for (uint32_t i = 0; i < cup->pool_count &&
                         count < COMPETITION_DRAFT_MAX_POOL; i++)
      pool[count++] = cup->team_ids[i];
  }
  if (!competition_draft_random_fill(&cup_draft, pool, count)) return 0;
  competition_rebuild_cup_bracket();
  return 1;
}

static void competition_rebuild_league(void) {
  league_tournament_valid = 0u;
  memset(&league_tournament, 0, sizeof(league_tournament));
  if (!competition_draft_ready(&league_draft)) return;
  uint32_t humans[COMPETITION_MAX_PLAYER_SLOTS] = {0};
  uint32_t human_count = 0u;
  for (uint32_t slot = 0; slot < league_draft.team_count; slot++)
    if (league_draft.owners[slot] &&
        human_count < COMPETITION_MAX_PLAYER_SLOTS)
      humans[human_count++] = league_draft.teams[slot];
  league_tournament_valid = league_tournament_init(
      &league_tournament, league_draft.teams, league_draft.team_count,
      humans, human_count, league_home_away,
      league_draft.seed);
}

static void competition_open_league_hub(void) {
  if (!competition_draft_init(&league_draft, league_team_count,
                               league_player_count,
                               0x26f04c45u ^ league_team_count ^
                                   (league_home_away << 16))) {
    competition_set_status("LEAGUE TABLE COULD NOT BE CREATED");
    return;
  }
  competition_rebuild_league();
  league_table_page = 0u;
  league_schedule_page = 0u;
  league_bracket_round = 0u;
  league_bracket_page = 0u;
  league_scorers_open = 0u;
  league_teams_editing = 0u;
  league_team_slot_focus = 0u;
  competition_set_state(COMPETITION_FRONTEND_LEAGUE_HUB, 0u);
}

static int competition_random_fill_league(void) {
  uint32_t pool[COMPETITION_DRAFT_MAX_POOL];
  uint32_t count = 0u;
  for (uint32_t i = 0; i < EXHIBITION_TEAM_CATALOG_COUNT &&
                       count < COMPETITION_DRAFT_MAX_POOL; i++)
    pool[count++] = exhibition_team_catalog[i].team_id;
  if (!competition_draft_random_fill(&league_draft, pool, count)) return 0;
  competition_rebuild_league();
  return 1;
}

static int competition_league_save_valid(const LeagueSaveState *save) {
  if (!save || save->team_count < 2u ||
      save->team_count > LEAGUE_MAX_TEAMS ||
      save->player_count < 1u ||
      save->player_count > COMPETITION_MAX_PLAYER_SLOTS ||
      save->player_count > save->team_count ||
      save->com_level > 6u || save->home_away > 1u ||
      save->game_time < 3u || save->game_time > 10u ||
      save->max_substitutions < 3u ||
      save->max_substitutions > 5u || save->injuries > 1u ||
      save->ball_index >= 10u || save->var_enabled > 1u ||
      save->tournament_valid > 1u ||
      save->draft.team_count != save->team_count ||
      save->draft.player_count != save->player_count)
    return 0;
  if (!save->tournament_valid)
    return !save->tournament.first_match_started;
  return competition_draft_ready(&save->draft) &&
      save->tournament.team_count == save->team_count &&
      save->tournament.home_away == save->home_away &&
      save->tournament.phase <= LEAGUE_PHASE_COMPLETE &&
      save->tournament.matchday_count >= 1u &&
      save->tournament.matchday_count <= LEAGUE_MAX_MATCHDAYS &&
      save->tournament.fixture_count <= LEAGUE_MAX_FIXTURES &&
      save->tournament.active_matchday <=
          save->tournament.matchday_count;
}

static void competition_scan_league_saves(void) {
  static LeagueSaveState save;
  for (uint32_t slot = 0; slot < LEAGUE_SAVE_SLOTS; slot++) {
    league_slot_valid[slot] = league_save_read(slot, &save) &&
        competition_league_save_valid(&save);
    league_slot_completed[slot] = league_slot_valid[slot] &&
        save.tournament.phase == LEAGUE_PHASE_COMPLETE;
  }
}

static int competition_save_league_slot(uint32_t slot) {
  if (slot >= LEAGUE_SAVE_SLOTS || !league_draft.team_count) return 0;
  static LeagueSaveState save;
  memset(&save, 0, sizeof(save));
  save.player_count = league_player_count;
  save.team_count = league_team_count;
  save.com_level = cup_com_level;
  save.home_away = league_home_away;
  save.game_time = cup_game_time;
  save.extra_time = cup_extra_time;
  save.max_substitutions = cup_max_substitutions;
  save.injuries = cup_injuries;
  save.ball_index = cup_ball_index;
  save.var_enabled = cup_var;
  save.tournament_valid = league_tournament_valid;
  save.draft = league_draft;
  save.tournament = league_tournament;
  if (!league_save_write(slot, &save)) return 0;
  league_active_slot = slot;
  league_slot_valid[slot] = 1u;
  league_slot_completed[slot] =
      league_tournament.phase == LEAGUE_PHASE_COMPLETE;
  return 1;
}

static int competition_load_league_slot(uint32_t slot) {
  static LeagueSaveState save;
  if (!league_save_read(slot, &save) ||
      !competition_league_save_valid(&save)) return 0;
  league_player_count = save.player_count;
  league_team_count = save.team_count;
  league_home_away = save.home_away;
  cup_com_level = save.com_level;
  cup_game_time = save.game_time;
  cup_extra_time = save.extra_time;
  cup_max_substitutions = save.max_substitutions;
  cup_injuries = save.injuries;
  cup_ball_index = save.ball_index;
  cup_var = save.var_enabled;
  league_tournament_valid = save.tournament_valid;
  league_draft = save.draft;
  league_tournament = save.tournament;
  league_active_slot = slot;
  league_teams_editing = 0u;
  league_scorers_open = 0u;
  league_table_page = 0u;
  league_schedule_page = 0u;
  league_bracket_round = league_tournament.knockout.active_round;
  league_bracket_page = 0u;
  cup_team_picker_active = 0u;
  competition_set_state(COMPETITION_FRONTEND_LEAGUE_HUB,
                         league_tournament.phase == LEAGUE_PHASE_COMPLETE
                             ? 0u : 2u);
  return 1;
}

static void competition_open_cup_team_picker(void) {
  if (cup_first_match_started || !cup_bracket_editing) return;
  cup_bracket_swap_source = UINT32_MAX;
  cup_team_picker_active = 1;
  cup_team_picker_category = competition_cup_is_custom()
      ? 0u : competition_cup_entry()->category_index;
  /* Predefined cups go straight to their eligible league's team list. */
  cup_team_picker_phase = competition_cup_is_custom() ? 1u : 2u;
  cup_team_picker_focus = 0;
  cup_team_picker_scroll = 0;
  competition_clear_status();
}

static void competition_focus_cup_slot(uint32_t slot) {
  if (slot >= cup_draft.team_count) return;
  cup_bracket_slot_focus = slot;
  uint32_t fixture = 0;
  if (competition_draft_slot_fixture(&cup_draft, slot, &fixture, NULL)) {
    cup_bracket_stage = 0u;
    cup_bracket_page = competition_bracket_stage_pages(0u) > 1u
        ? fixture / 2u : 0u;
  }
}

static void competition_move_cup_action(int direction) {
  const uint32_t count = competition_item_count_for_state();
  for (uint32_t attempt = 0; attempt < count; attempt++) {
    const uint32_t next = direction > 0
        ? (frontend_focus + 1u) % count
        : (frontend_focus + count - 1u) % count;
    frontend_focus = next;
    if (competition_frontend_item_enabled(next)) return;
  }
}

static void competition_confirm(void) {
  switch (frontend_state) {
    case COMPETITION_FRONTEND_MATCH_MODE:
      frontend_pending_action = frontend_focus == 0
                                    ? COMPETITION_ACTION_EXHIBITION
                                    : COMPETITION_ACTION_TWO_PLAYER;
      /* Keep the action latched until ue4_hooks consumes it, but leave the
       * Match submenu alive while the synchronous controller applet opens.
       * The bridge closes this page only after the native selector is ready;
       * this prevents a one-frame flash back to the four-tile host menu. */
      frontend_closing = 0;
      frontend_controller_gate_request = 0;
      competition_clear_status();
      return;
    case COMPETITION_FRONTEND_MODES:
      if (frontend_focus == 0) {
        competition_reset_cup_setup();
        competition_scan_cup_saves();
        competition_set_state(COMPETITION_FRONTEND_CUP_LANDING, 0);
      } else if (frontend_focus == 1u) {
        competition_reset_league_setup();
        competition_scan_league_saves();
        competition_set_state(COMPETITION_FRONTEND_LEAGUE_LANDING, 0u);
      } else {
        competition_set_status("MASTER LEAGUE COMING SOON");
      }
      return;
    case COMPETITION_FRONTEND_LEAGUE_LANDING:
      if (frontend_focus == 0u) {
        competition_reset_league_setup();
        competition_set_state(COMPETITION_FRONTEND_LEAGUE_SETTINGS, 0u);
      } else if (frontend_focus == 1u) {
        league_slots_saving = 0u;
        competition_scan_league_saves();
        competition_set_state(COMPETITION_FRONTEND_LEAGUE_SLOTS, 0u);
      }
      return;
    case COMPETITION_FRONTEND_LEAGUE_SLOTS:
      if (frontend_focus < LEAGUE_SAVE_SLOTS) {
        if (league_slots_saving) {
          const uint32_t slot = frontend_focus;
          competition_set_state(COMPETITION_FRONTEND_LEAGUE_HUB, 3u);
          competition_set_status(competition_save_league_slot(slot)
              ? "LEAGUE SAVED" : "LEAGUE SAVE FAILED");
        } else if (league_slot_valid[frontend_focus]) {
          if (!competition_load_league_slot(frontend_focus))
            competition_set_status("SAVE SLOT CORRUPT");
        } else {
          competition_set_status("EMPTY SLOT");
        }
      }
      return;
    case COMPETITION_FRONTEND_LEAGUE_SETTINGS:
      if (frontend_focus == 4u)
        competition_open_league_hub();
      else
        competition_adjust_setting(1);
      return;
    case COMPETITION_FRONTEND_LEAGUE_HUB:
      if (league_tournament.phase == LEAGUE_PHASE_COMPLETE) {
        competition_frontend_close();
        return;
      }
      if (frontend_focus == 0u) {
        if (league_tournament.first_match_started) return;
        league_teams_editing = 1u;
        league_team_slot_focus = 0u;
        return;
      }
      if (frontend_focus == 1u) {
        cup_general_open = 1u;
        cup_general_focus = 0u;
        return;
      }
      if (frontend_focus == 3u) {
        league_slots_saving = 1u;
        competition_scan_league_saves();
        competition_set_state(COMPETITION_FRONTEND_LEAGUE_SLOTS,
                              league_active_slot < LEAGUE_SAVE_SLOTS
                                  ? league_active_slot : 0u);
        return;
      }
      if (frontend_focus != 2u || !league_tournament_valid) {
        competition_set_status("ASSIGN ALL LEAGUE TEAMS FIRST");
        return;
      }
      if ((pes_controller_native_hid_connected_mask() &
           (league_player_count > 1u ? 3u : 1u)) !=
          (league_player_count > 1u ? 3u : 1u)) {
        frontend_controller_gate_request = 1u;
        competition_set_status("WAITING FOR CONTROLLERS");
        return;
      }
      league_tournament_advance(&league_tournament);
      league_bracket_round = league_tournament.knockout.active_round;
      league_bracket_page = 0u;
      if (league_tournament.phase == LEAGUE_PHASE_COMPLETE) {
        frontend_focus = 0u;
        competition_set_status("LEAGUE COMPLETE");
        if (league_active_slot < LEAGUE_SAVE_SLOTS)
          competition_save_league_slot(league_active_slot);
        return;
      }
      if (!league_tournament_next_human(
              &league_tournament, &league_pending_fixture,
              &league_pending_round, &league_pending_index)) {
        competition_set_status("NO PLAYABLE FIXTURE");
        return;
      }
      frontend_pending_action = COMPETITION_ACTION_LEAGUE_FIXTURE;
      return;
    case COMPETITION_FRONTEND_CUP_LANDING:
      if (frontend_focus == 0) {
        competition_reset_cup_setup();
        competition_set_state(COMPETITION_FRONTEND_CUP_SETTINGS, 0);
      } else if (frontend_focus == 1) {
        cup_slots_saving = 0;
        competition_scan_cup_saves();
        competition_set_state(COMPETITION_FRONTEND_CUP_SLOTS, 0);
      }
      return;
    case COMPETITION_FRONTEND_CUP_SLOTS:
      if (frontend_focus < COMPETITION_SAVE_SLOT_COUNT) {
        if (cup_slots_saving) {
          const uint32_t slot = frontend_focus;
          competition_set_state(COMPETITION_FRONTEND_CUP_BRACKET,
                                CUP_HUB_ACTION_SAVE);
          if (competition_save_cup_slot(slot))
            competition_set_status("CUP SAVED");
          else
            competition_set_status("CUP SAVE FAILED");
        } else if (cup_slot_valid[frontend_focus]) {
          if (!competition_load_cup_slot(frontend_focus))
            competition_set_status("SAVE SLOT CORRUPT");
        } else {
          competition_set_status("EMPTY SLOT");
        }
      }
      return;
    case COMPETITION_FRONTEND_CUP_SETTINGS:
      if (frontend_focus == 5u) {
        competition_open_bracket();
      } else {
        competition_adjust_setting(1);
      }
      return;
    case COMPETITION_FRONTEND_CUP_TEAMS:
      if (cup_team_picker_active) {
        competition_frontend_cup_team_picker_result(
            competition_frontend_cup_picker_focused_team());
        return;
      }
      if (frontend_focus < cup_player_count) {
        cup_team_picker_phase = 1;
        cup_team_picker_category = 0;
        cup_team_picker_focus = 0;
        cup_team_picker_scroll = 0;
        cup_team_picker_active = 1;
        return;
      }
      if (frontend_focus == cup_player_count) {
        if (competition_cup_teams_complete())
          competition_open_bracket();
        else
          competition_set_status("SELECT ALL PLAYER TEAMS");
      }
      return;
    case COMPETITION_FRONTEND_CUP_BRACKET:
      if (cup_tournament.champion) {
        competition_frontend_close();
        return;
      }
      if (frontend_focus == CUP_HUB_ACTION_TEAMS) {
        if (cup_first_match_started) return;
        cup_bracket_editing = 1;
        cup_bracket_swap_source = UINT32_MAX;
        competition_focus_cup_slot(0u);
        return;
      }
      if (frontend_focus == CUP_HUB_ACTION_GENERAL) {
        cup_general_open = 1u;
        cup_general_focus = 0u;
        return;
      }
      if (frontend_focus == CUP_HUB_ACTION_SAVE) {
        cup_slots_saving = 1;
        competition_scan_cup_saves();
        competition_set_state(COMPETITION_FRONTEND_CUP_SLOTS,
                              cup_active_slot < COMPETITION_SAVE_SLOT_COUNT
                                  ? cup_active_slot : 0u);
        return;
      }
      if (frontend_focus != CUP_HUB_ACTION_NEXT ||
          !cup_tournament_valid || cup_tournament.champion) {
        competition_set_status("ASSIGN ALL BRACKET TEAMS FIRST");
        return;
      }
      if (!cup_first_match_started &&
          !competition_cup_opening_has_player_match(&cup_draft)) {
        cup_opening_rule_popup = 1u;
        return;
      }
      if (!competition_frontend_cup_controllers_ready()) {
        frontend_controller_gate_request = 1;
        competition_set_status(
            cup_player_count > 1 ? "WAITING FOR CONTROLLERS 1 + 2"
                                 : "WAITING FOR CONTROLLER 1");
        return;
      }
      if (!cup_tournament_next_human(&cup_tournament, &cup_pending_round,
                                     &cup_pending_index)) {
        /* Remaining COM fixtures are resolved only after a player match;
         * setup validation guarantees a player starts the opening round. */
        cup_tournament_advance(&cup_tournament);
        competition_bracket_view_active();
        if (cup_active_slot < COMPETITION_SAVE_SLOT_COUNT)
          competition_save_cup_slot(cup_active_slot);
        if (!cup_tournament_next_human(&cup_tournament, &cup_pending_round,
                                       &cup_pending_index)) {
          competition_set_status(cup_tournament.champion
              ? "CUP COMPLETE" : "NO PLAYABLE FIXTURE");
          if (cup_tournament.champion) frontend_focus = 0u;
          return;
        }
      }
      frontend_pending_action = COMPETITION_ACTION_CUP_FIXTURE;
      return;
    case COMPETITION_FRONTEND_CUP_CHECKPOINT:
      competition_set_state(COMPETITION_FRONTEND_CUP_BRACKET, 0);
      return;
    case COMPETITION_FRONTEND_NOTICE:
      competition_set_state(COMPETITION_FRONTEND_MODES, 0);
      return;
    default:
      return;
  }
}

void competition_frontend_open_match_mode(void) {
  competition_set_state(COMPETITION_FRONTEND_MATCH_MODE, 0);
  frontend_closing = 0;
  /* The native tile's confirm A is still present in this Pad::Update tick.
   * Do not let it also activate Exhibition inside the newly opened page. */
  frontend_skip_input_tick = 1;
}

void competition_frontend_match_action_result(int opened) {
  if (opened) {
    competition_frontend_finish_close();
    return;
  }
  /* The controller applet can be cancelled. Keep the submenu alive and put
   * focus back on 2 Player instead of falling through to the four-tile host. */
  competition_set_state(COMPETITION_FRONTEND_MATCH_MODE, 1);
  frontend_closing = 0;
  frontend_skip_input_tick = 1;
}

void competition_frontend_open_modes(void) {
  competition_set_state(COMPETITION_FRONTEND_MODES, 0);
  frontend_closing = 0;
  frontend_skip_input_tick = 1;
}

void competition_frontend_close(void) {
  if (frontend_state != COMPETITION_FRONTEND_NONE)
    frontend_closing = 1;
  frontend_state = COMPETITION_FRONTEND_NONE;
  frontend_focus = 0;
  frontend_controller_gate_request = 0;
  frontend_skip_input_tick = 0;
  frontend_buttons_latched = 0;
  cup_opening_rule_popup = 0u;
  cup_champion_presentation_pending = 0u;
  competition_clear_status();
}

void competition_frontend_finish_close(void) {
  frontend_closing = 0;
  frontend_state = COMPETITION_FRONTEND_NONE;
  frontend_focus = 0;
  frontend_controller_gate_request = 0;
  frontend_skip_input_tick = 0;
  frontend_buttons_latched = 0;
  cup_opening_rule_popup = 0u;
  competition_clear_status();
}

int competition_frontend_active(void) {
  return frontend_state != COMPETITION_FRONTEND_NONE || frontend_closing;
}

int competition_frontend_closing(void) {
  return frontend_closing != 0;
}

CompetitionFrontendState competition_frontend_state(void) {
  return frontend_state;
}

uint32_t competition_frontend_focus(void) {
  return frontend_focus;
}

uint32_t competition_frontend_item_count(void) {
  return competition_item_count_for_state();
}

const char *competition_frontend_title(void) {
  if (cup_team_picker_active)
    return "SELECT TEAM";
  switch (frontend_state) {
    case COMPETITION_FRONTEND_MATCH_MODE:
      return "SELECT MATCH MODE";
    case COMPETITION_FRONTEND_MODES:
      return "SELECT MODES";
    case COMPETITION_FRONTEND_CUP_LANDING:
      return "CUP";
    case COMPETITION_FRONTEND_CUP_SLOTS:
      return cup_slots_saving ? "SAVE CUP" : "SELECT CUP SAVE";
    case COMPETITION_FRONTEND_CUP_SETTINGS:
      return "CUP SETTINGS";
    case COMPETITION_FRONTEND_CUP_TEAMS:
      return "SELECT TEAMS";
    case COMPETITION_FRONTEND_CUP_BRACKET:
      return competition_frontend_cup_name();
    case COMPETITION_FRONTEND_CUP_CHECKPOINT:
      return "MATCH CHECKPOINT";
    case COMPETITION_FRONTEND_LEAGUE_LANDING:
      return "LEAGUE";
    case COMPETITION_FRONTEND_LEAGUE_SLOTS:
      return league_slots_saving ? "SAVE LEAGUE" : "SELECT LEAGUE SAVE";
    case COMPETITION_FRONTEND_LEAGUE_SETTINGS:
      return "LEAGUE SETTINGS";
    case COMPETITION_FRONTEND_LEAGUE_HUB:
      return "FOOTBALLNX LEAGUE";
    case COMPETITION_FRONTEND_NOTICE:
      return "SELECT MODES";
    default:
      return "";
  }
}

const char *competition_frontend_subtitle(void) {
  switch (frontend_state) {
    case COMPETITION_FRONTEND_MATCH_MODE:
      return "LOCAL MATCH";
    case COMPETITION_FRONTEND_MODES:
      return "COMPETITION MODES";
    case COMPETITION_FRONTEND_CUP_LANDING:
      return "NEW OR CONTINUE CUP";
    case COMPETITION_FRONTEND_CUP_SLOTS:
      return "THREE SAVE SLOTS";
    case COMPETITION_FRONTEND_CUP_SETTINGS:
      return "P1 SETUP";
    case COMPETITION_FRONTEND_CUP_TEAMS:
      return "P1 SELECTS ALL TEAMS";
    case COMPETITION_FRONTEND_CUP_BRACKET:
      return cup_tournament.champion ? "CUP COMPLETE" : "BRACKET";
    case COMPETITION_FRONTEND_CUP_CHECKPOINT:
      return "MATCH ROUTE NOT ENABLED";
    case COMPETITION_FRONTEND_LEAGUE_LANDING:
      return "NEW OR CONTINUE LEAGUE";
    case COMPETITION_FRONTEND_LEAGUE_SLOTS:
      return "THREE SAVE SLOTS";
    case COMPETITION_FRONTEND_LEAGUE_SETTINGS:
      return "LEAGUE SETUP";
    case COMPETITION_FRONTEND_LEAGUE_HUB:
      return league_tournament.phase == LEAGUE_PHASE_COMPLETE
          ? "LEAGUE COMPLETE"
          : league_tournament.phase == LEAGUE_PHASE_KNOCKOUT
              ? "KNOCKOUT STAGE" : "LEAGUE PHASE";
    case COMPETITION_FRONTEND_NOTICE:
      return frontend_status;
    default:
      return "";
  }
}

const char *competition_frontend_item_label(uint32_t index) {
  static const char *const match_labels[2] = {"EXHIBITION", "2 PLAYER"};
  static const char *const mode_labels[3] = {"CUP", "LEAGUE", "MASTER LEAGUE"};
  static const char *const landing_labels[2] = {"NEW", "CONTINUE"};
  static const char *const settings_labels[6] = {
      "CUP TYPE", "NUMBER OF PLAYER", "NUMBER OF TEAMS", "HOME AWAY",
      "3RD PLACE MATCH", "NEXT"};
  static const char *const checkpoint_labels[1] = {"BACK TO BRACKET"};
  static const char *const league_settings_labels[5] = {
      "LEAGUE TYPE", "NUMBER OF PLAYER", "NUMBER OF TEAMS",
      "HOME AWAY", "NEXT"};
  switch (frontend_state) {
    case COMPETITION_FRONTEND_MATCH_MODE:
      return index < 2 ? match_labels[index] : "";
    case COMPETITION_FRONTEND_MODES:
      return index < 3 ? mode_labels[index] : "";
    case COMPETITION_FRONTEND_CUP_LANDING:
      return index < 2 ? landing_labels[index] : "";
    case COMPETITION_FRONTEND_CUP_SLOTS: {
      static char slot_label[24];
      if (index < COMPETITION_SAVE_SLOT_COUNT) {
        snprintf(slot_label, sizeof(slot_label), "SLOT %u", index + 1u);
        return slot_label;
      }
      return "";
    }
    case COMPETITION_FRONTEND_CUP_SETTINGS:
      return index < 6u ? settings_labels[index] : "";
    case COMPETITION_FRONTEND_LEAGUE_LANDING:
      return index < 2u ? landing_labels[index] : "";
    case COMPETITION_FRONTEND_LEAGUE_SLOTS: {
      static char slot_label[24];
      if (index < LEAGUE_SAVE_SLOTS) {
        snprintf(slot_label, sizeof(slot_label), "SLOT %u", index + 1u);
        return slot_label;
      }
      return "";
    }
    case COMPETITION_FRONTEND_LEAGUE_SETTINGS:
      return index < 5u ? league_settings_labels[index] : "";
    case COMPETITION_FRONTEND_LEAGUE_HUB:
      if (league_tournament.phase == LEAGUE_PHASE_COMPLETE)
        return index == 0u ? "TOP TO MENU" : "";
      switch (index) {
        case 0u: return "TEAMS";
        case 1u: return "GENERAL SETTING";
        case 2u: return "NEXT";
        case 3u: return "SAVE";
        default: return "";
      }
    case COMPETITION_FRONTEND_CUP_TEAMS:
      if (index < cup_player_count) {
        static char player_label[24];
        snprintf(player_label, sizeof(player_label), "P%u TEAM", index + 1u);
        return player_label;
      }
      return index == cup_player_count ? "NEXT" : "";
    case COMPETITION_FRONTEND_CUP_BRACKET:
      if (cup_tournament.champion)
        return index == 0u ? "TOP TO MENU" : "";
      switch (index) {
        case CUP_HUB_ACTION_TEAMS: return "TEAMS";
        case CUP_HUB_ACTION_NEXT: return "NEXT";
        case CUP_HUB_ACTION_GENERAL: return "GENERAL SETTING";
        case CUP_HUB_ACTION_SAVE: return "SAVE";
        default: return "";
      }
    case COMPETITION_FRONTEND_CUP_CHECKPOINT:
    case COMPETITION_FRONTEND_NOTICE:
      return index == 0 ? checkpoint_labels[0] : "";
    default:
      return "";
  }
}

const char *competition_frontend_item_value(uint32_t index) {
  static char value[32];
  value[0] = '\0';
  if (frontend_state == COMPETITION_FRONTEND_CUP_SETTINGS) {
    switch (index) {
      case 0:
        return competition_cup_entry()->name;
      case 1:
        snprintf(value, sizeof(value), "%u", cup_player_count);
        return value;
      case 2:
        snprintf(value, sizeof(value), "%u", competition_cup_effective_team_count());
        return value;
      case 3:
        return cup_home_away ? "ON" : "OFF";
      case 4:
        return cup_third_place ? "ON" : "OFF";
      default:
        return "";
    }
  }
  if (frontend_state == COMPETITION_FRONTEND_LEAGUE_SETTINGS) {
    switch (index) {
      case 0u: return "FOOTBALLNX LEAGUE";
      case 1u:
        snprintf(value, sizeof(value), "%u", league_player_count);
        return value;
      case 2u:
        snprintf(value, sizeof(value), "%u", league_team_count);
        return value;
      case 3u: return league_home_away ? "ON" : "OFF";
      default: return "";
    }
  }
  if (frontend_state == COMPETITION_FRONTEND_LEAGUE_SLOTS &&
      index < LEAGUE_SAVE_SLOTS)
    return league_slot_valid[index]
        ? league_slot_completed[index] ? "COMPLETED" : "IN PROGRESS"
        : "EMPTY";
  if (frontend_state == COMPETITION_FRONTEND_CUP_SLOTS &&
      index < COMPETITION_SAVE_SLOT_COUNT)
    return cup_slot_valid[index]
               ? (cup_slot_completed[index] ? "COMPLETED" : "IN PROGRESS")
               : "EMPTY";
  if (frontend_state == COMPETITION_FRONTEND_CUP_TEAMS &&
      index < cup_player_count) {
    if (!cup_team_selected[index])
      return "SELECT TEAM";
    return exhibition_team_catalog_name(cup_team_catalog_index[index]);
  }
  if (frontend_state == COMPETITION_FRONTEND_CUP_BRACKET &&
      index == CUP_HUB_ACTION_NEXT)
    return cup_tournament.champion ? "COMPLETE"
           : !cup_tournament_valid ? "ASSIGN TEAMS"
           : competition_frontend_cup_controllers_ready() ? "READY" : "WAITING";
  return "";
}

int competition_frontend_item_enabled(uint32_t index) {
  if (frontend_state == COMPETITION_FRONTEND_CUP_SETTINGS) {
    return index == 5u || competition_cup_setting_visible(index);
  }
  if (frontend_state == COMPETITION_FRONTEND_CUP_TEAMS &&
      index == cup_player_count)
    return competition_cup_teams_complete();
  if (frontend_state == COMPETITION_FRONTEND_CUP_SLOTS &&
      index < COMPETITION_SAVE_SLOT_COUNT)
    return cup_slots_saving || cup_slot_valid[index] != 0;
  if (frontend_state == COMPETITION_FRONTEND_CUP_BRACKET) {
    if (cup_tournament.champion) return index == 0u;
    if (index == CUP_HUB_ACTION_TEAMS) return !cup_first_match_started;
    if (index == CUP_HUB_ACTION_NEXT)
      return cup_tournament_valid &&
             (cup_first_match_started ||
              competition_cup_opening_has_player_match(&cup_draft));
    return index == CUP_HUB_ACTION_GENERAL ||
           index == CUP_HUB_ACTION_SAVE;
  }
  if (frontend_state == COMPETITION_FRONTEND_LEAGUE_SETTINGS)
    return index < 5u;
  if (frontend_state == COMPETITION_FRONTEND_LEAGUE_SLOTS &&
      index < LEAGUE_SAVE_SLOTS)
    return league_slots_saving || league_slot_valid[index];
  if (frontend_state == COMPETITION_FRONTEND_LEAGUE_HUB) {
    if (league_tournament.phase == LEAGUE_PHASE_COMPLETE)
      return index == 0u;
    if (index == 0u) return !league_tournament.first_match_started;
    if (index == 2u) return league_tournament_valid != 0u;
    return index == 1u || index == 3u;
  }
  return index < competition_item_count_for_state();
}

const char *competition_frontend_status(void) {
  if (frontend_status[0])
    return frontend_status;
  if (frontend_state == COMPETITION_FRONTEND_CUP_BRACKET &&
      !competition_draft_ready(&cup_draft)) {
    static char assignment[64];
    snprintf(assignment, sizeof(assignment), "ASSIGN TEAMS  %u / %u",
             competition_draft_assigned_count(&cup_draft),
             cup_draft.team_count);
    return assignment;
  }
  if (frontend_state == COMPETITION_FRONTEND_CUP_BRACKET &&
      !cup_tournament.champion &&
      !competition_frontend_cup_controllers_ready())
    return cup_player_count > 1 ? "WAITING FOR CONTROLLERS 1 + 2"
                                : "WAITING FOR CONTROLLER 1";
  return "";
}

uint32_t competition_frontend_cup_team_count(void) {
  return competition_cup_effective_team_count();
}

uint32_t competition_frontend_cup_setting_count(void) {
  if (frontend_state == COMPETITION_FRONTEND_LEAGUE_SETTINGS) return 4u;
  uint32_t count = 0;
  for (uint32_t row = 0; row < 5u; row++)
    if (competition_cup_setting_visible(row))
      count++;
  return count;
}

uint32_t competition_frontend_cup_setting_row(uint32_t visible_index) {
  if (frontend_state == COMPETITION_FRONTEND_LEAGUE_SETTINGS)
    return visible_index < 4u ? visible_index : 4u;
  for (uint32_t row = 0; row < 5u; row++) {
    if (!competition_cup_setting_visible(row))
      continue;
    if (!visible_index)
      return row;
    visible_index--;
  }
  return 5u;
}

uint32_t competition_frontend_cup_setting_focus(void) {
  if (frontend_state == COMPETITION_FRONTEND_LEAGUE_SETTINGS)
    return frontend_focus;
  if (frontend_focus >= 5u)
    return competition_frontend_cup_setting_count();
  uint32_t visible = 0;
  for (uint32_t row = 0; row < frontend_focus; row++)
    if (competition_cup_setting_visible(row))
      visible++;
  return visible;
}

int competition_frontend_cup_general_open(void) {
  return cup_general_open != 0u;
}

uint32_t competition_frontend_cup_general_count(void) {
  return 7u - competition_general_first_row();
}

uint32_t competition_frontend_cup_general_focus(void) {
  return cup_general_focus;
}

const char *competition_frontend_cup_general_label(uint32_t index) {
  static const char *const labels[7] = {
      "COM LEVEL", "MATCH TIME", "OVERTIME", "SUBSTITUTIONS",
      "INJURIES", "BALL", "VAR"};
  return index < competition_frontend_cup_general_count()
      ? labels[index + competition_general_first_row()] : "";
}

const char *competition_frontend_cup_general_value(uint32_t index) {
  static char value[24];
  static const char *const levels[7] = {
      "BEGINNER", "AMATEUR", "REGULAR", "PROFESSIONAL",
      "TOP PLAYER", "SUPERSTAR", "LEGEND"};
  static const char *const balls[10] = {
      "TRIPLETTA", "UNIFORIA EURO", "WE-PES CLASSIC", "REGISTA",
      "MOMENTO", "SPECIAL BRONZE", "SPECIAL SILVER", "SPECIAL GOLD",
      "SPECIAL BLACK", "METALLIC EDITION"};
  switch (competition_general_row(index)) {
    case 0: return levels[cup_com_level <= 6u ? cup_com_level : 3u];
    case 1:
      snprintf(value, sizeof(value), "%u MIN", cup_game_time);
      return value;
    case 2: return cup_extra_time ? "ON" : "OFF";
    case 4:
      snprintf(value, sizeof(value), "%u", cup_max_substitutions);
      return value;
    case 5: return cup_injuries ? "ON" : "OFF";
    case 6: return balls[cup_ball_index % 10u];
    case 7: return cup_var ? "ON" : "OFF";
    default: return "";
  }
}

const char *competition_frontend_cup_team_name(uint32_t index) {
  static char fallback[24];
  if (index >= competition_cup_effective_team_count())
    return "";
  const uint32_t slot = index < cup_player_count ? index
                             : index % COMPETITION_MAX_PLAYER_SLOTS;
  const uint32_t team_id = cup_team_selected[slot]
                               ? cup_team_catalog_index[slot]
                               : exhibition_team_catalog_first_id();
  const char *name = exhibition_team_catalog_name(team_id);
  if (name[0])
    return name;
  snprintf(fallback, sizeof(fallback), "TEAM %u", index + 1u);
  return fallback;
}

uint32_t competition_frontend_cup_player_count(void) {
  return cup_player_count;
}

uint32_t competition_frontend_cup_required_controller_mask(void) {
  return cup_player_count > 1 ? 3u : 1u;
}

uint32_t competition_frontend_cup_connected_controller_mask(void) {
  return pes_controller_native_hid_connected_mask() & 3u;
}

int competition_frontend_cup_controllers_ready(void) {
  const uint32_t required = competition_frontend_cup_required_controller_mask();
  return (competition_frontend_cup_connected_controller_mask() & required) ==
         required;
}

int competition_frontend_cup_team_selected(uint32_t index) {
  return index < cup_player_count && cup_team_selected[index] != 0;
}

int competition_frontend_cup_teams_ready(void) {
  return competition_cup_teams_complete();
}

int competition_frontend_cup_team_picker_active(void) {
  return cup_team_picker_active != 0;
}

uint32_t competition_frontend_cup_picker_phase(void) {
  return cup_team_picker_active ? cup_team_picker_phase : 0u;
}

uint32_t competition_frontend_cup_picker_focus(void) {
  return cup_team_picker_focus;
}

uint32_t competition_frontend_cup_picker_scroll(void) {
  return cup_team_picker_scroll;
}

uint32_t competition_frontend_cup_picker_visible_count(void) {
  const uint32_t count = competition_cup_picker_count();
  if (cup_team_picker_scroll >= count)
    return 0;
  const uint32_t remaining = count - cup_team_picker_scroll;
  return remaining < 5u ? remaining : 5u;
}

uint32_t competition_frontend_cup_picker_focused_team(void) {
  if (cup_team_picker_phase == 2 && !competition_picker_unrestricted()) {
    const Fl26CupCatalogEntry *cup = competition_cup_entry();
    return cup_team_picker_focus < cup->pool_count
        ? cup->team_ids[cup_team_picker_focus] : 0u;
  }
  if (cup_team_picker_phase != 2 ||
      cup_team_picker_category >= EXHIBITION_TEAM_CATEGORY_COUNT)
    return 0u;
  const ExhibitionTeamCategory *category =
      &exhibition_team_categories[cup_team_picker_category];
  return cup_team_picker_focus < category->team_count
             ? category->teams[cup_team_picker_focus] : 0u;
}

const char *competition_frontend_cup_picker_title(void) {
  if (!competition_picker_unrestricted())
    return competition_cup_entry()->name;
  return cup_team_picker_phase == 2 &&
                 cup_team_picker_category < EXHIBITION_TEAM_CATEGORY_COUNT
             ? exhibition_team_categories[cup_team_picker_category].label
             : "SELECT LEAGUE";
}

const char *competition_frontend_cup_picker_label(uint32_t index) {
  if (cup_team_picker_phase == 1)
    return index < competition_cup_picker_count()
               ? exhibition_team_categories[index].label : "";
  if (!competition_picker_unrestricted()) {
    const Fl26CupCatalogEntry *cup = competition_cup_entry();
    return index < cup->pool_count
        ? exhibition_team_catalog_name(cup->team_ids[index]) : "";
  }
  if (cup_team_picker_category >= EXHIBITION_TEAM_CATEGORY_COUNT)
    return "";
  const ExhibitionTeamCategory *category =
      &exhibition_team_categories[cup_team_picker_category];
  return index < category->team_count
             ? exhibition_team_catalog_name(category->teams[index]) : "";
}

uint32_t competition_frontend_cup_picker_badge(uint32_t index) {
  if (cup_team_picker_phase == 1)
    return index < competition_cup_picker_count()
               ? exhibition_team_categories[index].badge_slot : 0u;
  if (!competition_picker_unrestricted()) {
    const Fl26CupCatalogEntry *cup = competition_cup_entry();
    return index < cup->pool_count
        ? exhibition_team_catalog_badge(cup->team_ids[index]) : 0u;
  }
  if (cup_team_picker_category >= EXHIBITION_TEAM_CATEGORY_COUNT)
    return 0u;
  const ExhibitionTeamCategory *category =
      &exhibition_team_categories[cup_team_picker_category];
  return index < category->team_count
             ? exhibition_team_catalog_badge(category->teams[index]) : 0u;
}

uint32_t competition_frontend_cup_team_picker_index(void) {
  return competition_frontend_cup_picker_focused_team();
}

const char *competition_frontend_cup_team_picker_name(void) {
  return competition_frontend_cup_picker_label(cup_team_picker_focus);
}

const char *competition_frontend_cup_team_picker_name_at(int relative) {
  const int index = (int)cup_team_picker_focus + relative;
  return index >= 0 ? competition_frontend_cup_picker_label((uint32_t)index)
                    : "";
}

uint32_t competition_frontend_cup_team_badge(uint32_t slot) {
  if (slot >= cup_player_count || !cup_team_selected[slot])
    return 0u;
  return exhibition_team_catalog_badge(cup_team_catalog_index[slot]);
}

uint32_t competition_frontend_cup_picker_category_count(void) {
  return EXHIBITION_TEAM_CATEGORY_COUNT;
}

uint32_t competition_frontend_cup_picker_category(uint32_t index) {
  return index < EXHIBITION_TEAM_CATEGORY_COUNT ? index : 0u;
}

int competition_frontend_cup_team_allowed(uint32_t team_id) {
  return competition_team_is_allowed(team_id);
}

const CupTournament *competition_frontend_cup_tournament(void) {
  return cup_tournament.round_count ? &cup_tournament : NULL;
}

const CompetitionEntryDraft *competition_frontend_cup_draft(void) {
  return cup_draft.team_count ? &cup_draft : NULL;
}

int competition_frontend_cup_bracket_editing(void) {
  return cup_bracket_editing != 0;
}

int competition_frontend_cup_opening_rule_popup(void) {
  return cup_opening_rule_popup != 0u;
}

uint32_t competition_frontend_cup_bracket_slot_focus(void) {
  return cup_bracket_slot_focus;
}

uint32_t competition_frontend_cup_bracket_swap_source(void) {
  return cup_bracket_swap_source;
}

int competition_frontend_cup_bracket_editable(void) {
  return cup_draft.team_count && !cup_first_match_started;
}

uint32_t competition_frontend_cup_view_round(void) {
  return cup_bracket_stage;
}

uint32_t competition_frontend_cup_view_first_fixture(void) {
  return cup_bracket_page * 2u;
}

uint32_t competition_frontend_cup_view_count(void) {
  return competition_bracket_view_count();
}

uint32_t competition_frontend_cup_view_index(void) {
  uint32_t index = cup_bracket_page;
  for (uint32_t stage = 0; stage < cup_bracket_stage; stage++)
    index += competition_bracket_stage_pages(stage);
  return index;
}

uint32_t competition_frontend_cup_view_stage_count(void) {
  return competition_bracket_stage_count();
}

uint32_t competition_frontend_cup_view_page_count(void) {
  return competition_bracket_stage_pages(cup_bracket_stage);
}

uint32_t competition_frontend_cup_view_page_index(void) {
  return cup_bracket_page;
}

const char *competition_frontend_cup_name(void) {
  return competition_cup_entry()->name;
}

uint32_t competition_frontend_cup_catalog_index(void) {
  return cup_select;
}

const char *competition_frontend_cup_logo_file(void) {
  return competition_cup_entry()->logo_file;
}

const char *competition_frontend_cup_round_name(uint32_t round) {
  const uint32_t remaining = cup_tournament.round_count > round
                                 ? cup_tournament.round_count - round : 0u;
  switch (remaining) {
    case 1: return "FINAL";
    case 2: return "SEMI FINAL";
    case 3: return "QUARTER FINAL";
    case 4: return "ROUND OF 16";
    case 5: return "ROUND OF 32";
    default: return "CUP";
  }
}

int competition_frontend_cup_next_fixture(uint32_t *round, uint32_t *index) {
  return cup_tournament_valid &&
         cup_tournament_next_human(&cup_tournament, round, index);
}

int competition_frontend_cup_team_is_human(uint32_t team) {
  for (uint32_t i = 0; i < cup_player_count; i++)
    if (cup_team_catalog_index[i] == team) return 1;
  return 0;
}

uint32_t competition_frontend_cup_player_slot(uint32_t team) {
  for (uint32_t i = 0; i < cup_player_count; i++)
    if (cup_team_catalog_index[i] == team) return i + 1u;
  return 0u;
}

static uint32_t competition_cup_human_slot(uint32_t team) {
  for (uint32_t i = 0; i < cup_player_count; i++)
    if (cup_team_catalog_index[i] == team) return i;
  return UINT32_MAX;
}

int competition_frontend_cup_match_teams(uint32_t *home, uint32_t *away) {
  const CupFixture *fixture = cup_tournament_valid
      ? cup_tournament_fixture(&cup_tournament, cup_pending_round,
                               cup_pending_index) : NULL;
  if (!fixture || fixture->complete || !fixture->home || !fixture->away)
    return 0;
  /* Native pad 1 controls HOME.  Put the sole human there, or the earlier
   * assigned player slot when two human teams meet.  Physical pads 1 and 2
   * then control the two selected teams in slot order, even with >2 logical
   * cup entrants rotating through later fixtures. */
  cup_match_swapped =
      competition_cup_human_slot(fixture->away) <
      competition_cup_human_slot(fixture->home);
  if (home) *home = cup_match_swapped ? fixture->away : fixture->home;
  if (away) *away = cup_match_swapped ? fixture->home : fixture->away;
  return 1;
}

uint32_t competition_frontend_cup_game_time(void) { return cup_game_time; }
uint32_t competition_frontend_cup_com_level(void) { return cup_com_level; }
uint32_t competition_frontend_cup_max_substitutions(void) {
  return cup_max_substitutions;
}
uint32_t competition_frontend_cup_injuries(void) { return cup_injuries; }
uint32_t competition_frontend_cup_ball_index(void) { return cup_ball_index; }
uint32_t competition_frontend_cup_var(void) { return cup_var; }
int competition_frontend_cup_home_away(void) { return cup_home_away != 0; }
int competition_frontend_cup_third_place(void) { return cup_third_place != 0; }
static int competition_cup_first_leg_pending(void) {
  const CupFixture *fixture = cup_tournament_valid
      ? cup_tournament_fixture(&cup_tournament, cup_pending_round,
                               cup_pending_index) : NULL;
  return fixture && cup_home_away &&
         cup_pending_round + 1u < cup_tournament.round_count &&
         !fixture->first_leg_complete;
}
int competition_frontend_cup_extra_time(void) {
  return !competition_cup_first_leg_pending() && cup_extra_time != 0;
}
int competition_frontend_cup_penalty(void) {
  return !competition_cup_first_leg_pending();
}
int competition_frontend_cup_match_active(void) { return cup_match_active != 0; }

int competition_frontend_cup_take_champion_presentation(void) {
  if (frontend_state != COMPETITION_FRONTEND_CUP_BRACKET ||
      !cup_champion_presentation_pending)
    return 0;
  cup_champion_presentation_pending = 0;
  return 1;
}

void competition_frontend_cup_handoff_result(int opened) {
  if (opened) {
    cup_first_match_started = 1;
    cup_bracket_editing = 0;
    cup_bracket_swap_source = UINT32_MAX;
    if (cup_active_slot < COMPETITION_SAVE_SLOT_COUNT)
      competition_save_cup_slot(cup_active_slot);
    cup_match_active = 1;
    cup_match_result_received = 0;
    cup_champion_presentation_pending = 0;
    frontend_state = COMPETITION_FRONTEND_NONE;
    frontend_focus = 0;
    frontend_closing = 0;
    frontend_buttons_latched = 0;
    competition_clear_status();
  } else {
    competition_set_status("MATCH HUB UNAVAILABLE - TRY NEXT AGAIN");
  }
}

void competition_frontend_cup_match_result(uint32_t home_goals,
                                           uint32_t away_goals) {
  if (!cup_match_active || cup_match_result_received) return;
  if (cup_match_swapped) {
    const uint32_t tmp = home_goals;
    home_goals = away_goals;
    away_goals = tmp;
  }
  if (!cup_tournament_record(&cup_tournament, cup_pending_round,
                             cup_pending_index, home_goals, away_goals))
    return;
  cup_match_result_received = 1;
  cup_champion_presentation_pending = cup_tournament.champion &&
      competition_frontend_cup_team_is_human(cup_tournament.champion);
  competition_bracket_view_active();
  if (cup_active_slot < COMPETITION_SAVE_SLOT_COUNT)
    competition_save_cup_slot(cup_active_slot);
}

void competition_frontend_cup_restore_after_match(void) {
  if (!cup_match_active) return;
  cup_match_active = 0;
  competition_set_state(COMPETITION_FRONTEND_CUP_BRACKET,
                        cup_tournament.champion ? CUP_HUB_ACTION_TEAMS
                                                : CUP_HUB_ACTION_NEXT);
  frontend_skip_input_tick = 1;
  if (!cup_match_result_received)
    competition_set_status("MATCH NOT FINISHED - FIXTURE STILL PENDING");
  else if (cup_tournament.champion)
    competition_set_status(
        competition_frontend_cup_team_is_human(cup_tournament.champion)
            ? "CUP COMPLETE - CHAMPION"
            : "GAME OVER - CUP COMPLETE");
}

const LeagueTournament *competition_frontend_league_tournament(void) {
  return league_draft.team_count ? &league_tournament : NULL;
}

const CompetitionEntryDraft *competition_frontend_league_draft(void) {
  return league_draft.team_count ? &league_draft : NULL;
}

uint32_t competition_frontend_league_table_page(void) {
  return league_table_page;
}

uint32_t competition_frontend_league_schedule_page(void) {
  return league_schedule_page;
}

uint32_t competition_frontend_league_bracket_round(void) {
  return league_bracket_round;
}

uint32_t competition_frontend_league_bracket_page(void) {
  return league_bracket_page;
}

int competition_frontend_league_scorers_open(void) {
  return league_scorers_open != 0u;
}

int competition_frontend_league_teams_editing(void) {
  return league_teams_editing != 0u;
}

uint32_t competition_frontend_league_team_slot_focus(void) {
  return league_team_slot_focus;
}

int competition_frontend_league_team_is_human(uint32_t team) {
  for (uint32_t i = 0; i < league_draft.team_count; i++)
    if (league_draft.teams[i] == team)
      return league_draft.owners[i] != 0u;
  return 0;
}

static uint32_t competition_league_human_slot(uint32_t team) {
  for (uint32_t i = 0; i < league_draft.team_count; i++)
    if (league_draft.teams[i] == team && league_draft.owners[i])
      return league_draft.owners[i] - 1u;
  return UINT32_MAX;
}

int competition_frontend_league_match_teams(uint32_t *home,
                                             uint32_t *away) {
  if (!league_tournament_valid ||
      league_tournament.phase == LEAGUE_PHASE_COMPLETE) return 0;
  uint32_t fixture_home = 0u, fixture_away = 0u;
  if (league_tournament.phase == LEAGUE_PHASE_TABLE) {
    if (league_pending_fixture >= league_tournament.fixture_count) return 0;
    const LeagueFixture *fixture =
        &league_tournament.fixtures[league_pending_fixture];
    if (fixture->complete) return 0;
    fixture_home = fixture->home;
    fixture_away = fixture->away;
  } else {
    const CupFixture *fixture = cup_tournament_fixture(
        &league_tournament.knockout, league_pending_round,
        league_pending_index);
    if (!fixture || fixture->complete) return 0;
    fixture_home = fixture->home;
    fixture_away = fixture->away;
  }
  if (!fixture_home || !fixture_away) return 0;
  league_match_swapped = competition_league_human_slot(fixture_away) <
                         competition_league_human_slot(fixture_home);
  if (home) *home = league_match_swapped ? fixture_away : fixture_home;
  if (away) *away = league_match_swapped ? fixture_home : fixture_away;
  return 1;
}

int competition_frontend_league_match_active(void) {
  return league_match_active != 0u;
}

int competition_frontend_league_match_is_knockout(void) {
  return league_tournament.phase == LEAGUE_PHASE_KNOCKOUT;
}

void competition_frontend_league_handoff_result(int opened) {
  if (!opened) {
    competition_set_status("MATCH HUB UNAVAILABLE - TRY NEXT AGAIN");
    return;
  }
  league_tournament.first_match_started = 1u;
  league_teams_editing = 0u;
  if (league_active_slot < LEAGUE_SAVE_SLOTS)
    competition_save_league_slot(league_active_slot);
  league_match_active = 1u;
  league_match_result_received = 0u;
  frontend_state = COMPETITION_FRONTEND_NONE;
  frontend_focus = 0u;
  frontend_closing = 0u;
  frontend_buttons_latched = 0u;
  competition_clear_status();
}

void competition_frontend_league_match_result_with_scorers(
    uint32_t home_goals, uint32_t away_goals,
    const LeagueScorer *scorers, uint32_t scorer_count) {
  if (!league_match_active || league_match_result_received) return;
  if (league_match_swapped) {
    const uint32_t tmp = home_goals;
    home_goals = away_goals;
    away_goals = tmp;
  }
  if (!league_tournament_record(&league_tournament,
                                 league_pending_fixture,
                                 league_pending_round,
                                 league_pending_index,
                                 home_goals, away_goals)) return;
  if (scorers) {
    const uint32_t limit = scorer_count < 80u ? scorer_count : 80u;
    for (uint32_t i = 0; i < limit; i++) {
      const LeagueScorer *scorer = &scorers[i];
      league_tournament_credit_goals(&league_tournament, scorer->team,
          scorer->base_id, scorer->portrait_id, scorer->name,
          scorer->goals);
    }
  }
  league_match_result_received = 1u;
  league_schedule_page = 0u;
  league_bracket_round = league_tournament.knockout.active_round;
  league_bracket_page = 0u;
  if (league_active_slot < LEAGUE_SAVE_SLOTS)
    competition_save_league_slot(league_active_slot);
}

void competition_frontend_league_match_result(uint32_t home_goals,
                                               uint32_t away_goals) {
  competition_frontend_league_match_result_with_scorers(
      home_goals, away_goals, NULL, 0u);
}

void competition_frontend_league_restore_after_match(void) {
  if (!league_match_active) return;
  league_match_active = 0u;
  competition_set_state(COMPETITION_FRONTEND_LEAGUE_HUB,
      league_tournament.phase == LEAGUE_PHASE_COMPLETE ? 0u : 2u);
  frontend_skip_input_tick = 1u;
  if (!league_match_result_received)
    competition_set_status("MATCH NOT FINISHED - FIXTURE STILL PENDING");
  else if (league_tournament.phase == LEAGUE_PHASE_COMPLETE)
    competition_set_status("LEAGUE COMPLETE - CHAMPION");
}

void competition_frontend_cup_team_picker_result(uint32_t team_id) {
  if (frontend_state == COMPETITION_FRONTEND_LEAGUE_HUB &&
      league_teams_editing && cup_team_picker_active &&
      league_team_slot_focus < league_draft.team_count &&
      exhibition_team_catalog_find(team_id)) {
    if (!competition_draft_assign(&league_draft,
                                   league_team_slot_focus, team_id)) {
      competition_set_status("TEAM ALREADY ASSIGNED");
      return;
    }
    competition_rebuild_league();
    cup_team_picker_active = 0u;
    competition_clear_status();
    return;
  }
  if (frontend_state != COMPETITION_FRONTEND_CUP_BRACKET ||
      !cup_bracket_editing || !cup_team_picker_active ||
      cup_bracket_slot_focus >= cup_draft.team_count ||
      !competition_team_is_allowed(team_id))
    return;
  if (!competition_draft_assign_or_swap(
          &cup_draft, cup_bracket_slot_focus, team_id)) {
    competition_set_status("TEAM SELECTION FAILED");
    return;
  }
  competition_rebuild_cup_bracket();
  competition_focus_cup_slot(cup_bracket_slot_focus);
  cup_team_picker_active = 0;
  competition_clear_status();
}

void competition_frontend_pad_event(uint32_t buttons,
                                    uint32_t previous_buttons) {
  if (!competition_frontend_active())
    return;
  (void)previous_buttons;
  frontend_input_consumed = 1;
  if (frontend_closing || frontend_state == COMPETITION_FRONTEND_NONE)
    return;
  const uint32_t pressed =
      buttons & ~frontend_buttons_latched &
      (COMPETITION_BUTTON_A | COMPETITION_BUTTON_B |
       COMPETITION_BUTTON_X | COMPETITION_BUTTON_Y | COMPETITION_BUTTON_UP |
       COMPETITION_BUTTON_DOWN | COMPETITION_BUTTON_LEFT |
       COMPETITION_BUTTON_RIGHT | COMPETITION_BUTTON_L |
       COMPETITION_BUTTON_R);
  frontend_buttons_latched =
      buttons & (COMPETITION_BUTTON_A | COMPETITION_BUTTON_B |
                 COMPETITION_BUTTON_X | COMPETITION_BUTTON_Y |
                 COMPETITION_BUTTON_UP | COMPETITION_BUTTON_DOWN |
                 COMPETITION_BUTTON_LEFT | COMPETITION_BUTTON_RIGHT |
                 COMPETITION_BUTTON_L | COMPETITION_BUTTON_R);
  if (frontend_skip_input_tick) {
    frontend_skip_input_tick = 0;
    return;
  }
  if (cup_opening_rule_popup) {
    if (pressed & (COMPETITION_BUTTON_A | COMPETITION_BUTTON_B)) {
      cup_opening_rule_popup = 0u;
      competition_clear_status();
    }
    return;
  }
  if (frontend_state == COMPETITION_FRONTEND_CUP_TEAMS ||
      (frontend_state == COMPETITION_FRONTEND_CUP_BRACKET &&
       cup_team_picker_active) ||
      (frontend_state == COMPETITION_FRONTEND_LEAGUE_HUB &&
       cup_team_picker_active)) {
    if (cup_team_picker_active) {
      if (pressed & COMPETITION_BUTTON_B) {
        if (cup_team_picker_phase == 2 &&
            competition_picker_unrestricted()) {
          cup_team_picker_phase = 1;
          cup_team_picker_focus = cup_team_picker_category;
          competition_cup_picker_center_scroll();
        } else {
          cup_team_picker_active = 0;
        }
        competition_clear_status();
        return;
      }
      if (pressed & (COMPETITION_BUTTON_LEFT | COMPETITION_BUTTON_UP)) {
        if (cup_team_picker_focus > 0u)
          cup_team_picker_focus--;
        competition_cup_picker_center_scroll();
        return;
      }
      if (pressed & (COMPETITION_BUTTON_RIGHT | COMPETITION_BUTTON_DOWN)) {
        if (cup_team_picker_focus + 1u < competition_cup_picker_count())
          cup_team_picker_focus++;
        competition_cup_picker_center_scroll();
        return;
      }
      if (pressed & COMPETITION_BUTTON_A) {
        if (cup_team_picker_phase == 1) {
          cup_team_picker_category = cup_team_picker_focus;
          cup_team_picker_phase = 2;
          cup_team_picker_focus = 0;
          cup_team_picker_scroll = 0;
        } else {
          competition_frontend_cup_team_picker_result(
              competition_frontend_cup_picker_focused_team());
        }
      }
      return;
    }
    if (pressed & COMPETITION_BUTTON_B) {
      competition_back();
      return;
    }
    if (pressed & COMPETITION_BUTTON_LEFT) {
      if (frontend_focus < cup_player_count)
        frontend_focus = frontend_focus ? frontend_focus - 1u
                                        : cup_player_count - 1u;
      return;
    }
    if (pressed & COMPETITION_BUTTON_RIGHT) {
      if (frontend_focus < cup_player_count)
        frontend_focus = (frontend_focus + 1u) % cup_player_count;
      return;
    }
    if (pressed & COMPETITION_BUTTON_DOWN) {
      if (frontend_focus < cup_player_count)
        frontend_focus = cup_player_count;
      return;
    }
    if (pressed & COMPETITION_BUTTON_UP) {
      if (frontend_focus == cup_player_count)
        frontend_focus = cup_player_count ? cup_player_count - 1u : 0u;
      return;
    }
    if (pressed & COMPETITION_BUTTON_A)
      competition_confirm();
    return;
  }
  if ((frontend_state == COMPETITION_FRONTEND_CUP_BRACKET ||
       frontend_state == COMPETITION_FRONTEND_LEAGUE_HUB) &&
      cup_general_open) {
    const uint32_t count = competition_frontend_cup_general_count();
    if (pressed & COMPETITION_BUTTON_B)
      cup_general_open = 0u;
    else if (pressed & COMPETITION_BUTTON_UP)
      cup_general_focus = cup_general_focus ? cup_general_focus - 1u
                                            : count - 1u;
    else if (pressed & COMPETITION_BUTTON_DOWN)
      cup_general_focus = (cup_general_focus + 1u) % count;
    else if (pressed & COMPETITION_BUTTON_LEFT)
      competition_adjust_general(-1);
    else if (pressed & (COMPETITION_BUTTON_RIGHT | COMPETITION_BUTTON_A))
      competition_adjust_general(1);
    return;
  }
  if (frontend_state == COMPETITION_FRONTEND_CUP_BRACKET &&
      cup_bracket_editing) {
    if (pressed & COMPETITION_BUTTON_B) {
      competition_back();
    } else if (pressed & (COMPETITION_BUTTON_UP | COMPETITION_BUTTON_LEFT)) {
      competition_focus_cup_slot(cup_bracket_slot_focus
          ? cup_bracket_slot_focus - 1u : cup_draft.team_count - 1u);
    } else if (pressed & (COMPETITION_BUTTON_DOWN |
                          COMPETITION_BUTTON_RIGHT)) {
      competition_focus_cup_slot((cup_bracket_slot_focus + 1u) %
                                  cup_draft.team_count);
    } else if (pressed & COMPETITION_BUTTON_A) {
      if (cup_bracket_swap_source == UINT32_MAX) {
        competition_open_cup_team_picker();
      } else if (cup_bracket_swap_source == cup_bracket_slot_focus) {
        cup_bracket_swap_source = UINT32_MAX;
        competition_clear_status();
      } else {
        CompetitionEntryDraft candidate = cup_draft;
        if (competition_draft_swap_slots(
                &candidate, cup_bracket_swap_source,
                cup_bracket_slot_focus)) {
          if (!competition_cup_opening_has_player_match(&candidate)) {
            cup_opening_rule_popup = 1u;
            competition_set_status("PLAYER MATCH REQUIRED IN ROUND 1");
          } else {
            cup_draft = candidate;
            cup_bracket_swap_source = UINT32_MAX;
            competition_rebuild_cup_bracket();
            competition_focus_cup_slot(cup_bracket_slot_focus);
            competition_set_status("BRACKET SLOTS SWAPPED");
          }
        }
      }
    } else if (pressed & COMPETITION_BUTTON_X) {
      if (competition_random_fill_cup()) {
        cup_bracket_swap_source = UINT32_MAX;
        competition_focus_cup_slot(cup_bracket_slot_focus);
        competition_set_status("REMAINING TEAMS ASSIGNED");
      } else {
        competition_set_status("NOT ENOUGH ELIGIBLE TEAMS");
      }
    } else if (pressed & COMPETITION_BUTTON_Y) {
      if (cup_bracket_swap_source == UINT32_MAX) {
        cup_bracket_swap_source = cup_bracket_slot_focus;
        competition_set_status("CHOOSE TARGET SLOT AND PRESS A");
      }
    }
    return;
  }
  if (frontend_state == COMPETITION_FRONTEND_LEAGUE_HUB &&
      league_teams_editing) {
    if (pressed & COMPETITION_BUTTON_B) {
      competition_back();
    } else if (pressed & (COMPETITION_BUTTON_UP |
                          COMPETITION_BUTTON_LEFT)) {
      league_team_slot_focus = league_team_slot_focus
          ? league_team_slot_focus - 1u : league_draft.team_count - 1u;
      league_table_page = league_team_slot_focus / 5u;
    } else if (pressed & (COMPETITION_BUTTON_DOWN |
                          COMPETITION_BUTTON_RIGHT)) {
      league_team_slot_focus = (league_team_slot_focus + 1u) %
          league_draft.team_count;
      league_table_page = league_team_slot_focus / 5u;
    } else if (pressed & COMPETITION_BUTTON_A) {
      cup_team_picker_active = 1u;
      cup_team_picker_phase = 1u;
      cup_team_picker_category = 0u;
      cup_team_picker_focus = 0u;
      cup_team_picker_scroll = 0u;
    } else if (pressed & COMPETITION_BUTTON_X) {
      competition_set_status(competition_random_fill_league()
          ? "REMAINING TEAMS ASSIGNED" : "NOT ENOUGH ELIGIBLE TEAMS");
    } else if (pressed & COMPETITION_BUTTON_Y) {
      league_scorers_open = !league_scorers_open;
    }
    return;
  }
  if (pressed & COMPETITION_BUTTON_B) {
    competition_back();
    return;
  }
  if (frontend_state == COMPETITION_FRONTEND_CUP_BRACKET) {
    if (cup_tournament.champion) {
      if (pressed & COMPETITION_BUTTON_A) competition_confirm();
      return;
    }
    const uint32_t stages = competition_bracket_stage_count();
    const uint32_t pages = competition_bracket_stage_pages(cup_bracket_stage);
    if ((pressed & COMPETITION_BUTTON_L) && cup_bracket_stage) {
      cup_bracket_stage--;
      cup_bracket_page = 0u;
    } else if ((pressed & COMPETITION_BUTTON_R) &&
               cup_bracket_stage + 1u < stages) {
      cup_bracket_stage++;
      cup_bracket_page = 0u;
    } else if ((pressed & COMPETITION_BUTTON_Y) && pages > 1u) {
      cup_bracket_page = (cup_bracket_page + 1u) % pages;
    } else if (pressed & COMPETITION_BUTTON_LEFT)
      competition_move_cup_action(-1);
    else if (pressed & COMPETITION_BUTTON_RIGHT)
      competition_move_cup_action(1);
    else if (pressed & COMPETITION_BUTTON_A)
      competition_confirm();
    return;
  }
  if (frontend_state == COMPETITION_FRONTEND_LEAGUE_HUB) {
    if (league_tournament.phase == LEAGUE_PHASE_COMPLETE) {
      if (pressed & COMPETITION_BUTTON_A) competition_confirm();
      return;
    }
    if (pressed & COMPETITION_BUTTON_Y) {
      league_scorers_open = !league_scorers_open;
    } else if (pressed & COMPETITION_BUTTON_L) {
      if (league_tournament.phase == LEAGUE_PHASE_TABLE) {
        if (league_table_page) league_table_page--;
      } else if (league_bracket_round) {
        league_bracket_round--;
        league_bracket_page = 0u;
      }
    } else if (pressed & COMPETITION_BUTTON_R) {
      if (league_tournament.phase == LEAGUE_PHASE_TABLE) {
        if ((league_table_page + 1u) * 5u < league_team_count)
          league_table_page++;
      } else if (league_bracket_round + 1u <
                 league_tournament.knockout.round_count) {
        league_bracket_round++;
        league_bracket_page = 0u;
      }
    } else if (pressed & COMPETITION_BUTTON_UP) {
      if (league_tournament.phase == LEAGUE_PHASE_TABLE &&
          league_schedule_page) league_schedule_page--;
      else if (league_tournament.phase == LEAGUE_PHASE_KNOCKOUT &&
               league_bracket_page) league_bracket_page--;
    } else if (pressed & COMPETITION_BUTTON_DOWN) {
      if (league_tournament.phase == LEAGUE_PHASE_TABLE &&
          league_tournament_valid &&
          league_tournament.active_matchday <
              league_tournament.matchday_count &&
          (league_schedule_page + 1u) * 4u <
              league_tournament.matchday_fixture_count[
                  league_tournament.active_matchday])
        league_schedule_page++;
      else if (league_tournament.phase == LEAGUE_PHASE_KNOCKOUT &&
          (league_bracket_page + 1u) * 2u < cup_tournament_fixture_count(
              &league_tournament.knockout, league_bracket_round))
        league_bracket_page++;
    } else if (pressed & COMPETITION_BUTTON_LEFT) {
      frontend_focus = (frontend_focus + 3u) % 4u;
    } else if (pressed & COMPETITION_BUTTON_RIGHT) {
      frontend_focus = (frontend_focus + 1u) % 4u;
    } else if (pressed & COMPETITION_BUTTON_A) {
      competition_confirm();
    }
    return;
  }
  if (pressed & COMPETITION_BUTTON_UP) {
    competition_move_focus(1);
    return;
  }
  if (pressed & COMPETITION_BUTTON_DOWN) {
    competition_move_focus(2);
    return;
  }
  if (pressed & COMPETITION_BUTTON_LEFT) {
    competition_adjust_setting(-1);
    return;
  }
  if (pressed & COMPETITION_BUTTON_RIGHT) {
    competition_adjust_setting(1);
    return;
  }
  if (pressed & COMPETITION_BUTTON_A)
    competition_confirm();
}

uint32_t competition_frontend_take_action(void) {
  const uint32_t action = frontend_pending_action;
  frontend_pending_action = COMPETITION_ACTION_NONE;
  return action;
}

int competition_frontend_take_controller_gate_request(void) {
  const int request = frontend_controller_gate_request != 0;
  frontend_controller_gate_request = 0;
  return request;
}

int competition_frontend_take_input_consumed(void) {
  const int consumed = frontend_input_consumed != 0;
  frontend_input_consumed = 0;
  return consumed;
}

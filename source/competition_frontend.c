#include "competition_frontend.h"

#include <stdio.h>
#include <string.h>

#include "exhibition_team_catalog.h"
#include "ue4_hooks.h"

#define COMPETITION_MAX_PLAYER_SLOTS 8u
#define COMPETITION_SAVE_SLOT_COUNT 3u
#define COMPETITION_BUTTON_B (1u << 0)
#define COMPETITION_BUTTON_A (1u << 1)
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
static uint32_t cup_team_count = 8;
static uint32_t cup_select = 0;
static uint32_t cup_com_level = 3;
static uint32_t cup_match_mode = 1;
static uint32_t cup_game_time = 10;
static uint32_t cup_extra_time = 1;
static uint32_t cup_penalty = 1;
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

static void competition_clear_status(void) {
  frontend_status[0] = '\0';
}

static void competition_set_status(const char *status) {
  if (!status)
    status = "";
  snprintf(frontend_status, sizeof(frontend_status), "%s", status);
}

static void competition_reset_cup_setup(void) {
  cup_player_count = 1;
  cup_team_count = 8;
  cup_select = 0;
  cup_com_level = 3;
  cup_match_mode = 1;
  cup_game_time = 10;
  cup_extra_time = 1;
  cup_penalty = 1;
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

static int competition_cup_is_custom(void) {
  return cup_select == 0;
}

static uint32_t competition_cup_fixed_team_count(void) {
  /* The first native reference cup is a full domestic competition.  The
   * custom FootballNX Cup remains the only format whose field is editable. */
  return 20u;
}

static uint32_t competition_cup_effective_team_count(void) {
  return competition_cup_is_custom() ? cup_team_count
                                     : competition_cup_fixed_team_count();
}

static int competition_cup_setting_visible(uint32_t row) {
  if ((row == 1u || row == 2u) && !competition_cup_is_custom())
    return 0;
  if (row == 3u && cup_player_count >= competition_cup_effective_team_count())
    return 0;
  return row < 8u;
}

static int competition_cup_teams_complete(void) {
  if (!cup_player_count)
    return 0;
  for (uint32_t index = 0; index < cup_player_count; index++)
    if (!cup_team_selected[index])
      return 0;
  return 1;
}

static void competition_set_state(CompetitionFrontendState state,
                                  uint32_t focus) {
  frontend_state = state;
  frontend_focus = focus;
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
      return 3;
    case COMPETITION_FRONTEND_CUP_SLOTS:
      return COMPETITION_SAVE_SLOT_COUNT + 1u;
    case COMPETITION_FRONTEND_CUP_SETTINGS:
      /* Eight setting rows plus the floating Next action. Back is the
       * global B affordance, matching the Hub Settings page. */
      return 9;
    case COMPETITION_FRONTEND_CUP_TEAMS:
      /* Team rows plus the floating Next action; B backs out of the page. */
      return cup_player_count + 1u;
    case COMPETITION_FRONTEND_CUP_BRACKET:
      return 2;
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
  if (cup_select == 0)
    return 1;
  /* Predefined cups are fixed participant pools.  The first catalog category
   * is the authored English league set used by the reference cup. */
  const ExhibitionTeamCategory *category =
      EXHIBITION_TEAM_CATEGORY_COUNT ? &exhibition_team_categories[0] : NULL;
  if (!category)
    return 0;
  for (uint32_t index = 0; index < category->team_count; index++)
    if (category->teams[index] == team_id)
      return 1;
  return 0;
}

static uint32_t competition_cup_picker_count(void) {
  if (cup_team_picker_phase == 1)
    return competition_cup_is_custom() ? EXHIBITION_TEAM_CATEGORY_COUNT : 1u;
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
  if (frontend_state != COMPETITION_FRONTEND_CUP_SETTINGS || !direction)
    return;
  switch (frontend_focus) {
    case 0:
      cup_select = (cup_select + 1u) % 2u;
      if (!competition_cup_is_custom()) {
        cup_player_count = 1;
        cup_team_count = competition_cup_fixed_team_count();
        cup_team_selected[0] = 0;
      }
      break;
    case 1:
      if (!competition_cup_is_custom())
        break;
      if (direction > 0) {
        if (cup_player_count < COMPETITION_MAX_PLAYER_SLOTS &&
            cup_player_count < cup_team_count) {
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
      if (!competition_cup_is_custom())
        break;
      if (direction > 0) {
        if (cup_team_count < 32)
          cup_team_count++;
      } else if (cup_team_count > 3) {
        cup_team_count--;
      }
      if (cup_player_count > cup_team_count)
        cup_player_count = cup_team_count;
      break;
    case 3:
      cup_com_level = (uint32_t)((int)cup_com_level +
                                 (direction > 0 ? 1 : -1));
      if (cup_com_level > 6)
        cup_com_level = direction > 0 ? 0 : 6;
      break;
    case 4:
      cup_match_mode = cup_match_mode ? 0u : 1u;
      break;
    case 5:
      if (direction < 0)
        cup_game_time = cup_game_time <= 3u ? 10u
                            : cup_game_time <= 5u ? 3u : cup_game_time - 1u;
      else
        cup_game_time = cup_game_time >= 10u ? 3u
                            : cup_game_time < 5u ? 5u : cup_game_time + 1u;
      break;
    case 6:
      cup_extra_time = cup_extra_time ? 0u : 1u;
      break;
    case 7:
      cup_penalty = cup_penalty ? 0u : 1u;
      break;
    default:
      break;
  }
  competition_clear_status();
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
        candidate < 8u && !competition_cup_setting_visible(candidate))
      continue;
    return;
  }
}

static void competition_back(void) {
  switch (frontend_state) {
    case COMPETITION_FRONTEND_MATCH_MODE:
    case COMPETITION_FRONTEND_MODES:
      competition_frontend_close();
      return;
    case COMPETITION_FRONTEND_CUP_LANDING:
      competition_set_state(COMPETITION_FRONTEND_MODES, 0);
      return;
    case COMPETITION_FRONTEND_CUP_SLOTS:
    case COMPETITION_FRONTEND_CUP_SETTINGS:
      competition_set_state(COMPETITION_FRONTEND_CUP_LANDING, 0);
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
      competition_set_state(COMPETITION_FRONTEND_CUP_LANDING, 0);
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

static void competition_open_bracket(void) {
  cup_slot_valid[0] = 1;
  cup_slot_completed[0] = 0;
  cup_slot_round[0] = 0;
  competition_set_state(COMPETITION_FRONTEND_CUP_BRACKET, 0);
  frontend_controller_gate_request = 1;
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
        competition_set_state(COMPETITION_FRONTEND_CUP_LANDING, 0);
      } else {
        competition_set_status("LEAGUE / MASTER LEAGUE COMING SOON");
      }
      return;
    case COMPETITION_FRONTEND_CUP_LANDING:
      if (frontend_focus == 0) {
        competition_reset_cup_setup();
        competition_set_state(COMPETITION_FRONTEND_CUP_SETTINGS, 0);
      } else if (frontend_focus == 1) {
        competition_set_state(COMPETITION_FRONTEND_CUP_SLOTS, 0);
      } else {
        competition_set_state(COMPETITION_FRONTEND_MODES, 0);
      }
      return;
    case COMPETITION_FRONTEND_CUP_SLOTS:
      if (frontend_focus < COMPETITION_SAVE_SLOT_COUNT) {
        if (cup_slot_valid[frontend_focus]) {
          competition_set_state(COMPETITION_FRONTEND_CUP_BRACKET, 0);
          frontend_controller_gate_request = 1;
        } else {
          competition_set_status("EMPTY SLOT");
        }
      } else {
        competition_set_state(COMPETITION_FRONTEND_CUP_LANDING, 0);
      }
      return;
    case COMPETITION_FRONTEND_CUP_SETTINGS:
      if (frontend_focus == 8) {
        competition_set_state(COMPETITION_FRONTEND_CUP_TEAMS, 0);
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
      if (!competition_frontend_cup_controllers_ready()) {
        competition_set_status(
            cup_player_count > 1 ? "WAITING FOR CONTROLLERS 1 + 2"
                                 : "WAITING FOR CONTROLLER 1");
        return;
      }
      competition_set_state(COMPETITION_FRONTEND_CUP_CHECKPOINT, 0);
      competition_set_status("MATCH HANDOFF RESERVED FOR NEXT CHECKPOINT");
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
  competition_clear_status();
}

void competition_frontend_finish_close(void) {
  frontend_closing = 0;
  frontend_state = COMPETITION_FRONTEND_NONE;
  frontend_focus = 0;
  frontend_controller_gate_request = 0;
  frontend_skip_input_tick = 0;
  frontend_buttons_latched = 0;
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
  if (frontend_state == COMPETITION_FRONTEND_CUP_TEAMS &&
      cup_team_picker_active)
    return "SELECT TEAM";
  switch (frontend_state) {
    case COMPETITION_FRONTEND_MATCH_MODE:
      return "SELECT MATCH MODE";
    case COMPETITION_FRONTEND_MODES:
      return "SELECT MODES";
    case COMPETITION_FRONTEND_CUP_LANDING:
      return "CUP";
    case COMPETITION_FRONTEND_CUP_SLOTS:
      return "SELECT CUP SAVE";
    case COMPETITION_FRONTEND_CUP_SETTINGS:
      return "CUP SETTINGS";
    case COMPETITION_FRONTEND_CUP_TEAMS:
      return "SELECT TEAMS";
    case COMPETITION_FRONTEND_CUP_BRACKET:
      return "FOOTBALLNX CUP";
    case COMPETITION_FRONTEND_CUP_CHECKPOINT:
      return "MATCH CHECKPOINT";
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
      return "BRACKET CHECKPOINT";
    case COMPETITION_FRONTEND_CUP_CHECKPOINT:
      return "MATCH ROUTE NOT ENABLED";
    case COMPETITION_FRONTEND_NOTICE:
      return frontend_status;
    default:
      return "";
  }
}

const char *competition_frontend_item_label(uint32_t index) {
  static const char *const match_labels[2] = {"EXHIBITION", "2 PLAYER"};
  static const char *const mode_labels[3] = {"CUP", "LEAGUE", "MASTER LEAGUE"};
  static const char *const landing_labels[3] = {"NEW", "CONTINUE", "BACK"};
  static const char *const settings_labels[9] = {
      "SELECT CUP", "NUMBER OF PLAYER", "NUMBER OF TEAMS", "COM LEVEL",
      "MATCH MODE", "GAME TIME", "EXTRA TIME", "PENALTY", "NEXT"};
  static const char *const checkpoint_labels[1] = {"BACK TO BRACKET"};
  switch (frontend_state) {
    case COMPETITION_FRONTEND_MATCH_MODE:
      return index < 2 ? match_labels[index] : "";
    case COMPETITION_FRONTEND_MODES:
      return index < 3 ? mode_labels[index] : "";
    case COMPETITION_FRONTEND_CUP_LANDING:
      return index < 3 ? landing_labels[index] : "";
    case COMPETITION_FRONTEND_CUP_SLOTS: {
      static char slot_label[24];
      if (index < COMPETITION_SAVE_SLOT_COUNT) {
        snprintf(slot_label, sizeof(slot_label), "SLOT %u", index + 1u);
        return slot_label;
      }
      return "BACK";
    }
    case COMPETITION_FRONTEND_CUP_SETTINGS:
      return index < 9 ? settings_labels[index] : "";
    case COMPETITION_FRONTEND_CUP_TEAMS:
      if (index < cup_player_count) {
        static char player_label[16];
        snprintf(player_label, sizeof(player_label), "P%u TEAM", index + 1u);
        return player_label;
      }
      return index == cup_player_count ? "NEXT" : "";
    case COMPETITION_FRONTEND_CUP_BRACKET:
      return index < 2 ? (index ? "BACK TO MENU" : "NEXT FIXTURE") : "";
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
        return cup_select ? "ENGLISH CUP" : "FOOTBALLNX CUP";
      case 1:
        snprintf(value, sizeof(value), "%u", cup_player_count);
        if (!competition_cup_is_custom())
          return "1";
        return value;
      case 2:
        snprintf(value, sizeof(value), "%u", competition_cup_effective_team_count());
        return value;
      case 3:
        static const char *const levels[7] = {
            "BEGINNER", "AMATEUR", "REGULAR", "PROFESSIONAL",
            "TOP PLAYER", "SUPERSTAR", "LEGEND"};
        return levels[cup_com_level <= 6u ? cup_com_level : 0u];
      case 4:
        return cup_match_mode ? "KNOCKOUT" : "HOME AWAY";
      case 5:
        snprintf(value, sizeof(value), "%u MIN", cup_game_time);
        return value;
      case 6:
        return cup_extra_time ? "ON" : "OFF";
      case 7:
        return cup_penalty ? "ON" : "OFF";
      default:
        return "";
    }
  }
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
  if (frontend_state == COMPETITION_FRONTEND_CUP_BRACKET && index == 0)
    return competition_frontend_cup_controllers_ready() ? "READY" : "WAITING";
  return "";
}

int competition_frontend_item_enabled(uint32_t index) {
  if (frontend_state == COMPETITION_FRONTEND_CUP_SETTINGS) {
    return index == 8u || competition_cup_setting_visible(index);
  }
  if (frontend_state == COMPETITION_FRONTEND_CUP_TEAMS &&
      index == cup_player_count)
    return competition_cup_teams_complete();
  if (frontend_state == COMPETITION_FRONTEND_CUP_SLOTS &&
      index < COMPETITION_SAVE_SLOT_COUNT)
    return cup_slot_valid[index] != 0;
  return index < competition_item_count_for_state();
}

const char *competition_frontend_status(void) {
  if (frontend_status[0])
    return frontend_status;
  if (frontend_state == COMPETITION_FRONTEND_CUP_BRACKET &&
      !competition_frontend_cup_controllers_ready())
    return cup_player_count > 1 ? "WAITING FOR CONTROLLERS 1 + 2"
                                : "WAITING FOR CONTROLLER 1";
  return "";
}

uint32_t competition_frontend_cup_team_count(void) {
  return competition_cup_effective_team_count();
}

uint32_t competition_frontend_cup_setting_count(void) {
  uint32_t count = 0;
  for (uint32_t row = 0; row < 8u; row++)
    if (competition_cup_setting_visible(row))
      count++;
  return count;
}

uint32_t competition_frontend_cup_setting_row(uint32_t visible_index) {
  for (uint32_t row = 0; row < 8u; row++) {
    if (!competition_cup_setting_visible(row))
      continue;
    if (!visible_index)
      return row;
    visible_index--;
  }
  return 8u;
}

uint32_t competition_frontend_cup_setting_focus(void) {
  if (frontend_focus >= 8u)
    return competition_frontend_cup_setting_count();
  uint32_t visible = 0;
  for (uint32_t row = 0; row < frontend_focus; row++)
    if (competition_cup_setting_visible(row))
      visible++;
  return visible;
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
  if (cup_team_picker_phase != 2 ||
      cup_team_picker_category >= EXHIBITION_TEAM_CATEGORY_COUNT)
    return 0u;
  const ExhibitionTeamCategory *category =
      &exhibition_team_categories[cup_team_picker_category];
  return cup_team_picker_focus < category->team_count
             ? category->teams[cup_team_picker_focus] : 0u;
}

const char *competition_frontend_cup_picker_title(void) {
  return cup_team_picker_phase == 2 &&
                 cup_team_picker_category < EXHIBITION_TEAM_CATEGORY_COUNT
             ? exhibition_team_categories[cup_team_picker_category].label
             : "SELECT LEAGUE";
}

const char *competition_frontend_cup_picker_label(uint32_t index) {
  if (cup_team_picker_phase == 1)
    return index < competition_cup_picker_count()
               ? exhibition_team_categories[index].label : "";
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

void competition_frontend_cup_team_picker_result(uint32_t team_id) {
  if (frontend_state != COMPETITION_FRONTEND_CUP_TEAMS ||
      !cup_team_picker_active || frontend_focus >= cup_player_count ||
      !competition_team_is_allowed(team_id))
    return;
  for (uint32_t slot = 0; slot < cup_player_count; slot++)
    if (slot != frontend_focus && cup_team_selected[slot] &&
        cup_team_catalog_index[slot] == team_id)
      return;
  cup_team_catalog_index[frontend_focus] = team_id;
  cup_team_selected[frontend_focus] = 1;
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
      (COMPETITION_BUTTON_A | COMPETITION_BUTTON_B | COMPETITION_BUTTON_UP |
       COMPETITION_BUTTON_DOWN | COMPETITION_BUTTON_LEFT |
       COMPETITION_BUTTON_RIGHT);
  frontend_buttons_latched =
      buttons & (COMPETITION_BUTTON_A | COMPETITION_BUTTON_B |
                 COMPETITION_BUTTON_UP | COMPETITION_BUTTON_DOWN |
                 COMPETITION_BUTTON_LEFT | COMPETITION_BUTTON_RIGHT);
  if (frontend_skip_input_tick) {
    frontend_skip_input_tick = 0;
    return;
  }
  if (frontend_state == COMPETITION_FRONTEND_CUP_TEAMS) {
    if (cup_team_picker_active) {
      if (pressed & COMPETITION_BUTTON_B) {
        if (cup_team_picker_phase == 2) {
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
  if (pressed & COMPETITION_BUTTON_B) {
    competition_back();
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

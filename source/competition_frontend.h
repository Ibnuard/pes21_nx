#ifndef PES21_COMPETITION_FRONTEND_H
#define PES21_COMPETITION_FRONTEND_H

#include <stdint.h>
#include "cup_tournament.h"
#include "competition_entry_draft.h"

typedef enum {
  COMPETITION_FRONTEND_NONE = 0,
  COMPETITION_FRONTEND_MATCH_MODE,
  COMPETITION_FRONTEND_MODES,
  COMPETITION_FRONTEND_CUP_LANDING,
  COMPETITION_FRONTEND_CUP_SLOTS,
  COMPETITION_FRONTEND_CUP_SETTINGS,
  COMPETITION_FRONTEND_CUP_TEAMS,
  COMPETITION_FRONTEND_CUP_BRACKET,
  COMPETITION_FRONTEND_CUP_CHECKPOINT,
  COMPETITION_FRONTEND_NOTICE,
} CompetitionFrontendState;

enum {
  COMPETITION_ACTION_NONE = 0,
  COMPETITION_ACTION_EXHIBITION = 1,
  COMPETITION_ACTION_TWO_PLAYER = 2,
  COMPETITION_ACTION_CUP_TEAM_PICKER = 3,
  COMPETITION_ACTION_CUP_FIXTURE = 4,
};

void competition_frontend_open_match_mode(void);
void competition_frontend_match_action_result(int opened);
void competition_frontend_open_modes(void);
void competition_frontend_close(void);
void competition_frontend_finish_close(void);

int competition_frontend_active(void);
int competition_frontend_closing(void);
CompetitionFrontendState competition_frontend_state(void);
uint32_t competition_frontend_focus(void);
uint32_t competition_frontend_item_count(void);
const char *competition_frontend_title(void);
const char *competition_frontend_subtitle(void);
const char *competition_frontend_item_label(uint32_t index);
const char *competition_frontend_item_value(uint32_t index);
int competition_frontend_item_enabled(uint32_t index);
const char *competition_frontend_status(void);

uint32_t competition_frontend_cup_team_count(void);
uint32_t competition_frontend_cup_setting_count(void);
uint32_t competition_frontend_cup_setting_row(uint32_t visible_index);
uint32_t competition_frontend_cup_setting_focus(void);
const char *competition_frontend_cup_team_name(uint32_t index);
uint32_t competition_frontend_cup_player_count(void);
uint32_t competition_frontend_cup_required_controller_mask(void);
uint32_t competition_frontend_cup_connected_controller_mask(void);
int competition_frontend_cup_controllers_ready(void);
int competition_frontend_cup_team_selected(uint32_t index);
int competition_frontend_cup_teams_ready(void);
int competition_frontend_cup_team_picker_active(void);
uint32_t competition_frontend_cup_picker_phase(void);
uint32_t competition_frontend_cup_picker_focus(void);
uint32_t competition_frontend_cup_picker_scroll(void);
uint32_t competition_frontend_cup_picker_visible_count(void);
uint32_t competition_frontend_cup_picker_focused_team(void);
const char *competition_frontend_cup_picker_title(void);
const char *competition_frontend_cup_picker_label(uint32_t index);
uint32_t competition_frontend_cup_picker_badge(uint32_t index);
uint32_t competition_frontend_cup_team_picker_index(void);
const char *competition_frontend_cup_team_picker_name(void);
const char *competition_frontend_cup_team_picker_name_at(int relative);
uint32_t competition_frontend_cup_team_badge(uint32_t slot);
uint32_t competition_frontend_cup_picker_category_count(void);
uint32_t competition_frontend_cup_picker_category(uint32_t index);
int competition_frontend_cup_team_allowed(uint32_t team_id);
void competition_frontend_cup_team_picker_result(uint32_t team_id);
const CupTournament *competition_frontend_cup_tournament(void);
const CompetitionEntryDraft *competition_frontend_cup_draft(void);
int competition_frontend_cup_bracket_editing(void);
uint32_t competition_frontend_cup_bracket_slot_focus(void);
uint32_t competition_frontend_cup_bracket_swap_source(void);
int competition_frontend_cup_bracket_editable(void);
const char *competition_frontend_cup_name(void);
const char *competition_frontend_cup_round_name(uint32_t round);
int competition_frontend_cup_next_fixture(uint32_t *round, uint32_t *index);
int competition_frontend_cup_match_teams(uint32_t *home, uint32_t *away);
int competition_frontend_cup_team_is_human(uint32_t team);
uint32_t competition_frontend_cup_player_slot(uint32_t team);
uint32_t competition_frontend_cup_view_round(void);
uint32_t competition_frontend_cup_view_first_fixture(void);
uint32_t competition_frontend_cup_view_count(void);
uint32_t competition_frontend_cup_view_index(void);
uint32_t competition_frontend_cup_view_stage_count(void);
uint32_t competition_frontend_cup_view_page_count(void);
uint32_t competition_frontend_cup_view_page_index(void);
uint32_t competition_frontend_cup_game_time(void);
uint32_t competition_frontend_cup_com_level(void);
uint32_t competition_frontend_cup_max_substitutions(void);
int competition_frontend_cup_extra_time(void);
int competition_frontend_cup_penalty(void);
int competition_frontend_cup_match_active(void);
void competition_frontend_cup_handoff_result(int opened);
void competition_frontend_cup_match_result(uint32_t home_goals,
                                           uint32_t away_goals);
void competition_frontend_cup_restore_after_match(void);

void competition_frontend_pad_event(uint32_t buttons,
                                    uint32_t previous_buttons);
uint32_t competition_frontend_take_action(void);
int competition_frontend_take_controller_gate_request(void);
int competition_frontend_take_input_consumed(void);

#endif

#ifndef __UE4_HOOKS_H__
#define __UE4_HOOKS_H__

#include "so_util.h"

#define PES_MOBILE_CONTROL_UNKNOWN 0
#define PES_MOBILE_CONTROL_OFFENSE 1
#define PES_MOBILE_CONTROL_DEFENSE 2

#define PES_VIRTUAL_CURSOR_NONE 0
#define PES_VIRTUAL_CURSOR_GAMEPLAN 1
#define PES_VIRTUAL_CURSOR_PAUSE 2
#define PES_VIRTUAL_CURSOR_HALF_TIME 3
#define PES_VIRTUAL_CURSOR_FULL_TIME 4
#define PES_VIRTUAL_CURSOR_HALF_PREVIEW 5
#define PES_VIRTUAL_CURSOR_TUTORIAL 6
#define PES_VIRTUAL_CURSOR_SET_PIECE_TAKER 7

#define PES_REPLAY_FEEDBACK_NONE 0
#define PES_REPLAY_FEEDBACK_SKIP 1
#define PES_REPLAY_FEEDBACK_GOAL_CELEBRATION 2
#define PES_REPLAY_FEEDBACK_B_SKIP 3
#define PES_REPLAY_FEEDBACK_A_SKIP 4

#define PES_SETPLAY_NONE 0u
#define PES_SETPLAY_GOAL_KICK 1u
#define PES_SETPLAY_CORNER 2u
#define PES_SETPLAY_FREE_KICK 3u
#define PES_SETPLAY_THROW_IN 4u

#define PES_SETPLAY_OPTION_TEAM_UP (1u << 0)
#define PES_SETPLAY_OPTION_CAMERA (1u << 1)
#define PES_SETPLAY_OPTION_KICKER (1u << 2)
#define PES_SETPLAY_OPTION_SHORT_CORNER (1u << 3)

// Native ButtonSetplay action identifiers. These are the values stored in
// ButtonSetplay's own action vector, so callers can request an action without
// depending on screen coordinates or the current resolution.
#define PES_SETPLAY_BUTTON_SET_PIECE_TAKER 1u
#define PES_SETPLAY_BUTTON_SELECT_THROWER 2u
#define PES_SETPLAY_BUTTON_SHORT_CORNER 3u
#define PES_SETPLAY_BUTTON_POSITION_SHIFT 4u
#define PES_SETPLAY_BUTTON_SWITCH_VIEW 7u

#define PES_CONTROLLER_SURFACE_NONE 0u
#define PES_CONTROLLER_SURFACE_REPLAY 1u
#define PES_CONTROLLER_SURFACE_GOAL_DEMO 2u
#define PES_CONTROLLER_SURFACE_CINEMATIC 3u
#define PES_CONTROLLER_SURFACE_SETPLAY 4u

#define PES_PENALTY_NONE 0u
#define PES_PENALTY_KICKER 1u
#define PES_PENALTY_GOALKEEPER 2u

typedef struct {
  uint32_t generation;
  uint32_t surface;
  uint32_t setplay_context;
  uint32_t setplay_options;
  uint32_t setplay_button_mask;
  uint32_t goal_player;
  uint32_t replay_feedback;
} PesControllerSnapshot;

#define PES_PAUSE_INPUT_UP 1u
#define PES_PAUSE_INPUT_DOWN 2u
#define PES_PAUSE_INPUT_DECIDE 3u
#define PES_PAUSE_INPUT_BACK 4u
#define PES_PAUSE_INPUT_LEFT 5u
#define PES_PAUSE_INPUT_RIGHT 6u

void install_ue4_hooks(so_module *module);
void ue4_hooks_post_finalize(so_module *module);
void cobra_pad_set_input(uint32_t buttons, int32_t up, int32_t down,
                         int32_t left, int32_t right, int connected);
uint32_t pes_mobile_control_context(int *mode);
int pes_mobile_control_active_mode(void);
int pes_controller_replay_active(void);
int pes_controller_replay_goal_active(void);
int pes_controller_goal_demo_active(void);
int pes_controller_goal_demo_player_goal(void);
void pes_controller_cinematic_update(int gameplay_active, int control_mode,
                                     int excluded, uint64_t now_ms);
int pes_controller_cinematic_skip_active(void);
int pes_controller_inmatch_tutorial_active(void);
void pes_controller_inmatch_tutorial_play_request(void);
uint32_t pes_controller_penalty_role(void);
void pes_controller_surface_snapshot(PesControllerSnapshot *snapshot);
// Read the controller surface last published by the 60 Hz input thread.
// Render code must use this cached form so it does not repeat native lifecycle
// expiry checks and atomic publication work on every eglSwap.
void pes_controller_surface_cached_snapshot(PesControllerSnapshot *snapshot);
void pes_controller_demo_skip_request(void);
void pes_controller_setplay_request(uint32_t button_type,
                                    uint32_t generation);
void pes_controller_replay_feedback_set(uint32_t feedback);
uint32_t pes_controller_replay_feedback(void);
uint32_t pes_controller_setplay_context(void);
uint32_t pes_controller_setplay_options(void);
int pes_controller_set_piece_selector_active(void);
uint32_t pes_controller_set_piece_selector_focus(void);
uint32_t pes_controller_set_piece_selector_count(void);
const char *pes_controller_set_piece_selector_title(void);
const char *pes_controller_set_piece_selector_name(void);
const char *pes_controller_set_piece_selector_foot(void);
const char *pes_controller_set_piece_selector_name_at(uint32_t index);
const char *pes_controller_set_piece_selector_foot_at(uint32_t index);
void pes_controller_set_piece_selector_move(int direction);
void pes_controller_set_piece_selector_input(uint32_t action);
void pes_controller_pause_back_request(void);
int pes_controller_custom_pause_active(void);
void pes_controller_custom_pause_input(uint32_t action);
int pes_controller_pause_camera_active(void);
void pes_controller_pause_camera_input(uint32_t action);
int pes_controller_gameplan_pause_route(void);
void pes_controller_result_input(uint32_t action);
void pes_controller_fix_demo_skip_request(void);
int pes_controller_fix_demo_skip_active(void);
int pes_controller_custom_postmatch_active(void);
void pes_controller_custom_postmatch_input(uint32_t action);
int pes_controller_custom_prematch_gameplan_active(void);
void pes_controller_custom_prematch_gameplan_input(uint32_t action);
int pes_controller_menu_active(void);
int pes_controller_gameplan_cursor_active(void);
int pes_controller_virtual_cursor_context(void);
int pes_controller_gameplan_cursor_position(float *normalized_x,
                                             float *normalized_y);
void pes_controller_gameplan_cursor_set(float normalized_x,
                                         float normalized_y);
void pes_controller_result_cursor_clear(void);
uintptr_t pes_match_replay_check_skip_entry(void *replay,
                                            const void *context);
uintptr_t pes_match_goal_demo_update_entry(void *goal_demo,
                                           const void *registry,
                                           void *screen_info,
                                           const void *context);
uintptr_t pes_match_pause_update_entry(void *window, uint32_t pad_status);
uintptr_t pes_match_result_full_entry(void *result, const char *name,
                                      uint32_t modal);
uintptr_t pes_match_result_half_entry(void *result, const char *name,
                                      uint32_t modal);
int pes_main_menu_controller_active(void);
uint32_t pes_main_menu_focus_index(void);
void pes_main_menu_pad_event(uint32_t buttons, uint32_t previous_buttons);
void pes_exhibition_search_pad_event(uint32_t buttons,
                                     uint32_t previous_buttons);
int pes_controller_menu_touch_target(float *normalized_x,
                                     float *normalized_y);
int pes_controller_menu_back_target(float *normalized_x,
                                    float *normalized_y);
void pes_controller_menu_back_pressed(void);
void pes_controller_title_ready(void *window);
int pes_controller_selector_rect(float *x, float *y, float *width,
                                 float *height);
int pes_controller_selector_custom_style(void);
int pes_controller_custom_team_popup_active(void);
uint32_t pes_controller_custom_team_popup_scroll(void);
uint32_t pes_controller_custom_team_popup_focus(void);
uint32_t pes_controller_custom_team_popup_visible_count(void);
const char *pes_controller_custom_team_popup_label(uint32_t index);
const char *pes_controller_custom_team_popup_icon(uint32_t index);
uint32_t pes_controller_custom_team_popup_badge(uint32_t index);
const char *pes_controller_custom_team_popup_title(void);
uint32_t pes_controller_custom_team_popup_page(void);
uint32_t pes_controller_custom_team_popup_page_count(void);
int pes_controller_custom_cpu_popup_active(void);
uint32_t pes_controller_custom_cpu_popup_focus(void);
uint32_t pes_controller_custom_cpu_popup_value(void);
uint32_t pes_controller_custom_cpu_popup_count(void);
const char *pes_controller_custom_cpu_popup_label(uint32_t index);
int pes_controller_custom_match_settings_active(void);
uint32_t pes_controller_custom_match_settings_focus(void);
const char *pes_controller_custom_match_settings_label(uint32_t index);
const char *pes_controller_custom_match_settings_value(uint32_t index);
int pes_controller_custom_video_settings_active(void);
uint32_t pes_controller_custom_video_settings_focus(void);
const char *pes_controller_custom_video_settings_label(uint32_t index);
const char *pes_controller_custom_video_settings_value(uint32_t index);
int pes_controller_custom_info_popup_active(void);
const char *pes_controller_custom_info_popup_title(void);
uint32_t pes_controller_custom_info_popup_line_count(void);
const char *pes_controller_custom_info_popup_line(uint32_t index);
int pes_controller_start_prompt(float *normalized_x, float *normalized_y);
int pes_controller_menu_scroll_request(void);
void pes_controller_menu_tap(float normalized_x, float normalized_y);
int pes_controller_menu_physical_tap(float normalized_x,
                                     float normalized_y);
void pes_controller_menu_physical_swipe(float start_x, float start_y,
                                         float end_x, float end_y);
void pes_exhibition_matchmaking_tap(float normalized_x, float normalized_y);
uintptr_t pes_exhibition_strategy_created_entry(void *strategy_flow,
                                                void *squad_edit);

#endif

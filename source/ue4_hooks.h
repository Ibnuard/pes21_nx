#ifndef __UE4_HOOKS_H__
#define __UE4_HOOKS_H__

#include "so_util.h"

#define PES_MOBILE_CONTROL_UNKNOWN 0
#define PES_MOBILE_CONTROL_OFFENSE 1
#define PES_MOBILE_CONTROL_DEFENSE 2

void install_ue4_hooks(so_module *module);
void ue4_hooks_post_finalize(so_module *module);
void cobra_pad_set_input(uint32_t buttons, int32_t up, int32_t down,
                         int32_t left, int32_t right, int connected);
uint32_t pes_mobile_control_context(int *mode);
int pes_mobile_control_active_mode(void);
int pes_controller_replay_active(void);
int pes_controller_menu_active(void);
int pes_controller_gameplan_cursor_active(void);
int pes_controller_gameplan_cursor_position(float *normalized_x,
                                            float *normalized_y);
void pes_controller_gameplan_cursor_set(float normalized_x,
                                        float normalized_y);
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
void pes_controller_title_ready(void);
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

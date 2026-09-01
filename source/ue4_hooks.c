#include <stdint.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <switch.h>

#include "aaudio_shim.h"
#include "config.h"
#include "match_visual_policy.h"
#include "error.h"
#include "so_util.h"
#include "ue4_hooks.h"
#include "util.h"

#define OBJECT_INITIALIZER_STATE_SLOTS 32
#define OBJECT_INITIALIZER_MAX_ITEMS (1 << 20)

#ifndef PES_NX_VERSION
#define PES_NX_VERSION "0.0.0"
#endif

typedef struct {
  void *data;
  int32_t num;
  int32_t max;
} Ue4Array;

typedef struct {
  Ue4Array *array;
  void *data;
  int32_t max;
  uint32_t growths;
} ObjectInitializerArrayState;

static ObjectInitializerArrayState object_initializer_states[
    OBJECT_INITIALIZER_STATE_SLOTS];
static void *(*ue4_fmemory_malloc)(uint64_t size, uint32_t alignment);

static _Alignas(8) uint64_t cobra_pad_input;
static _Alignas(4) uint32_t cobra_pad_connected;
static void native_pad_lab_reset(void);
static uintptr_t cobra_pad_update_resume;
static uintptr_t mobile_screen_tap_entry_resume;
static uintptr_t exhibition_flow_create_resume;
static uintptr_t exhibition_tutorial_main_resume;
static uintptr_t exhibition_strategy_main_resume;
static uintptr_t exhibition_strategy_created_resume;
static uintptr_t exhibition_training_touch_resume;
static uintptr_t exhibition_training_list_resume;
static uintptr_t exhibition_training_child_resume;
static uintptr_t exhibition_training_footer_resume;
static uintptr_t exhibition_filter_teams_resume;
static uintptr_t exhibition_string_get_resume;
static uintptr_t exhibition_search_post_resume;
static uintptr_t exhibition_search_user_name_resume;
static uintptr_t exhibition_search_task_ready_resume;
static uintptr_t match_replay_check_skip_resume;
static uintptr_t match_goal_demo_update_resume;
uintptr_t match_goal_demo_init_resume;
static uintptr_t match_pause_update_resume;
static uintptr_t match_pause_d1_resume;
static uintptr_t match_pause_d0_resume;
uintptr_t pes_match_pause_destructor_slot;
uintptr_t pes_match_squad_edit_update_resume;
uintptr_t pes_match_team_stats_update_resume;
uintptr_t pes_match_team_stats_debug_aging_get_state;
static uintptr_t match_result_full_resume;
static uintptr_t match_result_half_resume;
static uintptr_t match_result_half_update_resume;
static uintptr_t match_tutorial_guide_update_resume;
static uintptr_t match_flow_check_skip_fix_demo_resume;
static uintptr_t exhibition_match_setup_data_resume;
uintptr_t inplay_ball_position_broadcast_resume;
static uintptr_t ue4_tickrate_resume;
uintptr_t pes_virtual_pad_update_resume;
uintptr_t pes_main_menu_graphics_d1_resume;
uintptr_t pes_main_menu_graphics_d0_resume;
uintptr_t pes_main_menu_graphics_destructor_page;
uintptr_t pes_main_menu_graphics_d0_page;
static void **exhibition_flow_listener_instance;
static void (*exhibition_flow_direct_set)(void *transition,
                                           const char *flow_name);
static void *(*exhibition_matchplan_get_instance)(void);
static void (*exhibition_matchplan_setup_team)(void *data,
                                                const uint32_t *team_id,
                                                uint32_t home_away);
static void (*exhibition_matchplan_setup_tmpdb)(void *data);
static void (*exhibition_matchplan_update_tmpdb)(void *data);
static void (*exhibition_set_team)(const uint32_t *team_id,
                                   uint32_t home_away,
                                   uint32_t preserve_player_data);
static void (*exhibition_check_uniform)(const uint32_t *home_team_id,
                                        const uint32_t *away_team_id,
                                        uint32_t unused);
static uint32_t (*exhibition_match_get_uni_id)(const void *match,
                                               uint32_t home_away);
static void (*exhibition_match_set_uni_id)(void *match,
                                            uint32_t home_away,
                                            uint32_t uniform_id);
static const uint32_t *(*exhibition_match_get_extra_uniform_list)(
    void *match, const uint32_t *home_away, const uint32_t *index);
static void *(*exhibition_tmpdb_manager_get_instance)(void);
static void *(*exhibition_tmpdb_match_get_team)(void *match,
                                                 const uint32_t *home_away);
static void (*exhibition_tmpdb_match_set_user_id)(void *match,
                                                   uint32_t home_away,
                                                   uint32_t user_id);
static void *(*exhibition_online_parameter_get_instance)(void);
static uint32_t (*exhibition_parameter_common_get_user_id)(void *common);
static uint32_t (*exhibition_get_match_my_side)(void);
static void *(*exhibition_commonwork_update_team)(void *common_work,
                                                   const uint32_t *team_id);
static void *(*exhibition_commonwork_update_player)(void *common_work,
                                                     uint64_t player_id);
static uint64_t (*exhibition_get_player_id_by_unique_id)(
    const uint32_t *unique_id);
static void *(*exhibition_squad_edit_get_squad_data)(void *squad_edit,
                                                      uint32_t home_away);
static uint32_t (*exhibition_squad_data_get_player_count)(void *squad_data);
static void *(*exhibition_squad_data_get_player_by_index)(
    void *squad_data, const uint32_t *index);
static void (*exhibition_squad_edit_update_player)(
    void *squad_edit, const void *player_id, const void *player,
    uint32_t parameter_type);
static uint32_t (*exhibition_get_player_overall)(
    const void *player, const uint32_t *position, uint32_t condition);
static void (*exhibition_set_test_match_team_id)(uint32_t team_id);
static void (*exhibition_set_test_match_cpu_level)(uint32_t level);
static uint32_t (*exhibition_get_test_match_cpu_level)(void);
static uint32_t (*exhibition_match_get_match_level)(const void *match);
static void (*exhibition_match_set_match_level)(void *match, uint32_t level);
static uint32_t (*exhibition_match_get_time_zone)(const void *match);
static void (*exhibition_match_set_time_zone)(void *match,
                                               uint32_t time_zone);
static uint32_t (*exhibition_match_get_match_time)(const void *match);
static void (*exhibition_match_set_match_time)(void *match,
                                                uint32_t minutes);
static uint32_t (*exhibition_match_is_ex)(const void *match);
static void (*exhibition_match_set_ex)(void *match, uint32_t enabled);
static uint32_t (*exhibition_match_is_pk)(const void *match);
static void (*exhibition_match_set_pk)(void *match, uint32_t enabled);
static void (*match_pause_pad_event_back)(void *window);
static void (*match_pause_exec_event_decide)(void *window,
                                              const void *event_name);
static void (*matchplan_squad_load)(void);
static void (*matchplan_squad_save)(void);
static void *(*match_squad_data_get_tmpdb_player)(void *squad_data,
                                                   const void *player_id);
static const char *(*match_tmpdb_player_get_name)(const void *player);
static uint32_t (*match_tmpdb_player_get_data)(const void *player,
                                                uint32_t key,
                                                uint32_t *value);
static uint32_t (*match_squad_data_get_order_no)(void *squad_data,
                                                 const void *player_id);
static uint32_t (*match_squad_data_get_member_id)(void *squad_data,
                                                   const void *player_id);
static uint32_t (*match_squad_data_is_starting)(void *squad_data,
                                                const void *player_id);
static void (*match_swap_member_info_construct)(void *info,
                                                 uint32_t order_no,
                                                 uint32_t member_id,
                                                 const void *player_id);
static void (*match_replace_squad_player)(void *squad_data,
                                          const void *first,
                                          const void *second);
static uint32_t (*match_squad_data_get_tactics)(void *squad_data);
static void (*match_squad_data_set_tactics)(void *squad_data,
                                             uint32_t tactics);
static void (*match_pause_camera_swipe)(void *window, uint32_t old_page,
                                         uint32_t new_page);
static void (*match_pause_camera_footer)(void *window, uint32_t footer_key);
static uint32_t (*match_pause_camera_update_original)(void *window,
                                                       uint32_t pad_status);
static void (*match_result_exec_event_decide)(void *window,
                                               const void *event_name);
static void (*match_result_footer_touch)(void *window, uint32_t footer_key);
static void (*match_result_update_original)(void *window);
static void **match_listener_instance;
static uint32_t (*match_ball_position_broadcast_original)(
    void *camera, const float *blend, const uint32_t *home_away,
    float *target_position, float *zoom, uint32_t active);
static const float *(*match_ball_info_get_trans)(const void *ball_info);
static uint32_t (*match_goal_demo_get_goal_side)(const void *registry);
static uint32_t (*match_goal_demo_is_cpu_goal)(void *goal_demo,
                                               const void *registry);
static void *(*match_global_registry_get_instance)(void);
static uint32_t (*match_cursor_is_user_control_team)(
    const void *cursor_info, uint32_t home_away, uint32_t cursor_change_type);
static uint32_t (*match_goalkick_main_original)(void *unit,
                                                const void *input,
                                                uint32_t kind);
static uint32_t (*match_corner_main_original)(void *unit,
                                              const void *input,
                                              uint32_t kind);
static uint32_t (*match_freekick_main_original)(void *unit,
                                                 const void *input,
                                                 uint32_t kind);
static uint32_t (*match_freekick_is_disp_original)(const void *unit);
static uint32_t (*match_kicker_select_main_original)(void *unit,
                                                     const void *input,
                                                     uint32_t kind);
static uint32_t (*match_kicker_select_is_disp_enable)(const void *input);
static uint32_t (*match_goal_demo_pad_main_original)(void *unit,
                                                     const void *input,
                                                     uint32_t kind);
static uint32_t (*match_penalty_kicker_main_original)(void *unit,
                                                       const void *input,
                                                       uint32_t kind);
static uint32_t (*match_penalty_goalkeeper_main_original)(void *unit,
                                                           const void *input,
                                                           uint32_t kind);
static uint32_t (*match_penalty_goalkeeper_move_main_original)(
    void *unit, const void *input, uint32_t kind);
static void (*match_inmatch_tutorial_update_original)(void *window);
static void (*match_inmatch_tutorial_footer_touch)(void *window,
                                                    uint32_t footer_key);
static uint32_t (*match_inmatch_tutorial_is_explaining)(const void *window);
static uint32_t (*match_window_get_pad_key_active)(const void *window,
                                                   uint32_t key);
static uint32_t (*match_replay_mode_init_original)(void *replay,
                                                   const void *context);
static uint32_t (*match_replay_mode_main_original)(void *replay,
                                                   const void *context);
static uint32_t (*match_replay_mode_end_original)(void *replay,
                                                  const void *context);
static uint32_t (*match_demo_skip_main_original)(void *unit,
                                                 const void *input,
                                                 uint32_t kind);
static uint32_t (*match_outofplay_skip_main_original)(void *unit,
                                                      const void *input,
                                                      uint32_t kind);
static uint32_t (*match_button_setplay_need_disp_original)(void *window);
static void (*match_button_setplay_update_original)(void *window);
static void (*match_button_setplay_touch_sub_original)(
    void *window, const void *touch_info);
static void (*match_action_button_pad_event_touch)(void *window,
                                                   const void *touch_info);
static float (*match_action_button_get_disable_timer)(void *window,
                                                       uint32_t button_type);
static uint32_t (*match_setplay_camera_main_original)(
    void *unit, const void *input, uint32_t kind);
static void *(*match_global_registry_get_order_info)(const void *registry,
                                                     uint32_t side);
static uint32_t (*match_order_info_get_member_id)(const void *order_info,
                                                   uint32_t order_no);
static const void *(*match_tmpdb_match_get_player)(
    const void *match, const uint32_t *side, const uint32_t *member_id);
static void (*match_window_set_se)(void *window, uint32_t sound_id);
static void (*match_fix_demo_skip)(void);
static void *(*exhibition_match_setting_create_child)(
    const void *name, const uint8_t *enabled);
static uint32_t (*exhibition_is_test_match_original)(void);
static void *(*exhibition_status_get_instance)(void);
static void (*exhibition_status_set_game_mode)(void *status, uint32_t mode);
static void (*exhibition_set_pad_key_kind)(void *window, uint32_t key,
                                           uint32_t enabled);
static void (*exhibition_set_pad_key_string)(void *window, uint32_t key,
                                             uint32_t string_id);
static void (*exhibition_set_pad_key_active)(void *window, uint32_t key,
                                             uint32_t enabled);
static void (*exhibition_search_update_disp)(void *window);
static void (*exhibition_search_update_team_info)(void *window,
                                                   const uint32_t *side);
static void *(*exhibition_window_get_window)(void *window);
static int32_t (*match_node_set_alpha)(void *node, float alpha);
static void *(*match_setplay_get_root)(void *window);
static void (*match_visual_model_action_original)(void *manager);
static void (*match_visual_model_set_disp)(void *model, uint32_t visible);
static void *(*exhibition_holder_get_duplicate)(void *holder,
                                                 uint32_t index);
static void (*exhibition_node_set_visible)(void *node, uint32_t visible,
                                            uint32_t flags);
static void (*exhibition_text_set_string)(void *text, const void *string);
static void (*exhibition_emblem_set_team)(void *emblem,
                                          const uint32_t *team_id,
                                          uint32_t use_nation,
                                          uint32_t symbol_type,
                                          uint32_t unused,
                                          uint32_t symbol_color);
static void (*exhibition_search_footer_original)(void *window, uint32_t key);
static void (*exhibition_search_touch_original)(void *window,
                                                 const void *touch_info);
static void *(*exhibition_team_select_create_child)(const void *name,
                                                     uint32_t unused,
                                                     void *parent,
                                                     uint32_t team_id,
                                                     uint32_t a,
                                                     uint32_t b,
                                                     uint32_t c);
static void (*exhibition_task_add_unit)(void *parent, void *child);
static void (*exhibition_setup_usable_teams)(void);
static void (*exhibition_team_select_set_usable)(void *selector,
                                                  uint32_t enabled);
static void (*exhibition_training_footer_original)(void *window,
                                                    uint32_t key);
static uint32_t (*exhibition_strategy_update_original)(void *window,
                                                        uint32_t pad_status);
static void (*exhibition_strategy_footer_original)(void *window,
                                                    uint32_t key);
static const void *(*exhibition_user_info_get_name)(void *user_info);
static void *(*exhibition_parameter_get_instance)(uint32_t create);
static void (*exhibition_parameter_myclub_create_work)(void *myclub);
static void (*main_menu_choice_set_active)(void *choice, uint32_t active,
                                           uint32_t reaction,
                                           uint32_t flags);
static void *(*main_menu_graphics_create)(const void *name,
                                          const uint8_t *modal);
static uint32_t (*main_menu_save_graphics_quality)(uint32_t quality);
static uint32_t (*main_menu_get_graphics_quality)(void);
static uint32_t (*main_menu_save_frame_rate)(uint32_t mode);
static void (*main_menu_set_frame_rate_mode)(uint32_t mode);
static uint32_t (*main_menu_get_frame_rate_mode)(void);
static void *(*main_menu_get_ue_bridge)(void);
static uintptr_t main_menu_selected_resume;
static void *main_menu_tiles[4];
static void *main_menu_match_page;
static uint32_t main_menu_focus_index;
static uint32_t main_menu_focus_direction;
static uint64_t main_menu_focus_started_ms;
static uint64_t main_menu_focus_repeat_ms;
static int main_menu_focus_painted;
static const char *main_menu_titles[4] = {
    "Exhibition", "Credits", "2 Player", "Settings"};
static const char *main_menu_descriptions[4] = {
    "Local match", "Credits and support", "Native Pad Lab",
    "Graphics and FPS"};
static uint32_t (*mobile_is_mode_offense)(const void *control_mode);
static uint32_t (*mobile_is_mode_defense)(const void *control_mode);
static void (*virtual_pad_set_color)(void *movie_clip, float red, float green,
                                     float blue, float alpha);
static _Alignas(4) uint32_t mobile_control_mode;
static _Alignas(4) uint32_t mobile_control_generation;
static _Alignas(8) uint64_t mobile_control_seen_tick;
static uint64_t cobra_pad_last_applied = UINT64_MAX;
static unsigned int cobra_pad_apply_log_count;
static unsigned int cursor_pad_log_count;
static unsigned int real_pad_log_count;
static unsigned int mobile_context_log_count;
static unsigned int exhibition_flow_log_count;
static void *(*sound_file_binder_get_instance)(void);
static int32_t (*sound_file_binder_attach_sound_cpk)(void *binder);
static uint32_t (*sound_file_binder_is_ready)(void *binder);
static _Alignas(4) uint32_t commentary_sound_cpk_state;

// The mobile binary hardcodes the commentary ACB namespace as cpk_snd/xxx,
// while its AWB path can inherit an unsupported sound-language sentinel. This
// port currently ships the English dt510/dt530 pack, so keep loading and match
// settings on English.
static uint32_t pes_sound_language_english(void) {
  return 0;
}

static const char *pes_sound_language_name_english(uint32_t language) {
  (void)language;
  return "eng";
}

static void pes_attach_commentary_sound_cpk(void) {
  if (commentary_sound_cpk_state != 0)
    return;

  commentary_sound_cpk_state = 1;
  void *binder = sound_file_binder_get_instance();
  if (!binder) {
    commentary_sound_cpk_state = 0;
    return;
  }

  sound_file_binder_attach_sound_cpk(binder);
  for (uint32_t attempt = 0; attempt < 5000; attempt++) {
    if (sound_file_binder_is_ready(binder)) {
      // Advance the game's attach state once more for its error/version checks.
      sound_file_binder_attach_sound_cpk(binder);
      commentary_sound_cpk_state = 2;
#ifdef DEBUG_LOG
      debugPrintf("sound: AttachSoundCpk binder ready after %u attempts\n",
                  attempt + 1);
#endif
      return;
    }
    svcSleepThread(1000000LL);
  }

  commentary_sound_cpk_state = 0;
#ifdef DEBUG_LOG
  debugPrintf("sound: AttachSoundCpk timed out\n");
#endif
}

static int32_t pes_sound_language_string3_english(char *language,
                                                   uint32_t uppercase) {
  if (!language)
    return -1;

  if (!uppercase)
    pes_attach_commentary_sound_cpk();

  language[0] = uppercase ? 'E' : 'e';
  language[1] = uppercase ? 'N' : 'n';
  language[2] = uppercase ? 'G' : 'g';
  language[3] = '\0';
#ifdef DEBUG_LOG
  debugPrintf("sound: forced sound language=%s uppercase=%u\n", language,
              uppercase);
#endif
  return 0;
}

static uint32_t pes_use_commentary_enabled(void) {
  return 1;
}

#ifdef DEBUG_LOG
static int32_t (*sound_cinf_play_original)(const void *play_info,
                                           uint64_t *handle);
static int32_t (*sound_music_set_event_original)(int32_t event_id);
static int32_t (*sound_mount_data_original)(void *acb_data, uint32_t acb_size,
                                            void *binder,
                                            const char *awb_path,
                                            uint16_t mount_flags,
                                            uint16_t search_flags,
                                            int16_t *mount_id);
static int32_t (*sound_file_is_exist_original)(const char *path);
static int32_t (*sound_set_game_option_volume_original)(uint32_t type,
                                                        float volume);
static int32_t (*sound_set_category_volume_original)(const char *category,
                                                     float volume);
static int32_t (*sound_cri_bind_cpk_original)(void *binder,
                                              void *source_binder,
                                              const char *path,
                                              void *work,
                                              int32_t work_size,
                                              uint32_t *bind_id);
static float (*sound_get_category_volume)(const char *category);
static float (*sound_get_category_total_volume)(const char *category);
static unsigned int sound_play_log_count;
static unsigned int sound_mount_log_count;

static int32_t pes_sound_cinf_play_diagnostic(const void *play_info,
                                              uint64_t *handle) {
  uint64_t words[4] = {0, 0, 0, 0};
  if (play_info)
    memcpy(words, play_info, sizeof(words));
  const int32_t result = sound_cinf_play_original(play_info, handle);
  if (sound_play_log_count++ < 128) {
    debugPrintf("sound: CInfBase::Play result=%d handle=%p/0x%llx "
                "info=%p words=%016llx,%016llx,%016llx,%016llx\n",
                result, handle,
                (unsigned long long)(handle ? *handle : 0), play_info,
                (unsigned long long)words[0],
                (unsigned long long)words[1],
                (unsigned long long)words[2],
                (unsigned long long)words[3]);
  }
  return result;
}

static int32_t pes_sound_music_set_event_diagnostic(int32_t event_id) {
  const int32_t result = sound_music_set_event_original(event_id);
  debugPrintf("sound: MusicManager::SetEventId id=%d result=%d\n",
              event_id, result);
  return result;
}

static int32_t pes_sound_mount_data_diagnostic(
    void *acb_data, uint32_t acb_size, void *binder, const char *awb_path,
    uint16_t mount_flags, uint16_t search_flags, int16_t *mount_id) {
  const int32_t result = sound_mount_data_original(
      acb_data, acb_size, binder, awb_path, mount_flags, search_flags,
      mount_id);
  if (sound_mount_log_count++ < 128) {
    debugPrintf("sound: CInfBase::MountData result=%d mount=%d acb=%p/%u "
                "binder=%p awb=%s flags=%u/%u\n",
                result, mount_id ? *mount_id : -1, acb_data, acb_size, binder,
                awb_path ? awb_path : "(null)", mount_flags, search_flags);
  }
  return result;
}

static int32_t pes_sound_file_is_exist_diagnostic(const char *path) {
  const int32_t result = sound_file_is_exist_original(path);
  if (path && (strstr(path, ".acf") || strstr(path, ".acb") ||
               strstr(path, ".awb") || strstr(path, "sound/"))) {
    debugPrintf("sound: File::IsExist path=%s result=%d\n", path, result);
  }
  return result;
}

static int32_t pes_sound_set_game_option_volume_diagnostic(uint32_t type,
                                                           float volume) {
  const int32_t result =
      sound_set_game_option_volume_original(type, volume);
  debugPrintf("sound: SetGameOptionVolume type=%u volume=%f result=%d\n",
              type, volume, result);
  if (type == 2) {
    static const char *const default_categories[] = {
        "DefVol_Menu_SFX", "DefVol_Menu_Music", "DefVol_Commentary",
        "DefVol_Chant",
    };
    for (unsigned int index = 0;
         index < sizeof(default_categories) / sizeof(default_categories[0]);
         index++) {
      float category_volume = -1.0f;
      float total_volume = -1.0f;
      category_volume =
          sound_get_category_volume(default_categories[index]);
      total_volume =
          sound_get_category_total_volume(default_categories[index]);
      debugPrintf("sound: default category=%s volume=%f total=%f\n",
                  default_categories[index], category_volume, total_volume);
    }
  }
  return result;
}

static int32_t pes_sound_set_category_volume_diagnostic(
    const char *category, float volume) {
  const int32_t result =
      sound_set_category_volume_original(category, volume);
  float category_volume = -1.0f;
  float total_volume = -1.0f;
  if (category) {
    category_volume = sound_get_category_volume(category);
    total_volume = sound_get_category_total_volume(category);
  }
  debugPrintf("sound: SetCategoryVolume category=%s volume=%f result=%d "
              "read=%f total=%f\n",
              category ? category : "(null)", volume, result,
              category_volume, total_volume);
  return result;
}

static int32_t pes_sound_cri_bind_cpk_diagnostic(
    void *binder, void *source_binder, const char *path, void *work,
    int32_t work_size, uint32_t *bind_id) {
  const int32_t result = sound_cri_bind_cpk_original(
      binder, source_binder, path, work, work_size, bind_id);
  debugPrintf("sound: criFsBinder_BindCpk path=%s result=%d bind=%u "
              "binder=%p source=%p work=%p/%d\n",
              path ? path : "(null)", result, bind_id ? *bind_id : 0,
              binder, source_binder, work, work_size);
  return result;
}
#endif
static _Alignas(4) uint32_t exhibition_requested;
// Armed only from the main-menu 2P tile, which is currently a ONE-player
// native-input proof. Normal Exhibition remains on synthetic touch.
static _Alignas(4) uint32_t native_gamepad_lab_active;
static _Alignas(4) uint32_t native_gamepad_lab_autostart;
static _Alignas(4) uint32_t exhibition_strategy_pending;
static _Alignas(4) uint32_t exhibition_session_active;
static _Alignas(4) uint32_t exhibition_team_select_active;
static _Alignas(4) uint32_t exhibition_select_side;
static _Alignas(4) uint32_t exhibition_strategy_action;
static _Alignas(4) uint32_t exhibition_plan_ready;
static _Alignas(4) uint32_t exhibition_return_to_selector;
static _Alignas(4) uint32_t exhibition_gameplan_custom_active;
static _Alignas(4) uint32_t exhibition_gameplan_custom_page;
static _Alignas(4) uint32_t exhibition_gameplan_custom_focus;
static _Alignas(4) uint32_t exhibition_gameplan_custom_action;
#define EXHIBITION_UNIFORM_CHOICE_MAX 7u
static uint32_t exhibition_uniform_choices[2][EXHIBITION_UNIFORM_CHOICE_MAX];
static uint32_t exhibition_uniform_choice_count[2];
static uint32_t exhibition_uniform_choice_index[2];
static _Alignas(4) uint32_t virtual_cursor_context;
static _Alignas(4) uint32_t exhibition_gameplan_cursor_x = 32768;
static _Alignas(4) uint32_t exhibition_gameplan_cursor_y = 32768;
static _Alignas(4) uint32_t exhibition_searching_active;
static _Alignas(4) uint32_t exhibition_search_refresh_pending;
static _Alignas(4) uint32_t exhibition_search_initial_refresh_ticks;
static _Alignas(4) uint32_t exhibition_search_touch_pending;
static _Alignas(4) uint32_t exhibition_team_picker_open;
static _Alignas(4) uint32_t exhibition_cpu_level_popup_open;
static _Alignas(4) uint32_t exhibition_settings_popup_open;
static _Alignas(4) uint32_t exhibition_cpu_level_value = 2;
static _Alignas(4) uint32_t exhibition_settings_time_zone;
static _Alignas(4) uint32_t exhibition_settings_match_time = 10;
static _Alignas(4) uint32_t exhibition_settings_extra_time;
static _Alignas(4) uint32_t exhibition_settings_penalties;
static _Alignas(4) uint32_t exhibition_match_settings_armed;
static void *exhibition_settings_match;
// A settings child can open another list without closing menuMatchSetting.
// Keep that child separate so the controller focus follows the visible list.
static _Alignas(4) uint32_t exhibition_nested_popup_open;
static _Alignas(4) uint32_t exhibition_nested_popup_kind;
// Keep the nested selector alive until the native child has processed B.
// Clearing it on the synthetic touch release makes the overlay jump back to
// Match Settings one frame too early.
static _Alignas(4) uint32_t exhibition_nested_back_pending;
static _Alignas(8) uint64_t exhibition_nested_back_started_ms;
static _Alignas(4) uint32_t main_menu_controller_active;
static _Alignas(4) uint32_t main_menu_graphics_active;
static _Alignas(4) uint32_t main_menu_video_settings_open;
static _Alignas(4) uint32_t main_menu_info_popup;
static _Alignas(4) uint32_t main_menu_video_graphics = 1;
// Native FRAME_RATE_MODE values are 0 = 60 fps and 1 = 30 fps.
static _Alignas(4) uint32_t main_menu_video_frame_rate;
static uint32_t main_menu_video_apply_held;
static uint32_t main_menu_video_focus_index;
static uint32_t main_menu_video_focus_direction;
static uint64_t main_menu_video_focus_started_ms;
static uint64_t main_menu_video_focus_repeat_ms;
static _Alignas(8) uint64_t main_menu_video_opened_ms;
static _Alignas(4) uint32_t startup_prompt_active;
static void *exhibition_search_window;
static uint32_t exhibition_search_focus_index;
static uint32_t exhibition_search_focus_direction;
static uint64_t exhibition_search_focus_started_ms;
static uint64_t exhibition_search_focus_repeat_ms;
static uint32_t exhibition_popup_focus_index;
static uint32_t exhibition_popup_focus_direction;
static uint64_t exhibition_popup_focus_started_ms;
static uint64_t exhibition_popup_focus_repeat_ms;
static _Alignas(8) uint64_t exhibition_custom_popup_opened_ms;
static _Alignas(4) int32_t exhibition_popup_scroll_request;
// Switch-style team browser. Phase 1 selects a category; phase 2 selects a
// team. Both use a paginated 2x4 grid and never depend on native list pixels.
static _Alignas(4) uint32_t exhibition_custom_team_popup;
static _Alignas(4) uint32_t exhibition_team_scroll_offset;
static _Alignas(4) uint32_t exhibition_team_category_index;
#define EXHIBITION_TEAM_GRID_PAGE_SIZE 8u
#define EXHIBITION_INITIAL_REFRESH_TICKS 180u
#define EXHIBITION_FALLBACK_HOME_TEAM 100u
#define EXHIBITION_FALLBACK_AWAY_TEAM 101u
static _Alignas(4) uint32_t exhibition_home_team_id;
static _Alignas(4) uint32_t exhibition_away_team_id;
static _Alignas(8) uint64_t match_replay_seen_tick;
static _Alignas(8) uintptr_t match_replay_owner;
static _Alignas(4) uint32_t match_replay_goal_active;
static _Alignas(4) uint32_t match_replay_feedback_value;
static _Alignas(8) uint64_t match_replay_feedback_tick;
static _Alignas(8) uint64_t match_goal_demo_seen_tick;
static _Alignas(8) uint64_t match_goal_demo_pad_seen_tick;
static _Alignas(4) uint32_t match_goal_demo_player_goal;
static _Alignas(4) uint32_t match_goal_demo_owner_known;
static _Alignas(4) uint32_t match_goal_demo_helper_consumed;
// Generic cinematic detector.  Replay/GoalDemo transition hooks are kept
// disabled because their object layouts differ between mobile builds; this
// state is inferred from the safe mobile-control heartbeat instead.
static _Alignas(8) uintptr_t match_demo_skip_owner;
static _Alignas(8) uint64_t match_demo_skip_seen_tick;
static _Alignas(8) uintptr_t match_outofplay_skip_owner;
static _Alignas(8) uint64_t match_outofplay_skip_seen_tick;
static _Alignas(8) uintptr_t match_demo_skip_request_owner;
static _Alignas(8) uint64_t match_demo_skip_request_tick;
static _Alignas(8) uint64_t match_pause_seen_tick;
static _Alignas(4) uint32_t match_pause_back_requested;
static _Alignas(4) uint32_t match_pause_custom_active;
static _Alignas(4) uint32_t match_pause_custom_focus;
static _Alignas(4) uint32_t match_pause_custom_action;
static _Alignas(4) uint32_t match_pause_custom_page;
static _Alignas(4) uint32_t match_gameplan_starter_index;
static _Alignas(4) uint32_t match_gameplan_bench_index;
static _Alignas(4) uint32_t match_gameplan_focus;
static _Alignas(4) uint32_t match_gameplan_tactics;
static void *match_gameplan_squad_data;
#define MATCH_GAMEPLAN_MAX_PLAYERS 40u
typedef struct {
  unsigned char player_id[16];
  char name[48];
  uint8_t starting;
} MatchGameplanPlayer;
static MatchGameplanPlayer match_gameplan_players[MATCH_GAMEPLAN_MAX_PLAYERS];
static uint32_t match_gameplan_player_count;
static uint32_t match_gameplan_starter_count;
static uint32_t match_gameplan_bench_count;
static _Alignas(8) uint64_t match_pause_camera_seen_tick;
static _Alignas(4) uint32_t match_pause_camera_action;
static void *match_pause_camera_window;
static _Alignas(4) uint32_t match_gameplan_pause_route;
static _Alignas(4) uint32_t match_result_input_action;
static _Alignas(4) uint32_t match_result_exit_requested;
static _Alignas(8) uint64_t match_fix_demo_skip_seen_tick;
static _Alignas(8) uint64_t match_tutorial_guide_seen_tick;
static _Alignas(8) uintptr_t match_inmatch_tutorial_owner;
static _Alignas(8) uint64_t match_inmatch_tutorial_seen_tick;
static _Alignas(4) uint32_t match_inmatch_tutorial_play_pending;
static void *match_result_window;
static _Alignas(4) uint32_t match_postmatch_custom_active;
static _Alignas(4) uint32_t match_postmatch_custom_page;
static _Alignas(4) uint32_t match_postmatch_custom_focus;
static _Alignas(4) uint32_t match_postmatch_custom_action;
static void *match_postmatch_window;
static _Alignas(8) uint64_t match_result_seen_tick;
static _Alignas(8) uint64_t match_result_started_tick;
static _Alignas(8) uint64_t match_gameplan_seen_tick;
static _Alignas(8) uint64_t match_kicker_select_seen_tick;
static _Alignas(4) uint32_t match_native_setplay_context;
static _Alignas(4) uint32_t match_penalty_role;
static _Alignas(8) uint64_t match_penalty_seen_tick;
static _Alignas(8) uintptr_t match_button_setplay_owner;
static _Alignas(8) uint64_t match_button_setplay_seen_tick;
static _Alignas(4) uint32_t match_button_setplay_mask;
static _Alignas(4) uint32_t match_button_setplay_pending_type;
static _Alignas(4) uint32_t match_button_setplay_pending_generation;
static _Alignas(8) uint64_t match_button_setplay_pending_tick;
// Low 32 bits hold the semantic controller surface; high 32 bits are a
// transition generation. Heartbeat refreshes intentionally do not advance it.
static _Alignas(8) uint64_t match_controller_surface_word;
#define MATCH_KICKER_SELECTOR_MAX_PLAYERS 11u
typedef struct {
  uint32_t order_no;
  uint32_t player_id;
  uint32_t current;
  char name[48];
  char foot[16];
} MatchKickerSelectorPlayer;
static MatchKickerSelectorPlayer
    match_kicker_selector_players[2][MATCH_KICKER_SELECTOR_MAX_PLAYERS];
static _Alignas(4) uint32_t match_kicker_selector_bank;
static _Alignas(4) uint32_t match_kicker_selector_count;
static _Alignas(4) uint32_t match_kicker_selector_focus;
static _Alignas(4) uint32_t match_kicker_selector_context;
static _Alignas(4) uint32_t match_kicker_selector_armed;
static _Alignas(4) uint32_t match_kicker_selector_open;
static _Alignas(4) uint32_t match_kicker_selector_pending_action;
static _Alignas(8) uintptr_t match_kicker_selector_button_owner;
static _Alignas(8) uint64_t match_camera_ball_seen_tick;
static float match_camera_previous_ball[3];
static uint32_t match_camera_previous_ball_valid;

static int match_native_demo_active_at(uint64_t now, uintptr_t *owner_out);

enum {
  EXHIBITION_STRATEGY_NONE = 0,
  EXHIBITION_STRATEGY_EDIT = 1,
  EXHIBITION_STRATEGY_START = 2,
};

enum {
  EXHIBITION_GAMEPLAN_PAGE_ROOT = 0,
  EXHIBITION_GAMEPLAN_PAGE_SUBSTITUTION = 1,
  EXHIBITION_GAMEPLAN_PAGE_FORMATION = 2,
};

enum {
  MATCH_POSTMATCH_PAGE_ROOT = 0,
  MATCH_POSTMATCH_PAGE_GAMEPLAN = 1,
  MATCH_POSTMATCH_PAGE_SUBSTITUTION = 2,
  MATCH_POSTMATCH_PAGE_FORMATION = 3,
};

enum {
  MAIN_MENU_INFO_CLOSED = 0,
  MAIN_MENU_INFO_CREDITS = 1,
  MAIN_MENU_INFO_TWO_PLAYER = 2,
};

enum {
  MATCH_PAUSE_PAGE_ROOT = 0,
  MATCH_PAUSE_PAGE_GAMEPLAN = 1,
  MATCH_PAUSE_PAGE_SUBSTITUTION = 2,
  MATCH_PAUSE_PAGE_FORMATION = 3,
};

enum {
  EXHIBITION_NESTED_NONE = 0,
  EXHIBITION_NESTED_SHORT_LIST = 1,
  EXHIBITION_NESTED_LONG_LIST = 2,
};

enum {
  EXHIBITION_TEAM_POPUP_CLOSED = 0,
  EXHIBITION_TEAM_POPUP_CATEGORY = 1,
  EXHIBITION_TEAM_POPUP_TEAM = 2,
};

static void exhibition_open_match_settings(void *window);
static void exhibition_open_cpu_level(void);
static void exhibition_set_matchmaking_visible(void *window,
                                                uint32_t visible);
static uint64_t exhibition_search_focus_now_ms(void);
static void exhibition_select_team(uint32_t side, uint32_t team_id);
static void exhibition_adjust_match_setting(int direction);
static uint64_t main_menu_focus_now_ms(void);
static void pes_exhibition_strategy_footer(void *window,
                                           uint32_t footer_key);
static void main_menu_video_adjust(int direction);
static void main_menu_video_apply_current(void);
static void main_menu_video_close(void);
static void main_menu_info_close(void);
static void main_menu_apply_focus(uint32_t index);
static void *exhibition_find_root_node(void *root, const char *name);
static void pes_virtual_cursor_activate(uint32_t context, uint32_t x,
                                        uint32_t y);

static void exhibition_nested_back_expire(void) {
  if (!__atomic_load_n(&exhibition_nested_back_pending, __ATOMIC_ACQUIRE))
    return;
  const uint64_t started =
      __atomic_load_n(&exhibition_nested_back_started_ms, __ATOMIC_ACQUIRE);
  if (started && exhibition_search_focus_now_ms() - started >= 700) {
    __atomic_store_n(&exhibition_nested_popup_open, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_nested_popup_kind, EXHIBITION_NESTED_NONE,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_nested_back_pending, 0, __ATOMIC_RELEASE);
    exhibition_popup_focus_index = 0;
    exhibition_popup_focus_direction = 0;
  }
}

static const uint32_t exhibition_category_english[] = {
    100, 101, 102, 103, 104, 105, 106, 107, 173, 177, 179, 377};
static const uint32_t exhibition_category_spanish[] = {108, 109, 110, 111};
static const uint32_t exhibition_category_french[] = {112, 113, 114, 115};
static const uint32_t exhibition_category_italian[] = {
    119, 120, 121, 122, 123, 124, 125};
static const uint32_t exhibition_category_dutch[] = {116, 117, 118};
static const uint32_t exhibition_category_german[] = {127, 128};
static const uint32_t exhibition_category_other_europe[] = {
    130, 131, 132, 133, 134, 135, 191, 192, 193, 234, 327, 333};
static const uint32_t exhibition_category_south_america_clubs[] = {
    136, 137, 138, 139};
static const uint32_t exhibition_category_national_europe[] = {
    1,  2,  3,  4,  5,  6,  7,  8,  9,  10, 11, 12, 13, 14, 15,
    16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 30, 31};
static const uint32_t exhibition_category_national_africa[] = {
    32, 33, 34, 35, 36, 37, 38};
static const uint32_t exhibition_category_national_north_america[] = {
    39, 40, 41, 42, 43};
static const uint32_t exhibition_category_national_south_america[] = {
    44, 45, 46, 47, 48, 49, 50, 51};
static const uint32_t exhibition_category_national_asia[] = {
    52, 53, 54, 55, 56, 57, 59};

typedef struct {
  const char *label;
  const char *icon;
  const uint32_t *teams;
  uint32_t team_count;
} ExhibitionTeamCategory;

#define EXHIBITION_CATEGORY(label_value, icon_value, array_value)          \
  {                                                                        \
      label_value, icon_value, array_value,                                \
      (uint32_t)(sizeof(array_value) / sizeof((array_value)[0])),           \
  }
static const ExhibitionTeamCategory exhibition_team_categories[] = {
    EXHIBITION_CATEGORY("ENGLISH LEAGUE", "ENG",
                        exhibition_category_english),
    EXHIBITION_CATEGORY("SPANISH LEAGUE", "ESP",
                        exhibition_category_spanish),
    EXHIBITION_CATEGORY("LIGUE 1", "FRA", exhibition_category_french),
    EXHIBITION_CATEGORY("SERIE A", "ITA", exhibition_category_italian),
    EXHIBITION_CATEGORY("EREDIVISIE", "NED", exhibition_category_dutch),
    EXHIBITION_CATEGORY("GERMAN TEAMS", "GER", exhibition_category_german),
    EXHIBITION_CATEGORY("OTHER EUROPE", "EUR",
                        exhibition_category_other_europe),
    EXHIBITION_CATEGORY("SOUTH AMERICA CLUBS", "SAM",
                        exhibition_category_south_america_clubs),
    EXHIBITION_CATEGORY("NATIONAL EUROPE", "EUR",
                        exhibition_category_national_europe),
    EXHIBITION_CATEGORY("NATIONAL AFRICA", "AFR",
                        exhibition_category_national_africa),
    EXHIBITION_CATEGORY("NATIONAL N AMERICA", "NAM",
                        exhibition_category_national_north_america),
    EXHIBITION_CATEGORY("NATIONAL S AMERICA", "SAM",
                        exhibition_category_national_south_america),
    EXHIBITION_CATEGORY("NATIONAL ASIA OCEANIA", "AOC",
                        exhibition_category_national_asia),
};
#undef EXHIBITION_CATEGORY

#define EXHIBITION_TEAM_CATEGORY_COUNT                                  \
  ((uint32_t)(sizeof(exhibition_team_categories) /                       \
              sizeof(exhibition_team_categories[0])))

static const ExhibitionTeamCategory *exhibition_team_category(void) {
  return exhibition_team_category_index < EXHIBITION_TEAM_CATEGORY_COUNT
             ? &exhibition_team_categories[exhibition_team_category_index]
             : NULL;
}

static uint32_t exhibition_custom_team_item_count(void) {
  if (__atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE) ==
      EXHIBITION_TEAM_POPUP_TEAM) {
    const ExhibitionTeamCategory *category = exhibition_team_category();
    return category ? category->team_count : 0;
  }
  return EXHIBITION_TEAM_CATEGORY_COUNT;
}

#define EXHIBITION_CPU_LEVEL_COUNT 7u

static const char *const exhibition_cpu_level_labels[] = {
    "BEGINNER", "AMATEUR", "REGULAR", "PROFESSIONAL", "TOP PLAYER",
    "SUPERSTAR", "LEGEND",
};

static void *exhibition_get_tmpdb_match(void) {
  void *manager = exhibition_tmpdb_manager_get_instance
                      ? exhibition_tmpdb_manager_get_instance()
                      : NULL;
  void *tmpdb_data = NULL;
  if (manager)
    memcpy(&tmpdb_data, (unsigned char *)manager + 72,
           sizeof(tmpdb_data));
  return tmpdb_data ? (unsigned char *)tmpdb_data + 0x4b38 : NULL;
}

// DebugMode owns the selector's global value, while MatchSetup reads the
// per-match tmpdb field. Keep both copies synchronized whenever the player
// changes COM difficulty and again after match-plan data is rebuilt.
static void exhibition_apply_cpu_level(uint32_t level, void *match) {
  if (level >= EXHIBITION_CPU_LEVEL_COUNT)
    level = 2;
  if (exhibition_set_test_match_cpu_level)
    exhibition_set_test_match_cpu_level(level);
  if (!match)
    match = exhibition_get_tmpdb_match();
  if (match && exhibition_match_set_match_level)
    exhibition_match_set_match_level(match, level);
  __atomic_store_n(&exhibition_cpu_level_value, level, __ATOMIC_RELEASE);
}

// MatchSetup rebuilds parts of tmpdb::Match after the custom selector closes.
// Reapply every visible rule as one transaction at each hand-off so Extra
// Time and PK cannot silently fall back to the tutorial-flow defaults.
static void exhibition_apply_match_settings(void *match) {
  if (!match)
    match = exhibition_get_tmpdb_match();
  if (!match)
    return;

  const uint32_t time_zone = __atomic_load_n(
      &exhibition_settings_time_zone, __ATOMIC_ACQUIRE);
  const uint32_t match_time = __atomic_load_n(
      &exhibition_settings_match_time, __ATOMIC_ACQUIRE);
  const uint32_t extra_time = __atomic_load_n(
      &exhibition_settings_extra_time, __ATOMIC_ACQUIRE);
  const uint32_t penalties = __atomic_load_n(
      &exhibition_settings_penalties, __ATOMIC_ACQUIRE);
  if (exhibition_match_set_time_zone)
    exhibition_match_set_time_zone(match, time_zone);
  if (exhibition_match_set_match_time)
    exhibition_match_set_match_time(match, match_time);
  if (exhibition_match_set_ex)
    exhibition_match_set_ex(match, extra_time);
  if (exhibition_match_set_pk)
    exhibition_match_set_pk(match, penalties);
  debugPrintf("exhibition: committed match rules time=%u zone=%u ex=%u pk=%u "
              "match=%p\n",
              match_time, time_zone, extra_time, penalties, match);
}

uintptr_t pes_exhibition_match_setup_data_entry(void) {
  if (__atomic_load_n(&exhibition_match_settings_armed, __ATOMIC_ACQUIRE)) {
    exhibition_apply_cpu_level(
        __atomic_load_n(&exhibition_cpu_level_value, __ATOMIC_ACQUIRE), NULL);
    exhibition_apply_match_settings(NULL);
  }
  return exhibition_match_setup_data_resume;
}

static int exhibition_refresh_match_settings(void) {
  void *match = exhibition_get_tmpdb_match();
  if (!match)
    return 0;

  uint32_t time_zone = exhibition_match_get_time_zone
                           ? exhibition_match_get_time_zone(match)
                           : 0;
  uint32_t match_time = exhibition_match_get_match_time
                            ? exhibition_match_get_match_time(match)
                            : 10;
  if (time_zone > 1)
    time_zone = 0;
  if (match_time < 5 || match_time > 10)
    match_time = 10;

  exhibition_settings_match = match;
  if (exhibition_match_get_match_level) {
    const uint32_t level = exhibition_match_get_match_level(match);
    if (level < EXHIBITION_CPU_LEVEL_COUNT)
      __atomic_store_n(&exhibition_cpu_level_value, level, __ATOMIC_RELEASE);
  }
  __atomic_store_n(&exhibition_settings_time_zone, time_zone,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_settings_match_time, match_time,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_settings_extra_time,
                   exhibition_match_is_ex
                       ? (exhibition_match_is_ex(match) != 0)
                       : 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_settings_penalties,
                   exhibition_match_is_pk
                       ? (exhibition_match_is_pk(match) != 0)
                       : 0,
                   __ATOMIC_RELEASE);
  return 1;
}

static void exhibition_adjust_match_setting(int direction) {
  void *match = exhibition_settings_match;
  if (!match || !direction ||
      !__atomic_load_n(&exhibition_settings_popup_open, __ATOMIC_ACQUIRE))
    return;

  const uint32_t focus = exhibition_popup_focus_index;
  uint32_t value = 0;
  if (focus == 0) {
    value = !__atomic_load_n(&exhibition_settings_time_zone,
                             __ATOMIC_ACQUIRE);
    if (exhibition_match_set_time_zone)
      exhibition_match_set_time_zone(match, value);
    __atomic_store_n(&exhibition_settings_time_zone, value,
                     __ATOMIC_RELEASE);
  } else if (focus == 1) {
    value = __atomic_load_n(&exhibition_settings_match_time,
                            __ATOMIC_ACQUIRE);
    if (direction < 0)
      value = value <= 5 ? 10 : value - 1;
    else
      value = value >= 10 ? 5 : value + 1;
    if (exhibition_match_set_match_time)
      exhibition_match_set_match_time(match, value);
    __atomic_store_n(&exhibition_settings_match_time, value,
                     __ATOMIC_RELEASE);
  } else if (focus == 2) {
    value = !__atomic_load_n(&exhibition_settings_extra_time,
                             __ATOMIC_ACQUIRE);
    if (exhibition_match_set_ex)
      exhibition_match_set_ex(match, value);
    __atomic_store_n(&exhibition_settings_extra_time, value,
                     __ATOMIC_RELEASE);
  } else if (focus == 3) {
    value = !__atomic_load_n(&exhibition_settings_penalties,
                             __ATOMIC_ACQUIRE);
    if (exhibition_match_set_pk)
      exhibition_match_set_pk(match, value);
    __atomic_store_n(&exhibition_settings_penalties, value,
                     __ATOMIC_RELEASE);
  } else if (focus == 4) {
    value = !__atomic_load_n(&config.player_cursor_show, __ATOMIC_ACQUIRE);
    __atomic_store_n(&config.player_cursor_show, value, __ATOMIC_RELEASE);
    write_config(CONFIG_NAME);
  } else {
    return;
  }

  debugPrintf("exhibition: custom Match Settings row=%u value=%u\n", focus,
              value);
}

static uint32_t pes_exhibition_is_test_match(void) {
  if (__atomic_load_n(&exhibition_session_active, __ATOMIC_ACQUIRE) &&
      __atomic_load_n(&exhibition_settings_popup_open, __ATOMIC_ACQUIRE))
    return 1;
  return exhibition_is_test_match_original
             ? exhibition_is_test_match_original()
             : 0;
}

typedef struct {
  uint32_t team_id;
  const uint32_t *player_unique_ids;
  const uint8_t *shirt_numbers;
  uint32_t player_count;
} ExhibitionMasterRoster;

// PlayerAssignment.raw is the authoritative base-club membership table. The
// mobile build loads Team.raw and Player.raw, but its old myClub-only startup
// path leaves the Team records' runtime member arrays empty. Every PlayerId is
// resolved back through CommonWork so matches use the game's real master
// player records and abilities. The expanded clubs below were admitted only
// after their complete PlayerAssignment membership was validated against
// Player.raw.
static const uint32_t exhibition_barcelona_players[] = {
    61672u,  108662u, 104418u, 126426u, 121314u, 38568u,
    138298u, 121985u, 126673u, 42316u,  7511u,   43202u,
    116578u, 45330u,  132153u, 40425u,  37422u,  114661u,
    133157u, 122908u, 110626u, 138300u, 60622u,  138292u,
    8639u,   132535u, 132544u, 42892u,  42641u,  133215u,
};
static const uint8_t exhibition_barcelona_shirts[] = {
    0, 20, 14, 27, 23, 4, 26, 11, 16, 6, 9, 12, 25, 22, 1,
    17, 7, 18, 15, 29, 10, 28, 8, 35, 2, 31, 3, 19, 13, 21,
};
static const uint32_t exhibition_madrid_players[] = {
    44383u,  43076u,  42874u,  57353u,  107889u, 42669u,
    34098u,  36770u,  103420u, 117047u, 8944u,   123124u,
    131379u, 7329u,   140837u, 112940u, 34908u,  113911u,
    42556u,  103408u, 140573u, 36998u,  111343u, 138545u,
    141001u, 113525u, 141417u, 142849u, 118977u, 131387u,
    141615u, 118968u,
};
static const uint8_t exhibition_madrid_shirts[] = {
    0, 4, 5, 1, 22, 13, 9, 7, 10, 19, 8, 12, 25, 3, 31, 18,
    11, 14, 21, 16, 29, 6, 23, 32, 41, 2, 39, 30, 24, 27, 42, 26,
};

#include "exhibition_rosters.inc"
#include "exhibition_migration.inc"
#include "exhibition_rosters_ef10.inc"

#define EXHIBITION_ARRAY_COUNT(array) (sizeof(array) / sizeof((array)[0]))
#define EXHIBITION_ASSERT_ROSTER(name)                                      \
  _Static_assert(EXHIBITION_ARRAY_COUNT(exhibition_##name##_players) ==     \
                     EXHIBITION_ARRAY_COUNT(exhibition_##name##_shirts),    \
                 "Exhibition roster and shirt counts must match")
EXHIBITION_ASSERT_ROSTER(manchester_united);
EXHIBITION_ASSERT_ROSTER(arsenal);
EXHIBITION_ASSERT_ROSTER(chelsea);
EXHIBITION_ASSERT_ROSTER(liverpool);
EXHIBITION_ASSERT_ROSTER(leeds);
EXHIBITION_ASSERT_ROSTER(west_ham);
EXHIBITION_ASSERT_ROSTER(newcastle);
EXHIBITION_ASSERT_ROSTER(aston);
EXHIBITION_ASSERT_ROSTER(barcelona);
EXHIBITION_ASSERT_ROSTER(madrid);
EXHIBITION_ASSERT_ROSTER(valencia);
EXHIBITION_ASSERT_ROSTER(psg);
EXHIBITION_ASSERT_ROSTER(ajax);
EXHIBITION_ASSERT_ROSTER(psv);
EXHIBITION_ASSERT_ROSTER(inter);
EXHIBITION_ASSERT_ROSTER(juventus);
EXHIBITION_ASSERT_ROSTER(milan);
EXHIBITION_ASSERT_ROSTER(lazio);
EXHIBITION_ASSERT_ROSTER(roma);
EXHIBITION_ASSERT_ROSTER(bayern);
EXHIBITION_ASSERT_ROSTER(river);
EXHIBITION_ASSERT_ROSTER(boca);
EXHIBITION_ASSERT_ROSTER(la_coruna);
EXHIBITION_ASSERT_ROSTER(monaco);
EXHIBITION_ASSERT_ROSTER(marseille);
EXHIBITION_ASSERT_ROSTER(bordeaux);
EXHIBITION_ASSERT_ROSTER(feyenoord);
EXHIBITION_ASSERT_ROSTER(parma);
EXHIBITION_ASSERT_ROSTER(fiorentina);
EXHIBITION_ASSERT_ROSTER(leverkusen);
EXHIBITION_ASSERT_ROSTER(galatasaray);
EXHIBITION_ASSERT_ROSTER(celtic);
EXHIBITION_ASSERT_ROSTER(rangers);
EXHIBITION_ASSERT_ROSTER(olympiakos);
EXHIBITION_ASSERT_ROSTER(dynamo_kyiv);
EXHIBITION_ASSERT_ROSTER(spartak);
EXHIBITION_ASSERT_ROSTER(vasco);
EXHIBITION_ASSERT_ROSTER(barra_funda);
EXHIBITION_ASSERT_ROSTER(manchester_b);
EXHIBITION_ASSERT_ROSTER(everton_b);
EXHIBITION_ASSERT_ROSTER(tottenham_wb);
EXHIBITION_ASSERT_ROSTER(benfica);
EXHIBITION_ASSERT_ROSTER(porto);
EXHIBITION_ASSERT_ROSTER(sporting_cp);
EXHIBITION_ASSERT_ROSTER(atalanta);
EXHIBITION_ASSERT_ROSTER(napoli);
EXHIBITION_ASSERT_ROSTER(torino);
EXHIBITION_ASSERT_ROSTER(brighton_wb);
#define EXHIBITION_NATION(name, team_id, display_name) \
  EXHIBITION_ASSERT_ROSTER(name);
#include "exhibition_nations.inc"
#undef EXHIBITION_NATION
#undef EXHIBITION_ASSERT_ROSTER
#undef EXHIBITION_ARRAY_COUNT

static const ExhibitionMasterRoster exhibition_master_rosters[] = {
    {
        100,
        exhibition_manchester_united_players,
        exhibition_manchester_united_shirts,
        sizeof(exhibition_manchester_united_players) /
            sizeof(exhibition_manchester_united_players[0]),
    },
    {
        101,
        exhibition_arsenal_players,
        exhibition_arsenal_shirts,
        sizeof(exhibition_arsenal_players) /
            sizeof(exhibition_arsenal_players[0]),
    },
    {
        102,
        exhibition_chelsea_players,
        exhibition_chelsea_shirts,
        sizeof(exhibition_chelsea_players) /
            sizeof(exhibition_chelsea_players[0]),
    },
    {
        103,
        exhibition_liverpool_players,
        exhibition_liverpool_shirts,
        sizeof(exhibition_liverpool_players) /
            sizeof(exhibition_liverpool_players[0]),
    },
    {
        104,
        exhibition_leeds_players,
        exhibition_leeds_shirts,
        sizeof(exhibition_leeds_players) /
            sizeof(exhibition_leeds_players[0]),
    },
    {
        105,
        exhibition_west_ham_players,
        exhibition_west_ham_shirts,
        sizeof(exhibition_west_ham_players) /
            sizeof(exhibition_west_ham_players[0]),
    },
    {
        106,
        exhibition_newcastle_players,
        exhibition_newcastle_shirts,
        sizeof(exhibition_newcastle_players) /
            sizeof(exhibition_newcastle_players[0]),
    },
    {
        107,
        exhibition_aston_players,
        exhibition_aston_shirts,
        sizeof(exhibition_aston_players) /
            sizeof(exhibition_aston_players[0]),
    },
    {
        108,
        exhibition_barcelona_players,
        exhibition_barcelona_shirts,
        sizeof(exhibition_barcelona_players) /
            sizeof(exhibition_barcelona_players[0]),
    },
    {
        109,
        exhibition_madrid_players,
        exhibition_madrid_shirts,
        sizeof(exhibition_madrid_players) /
            sizeof(exhibition_madrid_players[0]),
    },
    {
        110,
        exhibition_valencia_players,
        exhibition_valencia_shirts,
        sizeof(exhibition_valencia_players) /
            sizeof(exhibition_valencia_players[0]),
    },
    {
        114,
        exhibition_psg_players,
        exhibition_psg_shirts,
        sizeof(exhibition_psg_players) / sizeof(exhibition_psg_players[0]),
    },
    {
        116,
        exhibition_ajax_players,
        exhibition_ajax_shirts,
        sizeof(exhibition_ajax_players) / sizeof(exhibition_ajax_players[0]),
    },
    {
        118,
        exhibition_psv_players,
        exhibition_psv_shirts,
        sizeof(exhibition_psv_players) / sizeof(exhibition_psv_players[0]),
    },
    {
        119,
        exhibition_inter_players,
        exhibition_inter_shirts,
        sizeof(exhibition_inter_players) / sizeof(exhibition_inter_players[0]),
    },
    {
        120,
        exhibition_juventus_players,
        exhibition_juventus_shirts,
        sizeof(exhibition_juventus_players) /
            sizeof(exhibition_juventus_players[0]),
    },
    {
        121,
        exhibition_milan_players,
        exhibition_milan_shirts,
        sizeof(exhibition_milan_players) / sizeof(exhibition_milan_players[0]),
    },
    {
        122,
        exhibition_lazio_players,
        exhibition_lazio_shirts,
        sizeof(exhibition_lazio_players) / sizeof(exhibition_lazio_players[0]),
    },
    {
        125,
        exhibition_roma_players,
        exhibition_roma_shirts,
        sizeof(exhibition_roma_players) / sizeof(exhibition_roma_players[0]),
    },
    {
        127,
        exhibition_bayern_players,
        exhibition_bayern_shirts,
        sizeof(exhibition_bayern_players) /
            sizeof(exhibition_bayern_players[0]),
    },
    {
        138,
        exhibition_river_players,
        exhibition_river_shirts,
        sizeof(exhibition_river_players) / sizeof(exhibition_river_players[0]),
    },
    {
        139,
        exhibition_boca_players,
        exhibition_boca_shirts,
        sizeof(exhibition_boca_players) / sizeof(exhibition_boca_players[0]),
    },
    {
        111,
        exhibition_la_coruna_players,
        exhibition_la_coruna_shirts,
        sizeof(exhibition_la_coruna_players) /
            sizeof(exhibition_la_coruna_players[0]),
    },
    {
        112,
        exhibition_monaco_players,
        exhibition_monaco_shirts,
        sizeof(exhibition_monaco_players) /
            sizeof(exhibition_monaco_players[0]),
    },
    {
        113,
        exhibition_marseille_players,
        exhibition_marseille_shirts,
        sizeof(exhibition_marseille_players) /
            sizeof(exhibition_marseille_players[0]),
    },
    {
        115,
        exhibition_bordeaux_players,
        exhibition_bordeaux_shirts,
        sizeof(exhibition_bordeaux_players) /
            sizeof(exhibition_bordeaux_players[0]),
    },
    {
        117,
        exhibition_feyenoord_players,
        exhibition_feyenoord_shirts,
        sizeof(exhibition_feyenoord_players) /
            sizeof(exhibition_feyenoord_players[0]),
    },
    {
        123,
        exhibition_parma_players,
        exhibition_parma_shirts,
        sizeof(exhibition_parma_players) /
            sizeof(exhibition_parma_players[0]),
    },
    {
        124,
        exhibition_fiorentina_players,
        exhibition_fiorentina_shirts,
        sizeof(exhibition_fiorentina_players) /
            sizeof(exhibition_fiorentina_players[0]),
    },
    {
        128,
        exhibition_leverkusen_players,
        exhibition_leverkusen_shirts,
        sizeof(exhibition_leverkusen_players) /
            sizeof(exhibition_leverkusen_players[0]),
    },
    {
        130,
        exhibition_galatasaray_players,
        exhibition_galatasaray_shirts,
        sizeof(exhibition_galatasaray_players) /
            sizeof(exhibition_galatasaray_players[0]),
    },
    {
        131,
        exhibition_celtic_players,
        exhibition_celtic_shirts,
        sizeof(exhibition_celtic_players) /
            sizeof(exhibition_celtic_players[0]),
    },
    {
        132,
        exhibition_rangers_players,
        exhibition_rangers_shirts,
        sizeof(exhibition_rangers_players) /
            sizeof(exhibition_rangers_players[0]),
    },
    {
        133,
        exhibition_olympiakos_players,
        exhibition_olympiakos_shirts,
        sizeof(exhibition_olympiakos_players) /
            sizeof(exhibition_olympiakos_players[0]),
    },
    {
        134,
        exhibition_dynamo_kyiv_players,
        exhibition_dynamo_kyiv_shirts,
        sizeof(exhibition_dynamo_kyiv_players) /
            sizeof(exhibition_dynamo_kyiv_players[0]),
    },
    {
        135,
        exhibition_spartak_players,
        exhibition_spartak_shirts,
        sizeof(exhibition_spartak_players) /
            sizeof(exhibition_spartak_players[0]),
    },
    {
        136,
        exhibition_vasco_players,
        exhibition_vasco_shirts,
        sizeof(exhibition_vasco_players) /
            sizeof(exhibition_vasco_players[0]),
    },
    {
        137,
        exhibition_barra_funda_players,
        exhibition_barra_funda_shirts,
        sizeof(exhibition_barra_funda_players) /
            sizeof(exhibition_barra_funda_players[0]),
    },
    {
        173,
        exhibition_manchester_b_players,
        exhibition_manchester_b_shirts,
        sizeof(exhibition_manchester_b_players) /
            sizeof(exhibition_manchester_b_players[0]),
    },
    {
        177,
        exhibition_everton_b_players,
        exhibition_everton_b_shirts,
        sizeof(exhibition_everton_b_players) /
            sizeof(exhibition_everton_b_players[0]),
    },
    {
        179,
        exhibition_tottenham_wb_players,
        exhibition_tottenham_wb_shirts,
        sizeof(exhibition_tottenham_wb_players) /
            sizeof(exhibition_tottenham_wb_players[0]),
    },
    {
        191,
        exhibition_benfica_players,
        exhibition_benfica_shirts,
        sizeof(exhibition_benfica_players) /
            sizeof(exhibition_benfica_players[0]),
    },
    {
        192,
        exhibition_porto_players,
        exhibition_porto_shirts,
        sizeof(exhibition_porto_players) /
            sizeof(exhibition_porto_players[0]),
    },
    {
        193,
        exhibition_sporting_cp_players,
        exhibition_sporting_cp_shirts,
        sizeof(exhibition_sporting_cp_players) /
            sizeof(exhibition_sporting_cp_players[0]),
    },
    {
        234,
        exhibition_atalanta_players,
        exhibition_atalanta_shirts,
        sizeof(exhibition_atalanta_players) /
            sizeof(exhibition_atalanta_players[0]),
    },
    {
        327,
        exhibition_napoli_players,
        exhibition_napoli_shirts,
        sizeof(exhibition_napoli_players) /
            sizeof(exhibition_napoli_players[0]),
    },
    {
        333,
        exhibition_torino_players,
        exhibition_torino_shirts,
        sizeof(exhibition_torino_players) /
            sizeof(exhibition_torino_players[0]),
    },
    {
        377,
        exhibition_brighton_wb_players,
        exhibition_brighton_wb_shirts,
        sizeof(exhibition_brighton_wb_players) /
            sizeof(exhibition_brighton_wb_players[0]),
    },
#define EXHIBITION_NATION(name, team_id, display_name)                    \
  {                                                                      \
      team_id, exhibition_##name##_players, exhibition_##name##_shirts, \
      sizeof(exhibition_##name##_players) /                              \
          sizeof(exhibition_##name##_players[0]),                        \
  },
#include "exhibition_nations.inc"
#undef EXHIBITION_NATION
};

static const ExhibitionMasterRoster *exhibition_find_roster(
    uint32_t team_id) {
  // Prefer the generated eFootball 10 compatibility roster. These entries
  // contain only IDs that the PES21 CommonWork database can resolve, so this
  // changes no player objects and adds no per-frame work.
  for (uint32_t i = 0;
       i < sizeof(exhibition_ef10_master_rosters) /
               sizeof(exhibition_ef10_master_rosters[0]);
       i++) {
    if (exhibition_ef10_master_rosters[i].team_id == team_id)
      return &exhibition_ef10_master_rosters[i];
  }
  for (uint32_t i = 0;
       i < sizeof(exhibition_master_rosters) /
               sizeof(exhibition_master_rosters[0]);
       i++) {
    if (exhibition_master_rosters[i].team_id == team_id)
      return &exhibition_master_rosters[i];
  }
  return NULL;
}

static int exhibition_is_valid_team(uint32_t team_id) {
  const ExhibitionMasterRoster *roster = exhibition_find_roster(team_id);
  // A selector entry without a full starting squad can never reach kickoff.
  return roster && roster->player_count >= 11u;
}

static int exhibition_matchup_ready(void) {
  return exhibition_is_valid_team(
             __atomic_load_n(&exhibition_home_team_id, __ATOMIC_ACQUIRE)) &&
         exhibition_is_valid_team(
             __atomic_load_n(&exhibition_away_team_id, __ATOMIC_ACQUIRE));
}

static uint32_t exhibition_picker_seed_team(uint32_t team_id) {
  return exhibition_is_valid_team(team_id)
             ? team_id
             : exhibition_master_rosters[0].team_id;
}

static uint32_t exhibition_first_other_team(uint32_t team_id) {
  for (uint32_t i = 0;
       i < sizeof(exhibition_master_rosters) /
               sizeof(exhibition_master_rosters[0]);
       i++) {
    if (exhibition_master_rosters[i].team_id != team_id)
      return exhibition_master_rosters[i].team_id;
  }
  return team_id;
}

static void exhibition_refresh_uniforms(void *tmpdb_match,
                                         const uint32_t *home_team_id,
                                         const uint32_t *away_team_id) {
  if (!home_team_id || !away_team_id || !exhibition_check_uniform)
    return;
  exhibition_check_uniform(home_team_id, away_team_id, 0);
  const uint32_t home_uniform =
      tmpdb_match && exhibition_match_get_uni_id
          ? exhibition_match_get_uni_id(tmpdb_match, 0)
          : UINT32_MAX;
  const uint32_t away_uniform =
      tmpdb_match && exhibition_match_get_uni_id
          ? exhibition_match_get_uni_id(tmpdb_match, 1)
          : UINT32_MAX;
  debugPrintf("exhibition: refreshed uniforms HOME=%u COM=%u\n",
              home_uniform, away_uniform);
}

static void exhibition_gameplan_refresh_uniform_choices(void) {
  memset(exhibition_uniform_choices, 0,
         sizeof(exhibition_uniform_choices));
  memset(exhibition_uniform_choice_count, 0,
         sizeof(exhibition_uniform_choice_count));
  memset(exhibition_uniform_choice_index, 0,
         sizeof(exhibition_uniform_choice_index));

  void *match = exhibition_get_tmpdb_match();
  if (!match || !exhibition_match_get_uni_id)
    return;

  const uint32_t selected_team[2] = {
      __atomic_load_n(&exhibition_home_team_id, __ATOMIC_ACQUIRE),
      __atomic_load_n(&exhibition_away_team_id, __ATOMIC_ACQUIRE),
  };
  for (uint32_t side = 0; side < 2; side++) {
    const uint32_t current = exhibition_match_get_uni_id(match, side);
    uint32_t count = 0;
    if (current != UINT32_MAX && (current >> 14) == selected_team[side])
      exhibition_uniform_choices[side][count++] = current;

    if (exhibition_match_get_extra_uniform_list) {
      for (uint32_t list_index = 0; list_index < 6; list_index++) {
        const uint32_t *entry = exhibition_match_get_extra_uniform_list(
            match, &side, &list_index);
        const uint32_t candidate = entry ? *entry : UINT32_MAX;
        if (candidate == UINT32_MAX ||
            (candidate >> 14) != selected_team[side])
          continue;
        uint32_t duplicate = 0;
        for (uint32_t index = 0; index < count; index++) {
          if (exhibition_uniform_choices[side][index] == candidate) {
            duplicate = 1;
            break;
          }
        }
        if (!duplicate && count < EXHIBITION_UNIFORM_CHOICE_MAX)
          exhibition_uniform_choices[side][count++] = candidate;
      }
    }
    exhibition_uniform_choice_count[side] = count;
    debugPrintf("exhibition: custom Game Plan kits side=%u count=%u "
                "selected=%u\n",
                side, count, current);
  }
}

static void exhibition_gameplan_change_uniform(uint32_t side,
                                                int direction) {
  if (side > 1 || !direction || !exhibition_match_set_uni_id)
    return;
  const uint32_t count = exhibition_uniform_choice_count[side];
  if (count < 2)
    return;
  uint32_t index = exhibition_uniform_choice_index[side];
  index = direction > 0 ? (index + 1) % count
                        : (index ? index - 1 : count - 1);
  exhibition_uniform_choice_index[side] = index;
  void *match = exhibition_get_tmpdb_match();
  if (match) {
    const uint32_t uniform_id = exhibition_uniform_choices[side][index];
    exhibition_match_set_uni_id(match, side, uniform_id);
    debugPrintf("exhibition: custom Game Plan kit side=%u choice=%u/%u "
                "uniform=%u\n",
                side, index + 1, count, uniform_id);
  }
}

static const char *exhibition_team_name(uint32_t team_id) {
#define EXHIBITION_NATION(name, nation_team_id, display_name) \
  if (team_id == nation_team_id)                              \
    return display_name;
#include "exhibition_nations.inc"
#undef EXHIBITION_NATION
  if (team_id == 100)
    return "MANCHESTER UNITED";
  if (team_id == 101)
    return "ARSENAL";
  if (team_id == 102)
    return "CHELSEA B";
  if (team_id == 103)
    return "LIVERPOOL R";
  if (team_id == 104)
    return "LEEDS W";
  if (team_id == 105)
    return "WEST HAM RB";
  if (team_id == 106)
    return "NEWCASTLE WB";
  if (team_id == 107)
    return "ASTON RB";
  if (team_id == 108)
    return "FC BARCELONA";
  if (team_id == 109)
    return "MADRID CHAMARTIN B";
  if (team_id == 110)
    return "VALENCIA BN";
  if (team_id == 114)
    return "PSG";
  if (team_id == 116)
    return "AJAX";
  if (team_id == 118)
    return "PSV";
  if (team_id == 119)
    return "LOMBARDIA NA";
  if (team_id == 120)
    return "JUVENTUS";
  if (team_id == 121)
    return "MILANO RN";
  if (team_id == 122)
    return "LAZIO";
  if (team_id == 125)
    return "ROMA";
  if (team_id == 127)
    return "FC BAYERN MUNCHEN";
  if (team_id == 138)
    return "RIVER PLATE";
  if (team_id == 139)
    return "BOCA JUNIORS";
  if (team_id == 111)
    return "LA CORUNA AB";
  if (team_id == 112)
    return "MONACO";
  if (team_id == 113)
    return "OLYMPIQUE MARSEILLE";
  if (team_id == 115)
    return "BORDEAUX";
  if (team_id == 117)
    return "FEYENOORD";
  if (team_id == 123)
    return "PARMA";
  if (team_id == 124)
    return "FIORENTINA";
  if (team_id == 128)
    return "BAYER LEVERKUSEN";
  if (team_id == 130)
    return "GALATASARAY";
  if (team_id == 131)
    return "CELTIC";
  if (team_id == 132)
    return "RANGERS";
  if (team_id == 133)
    return "OLYMPIAKOS PIRAEUS";
  if (team_id == 134)
    return "DYNAMO KYIV";
  if (team_id == 135)
    return "SPARTAK MOSKVA";
  if (team_id == 136)
    return "VASCO DA GAMA";
  if (team_id == 137)
    return "BARRA FUNDA V";
  if (team_id == 173)
    return "MANCHESTER B";
  if (team_id == 177)
    return "EVERTON B";
  if (team_id == 179)
    return "TOTTENHAM WB";
  if (team_id == 191)
    return "BENFICA";
  if (team_id == 192)
    return "PORTO";
  if (team_id == 193)
    return "SPORTING CP";
  if (team_id == 234)
    return "ATALANTA";
  if (team_id == 327)
    return "NAPOLI";
  if (team_id == 333)
    return "TORINO";
  if (team_id == 377)
    return "BRIGHTON WB";
  return "";
}

static void exhibition_select_team(uint32_t side, uint32_t team_id) {
  if (side >= 2 || !exhibition_is_valid_team(team_id))
    return;

  const uint32_t old_home =
      __atomic_load_n(&exhibition_home_team_id, __ATOMIC_ACQUIRE);
  const uint32_t old_away =
      __atomic_load_n(&exhibition_away_team_id, __ATOMIC_ACQUIRE);
  uint32_t home = old_home;
  uint32_t away = old_away;
  if (side == 0) {
    home = team_id;
    if (home == away && exhibition_is_valid_team(away))
      away = old_home != team_id ? old_home
                                 : exhibition_first_other_team(team_id);
  } else {
    away = team_id;
    if (away == home && exhibition_is_valid_team(home))
      home = old_away != team_id ? old_away
                                 : exhibition_first_other_team(team_id);
  }
  __atomic_store_n(&exhibition_home_team_id, home, __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_away_team_id, away, __ATOMIC_RELEASE);
  debugPrintf("exhibition: selection side=%u requested=%u HOME=%u COM=%u\n",
              side, team_id, home, away);
}

uintptr_t pes_exhibition_string_get_target(uint32_t string_id) {
  // Main-menu Match choice zero uses this title ID for "eFootball". Return a
  // wrapper-owned literal. The Exhibition hub reuses the stock footer slot
  // for match settings, while Proceed opens the normal Strategy editor.
  static const char exhibition_label[] __attribute__((aligned(2))) =
      "Exhibition";
  static const char training_label[] __attribute__((aligned(2))) =
      "Training";
  static const char training_description[] __attribute__((aligned(2))) =
      "Practice matches and controls";
  static const char settings_label[] __attribute__((aligned(2))) =
      "Settings";
  static const char change_team_label[] __attribute__((aligned(2))) =
      "Tap to Change Team";
  static const char proceed_label[] __attribute__((aligned(2))) = "Proceed";
  static const char play_label[] __attribute__((aligned(2))) = "Play";
  if (string_id == 0x0460005d)
    return (uintptr_t)exhibition_label | 1u;
  if (string_id == 0x0460005e)
    return (uintptr_t)training_label | 1u;
  if (string_id == 0x045d01d4)
    return (uintptr_t)training_description | 1u;
  if (string_id == 0x01f9003d &&
      __atomic_load_n(&exhibition_session_active, __ATOMIC_ACQUIRE))
    return (uintptr_t)settings_label | 1u;
  if (string_id == 0x045e0023 &&
      __atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE))
    return (uintptr_t)change_team_label | 1u;
  if (string_id == 0x7fff0001 &&
      __atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE))
    return (uintptr_t)proceed_label | 1u;
  if (string_id == 0x7fff0002 &&
      __atomic_load_n(&exhibition_session_active, __ATOMIC_ACQUIRE) &&
      __atomic_load_n(&exhibition_strategy_action, __ATOMIC_ACQUIRE) ==
          EXHIBITION_STRATEGY_START)
    return (uintptr_t)play_label | 1u;
  return exhibition_string_get_resume;
}

static uint32_t exhibition_install_master_roster(
    void *common_work, const uint32_t *team_id,
    const ExhibitionMasterRoster *roster) {
  if (!common_work || !team_id || !roster ||
      !exhibition_commonwork_update_team ||
      !exhibition_commonwork_update_player ||
      !exhibition_get_player_id_by_unique_id)
    return 0;

  // SetExhibitionTeam imports from CommonWork::UpdateTeam, not the immutable
  // pesdb view returned by GetTeam. Patch that exact runtime Team object.
  unsigned char *team =
      exhibition_commonwork_update_team(common_work, team_id);
  uint32_t actual_team_id = 0;
  if (team)
    memcpy(&actual_team_id, team, sizeof(actual_team_id));
  if (!team || actual_team_id != *team_id) {
    debugPrintf("exhibition: master team lookup failed requested=0x%x "
                "actual=0x%x ptr=%p\n",
                *team_id, actual_team_id, team);
    return 0;
  }

  uint64_t *member_ids = (uint64_t *)(team + 272);
  uint8_t *appointment_order = team + 0x218;
  uint16_t *shirt_numbers = (uint16_t *)(team + 604);
  memset(member_ids, 0, 40 * sizeof(*member_ids));
  memset(appointment_order, 0xff, 40);
  memset(shirt_numbers, 0, 40 * sizeof(*shirt_numbers));

  uint32_t valid = 0;
  uint32_t missing = 0;
  for (uint32_t i = 0; i < roster->player_count && valid < 40; i++) {
    const uint32_t unique_id = roster->player_unique_ids[i];
    const uint64_t player_id =
        exhibition_get_player_id_by_unique_id(&unique_id);
    if ((uint32_t)(player_id >> 32) != unique_id ||
        !exhibition_commonwork_update_player(common_work, player_id)) {
      missing++;
      continue;
    }
    member_ids[valid] = player_id;
    shirt_numbers[valid] = roster->shirt_numbers[i];
    appointment_order[valid] = (uint8_t)valid;
    valid++;
  }

  uint32_t member_flags;
  memcpy(&member_flags, team + 0x3a6, sizeof(member_flags));
  member_flags &= ~(0x7fu << 9);
  member_flags |= (valid & 0x7fu) << 9;
  memcpy(team + 0x3a6, &member_flags, sizeof(member_flags));
  debugPrintf("exhibition: master roster team=0x%x valid=%u missing=%u "
              "flags=0x%x\n",
              *team_id, valid, missing, member_flags);
  return valid;
}

static uint32_t exhibition_refresh_squad_side_player_stats(
    unsigned char *squad_edit, void *common_work, uint32_t side) {
  const uint32_t raw_team = __atomic_load_n(
      side ? &exhibition_away_team_id : &exhibition_home_team_id,
      __ATOMIC_ACQUIRE);
  const ExhibitionMasterRoster *roster = exhibition_find_roster(raw_team);
  void *squad_data = exhibition_squad_edit_get_squad_data(squad_edit, side);
  if (!roster || !squad_data)
    return 0;

  uint32_t squad_count = exhibition_squad_data_get_player_count(squad_data);
  if (squad_count > 40)
    squad_count = 40;

  uint32_t updated = 0;
  uint32_t roster_index = 0;
  while (updated < squad_count && roster_index < roster->player_count) {
    const uint32_t unique_id =
        roster->player_unique_ids[roster_index++];
    const uint64_t player_id =
        exhibition_get_player_id_by_unique_id(&unique_id);
    unsigned char *player =
        exhibition_commonwork_update_player(common_work, player_id);
    uint64_t actual_player_id = 0;
    if (player)
      memcpy(&actual_player_id, player + 44, sizeof(actual_player_id));
    if (!player || actual_player_id != player_id)
      continue;

    void *squad_player = exhibition_squad_data_get_player_by_index(
        squad_data, &updated);
    if (!squad_player)
      break;

    // SquadPlayer stores its lookup key first, followed by normal and boosted
    // tmpdb::Player copies. Refresh both copies from the authentic master row.
    exhibition_squad_edit_update_player(squad_edit, squad_player, player, 0);
    exhibition_squad_edit_update_player(squad_edit, squad_player, player, 1);

#ifdef DEBUG_LOG
    if (exhibition_get_player_overall && updated < 4) {
      const uint32_t natural_position = 13;
      const uint32_t overall = exhibition_get_player_overall(
          player, &natural_position, 2);
      debugPrintf("exhibition: squad stats side=%u slot=%u unique=%u "
                  "player=0x%llx overall=%u\n",
                  side, updated, unique_id,
                  (unsigned long long)player_id, overall);
    }
#endif
    updated++;
  }

  debugPrintf("exhibition: refreshed squad stats side=%u team=%u "
              "players=%u/%u\n",
              side, raw_team, updated, squad_count);
  return updated;
}

static uint32_t exhibition_refresh_squad_player_stats(void) {
  if (!exhibition_tmpdb_manager_get_instance ||
      !exhibition_commonwork_update_player ||
      !exhibition_get_player_id_by_unique_id ||
      !exhibition_squad_edit_get_squad_data ||
      !exhibition_squad_data_get_player_count ||
      !exhibition_squad_data_get_player_by_index ||
      !exhibition_squad_edit_update_player)
    return 0;

  void *manager = exhibition_tmpdb_manager_get_instance();
  void *common_work = NULL;
  void *tmpdb_data = NULL;
  if (manager) {
    memcpy(&common_work, (unsigned char *)manager + 64,
           sizeof(common_work));
    memcpy(&tmpdb_data, (unsigned char *)manager + 72,
           sizeof(tmpdb_data));
  }
  if (!common_work || !tmpdb_data)
    return 0;

  unsigned char *squad_edit = (unsigned char *)tmpdb_data + 0x18360;
  uint32_t previous_side = 0;
  memcpy(&previous_side, squad_edit + 5312, sizeof(previous_side));

  uint32_t updated = 0;
  for (uint32_t side = 0; side < 2; side++) {
    // UpdateMemberTmpdbPlayer targets the side stored in SquadEdit, so switch
    // it briefly while refreshing both the home and away squad copies.
    memcpy(squad_edit + 5312, &side, sizeof(side));
    updated += exhibition_refresh_squad_side_player_stats(
        squad_edit, common_work, side);
  }

  memcpy(squad_edit + 5312, &previous_side, sizeof(previous_side));
  return updated;
}

static int exhibition_refresh_selected_tmpdb(void) {
  uint32_t home_raw =
      __atomic_load_n(&exhibition_home_team_id, __ATOMIC_ACQUIRE);
  uint32_t away_raw =
      __atomic_load_n(&exhibition_away_team_id, __ATOMIC_ACQUIRE);
  const ExhibitionMasterRoster *home_roster = exhibition_find_roster(home_raw);
  const ExhibitionMasterRoster *away_roster = exhibition_find_roster(away_raw);
  if (!home_roster || !away_roster || !exhibition_set_team)
    return 0;

  const uint32_t home_team_id = home_raw << 14;
  const uint32_t away_team_id = away_raw << 14;
  void *manager = exhibition_tmpdb_manager_get_instance
                      ? exhibition_tmpdb_manager_get_instance()
                      : NULL;
  void *common_work = NULL;
  if (manager)
    memcpy(&common_work, (unsigned char *)manager + 64,
           sizeof(common_work));

  const uint32_t home_count = exhibition_install_master_roster(
      common_work, &home_team_id, home_roster);
  const uint32_t away_count = exhibition_install_master_roster(
      common_work, &away_team_id, away_roster);
  if (home_count < 11 || away_count < 11)
    return 0;

  exhibition_set_team(&home_team_id, 0, 0);
  exhibition_set_team(&away_team_id, 1, 0);

  unsigned char *tmpdb_match = NULL;
  if (manager) {
    void *tmpdb_data = NULL;
    memcpy(&tmpdb_data, (unsigned char *)manager + 72,
           sizeof(tmpdb_data));
    if (tmpdb_data)
      tmpdb_match = (unsigned char *)tmpdb_data + 0x4b38;
  }

  uint32_t local_user_id = 0;
  void *online_parameter = exhibition_online_parameter_get_instance
                               ? exhibition_online_parameter_get_instance()
                               : NULL;
  void *parameter_common = NULL;
  if (online_parameter)
    memcpy(&parameter_common, (unsigned char *)online_parameter + 8,
           sizeof(parameter_common));
  if (parameter_common && exhibition_parameter_common_get_user_id)
    local_user_id = exhibition_parameter_common_get_user_id(parameter_common);
  if (tmpdb_match && exhibition_tmpdb_match_set_user_id)
    exhibition_tmpdb_match_set_user_id(tmpdb_match, 0, local_user_id);

  exhibition_refresh_uniforms(tmpdb_match, &home_team_id, &away_team_id);

  debugPrintf("exhibition: refreshed matchup HOME=%u(%u) COM=%u(%u) "
              "match=%p user=%u\n",
              home_raw, home_count, away_raw, away_count, tmpdb_match,
              local_user_id);
  return 1;
}

static int exhibition_prepare_search_parameters(void) {
  if (!exhibition_parameter_get_instance ||
      !exhibition_parameter_myclub_create_work)
    return 0;
  void *parameter = exhibition_parameter_get_instance(1);
  void *myclub = NULL;
  if (parameter)
    memcpy(&myclub, (unsigned char *)parameter + 24, sizeof(myclub));
  if (!myclub)
    return 0;
  // The stock routine checks every pointer before creating it, so this is
  // safe both on first entry and when returning from Game Plan.
  exhibition_parameter_myclub_create_work(myclub);
  debugPrintf("exhibition: prepared local MyClub work parameter=%p myclub=%p\n",
              parameter, myclub);
  return 1;
}

// cobra::stl::basic_string uses a one-byte short-string tag or the usual
// [capacity, size, data] long representation. Menu flow names longer than 23
// bytes use the latter. Redirect only the stock eFootball/Divisions target;
// every other flow and all startup/network state remain untouched.
uintptr_t pes_exhibition_redirect_flow(void *flow_name_ptr) {
  static const char online_target[] = "MyClub/MainMenu/MenuOnlineMatchTop";
  static const char divisions_target[] = "MyClub/MainMenu/MenuDivisionsTop";
  static const char searching_target[] =
      "MyClub/Match/Training/MenuMatchSearching";
  static const char team_select_target[] =
      "MyClub/Match/Training/MenuMatchTeamSelect";
  static const char post_match_target[] = "MyClub/Match/PostMatchMenu";
  static const char intro_target[] = "Intro/MenuIntroKonamiLogo";
  static const char tutorial_replacement[] = "MyClub/TutorialMatch";
  unsigned char *object = flow_name_ptr;
  char *data = NULL;
  size_t length = 0;
  size_t allocation_size = 0;

  if (object) {
    if (object[0] & 1) {
      size_t encoded_capacity = 0;
      memcpy(&encoded_capacity, object, sizeof(encoded_capacity));
      allocation_size = encoded_capacity & ~(size_t)1;
      memcpy(&length, object + 8, sizeof(length));
      memcpy(&data, object + 16, sizeof(data));
    } else {
      length = object[0] >> 1;
      data = (char *)object + 1;
    }
  }

  if (data && length < 128 && exhibition_flow_log_count < 64) {
    exhibition_flow_log_count++;
    debugPrintf("exhibition: FactoryMobile flow=%.*s length=%u\n",
                (int)length, data, (unsigned int)length);
  }

  const char *matched_target = NULL;
  const char *replacement = NULL;
  if (data && (object[0] & 1)) {
    if (length == sizeof(online_target) - 1 &&
        memcmp(data, online_target, sizeof(online_target) - 1) == 0) {
      matched_target = online_target;
      replacement = tutorial_replacement;
    } else if (length == sizeof(divisions_target) - 1 &&
             memcmp(data, divisions_target,
                    sizeof(divisions_target) - 1) == 0) {
      matched_target = divisions_target;
      replacement = tutorial_replacement;
    } else if (__atomic_load_n(&exhibition_session_active,
                               __ATOMIC_ACQUIRE) &&
               __atomic_load_n(&exhibition_strategy_action,
                               __ATOMIC_ACQUIRE) ==
                   EXHIBITION_STRATEGY_EDIT &&
               ((length == sizeof(post_match_target) - 1 &&
                 memcmp(data, post_match_target,
                        sizeof(post_match_target) - 1) == 0) ||
                (length == sizeof(intro_target) - 1 &&
                 memcmp(data, intro_target,
                        sizeof(intro_target) - 1) == 0))) {
      // Strategy was opened from the Practice Match "Game Plan" footer.
      // Persist the edited plan, then make both Confirm and Back return to
      // the matchup hub instead of starting/leaving the Exhibition.
      void *plan = exhibition_matchplan_get_instance
                       ? exhibition_matchplan_get_instance()
                       : NULL;
      if (plan && exhibition_matchplan_update_tmpdb)
        exhibition_matchplan_update_tmpdb(plan);
      matched_target = length == sizeof(post_match_target) - 1
                           ? post_match_target
                           : intro_target;
      // FactoryMobile's source string only reserves enough storage for the
      // short PostMatch/Intro path. Use TutorialMatch as a short trampoline;
      // its entry hook immediately returns to the Exhibition Matchmaking hub
      // without rebuilding or resetting either selected team.
      replacement = tutorial_replacement;
      __atomic_store_n(&exhibition_plan_ready, 1, __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_return_to_selector, 1,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_strategy_action,
                       EXHIBITION_STRATEGY_NONE, __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_team_select_active, 0,
                       __ATOMIC_RELEASE);
    } else if (__atomic_load_n(&exhibition_session_active,
                               __ATOMIC_ACQUIRE) &&
               length == sizeof(searching_target) - 1 &&
               memcmp(data, searching_target,
                      sizeof(searching_target) - 1) == 0) {
      __atomic_store_n(&exhibition_searching_active, 1, __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_search_refresh_pending, 1,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_search_initial_refresh_ticks,
                       EXHIBITION_INITIAL_REFRESH_TICKS, __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_team_select_active, 1,
                       __ATOMIC_RELEASE);
      debugPrintf("exhibition: Matchmaking hub opened: %s\n",
                  searching_target);
    } else if (__atomic_load_n(&exhibition_session_active,
                               __ATOMIC_ACQUIRE) &&
               length == sizeof(team_select_target) - 1 &&
               memcmp(data, team_select_target,
                      sizeof(team_select_target) - 1) == 0) {
      __atomic_store_n(&exhibition_team_select_active, 1,
                       __ATOMIC_RELEASE);
    }
  }
  if (matched_target && replacement) {
    const size_t replacement_length = strlen(replacement);
    if (allocation_size < replacement_length + 1) {
      debugPrintf("exhibition: cannot redirect %s -> %s capacity=%u\n",
                  matched_target, replacement,
                  (unsigned int)allocation_size);
      return exhibition_flow_create_resume;
    }
    memcpy(data, replacement, replacement_length + 1);
    memcpy(object + 8, &replacement_length, sizeof(replacement_length));
    if (replacement == tutorial_replacement &&
        (matched_target == online_target || matched_target == divisions_target)) {
      __atomic_store_n(&exhibition_requested, 1, __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_session_active, 1, __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_searching_active, 0, __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_search_refresh_pending, 0,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_search_initial_refresh_ticks, 0,
                       __ATOMIC_RELEASE);
    }
    debugPrintf("exhibition: redirected %s -> %s\n", matched_target,
                replacement);
  }

  return exhibition_flow_create_resume;
}

// TutorialMatch is also visited by the normal startup flow. Leave that visit
// completely stock. A Divisions/eFootball redirect arms a one-shot request;
// only then change state 0 to the complete local-team initializer (state 3).
// Once the stock graphics/font wait has selected its normal post-tutorial
// route (state 7), enter the stock TrainingInit process. That process prepares
// ParameterMatchSpecialTeamData before it opens Training Team Select, whose
// window already has two club panels, touch/controller selection and a
// proceed button. State 9
// is outside TutorialMatch's 0..8 dispatcher, so the original Main returns
// without also emitting its stock proceed event while FlowTransition owns the
// fade. This keeps the master-data teams produced by state 3 and avoids the
// invalid myClub squad converter entirely.
uintptr_t pes_exhibition_tutorial_main_entry(void *tutorial_flow) {
  if (tutorial_flow &&
      __atomic_exchange_n(&exhibition_return_to_selector, 0,
                          __ATOMIC_ACQ_REL)) {
    uint32_t *state = (uint32_t *)((unsigned char *)tutorial_flow + 540);
    void *listener = exhibition_flow_listener_instance
                         ? *exhibition_flow_listener_instance
                         : NULL;
    if (listener && exhibition_flow_direct_set) {
      static const char searching_flow[] =
          "MyClub/Match/Training/MenuMatchSearching";
      exhibition_prepare_search_parameters();
      exhibition_flow_direct_set((unsigned char *)listener + 0x118,
                                 searching_flow);
      *state = 9;
      __atomic_store_n(&exhibition_requested, 0, __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_searching_active, 1,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_search_refresh_pending, 1,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_search_initial_refresh_ticks,
                       EXHIBITION_INITIAL_REFRESH_TICKS, __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_team_select_active, 1,
                       __ATOMIC_RELEASE);
      debugPrintf("exhibition: Game Plan closed; trampoline -> %s\n",
                  searching_flow);
      return exhibition_tutorial_main_resume;
    }
    // Retry next frame if the global listener has not been published yet.
    __atomic_store_n(&exhibition_return_to_selector, 1, __ATOMIC_RELEASE);
  }

  if (tutorial_flow &&
      __atomic_load_n(&exhibition_requested, __ATOMIC_ACQUIRE)) {
    uint32_t *state = (uint32_t *)((unsigned char *)tutorial_flow + 540);
    if (*state == 0) {
      *state = 3;
      debugPrintf("exhibition: TutorialMatch state 0 -> 3 (initialize)\n");
    } else if (*state == 7) {
      void *listener = exhibition_flow_listener_instance
                           ? *exhibition_flow_listener_instance
                           : NULL;
      if (listener && exhibition_flow_direct_set) {
        static const char searching_flow[] =
            "MyClub/Match/Training/MenuMatchSearching";
        static const char strategy_flow[] = "MyClub/Match/MenuMatchMenu";
        const int native_lab = pes_controller_native_pad_lab_active();
        if (!native_lab) {
          __atomic_store_n(&exhibition_home_team_id, 0, __ATOMIC_RELEASE);
          __atomic_store_n(&exhibition_away_team_id, 0, __ATOMIC_RELEASE);
        }
        __atomic_store_n(&exhibition_select_side, 0, __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_strategy_action,
                         EXHIBITION_STRATEGY_NONE, __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_plan_ready, 0, __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_return_to_selector, 0,
                         __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_searching_active, native_lab ? 0 : 1,
                         __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_search_refresh_pending, 1,
                         __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_search_initial_refresh_ticks,
                         EXHIBITION_INITIAL_REFRESH_TICKS, __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_team_select_active, native_lab ? 0 : 1,
                         __ATOMIC_RELEASE);
        if (exhibition_status_get_instance && exhibition_status_set_game_mode)
          exhibition_status_set_game_mode(exhibition_status_get_instance(),
                                          72);
        exhibition_prepare_search_parameters();
        exhibition_refresh_selected_tmpdb();
        exhibition_flow_direct_set((unsigned char *)listener + 0x118,
                                   native_lab ? strategy_flow : searching_flow);
        if (native_lab) {
          __atomic_store_n(&exhibition_strategy_action,
                           EXHIBITION_STRATEGY_START, __ATOMIC_RELEASE);
          __atomic_store_n(&exhibition_strategy_pending, 1,
                           __ATOMIC_RELEASE);
        }
        *state = 9;
        __atomic_store_n(&exhibition_requested, 0, __ATOMIC_RELEASE);
        debugPrintf("exhibition: TutorialMatch initialized master teams; "
                    "DirectSet -> %s nativeLab=%d\n",
                    native_lab ? strategy_flow : searching_flow, native_lab);
      } else {
        debugPrintf("exhibition: waiting for FlowListener instance=%p "
                    "DirectSet=%p\n",
                    listener, exhibition_flow_direct_set);
      }
    }
  }
  return exhibition_tutorial_main_resume;
}

// Adapt the stock Training Team Select window into the Exhibition matchup
// screen. The original window already owns the two touchable team panels and
// launches MyClubFlowTeamSelect. During an Exhibition session both rows use
// the same master-club picker; this wrapper keeps independent HOME/AWAY IDs.
uintptr_t pes_exhibition_training_touch_entry(void *window,
                                              const void *touch_info) {
  (void)window;
  if (touch_info &&
      __atomic_load_n(&exhibition_team_select_active, __ATOMIC_ACQUIRE)) {
    uint32_t side = UINT32_MAX;
    memcpy(&side, (const unsigned char *)touch_info + 8, sizeof(side));
    if (side < 2) {
      const uint32_t selected_team =
          side == 0
              ? __atomic_load_n(&exhibition_home_team_id, __ATOMIC_ACQUIRE)
              : __atomic_load_n(&exhibition_away_team_id, __ATOMIC_ACQUIRE);
      const uint32_t team_id = exhibition_picker_seed_team(selected_team);
      __atomic_store_n(&exhibition_select_side, side, __ATOMIC_RELEASE);
      if (exhibition_set_test_match_team_id)
        exhibition_set_test_match_team_id(team_id);
      debugPrintf("exhibition: team picker open side=%u current=%u seed=%u\n",
                  side, selected_team, team_id);
    }
  }
  return exhibition_training_touch_resume;
}

uintptr_t pes_exhibition_training_list_entry(void *window, void *page,
                                             const uint32_t *side_ptr) {
  (void)window;
  (void)page;
  if (side_ptr &&
      __atomic_load_n(&exhibition_team_select_active, __ATOMIC_ACQUIRE)) {
    const uint32_t side = *side_ptr;
    if (side < 2 && exhibition_set_test_match_team_id) {
      const uint32_t selected_team =
          side == 0
              ? __atomic_load_n(&exhibition_home_team_id, __ATOMIC_ACQUIRE)
              : __atomic_load_n(&exhibition_away_team_id, __ATOMIC_ACQUIRE);
      const uint32_t team_id = exhibition_picker_seed_team(selected_team);
      exhibition_set_test_match_team_id(team_id);
    }
  }
  return exhibition_training_list_resume;
}

uintptr_t pes_exhibition_training_child_entry(void *window,
                                              const void *child_name,
                                              uint32_t selected_team_id) {
  (void)window;
  (void)child_name;
  if (__atomic_load_n(&exhibition_team_select_active, __ATOMIC_ACQUIRE) &&
      exhibition_is_valid_team(selected_team_id)) {
    const uint32_t side =
        __atomic_load_n(&exhibition_select_side, __ATOMIC_ACQUIRE);
    exhibition_select_team(side, selected_team_id);
    __atomic_store_n(&exhibition_plan_ready, 0, __ATOMIC_RELEASE);
    debugPrintf("exhibition: selected side=%u team=%u\n", side,
                selected_team_id);
  }
  return exhibition_training_child_resume;
}

// Practice Match is the single Exhibition hub. The stock footer uses key 0
// for Next and key 3 for its HOME/AWAY dialog. Replace both transitions with
// scoped Strategy entries: key 3 shows the editor and returns here, while
// Next seeds the same match plan invisibly and continues to MatchSetup.
uintptr_t pes_exhibition_training_footer_entry(void *window,
                                               uint32_t footer_key) {
  (void)window;
  if (!__atomic_load_n(&exhibition_team_select_active,
                       __ATOMIC_ACQUIRE) ||
      (footer_key != 0 && footer_key != 3))
    return exhibition_training_footer_resume;

  void *listener = exhibition_flow_listener_instance
                       ? *exhibition_flow_listener_instance
                       : NULL;
  if (!listener || !exhibition_flow_direct_set)
    return exhibition_training_footer_resume;

  static const char strategy_flow[] = "MyClub/Match/MenuMatchMenu";
  const uint32_t action = footer_key == 3 ? EXHIBITION_STRATEGY_EDIT
                                          : EXHIBITION_STRATEGY_START;
  __atomic_store_n(&exhibition_strategy_action, action, __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_strategy_pending, 1, __ATOMIC_RELEASE);
  __atomic_store_n(&virtual_cursor_context, PES_VIRTUAL_CURSOR_NONE,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_team_select_active, 0, __ATOMIC_RELEASE);
  exhibition_flow_direct_set((unsigned char *)listener + 0x118,
                             strategy_flow);
  debugPrintf("exhibition: Practice Match footer key=%u -> Strategy action=%u\n",
              footer_key, action);
  return 0;
}

static const char *exhibition_cobra_string_data(const void *string_object,
                                                 size_t *length) {
  const unsigned char *object = string_object;
  if (!object || !length)
    return NULL;
  if (object[0] & 1) {
    const char *data = NULL;
    memcpy(length, object + 8, sizeof(*length));
    memcpy(&data, object + 16, sizeof(data));
    return *length < 128 ? data : NULL;
  }
  *length = object[0] >> 1;
  return (const char *)object + 1;
}

// MatchSearching renders two team cards but, unlike TrainingTeamSelect, does
// not register either card with UE's touch dispatcher. The Android shim
// publishes a completed tap here and this game-thread hook consumes it from
// pes_exhibition_search_post_entry(). Values are side+1 so zero remains the
// lock-free "no request" state.
void pes_exhibition_matchmaking_tap(float normalized_x, float normalized_y) {
  if (!__atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE) ||
      __atomic_load_n(&exhibition_team_picker_open, __ATOMIC_ACQUIRE) ||
      __atomic_load_n(&exhibition_cpu_level_popup_open, __ATOMIC_ACQUIRE) ||
      __atomic_load_n(&exhibition_settings_popup_open, __ATOMIC_ACQUIRE) ||
      normalized_y < 0.18f || normalized_y > 0.87f)
    return;

  uint32_t request = 0;
  if (normalized_x >= 0.06f && normalized_x <= 0.48f)
    request = 1;
  else if (normalized_x >= 0.52f && normalized_x <= 0.94f)
    request = 2;
  if (request)
    __atomic_store_n(&exhibition_search_touch_pending, request,
                     __ATOMIC_RELEASE);
}

static uint64_t exhibition_search_focus_now_ms(void) {
  return armTicksToNs(armGetSystemTick()) / 1000000ULL;
}

void pes_exhibition_search_footer(void *window, uint32_t footer_key);

static void exhibition_search_focus_apply(void *window) {
  if (!window || !exhibition_set_pad_key_active)
    return;
  const int footer_focus = exhibition_search_focus_index >= 2;
  const uint32_t focused_key =
      exhibition_search_focus_index == 2
          ? 1
          : exhibition_search_focus_index == 3
                ? 2
                : exhibition_search_focus_index == 4 ? 3 : 0;
  const int matchup_ready = exhibition_matchup_ready();
  for (uint32_t key = 0; key < 4; key++) {
    const int available = key != 0 || matchup_ready;
    const int active = footer_focus ? (available && key == focused_key)
                                    : available;
    exhibition_set_pad_key_active(window, key, active);
  }
}

void pes_exhibition_search_pad_event(uint32_t buttons,
                                     uint32_t previous_buttons) {
  if (!__atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE))
    return;

  uint32_t direction = 0;
  if (buttons & (1u << 10))
    direction = 1; // up
  else if (buttons & (1u << 11))
    direction = 2; // down
  else if (buttons & (1u << 12))
    direction = 3; // left
  else if (buttons & (1u << 13))
    direction = 4; // right

  const uint64_t now = exhibition_search_focus_now_ms();
  const int team_popup =
      __atomic_load_n(&exhibition_team_picker_open, __ATOMIC_ACQUIRE);
  const int cpu_popup =
      __atomic_load_n(&exhibition_cpu_level_popup_open, __ATOMIC_ACQUIRE);
  const int settings_popup =
      __atomic_load_n(&exhibition_settings_popup_open, __ATOMIC_ACQUIRE);
  const int nested_popup =
      __atomic_load_n(&exhibition_nested_popup_open, __ATOMIC_ACQUIRE);
  if (nested_popup) {
    if (!direction) {
      exhibition_popup_focus_direction = 0;
      return;
    }
    const int pressed = (buttons & (1u << (direction + 9))) != 0 &&
                        !(previous_buttons & (1u << (direction + 9)));
    if (direction != exhibition_popup_focus_direction) {
      exhibition_popup_focus_direction = direction;
      exhibition_popup_focus_started_ms = now;
      exhibition_popup_focus_repeat_ms = now;
    } else if (!pressed && now - exhibition_popup_focus_started_ms < 300) {
      return;
    } else if (!pressed && now - exhibition_popup_focus_repeat_ms < 120) {
      return;
    }
    exhibition_popup_focus_repeat_ms = now;
    const uint32_t nested_kind = __atomic_load_n(
        &exhibition_nested_popup_kind, __ATOMIC_ACQUIRE);
    const uint32_t max_index =
        nested_kind == EXHIBITION_NESTED_SHORT_LIST ? 1 : 5;
    if (direction == 1) {
      if (exhibition_popup_focus_index > 0)
        exhibition_popup_focus_index--;
      else if (nested_kind == EXHIBITION_NESTED_LONG_LIST)
        __atomic_store_n(&exhibition_popup_scroll_request, -1,
                         __ATOMIC_RELEASE);
    } else if (direction == 2) {
      if (exhibition_popup_focus_index < max_index)
        exhibition_popup_focus_index++;
      else if (nested_kind == EXHIBITION_NESTED_LONG_LIST)
        __atomic_store_n(&exhibition_popup_scroll_request, 1,
                         __ATOMIC_RELEASE);
    }
    return;
  }
  if (team_popup || cpu_popup || settings_popup) {
    if (!direction) {
      exhibition_popup_focus_direction = 0;
      return;
    }
    const int pressed = (buttons & (1u << (direction + 9))) != 0 &&
                        !(previous_buttons & (1u << (direction + 9)));
    if (direction != exhibition_popup_focus_direction) {
      exhibition_popup_focus_direction = direction;
      exhibition_popup_focus_started_ms = now;
      exhibition_popup_focus_repeat_ms = now;
    } else if (!pressed && now - exhibition_popup_focus_started_ms < 300) {
      return;
    } else if (!pressed && now - exhibition_popup_focus_repeat_ms < 120) {
      return;
    }
    exhibition_popup_focus_repeat_ms = now;
    if (team_popup &&
        __atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE)) {
      const uint32_t item_count = exhibition_custom_team_item_count();
      const uint32_t old_focus = exhibition_popup_focus_index;
      if (direction == 1) {
        if (exhibition_popup_focus_index >= 2)
          exhibition_popup_focus_index -= 2;
      } else if (direction == 2) {
        if (exhibition_popup_focus_index + 2 < item_count)
          exhibition_popup_focus_index += 2;
        else if ((exhibition_popup_focus_index & 1u) &&
                 exhibition_popup_focus_index + 1 < item_count)
          exhibition_popup_focus_index++;
      } else if (direction == 3) {
        if (exhibition_popup_focus_index & 1u)
          exhibition_popup_focus_index--;
      } else if (direction == 4) {
        if (!(exhibition_popup_focus_index & 1u) &&
            exhibition_popup_focus_index + 1 < item_count)
          exhibition_popup_focus_index++;
      }
      if (old_focus != exhibition_popup_focus_index)
        exhibition_team_scroll_offset =
            (exhibition_popup_focus_index / EXHIBITION_TEAM_GRID_PAGE_SIZE) *
            EXHIBITION_TEAM_GRID_PAGE_SIZE;
      return;
    }
    if (settings_popup) {
      if (direction == 1 && exhibition_popup_focus_index > 0)
        exhibition_popup_focus_index--;
      else if (direction == 2 && exhibition_popup_focus_index + 1 < PES_MATCH_SETTINGS_COUNT)
        exhibition_popup_focus_index++;
      else if (direction == 3)
        exhibition_adjust_match_setting(-1);
      else if (direction == 4)
        exhibition_adjust_match_setting(1);
      return;
    }
    if (cpu_popup) {
      if (direction == 1 && exhibition_popup_focus_index > 0)
        exhibition_popup_focus_index--;
      else if (direction == 2 &&
               exhibition_popup_focus_index + 1 <
                   EXHIBITION_CPU_LEVEL_COUNT)
        exhibition_popup_focus_index++;
      return;
    }
    // Bottom buttons are always reached with B. Directional focus stays in
    // the content so a long team/nation list scrolls immediately at row six.
    const uint32_t max_index = 5;
    if (direction == 1) {
      if (exhibition_popup_focus_index > 0)
        exhibition_popup_focus_index--;
      else if (team_popup || cpu_popup)
        __atomic_store_n(&exhibition_popup_scroll_request, -1,
                         __ATOMIC_RELEASE);
    } else if (direction == 2) {
      if (exhibition_popup_focus_index < max_index)
        exhibition_popup_focus_index++;
      else if (team_popup || cpu_popup)
        __atomic_store_n(&exhibition_popup_scroll_request, 1,
                         __ATOMIC_RELEASE);
    }
    return;
  }

  if (!direction) {
    exhibition_search_focus_direction = 0;
    return;
  }
  const int pressed = (buttons & (1u << (direction + 9))) != 0 &&
                      !(previous_buttons & (1u << (direction + 9)));
  if (direction != exhibition_search_focus_direction) {
    exhibition_search_focus_direction = direction;
    exhibition_search_focus_started_ms = now;
    exhibition_search_focus_repeat_ms = now;
  } else if (!pressed && now - exhibition_search_focus_started_ms < 300) {
    return;
  } else if (!pressed && now - exhibition_search_focus_repeat_ms < 120) {
    return;
  }
  exhibition_search_focus_repeat_ms = now;

  uint32_t next = exhibition_search_focus_index;
  if (next < 2) {
    if (direction == 3 || direction == 4)
      next = next == 0 ? 1 : 0;
    else if (direction == 2)
      next = next == 0 ? 2 : 3;
  } else {
    if (direction == 1)
      next = next == 2 ? 0 : 1;
    else if (direction == 3 && next > 2)
      next--;
    else if (direction == 4 && next < 5)
      next++;
  }
  if (next != exhibition_search_focus_index) {
    exhibition_search_focus_index = next;
    exhibition_search_focus_apply(exhibition_search_window);
  }
}

int pes_controller_menu_touch_target(float *normalized_x,
                                     float *normalized_y) {
  float prompt_x = 0.0f;
  float prompt_y = 0.0f;
  if (pes_controller_start_prompt(&prompt_x, &prompt_y)) {
    if (normalized_x)
      *normalized_x = prompt_x;
    if (normalized_y)
      *normalized_y = prompt_y;
    return 1;
  }
  if (__atomic_load_n(&main_menu_graphics_active, __ATOMIC_ACQUIRE))
    return 0;
  if (__atomic_load_n(&main_menu_info_popup, __ATOMIC_ACQUIRE) !=
      MAIN_MENU_INFO_CLOSED) {
    if (normalized_x)
      *normalized_x = 0.50f;
    if (normalized_y)
      *normalized_y = 0.18f;
    return 1;
  }
  if (__atomic_load_n(&main_menu_video_settings_open, __ATOMIC_ACQUIRE)) {
    // A is consumed by the custom overlay after this inert synthetic touch.
    if (normalized_x)
      *normalized_x = 0.50f;
    if (normalized_y)
      *normalized_y = 0.18f;
    return 1;
  }
  if (pes_main_menu_controller_active()) {
    const uint32_t index = pes_main_menu_focus_index();
    if (index >= 4)
      return 0;
    if (normalized_x)
      *normalized_x = (index & 1) ? 0.745f : 0.255f;
    if (normalized_y)
      *normalized_y = index >= 2 ? 0.825f : 0.465f;
    return 1;
  }
  if (!__atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE))
    return 0;
  if (__atomic_load_n(&exhibition_nested_popup_open, __ATOMIC_ACQUIRE)) {
    if (normalized_x)
      *normalized_x = 0.50f;
    if (normalized_y)
      *normalized_y = 0.194f + 0.111f * exhibition_popup_focus_index;
    return 1;
  }
  if (__atomic_load_n(&exhibition_team_picker_open, __ATOMIC_ACQUIRE)) {
    if (__atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE)) {
      // The custom browser handles A on touch release. Send the synthetic tap
      // to the inert header so the native Matchmaking page cannot activate a
      // card or footer underneath it.
      if (normalized_x)
        *normalized_x = 0.50f;
      if (normalized_y)
        *normalized_y = 0.08f;
      return 1;
    }
    if (normalized_x)
      *normalized_x = 0.50f;
    if (normalized_y)
      *normalized_y = 0.199f + 0.111f * exhibition_popup_focus_index;
    return 1;
  }
  if (__atomic_load_n(&exhibition_cpu_level_popup_open, __ATOMIC_ACQUIRE)) {
    // Custom modals consume A after the synthetic touch is released. Aim the
    // touch at the inert title band so the matchmaking page underneath cannot
    // activate anything first.
    if (normalized_x)
      *normalized_x = 0.50f;
    if (normalized_y)
      *normalized_y = 0.10f;
    return 1;
  }
  if (__atomic_load_n(&exhibition_settings_popup_open, __ATOMIC_ACQUIRE)) {
    if (normalized_x)
      *normalized_x = 0.50f;
    if (normalized_y)
      *normalized_y = 0.10f;
    return 1;
  }
  if (exhibition_search_focus_index < 2) {
    if (normalized_x)
      *normalized_x = exhibition_search_focus_index == 0 ? 0.255f : 0.745f;
    if (normalized_y)
      *normalized_y = 0.47f;
    return 1;
  }
  if (normalized_x)
    *normalized_x = (float[]){0.13f, 0.37f, 0.63f, 0.87f}
                         [exhibition_search_focus_index - 2];
  if (normalized_y)
    *normalized_y = 0.91f;
  return 1;
}

int pes_controller_menu_back_target(float *normalized_x,
                                    float *normalized_y) {
  if (__atomic_load_n(&main_menu_info_popup, __ATOMIC_ACQUIRE) !=
      MAIN_MENU_INFO_CLOSED) {
    if (normalized_x)
      *normalized_x = 0.50f;
    if (normalized_y)
      *normalized_y = 0.18f;
    return 1;
  }
  if (__atomic_load_n(&main_menu_video_settings_open, __ATOMIC_ACQUIRE)) {
    if (normalized_x)
      *normalized_x = 0.50f;
    if (normalized_y)
      *normalized_y = 0.18f;
    return 1;
  }
  if (!__atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE))
    return 0;

  if (normalized_x)
    *normalized_x = 0.50f;
  if (normalized_y)
    *normalized_y = 0.905f;

  if (__atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE) ||
      __atomic_load_n(&exhibition_cpu_level_popup_open, __ATOMIC_ACQUIRE) ||
      __atomic_load_n(&exhibition_settings_popup_open, __ATOMIC_ACQUIRE)) {
    if (normalized_x)
      *normalized_x = 0.50f;
    if (normalized_y)
      *normalized_y = 0.08f;
    return 1;
  }

  if (!__atomic_load_n(&exhibition_team_picker_open,
                              __ATOMIC_ACQUIRE) &&
             !__atomic_load_n(&exhibition_cpu_level_popup_open,
                              __ATOMIC_ACQUIRE) &&
             !__atomic_load_n(&exhibition_nested_popup_open,
                              __ATOMIC_ACQUIRE)) {
    if (normalized_x)
      *normalized_x = 0.13f;
    if (normalized_y)
      *normalized_y = 0.91f;
  }
  return 1;
}

void pes_controller_menu_back_pressed(void) {
  if (__atomic_load_n(&main_menu_info_popup, __ATOMIC_ACQUIRE) !=
      MAIN_MENU_INFO_CLOSED) {
    main_menu_info_close();
    return;
  }
  if (__atomic_load_n(&main_menu_video_settings_open, __ATOMIC_ACQUIRE)) {
    main_menu_video_close();
    return;
  }
  const uint32_t custom_team_phase =
      __atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE);
  if (custom_team_phase) {
    if (custom_team_phase == EXHIBITION_TEAM_POPUP_TEAM) {
      __atomic_store_n(&exhibition_custom_team_popup,
                       EXHIBITION_TEAM_POPUP_CATEGORY, __ATOMIC_RELEASE);
    } else {
      __atomic_store_n(&exhibition_custom_team_popup,
                       EXHIBITION_TEAM_POPUP_CLOSED, __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_team_picker_open, 0, __ATOMIC_RELEASE);
    }
    exhibition_team_scroll_offset = 0;
    exhibition_popup_focus_index = 0;
    exhibition_popup_focus_direction = 0;
    return;
  }
  if (__atomic_exchange_n(&exhibition_cpu_level_popup_open, 0,
                          __ATOMIC_ACQ_REL)) {
    exhibition_popup_focus_index = 0;
    exhibition_popup_focus_direction = 0;
    debugPrintf("exhibition: custom COM Level closed\n");
    return;
  }
  if (__atomic_exchange_n(&exhibition_settings_popup_open, 0,
                          __ATOMIC_ACQ_REL)) {
    exhibition_settings_match = NULL;
    exhibition_popup_focus_index = 0;
    exhibition_popup_focus_direction = 0;
    debugPrintf("exhibition: custom Match Settings closed\n");
    return;
  }
  if (!__atomic_load_n(&exhibition_nested_popup_open, __ATOMIC_ACQUIRE))
    return;
  // Let the native child consume the synthetic B/UP first. Its callback will
  // clear this state; the timeout is only a safety net for a missing callback.
  __atomic_store_n(&exhibition_nested_back_pending, 1, __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_nested_back_started_ms,
                   exhibition_search_focus_now_ms(), __ATOMIC_RELEASE);
}

void pes_controller_title_ready(void *window) {
  __atomic_store_n(&startup_prompt_active, 1, __ATOMIC_RELEASE);

  // The Android title layout exposes its graphics/settings shortcut as the
  // c_menu choice in the lower-right corner. Settings is now available from
  // the compact four-tile page, so keep this duplicate entry out of the title
  // screen. PostInitMobile runs after the choice has been constructed.
  void *root = window && exhibition_window_get_window
                   ? exhibition_window_get_window(window)
                   : NULL;
  void *settings_choice = root ? exhibition_find_root_node(root, "c_menu")
                               : NULL;
  if (settings_choice && exhibition_node_set_visible)
    exhibition_node_set_visible(settings_choice, 0, 2);
  debugPrintf("UE4 menu: title ready root=%p c_menu=%p hidden=%u\n", root,
              settings_choice, settings_choice != NULL);
}

int pes_controller_start_prompt(float *normalized_x, float *normalized_y) {
  if (!__atomic_load_n(&startup_prompt_active, __ATOMIC_ACQUIRE) ||
      __atomic_load_n(&exhibition_session_active, __ATOMIC_ACQUIRE) ||
      __atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE) ||
      __atomic_load_n(&exhibition_team_select_active, __ATOMIC_ACQUIRE))
    return 0;
  if (normalized_x)
    *normalized_x = 0.284f;
  if (normalized_y)
    *normalized_y = 0.704f;
  return 1;
}

int pes_controller_selector_rect(float *x, float *y, float *width,
                                 float *height) {
  exhibition_nested_back_expire();
  float rect_x = 0.0f;
  float rect_y = 0.0f;
  float rect_width = 0.0f;
  float rect_height = 0.0f;
  if (__atomic_load_n(&main_menu_info_popup, __ATOMIC_ACQUIRE) !=
          MAIN_MENU_INFO_CLOSED ||
      __atomic_load_n(&main_menu_video_settings_open, __ATOMIC_ACQUIRE)) {
    return 0;
  } else if (pes_main_menu_controller_active()) {
    const uint32_t index = pes_main_menu_focus_index();
    if (index >= 4)
      return 0;
    rect_x = (index & 1) ? 0.506f : 0.024f;
    rect_y = index >= 2 ? 0.724f : 0.234f;
    rect_width = 0.470f;
    // The stock cards are not equal-height: the top pair are tall hero cards
    // and the bottom pair are compact action cards. Keep the outline inside
    // their rounded corners instead of bleeding into the gutters.
    rect_height = index >= 2 ? 0.212f : 0.456f;
  } else if (__atomic_load_n(&exhibition_searching_active,
                             __ATOMIC_ACQUIRE)) {
    if (__atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE) ||
        __atomic_load_n(&exhibition_cpu_level_popup_open, __ATOMIC_ACQUIRE) ||
        __atomic_load_n(&exhibition_settings_popup_open, __ATOMIC_ACQUIRE))
      return 0;
    if (__atomic_load_n(&exhibition_nested_popup_open, __ATOMIC_ACQUIRE)) {
      rect_x = 0.225f;
      rect_y = 0.148f + 0.111f * exhibition_popup_focus_index;
      rect_width = 0.550f;
      rect_height = 0.102f;
    } else if (__atomic_load_n(&exhibition_team_picker_open, __ATOMIC_ACQUIRE)) {
      rect_x = 0.225f;
      // Team category rows sit a few pixels higher than COM's value rows.
      rect_y = 0.138f + 0.111f * exhibition_popup_focus_index;
      rect_width = 0.550f;
      rect_height = 0.106f;
    } else if (__atomic_load_n(&exhibition_cpu_level_popup_open,
                               __ATOMIC_ACQUIRE)) {
      rect_x = 0.225f;
      rect_y = 0.148f + 0.111f * exhibition_popup_focus_index;
      rect_width = 0.550f;
      rect_height = 0.102f;
    } else if (__atomic_load_n(&exhibition_settings_popup_open,
                               __ATOMIC_ACQUIRE)) {
      static const float settings_y[5] = {0.320f, 0.540f, 0.645f, 0.750f,
                                          0.915f};
      rect_x = exhibition_popup_focus_index >= 2 ? 0.875f : 0.050f;
      rect_y = settings_y[exhibition_popup_focus_index];
      rect_width = exhibition_popup_focus_index >= 2 ? 0.075f : 0.900f;
      rect_height = 0.100f;
    } else {
    const uint32_t index = exhibition_search_focus_index;
    if (index < 2) {
      rect_x = index == 0 ? 0.035f : 0.520f;
      rect_y = 0.205f;
      rect_width = 0.445f;
      rect_height = 0.615f;
    } else if (index < 6) {
      static const float footer_x[4] = {0.024f, 0.250f, 0.505f, 0.760f};
      static const float footer_width[4] = {0.215f, 0.245f, 0.245f,
                                            0.215f};
      rect_x = footer_x[index - 2];
      rect_y = 0.895f;
      rect_width = footer_width[index - 2];
      rect_height = 0.090f;
    } else {
      return 0;
    }
    }
  } else {
    return 0;
  }
  if (x)
    *x = rect_x;
  if (y)
    *y = rect_y;
  if (width)
    *width = rect_width;
  if (height)
    *height = rect_height;
  return 1;
}

int pes_controller_selector_custom_style(void) {
  // Filled rows are most useful on the two long list pickers; the other
  // screens keep the lighter outline-only treatment.
  return __atomic_load_n(&exhibition_cpu_level_popup_open, __ATOMIC_ACQUIRE) !=
             0 ||
         __atomic_load_n(&exhibition_team_picker_open, __ATOMIC_ACQUIRE) != 0;
}

int pes_controller_custom_team_popup_active(void) {
  return __atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE) != 0;
}

uint32_t pes_controller_custom_team_popup_scroll(void) {
  return exhibition_team_scroll_offset;
}

uint32_t pes_controller_custom_team_popup_focus(void) {
  return exhibition_popup_focus_index - exhibition_team_scroll_offset;
}

uint32_t pes_controller_custom_team_popup_visible_count(void) {
  const uint32_t count = exhibition_custom_team_item_count();
  if (exhibition_team_scroll_offset >= count)
    return 0;
  const uint32_t remaining = count - exhibition_team_scroll_offset;
  return remaining < EXHIBITION_TEAM_GRID_PAGE_SIZE
             ? remaining
             : EXHIBITION_TEAM_GRID_PAGE_SIZE;
}

const char *pes_controller_custom_team_popup_label(uint32_t index) {
  if (__atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE) ==
      EXHIBITION_TEAM_POPUP_TEAM) {
    const ExhibitionTeamCategory *category = exhibition_team_category();
    return category && index < category->team_count
               ? exhibition_team_name(category->teams[index])
               : "";
  }
  return index < EXHIBITION_TEAM_CATEGORY_COUNT
             ? exhibition_team_categories[index].label
             : "";
}

const char *pes_controller_custom_team_popup_icon(uint32_t index) {
  if (__atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE) ==
      EXHIBITION_TEAM_POPUP_TEAM) {
    const ExhibitionTeamCategory *category = exhibition_team_category();
    return category ? category->icon : "FC";
  }
  return index < EXHIBITION_TEAM_CATEGORY_COUNT
             ? exhibition_team_categories[index].icon
             : "";
}

uint32_t pes_controller_custom_team_popup_badge(uint32_t index) {
  if (__atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE) ==
      EXHIBITION_TEAM_POPUP_TEAM) {
    const ExhibitionTeamCategory *category = exhibition_team_category();
    if (!category || index >= category->team_count)
      return 0;
    const uint32_t team_id = category->teams[index];
    if (team_id < 140u)
      return team_id;
    // Slots 140..152 are category emblems. The migrated high-ID clubs use
    // compact slots 153..162 populated from the same native badge PNGs.
    switch (team_id) {
    case 173u: return 153u;
    case 177u: return 154u;
    case 179u: return 155u;
    case 191u: return 156u;
    case 192u: return 157u;
    case 193u: return 158u;
    case 234u: return 159u;
    case 327u: return 160u;
    case 333u: return 161u;
    case 377u: return 162u;
    default: return 0;
    }
  }
  return index < EXHIBITION_TEAM_CATEGORY_COUNT ? 140u + index : 140u;
}

const char *pes_controller_custom_team_popup_title(void) {
  if (__atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE) ==
      EXHIBITION_TEAM_POPUP_TEAM) {
    const ExhibitionTeamCategory *category = exhibition_team_category();
    return category ? category->label : "SELECT TEAM";
  }
  return "SELECT CATEGORY";
}

uint32_t pes_controller_custom_team_popup_page(void) {
  return exhibition_team_scroll_offset / EXHIBITION_TEAM_GRID_PAGE_SIZE;
}

uint32_t pes_controller_custom_team_popup_page_count(void) {
  const uint32_t count = exhibition_custom_team_item_count();
  return count ? (count + EXHIBITION_TEAM_GRID_PAGE_SIZE - 1) /
                     EXHIBITION_TEAM_GRID_PAGE_SIZE
               : 1;
}

int pes_controller_custom_cpu_popup_active(void) {
  return __atomic_load_n(&exhibition_cpu_level_popup_open,
                         __ATOMIC_ACQUIRE) != 0;
}

uint32_t pes_controller_custom_cpu_popup_focus(void) {
  return exhibition_popup_focus_index < EXHIBITION_CPU_LEVEL_COUNT
             ? exhibition_popup_focus_index
             : 0;
}

uint32_t pes_controller_custom_cpu_popup_value(void) {
  const uint32_t value = __atomic_load_n(&exhibition_cpu_level_value,
                                         __ATOMIC_ACQUIRE);
  return value < EXHIBITION_CPU_LEVEL_COUNT ? value : 2;
}

uint32_t pes_controller_custom_cpu_popup_count(void) {
  return EXHIBITION_CPU_LEVEL_COUNT;
}

const char *pes_controller_custom_cpu_popup_label(uint32_t index) {
  return index < EXHIBITION_CPU_LEVEL_COUNT
             ? exhibition_cpu_level_labels[index]
             : "";
}

int pes_controller_custom_match_settings_active(void) {
  return __atomic_load_n(&exhibition_settings_popup_open,
                         __ATOMIC_ACQUIRE) != 0;
}

uint32_t pes_controller_custom_match_settings_focus(void) {
  return exhibition_popup_focus_index < PES_MATCH_SETTINGS_COUNT ? exhibition_popup_focus_index : 0;
}

const char *pes_controller_custom_match_settings_label(uint32_t index) {
  static const char *const labels[] = {
      "TIME", "MATCH TIME", "OVERTIME", "PENALTIES", "PLAYER CURSOR"};
  return index < PES_MATCH_SETTINGS_COUNT ? labels[index] : "";
}

const char *pes_controller_custom_match_settings_value(uint32_t index) {
  static const char *const match_time_labels[] = {
      "5 MIN", "6 MIN", "7 MIN", "8 MIN", "9 MIN", "10 MIN"};
  if (index == 0)
    return __atomic_load_n(&exhibition_settings_time_zone,
                           __ATOMIC_ACQUIRE)
               ? "NIGHT"
               : "DAY";
  if (index == 1) {
    const uint32_t minutes = __atomic_load_n(&exhibition_settings_match_time,
                                             __ATOMIC_ACQUIRE);
    return minutes >= 5 && minutes <= 10 ? match_time_labels[minutes - 5]
                                         : "10 MIN";
  }
  if (index == 2)
    return __atomic_load_n(&exhibition_settings_extra_time,
                           __ATOMIC_ACQUIRE)
               ? "ON"
               : "OFF";
  if (index == 3)
    return __atomic_load_n(&exhibition_settings_penalties,
                           __ATOMIC_ACQUIRE)
               ? "ON"
               : "OFF";
  if (index == 4)
    return __atomic_load_n(&config.player_cursor_show, __ATOMIC_ACQUIRE)
               ? "SHOW" : "HIDE";
  return "";
}

int pes_controller_custom_video_settings_active(void) {
  return __atomic_load_n(&main_menu_video_settings_open,
                         __ATOMIC_ACQUIRE) != 0;
}

uint32_t pes_controller_custom_video_settings_focus(void) {
  return main_menu_video_focus_index < 2 ? main_menu_video_focus_index : 0;
}

const char *pes_controller_custom_video_settings_label(uint32_t index) {
  static const char *const labels[] = {"GRAPHICS", "FRAME RATE"};
  return index < 2 ? labels[index] : "";
}

const char *pes_controller_custom_video_settings_value(uint32_t index) {
  if (index == 0)
    return __atomic_load_n(&main_menu_video_graphics, __ATOMIC_ACQUIRE)
               ? "STANDARD"
               : "LOW";
  if (index == 1)
    return __atomic_load_n(&main_menu_video_frame_rate, __ATOMIC_ACQUIRE)
               ? "30 FPS"
               : "60 FPS";
  return "";
}

static void *match_gameplan_resolve_squad(uint32_t reload) {
  if (reload && matchplan_squad_load)
    matchplan_squad_load();
  if (!exhibition_tmpdb_manager_get_instance ||
      !exhibition_squad_edit_get_squad_data)
    return NULL;

  void *manager = exhibition_tmpdb_manager_get_instance();
  void *tmpdb_data = NULL;
  if (manager)
    memcpy(&tmpdb_data, (unsigned char *)manager + 72,
           sizeof(tmpdb_data));
  if (!tmpdb_data)
    return NULL;

  unsigned char *squad_edit = (unsigned char *)tmpdb_data + 0x18360;
  uint32_t side = exhibition_get_match_my_side
                      ? exhibition_get_match_my_side()
                      : 0;
  if (side > 1) {
    memcpy(&side, squad_edit + 5312, sizeof(side));
    if (side > 1)
      side = 0;
  }
  return exhibition_squad_edit_get_squad_data(squad_edit, side);
}

static void match_gameplan_refresh_players(uint32_t reload) {
  match_gameplan_player_count = 0;
  match_gameplan_starter_count = 0;
  match_gameplan_bench_count = 0;
  match_gameplan_squad_data = match_gameplan_resolve_squad(reload);
  void *squad_data = match_gameplan_squad_data;
  if (!squad_data || !exhibition_squad_data_get_player_count ||
      !exhibition_squad_data_get_player_by_index)
    return;

  uint32_t count = exhibition_squad_data_get_player_count(squad_data);
  if (count > MATCH_GAMEPLAN_MAX_PLAYERS)
    count = MATCH_GAMEPLAN_MAX_PLAYERS;
  for (uint32_t index = 0; index < count; index++) {
    void *squad_player =
        exhibition_squad_data_get_player_by_index(squad_data, &index);
    if (!squad_player)
      continue;
    MatchGameplanPlayer *entry =
        &match_gameplan_players[match_gameplan_player_count];
    memset(entry, 0, sizeof(*entry));
    memcpy(entry->player_id, squad_player, sizeof(entry->player_id));
    entry->starting = match_squad_data_is_starting
                          ? match_squad_data_is_starting(
                                squad_data, entry->player_id) != 0
                          : index < 11;
    void *player = match_squad_data_get_tmpdb_player
                       ? match_squad_data_get_tmpdb_player(
                             squad_data, entry->player_id)
                       : NULL;
    const char *name = player && match_tmpdb_player_get_name
                           ? match_tmpdb_player_get_name(player)
                           : NULL;
    if (name && name[0]) {
      strncpy(entry->name, name, sizeof(entry->name) - 1);
      entry->name[sizeof(entry->name) - 1] = '\0';
    } else {
      snprintf(entry->name, sizeof(entry->name), "PLAYER %u", index + 1);
    }
    if (entry->starting)
      match_gameplan_starter_count++;
    else
      match_gameplan_bench_count++;
    match_gameplan_player_count++;
  }
  if (!match_gameplan_starter_count && match_gameplan_player_count) {
    match_gameplan_starter_count =
        match_gameplan_player_count < 11 ? match_gameplan_player_count : 11;
    match_gameplan_bench_count =
        match_gameplan_player_count - match_gameplan_starter_count;
    for (uint32_t index = 0; index < match_gameplan_player_count; index++)
      match_gameplan_players[index].starting =
          index < match_gameplan_starter_count;
  }
  match_gameplan_tactics = match_squad_data_get_tactics
                               ? match_squad_data_get_tactics(squad_data) & 1u
                               : 0;
  if (match_gameplan_starter_index >= match_gameplan_starter_count)
    match_gameplan_starter_index = 0;
  if (match_gameplan_bench_index >= match_gameplan_bench_count)
    match_gameplan_bench_index = 0;
}

static MatchGameplanPlayer *match_gameplan_nth_player(uint32_t starting,
                                                       uint32_t wanted) {
  uint32_t seen = 0;
  for (uint32_t index = 0; index < match_gameplan_player_count; index++) {
    MatchGameplanPlayer *entry = &match_gameplan_players[index];
    if ((uint32_t)entry->starting != starting)
      continue;
    if (seen++ == wanted)
      return entry;
  }
  return NULL;
}

static void match_gameplan_swap_selected(void) {
  void *squad_data = match_gameplan_squad_data;
  MatchGameplanPlayer *starter = match_gameplan_nth_player(
      1, match_gameplan_starter_index);
  MatchGameplanPlayer *bench = match_gameplan_nth_player(
      0, match_gameplan_bench_index);
  if (!squad_data || !starter || !bench ||
      !match_squad_data_get_order_no || !match_squad_data_get_member_id ||
      !match_swap_member_info_construct || !match_replace_squad_player)
    return;

  _Alignas(8) unsigned char starter_info[24] = {0};
  _Alignas(8) unsigned char bench_info[24] = {0};
  match_swap_member_info_construct(
      starter_info,
      match_squad_data_get_order_no(squad_data, starter->player_id),
      match_squad_data_get_member_id(squad_data, starter->player_id),
      starter->player_id);
  match_swap_member_info_construct(
      bench_info,
      match_squad_data_get_order_no(squad_data, bench->player_id),
      match_squad_data_get_member_id(squad_data, bench->player_id),
      bench->player_id);
  match_replace_squad_player(squad_data, starter_info, bench_info);
  if (matchplan_squad_save)
    matchplan_squad_save();
  match_gameplan_refresh_players(0);
}

int pes_controller_custom_info_popup_active(void) {
  return pes_controller_custom_prematch_gameplan_active() ||
         __atomic_load_n(&match_pause_custom_active, __ATOMIC_ACQUIRE) != 0 ||
         __atomic_load_n(&match_postmatch_custom_active,
                         __ATOMIC_ACQUIRE) != 0 ||
         __atomic_load_n(&main_menu_info_popup, __ATOMIC_ACQUIRE) !=
             MAIN_MENU_INFO_CLOSED;
}

const char *pes_controller_custom_info_popup_title(void) {
  if (pes_controller_custom_prematch_gameplan_active()) {
    const uint32_t page = __atomic_load_n(
        &exhibition_gameplan_custom_page, __ATOMIC_ACQUIRE);
    if (page == EXHIBITION_GAMEPLAN_PAGE_SUBSTITUTION)
      return "SUBSTITUTION";
    if (page == EXHIBITION_GAMEPLAN_PAGE_FORMATION)
      return "FORMATION";
    return "GAME PLAN";
  }
  if (__atomic_load_n(&match_pause_custom_active, __ATOMIC_ACQUIRE)) {
    const uint32_t page =
        __atomic_load_n(&match_pause_custom_page, __ATOMIC_ACQUIRE);
    if (page == MATCH_PAUSE_PAGE_GAMEPLAN)
      return "GAME PLAN";
    if (page == MATCH_PAUSE_PAGE_SUBSTITUTION)
      return "SUBSTITUTION";
    if (page == MATCH_PAUSE_PAGE_FORMATION)
      return "FORMATION";
    return "PAUSE MENU";
  }
  if (__atomic_load_n(&match_postmatch_custom_active, __ATOMIC_ACQUIRE)) {
    const uint32_t page = __atomic_load_n(&match_postmatch_custom_page,
                                           __ATOMIC_ACQUIRE);
    if (page == MATCH_POSTMATCH_PAGE_GAMEPLAN)
      return "GAME PLAN";
    if (page == MATCH_POSTMATCH_PAGE_SUBSTITUTION)
      return "SUBSTITUTION";
    if (page == MATCH_POSTMATCH_PAGE_FORMATION)
      return "FORMATION";
    return "POST MATCH";
  }
  const uint32_t popup =
      __atomic_load_n(&main_menu_info_popup, __ATOMIC_ACQUIRE);
  if (popup == MAIN_MENU_INFO_CREDITS)
    return "CREDITS";
  if (popup == MAIN_MENU_INFO_TWO_PLAYER)
    return "2 PLAYER";
  return "";
}

uint32_t pes_controller_custom_info_popup_line_count(void) {
  if (pes_controller_custom_prematch_gameplan_active()) {
    const uint32_t page = __atomic_load_n(
        &exhibition_gameplan_custom_page, __ATOMIC_ACQUIRE);
    return page == EXHIBITION_GAMEPLAN_PAGE_ROOT ? 5 : 4;
  }
  if (__atomic_load_n(&match_pause_custom_active, __ATOMIC_ACQUIRE)) {
    const uint32_t page =
        __atomic_load_n(&match_pause_custom_page, __ATOMIC_ACQUIRE);
    return page == MATCH_PAUSE_PAGE_ROOT ? 5 : 4;
  }
  if (__atomic_load_n(&match_postmatch_custom_active, __ATOMIC_ACQUIRE))
    return 4;
  const uint32_t popup =
      __atomic_load_n(&main_menu_info_popup, __ATOMIC_ACQUIRE);
  if (popup == MAIN_MENU_INFO_CREDITS)
    return 3;
  if (popup == MAIN_MENU_INFO_TWO_PLAYER)
    return 1;
  return 0;
}

const char *pes_controller_custom_info_popup_line(uint32_t index) {
  if (pes_controller_custom_prematch_gameplan_active()) {
    const uint32_t page = __atomic_load_n(
        &exhibition_gameplan_custom_page, __ATOMIC_ACQUIRE);
    if (page == EXHIBITION_GAMEPLAN_PAGE_ROOT) {
      static const char *const normal[] = {
          "  SUBSTITUTION", "  FORMATION", "  HOME KIT",
          "  AWAY KIT", "  PLAY"};
      static const char *const focused[] = {
          "> SUBSTITUTION", "> FORMATION", "> HOME KIT",
          "> AWAY KIT", "> PLAY"};
      static char kit_line[2][64];
      const uint32_t focus = __atomic_load_n(
          &exhibition_gameplan_custom_focus, __ATOMIC_ACQUIRE);
      if (index == 2 || index == 3) {
        const uint32_t side = index - 2;
        const uint32_t count = exhibition_uniform_choice_count[side];
        const uint32_t choice = exhibition_uniform_choice_index[side];
        if (count && choice < count) {
          const uint32_t kit_number =
              (exhibition_uniform_choices[side][choice] & 0x3fffu) + 1u;
          snprintf(kit_line[side], sizeof(kit_line[side]),
                   "%c %s KIT: < KIT %u >",
                   focus == index ? '>' : ' ', side ? "AWAY" : "HOME",
                   kit_number);
        } else {
          snprintf(kit_line[side], sizeof(kit_line[side]),
                   "%c %s KIT: UNAVAILABLE",
                   focus == index ? '>' : ' ', side ? "AWAY" : "HOME");
        }
        return kit_line[side];
      }
      return index < 5 ? (index == focus ? focused[index] : normal[index])
                       : "";
    }
    if (page == EXHIBITION_GAMEPLAN_PAGE_SUBSTITUTION) {
      static char starter_line[64];
      static char bench_line[64];
      const MatchGameplanPlayer *starter = match_gameplan_nth_player(
          1, match_gameplan_starter_index);
      const MatchGameplanPlayer *bench = match_gameplan_nth_player(
          0, match_gameplan_bench_index);
      if (index == 0) {
        snprintf(starter_line, sizeof(starter_line), "%c STARTER: < %s >",
                 match_gameplan_focus == 0 ? '>' : ' ',
                 starter ? starter->name : "UNAVAILABLE");
        return starter_line;
      }
      if (index == 1) {
        snprintf(bench_line, sizeof(bench_line), "%c BENCH: < %s >",
                 match_gameplan_focus == 1 ? '>' : ' ',
                 bench ? bench->name : "UNAVAILABLE");
        return bench_line;
      }
      if (index == 2)
        return "LEFT / RIGHT: CHOOSE PLAYER";
      return index == 3 ? "A SWAP   B BACK" : "";
    }
    if (page == EXHIBITION_GAMEPLAN_PAGE_FORMATION) {
      if (index == 0)
        return "> FORMATION MODE";
      if (index == 1)
        return match_gameplan_tactics ? "< DEFENSIVE >" : "< OFFENSIVE >";
      if (index == 2)
        return "LEFT / RIGHT: CHANGE";
      return index == 3 ? "A APPLY   B BACK" : "";
    }
  }
  if (__atomic_load_n(&match_pause_custom_active, __ATOMIC_ACQUIRE)) {
    const uint32_t page =
        __atomic_load_n(&match_pause_custom_page, __ATOMIC_ACQUIRE);
    if (page == MATCH_PAUSE_PAGE_GAMEPLAN) {
      static const char *const normal[] = {
          "  SUBSTITUTION", "  FORMATION", "  RETURN TO PAUSE"};
      static const char *const focused[] = {
          "> SUBSTITUTION", "> FORMATION", "> RETURN TO PAUSE"};
      if (index < 3) {
        const uint32_t focus = __atomic_load_n(&match_gameplan_focus,
                                                __ATOMIC_ACQUIRE);
        return index == focus ? focused[index] : normal[index];
      }
      return index == 3 ? "A SELECT" : "";
    }
    if (page == MATCH_PAUSE_PAGE_SUBSTITUTION) {
      static char starter_line[64];
      static char bench_line[64];
      const MatchGameplanPlayer *starter = match_gameplan_nth_player(
          1, match_gameplan_starter_index);
      const MatchGameplanPlayer *bench = match_gameplan_nth_player(
          0, match_gameplan_bench_index);
      if (index == 0) {
        snprintf(starter_line, sizeof(starter_line), "%c STARTER: < %s >",
                 match_gameplan_focus == 0 ? '>' : ' ',
                 starter ? starter->name : "UNAVAILABLE");
        return starter_line;
      }
      if (index == 1) {
        snprintf(bench_line, sizeof(bench_line), "%c BENCH: < %s >",
                 match_gameplan_focus == 1 ? '>' : ' ',
                 bench ? bench->name : "UNAVAILABLE");
        return bench_line;
      }
      if (index == 2)
        return "LEFT / RIGHT: CHOOSE PLAYER";
      return index == 3 ? "A SWAP   B BACK" : "";
    }
    if (page == MATCH_PAUSE_PAGE_FORMATION) {
      if (index == 0)
        return match_gameplan_focus == 0
                   ? "> FORMATION MODE"
                   : "  FORMATION MODE";
      if (index == 1)
        return match_gameplan_tactics ? "< DEFENSIVE >" : "< OFFENSIVE >";
      if (index == 2)
        return "LEFT / RIGHT: CHANGE";
      return index == 3 ? "A APPLY   B BACK" : "";
    }
    static const char *const normal[] = {
        "  RESUME MATCH", "  GAME PLAN", "  CAMERA MODE",
        "  BACK TO HOME"};
    static const char *const focused[] = {
        "> RESUME MATCH", "> GAME PLAN", "> CAMERA MODE",
        "> BACK TO HOME"};
    if (index < 4) {
      const uint32_t focus = __atomic_load_n(&match_pause_custom_focus,
                                              __ATOMIC_ACQUIRE);
      return index == focus ? focused[index] : normal[index];
    }
    return index == 4 ? "A SELECT" : "";
  }
  if (__atomic_load_n(&match_postmatch_custom_active, __ATOMIC_ACQUIRE)) {
    const uint32_t page = __atomic_load_n(&match_postmatch_custom_page,
                                           __ATOMIC_ACQUIRE);
    if (page == MATCH_POSTMATCH_PAGE_ROOT) {
      static const char *const normal[] = {
          "  GAME PLAN", "  BACK TO MAIN MENU"};
      static const char *const focused[] = {
          "> GAME PLAN", "> BACK TO MAIN MENU"};
      if (index < 2) {
        const uint32_t focus = __atomic_load_n(&match_postmatch_custom_focus,
                                                __ATOMIC_ACQUIRE);
        return index == focus ? focused[index] : normal[index];
      }
      return index == 2 ? "A SELECT" : "";
    }
    if (page == MATCH_POSTMATCH_PAGE_GAMEPLAN) {
      static const char *const normal[] = {
          "  SUBSTITUTION", "  FORMATION", "  RETURN TO RESULT"};
      static const char *const focused[] = {
          "> SUBSTITUTION", "> FORMATION", "> RETURN TO RESULT"};
      if (index < 3)
        return index == match_gameplan_focus ? focused[index]
                                              : normal[index];
      return index == 3 ? "A SELECT" : "";
    }
    if (page == MATCH_POSTMATCH_PAGE_SUBSTITUTION) {
      static char starter_line[64];
      static char bench_line[64];
      const MatchGameplanPlayer *starter = match_gameplan_nth_player(
          1, match_gameplan_starter_index);
      const MatchGameplanPlayer *bench = match_gameplan_nth_player(
          0, match_gameplan_bench_index);
      if (index == 0) {
        snprintf(starter_line, sizeof(starter_line), "%c STARTER: < %s >",
                 match_gameplan_focus == 0 ? '>' : ' ',
                 starter ? starter->name : "UNAVAILABLE");
        return starter_line;
      }
      if (index == 1) {
        snprintf(bench_line, sizeof(bench_line), "%c BENCH: < %s >",
                 match_gameplan_focus == 1 ? '>' : ' ',
                 bench ? bench->name : "UNAVAILABLE");
        return bench_line;
      }
      if (index == 2)
        return "LEFT / RIGHT: CHOOSE PLAYER";
      return index == 3 ? "A SWAP   B BACK" : "";
    }
    if (page == MATCH_POSTMATCH_PAGE_FORMATION) {
      if (index == 0)
        return "> FORMATION MODE";
      if (index == 1)
        return match_gameplan_tactics ? "< DEFENSIVE >" : "< OFFENSIVE >";
      if (index == 2)
        return "LEFT / RIGHT: CHANGE";
      return index == 3 ? "A APPLY   B BACK" : "";
    }
  }
  const uint32_t popup =
      __atomic_load_n(&main_menu_info_popup, __ATOMIC_ACQUIRE);
  if (popup == MAIN_MENU_INFO_CREDITS) {
    static const char *const lines[] = {
        "Port & Mod By Ibnuard",
        "Support : androswitch.vercel.app",
        "Version: " PES_NX_VERSION,
    };
    return index < 3 ? lines[index] : "";
  }
  if (popup == MAIN_MENU_INFO_TWO_PLAYER)
    return index == 0 ? "Single-player native controller test" : "";
  return "";
}

int pes_controller_menu_scroll_request(void) {
  return __atomic_exchange_n(&exhibition_popup_scroll_request, 0,
                             __ATOMIC_ACQ_REL);
}

void pes_controller_menu_tap(float normalized_x, float normalized_y) {
  if (pes_controller_start_prompt(NULL, NULL)) {
    // The first A is the start-screen confirmation. Clear this one-shot
    // state after the synthetic touch is delivered so later A presses can
    // activate tiles and settings.
    __atomic_store_n(&startup_prompt_active, 0, __ATOMIC_RELEASE);
    debugPrintf("input: startup prompt accepted via controller A\n");
    return;
  }
  if (__atomic_load_n(&main_menu_info_popup, __ATOMIC_ACQUIRE) !=
      MAIN_MENU_INFO_CLOSED)
    return;
  if (__atomic_load_n(&main_menu_video_settings_open, __ATOMIC_ACQUIRE)) {
    const uint64_t opened = __atomic_load_n(&main_menu_video_opened_ms,
                                             __ATOMIC_ACQUIRE);
    const uint64_t now = main_menu_focus_now_ms();
    // The A release that opened Settings must not immediately flip Graphics.
    if (!opened || now < opened || now - opened >= 140)
      main_menu_video_adjust(2);
    return;
  }
  if (__atomic_load_n(&exhibition_nested_popup_open, __ATOMIC_ACQUIRE)) {
    // Keep the child modal active after a value selection. B is the explicit
    // close action, matching the Switch flow instead of jumping to the parent.
    return;
  }
  const uint64_t popup_opened = __atomic_load_n(
      &exhibition_custom_popup_opened_ms, __ATOMIC_ACQUIRE);
  const uint64_t tap_now = exhibition_search_focus_now_ms();
  if (popup_opened && tap_now >= popup_opened &&
      tap_now - popup_opened < 140 &&
      (__atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE) ||
       __atomic_load_n(&exhibition_cpu_level_popup_open, __ATOMIC_ACQUIRE) ||
       __atomic_load_n(&exhibition_settings_popup_open, __ATOMIC_ACQUIRE)))
    return;
  if (__atomic_load_n(&exhibition_team_picker_open, __ATOMIC_ACQUIRE) &&
      __atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE)) {
    const uint32_t phase =
        __atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE);
    if (phase == EXHIBITION_TEAM_POPUP_CATEGORY &&
        exhibition_popup_focus_index < EXHIBITION_TEAM_CATEGORY_COUNT) {
      exhibition_team_category_index = exhibition_popup_focus_index;
      __atomic_store_n(&exhibition_custom_team_popup,
                       EXHIBITION_TEAM_POPUP_TEAM, __ATOMIC_RELEASE);
      exhibition_popup_focus_index = 0;
      exhibition_team_scroll_offset = 0;
      exhibition_popup_focus_direction = 0;
      debugPrintf("exhibition: custom category=%u %s\n",
                  exhibition_team_category_index,
                  exhibition_team_categories[exhibition_team_category_index]
                      .label);
      return;
    }
    const ExhibitionTeamCategory *category = exhibition_team_category();
    if (phase == EXHIBITION_TEAM_POPUP_TEAM && category &&
        exhibition_popup_focus_index < category->team_count) {
      const uint32_t side =
          __atomic_load_n(&exhibition_select_side, __ATOMIC_ACQUIRE);
      const uint32_t team_id = category->teams[exhibition_popup_focus_index];
      exhibition_select_team(side, team_id);
      __atomic_store_n(&exhibition_plan_ready, 0, __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_search_refresh_pending, 1,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_custom_team_popup,
                       EXHIBITION_TEAM_POPUP_CLOSED, __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_team_picker_open, 0, __ATOMIC_RELEASE);
      debugPrintf("exhibition: custom selected side=%u team=%u\n", side,
                  team_id);
    }
    exhibition_team_scroll_offset = 0;
    exhibition_popup_focus_index = 0;
    exhibition_popup_focus_direction = 0;
    return;
  }
  if (__atomic_load_n(&exhibition_cpu_level_popup_open, __ATOMIC_ACQUIRE)) {
    uint32_t level = exhibition_popup_focus_index;
    if (level >= EXHIBITION_CPU_LEVEL_COUNT)
      level = 2;
    exhibition_apply_cpu_level(level, NULL);
    debugPrintf("exhibition: custom COM level applied=%u\n", level);
    return;
  }
  if (__atomic_load_n(&exhibition_settings_popup_open, __ATOMIC_ACQUIRE)) {
    exhibition_adjust_match_setting(1);
    return;
  }
  if (__atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE) &&
      !__atomic_load_n(&exhibition_team_picker_open, __ATOMIC_ACQUIRE) &&
      !__atomic_load_n(&exhibition_cpu_level_popup_open, __ATOMIC_ACQUIRE) &&
      !__atomic_load_n(&exhibition_settings_popup_open, __ATOMIC_ACQUIRE) &&
      exhibition_search_focus_index < 2)
    pes_exhibition_matchmaking_tap(normalized_x, normalized_y);
}

int pes_controller_menu_physical_tap(float normalized_x,
                                     float normalized_y) {
  if (pes_controller_start_prompt(NULL, NULL)) {
    // A physical tap on the launch prompt follows the same one-shot path as
    // controller A. The game's original touch stream still receives the tap.
    __atomic_store_n(&startup_prompt_active, 0, __ATOMIC_RELEASE);
    debugPrintf("input: startup prompt accepted via physical tap at %.3f,%.3f\n",
                normalized_x, normalized_y);
    return 0;
  }
  if (__atomic_load_n(&main_menu_info_popup, __ATOMIC_ACQUIRE) !=
      MAIN_MENU_INFO_CLOSED) {
    if (normalized_y >= 0.68f && normalized_y <= 0.80f &&
        normalized_x >= 0.36f && normalized_x <= 0.64f)
      main_menu_info_close();
    return 0;
  }
  if (__atomic_load_n(&main_menu_video_settings_open, __ATOMIC_ACQUIRE)) {
    if (normalized_y >= 0.68f && normalized_y <= 0.78f) {
      if (normalized_x >= 0.61f && normalized_x <= 0.78f)
        main_menu_video_close();
      else if (normalized_x >= 0.41f && normalized_x <= 0.59f)
        main_menu_video_apply_current();
      else if (normalized_x >= 0.22f && normalized_x <= 0.39f)
        main_menu_video_adjust(2);
      return 0;
    }
    if (normalized_x >= 0.22f && normalized_x <= 0.78f &&
        normalized_y >= 0.30f && normalized_y < 0.61f) {
      int index = (int)floorf((normalized_y - 0.32f) / 0.145f);
      if (index < 0)
        index = 0;
      if (index > 1)
        index = 1;
      main_menu_video_focus_index = (uint32_t)index;
      main_menu_video_focus_direction = 0;
      main_menu_video_adjust(2);
    }
    return 0;
  }
  if (pes_main_menu_controller_active()) {
    if (normalized_x >= 0.02f && normalized_x <= 0.98f &&
        normalized_y >= 0.20f && normalized_y <= 0.95f) {
      const uint32_t column = normalized_x >= 0.50f ? 1u : 0u;
      const uint32_t row = normalized_y >= 0.70f ? 1u : 0u;
      main_menu_apply_focus(row * 2u + column);
    }
    return 1;
  }
  if (__atomic_load_n(&exhibition_nested_popup_open, __ATOMIC_ACQUIRE)) {
    // Keep the custom focus aligned with a physical row selection while the
    // native child applies its value/checkmark.
    if (normalized_y >= 0.130f && normalized_y < 0.860f) {
      // The row centers are about .199, .310, ... in the 720p viewport.
      int index = (int)floorf((normalized_y - 0.199f) / 0.111f + 0.5f);
      const uint32_t nested_kind = __atomic_load_n(
          &exhibition_nested_popup_kind, __ATOMIC_ACQUIRE);
      const int max_index =
          nested_kind == EXHIBITION_NESTED_SHORT_LIST ? 1 : 5;
      if (index < 0)
        index = 0;
      if (index > max_index)
        index = max_index;
      exhibition_popup_focus_index = (uint32_t)index;
      exhibition_popup_focus_direction = 0;
      debugPrintf("exhibition: physical nested row focus=%d y=%.3f\n",
                  index, normalized_y);
    }
    (void)normalized_x;
    return 0;
  }
  if (__atomic_load_n(&exhibition_team_picker_open, __ATOMIC_ACQUIRE)) {
    if (__atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE)) {
      if (normalized_x >= 0.17f && normalized_x <= 0.40f &&
          normalized_y >= 0.83f && normalized_y <= 0.93f) {
        pes_controller_menu_back_pressed();
        return 1;
      }
      if (normalized_x >= 0.170f && normalized_x <= 0.830f &&
          normalized_y >= 0.170f && normalized_y < 0.790f) {
        int row = (int)floorf((normalized_y - 0.190f) / 0.145f);
        int column = normalized_x >= 0.50f ? 1 : 0;
        if (row < 0)
          row = 0;
        if (row > 3)
          row = 3;
        const uint32_t index = exhibition_team_scroll_offset +
                               (uint32_t)(row * 2 + column);
        if (index < exhibition_custom_team_item_count()) {
          exhibition_popup_focus_index = index;
          exhibition_popup_focus_direction = 0;
          debugPrintf("exhibition: physical custom grid focus=%u y=%.3f\n",
                      index, normalized_y);
          pes_controller_menu_tap(normalized_x, normalized_y);
        }
      }
      return 1;
    }
    // Keep native taps intact, but mirror the visible row for the overlay.
    // Ignore the scrollbar strip so dragging it never jumps the selector.
    if (normalized_x >= 0.225f && normalized_x <= 0.800f &&
        normalized_y >= 0.130f && normalized_y < 0.860f) {
      int index = (int)floorf((normalized_y - 0.199f) / 0.111f + 0.5f);
      if (index < 0)
        index = 0;
      if (index > 5)
        index = 5;
      exhibition_popup_focus_index = (uint32_t)index;
      exhibition_popup_focus_direction = 0;
      debugPrintf("exhibition: physical team row focus=%d y=%.3f\n", index,
                  normalized_y);
    }
    return 0;
  }
  if (__atomic_load_n(&exhibition_cpu_level_popup_open, __ATOMIC_ACQUIRE)) {
    if (normalized_y >= 0.81f && normalized_y <= 0.91f) {
      if (normalized_x >= 0.53f && normalized_x <= 0.76f)
        pes_controller_menu_back_pressed();
      else if (normalized_x >= 0.24f && normalized_x <= 0.50f)
        pes_controller_menu_tap(normalized_x, normalized_y);
      return 1;
    }
    if (normalized_x >= 0.24f && normalized_x <= 0.76f &&
        normalized_y >= 0.195f && normalized_y < 0.750f) {
      int index = (int)floorf((normalized_y - 0.205f) / 0.077f);
      if (index < 0)
        index = 0;
      if (index >= (int)EXHIBITION_CPU_LEVEL_COUNT)
        index = (int)EXHIBITION_CPU_LEVEL_COUNT - 1;
      exhibition_popup_focus_index = (uint32_t)index;
      exhibition_popup_focus_direction = 0;
      pes_controller_menu_tap(normalized_x, normalized_y);
    }
    return 1;
  }
  if (!__atomic_load_n(&exhibition_settings_popup_open, __ATOMIC_ACQUIRE))
    return 0;

  if (normalized_y >= 0.81f && normalized_y <= 0.91f) {
    if (normalized_x >= 0.55f && normalized_x <= 0.80f)
      pes_controller_menu_back_pressed();
    else if (normalized_x >= 0.20f && normalized_x <= 0.49f)
      pes_controller_menu_tap(normalized_x, normalized_y);
    return 1;
  }
  if (normalized_x >= 0.18f && normalized_x <= 0.82f &&
      normalized_y >= PES_MATCH_SETTINGS_ROW_Y &&
      normalized_y < PES_MATCH_SETTINGS_ROW_Y + PES_MATCH_SETTINGS_ROW_STEP * PES_MATCH_SETTINGS_COUNT) {
    int index = (int)floorf((normalized_y - PES_MATCH_SETTINGS_ROW_Y) / PES_MATCH_SETTINGS_ROW_STEP);
    if (index < 0)
      index = 0;
    if (index >= (int)PES_MATCH_SETTINGS_COUNT)
      index = (int)PES_MATCH_SETTINGS_COUNT - 1;
    exhibition_popup_focus_index = (uint32_t)index;
    exhibition_popup_focus_direction = 0;
    pes_controller_menu_tap(normalized_x, normalized_y);
  }
  return 1;
}

void pes_controller_menu_physical_swipe(float start_x, float start_y,
                                         float end_x, float end_y) {
  if (!__atomic_load_n(&exhibition_team_picker_open, __ATOMIC_ACQUIRE))
    return;
  if (start_x < 0.225f || start_x > 0.800f || end_x < 0.225f ||
      end_x > 0.800f)
    return;
  const float dy = end_y - start_y;
  if (fabsf(dy) < 0.08f)
    return;

  if (__atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE)) {
    const uint32_t count = exhibition_custom_team_item_count();
    const uint32_t page_count =
        count ? (count + EXHIBITION_TEAM_GRID_PAGE_SIZE - 1) /
                    EXHIBITION_TEAM_GRID_PAGE_SIZE
              : 1;
    uint32_t page = exhibition_team_scroll_offset /
                    EXHIBITION_TEAM_GRID_PAGE_SIZE;
    if (dy < 0.0f && page + 1 < page_count)
      page++;
    else if (dy > 0.0f && page > 0)
      page--;
    else
      return;
    const uint32_t local = exhibition_popup_focus_index %
                           EXHIBITION_TEAM_GRID_PAGE_SIZE;
    exhibition_team_scroll_offset = page * EXHIBITION_TEAM_GRID_PAGE_SIZE;
    exhibition_popup_focus_index = exhibition_team_scroll_offset + local;
    if (exhibition_popup_focus_index >= count)
      exhibition_popup_focus_index = count - 1;
    exhibition_popup_focus_direction = 0;
    return;
  }

  // Native scrolling owns the content offset. Pin the custom focus to the
  // edge exposed by the gesture so it remains useful after large jumps.
  exhibition_popup_focus_index = dy < 0.0f ? 5u : 0u;
  exhibition_popup_focus_direction = 0;
  debugPrintf("exhibition: team list swipe dy=%.3f focus=%u\n", dy,
              exhibition_popup_focus_index);
}

static void exhibition_open_team_picker(void *window, uint32_t side) {
  if (!window || side >= 2 ||
      !__atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE))
    return;

  if (__atomic_exchange_n(&exhibition_team_picker_open, 1,
                          __ATOMIC_ACQ_REL))
    return;
  __atomic_store_n(&exhibition_nested_popup_open, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_nested_popup_kind, EXHIBITION_NESTED_NONE,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_nested_back_pending, 0, __ATOMIC_RELEASE);
  exhibition_popup_focus_index = 0;
  exhibition_popup_focus_direction = 0;
  exhibition_team_scroll_offset = 0;
  exhibition_team_category_index = 0;
  __atomic_store_n(&exhibition_custom_team_popup,
                   EXHIBITION_TEAM_POPUP_CATEGORY, __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_custom_popup_opened_ms,
                   exhibition_search_focus_now_ms(), __ATOMIC_RELEASE);

  const uint32_t selected_team =
      side == 0
          ? __atomic_load_n(&exhibition_home_team_id, __ATOMIC_ACQUIRE)
          : __atomic_load_n(&exhibition_away_team_id, __ATOMIC_ACQUIRE);
  __atomic_store_n(&exhibition_select_side, side, __ATOMIC_RELEASE);
  debugPrintf("exhibition: custom team browser side=%u current=%u "
              "categories=%u\n",
              side, selected_team, EXHIBITION_TEAM_CATEGORY_COUNT);
}

void pes_exhibition_search_touch(void *window, const void *touch_info) {
  if (!window || !touch_info ||
      !__atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE)) {
    if (exhibition_search_touch_original)
      exhibition_search_touch_original(window, touch_info);
    return;
  }
  if (__atomic_load_n(&exhibition_custom_team_popup, __ATOMIC_ACQUIRE) ||
      __atomic_load_n(&exhibition_cpu_level_popup_open, __ATOMIC_ACQUIRE) ||
      __atomic_load_n(&exhibition_settings_popup_open, __ATOMIC_ACQUIRE))
    return;

  uint32_t action = UINT32_MAX;
  uint32_t side = UINT32_MAX;
  memcpy(&action, (const unsigned char *)touch_info + 4, sizeof(action));
  memcpy(&side, (const unsigned char *)touch_info + 8, sizeof(side));
  if (action != 0 || side >= 2) {
    if (exhibition_search_touch_original)
      exhibition_search_touch_original(window, touch_info);
    return;
  }

  exhibition_open_team_picker(window, side);
}

void pes_exhibition_search_child(void *window, const void *child_name,
                                 uint32_t selected_value) {
  size_t length = 0;
  const char *name = exhibition_cobra_string_data(child_name, &length);
  if (!name)
    return;

  // A nested settings child is a visible Switch modal, not a completed
  // selection. Keep its custom focus alive across the native child callback;
  // the explicit B path clears it after the modal is dismissed.
  const int nested_popup =
      __atomic_load_n(&exhibition_nested_popup_open, __ATOMIC_ACQUIRE);

  static const char team_select_name[] = "menuTeamSelect";
  static const char cpu_level_name[] = "popupSelectCpuLevel";
  static const char match_setting_name[] = "menuMatchSetting";
  const int nested_back =
      __atomic_load_n(&exhibition_nested_back_pending, __ATOMIC_ACQUIRE);
  if (nested_back) {
    __atomic_store_n(&exhibition_nested_popup_open, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_nested_popup_kind, EXHIBITION_NESTED_NONE,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_nested_back_pending, 0, __ATOMIC_RELEASE);
    exhibition_popup_focus_index = 0;
    exhibition_popup_focus_direction = 0;
    // Native implementations may report the parent callback for a child
    // dismissal. Keep Match Settings open and release only nested focus.
    if (length == sizeof(match_setting_name) - 1 &&
        memcmp(name, match_setting_name, sizeof(match_setting_name) - 1) == 0) {
      debugPrintf("exhibition: nested Match Settings child dismissed by B\n");
      return;
    }
  }
  if (length == sizeof(team_select_name) - 1 &&
      memcmp(name, team_select_name, sizeof(team_select_name) - 1) == 0) {
    __atomic_store_n(&exhibition_nested_popup_open, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_nested_popup_kind, EXHIBITION_NESTED_NONE,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_nested_back_pending, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_custom_team_popup, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_team_picker_open, 0, __ATOMIC_RELEASE);
    exhibition_popup_focus_index = 0;
    if (selected_value != UINT32_MAX &&
        exhibition_is_valid_team(selected_value)) {
      const uint32_t side =
          __atomic_load_n(&exhibition_select_side, __ATOMIC_ACQUIRE);
      exhibition_select_team(side, selected_value);
      __atomic_store_n(&exhibition_plan_ready, 0, __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_search_refresh_pending, 1,
                       __ATOMIC_RELEASE);
      debugPrintf("exhibition: Matchmaking selected side=%u team=%u\n",
                  side, selected_value);
    }
    return;
  }

  if (length == sizeof(cpu_level_name) - 1 &&
      memcmp(name, cpu_level_name, sizeof(cpu_level_name) - 1) == 0) {
    __atomic_store_n(&exhibition_nested_popup_open, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_nested_popup_kind, EXHIBITION_NESTED_NONE,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_nested_back_pending, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_cpu_level_popup_open, 0,
                     __ATOMIC_RELEASE);
    exhibition_popup_focus_index = 0;
    if (selected_value != UINT32_MAX) {
      exhibition_apply_cpu_level(selected_value, NULL);
      debugPrintf("exhibition: COM level=%u\n", selected_value);
    }
    return;
  }

  if (length == sizeof(match_setting_name) - 1 &&
      memcmp(name, match_setting_name,
             sizeof(match_setting_name) - 1) == 0) {
    if (nested_popup) {
      debugPrintf("exhibition: kept nested Match Settings focus after "
                  "child callback value=%u\n",
                  selected_value);
      return;
    }
    __atomic_store_n(&exhibition_settings_popup_open, 0,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_nested_back_pending, 0, __ATOMIC_RELEASE);
    exhibition_set_matchmaking_visible(window, 1);
    debugPrintf("exhibition: Match Settings closed\n");
  }
}

void pes_exhibition_search_footer(void *window, uint32_t footer_key) {
  if (!__atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE)) {
    if (exhibition_search_footer_original)
      exhibition_search_footer_original(window, footer_key);
    return;
  }

  if (__atomic_load_n(&exhibition_team_picker_open, __ATOMIC_ACQUIRE) ||
      __atomic_load_n(&exhibition_cpu_level_popup_open, __ATOMIC_ACQUIRE) ||
      __atomic_load_n(&exhibition_settings_popup_open, __ATOMIC_ACQUIRE))
    return;

  if (footer_key == 0 && !exhibition_matchup_ready()) {
    debugPrintf("exhibition: ignored footer key=%u until both teams are "
                "selected\n",
                footer_key);
    return;
  }

  if (footer_key == 3) {
    exhibition_open_match_settings(window);
    return;
  }

  if (footer_key == 2) {
    exhibition_open_cpu_level();
    return;
  }

  void *listener = exhibition_flow_listener_instance
                       ? *exhibition_flow_listener_instance
                       : NULL;
  if (!listener || !exhibition_flow_direct_set)
    return;

  static const char strategy_flow[] = "MyClub/Match/MenuMatchMenu";
  static const char main_menu_flow[] = "MyClub/MainMenu/PreMainMenuCheck";
  // MatchSearching's native footer enum is RIGHT/Next=0 and LEFT/Back=1.
  // Keep that ordering even though the visual footer is laid out left-to-right.
  if (footer_key == 1) {
    __atomic_store_n(&exhibition_nested_popup_open, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_nested_popup_kind, EXHIBITION_NESTED_NONE,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_searching_active, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_team_select_active, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_session_active, 0, __ATOMIC_RELEASE);
    exhibition_flow_direct_set((unsigned char *)listener + 0x118,
                               main_menu_flow);
    debugPrintf("exhibition: Matchmaking Back -> %s\n", main_menu_flow);
    return;
  }

  if (footer_key == 0) {
    const uint32_t action = EXHIBITION_STRATEGY_START;
    __atomic_store_n(&exhibition_strategy_action, action, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_strategy_pending, 1, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_nested_popup_open, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_nested_popup_kind, EXHIBITION_NESTED_NONE,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_searching_active, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_team_select_active, 0, __ATOMIC_RELEASE);
    exhibition_flow_direct_set((unsigned char *)listener + 0x118,
                               strategy_flow);
    debugPrintf("exhibition: Proceed -> visible Strategy action=%u\n",
                action);
    return;
  }

  if (exhibition_search_footer_original)
    exhibition_search_footer_original(window, footer_key);
}

static void exhibition_make_short_string(unsigned char object[24],
                                          const char *text) {
  size_t length = text ? strlen(text) : 0;
  if (length > 23)
    length = 23;
  memset(object, 0, 24);
  object[0] = (unsigned char)(length << 1);
  if (length)
    memcpy(object + 1, text, length);
}

static void exhibition_set_matchmaking_visible(void *window,
                                                uint32_t visible) {
  if (!window || !exhibition_window_get_window ||
      !exhibition_node_set_visible)
    return;

  // Match Settings owns a separate fullscreen root. Hide the complete parent
  // page so none of its title or team-card layers can bleed through.
  void *root = exhibition_window_get_window(window);
  if (root)
    exhibition_node_set_visible(root, visible, 2);
}

static void exhibition_open_cpu_level(void) {
  if (!__atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE) ||
      __atomic_exchange_n(&exhibition_cpu_level_popup_open, 1,
                          __ATOMIC_ACQ_REL))
    return;

  uint32_t level = exhibition_get_test_match_cpu_level
                       ? exhibition_get_test_match_cpu_level()
                       : __atomic_load_n(&exhibition_cpu_level_value,
                                         __ATOMIC_ACQUIRE);
  if (level >= EXHIBITION_CPU_LEVEL_COUNT)
    level = 2;
  __atomic_store_n(&exhibition_cpu_level_value, level, __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_nested_popup_open, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_nested_popup_kind, EXHIBITION_NESTED_NONE,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_nested_back_pending, 0, __ATOMIC_RELEASE);
  exhibition_popup_focus_index = level;
  exhibition_popup_focus_direction = 0;
  __atomic_store_n(&exhibition_custom_popup_opened_ms,
                   exhibition_search_focus_now_ms(), __ATOMIC_RELEASE);
  debugPrintf("exhibition: opened custom COM Level current=%u\n", level);
}

static void exhibition_open_match_settings(void *window) {
  if (!window ||
      !__atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE))
    return;

  if (__atomic_exchange_n(&exhibition_settings_popup_open, 1,
                          __ATOMIC_ACQ_REL))
    return;
  __atomic_store_n(&exhibition_nested_popup_open, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_nested_popup_kind, EXHIBITION_NESTED_NONE,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_nested_back_pending, 0, __ATOMIC_RELEASE);
  exhibition_popup_focus_index = 0;
  exhibition_popup_focus_direction = 0;
  __atomic_store_n(&exhibition_custom_popup_opened_ms,
                   exhibition_search_focus_now_ms(), __ATOMIC_RELEASE);
  if (!exhibition_refresh_match_settings()) {
    __atomic_store_n(&exhibition_settings_popup_open, 0,
                     __ATOMIC_RELEASE);
    exhibition_settings_match = NULL;
    debugPrintf("exhibition: custom Match Settings missing tmpdb match\n");
    return;
  }
  debugPrintf("exhibition: opened custom Match Settings match=%p\n",
              exhibition_settings_match);
}

static void exhibition_update_search_task_record(void *task, uint32_t side,
                                                  uint32_t team_raw) {
  if (!task || side >= 2)
    return;

  unsigned char *record =
      (unsigned char *)task + 0x78 + side * 0x70;
  const int selected = exhibition_is_valid_team(team_raw);
  const uint32_t team_id = selected ? team_raw << 14 : 0;
  memcpy(record, &side, sizeof(side));
  memcpy(record + 8, &team_id, sizeof(team_id));
  exhibition_make_short_string(record + 16,
                               selected ? exhibition_team_name(team_raw) : "");
  exhibition_make_short_string(record + 40, side == 0 ? "HOME" : "COM");
}

static int exhibition_update_matching_record(void *window, uint32_t side,
                                              uint32_t team_raw) {
  if (!window || side >= 2)
    return 0;
  void *task = NULL;
  memcpy(&task, (unsigned char *)window + 544, sizeof(task));
  if (!task)
    return 0;

  exhibition_update_search_task_record(task, side, team_raw);
  return 1;
}

uintptr_t pes_exhibition_search_task_ready_entry(void *task) {
  if (task &&
      __atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE)) {
    exhibition_update_search_task_record(
        task, 0,
        __atomic_load_n(&exhibition_home_team_id, __ATOMIC_ACQUIRE));
    exhibition_update_search_task_record(
        task, 1,
        __atomic_load_n(&exhibition_away_team_id, __ATOMIC_ACQUIRE));
    __atomic_store_n(&exhibition_search_refresh_pending, 1,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_search_initial_refresh_ticks,
                     EXHIBITION_INITIAL_REFRESH_TICKS, __ATOMIC_RELEASE);
    debugPrintf("exhibition: preseeded Matchmaking task HOME=%u COM=%u\n",
                __atomic_load_n(&exhibition_home_team_id, __ATOMIC_ACQUIRE),
                __atomic_load_n(&exhibition_away_team_id, __ATOMIC_ACQUIRE));
  }
  return exhibition_search_task_ready_resume;
}

static void *exhibition_find_root_node(void *root, const char *name) {
  if (!root || !name)
    return NULL;
  void **vtable = NULL;
  memcpy(&vtable, root, sizeof(vtable));
  if (!vtable || !vtable[30])
    return NULL;
  return ((void *(*)(void *, const char *))vtable[30])(root, name);
}

static void exhibition_make_short_string(unsigned char object[24],
                                          const char *text);

static void main_menu_set_tile_text(void *tile, const char *title,
                                    const char *description) {
  if (!tile || !exhibition_text_set_string)
    return;

  unsigned char text[24];
  void *title_node = exhibition_find_root_node(tile, "textLarge_item");
  if (title_node) {
    exhibition_make_short_string(text, title);
    exhibition_text_set_string(title_node, text);
  }

  void *small_node = exhibition_find_root_node(tile, "textSmall_item");
  const int compact_tile = tile == main_menu_tiles[2] ||
                           tile == main_menu_tiles[3];
  if (small_node) {
    exhibition_make_short_string(text, compact_tile ? title : description);
    exhibition_text_set_string(small_node, text);
  }
  void *compact_title_node = exhibition_find_root_node(tile, "textLarge_sub");
  if (compact_title_node) {
    exhibition_make_short_string(text, compact_tile ? title : description);
    exhibition_text_set_string(compact_title_node, text);
  }
}

static void main_menu_apply_focus(uint32_t index) {
  if (index >= 4)
    return;
  main_menu_focus_index = index;
  int painted_any = 0;
  for (uint32_t i = 0; i < 4; i++) {
    void *tile = main_menu_tiles[i];
    if (!tile)
      continue;
    painted_any = 1;
    if (main_menu_choice_set_active)
      main_menu_choice_set_active(tile, 1, i == index, 2);
    const char *base_title = main_menu_titles[i];
    const char *base_description = main_menu_descriptions[i];
    // Keep the stock labels clean; focus is shown by the active tile tint.
    main_menu_set_tile_text(tile, base_title, base_description);
  }
  main_menu_focus_painted = painted_any;
}

static uint64_t main_menu_focus_now_ms(void) {
  return armTicksToNs(armGetSystemTick()) / 1000000ULL;
}

static void main_menu_video_apply(uint32_t index, uint32_t value) {
  value = value ? 1u : 0u;
  if (index == 0) {
    if (!main_menu_save_graphics_quality ||
        !main_menu_save_graphics_quality(value)) {
      debugPrintf("UE4 menu: failed to save graphics quality=%u\n", value);
      return;
    }
    __atomic_store_n(&main_menu_video_graphics, value, __ATOMIC_RELEASE);

    // This is the same runtime apply path used by the stock graphics page.
    // SaveData persists the choice, while UEBridge updates the live renderer.
    void *bridge = main_menu_get_ue_bridge ? main_menu_get_ue_bridge() : NULL;
    if (bridge) {
      void **vtable = *(void ***)bridge;
      if (vtable && vtable[47])
        ((void (*)(void *, uint32_t))vtable[47])(bridge, value);
    }
    debugPrintf("UE4 menu: custom video Graphics=%s saved\n",
                value ? "Standard" : "Low");
    return;
  }

  if (index == 1) {
    if (!main_menu_save_frame_rate || !main_menu_save_frame_rate(value)) {
      debugPrintf("UE4 menu: failed to save frame rate=%u\n", value);
      return;
    }
    if (main_menu_set_frame_rate_mode)
      main_menu_set_frame_rate_mode(value);

    // FrameRateController eventually mirrors Status to this console variable,
    // but issuing the same UE command here makes the selection effective in
    // the current main-menu frame as well.
    void *bridge = main_menu_get_ue_bridge ? main_menu_get_ue_bridge() : NULL;
    if (bridge) {
      void **vtable = *(void ***)bridge;
      if (vtable && vtable[2])
        ((void (*)(void *, const char *))vtable[2])(
            bridge, value == 0 ? "t.MaxFPS 60" : "t.MaxFPS 30");
    }
    __atomic_store_n(&main_menu_video_frame_rate, value, __ATOMIC_RELEASE);
    debugPrintf("UE4 menu: custom video Frame Rate=%s saved\n",
                value ? "30 FPS" : "60 FPS");
  }
}

static void main_menu_video_apply_current(void) {
  if (!__atomic_load_n(&main_menu_video_settings_open, __ATOMIC_ACQUIRE))
    return;
  main_menu_video_apply(
      0, __atomic_load_n(&main_menu_video_graphics, __ATOMIC_ACQUIRE));
  main_menu_video_apply(
      1, __atomic_load_n(&main_menu_video_frame_rate, __ATOMIC_ACQUIRE));
  debugPrintf("UE4 menu: custom video settings explicitly applied\n");
}

static void main_menu_video_adjust(int direction) {
  if (!direction ||
      !__atomic_load_n(&main_menu_video_settings_open, __ATOMIC_ACQUIRE))
    return;
  const uint32_t focus = main_menu_video_focus_index < 2
                             ? main_menu_video_focus_index
                             : 0;
  const uint32_t current =
      focus == 0
          ? __atomic_load_n(&main_menu_video_graphics, __ATOMIC_ACQUIRE)
          : __atomic_load_n(&main_menu_video_frame_rate, __ATOMIC_ACQUIRE);
  // Left/right select an absolute value, so holding an arrow can never make a
  // two-value row flicker. Direction 2 is the explicit A/tap toggle action.
  uint32_t value;
  if (direction == 2) {
    value = current ? 0u : 1u;
  } else if (focus == 1) {
    // FPS enum order is inverted: left=30 (1), right=60 (0).
    value = direction > 0 ? 0u : 1u;
  } else {
    value = direction > 0 ? 1u : 0u;
  }
  if (value != current)
    main_menu_video_apply(focus, value);
}

static void main_menu_video_open(void) {
  uint32_t graphics = main_menu_get_graphics_quality
                          ? main_menu_get_graphics_quality()
                          : 1u;
  if (graphics > 1)
    graphics = 1;

  // The active Status mode mirrors the persisted frame-rate selection. The
  // stock enum is 0 = 60 fps and 1 = 30 fps (2 is the unused 120 fps mode).
  uint32_t frame_rate = main_menu_get_frame_rate_mode
                            ? main_menu_get_frame_rate_mode()
                            : 0u;
  if (frame_rate > 1)
    frame_rate = 1;
  __atomic_store_n(&main_menu_video_graphics, graphics, __ATOMIC_RELEASE);
  __atomic_store_n(&main_menu_video_frame_rate, frame_rate,
                   __ATOMIC_RELEASE);
  main_menu_video_focus_index = 0;
  main_menu_video_focus_direction = 0;
  main_menu_video_apply_held = 0;
  __atomic_store_n(&main_menu_video_opened_ms, main_menu_focus_now_ms(),
                   __ATOMIC_RELEASE);
  __atomic_store_n(&main_menu_video_settings_open, 1, __ATOMIC_RELEASE);
  debugPrintf("UE4 menu: custom Video Settings opened graphics=%u fps=%u\n",
              graphics, frame_rate);
}

static void main_menu_video_close(void) {
  if (!__atomic_exchange_n(&main_menu_video_settings_open, 0,
                           __ATOMIC_ACQ_REL))
    return;
  main_menu_video_focus_index = 0;
  main_menu_video_focus_direction = 0;
  main_menu_video_apply_held = 0;
  __atomic_store_n(&main_menu_video_opened_ms, 0, __ATOMIC_RELEASE);
  main_menu_apply_focus(3);
  debugPrintf("UE4 menu: custom Video Settings closed\n");
}

static void main_menu_info_open(uint32_t popup) {
  if (popup != MAIN_MENU_INFO_CREDITS &&
      popup != MAIN_MENU_INFO_TWO_PLAYER)
    return;
  __atomic_store_n(&main_menu_info_popup, popup, __ATOMIC_RELEASE);
  __atomic_store_n(&main_menu_controller_active, 1, __ATOMIC_RELEASE);
  __atomic_store_n(&virtual_cursor_context, PES_VIRTUAL_CURSOR_NONE,
                   __ATOMIC_RELEASE);
  debugPrintf("UE4 menu: custom info opened type=%u\n", popup);
}

static void main_menu_info_close(void) {
  const uint32_t popup = __atomic_exchange_n(
      &main_menu_info_popup, MAIN_MENU_INFO_CLOSED, __ATOMIC_ACQ_REL);
  if (popup == MAIN_MENU_INFO_CLOSED)
    return;
  main_menu_apply_focus(popup == MAIN_MENU_INFO_CREDITS ? 1u : 2u);
  debugPrintf("UE4 menu: custom info closed type=%u\n", popup);
}

void pes_main_menu_pad_event(uint32_t buttons, uint32_t previous_buttons) {
  if (!__atomic_load_n(&main_menu_controller_active, __ATOMIC_ACQUIRE))
    return;

  // Do not let the first start-screen A fall through to tile zero when the
  // native main window is already constructed behind the launch prompt.
  if (pes_controller_start_prompt(NULL, NULL) &&
      (buttons & (1u << 1)) && !(previous_buttons & (1u << 1)))
    return;

  if (__atomic_load_n(&main_menu_info_popup, __ATOMIC_ACQUIRE) !=
      MAIN_MENU_INFO_CLOSED)
    return;

  if (__atomic_load_n(&main_menu_video_settings_open, __ATOMIC_ACQUIRE)) {
    const uint32_t apply_held = (buttons & (1u << 3)) != 0;
    if (apply_held) {
      if (!main_menu_video_apply_held)
        main_menu_video_apply_current();
      main_menu_video_apply_held = 1;
      main_menu_video_focus_direction = 0;
      return;
    }
    main_menu_video_apply_held = 0;

    uint32_t direction = 0;
    if (buttons & (1u << 10))
      direction = 1;
    else if (buttons & (1u << 11))
      direction = 2;
    else if (buttons & (1u << 12))
      direction = 3;
    else if (buttons & (1u << 13))
      direction = 4;
    const uint64_t now = main_menu_focus_now_ms();
    if (!direction) {
      main_menu_video_focus_direction = 0;
      return;
    }
    // Custom-overlay buttons are deliberately removed from native pad state,
    // so the game's previous_buttons cannot be used for edge detection here.
    const int pressed = direction != main_menu_video_focus_direction;
    if (direction != main_menu_video_focus_direction) {
      main_menu_video_focus_direction = direction;
      main_menu_video_focus_started_ms = now;
      main_menu_video_focus_repeat_ms = now;
    } else if (!pressed && now - main_menu_video_focus_started_ms < 300) {
      return;
    } else if (!pressed && now - main_menu_video_focus_repeat_ms < 120) {
      return;
    }
    main_menu_video_focus_repeat_ms = now;
    if (direction == 1 && main_menu_video_focus_index > 0)
      main_menu_video_focus_index--;
    else if (direction == 2 && main_menu_video_focus_index < 1)
      main_menu_video_focus_index++;
    else if (direction == 3 || direction == 4)
      main_menu_video_adjust(direction == 3 ? -1 : 1);
    return;
  }

  if (!main_menu_focus_painted)
    main_menu_apply_focus(main_menu_focus_index);

  uint32_t direction = 0;
  if (buttons & (1u << 10))
    direction = 1; // up
  else if (buttons & (1u << 11))
    direction = 2; // down
  else if (buttons & (1u << 12))
    direction = 3; // left
  else if (buttons & (1u << 13))
    direction = 4; // right

  const uint64_t now = main_menu_focus_now_ms();
  if (!direction) {
    main_menu_focus_direction = 0;
    return;
  }

  const int pressed = (buttons & (1u << (direction + 9))) != 0 &&
                      !(previous_buttons & (1u << (direction + 9)));
  if (direction != main_menu_focus_direction) {
    main_menu_focus_direction = direction;
    main_menu_focus_started_ms = now;
    main_menu_focus_repeat_ms = now;
  } else if (!pressed && now - main_menu_focus_started_ms < 300) {
    return;
  } else if (!pressed && now - main_menu_focus_repeat_ms < 120) {
    return;
  }

  main_menu_focus_repeat_ms = now;
  uint32_t next = main_menu_focus_index;
  if (direction == 1 && next >= 2)
    next -= 2;
  else if (direction == 2 && next < 2)
    next += 2;
  else if (direction == 3 && (next & 1))
    next--;
  else if (direction == 4 && !(next & 1))
    next++;
  if (next != main_menu_focus_index)
    main_menu_apply_focus(next);
}

void pes_main_menu_simplify(void *window) {
  static int logged;
  main_menu_match_page = NULL;
  if (!window || !exhibition_window_get_window ||
      !exhibition_node_set_visible)
    return;

  __atomic_store_n(&main_menu_graphics_active, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_gamepad_lab_active, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_gamepad_lab_autostart, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&main_menu_info_popup, MAIN_MENU_INFO_CLOSED,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&main_menu_controller_active, 1, __ATOMIC_RELEASE);
  __atomic_store_n(&virtual_cursor_context, PES_VIRTUAL_CURSOR_NONE,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_match_settings_armed, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_postmatch_custom_active, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_postmatch_custom_action, 0, __ATOMIC_RELEASE);
  match_postmatch_window = NULL;

  void *root = exhibition_window_get_window(window);
  if (!root)
    return;

  // Keep the stock 2x2 Match grid and relabel all four choices. Exhibition
  // retains its proven handler; tile 2 is an isolated single-player lab.
  void *tab_strip = exhibition_find_root_node(root, "p_tab");
  void *match_page = exhibition_find_root_node(root, "page_0");
  main_menu_match_page = match_page;
  if (tab_strip)
    exhibition_node_set_visible(tab_strip, 0, 2);
  if (match_page) {
    void *tiles[4] = {0};
    main_menu_focus_painted = 0;
    for (uint32_t i = 0; i < 4; i++) {
      char choice_name[] = "choice_0";
      choice_name[7] = (char)('0' + i);
      tiles[i] = exhibition_find_root_node(match_page, choice_name);
      main_menu_tiles[i] = tiles[i];
      if (tiles[i]) {
        exhibition_node_set_visible(tiles[i], 1, 2);
      }
    }
    main_menu_apply_focus(0);
  }

  for (uint32_t i = 1; i < 4; i++) {
    char page_name[] = "page_0";
    page_name[5] = (char)('0' + i);
    void *page = exhibition_find_root_node(root, page_name);
    if (page)
      exhibition_node_set_visible(page, 0, 2);
  }

  // The unused pages are no longer constructed and swipe navigation is
  // disabled, so always leave the menu on its Match page.
  *(uint32_t *)((unsigned char *)window + 532) = 0;
  if (!logged) {
    debugPrintf("UE4 menu: four-tile mode active "
                "root=%p page=%p\n",
                root, match_page);
    logged = 1;
  }
}

uintptr_t pes_main_menu_selected_entry(void *window,
                                       const void *touch_info) {
  if (!window || !touch_info)
    return main_menu_selected_resume;

  uint32_t choice = UINT32_MAX;
  memcpy(&choice, (const unsigned char *)touch_info + 8, sizeof(choice));
  if (choice == 0) {
    __atomic_store_n(&main_menu_controller_active, 0, __ATOMIC_RELEASE);
    return main_menu_selected_resume;
  }

  if (choice == 1) {
    main_menu_info_open(MAIN_MENU_INFO_CREDITS);
    return 0;
  }

  if (choice == 2) {
    // Use the same TutorialMatch bootstrap as local Exhibition, but do not
    // mutate the const native touch event or execute tile zero's handler.
    // This DirectSet and every native-input flag remain scoped to tile 2.
    void *listener = exhibition_flow_listener_instance
                         ? *exhibition_flow_listener_instance
                         : NULL;
    if (!listener || !exhibition_flow_direct_set)
      return 0;
    static const char tutorial_flow[] = "MyClub/TutorialMatch";
    native_pad_lab_reset();
    __atomic_store_n(&native_gamepad_lab_active, 1, __ATOMIC_RELEASE);
    __atomic_store_n(&native_gamepad_lab_autostart, 1, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_requested, 1, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_session_active, 1, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_searching_active, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_team_select_active, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_home_team_id, 108, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_away_team_id, 114, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_plan_ready, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&main_menu_controller_active, 0, __ATOMIC_RELEASE);
    exhibition_flow_direct_set((unsigned char *)listener + 0x118,
                               tutorial_flow);
    debugPrintf("native gamepad lab: armed Barcelona(108) vs PSG(114), "
                "single player\n");
    return 0;
  }

  if (choice == 3) {
    main_menu_video_open();
    __atomic_store_n(&main_menu_controller_active, 1, __ATOMIC_RELEASE);
    __atomic_store_n(&virtual_cursor_context, PES_VIRTUAL_CURSOR_NONE,
                     __ATOMIC_RELEASE);
    return 0;
  }
  return main_menu_selected_resume;
}

static void *exhibition_find_holder_node(void *holder, const char *name) {
  if (!holder || !name)
    return NULL;
  void **vtable = NULL;
  memcpy(&vtable, holder, sizeof(vtable));
  if (!vtable || !vtable[2])
    return NULL;
  return ((void *(*)(void *, const char *))vtable[2])(holder, name);
}

static void exhibition_update_matchmaking_card(void *window, uint32_t side,
                                                uint32_t team_raw) {
  if (!window || side >= 2 || !exhibition_window_get_window ||
      !exhibition_holder_get_duplicate || !exhibition_node_set_visible ||
      !exhibition_text_set_string || !exhibition_emblem_set_team)
    return;

  void *root = exhibition_window_get_window(window);
  void *team_info = exhibition_find_root_node(root, "p_teamInfo");
  if (!team_info)
    return;
  void *card = exhibition_holder_get_duplicate(
      (unsigned char *)team_info + 0x90, side);
  if (!card)
    return;

  exhibition_node_set_visible(card, 1, 2);
  void *holder = (unsigned char *)card + 0x90;
  void *emblem = exhibition_find_holder_node(holder, "headline_emblem");
  void *team_name =
      exhibition_find_holder_node(holder, "headline_teamName");
  void *sub_name = exhibition_find_holder_node(holder, "userName");
  void *points = exhibition_find_holder_node(holder, "numInfo_value");
  if (emblem) {
    const int selected = exhibition_is_valid_team(team_raw);
    exhibition_node_set_visible(emblem, selected, 2);
    if (selected) {
      const uint32_t team_id = team_raw << 14;
      exhibition_emblem_set_team(emblem, &team_id, 0, 5, 0, 0);
    }
  }

  unsigned char text[24];
  if (team_name) {
    const int selected = exhibition_is_valid_team(team_raw);
    exhibition_node_set_visible(team_name, selected, 2);
    if (selected) {
      exhibition_make_short_string(text, exhibition_team_name(team_raw));
      exhibition_text_set_string(team_name, text);
    }
  }
  if (sub_name) {
    exhibition_make_short_string(text, side == 0 ? "HOME" : "COM");
    exhibition_text_set_string(sub_name, text);
  }
  if (points)
    exhibition_node_set_visible(points, 0, 2);
}

uintptr_t pes_exhibition_search_post_entry(void *window) {
  if (window &&
      __atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE)) {
    exhibition_search_window = window;
    if (exhibition_search_focus_index >= 6)
      exhibition_search_focus_index = 0;
  }
  int matching_records_ready = 0;
  if (window &&
      __atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE)) {
    const int home_record_ready = exhibition_update_matching_record(
        window, 0,
        __atomic_load_n(&exhibition_home_team_id, __ATOMIC_ACQUIRE));
    const int away_record_ready = exhibition_update_matching_record(
        window, 1,
        __atomic_load_n(&exhibition_away_team_id, __ATOMIC_ACQUIRE));
    matching_records_ready = home_record_ready && away_record_ready;
  }
  if (exhibition_search_update_disp)
    exhibition_search_update_disp(window);

  if (window &&
      __atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE)) {
    const uint32_t matchup_ready = exhibition_matchup_ready();
    const uint32_t touch_request =
        __atomic_exchange_n(&exhibition_search_touch_pending, 0,
                            __ATOMIC_ACQ_REL);
    if (touch_request >= 1 && touch_request <= 2)
      exhibition_open_team_picker(window, touch_request - 1);

    const int explicit_refresh =
        matching_records_ready &&
        __atomic_exchange_n(&exhibition_search_refresh_pending, 0,
                            __ATOMIC_ACQ_REL);
    int initial_refresh = 0;
    if (matching_records_ready && !matchup_ready) {
      const uint32_t ticks = __atomic_load_n(
          &exhibition_search_initial_refresh_ticks, __ATOMIC_ACQUIRE);
      if (ticks) {
        initial_refresh = ticks % 15u == 0;
        __atomic_store_n(&exhibition_search_initial_refresh_ticks, ticks - 1,
                         __ATOMIC_RELEASE);
      }
    } else if (matchup_ready) {
      __atomic_store_n(&exhibition_search_initial_refresh_ticks, 0,
                       __ATOMIC_RELEASE);
    }
    if (explicit_refresh || initial_refresh) {
      if (explicit_refresh)
        exhibition_refresh_selected_tmpdb();
      if (exhibition_search_update_team_info) {
        const uint32_t home = 0;
        const uint32_t away = 1;
        exhibition_search_update_team_info(window, &home);
        exhibition_search_update_team_info(window, &away);
      }
    }
    for (uint32_t key = 0; key < 4; key++) {
      if (exhibition_set_pad_key_kind)
        exhibition_set_pad_key_kind(window, key, 1);
      if (exhibition_set_pad_key_active)
        exhibition_set_pad_key_active(
            window, key, key == 0 ? matchup_ready : 1);
    }
    if (exhibition_set_pad_key_string) {
      // Wrapper-private sentinel resolved by pes_exhibition_string_get_target.
      // This keeps the stock layout while making the action unambiguous.
      exhibition_set_pad_key_string(window, 0, 0x7fff0001);
      exhibition_set_pad_key_string(window, 2, 0x045e00a4);
      exhibition_set_pad_key_string(window, 3, 0x01f9003d);
    }
    exhibition_update_matchmaking_card(
        window, 0,
        __atomic_load_n(&exhibition_home_team_id, __ATOMIC_ACQUIRE));
    exhibition_update_matchmaking_card(
        window, 1,
        __atomic_load_n(&exhibition_away_team_id, __ATOMIC_ACQUIRE));
    exhibition_search_focus_apply(window);
  }
  return exhibition_search_post_resume;
}

// TaskMatchSearchingTraining assumes a fully initialized MyClubUserInfo even
// in its local Training mode. The offline Exhibition bootstrap intentionally
// has no server-backed profile, so GetUserInfo can return null here. Supply a
// valid cobra short string only for the Exhibition session; all stock flows
// continue through the original getter.
uintptr_t pes_exhibition_search_user_name(void *user_info,
                                           const void **name_out) {
  static const _Alignas(8) unsigned char local_name[24] = {
      12, 'P', 'E', 'S', ' ', 'N', 'X', 0,
  };
  const void *name = NULL;
  if (__atomic_load_n(&exhibition_session_active, __ATOMIC_ACQUIRE) ||
      !user_info) {
    name = local_name;
  } else if (exhibition_user_info_get_name) {
    name = exhibition_user_info_get_name(user_info);
  }
  if (!name)
    name = local_name;
  if (name_out)
    *name_out = name;
  return exhibition_search_user_name_resume;
}

uintptr_t pes_exhibition_filter_teams_entry(void *selector,
                                            void *team_vector) {
  (void)selector;
  if (team_vector &&
      __atomic_load_n(&exhibition_team_select_active, __ATOMIC_ACQUIRE)) {
    uint32_t *begin = NULL;
    uint32_t *end = NULL;
    memcpy(&begin, team_vector, sizeof(begin));
    memcpy(&end, (unsigned char *)team_vector + 8, sizeof(end));
    if (begin && end && end >= begin && (size_t)(end - begin) < (1u << 20)) {
      uint32_t *out = begin;
      for (uint32_t *it = begin; it != end; ++it) {
        const uint32_t encoded = *it;
        const uint32_t raw = encoded >> 14;
        if (exhibition_is_valid_team(raw))
          *out++ = encoded;
      }
      memcpy((unsigned char *)team_vector + 8, &out, sizeof(out));
    }
  }
  return exhibition_filter_teams_resume;
}

// MyClubFlowMatchMenu's constructor creates matchPlan::Data in mode 2 and
// imports tmpdb::Match. Some mobile/tutorial configurations leave that tmpdb
// object empty even though the selected master TeamIds are valid. Build both
// sides directly from CommonWork here, before Strategy's state-0 loader runs,
// then publish the complete plan back to tmpdb::Match for MatchSetup.
uintptr_t pes_exhibition_strategy_main_entry(void *strategy_flow) {
  if (strategy_flow &&
      __atomic_load_n(&exhibition_strategy_pending, __ATOMIC_ACQUIRE)) {
    uint32_t state;
    memcpy(&state, (unsigned char *)strategy_flow + 540, sizeof(state));
    if (state == 0 &&
        __atomic_exchange_n(&exhibition_strategy_pending, 0,
                            __ATOMIC_ACQ_REL)) {
      __atomic_store_n(&virtual_cursor_context, PES_VIRTUAL_CURSOR_NONE,
                       __ATOMIC_RELEASE);
      const uint32_t action = __atomic_load_n(
          &exhibition_strategy_action, __ATOMIC_ACQUIRE);
      const int reuse_plan =
          action == EXHIBITION_STRATEGY_START &&
          __atomic_load_n(&exhibition_plan_ready, __ATOMIC_ACQUIRE);
      if (!reuse_plan) {
        void *data = exhibition_matchplan_get_instance
                         ? exhibition_matchplan_get_instance()
                         : NULL;
        if (data && exhibition_set_team &&
            exhibition_matchplan_setup_tmpdb) {
        uint32_t home_raw =
            __atomic_load_n(&exhibition_home_team_id, __ATOMIC_ACQUIRE);
        uint32_t away_raw =
            __atomic_load_n(&exhibition_away_team_id, __ATOMIC_ACQUIRE);
        const ExhibitionMasterRoster *home_roster =
            exhibition_find_roster(home_raw);
        const ExhibitionMasterRoster *away_roster =
            exhibition_find_roster(away_raw);
        if (!home_roster || !away_roster) {
          debugPrintf("exhibition: invalid selected matchup home=%u away=%u; "
                      "falling back to %uv%u\n",
                      home_raw, away_raw, EXHIBITION_FALLBACK_HOME_TEAM,
                      EXHIBITION_FALLBACK_AWAY_TEAM);
          home_raw = EXHIBITION_FALLBACK_HOME_TEAM;
          away_raw = EXHIBITION_FALLBACK_AWAY_TEAM;
          home_roster = exhibition_find_roster(home_raw);
          away_roster = exhibition_find_roster(away_raw);
        }
        const uint32_t home_team_id = home_raw << 14;
        const uint32_t away_team_id = away_raw << 14;
        uint32_t data_mode;
        memcpy(&data_mode, (unsigned char *)data + 8, sizeof(data_mode));

        void *manager = exhibition_tmpdb_manager_get_instance
                            ? exhibition_tmpdb_manager_get_instance()
                            : NULL;
        void *common_work = NULL;
        if (manager)
          memcpy(&common_work, (unsigned char *)manager + 64,
                 sizeof(common_work));
        const uint32_t home_count = exhibition_install_master_roster(
            common_work, &home_team_id, home_roster);
        const uint32_t away_count = exhibition_install_master_roster(
            common_work, &away_team_id, away_roster);

        // TutorialMatch called SetExhibitionTeam before the mobile master
        // Team records had member arrays, so tmpdb::Match still contains two
        // empty squads. Re-run the same stock importer now that the authentic
        // PlayerAssignment rosters are installed. Then rebuild matchPlan from
        // tmpdb exactly as MyClubFlowMatchMenu's constructor normally does.
        // This populates the badge, coach, formation and tmpdb Player objects
        // consumed by MyClubSquadEdit, not merely matchPlan's local team copy.
        exhibition_set_team(&home_team_id, 0, 0);
        exhibition_set_team(&away_team_id, 1, 0);

        // Verify the exact tmpdb::Match objects consumed by
        // SetupDataFromTmpdbMatch. This distinguishes a failed master-team
        // import from a later matchPlan/UI reset without relying on what the
        // screen happens to render.
        unsigned char *tmpdb_match = NULL;
        if (manager) {
          void *tmpdb_data = NULL;
          memcpy(&tmpdb_data, (unsigned char *)manager + 72,
                 sizeof(tmpdb_data));
          if (tmpdb_data)
            tmpdb_match = (unsigned char *)tmpdb_data + 0x4b38;
        }
        exhibition_apply_cpu_level(
            __atomic_load_n(&exhibition_cpu_level_value, __ATOMIC_ACQUIRE),
            tmpdb_match);
        exhibition_apply_match_settings(tmpdb_match);
        exhibition_refresh_uniforms(tmpdb_match, &home_team_id,
                                     &away_team_id);

        // The MyClub Strategy loader immediately returns without creating a
        // SquadData when UtilityCommon::GetMatchMySide() is NONE (2). The
        // tutorial team initializer assigns clubs but does not associate the
        // local account with either side. Bind the current account to HOME so
        // the stock loader consumes the complete matchPlan we just built;
        // AWAY remains the CPU side.
        uint32_t local_user_id = 0;
        void *online_parameter = exhibition_online_parameter_get_instance
                                     ? exhibition_online_parameter_get_instance()
                                     : NULL;
        void *parameter_common = NULL;
        if (online_parameter)
          memcpy(&parameter_common, (unsigned char *)online_parameter + 8,
                 sizeof(parameter_common));
        if (parameter_common && exhibition_parameter_common_get_user_id)
          local_user_id =
              exhibition_parameter_common_get_user_id(parameter_common);
        if (tmpdb_match && exhibition_tmpdb_match_set_user_id)
          exhibition_tmpdb_match_set_user_id(tmpdb_match, 0, local_user_id);
        const uint32_t match_my_side = exhibition_get_match_my_side
                                           ? exhibition_get_match_my_side()
                                           : UINT32_MAX;
        debugPrintf("exhibition: local user=%u assigned HOME mySide=%u "
                    "match=%p parameter=%p common=%p\n",
                    local_user_id, match_my_side, tmpdb_match,
                    online_parameter, parameter_common);

        for (uint32_t side = 0; side < 2; side++) {
          unsigned char *match_team =
              (tmpdb_match && exhibition_tmpdb_match_get_team)
                  ? exhibition_tmpdb_match_get_team(tmpdb_match, &side)
                  : NULL;
          uint32_t match_team_id = 0;
          uint32_t match_flags = 0;
          uint64_t first_player_id = 0;
          if (match_team) {
            memcpy(&match_team_id, match_team, sizeof(match_team_id));
            memcpy(&first_player_id, match_team + 272,
                   sizeof(first_player_id));
            memcpy(&match_flags, match_team + 0x3a6,
                   sizeof(match_flags));
          }
          debugPrintf("exhibition: tmpdb side=%u team=0x%x count=%u "
                      "first=0x%llx ptr=%p\n",
                      side, match_team_id, (match_flags >> 9) & 0x7f,
                      (unsigned long long)first_player_id, match_team);
        }

        const uint32_t strategy_mode = 2;
        memcpy((unsigned char *)data + 8, &strategy_mode,
               sizeof(strategy_mode));
        exhibition_matchplan_setup_tmpdb(data);
        // SetupDataFromTmpdbMatch can copy the match record back over fields
        // written above, so apply the selected level once more afterwards.
        exhibition_apply_cpu_level(
            __atomic_load_n(&exhibition_cpu_level_value, __ATOMIC_ACQUIRE),
            tmpdb_match);
        exhibition_apply_match_settings(tmpdb_match);

        uint32_t plan_team_ids[2] = {0, 0};
        uint32_t plan_counts[2] = {0, 0};
        uint32_t plan_player_ptrs[2] = {0, 0};
        void *plan_first_players[2] = {NULL, NULL};
        for (uint32_t side = 0; side < 2; side++) {
          unsigned char *side_info = (unsigned char *)data + side * 0x218;
          plan_counts[side] = side_info[20];
          memcpy(&plan_team_ids[side],
                 (unsigned char *)data + 0x1048 + side * 4,
                 sizeof(plan_team_ids[side]));
          for (uint32_t member = 0; member < 40; member++) {
            void *player = NULL;
            memcpy(&player,
                   (unsigned char *)data + 0x508 + side * 0x340 +
                       member * 16,
                   sizeof(player));
            if (player) {
              plan_player_ptrs[side]++;
              if (!plan_first_players[side])
                plan_first_players[side] = player;
            }
          }
        }
          __atomic_store_n(&exhibition_plan_ready, 1, __ATOMIC_RELEASE);
          debugPrintf("exhibition: Strategy seeded matchPlan=%p "
                    "teams=%uv%u players=%uv%u old_mode=%u plan="
                    "0x%x/%u/%u/%p vs 0x%x/%u/%u/%p via refreshed "
                    "tmpdb::Match\n",
                    data, home_raw, away_raw, home_count, away_count,
                    data_mode,
                    plan_team_ids[0], plan_counts[0], plan_player_ptrs[0],
                    plan_first_players[0], plan_team_ids[1], plan_counts[1],
                    plan_player_ptrs[1], plan_first_players[1]);
        } else {
          debugPrintf("exhibition: Strategy seed unavailable data=%p get=%p "
                      "setTeam=%p setupTmpdb=%p\n",
                      data, exhibition_matchplan_get_instance,
                      exhibition_set_team,
                      exhibition_matchplan_setup_tmpdb);
        }
      } else {
        exhibition_apply_cpu_level(
            __atomic_load_n(&exhibition_cpu_level_value, __ATOMIC_ACQUIRE),
            NULL);
        exhibition_apply_match_settings(NULL);
        debugPrintf("exhibition: reusing edited match plan for start\n");
      }

      if (action == EXHIBITION_STRATEGY_START &&
          __atomic_load_n(&exhibition_plan_ready, __ATOMIC_ACQUIRE))
        debugPrintf("exhibition: match plan ready; showing Strategy before "
                    "Play\n");
    }
  }
  return exhibition_strategy_main_resume;
}

// Intercept the exact state-0 exit after MyClubSquadEdit::CreateObject. Register
// the Strategy child normally, then leave it in state 1 so the player can edit
// the plan and explicitly choose Play.
uintptr_t pes_exhibition_strategy_created_entry(void *strategy_flow,
                                                void *squad_edit) {
  uint32_t state = squad_edit ? 1u : 2u;
  if (strategy_flow && squad_edit && exhibition_task_add_unit)
    exhibition_task_add_unit(strategy_flow, squad_edit);
  if (strategy_flow)
    memcpy((unsigned char *)strategy_flow + 540, &state, sizeof(state));

  if (strategy_flow && squad_edit &&
      __atomic_load_n(&exhibition_session_active, __ATOMIC_ACQUIRE) &&
      __atomic_load_n(&exhibition_plan_ready, __ATOMIC_ACQUIRE))
    exhibition_refresh_squad_player_stats();

  const int native_active = strategy_flow && squad_edit;
  __atomic_store_n(&exhibition_gameplan_custom_active, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_gameplan_custom_page,
                   EXHIBITION_GAMEPLAN_PAGE_ROOT, __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_gameplan_custom_focus, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_gameplan_custom_action, 0,
                   __ATOMIC_RELEASE);
  if (native_active) {
    __atomic_store_n(&match_gameplan_seen_tick, armGetSystemTick(),
                     __ATOMIC_RELEASE);
    pes_virtual_cursor_activate(PES_VIRTUAL_CURSOR_GAMEPLAN, 32768, 29491);
    debugPrintf("exhibition: native pre-match Game Plan opened window=%p\n",
                squad_edit);
  }

  return exhibition_strategy_created_resume;
}

int pes_controller_custom_prematch_gameplan_active(void) {
  return __atomic_load_n(&exhibition_gameplan_custom_active,
                         __ATOMIC_ACQUIRE) != 0;
}

void pes_controller_custom_prematch_gameplan_input(uint32_t action) {
  if (pes_controller_custom_prematch_gameplan_active() && action)
    __atomic_store_n(&exhibition_gameplan_custom_action, action,
                     __ATOMIC_RELEASE);
}

static void exhibition_gameplan_process_input(void *window) {
  const uint32_t action = __atomic_exchange_n(
      &exhibition_gameplan_custom_action, 0, __ATOMIC_ACQ_REL);
  if (!action || !window)
    return;

  const uint32_t page = __atomic_load_n(
      &exhibition_gameplan_custom_page, __ATOMIC_ACQUIRE);
  if (page == EXHIBITION_GAMEPLAN_PAGE_ROOT) {
    uint32_t focus = __atomic_load_n(&exhibition_gameplan_custom_focus,
                                     __ATOMIC_ACQUIRE);
    if (focus >= 5)
      focus = 0;
    if (action == PES_PAUSE_INPUT_UP) {
      focus = focus ? focus - 1 : 4;
      __atomic_store_n(&exhibition_gameplan_custom_focus, focus,
                       __ATOMIC_RELEASE);
    } else if (action == PES_PAUSE_INPUT_DOWN) {
      __atomic_store_n(&exhibition_gameplan_custom_focus,
                       (focus + 1) % 5, __ATOMIC_RELEASE);
    } else if ((action == PES_PAUSE_INPUT_LEFT ||
                action == PES_PAUSE_INPUT_RIGHT) &&
               (focus == 2 || focus == 3)) {
      exhibition_gameplan_change_uniform(
          focus - 2, action == PES_PAUSE_INPUT_RIGHT ? 1 : -1);
    } else if (action == PES_PAUSE_INPUT_BACK) {
      __atomic_store_n(&exhibition_gameplan_custom_active, 0,
                       __ATOMIC_RELEASE);
      pes_exhibition_strategy_footer(window, 1);
    } else if (action == PES_PAUSE_INPUT_DECIDE) {
      if (focus == 0) {
        match_gameplan_focus = 0;
        __atomic_store_n(&exhibition_gameplan_custom_page,
                         EXHIBITION_GAMEPLAN_PAGE_SUBSTITUTION,
                         __ATOMIC_RELEASE);
      } else if (focus == 1) {
        match_gameplan_focus = 0;
        __atomic_store_n(&exhibition_gameplan_custom_page,
                         EXHIBITION_GAMEPLAN_PAGE_FORMATION,
                         __ATOMIC_RELEASE);
      } else if (focus == 2 || focus == 3) {
        exhibition_gameplan_change_uniform(focus - 2, 1);
      } else {
        __atomic_store_n(&exhibition_gameplan_custom_active, 0,
                         __ATOMIC_RELEASE);
        pes_exhibition_strategy_footer(window, 0);
      }
    }
    return;
  }

  if (page == EXHIBITION_GAMEPLAN_PAGE_SUBSTITUTION) {
    const uint32_t focus = match_gameplan_focus & 1u;
    if (action == PES_PAUSE_INPUT_UP || action == PES_PAUSE_INPUT_DOWN) {
      match_gameplan_focus = focus ^ 1u;
    } else if (action == PES_PAUSE_INPUT_LEFT ||
               action == PES_PAUSE_INPUT_RIGHT) {
      const int direction = action == PES_PAUSE_INPUT_RIGHT ? 1 : -1;
      uint32_t *selection = focus == 0 ? &match_gameplan_starter_index
                                       : &match_gameplan_bench_index;
      const uint32_t count = focus == 0 ? match_gameplan_starter_count
                                         : match_gameplan_bench_count;
      if (count)
        *selection = direction > 0 ? (*selection + 1) % count
                                   : (*selection ? *selection - 1
                                                 : count - 1);
    } else if (action == PES_PAUSE_INPUT_DECIDE) {
      match_gameplan_swap_selected();
    } else if (action == PES_PAUSE_INPUT_BACK) {
      match_gameplan_focus = 0;
      __atomic_store_n(&exhibition_gameplan_custom_focus, 0,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_gameplan_custom_page,
                       EXHIBITION_GAMEPLAN_PAGE_ROOT, __ATOMIC_RELEASE);
    }
    return;
  }

  if (page == EXHIBITION_GAMEPLAN_PAGE_FORMATION) {
    if (action == PES_PAUSE_INPUT_LEFT ||
        action == PES_PAUSE_INPUT_RIGHT) {
      match_gameplan_tactics ^= 1u;
    } else if (action == PES_PAUSE_INPUT_DECIDE) {
      if (match_gameplan_squad_data && match_squad_data_set_tactics) {
        match_squad_data_set_tactics(match_gameplan_squad_data,
                                      match_gameplan_tactics);
        if (matchplan_squad_save)
          matchplan_squad_save();
      }
    } else if (action == PES_PAUSE_INPUT_BACK) {
      match_gameplan_focus = 0;
      __atomic_store_n(&exhibition_gameplan_custom_focus, 1,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&exhibition_gameplan_custom_page,
                       EXHIBITION_GAMEPLAN_PAGE_ROOT, __ATOMIC_RELEASE);
    }
  }
}

static uint32_t pes_exhibition_strategy_update(void *window,
                                               uint32_t pad_status) {
  const uint32_t result = exhibition_strategy_update_original
                              ? exhibition_strategy_update_original(
                                    window, pad_status)
                              : 0;

  if (window && pes_controller_native_pad_lab_active() &&
      __atomic_load_n(&exhibition_plan_ready, __ATOMIC_ACQUIRE) &&
      __atomic_exchange_n(&native_gamepad_lab_autostart, 0,
                          __ATOMIC_ACQ_REL)) {
    debugPrintf("native gamepad lab: auto Play from prepared Strategy\n");
    pes_exhibition_strategy_footer(window, 0);
  }

  if (window && exhibition_set_pad_key_string &&
      __atomic_load_n(&exhibition_session_active, __ATOMIC_ACQUIRE) &&
      __atomic_load_n(&exhibition_strategy_action, __ATOMIC_ACQUIRE) ==
          EXHIBITION_STRATEGY_START)
    exhibition_set_pad_key_string(window, 0, 0x7fff0002);

  if (window && pes_controller_custom_prematch_gameplan_active()) {
    exhibition_gameplan_process_input(window);
  }

  return result;
}

static void pes_exhibition_strategy_footer(void *window,
                                           uint32_t footer_key) {
  const int starting_match =
      __atomic_load_n(&exhibition_session_active, __ATOMIC_ACQUIRE) &&
      __atomic_load_n(&exhibition_strategy_action, __ATOMIC_ACQUIRE) ==
          EXHIBITION_STRATEGY_START;

  // Back reuses the proven editor-return trampoline; Play stays on the stock
  // Strategy proceed path and enters MatchSetup normally.
  if (starting_match && footer_key == 1)
    __atomic_store_n(&exhibition_strategy_action,
                     EXHIBITION_STRATEGY_EDIT, __ATOMIC_RELEASE);

  if (starting_match && footer_key == 0) {
    exhibition_apply_cpu_level(
        __atomic_load_n(&exhibition_cpu_level_value, __ATOMIC_ACQUIRE), NULL);
    exhibition_apply_match_settings(NULL);
    __atomic_store_n(&exhibition_match_settings_armed, 1,
                     __ATOMIC_RELEASE);
  }

  __atomic_store_n(&virtual_cursor_context, PES_VIRTUAL_CURSOR_NONE,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_gameplan_custom_active, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_gameplan_custom_action, 0,
                   __ATOMIC_RELEASE);

  if (exhibition_strategy_footer_original)
    exhibition_strategy_footer_original(window, footer_key);

  if (starting_match && footer_key == 0) {
    __atomic_store_n(&exhibition_strategy_action,
                     EXHIBITION_STRATEGY_NONE, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_strategy_pending, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_session_active, 0, __ATOMIC_RELEASE);
    debugPrintf("exhibition: Strategy Play -> stock MatchSetup\n");
  }
}

static int32_t clamp_pad_value(int32_t value) {
  if (value < 0)
    return 0;
  if (value > 0x7fff)
    return 0x7fff;
  return value;
}

void cobra_pad_set_input(uint32_t buttons, int32_t up, int32_t down,
                         int32_t left, int32_t right, int connected) {
  const int16_t x = (int16_t)(clamp_pad_value(right) -
                              clamp_pad_value(left));
  const int16_t y = (int16_t)(clamp_pad_value(down) -
                              clamp_pad_value(up));
  const uint64_t packed = (uint64_t)buttons |
                          ((uint64_t)(uint16_t)x << 32) |
                          ((uint64_t)(uint16_t)y << 48);
  if (__atomic_load_n(&cobra_pad_input, __ATOMIC_RELAXED) != packed)
    __atomic_store_n(&cobra_pad_input, packed, __ATOMIC_RELEASE);
  const int connected_value = connected != 0;
  if (__atomic_load_n(&cobra_pad_connected, __ATOMIC_RELAXED) !=
      connected_value)
    __atomic_store_n(&cobra_pad_connected, connected_value,
                     __ATOMIC_RELEASE);
}

static int cobra_controller_is_connected(void) {
  return __atomic_load_n(&cobra_pad_connected, __ATOMIC_ACQUIRE) != 0;
}

int pes_controller_native_pad_lab_active(void) {
  return __atomic_load_n(&native_gamepad_lab_active,
                         __ATOMIC_ACQUIRE) != 0;
}

uint32_t pes_mobile_control_context(int *mode) {
  const uint32_t generation =
      __atomic_load_n(&mobile_control_generation, __ATOMIC_ACQUIRE);
  if (mode)
    *mode = (int)__atomic_load_n(&mobile_control_mode, __ATOMIC_ACQUIRE);
  return generation;
}

// Native pad input is useful for menu and matchmaking widgets. Normal live
// gameplay remains on the calibrated multi-touch mapping in android_shim.c;
// only the explicitly armed single-player lab uses the native gameplay path.
int pes_controller_menu_active(void) {
  return pes_controller_start_prompt(NULL, NULL) ||
         __atomic_load_n(&main_menu_graphics_active, __ATOMIC_ACQUIRE) ||
         __atomic_load_n(&main_menu_info_popup, __ATOMIC_ACQUIRE) !=
             MAIN_MENU_INFO_CLOSED ||
         __atomic_load_n(&main_menu_video_settings_open, __ATOMIC_ACQUIRE) ||
         __atomic_load_n(&main_menu_controller_active, __ATOMIC_ACQUIRE) ||
         __atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE) ||
         __atomic_load_n(&exhibition_team_picker_open, __ATOMIC_ACQUIRE) ||
         __atomic_load_n(&exhibition_cpu_level_popup_open, __ATOMIC_ACQUIRE) ||
         __atomic_load_n(&exhibition_settings_popup_open, __ATOMIC_ACQUIRE) ||
         __atomic_load_n(&exhibition_session_active, __ATOMIC_ACQUIRE) ||
         __atomic_load_n(&exhibition_team_select_active, __ATOMIC_ACQUIRE) ||
         pes_controller_pause_camera_active() ||
         pes_controller_custom_postmatch_active();
}

int pes_controller_virtual_cursor_context(void) {
  const uint32_t context =
      __atomic_load_n(&virtual_cursor_context, __ATOMIC_ACQUIRE);
  uint64_t seen = 0;
  if (context == PES_VIRTUAL_CURSOR_PAUSE)
    seen = __atomic_load_n(&match_pause_seen_tick, __ATOMIC_ACQUIRE);
  else if (context == PES_VIRTUAL_CURSOR_GAMEPLAN)
    seen = __atomic_load_n(&match_gameplan_seen_tick, __ATOMIC_ACQUIRE);
  else if (context == PES_VIRTUAL_CURSOR_HALF_TIME ||
           context == PES_VIRTUAL_CURSOR_HALF_PREVIEW ||
           context == PES_VIRTUAL_CURSOR_FULL_TIME)
    seen = __atomic_load_n(&match_result_seen_tick, __ATOMIC_ACQUIRE);
  else if (context == PES_VIRTUAL_CURSOR_TUTORIAL)
    seen = __atomic_load_n(&match_tutorial_guide_seen_tick,
                           __ATOMIC_ACQUIRE);
  else if (context == PES_VIRTUAL_CURSOR_SET_PIECE_TAKER)
    seen = __atomic_load_n(&match_kicker_select_seen_tick,
                           __ATOMIC_ACQUIRE);
  uint64_t cursor_timeout_ns = 500000000ULL;
  if (context == PES_VIRTUAL_CURSOR_HALF_TIME ||
      context == PES_VIRTUAL_CURSOR_HALF_PREVIEW ||
      context == PES_VIRTUAL_CURSOR_FULL_TIME)
    cursor_timeout_ns = 180000000ULL;
  if (context != PES_VIRTUAL_CURSOR_NONE &&
      (!seen || armTicksToNs(armGetSystemTick() - seen) > cursor_timeout_ns)) {
    uint32_t expected = context;
    __atomic_compare_exchange_n(&virtual_cursor_context, &expected,
                                PES_VIRTUAL_CURSOR_NONE, 0,
                                __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE);
    return PES_VIRTUAL_CURSOR_NONE;
  }
  if (context == PES_VIRTUAL_CURSOR_HALF_TIME ||
      context == PES_VIRTUAL_CURSOR_HALF_PREVIEW ||
      context == PES_VIRTUAL_CURSOR_FULL_TIME) {
    const uint64_t started = __atomic_load_n(&match_result_started_tick,
                                              __ATOMIC_ACQUIRE);
    // Result constructors run before the native Next footer has finished its
    // entrance animation. Delay the controller helper briefly so it follows
    // the visible button rather than leading the page transition.
    if (started &&
        armTicksToNs(armGetSystemTick() - started) < 300000000ULL)
      return PES_VIRTUAL_CURSOR_NONE;
  }
  return (int)context;
}

void pes_controller_result_cursor_clear(void) {
  const uint32_t context =
      __atomic_load_n(&virtual_cursor_context, __ATOMIC_ACQUIRE);
  if (context != PES_VIRTUAL_CURSOR_HALF_TIME &&
      context != PES_VIRTUAL_CURSOR_HALF_PREVIEW &&
      context != PES_VIRTUAL_CURSOR_FULL_TIME)
    return;
  // MobileControl can remain OFFENSE/DEFENSE while a result frontend owns the
  // screen. The input thread therefore still reports gameplay_active during
  // both result pages. Do not let that stale gameplay flag erase the result
  // cursor while its native window is refreshing this heartbeat.
  const uint64_t seen =
      __atomic_load_n(&match_result_seen_tick, __ATOMIC_ACQUIRE);
  if (seen && armTicksToNs(armGetSystemTick() - seen) <= 300000000ULL)
    return;
  __atomic_store_n(&match_result_seen_tick, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_result_started_tick, 0, __ATOMIC_RELEASE);
  match_result_window = NULL;
  __atomic_store_n(&virtual_cursor_context, PES_VIRTUAL_CURSOR_NONE,
                   __ATOMIC_RELEASE);
}

int pes_controller_gameplan_cursor_active(void) {
  return pes_controller_virtual_cursor_context() != PES_VIRTUAL_CURSOR_NONE;
}

int pes_controller_gameplan_cursor_position(float *normalized_x,
                                            float *normalized_y) {
  if (!pes_controller_gameplan_cursor_active())
    return 0;
  const uint32_t x = __atomic_load_n(&exhibition_gameplan_cursor_x,
                                     __ATOMIC_ACQUIRE);
  const uint32_t y = __atomic_load_n(&exhibition_gameplan_cursor_y,
                                     __ATOMIC_ACQUIRE);
  if (normalized_x)
    *normalized_x = (float)x / 65535.0f;
  if (normalized_y)
    *normalized_y = (float)y / 65535.0f;
  return 1;
}

void pes_controller_gameplan_cursor_set(float normalized_x,
                                        float normalized_y) {
  normalized_x = fmaxf(0.005f, fminf(normalized_x, 0.995f));
  normalized_y = fmaxf(0.008f, fminf(normalized_y, 0.992f));
  __atomic_store_n(&exhibition_gameplan_cursor_x,
                   (uint32_t)(normalized_x * 65535.0f + 0.5f),
                   __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_gameplan_cursor_y,
                   (uint32_t)(normalized_y * 65535.0f + 0.5f),
                   __ATOMIC_RELEASE);
}

static void pes_virtual_cursor_activate(uint32_t context, uint32_t x,
                                        uint32_t y) {
  const uint32_t previous =
      __atomic_load_n(&virtual_cursor_context, __ATOMIC_ACQUIRE);
  if (previous != context) {
    __atomic_store_n(&exhibition_gameplan_cursor_x, x, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_gameplan_cursor_y, y, __ATOMIC_RELEASE);
    if (context == PES_VIRTUAL_CURSOR_HALF_TIME ||
        context == PES_VIRTUAL_CURSOR_HALF_PREVIEW ||
        context == PES_VIRTUAL_CURSOR_FULL_TIME)
      __atomic_store_n(&match_result_started_tick, armGetSystemTick(),
                       __ATOMIC_RELEASE);
    __atomic_store_n(&virtual_cursor_context, context, __ATOMIC_RELEASE);
  }
}

static void match_result_process_controller_input(void *window);

// MyClubSquadEdit is the authoritative native Game Plan frontend for both
// pre-match and the Pause child. Keep one heartbeat on its real update method
// so the virtual cursor follows the child instead of expiring with its parent.
void pes_match_squad_edit_update_entry(void *window, uint32_t pad_status) {
  (void)pad_status;
  if (!window)
    return;
  const uint32_t previous_context =
      __atomic_load_n(&virtual_cursor_context, __ATOMIC_ACQUIRE);
  const uint64_t pause_seen =
      __atomic_load_n(&match_pause_seen_tick, __ATOMIC_ACQUIRE);
  const int from_pause =
      previous_context == PES_VIRTUAL_CURSOR_PAUSE ||
      (pause_seen && armTicksToNs(armGetSystemTick() - pause_seen) <=
                         5000000000ULL) ||
      __atomic_load_n(&match_gameplan_pause_route, __ATOMIC_ACQUIRE);
  if (from_pause)
    __atomic_store_n(&match_gameplan_pause_route, 1u, __ATOMIC_RELEASE);
  __atomic_store_n(&match_gameplan_seen_tick, armGetSystemTick(),
                   __ATOMIC_RELEASE);
  pes_virtual_cursor_activate(PES_VIRTUAL_CURSOR_GAMEPLAN, 32768, 29491);
}

int pes_controller_gameplan_pause_route(void) {
  return __atomic_load_n(&match_gameplan_pause_route, __ATOMIC_ACQUIRE) != 0;
}

// The first half-time page is MatchResultTeamStats. It precedes
// MatchResultMainMenuHalfTime, so it needs its own cursor lifetime even though
// both pages use the same bottom-right native Next footer.
void pes_match_team_stats_update_entry(void *window) {
  if (!window)
    return;
  match_result_window = window;
  __atomic_store_n(&match_result_seen_tick, armGetSystemTick(),
                   __ATOMIC_RELEASE);
  pes_virtual_cursor_activate(PES_VIRTUAL_CURSOR_HALF_PREVIEW, 56753, 61734);
  match_result_process_controller_input(window);
}

static void pes_match_tutorial_guide_update(void *window) {
  if (!window)
    return;
  __atomic_store_n(&match_tutorial_guide_seen_tick, armGetSystemTick(),
                   __ATOMIC_RELEASE);
  pes_virtual_cursor_activate(PES_VIRTUAL_CURSOR_TUTORIAL, 56753, 61734);
}

uintptr_t pes_match_tutorial_guide_update_entry(void *window) {
  pes_match_tutorial_guide_update(window);
  return match_tutorial_guide_update_resume;
}

// The first goal-kick/corner/penalty instructions are not menu::
// MatchTutorialGuide. They are the in-match TutorialInMatchTutorial window.
// Dispatch Play through its native footer callback on the UI thread instead
// of guessing a screen coordinate from the Android input thread.
static void pes_match_inmatch_tutorial_update(void *window) {
  if (match_inmatch_tutorial_update_original)
    match_inmatch_tutorial_update_original(window);
  const int play_active =
      window && match_inmatch_tutorial_is_explaining &&
      match_window_get_pad_key_active &&
      match_inmatch_tutorial_is_explaining(window) &&
      match_window_get_pad_key_active(window, 0u);
  if (!play_active) {
    uintptr_t expected = (uintptr_t)window;
    if (__atomic_compare_exchange_n(&match_inmatch_tutorial_owner, &expected,
                                    0, 0, __ATOMIC_ACQ_REL,
                                    __ATOMIC_ACQUIRE)) {
      __atomic_store_n(&match_inmatch_tutorial_seen_tick, 0,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&match_inmatch_tutorial_play_pending, 0,
                       __ATOMIC_RELEASE);
    }
    return;
  }

  __atomic_store_n(&match_inmatch_tutorial_owner, (uintptr_t)window,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&match_inmatch_tutorial_seen_tick, armGetSystemTick(),
                   __ATOMIC_RELEASE);
  // The older MatchTutorialGuide observer can overlap this native Play page.
  // Retire its cursor heartbeat while this exact tutorial owns the footer so
  // no stale A/cursor helper can reappear during the exit transition.
  __atomic_store_n(&match_tutorial_guide_seen_tick, 0, __ATOMIC_RELEASE);
  if (__atomic_exchange_n(&match_inmatch_tutorial_play_pending, 0,
                          __ATOMIC_ACQ_REL) &&
      match_inmatch_tutorial_footer_touch)
    match_inmatch_tutorial_footer_touch(window, 0u);
}

int pes_controller_inmatch_tutorial_active(void) {
  const uintptr_t owner = __atomic_load_n(&match_inmatch_tutorial_owner,
                                           __ATOMIC_ACQUIRE);
  const uint64_t seen = __atomic_load_n(&match_inmatch_tutorial_seen_tick,
                                         __ATOMIC_ACQUIRE);
  return owner && seen &&
         armTicksToNs(armGetSystemTick() - seen) <= 350000000ULL;
}

void pes_controller_inmatch_tutorial_play_request(void) {
  if (pes_controller_inmatch_tutorial_active())
    __atomic_store_n(&match_inmatch_tutorial_play_pending, 1,
                     __ATOMIC_RELEASE);
}

void pes_controller_fix_demo_skip_request(void) {
  pes_controller_demo_skip_request();
}

uintptr_t pes_match_flow_check_skip_fix_demo_entry(void *flow,
                                                   uint32_t input_a,
                                                   uint32_t input_b) {
  (void)flow;
  (void)input_a;
  (void)input_b;
  // FixDemoManager::Skip is a member function and requires its manager
  // instance. Calling the symbol as a free function caused a crash as soon
  // as a foul/offside demo entered the skip path. The pending request is now
  // exposed to the native pad bridge as Cobra's skip bit instead.
  __atomic_store_n(&match_fix_demo_skip_seen_tick, 0, __ATOMIC_RELEASE);
  return match_flow_check_skip_fix_demo_resume;
}

int pes_controller_fix_demo_skip_active(void) {
  return match_native_demo_active_at(armGetSystemTick(), NULL);
}

int pes_main_menu_controller_active(void) {
  return __atomic_load_n(&main_menu_controller_active, __ATOMIC_ACQUIRE) != 0;
}

uint32_t pes_main_menu_focus_index(void) { return main_menu_focus_index; }

int pes_mobile_control_active_mode(void) {
  const uint64_t seen =
      __atomic_load_n(&mobile_control_seen_tick, __ATOMIC_ACQUIRE);
  if (!seen)
    return PES_MOBILE_CONTROL_UNKNOWN;
  const uint64_t age_ns = armTicksToNs(armGetSystemTick() - seen);
  if (age_ns > 250000000ULL)
    return PES_MOBILE_CONTROL_UNKNOWN;
  return (int)__atomic_load_n(&mobile_control_mode, __ATOMIC_ACQUIRE);
}

static void match_replay_publish(void *replay) {
  if (!replay)
    return;
  const uint64_t now = armGetSystemTick();
  __atomic_store_n(&match_replay_seen_tick, now, __ATOMIC_RELEASE);
  if (__atomic_load_n(&match_replay_owner, __ATOMIC_ACQUIRE) ==
      (uintptr_t)replay)
    return;
  __atomic_store_n(&match_replay_owner, (uintptr_t)replay, __ATOMIC_RELEASE);
  // Replay is skip-only. Never let the preceding interactive goal page leak
  // its Celebration action into the replay that follows it.
  __atomic_store_n(&match_replay_goal_active, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_goal_demo_seen_tick, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_goal_demo_pad_seen_tick, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_goal_demo_owner_known, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_goal_demo_player_goal, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_goal_demo_helper_consumed, 1, __ATOMIC_RELEASE);
  __atomic_store_n(&match_replay_feedback_value, PES_REPLAY_FEEDBACK_NONE,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&match_replay_feedback_tick, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_button_setplay_owner, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_button_setplay_seen_tick, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_button_setplay_mask, 0, __ATOMIC_RELEASE);
}

static uint32_t pes_match_replay_mode_init(void *replay,
                                           const void *context) {
  const uint32_t result = match_replay_mode_init_original
                              ? match_replay_mode_init_original(replay,
                                                                context)
                              : 0;
  match_replay_publish(replay);
  return result;
}

static uint32_t pes_match_replay_mode_main(void *replay,
                                           const void *context) {
  // Publish before the native Main call so the Android input poll can expose
  // Cobra's replay skip bit during the same frame.
  match_replay_publish(replay);
  return match_replay_mode_main_original
             ? match_replay_mode_main_original(replay, context)
             : 0;
}

static uint32_t pes_match_replay_mode_end(void *replay,
                                          const void *context) {
  const uint32_t result = match_replay_mode_end_original
                              ? match_replay_mode_end_original(replay, context)
                              : 0;
  uintptr_t expected = (uintptr_t)replay;
  if (__atomic_compare_exchange_n(&match_replay_owner, &expected, 0, 0,
                                  __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE))
    __atomic_store_n(&match_replay_seen_tick, 0, __ATOMIC_RELEASE);
  return result;
}

static int match_native_replay_active_at(uint64_t now) {
  const uintptr_t owner =
      __atomic_load_n(&match_replay_owner, __ATOMIC_ACQUIRE);
  const uint64_t seen =
      __atomic_load_n(&match_replay_seen_tick, __ATOMIC_ACQUIRE);
  return owner && seen && armTicksToNs(now - seen) <= 1000000000ULL;
}

static int match_native_demo_active_at(uint64_t now, uintptr_t *owner_out) {
  const uintptr_t demo_owner =
      __atomic_load_n(&match_demo_skip_owner, __ATOMIC_ACQUIRE);
  const uint64_t demo_seen =
      __atomic_load_n(&match_demo_skip_seen_tick, __ATOMIC_ACQUIRE);
  const uintptr_t out_owner =
      __atomic_load_n(&match_outofplay_skip_owner, __ATOMIC_ACQUIRE);
  const uint64_t out_seen =
      __atomic_load_n(&match_outofplay_skip_seen_tick, __ATOMIC_ACQUIRE);
  const int demo_active =
      demo_owner && demo_seen && armTicksToNs(now - demo_seen) <= 400000000ULL;
  const int out_active =
      out_owner && out_seen && armTicksToNs(now - out_seen) <= 400000000ULL;
  if (!demo_active && !out_active) {
    if (owner_out)
      *owner_out = 0;
    return 0;
  }
  if (owner_out)
    *owner_out = out_active && (!demo_active || out_seen >= demo_seen)
                     ? out_owner
                     : demo_owner;
  return 1;
}

static uint32_t match_demo_skip_main_common(
    void *unit, const void *input, uint32_t kind,
    uint32_t (*original)(void *, const void *, uint32_t),
    uintptr_t *owner_slot, uint64_t *seen_slot) {
  const int enabled_before = unit && *((const uint8_t *)unit + 24) != 0;
  const uint32_t result = original ? original(unit, input, kind) : 0;
  const int enabled_after = unit && *((const uint8_t *)unit + 24) != 0;
  if (!enabled_before && !enabled_after) {
    if (__atomic_load_n(owner_slot, __ATOMIC_ACQUIRE) == (uintptr_t)unit) {
      uintptr_t expected = (uintptr_t)unit;
      if (__atomic_compare_exchange_n(owner_slot, &expected, 0, 0,
                                      __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE))
        __atomic_store_n(seen_slot, 0, __ATOMIC_RELEASE);
    }
    return result;
  }

  const uint64_t now = armGetSystemTick();
  __atomic_store_n(owner_slot, (uintptr_t)unit, __ATOMIC_RELEASE);
  __atomic_store_n(seen_slot, now, __ATOMIC_RELEASE);
  const uintptr_t request_owner = __atomic_load_n(
      &match_demo_skip_request_owner, __ATOMIC_ACQUIRE);
  const uint64_t request_tick = __atomic_load_n(
      &match_demo_skip_request_tick, __ATOMIC_ACQUIRE);
  if (request_owner == (uintptr_t)unit && request_tick &&
      armTicksToNs(now - request_tick) <= 300000000ULL) {
    uintptr_t expected = request_owner;
    if (__atomic_compare_exchange_n(&match_demo_skip_request_owner, &expected,
                                    0, 0, __ATOMIC_ACQ_REL,
                                    __ATOMIC_ACQUIRE)) {
      __atomic_store_n(&match_demo_skip_request_tick, 0, __ATOMIC_RELEASE);
      // ThinkUnitSkip::ExecClick returns command 43. Returning it here keeps
      // all UI work on the game's own thread and avoids guessing a PadId.
      return result ? result : 43u;
    }
  }
  return result;
}

static uint32_t pes_match_demo_skip_main(void *unit, const void *input,
                                         uint32_t kind) {
  return match_demo_skip_main_common(
      unit, input, kind, match_demo_skip_main_original,
      &match_demo_skip_owner, &match_demo_skip_seen_tick);
}

static uint32_t pes_match_outofplay_skip_main(void *unit, const void *input,
                                              uint32_t kind) {
  return match_demo_skip_main_common(
      unit, input, kind, match_outofplay_skip_main_original,
      &match_outofplay_skip_owner, &match_outofplay_skip_seen_tick);
}

void pes_controller_demo_skip_request(void) {
  uintptr_t owner = 0;
  const uint64_t now = armGetSystemTick();
  if (!match_native_demo_active_at(now, &owner) || !owner)
    return;
  __atomic_store_n(&match_demo_skip_request_tick, now, __ATOMIC_RELEASE);
  __atomic_store_n(&match_demo_skip_request_owner, owner, __ATOMIC_RELEASE);
}

uintptr_t pes_match_replay_check_skip_entry(void *replay,
                                            const void *context) {
  (void)context;
  if (replay) {
    // Replay is a separate native state from the interactive goal page.  Do
    // not carry GoalDemo ownership across this transition: doing so made the
    // first replay frame look like another Goal Celebration (and also showed
    // A for the opponent's goal).  GoalDemo owns A/B; Replay owns skip-only.
    __atomic_store_n(&match_replay_seen_tick, armGetSystemTick(),
                     __ATOMIC_RELEASE);
    __atomic_store_n(&match_replay_goal_active, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&match_goal_demo_seen_tick, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&match_goal_demo_pad_seen_tick, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&match_goal_demo_owner_known, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&match_goal_demo_player_goal, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&match_goal_demo_helper_consumed, 1, __ATOMIC_RELEASE);
    const uint32_t cursor =
        __atomic_load_n(&virtual_cursor_context, __ATOMIC_ACQUIRE);
    if (cursor != PES_VIRTUAL_CURSOR_GAMEPLAN)
      __atomic_store_n(&virtual_cursor_context, PES_VIRTUAL_CURSOR_NONE,
                       __ATOMIC_RELEASE);
  }
  return match_replay_check_skip_resume;
}

// Resolve goal ownership from the side that was actually awarded the goal.
// IsCpuGoal describes who performed the scoring action, so an own goal can be
// reported as a player action even though the point belongs to the opponent.
// GoalSide follows the scoreboard and is therefore authoritative here.
static uint32_t match_goal_demo_resolve_owner(void *goal_demo,
                                              const void *registry,
                                              uint32_t *player_goal) {
  if (!registry || !player_goal)
    return 0;

  if (match_goal_demo_get_goal_side && exhibition_get_match_my_side) {
    const uint32_t goal_side = match_goal_demo_get_goal_side(registry);
    const uint32_t user_side = exhibition_get_match_my_side();
    if (goal_side < 2u && user_side < 2u) {
      *player_goal = goal_side == user_side;
      return 1;
    }
  }

  // Compatibility fallback for goal-demo variants where GoalSide is not yet
  // available.  This is intentionally secondary because it cannot classify
  // own goals correctly.
  if (goal_demo && match_goal_demo_is_cpu_goal) {
    *player_goal = match_goal_demo_is_cpu_goal(goal_demo, registry) ? 0u : 1u;
    return 1;
  }
  return 0;
}

// GoalSide alone cannot identify an own goal: on this mobile build it can
// still describe the side controlling the scorer while the own-goal demo is
// being selected.  Replace the tiny native predicate with an equivalent
// implementation and publish its result to the controller surface.  This is
// event-driven by GoalDemo itself and adds no work to the gameplay hot path.
static uint32_t pes_match_goal_demo_is_own_goal(void *goal_demo) {
  uint32_t demo_kind = 0;
  if (goal_demo)
    memcpy(&demo_kind, (const uint8_t *)goal_demo + 8, sizeof(demo_kind));
  const uint32_t own_goal = (uint32_t)(demo_kind - 0x000300d0u) < 3u;
  if (own_goal) {
    __atomic_store_n(&match_goal_demo_player_goal, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&match_goal_demo_owner_known, 1, __ATOMIC_RELEASE);
  }
  return own_goal;
}

// InteractiveGoalDemoInit is the authoritative beginning of a new A/B choice
// page. Reset the one-shot latch here, rather than from a timeout heartbeat,
// so a stale GoalDemo unit cannot resurrect the helper during the black
// transition after replay.
uintptr_t pes_match_goal_demo_init_entry(void *goal_demo) {
  (void)goal_demo;
  __atomic_store_n(&match_goal_demo_helper_consumed, 0, __ATOMIC_RELEASE);
  return match_goal_demo_init_resume;
}

void pes_controller_goal_demo_consume(void) {
  __atomic_store_n(&match_goal_demo_helper_consumed, 1, __ATOMIC_RELEASE);

  // Hide only the cached presentation bit immediately. Keep the semantic
  // GoalDemo surface alive so its synthetic A/B touch can complete the full
  // 90 ms DOWN/MOVE/UP sequence instead of being released after one frame.
  uint64_t word = __atomic_load_n(&match_controller_surface_word,
                                  __ATOMIC_ACQUIRE);
  for (;;) {
    const uint32_t payload = (uint32_t)word;
    if ((payload & 0x7u) != PES_CONTROLLER_SURFACE_GOAL_DEMO ||
        !(payload & (1u << 19)))
      break;
    const uint32_t generation = (uint32_t)(word >> 32);
    const uint64_t replacement =
        ((uint64_t)(generation + 1u) << 32) |
        (uint64_t)(payload & ~(1u << 19));
    if (__atomic_compare_exchange_n(&match_controller_surface_word, &word,
                                    replacement, 0, __ATOMIC_ACQ_REL,
                                    __ATOMIC_ACQUIRE))
      break;
  }
}

uintptr_t pes_match_goal_demo_update_entry(void *goal_demo,
                                           const void *registry,
                                           void *screen_info,
                                           const void *context) {
  (void)screen_info;
  (void)context;
  if (goal_demo && registry) {
    uint32_t player_goal = 0;
    const uint32_t owner_known =
        match_goal_demo_resolve_owner(goal_demo, registry, &player_goal);
    __atomic_store_n(&match_goal_demo_player_goal, player_goal,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&match_goal_demo_owner_known, owner_known,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&match_goal_demo_seen_tick, armGetSystemTick(),
                     __ATOMIC_RELEASE);
    const uint32_t cursor =
        __atomic_load_n(&virtual_cursor_context, __ATOMIC_ACQUIRE);
    if (cursor != PES_VIRTUAL_CURSOR_GAMEPLAN)
      __atomic_store_n(&virtual_cursor_context, PES_VIRTUAL_CURSOR_NONE,
                       __ATOMIC_RELEASE);
  }
  return match_goal_demo_update_resume;
}

static void match_goal_demo_refresh_owner(void) {
  uint32_t owner_known = 0;
  uint32_t player_goal = 0;
  if (match_global_registry_get_instance) {
    const void *registry = match_global_registry_get_instance();
    owner_known =
        match_goal_demo_resolve_owner(NULL, registry, &player_goal);
  }
  __atomic_store_n(&match_goal_demo_owner_known, owner_known,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&match_goal_demo_player_goal, player_goal,
                   __ATOMIC_RELEASE);
}

// Unlike GoalDemo::UpdateGoalDemo2DInfo, this native pad unit is a small,
// frame-safe heartbeat that is only instantiated while the interactive goal
// actions (Skip/Celebration) are on screen.  Keep the original call intact and
// use the heartbeat only to select the goal-specific controller surface.
static uint32_t pes_match_goal_demo_pad_main(void *unit, const void *input,
                                             uint32_t kind) {
  const uint32_t result = match_goal_demo_pad_main_original
                              ? match_goal_demo_pad_main_original(unit, input,
                                                                  kind)
                              : 0;
  if (unit && input) {
    const uint64_t now = armGetSystemTick();
    const uint64_t previous_seen = __atomic_load_n(
        &match_goal_demo_pad_seen_tick, __ATOMIC_ACQUIRE);
    __atomic_store_n(&match_goal_demo_pad_seen_tick, now, __ATOMIC_RELEASE);
    // Resolve ownership from GoalDemo::GetGoalSide through the global native
    // registry.  The old implementation hard-coded this to player-owned and
    // therefore exposed Celebration for opponent goals as well.  If the
    // registry is not ready, keep the page skip-only rather than guessing.
    if ((!previous_seen ||
         armTicksToNs(now - previous_seen) > 500000000ULL) &&
        !__atomic_load_n(&match_goal_demo_owner_known, __ATOMIC_ACQUIRE))
      match_goal_demo_refresh_owner();
  }
  return result;
}

int pes_controller_goal_demo_active(void) {
  const uint64_t seen = __atomic_load_n(&match_goal_demo_seen_tick,
                                         __ATOMIC_ACQUIRE);
  const uint64_t pad_seen = __atomic_load_n(&match_goal_demo_pad_seen_tick,
                                             __ATOMIC_ACQUIRE);
  const uint64_t now = armGetSystemTick();
  return (seen && armTicksToNs(now - seen) <= 500000000ULL) ||
         (pad_seen && armTicksToNs(now - pad_seen) <= 500000000ULL);
}

int pes_controller_goal_demo_player_goal(void) {
  return pes_controller_goal_demo_active() &&
         __atomic_load_n(&match_goal_demo_owner_known, __ATOMIC_ACQUIRE) &&
         __atomic_load_n(&match_goal_demo_player_goal, __ATOMIC_ACQUIRE);
}

static uint32_t match_button_setplay_context_from_mask(uint32_t mask) {
  if (mask & (1u << PES_SETPLAY_BUTTON_POSITION_SHIFT))
    return PES_SETPLAY_GOAL_KICK;
  if (mask & (1u << PES_SETPLAY_BUTTON_SHORT_CORNER))
    return PES_SETPLAY_CORNER;
  if (mask & (1u << PES_SETPLAY_BUTTON_SELECT_THROWER))
    return PES_SETPLAY_THROW_IN;
  if (mask & (1u << PES_SETPLAY_BUTTON_SET_PIECE_TAKER))
    return PES_SETPLAY_FREE_KICK;
  return PES_SETPLAY_NONE;
}

static uint32_t match_button_setplay_options_from_mask(uint32_t mask) {
  uint32_t options = 0;
  if (mask & (1u << PES_SETPLAY_BUTTON_POSITION_SHIFT))
    options |= PES_SETPLAY_OPTION_TEAM_UP;
  if (mask & ((1u << PES_SETPLAY_BUTTON_SET_PIECE_TAKER) |
              (1u << PES_SETPLAY_BUTTON_SELECT_THROWER)))
    options |= PES_SETPLAY_OPTION_KICKER;
  if (mask & (1u << PES_SETPLAY_BUTTON_SHORT_CORNER))
    options |= PES_SETPLAY_OPTION_SHORT_CORNER;
  if (mask & (1u << PES_SETPLAY_BUTTON_SWITCH_VIEW))
    options |= PES_SETPLAY_OPTION_CAMERA;
  return options;
}

static uint32_t match_button_setplay_read_mask(const void *window) {
  if (!window)
    return 0;
  const uintptr_t begin =
      *(const uintptr_t *)((const uint8_t *)window + 632);
  const uintptr_t end = *(const uintptr_t *)((const uint8_t *)window + 640);
  if (!begin || end < begin || ((end - begin) & 3u) != 0 ||
      end - begin > 3u * sizeof(uint32_t))
    return 0;
  uint32_t mask = 0;
  const uint32_t *button = (const uint32_t *)begin;
  const uint32_t *button_end = (const uint32_t *)end;
  for (; button < button_end; button++) {
    const uint32_t type = *button;
    if (type <= PES_SETPLAY_BUTTON_SWITCH_VIEW)
      mask |= 1u << type;
  }
  return mask;
}

static void match_kicker_selector_close(void) {
  __atomic_store_n(&match_kicker_selector_open, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_kicker_selector_armed, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_kicker_selector_pending_action, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&match_kicker_selector_count, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_kicker_selector_button_owner, 0,
                   __ATOMIC_RELEASE);
}

static char match_kicker_selector_latin_fold(uint32_t codepoint) {
  switch (codepoint) {
  case 0x00c0: case 0x00c1: case 0x00c2: case 0x00c3:
  case 0x00c4: case 0x00c5: case 0x00c6: case 0x0104:
    return 'A';
  case 0x00e0: case 0x00e1: case 0x00e2: case 0x00e3:
  case 0x00e4: case 0x00e5: case 0x00e6: case 0x0105:
    return 'a';
  case 0x00c7: case 0x0106: case 0x0108: case 0x010c:
    return 'C';
  case 0x00e7: case 0x0107: case 0x0109: case 0x010d:
    return 'c';
  case 0x010e: case 0x0110:
    return 'D';
  case 0x010f: case 0x0111:
    return 'd';
  case 0x00c8: case 0x00c9: case 0x00ca: case 0x00cb: case 0x0118:
    return 'E';
  case 0x00e8: case 0x00e9: case 0x00ea: case 0x00eb: case 0x0119:
    return 'e';
  case 0x00cc: case 0x00cd: case 0x00ce: case 0x00cf:
    return 'I';
  case 0x00ec: case 0x00ed: case 0x00ee: case 0x00ef:
    return 'i';
  case 0x0141:
    return 'L';
  case 0x0142:
    return 'l';
  case 0x00d1: case 0x0143: case 0x0147:
    return 'N';
  case 0x00f1: case 0x0144: case 0x0148:
    return 'n';
  case 0x00d2: case 0x00d3: case 0x00d4: case 0x00d5:
  case 0x00d6: case 0x00d8:
    return 'O';
  case 0x00f2: case 0x00f3: case 0x00f4: case 0x00f5:
  case 0x00f6: case 0x00f8:
    return 'o';
  case 0x0158:
    return 'R';
  case 0x0159:
    return 'r';
  case 0x015a: case 0x0160:
    return 'S';
  case 0x00df: case 0x015b: case 0x0161:
    return 's';
  case 0x0164:
    return 'T';
  case 0x0165:
    return 't';
  case 0x00d9: case 0x00da: case 0x00db: case 0x00dc: case 0x016e:
    return 'U';
  case 0x00f9: case 0x00fa: case 0x00fb: case 0x00fc: case 0x016f:
    return 'u';
  case 0x00dd:
    return 'Y';
  case 0x00fd: case 0x00ff:
    return 'y';
  case 0x0179: case 0x017b: case 0x017d:
    return 'Z';
  case 0x017a: case 0x017c: case 0x017e:
    return 'z';
  default:
    return '?';
  }
}

static void match_kicker_selector_copy_name(char *destination,
                                             size_t destination_size,
                                             const char *source) {
  if (!destination || !destination_size)
    return;
  size_t out = 0;
  const unsigned char *cursor = (const unsigned char *)source;
  while (cursor && *cursor && out + 1u < destination_size) {
    uint32_t codepoint = *cursor++;
    if (codepoint >= 0xc2u && codepoint <= 0xdfu &&
        (cursor[0] & 0xc0u) == 0x80u) {
      codepoint = ((codepoint & 0x1fu) << 6) | (*cursor++ & 0x3fu);
    } else if (codepoint >= 0xe0u && codepoint <= 0xefu && cursor[0] &&
               cursor[1] && (cursor[0] & 0xc0u) == 0x80u &&
               (cursor[1] & 0xc0u) == 0x80u) {
      codepoint = ((codepoint & 0x0fu) << 12) |
                  ((cursor[0] & 0x3fu) << 6) | (cursor[1] & 0x3fu);
      cursor += 2;
    }
    destination[out++] = codepoint < 0x80u
                             ? (char)codepoint
                             : match_kicker_selector_latin_fold(codepoint);
  }
  destination[out] = '\0';
}

// ActionButtonBase dispatches every set-play card through this virtual
// method. Intercept only the two player-selector actions before the native
// TouchKickerSelect task is created; every other action remains stock.
static void pes_match_button_setplay_touch_sub(void *window,
                                               const void *touch_info) {
  uint32_t type = 0;
  if (window && touch_info) {
    const uintptr_t begin =
        *(const uintptr_t *)((const uint8_t *)window + 632);
    const uintptr_t end =
        *(const uintptr_t *)((const uint8_t *)window + 640);
    const uint32_t index = *(const uint32_t *)((const uint8_t *)touch_info + 20);
    if (begin && end >= begin && ((end - begin) & 3u) == 0 &&
        end - begin <= 3u * sizeof(uint32_t) &&
        index < (uint32_t)((end - begin) / sizeof(uint32_t)))
      type = ((const uint32_t *)begin)[index];
  }

  if (type != PES_SETPLAY_BUTTON_SET_PIECE_TAKER &&
      type != PES_SETPLAY_BUTTON_SELECT_THROWER) {
    if (match_button_setplay_touch_sub_original)
      match_button_setplay_touch_sub_original(window, touch_info);
    return;
  }

  const uint32_t mask = match_button_setplay_read_mask(window);
  uint32_t context = type == PES_SETPLAY_BUTTON_SELECT_THROWER
                         ? PES_SETPLAY_THROW_IN
                         : match_button_setplay_context_from_mask(mask);
  if (context != PES_SETPLAY_CORNER && context != PES_SETPLAY_FREE_KICK &&
      context != PES_SETPLAY_THROW_IN)
    context = type == PES_SETPLAY_BUTTON_SELECT_THROWER
                  ? PES_SETPLAY_THROW_IN
                  : PES_SETPLAY_FREE_KICK;

  // Publish the arm last. ThinkUnitKickerSelect builds the authoritative
  // roster on the match thread before opening the overlay.
  __atomic_store_n(&match_kicker_selector_button_owner, (uintptr_t)window,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&match_button_setplay_owner, (uintptr_t)window,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&match_button_setplay_mask, mask, __ATOMIC_RELEASE);
  __atomic_store_n(&match_button_setplay_seen_tick, armGetSystemTick(),
                   __ATOMIC_RELEASE);
  __atomic_store_n(&match_kicker_selector_context, context,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&match_kicker_selector_focus, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_kicker_selector_count, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_kicker_selector_pending_action, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&match_kicker_selector_open, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_kicker_selector_armed, 1, __ATOMIC_RELEASE);
  __atomic_store_n(&virtual_cursor_context, PES_VIRTUAL_CURSOR_NONE,
                   __ATOMIC_RELEASE);
  if (match_window_set_se)
    match_window_set_se(window, 60u);
}

static uint32_t pes_match_button_setplay_need_disp(void *window) {
  const uint32_t visible = match_button_setplay_need_disp_original
                               ? match_button_setplay_need_disp_original(window)
                               : 0;
  const uintptr_t owner =
      __atomic_load_n(&match_button_setplay_owner, __ATOMIC_ACQUIRE);
  if (!visible || !window) {
    if (owner == (uintptr_t)window) {
      __atomic_store_n(&match_button_setplay_owner, 0, __ATOMIC_RELEASE);
      __atomic_store_n(&match_button_setplay_seen_tick, 0, __ATOMIC_RELEASE);
      __atomic_store_n(&match_button_setplay_mask, 0, __ATOMIC_RELEASE);
    }
    if (__atomic_load_n(&match_kicker_selector_button_owner,
                        __ATOMIC_ACQUIRE) == (uintptr_t)window)
      match_kicker_selector_close();
    return visible;
  }

  const uint32_t mask = match_button_setplay_read_mask(window);
  if (__atomic_load_n(&match_button_setplay_mask, __ATOMIC_ACQUIRE) != mask)
    __atomic_store_n(&match_button_setplay_mask, mask, __ATOMIC_RELEASE);
  if (owner != (uintptr_t)window)
    __atomic_store_n(&match_button_setplay_owner, (uintptr_t)window,
                     __ATOMIC_RELEASE);
  __atomic_store_n(&match_button_setplay_seen_tick, armGetSystemTick(),
                   __ATOMIC_RELEASE);
  return visible;
}

static void pes_match_button_setplay_update(void *window) {
  if (match_button_setplay_update_original)
    match_button_setplay_update_original(window);
  if (!window)
    return;

  // Alpha only: NeedDisp/SetVisible also gate the touch/joy-con action state.
  // This is ButtonSetplay's own root, never the taker selector/pause window.
  if (match_node_set_alpha && match_setplay_get_root) {
    // Same visual root used by ActionButtonBase::SetupSwf, not the outer
    // GetWindow node whose wrapper need not own a Flash MovieClip.
    void *root = match_setplay_get_root(window);
    if (root)
      match_node_set_alpha(root, 0.0f);
  }

  const uint32_t requested = __atomic_load_n(
      &match_button_setplay_pending_type, __ATOMIC_ACQUIRE);
  if (!requested)
    return;
  const uint64_t now = armGetSystemTick();
  const uint64_t request_tick = __atomic_load_n(
      &match_button_setplay_pending_tick, __ATOMIC_ACQUIRE);
  if (!request_tick || armTicksToNs(now - request_tick) > 400000000ULL) {
    uint32_t expected = requested;
    __atomic_compare_exchange_n(&match_button_setplay_pending_type, &expected,
                                0, 0, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE);
    return;
  }

  PesControllerSnapshot snapshot;
  pes_controller_surface_snapshot(&snapshot);
  const uint32_t request_generation = __atomic_load_n(
      &match_button_setplay_pending_generation, __ATOMIC_ACQUIRE);
  if (snapshot.surface != PES_CONTROLLER_SURFACE_SETPLAY ||
      snapshot.generation != request_generation ||
      !(snapshot.setplay_button_mask & (1u << requested)) ||
      __atomic_load_n(&match_button_setplay_owner, __ATOMIC_ACQUIRE) !=
          (uintptr_t)window) {
    uint32_t expected = requested;
    __atomic_compare_exchange_n(&match_button_setplay_pending_type, &expected,
                                0, 0, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE);
    return;
  }

  const uintptr_t begin = *(const uintptr_t *)((const uint8_t *)window + 632);
  const uintptr_t end = *(const uintptr_t *)((const uint8_t *)window + 640);
  if (!begin || end < begin || ((end - begin) & 3u) != 0 ||
      end - begin > 3u * sizeof(uint32_t)) {
    uint32_t expected = requested;
    __atomic_compare_exchange_n(&match_button_setplay_pending_type, &expected,
                                0, 0, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE);
    return;
  }

  uint32_t index = UINT32_MAX;
  const uint32_t count = (uint32_t)((end - begin) / sizeof(uint32_t));
  for (uint32_t i = 0; i < count; i++) {
    if (((const uint32_t *)begin)[i] == requested) {
      index = i;
      break;
    }
  }
  if (index == UINT32_MAX) {
    uint32_t expected = requested;
    __atomic_compare_exchange_n(&match_button_setplay_pending_type, &expected,
                                0, 0, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE);
    return;
  }

  // Leave a request pending briefly while the game's native 0.3 s button
  // cooldown is active. This makes a quick Joy-Con edge reliable without
  // bypassing the UI's own debounce rules.
  if (match_action_button_get_disable_timer &&
      match_action_button_get_disable_timer(window, requested) > 0.0f)
    return;

  uint32_t expected = requested;
  if (!__atomic_compare_exchange_n(&match_button_setplay_pending_type,
                                   &expected, 0, 0, __ATOMIC_ACQ_REL,
                                   __ATOMIC_ACQUIRE))
    return;
  __atomic_store_n(&match_button_setplay_pending_tick, 0, __ATOMIC_RELEASE);
  _Alignas(8) uint8_t touch_info[32] = {0};
  *(uint32_t *)(touch_info + 20) = index;
  if (match_action_button_pad_event_touch)
    match_action_button_pad_event_touch(window, touch_info);
}

void pes_controller_setplay_request(uint32_t button_type,
                                    uint32_t generation) {
  if (button_type > PES_SETPLAY_BUTTON_SWITCH_VIEW)
    return;
  __atomic_store_n(&match_button_setplay_pending_generation, generation,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&match_button_setplay_pending_tick, armGetSystemTick(),
                   __ATOMIC_RELEASE);
  __atomic_store_n(&match_button_setplay_pending_type, button_type,
                   __ATOMIC_RELEASE);
}

static void match_native_setplay_publish(uint32_t context) {
  if (__atomic_load_n(&match_native_setplay_context, __ATOMIC_RELAXED) !=
      context)
    __atomic_store_n(&match_native_setplay_context, context,
                     __ATOMIC_RELEASE);
}

static void match_native_penalty_publish(uint32_t role) {
  if (__atomic_load_n(&match_penalty_role, __ATOMIC_RELAXED) != role)
    __atomic_store_n(&match_penalty_role, role, __ATOMIC_RELEASE);
  __atomic_store_n(&match_penalty_seen_tick, armGetSystemTick(),
                   __ATOMIC_RELEASE);
}

static uint32_t pes_match_penalty_kicker_main(void *unit,
                                               const void *input,
                                               uint32_t kind) {
  const uint32_t result = match_penalty_kicker_main_original
                              ? match_penalty_kicker_main_original(unit,
                                                                    input,
                                                                    kind)
                              : 0;
  // ThinkUnitBase::m_active is byte +24. Only the active mobile penalty unit
  // may own the controller surface; idle objects must not race the keeper.
  if (unit && input && *((const uint8_t *)unit + 24))
    match_native_penalty_publish(PES_PENALTY_KICKER);
  return result;
}

static uint32_t pes_match_penalty_goalkeeper_main(void *unit,
                                                   const void *input,
                                                   uint32_t kind) {
  const uint32_t result =
      match_penalty_goalkeeper_main_original
          ? match_penalty_goalkeeper_main_original(unit, input, kind)
          : 0;
  if (unit && input && *((const uint8_t *)unit + 24))
    match_native_penalty_publish(PES_PENALTY_GOALKEEPER);
  return result;
}

static uint32_t pes_match_penalty_goalkeeper_move_main(void *unit,
                                                        const void *input,
                                                        uint32_t kind) {
  const uint32_t result =
      match_penalty_goalkeeper_move_main_original
          ? match_penalty_goalkeeper_move_main_original(unit, input, kind)
          : 0;
  // The nested GKMove unit is the object that actually consumes ScreenTap's
  // right-half swipe and calculates the save angle. Its heartbeat is the
  // authoritative keeper state even if the outer unit changes lifecycle.
  if (unit && input && *((const uint8_t *)unit + 24))
    match_native_penalty_publish(PES_PENALTY_GOALKEEPER);
  return result;
}

uint32_t pes_controller_penalty_role(void) {
  const uint64_t seen = __atomic_load_n(&match_penalty_seen_tick,
                                         __ATOMIC_ACQUIRE);
  if (!seen ||
      armTicksToNs(armGetSystemTick() - seen) > 250000000ULL)
    return PES_PENALTY_NONE;
  return __atomic_load_n(&match_penalty_role, __ATOMIC_ACQUIRE);
}

void pes_controller_cinematic_update(int gameplay_active, int control_mode,
                                     int excluded, uint64_t now_ms) {
  (void)excluded;
  (void)now_ms;
  const int known_mode = control_mode == PES_MOBILE_CONTROL_OFFENSE ||
                         control_mode == PES_MOBILE_CONTROL_DEFENSE;
  if (gameplay_active && known_mode)
    pes_controller_result_cursor_clear();
  // The old ScreenTap gap heuristic confused set pieces and the first live
  // kickoff frame with cinematics. Replay and demo skip now have exact native
  // lifecycle hooks, so the heuristic must remain disabled.
}

int pes_controller_cinematic_skip_active(void) {
  return match_native_demo_active_at(armGetSystemTick(), NULL);
}

int pes_controller_replay_active(void) {
  return match_native_replay_active_at(armGetSystemTick());
}

int pes_controller_replay_goal_active(void) {
  // Interactive GoalDemo owns A/B. Native Replay is always skip-only.
  return 0;
}

void pes_controller_replay_feedback_set(uint32_t feedback) {
  __atomic_store_n(&match_replay_feedback_value, feedback, __ATOMIC_RELEASE);
  __atomic_store_n(&match_replay_feedback_tick, armGetSystemTick(),
                   __ATOMIC_RELEASE);
}

uint32_t pes_controller_replay_feedback(void) {
  const uint64_t tick = __atomic_load_n(&match_replay_feedback_tick,
                                        __ATOMIC_ACQUIRE);
  if (!tick || armTicksToNs(armGetSystemTick() - tick) > 750000000ULL)
    return PES_REPLAY_FEEDBACK_NONE;
  return __atomic_load_n(&match_replay_feedback_value, __ATOMIC_ACQUIRE);
}

void pes_controller_surface_snapshot(PesControllerSnapshot *snapshot) {
  if (!snapshot)
    return;
  memset(snapshot, 0, sizeof(*snapshot));
  const uint64_t now = armGetSystemTick();

  uint32_t surface = PES_CONTROLLER_SURFACE_NONE;
  uint32_t setplay_context = PES_SETPLAY_NONE;
  uint32_t setplay_options = 0;
  uint32_t setplay_mask = 0;
  uint32_t goal_player = 0;
  uint32_t goal_helper_visible = 0;

  if (match_native_replay_active_at(now)) {
    surface = PES_CONTROLLER_SURFACE_REPLAY;
  } else {
    const uint64_t goal_seen = __atomic_load_n(
        &match_goal_demo_seen_tick, __ATOMIC_ACQUIRE);
    const uint64_t goal_pad_seen = __atomic_load_n(
        &match_goal_demo_pad_seen_tick, __ATOMIC_ACQUIRE);
    const int goal_active =
        (goal_seen && armTicksToNs(now - goal_seen) <= 500000000ULL) ||
        (goal_pad_seen &&
         armTicksToNs(now - goal_pad_seen) <= 500000000ULL);
    if (goal_active) {
      surface = PES_CONTROLLER_SURFACE_GOAL_DEMO;
      goal_player =
          __atomic_load_n(&match_goal_demo_owner_known, __ATOMIC_ACQUIRE) &&
          __atomic_load_n(&match_goal_demo_player_goal, __ATOMIC_ACQUIRE);
      goal_helper_visible =
          !__atomic_load_n(&match_goal_demo_helper_consumed,
                           __ATOMIC_ACQUIRE);
    } else if (match_native_demo_active_at(now, NULL)) {
      surface = PES_CONTROLLER_SURFACE_CINEMATIC;
    } else {
      const uint64_t setplay_seen = __atomic_load_n(
          &match_button_setplay_seen_tick, __ATOMIC_ACQUIRE);
      const uintptr_t setplay_owner = __atomic_load_n(
          &match_button_setplay_owner, __ATOMIC_ACQUIRE);
      if (setplay_owner && setplay_seen &&
          armTicksToNs(now - setplay_seen) <= 500000000ULL) {
        setplay_mask = __atomic_load_n(&match_button_setplay_mask,
                                       __ATOMIC_ACQUIRE);
        setplay_context = match_button_setplay_context_from_mask(setplay_mask);
        if (setplay_context != PES_SETPLAY_NONE) {
          setplay_options =
              match_button_setplay_options_from_mask(setplay_mask);
          surface = PES_CONTROLLER_SURFACE_SETPLAY;
        } else {
          setplay_mask = 0;
        }
      }
    }
  }

  const uint32_t payload =
      (surface & 0x7u) | ((setplay_context & 0x7u) << 3) |
      ((setplay_options & 0xfu) << 6) | ((setplay_mask & 0xffu) << 10) |
      ((goal_player & 1u) << 18) |
      ((goal_helper_visible & 1u) << 19);
  uint64_t word = __atomic_load_n(&match_controller_surface_word,
                                  __ATOMIC_ACQUIRE);
  for (;;) {
    const uint32_t previous_payload = (uint32_t)word;
    const uint32_t previous_generation = (uint32_t)(word >> 32);
    if (previous_payload == payload)
      break;
    const uint64_t replacement =
        ((uint64_t)(previous_generation + 1u) << 32) | payload;
    if (__atomic_compare_exchange_n(&match_controller_surface_word, &word,
                                    replacement, 0, __ATOMIC_ACQ_REL,
                                    __ATOMIC_ACQUIRE)) {
      word = replacement;
      break;
    }
  }

  snapshot->generation = (uint32_t)(word >> 32);
  snapshot->surface = surface;
  snapshot->setplay_context = setplay_context;
  snapshot->setplay_options = setplay_options;
  snapshot->setplay_button_mask = setplay_mask;
  snapshot->goal_player = goal_player;
  snapshot->goal_helper_visible = goal_helper_visible;
  const uint64_t feedback_tick = __atomic_load_n(
      &match_replay_feedback_tick, __ATOMIC_ACQUIRE);
  if (feedback_tick &&
      armTicksToNs(now - feedback_tick) <= 750000000ULL)
    snapshot->replay_feedback = __atomic_load_n(
        &match_replay_feedback_value, __ATOMIC_ACQUIRE);
}

void pes_controller_surface_cached_snapshot(PesControllerSnapshot *snapshot) {
  if (!snapshot)
    return;
  memset(snapshot, 0, sizeof(*snapshot));
  const uint64_t word = __atomic_load_n(&match_controller_surface_word,
                                        __ATOMIC_ACQUIRE);
  const uint32_t payload = (uint32_t)word;
  snapshot->generation = (uint32_t)(word >> 32);
  snapshot->surface = payload & 0x7u;
  snapshot->setplay_context = (payload >> 3) & 0x7u;
  snapshot->setplay_options = (payload >> 6) & 0xfu;
  snapshot->setplay_button_mask = (payload >> 10) & 0xffu;
  snapshot->goal_player = (payload >> 18) & 1u;
  snapshot->goal_helper_visible = (payload >> 19) & 1u;
}

static uint32_t pes_match_goalkick_main(void *unit, const void *input,
                                        uint32_t kind) {
  const uint32_t result = match_goalkick_main_original
                              ? match_goalkick_main_original(unit, input, kind)
                              : 0;
  if (unit && input)
    match_native_setplay_publish(PES_SETPLAY_GOAL_KICK);
  return result;
}

static uint32_t pes_match_corner_main(void *unit, const void *input,
                                      uint32_t kind) {
  const uint32_t result = match_corner_main_original
                              ? match_corner_main_original(unit, input, kind)
                              : 0;
  if (unit && input) {
    match_native_setplay_publish(PES_SETPLAY_CORNER);
  }
  return result;
}

static uint32_t pes_match_freekick_main(void *unit, const void *input,
                                        uint32_t kind) {
  const uint32_t result = match_freekick_main_original
                              ? match_freekick_main_original(unit, input, kind)
                              : 0;
  if (unit && input) {
    match_native_setplay_publish(PES_SETPLAY_FREE_KICK);
  }
  return result;
}

// FreeKickTactics::Main is not dispatched on every variant of the basic free
// kick page.  Its native IsDisp query is, however, evaluated while the page is
// visible; use it as a read-only fallback heartbeat so the lower Switch View
// action cannot be mistaken for a throw-in camera page.
static uint32_t pes_match_freekick_is_disp(const void *unit) {
  const uint32_t result = match_freekick_is_disp_original
                              ? match_freekick_is_disp_original(unit)
                              : 0;
  if (unit && result)
    match_native_setplay_publish(PES_SETPLAY_FREE_KICK);
  return result;
}

static int match_kicker_selector_build(const void *input) {
  if (!input || !match_global_registry_get_instance ||
      !match_global_registry_get_order_info ||
      !match_order_info_get_member_id ||
      !exhibition_tmpdb_manager_get_instance ||
      !match_tmpdb_match_get_player || !match_tmpdb_player_get_name)
    return 0;

  const uint32_t player_no =
      *(const uint32_t *)((const uint8_t *)input + 36);
  const uint32_t side = (uint32_t)(player_no - 11u) < 11u ? 1u : 0u;
  const uint32_t current_order = player_no - side * 11u;
  const void *registry = match_global_registry_get_instance();
  const void *order_info = registry
                               ? match_global_registry_get_order_info(registry,
                                                                      side)
                               : NULL;
  void *manager = exhibition_tmpdb_manager_get_instance();
  void *tmpdb_data = NULL;
  if (manager)
    memcpy(&tmpdb_data, (const uint8_t *)manager + 72,
           sizeof(tmpdb_data));
  const void *match = tmpdb_data
                          ? (const uint8_t *)tmpdb_data + 0x4b38
                          : NULL;
  if (!registry || !order_info || !match)
    return 0;

  void *live = NULL;
  memcpy(&live, (const uint8_t *)registry + 1264, sizeof(live));
  MatchKickerSelectorPlayer valid[MATCH_KICKER_SELECTOR_MAX_PLAYERS];
  uint8_t eligible[MATCH_KICKER_SELECTOR_MAX_PLAYERS] = {0};
  uint32_t valid_count = 0;
  uint32_t eligible_count = 0;
  for (uint32_t order = 0; order < 11u; order++) {
    const uint32_t member =
        match_order_info_get_member_id(order_info, order);
    if (member == UINT32_MAX || member == 0xffu || member >= 40u)
      continue;
    const void *player = match_tmpdb_match_get_player(
        match, &side, &member);
    const char *name = player ? match_tmpdb_player_get_name(player) : NULL;
    if (!player || !name || !name[0])
      continue;

    MatchKickerSelectorPlayer *entry = &valid[valid_count];
    memset(entry, 0, sizeof(*entry));
    entry->order_no = order;
    entry->current = order == current_order;
    memcpy(&entry->player_id, (const uint8_t *)player + 48,
           sizeof(entry->player_id));
    match_kicker_selector_copy_name(entry->name, sizeof(entry->name), name);
    uint32_t preferred_foot = 0;
    if (match_tmpdb_player_get_data)
      match_tmpdb_player_get_data(player, 42u, &preferred_foot);
    snprintf(entry->foot, sizeof(entry->foot), "%s FOOT",
             preferred_foot ? "LEFT" : "RIGHT");

    const int can_select =
        !live || *((const uint8_t *)live + 0x1708 + side * 11u + order) != 0;
    eligible[valid_count] = can_select;
    eligible_count += can_select != 0;
    valid_count++;
  }
  if (!valid_count)
    return 0;

  const uint32_t next_bank =
      (__atomic_load_n(&match_kicker_selector_bank, __ATOMIC_ACQUIRE) ^ 1u) &
      1u;
  MatchKickerSelectorPlayer *published =
      match_kicker_selector_players[next_bank];
  memset(published, 0,
         sizeof(match_kicker_selector_players[next_bank]));
  uint32_t count = 0;
  // Always open on page one. Following the currently assigned taker made the
  // overlay appear to start on page two for common corner/free-kick takers.
  const uint32_t focus = 0;
  // Put the active taker in slot zero, then retain formation order for every
  // other eligible player. Page one therefore opens consistently and always
  // contains the visible CURRENT marker.
  for (uint32_t pass = 0; pass < 2u; pass++) {
    for (uint32_t index = 0; index < valid_count; index++) {
      const uint32_t is_current = valid[index].current != 0;
      if ((pass == 0u) != is_current)
        continue;
      if (eligible_count && !eligible[index] && !is_current)
        continue;
      published[count++] = valid[index];
    }
  }
  if (!count)
    return 0;

  // The inactive bank is complete before the release-published bank/count.
  // Overlay rendering therefore never observes a half-written player name.
  __atomic_store_n(&match_kicker_selector_bank, next_bank, __ATOMIC_RELEASE);
  __atomic_store_n(&match_kicker_selector_count, count, __ATOMIC_RELEASE);
  __atomic_store_n(&match_kicker_selector_focus, focus, __ATOMIC_RELEASE);
  __atomic_store_n(&match_kicker_selector_open, 1, __ATOMIC_RELEASE);
  __atomic_store_n(&match_kicker_selector_armed, 0, __ATOMIC_RELEASE);
  return 1;
}

// ThinkUnitKickerSelect is present throughout every set piece, even when its
// mobile list task is not created. A custom confirmation emits the exact
// native PadCommand (45) and option byte used by the stock selector.
static uint32_t pes_match_kicker_select_main(void *unit, const void *input,
                                             uint32_t kind) {
  const uint32_t result = match_kicker_select_main_original
                              ? match_kicker_select_main_original(unit, input,
                                                                  kind)
                              : 0;
  if (!unit || !input || kind != 0x61u)
    return result;

  uint32_t action = __atomic_load_n(
      &match_kicker_selector_pending_action, __ATOMIC_ACQUIRE);
  if (action == PES_PAUSE_INPUT_BACK) {
    __atomic_store_n(&match_kicker_selector_pending_action, 0,
                     __ATOMIC_RELEASE);
    match_kicker_selector_close();
    return result;
  }
  if (result) {
    if (__atomic_load_n(&match_kicker_selector_open, __ATOMIC_ACQUIRE) ||
        __atomic_load_n(&match_kicker_selector_armed, __ATOMIC_ACQUIRE))
      match_kicker_selector_close();
    return result;
  }

  if (__atomic_load_n(&match_kicker_selector_armed, __ATOMIC_ACQUIRE)) {
    if (match_kicker_select_is_disp_enable &&
        !match_kicker_select_is_disp_enable(input))
      return result;
    if (!match_kicker_selector_build(input))
      return result;
  }

  if (!__atomic_load_n(&match_kicker_selector_open, __ATOMIC_ACQUIRE))
    return result;
  action = __atomic_exchange_n(&match_kicker_selector_pending_action, 0,
                               __ATOMIC_ACQ_REL);
  if (action != PES_PAUSE_INPUT_DECIDE)
    return result;
  if (match_kicker_select_is_disp_enable &&
      !match_kicker_select_is_disp_enable(input))
    return result;

  const uint32_t count = __atomic_load_n(&match_kicker_selector_count,
                                          __ATOMIC_ACQUIRE);
  uint32_t focus = __atomic_load_n(&match_kicker_selector_focus,
                                   __ATOMIC_ACQUIRE);
  if (!count)
    return result;
  if (focus >= count)
    focus = count - 1u;
  const uint32_t bank =
      __atomic_load_n(&match_kicker_selector_bank, __ATOMIC_ACQUIRE) & 1u;
  const uint32_t order_no =
      match_kicker_selector_players[bank][focus].order_no;
  if (order_no >= 11u)
    return result;

  const uint32_t player_no =
      *(const uint32_t *)((const uint8_t *)input + 36);
  const uint32_t side_offset =
      (uint32_t)(player_no - 11u) < 11u ? 11u : 0u;
  *(uint16_t *)((uint8_t *)unit + 56) = 0;
  *((uint8_t *)unit + 25) = (uint8_t)(order_no + side_offset);
  match_kicker_selector_close();
  return 45u;
}

// This unit owns the small camera/action page shared by set pieces. It remains
// a fallback only for a throw-in variant that has no dedicated pad Main.
static uint32_t pes_match_setplay_camera_main(void *unit, const void *input,
                                              uint32_t kind) {
  const uint32_t result = match_setplay_camera_main_original
                              ? match_setplay_camera_main_original(unit, input,
                                                                    kind)
                              : 0;
  if (unit && input) {
    const uint32_t native_context =
        __atomic_load_n(&match_native_setplay_context, __ATOMIC_ACQUIRE);
    if (native_context == PES_SETPLAY_NONE ||
        native_context == PES_SETPLAY_THROW_IN) {
      match_native_setplay_publish(PES_SETPLAY_THROW_IN);
    }
  }
  return result;
}

uint32_t pes_controller_setplay_context(void) {
  PesControllerSnapshot snapshot;
  pes_controller_surface_snapshot(&snapshot);
  return snapshot.surface == PES_CONTROLLER_SURFACE_SETPLAY
             ? snapshot.setplay_context
             : PES_SETPLAY_NONE;
}

uint32_t pes_controller_setplay_options(void) {
  PesControllerSnapshot snapshot;
  pes_controller_surface_snapshot(&snapshot);
  return snapshot.surface == PES_CONTROLLER_SURFACE_SETPLAY
             ? snapshot.setplay_options
             : 0;
}

int pes_controller_set_piece_selector_active(void) {
  const int active =
      __atomic_load_n(&match_kicker_selector_open, __ATOMIC_ACQUIRE) ||
      __atomic_load_n(&match_kicker_selector_armed, __ATOMIC_ACQUIRE);
  if (!active)
    return 0;
  const uintptr_t owner = __atomic_load_n(
      &match_kicker_selector_button_owner, __ATOMIC_ACQUIRE);
  const uint64_t seen = __atomic_load_n(&match_button_setplay_seen_tick,
                                         __ATOMIC_ACQUIRE);
  if (!owner || !seen ||
      armTicksToNs(armGetSystemTick() - seen) > 750000000ULL) {
    match_kicker_selector_close();
    return 0;
  }
  return 1;
}

uint32_t pes_controller_set_piece_selector_focus(void) {
  return __atomic_load_n(&match_kicker_selector_focus, __ATOMIC_ACQUIRE);
}

uint32_t pes_controller_set_piece_selector_count(void) {
  return __atomic_load_n(&match_kicker_selector_count, __ATOMIC_ACQUIRE);
}

const char *pes_controller_set_piece_selector_title(void) {
  switch (__atomic_load_n(&match_kicker_selector_context,
                          __ATOMIC_ACQUIRE)) {
  case PES_SETPLAY_CORNER:
    return "CORNER KICK TAKER";
  case PES_SETPLAY_THROW_IN:
    return "THROW-IN TAKER";
  case PES_SETPLAY_FREE_KICK:
    return "FREE KICK TAKER";
  default:
    return "SET PIECE TAKER";
  }
}

const char *pes_controller_set_piece_selector_name_at(uint32_t index) {
  const uint32_t count = __atomic_load_n(&match_kicker_selector_count,
                                          __ATOMIC_ACQUIRE);
  if (index >= count)
    return "";
  const uint32_t bank =
      __atomic_load_n(&match_kicker_selector_bank, __ATOMIC_ACQUIRE) & 1u;
  return match_kicker_selector_players[bank][index].name;
}

const char *pes_controller_set_piece_selector_foot_at(uint32_t index) {
  const uint32_t count = __atomic_load_n(&match_kicker_selector_count,
                                          __ATOMIC_ACQUIRE);
  if (index >= count)
    return "";
  const uint32_t bank =
      __atomic_load_n(&match_kicker_selector_bank, __ATOMIC_ACQUIRE) & 1u;
  return match_kicker_selector_players[bank][index].foot;
}

int pes_controller_set_piece_selector_current_at(uint32_t index) {
  const uint32_t count = __atomic_load_n(&match_kicker_selector_count,
                                          __ATOMIC_ACQUIRE);
  if (index >= count)
    return 0;
  const uint32_t bank =
      __atomic_load_n(&match_kicker_selector_bank, __ATOMIC_ACQUIRE) & 1u;
  return match_kicker_selector_players[bank][index].current != 0;
}

const char *pes_controller_set_piece_selector_name(void) {
  return pes_controller_set_piece_selector_name_at(
      pes_controller_set_piece_selector_focus());
}

const char *pes_controller_set_piece_selector_foot(void) {
  return pes_controller_set_piece_selector_foot_at(
      pes_controller_set_piece_selector_focus());
}

void pes_controller_set_piece_selector_move(int direction) {
  if (!direction)
    return;
  pes_controller_set_piece_selector_input(
      direction > 0 ? PES_PAUSE_INPUT_DOWN : PES_PAUSE_INPUT_UP);
}

void pes_controller_set_piece_selector_input(uint32_t action) {
  if (!pes_controller_set_piece_selector_active())
    return;
  if (action == PES_PAUSE_INPUT_BACK) {
    // BACK is purely local: the stock frontend was never created, so this is
    // safe from the input thread and prevents an armed/loading soft-lock.
    match_kicker_selector_close();
    return;
  }
  if (action == PES_PAUSE_INPUT_DECIDE) {
    if (!__atomic_load_n(&match_kicker_selector_open, __ATOMIC_ACQUIRE) ||
        !__atomic_load_n(&match_kicker_selector_count, __ATOMIC_ACQUIRE))
      return;
    __atomic_store_n(&match_kicker_selector_pending_action, action,
                     __ATOMIC_RELEASE);
    return;
  }

  const uint32_t count = __atomic_load_n(&match_kicker_selector_count,
                                          __ATOMIC_ACQUIRE);
  if (!count)
    return;
  uint32_t focus = __atomic_load_n(&match_kicker_selector_focus,
                                   __ATOMIC_ACQUIRE);
  if (focus >= count)
    focus = count - 1u;
  switch (action) {
  case PES_PAUSE_INPUT_UP:
    if (focus)
      focus--;
    break;
  case PES_PAUSE_INPUT_DOWN:
    if (focus + 1u < count)
      focus++;
    break;
  default:
    return;
  }
  __atomic_store_n(&match_kicker_selector_focus, focus, __ATOMIC_RELEASE);
}

// Stadium/Broadcast normally widens its target to include nearby players.
// During a fast keeper throw or a backwards switch that heuristic can retain
// the old group for several frames and leave the ball outside the viewport.
// Keep the stock calculation, but while the ball is travelling quickly force
// its target back to the live BallInfo position when the group target trails
// by a large distance. Slow possession and ordinary camera composition remain
// untouched.
uint32_t pes_inplay_ball_position_broadcast(
    void *camera, const float *blend, const uint32_t *home_away,
    float *target_position, float *zoom, uint32_t active) {
  const uint32_t result = match_ball_position_broadcast_original
                              ? match_ball_position_broadcast_original(
                                    camera, blend, home_away, target_position,
                                    zoom, active)
                              : 0;
  if (!active || !camera || !target_position || !match_ball_info_get_trans)
    return result;

  const uint64_t now = armGetSystemTick();
  const uint64_t sampled_tick = __atomic_load_n(
      &match_camera_ball_seen_tick, __ATOMIC_ACQUIRE);
  // Some camera paths evaluate the same target more than once inside one
  // rendered frame. Sampling BallInfo again only adds game-thread work and can
  // perturb the velocity estimate. One sample per ~8 ms preserves both 60 and
  // 30 fps behaviour while eliminating those duplicate sub-frame calls.
  if (sampled_tick &&
      armTicksToNs(now - sampled_tick) < 8000000ULL)
    return result;

  void *ball_info = NULL;
  memcpy(&ball_info, (const unsigned char *)camera + 408,
         sizeof(ball_info));
  const float *ball = ball_info ? match_ball_info_get_trans(ball_info) : NULL;
  if (!ball || !isfinite(ball[0]) || !isfinite(ball[1]) ||
      !isfinite(ball[2]))
    return result;

  const uint64_t previous_tick = __atomic_exchange_n(
      &match_camera_ball_seen_tick, now, __ATOMIC_ACQ_REL);
  float travel_squared = 0.0f;
  if (match_camera_previous_ball_valid && previous_tick) {
    const float dx = ball[0] - match_camera_previous_ball[0];
    const float dy = ball[1] - match_camera_previous_ball[1];
    const float dz = ball[2] - match_camera_previous_ball[2];
    const uint64_t elapsed_ns = armTicksToNs(now - previous_tick);
    if (elapsed_ns > 0 && elapsed_ns < 250000000ULL) {
      const float frame_scale = 16666667.0f / (float)elapsed_ns;
      travel_squared = (dx * dx + dy * dy + dz * dz) *
                       frame_scale * frame_scale;
    }
  }
  memcpy(match_camera_previous_ball, ball,
         sizeof(match_camera_previous_ball));
  match_camera_previous_ball_valid = 1;

  const float lag_x = target_position[0] - ball[0];
  const float lag_y = target_position[1] - ball[1];
  const float planar_lag_squared = lag_x * lag_x + lag_y * lag_y;
  if (travel_squared >= 0.22f * 0.22f &&
      planar_lag_squared >= 12.0f * 12.0f) {
    // A hard assignment made the whole pitch appear to drop frames even while
    // the renderer reported a stable 60 fps. Preserve the fast-ball recovery,
    // but blend progressively: modest lag gets a gentle correction while an
    // escaped keeper throw converges much more aggressively.
    float correction = 0.20f;
    if (planar_lag_squared >= 24.0f * 24.0f)
      correction = 0.40f;
    if (planar_lag_squared >= 40.0f * 40.0f)
      correction = 0.65f;
    target_position[0] += (ball[0] - target_position[0]) * correction;
    target_position[1] += (ball[1] - target_position[1]) * correction;
    target_position[2] += (ball[2] - target_position[2]) * correction;
  }
  return result;
}

int pes_controller_custom_pause_active(void) {
  return __atomic_load_n(&match_pause_custom_active,
                         __ATOMIC_ACQUIRE) != 0;
}

void pes_controller_custom_pause_input(uint32_t action) {
  if (!pes_controller_custom_pause_active() || action == 0)
    return;
  __atomic_store_n(&match_pause_custom_action, action, __ATOMIC_RELEASE);
}

int pes_controller_pause_camera_active(void) {
  const uint64_t seen = __atomic_load_n(&match_pause_camera_seen_tick,
                                        __ATOMIC_ACQUIRE);
  return seen && armTicksToNs(armGetSystemTick() - seen) <= 500000000ULL;
}

void pes_controller_pause_camera_input(uint32_t action) {
  if (pes_controller_pause_camera_active() && action)
    __atomic_store_n(&match_pause_camera_action, action, __ATOMIC_RELEASE);
}

static uint32_t match_pause_camera_page(void *window, uint32_t *count_out) {
  uint32_t count = 0;
  uint32_t current = 0;
  int32_t *begin = NULL;
  int32_t *end = NULL;
  if (window) {
    memcpy(&begin, (unsigned char *)window + 536, sizeof(begin));
    memcpy(&end, (unsigned char *)window + 544, sizeof(end));
  }
  if (begin && end && end >= begin && (uintptr_t)(end - begin) <= 16)
    count = (uint32_t)(end - begin);

  uint8_t camera_type = 0;
  void *manager = exhibition_tmpdb_manager_get_instance
                      ? exhibition_tmpdb_manager_get_instance()
                      : NULL;
  void *tmpdb_data = NULL;
  if (manager)
    memcpy(&tmpdb_data, (unsigned char *)manager + 72, sizeof(tmpdb_data));
  if (tmpdb_data) {
    uint32_t setting_index = 0;
    memcpy(&setting_index, (unsigned char *)tmpdb_data + 0x18338,
           sizeof(setting_index));
    if (setting_index > 6)
      setting_index = 0;
    memcpy(&camera_type,
           (unsigned char *)tmpdb_data + 0xb78 + setting_index * 15,
           sizeof(camera_type));
  }
  for (uint32_t index = 0; index < count; index++) {
    if ((uint32_t)begin[index] == camera_type) {
      current = index;
      break;
    }
  }
  if (count_out)
    *count_out = count;
  return current;
}

static uint32_t pes_match_pause_camera_update(void *window,
                                               uint32_t pad_status) {
  const uint32_t result = match_pause_camera_update_original
                              ? match_pause_camera_update_original(
                                    window, pad_status)
                              : 0;
  if (!window)
    return result;
  match_pause_camera_window = window;
  __atomic_store_n(&match_pause_camera_seen_tick, armGetSystemTick(),
                   __ATOMIC_RELEASE);
  const uint32_t action = __atomic_exchange_n(
      &match_pause_camera_action, 0, __ATOMIC_ACQ_REL);
  if (action == PES_PAUSE_INPUT_LEFT ||
      action == PES_PAUSE_INPUT_RIGHT) {
    uint32_t count = 0;
    uint32_t current = match_pause_camera_page(window, &count);
    // Some builds expose the camera vector only after the first registry
    // refresh. The native screen still has six camera pages, so retain a safe
    // fallback index instead of dropping the first D-pad press.
    if (!count)
      count = 6;
    if (current >= count)
      current = 0;
    if (count && match_pause_camera_swipe) {
      // The page indicator follows the D-pad direction: Left selects the
      // previous camera and Right selects the next camera.
      const uint32_t next = action == PES_PAUSE_INPUT_LEFT
                                ? (current ? current - 1 : count - 1)
                                : (current + 1) % count;
      match_pause_camera_swipe(window, current, next);
      debugPrintf("input: pause camera swipe %u -> %u (count=%u)\n",
                  current, next, count);
    }
  } else if (action == PES_PAUSE_INPUT_BACK &&
             match_pause_camera_footer) {
    __atomic_store_n(&match_pause_camera_seen_tick, 0, __ATOMIC_RELEASE);
    match_pause_camera_window = NULL;
    match_pause_camera_footer(window, 1);
  }
  return result;
}

static void match_pause_dispatch_event(void *window, const char *name) {
  if (!window || !name || !match_pause_exec_event_decide)
    return;
  const size_t length = strlen(name);
  if (length > 22)
    return;
  // Cobra uses libc++'s 24-byte short-string layout here: the low bit is the
  // long-string tag and the remaining first byte stores twice the length.
  unsigned char event_name[24] = {0};
  event_name[0] = (unsigned char)(length << 1);
  memcpy(event_name + 1, name, length);
  match_pause_exec_event_decide(window, event_name);
}

static void match_result_dispatch_event(void *window, const char *name) {
  if (!window || !name || !match_result_exec_event_decide)
    return;
  const size_t length = strlen(name);
  if (length > 22)
    return;
  unsigned char event_name[24] = {0};
  event_name[0] = (unsigned char)(length << 1);
  memcpy(event_name + 1, name, length);
  match_result_exec_event_decide(window, event_name);
}

void pes_controller_result_input(uint32_t action) {
  if (action)
    __atomic_store_n(&match_result_input_action, action, __ATOMIC_RELEASE);
}

static void match_result_process_controller_input(void *window) {
  const uint32_t action = __atomic_exchange_n(
      &match_result_input_action, 0, __ATOMIC_ACQ_REL);
  if (!window)
    return;
  const uint32_t context =
      __atomic_load_n(&virtual_cursor_context, __ATOMIC_ACQUIRE);
  // The final MatchResultMainMenu intentionally has no tiles. Its remaining
  // native Next footer was unreliable through a coordinate-only synthetic
  // tap after the tiles were removed. Dispatch footer key 0 on the result UI
  // thread so the stock frontend selects next/onlineNext and enters its own
  // control-wait state exactly as a real footer tap would.
  const int final_next = action == PES_PAUSE_INPUT_DECIDE &&
                         context == PES_VIRTUAL_CURSOR_FULL_TIME;
  if (action != PES_PAUSE_INPUT_BACK && !final_next)
    return;
  __atomic_store_n(&match_postmatch_custom_active, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_result_exit_requested, 1, __ATOMIC_RELEASE);
  __atomic_store_n(&virtual_cursor_context, PES_VIRTUAL_CURSOR_NONE,
                   __ATOMIC_RELEASE);
  match_result_window = NULL;
  if (final_next && match_result_footer_touch)
    match_result_footer_touch(window, 0u);
  else
    match_result_dispatch_event(window, "match_topmenu");
}

int pes_controller_custom_postmatch_active(void) {
  return __atomic_load_n(&match_postmatch_custom_active,
                         __ATOMIC_ACQUIRE) != 0;
}

void pes_controller_custom_postmatch_input(uint32_t action) {
  if (pes_controller_custom_postmatch_active() && action)
    __atomic_store_n(&match_postmatch_custom_action, action,
                     __ATOMIC_RELEASE);
}

static void match_postmatch_go_home(void *window) {
  __atomic_store_n(&match_postmatch_custom_active, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_postmatch_custom_action, 0, __ATOMIC_RELEASE);
  match_postmatch_window = NULL;
  match_result_dispatch_event(window, "match_topmenu");
}

static void match_postmatch_process_input(void *window) {
  const uint32_t action = __atomic_exchange_n(
      &match_postmatch_custom_action, 0, __ATOMIC_ACQ_REL);
  if (!action)
    return;
  const uint32_t page = __atomic_load_n(&match_postmatch_custom_page,
                                         __ATOMIC_ACQUIRE);
  if (page == MATCH_POSTMATCH_PAGE_ROOT) {
    uint32_t focus = __atomic_load_n(&match_postmatch_custom_focus,
                                     __ATOMIC_ACQUIRE) & 1u;
    if (action == PES_PAUSE_INPUT_UP || action == PES_PAUSE_INPUT_DOWN) {
      __atomic_store_n(&match_postmatch_custom_focus, focus ^ 1u,
                       __ATOMIC_RELEASE);
    } else if (action == PES_PAUSE_INPUT_BACK ||
               (action == PES_PAUSE_INPUT_DECIDE && focus == 1)) {
      match_postmatch_go_home(window);
    } else if (action == PES_PAUSE_INPUT_DECIDE && focus == 0) {
      match_gameplan_refresh_players(1);
      __atomic_store_n(&match_gameplan_focus, 0, __ATOMIC_RELEASE);
      __atomic_store_n(&match_postmatch_custom_page,
                       MATCH_POSTMATCH_PAGE_GAMEPLAN, __ATOMIC_RELEASE);
    }
    return;
  }
  if (page == MATCH_POSTMATCH_PAGE_GAMEPLAN) {
    uint32_t focus = match_gameplan_focus;
    if (action == PES_PAUSE_INPUT_UP) {
      match_gameplan_focus = focus ? focus - 1 : 2;
    } else if (action == PES_PAUSE_INPUT_DOWN) {
      match_gameplan_focus = (focus + 1) % 3;
    } else if (action == PES_PAUSE_INPUT_BACK ||
               (action == PES_PAUSE_INPUT_DECIDE && focus == 2)) {
      __atomic_store_n(&match_postmatch_custom_page,
                       MATCH_POSTMATCH_PAGE_ROOT, __ATOMIC_RELEASE);
      __atomic_store_n(&match_postmatch_custom_focus, 0,
                       __ATOMIC_RELEASE);
    } else if (action == PES_PAUSE_INPUT_DECIDE && focus == 0) {
      match_gameplan_focus = 0;
      __atomic_store_n(&match_postmatch_custom_page,
                       MATCH_POSTMATCH_PAGE_SUBSTITUTION,
                       __ATOMIC_RELEASE);
    } else if (action == PES_PAUSE_INPUT_DECIDE && focus == 1) {
      match_gameplan_focus = 0;
      __atomic_store_n(&match_postmatch_custom_page,
                       MATCH_POSTMATCH_PAGE_FORMATION, __ATOMIC_RELEASE);
    }
    return;
  }
  if (page == MATCH_POSTMATCH_PAGE_SUBSTITUTION) {
    const uint32_t focus = match_gameplan_focus & 1u;
    if (action == PES_PAUSE_INPUT_UP || action == PES_PAUSE_INPUT_DOWN) {
      match_gameplan_focus = focus ^ 1u;
    } else if (action == PES_PAUSE_INPUT_LEFT ||
               action == PES_PAUSE_INPUT_RIGHT) {
      const int direction = action == PES_PAUSE_INPUT_RIGHT ? 1 : -1;
      uint32_t *selection = focus == 0 ? &match_gameplan_starter_index
                                       : &match_gameplan_bench_index;
      const uint32_t count = focus == 0 ? match_gameplan_starter_count
                                         : match_gameplan_bench_count;
      if (count)
        *selection = direction > 0 ? (*selection + 1) % count
                                   : (*selection ? *selection - 1
                                                 : count - 1);
    } else if (action == PES_PAUSE_INPUT_DECIDE) {
      match_gameplan_swap_selected();
    } else if (action == PES_PAUSE_INPUT_BACK) {
      match_gameplan_focus = 0;
      __atomic_store_n(&match_postmatch_custom_page,
                       MATCH_POSTMATCH_PAGE_GAMEPLAN, __ATOMIC_RELEASE);
    }
    return;
  }
  if (page == MATCH_POSTMATCH_PAGE_FORMATION) {
    if (action == PES_PAUSE_INPUT_LEFT ||
        action == PES_PAUSE_INPUT_RIGHT) {
      match_gameplan_tactics ^= 1u;
    } else if (action == PES_PAUSE_INPUT_DECIDE) {
      if (match_gameplan_squad_data && match_squad_data_set_tactics) {
        match_squad_data_set_tactics(match_gameplan_squad_data,
                                      match_gameplan_tactics);
        if (matchplan_squad_save)
          matchplan_squad_save();
      }
    } else if (action == PES_PAUSE_INPUT_BACK) {
      match_gameplan_focus = 1;
      __atomic_store_n(&match_postmatch_custom_page,
                       MATCH_POSTMATCH_PAGE_GAMEPLAN, __ATOMIC_RELEASE);
    }
  }
}

static void pes_match_result_update(void *window) {
  if (match_result_update_original)
    match_result_update_original(window);
  if (window) {
    match_result_window = window;
    __atomic_store_n(&match_result_seen_tick, armGetSystemTick(),
                     __ATOMIC_RELEASE);
    // MatchResultMainMenu is the second/final result page. Refresh FULL_TIME
    // unconditionally here; checking the previous cursor context made a
    // single stale gameplay poll permanently disable A and its helper.
    if (!__atomic_load_n(&match_result_exit_requested, __ATOMIC_ACQUIRE))
      pes_virtual_cursor_activate(PES_VIRTUAL_CURSOR_FULL_TIME, 56753, 61734);
  }
  match_result_process_controller_input(window);
  if (window && pes_controller_custom_postmatch_active()) {
    match_postmatch_window = window;
    match_postmatch_process_input(window);
  }
}

uintptr_t pes_match_pause_update_entry(void *window, uint32_t pad_status) {
  (void)pad_status;
  if (window) {
    __atomic_store_n(&match_pause_seen_tick, armGetSystemTick(),
                     __ATOMIC_RELEASE);
    __atomic_store_n(&match_pause_custom_active, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&match_pause_custom_action, 0, __ATOMIC_RELEASE);
    const uint64_t gameplan_seen = __atomic_load_n(&match_gameplan_seen_tick,
                                                   __ATOMIC_ACQUIRE);
    if (!gameplan_seen ||
        armTicksToNs(armGetSystemTick() - gameplan_seen) > 500000000ULL) {
      // A live Pause root is not the Game Plan child. Clear any route left by
      // the previous visit before drawing the native Back helper.
      __atomic_store_n(&match_gameplan_pause_route, 0, __ATOMIC_RELEASE);
      pes_virtual_cursor_activate(PES_VIRTUAL_CURSOR_PAUSE, 32768, 32768);
    }
    if (__atomic_exchange_n(&match_pause_back_requested, 0,
                            __ATOMIC_ACQ_REL) &&
        match_pause_pad_event_back)
      match_pause_pad_event_back(window);
  }
  return match_pause_update_resume;
}

void pes_controller_pause_back_request(void) {
  if (pes_controller_virtual_cursor_context() == PES_VIRTUAL_CURSOR_PAUSE)
    __atomic_store_n(&match_pause_back_requested, 1, __ATOMIC_RELEASE);
}

static void pes_match_pause_destroyed(void *window) {
  // Keep the last Pause heartbeat briefly. The native Pause object is
  // destroyed before its MyClubSquadEdit child receives the first Update, so
  // clearing this here made that child look like the pre-match Game Plan and
  // left an A helper at the bottom-right. The normal 5 s age check in the child
  // safely expires this route after returning to gameplay.
  __atomic_store_n(&match_pause_back_requested, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_pause_custom_active, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_pause_custom_action, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_pause_custom_focus, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&match_pause_custom_page, MATCH_PAUSE_PAGE_ROOT,
                   __ATOMIC_RELEASE);
  match_gameplan_squad_data = NULL;
  match_gameplan_player_count = 0;
  uint32_t expected = PES_VIRTUAL_CURSOR_PAUSE;
  const int cleared = __atomic_compare_exchange_n(
      &virtual_cursor_context, &expected, PES_VIRTUAL_CURSOR_NONE, 0,
      __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE);
  debugPrintf("input: MatchPause destroyed window=%p cursor_cleared=%d\n",
              window, cleared);
}

uintptr_t pes_match_pause_d1_entry(void *window) {
  pes_match_pause_destroyed(window);
  return match_pause_d1_resume;
}

uintptr_t pes_match_pause_d0_entry(void *window) {
  pes_match_pause_destroyed(window);
  return match_pause_d0_resume;
}

uintptr_t pes_match_result_full_entry(void *result, const char *name,
                                       uint32_t modal) {
  (void)name;
  (void)modal;
  if (result) {
    __atomic_store_n(&match_result_exit_requested, 0, __ATOMIC_RELEASE);
    match_result_window = result;
    __atomic_store_n(&match_result_seen_tick, armGetSystemTick(),
                     __ATOMIC_RELEASE);
    void *listener = match_listener_instance ? *match_listener_instance : NULL;
    uint8_t final_result = 0;
    if (listener)
      memcpy(&final_result, (unsigned char *)listener + 0x18ff3,
             sizeof(final_result));
    if (final_result) {
      // Final result keeps the native background but no longer owns a custom
      // post-match frontend. The result tile list is removed at init time;
      // B still returns directly to the Top Menu through result input.
      __atomic_store_n(&match_postmatch_custom_active, 0, __ATOMIC_RELEASE);
      // Keep the native bottom-right Next footer reachable with A while the
      // result tile list itself stays hidden. B is handled as Top Menu.
      pes_virtual_cursor_activate(PES_VIRTUAL_CURSOR_FULL_TIME, 56753, 61734);
    } else {
      __atomic_store_n(&match_postmatch_custom_active, 0, __ATOMIC_RELEASE);
      pes_virtual_cursor_activate(PES_VIRTUAL_CURSOR_FULL_TIME, 32768, 32768);
    }
  }
  return match_result_full_resume;
}

uintptr_t pes_match_result_half_entry(void *result, const char *name,
                                       uint32_t modal) {
  (void)name;
  (void)modal;
  if (result) {
    match_result_window = result;
    __atomic_store_n(&match_result_seen_tick, armGetSystemTick(),
                     __ATOMIC_RELEASE);
    pes_virtual_cursor_activate(PES_VIRTUAL_CURSOR_HALF_TIME, 32768, 32768);
  }
  return match_result_half_resume;
}

uintptr_t pes_match_result_half_update_entry(void *result) {
  if (result) {
    match_result_window = result;
    __atomic_store_n(&match_result_seen_tick, armGetSystemTick(),
                     __ATOMIC_RELEASE);
    pes_virtual_cursor_activate(PES_VIRTUAL_CURSOR_HALF_TIME, 32768, 32768);
    match_result_process_controller_input(result);
  }
  return match_result_half_update_resume;
}

void pes_main_menu_graphics_destroyed(void) {
  if (!__atomic_exchange_n(&main_menu_graphics_active, 0,
                           __ATOMIC_ACQ_REL))
    return;
  if (main_menu_match_page && exhibition_node_set_visible)
    exhibition_node_set_visible(main_menu_match_page, 1, 2);
  __atomic_store_n(&main_menu_controller_active, 1, __ATOMIC_RELEASE);
  __atomic_store_n(&virtual_cursor_context, PES_VIRTUAL_CURSOR_NONE,
                   __ATOMIC_RELEASE);
  main_menu_focus_painted = 0;
  debugPrintf("UE4 menu: graphics settings closed parent_page=%p restored=%u\n",
              main_menu_match_page, main_menu_match_page != NULL);
}

uintptr_t pes_main_menu_graphics_d1_entry(void *object) {
  (void)object;
  pes_main_menu_graphics_destroyed();
  return pes_main_menu_graphics_d1_resume;
}

uintptr_t pes_main_menu_graphics_d0_entry(void *object) {
  (void)object;
  pes_main_menu_graphics_destroyed();
  return pes_main_menu_graphics_d0_resume;
}

// Entry hook for ScreenTapManager::Update. ControlModeInfo is the original x2
// argument here, so its methods provide authoritative offense/defense context
// even while every ButtonObject is idle.
uintptr_t pes_mobile_screen_tap_entry(void *control_mode_ptr) {
  const uint64_t now = armGetSystemTick();
  const uint64_t previous_seen =
      __atomic_load_n(&mobile_control_seen_tick, __ATOMIC_ACQUIRE);
  const int resumed =
      !previous_seen || armTicksToNs(now - previous_seen) > 500000000ULL;
  int mode = PES_MOBILE_CONTROL_UNKNOWN;
  if (control_mode_ptr && mobile_is_mode_defense &&
      mobile_is_mode_defense(control_mode_ptr))
    mode = PES_MOBILE_CONTROL_DEFENSE;
  else if (control_mode_ptr && mobile_is_mode_offense &&
           mobile_is_mode_offense(control_mode_ptr))
    mode = PES_MOBILE_CONTROL_OFFENSE;
  __atomic_store_n(&mobile_control_mode, (uint32_t)mode, __ATOMIC_RELEASE);
  __atomic_store_n(&mobile_control_seen_tick, now, __ATOMIC_RELEASE);
  // MatchSetup owns normal rule commits. Reassert only when ScreenTap resumes
  // after a lifecycle gap (half/extra-time, suspend or menu hand-off). Calling
  // four native setters plus debug logging on every rendered frame caused the
  // visible 60-fps pacing spikes reported on hardware.
  if (resumed &&
      __atomic_load_n(&exhibition_match_settings_armed, __ATOMIC_ACQUIRE))
    exhibition_apply_match_settings(NULL);
  static int previous_mode = -1;
  uint32_t generation =
      __atomic_load_n(&mobile_control_generation, __ATOMIC_ACQUIRE);
  if (resumed || mode != previous_mode)
    generation = __atomic_add_fetch(&mobile_control_generation, 1,
                                    __ATOMIC_RELEASE);
  if (mode != previous_mode && mobile_context_log_count < 24) {
    mobile_context_log_count++;
    debugPrintf("input: ScreenTapManager entry control=%p mode=%d "
                "generation=%u\n",
                control_mode_ptr, mode, generation);
  }
  previous_mode = mode;
  return mobile_screen_tap_entry_resume;
}

// The Android/mobile match initializer calls SetPadNo(1), which this binary
// deliberately collapses to -1. Command::ExecCommand then skips the complete
// real-pad path for that cursor. When Switch HID is present, attach that primary
// cursor to port 0; preserve the game's original behavior for every other call.
static void pes_cursor_set_pad_no(void *cursor_ptr, uint32_t requested) {
  if (!cursor_ptr)
    return;
  // Keep the primary cursor attached to port 0 even before the first HID poll;
  // a disconnected Switch pad simply contributes no state to the game.
  const int connected = cobra_controller_is_connected();
  const int32_t pad_no = requested == 1 ? 0 : (requested ? -1 : 0);
  memcpy((unsigned char *)cursor_ptr + 16, &pad_no, sizeof(pad_no));
  if (cursor_pad_log_count < 16) {
    cursor_pad_log_count++;
    debugPrintf("input: CursorData::SetPadNo cursor=%p requested=%u "
                "connected=%d stored=%d\n",
                cursor_ptr, requested, connected, pad_no);
  }
}

// Mobile setup also disables all real-pad slots. Keep port 0 enabled only while
// Ryujinx/libnx reports a controller, leaving the other seven ports and the
// no-controller touch-only behavior unchanged.
static void pes_set_real_pad_is_enable(void *pad_input_ptr, uint32_t pad_no,
                                       uint32_t requested_enable) {
  if (!pad_input_ptr || pad_no > 7)
    return;
  const int connected = cobra_controller_is_connected();
  const uint8_t enabled =
      (requested_enable != 0 || pad_no == 0) ? 1 : 0;
  *((unsigned char *)pad_input_ptr + 0x86ca0 + pad_no) = enabled;
  if ((pad_no == 0 || requested_enable) && real_pad_log_count < 24) {
    real_pad_log_count++;
    debugPrintf("input: PadInput::SetRealPadIsEnable object=%p pad=%u "
                "requested=%u connected=%d stored=%u\n",
                pad_input_ptr, pad_no, requested_enable != 0, connected,
                enabled);
  }
}

// Called on cobra's game thread at the end of Pad::Update's clear/touch phase,
// immediately before the game computes clicked/released/repeated edges.
uintptr_t cobra_pad_apply_input(void *pad_ptr) {
  unsigned char *pad = pad_ptr;
  if (pad) {
    const uint64_t packed =
        __atomic_load_n(&cobra_pad_input, __ATOMIC_ACQUIRE);
    uint32_t buttons = (uint32_t)packed;
    int32_t x = (int16_t)(packed >> 32);
    int32_t y = (int16_t)(packed >> 48);
    int32_t pad_id;
    uint32_t previous;
    uint32_t current;
    memcpy(&pad_id, pad + 4, sizeof(pad_id));
    memcpy(&previous, pad + 12, sizeof(previous));
    memcpy(&current, pad + 16, sizeof(current));
    // The tile-2 experiment is intentionally one-player. Pad::Update runs for
    // multiple Cobra pad objects, so explicitly prevent player-1 HID state
    // from leaking into any internal port other than pad zero.
    if (pes_controller_native_pad_lab_active() && pad_id != 0) {
      buttons = 0;
      x = 0;
      y = 0;
    }
    const uint32_t current_before = current;
    current |= buttons;
    memcpy(pad + 16, &current, sizeof(current));
    for (int index = 0; index < 16; index++) {
      const int32_t value = buttons & (1u << index) ? 0x7fff : 0;
      memcpy(pad + 140 + index * 4, &value, sizeof(value));
    }
    const int32_t directions[4] = {
        y < 0 ? -y : 0,
        y > 0 ? y : 0,
        x < 0 ? -x : 0,
        x > 0 ? x : 0,
    };
    memcpy(pad + 140 + 16 * 4, directions, sizeof(directions));
    pes_main_menu_pad_event(current, previous);
    pes_exhibition_search_pad_event(current, previous);
    if (__atomic_load_n(&main_menu_info_popup, __ATOMIC_ACQUIRE) !=
            MAIN_MENU_INFO_CLOSED ||
        __atomic_load_n(&main_menu_video_settings_open, __ATOMIC_ACQUIRE)) {
      // Navigation was consumed by the custom overlay. Keep its buttons and
      // axes away from the four native tiles underneath the modal.
      current &= ~buttons;
      memcpy(pad + 16, &current, sizeof(current));
      const int32_t zero = 0;
      for (int index = 0; index < 20; index++)
        memcpy(pad + 140 + index * 4, &zero, sizeof(zero));
    }
    if (packed != cobra_pad_last_applied && cobra_pad_apply_log_count < 64) {
      cobra_pad_apply_log_count++;
      debugPrintf("input: cobra apply pad=%p id=%d packed=0x%llx "
                  "buttons=0x%x previous=0x%x current=0x%x->0x%x "
                  "axis=%d,%d raw=%d,%d,%d,%d resume=%p\n",
                  pad_ptr, pad_id, (unsigned long long)packed, buttons,
                  previous, current_before, current, x, y, directions[0],
                  directions[1], directions[2], directions[3],
                  (void *)cobra_pad_update_resume);
      cobra_pad_last_applied = packed;
    }
  }
  return cobra_pad_update_resume;
}

extern void cobra_pad_update_hook(void);
extern void pes_match_replay_check_skip_hook(void);
extern void pes_match_goal_demo_update_hook(void);
extern void pes_match_goal_demo_init_hook(void);
extern void pes_match_tutorial_guide_update_hook(void);
extern void pes_match_flow_check_skip_fix_demo_hook(void);
extern void pes_match_pause_update_hook(void);
extern void pes_match_squad_edit_update_hook(void);
extern void pes_match_team_stats_update_hook(void);
extern void pes_match_pause_d1_hook(void);
extern void pes_match_pause_d0_hook(void);
extern void pes_match_result_full_hook(void);
extern void pes_match_result_half_hook(void);
extern void pes_match_result_half_update_hook(void);
extern void pes_exhibition_match_setup_data_hook(void);
extern uint32_t pes_inplay_ball_position_broadcast_original(
    void *camera, const float *blend, const uint32_t *home_away,
    float *target_position, float *zoom, uint32_t active);
extern void pes_main_menu_graphics_d1_hook(void);
extern void pes_main_menu_graphics_d0_hook(void);
extern void pes_mobile_screen_tap_entry_hook(void);
extern void pes_exhibition_flow_create_hook(void);
extern void pes_exhibition_tutorial_main_hook(void);
extern void pes_exhibition_strategy_main_hook(void);
extern void pes_exhibition_strategy_created_hook(void);
extern void pes_exhibition_training_touch_hook(void);
extern void pes_exhibition_training_list_hook(void);
extern void pes_exhibition_training_child_hook(void);
extern void pes_exhibition_training_footer_hook(void);
extern void pes_exhibition_search_post_hook(void);
extern void pes_exhibition_search_user_name_hook(void);
extern void pes_exhibition_search_task_ready_hook(void);
extern void pes_exhibition_filter_teams_hook(void);
extern void pes_exhibition_string_get_hook(void);
extern void pes_title_prompt_ready_hook(void);
extern void pes_main_menu_simplify_hook(void);
extern void pes_main_menu_selected_hook(void);
extern void ue4_tickrate_clamp_hook(void);
extern void pes_virtual_pad_update_original(void *virtual_pad);

uintptr_t ue4_tickrate_clamp(void *engine) {
  (void)engine;
  return ue4_tickrate_resume;
}

// Visibility is part of the mobile control state: forcing these MovieClips
// hidden also prevents their ButtonObjects from accepting the synthetic touch
// stream. Keep every clip visible and interactive, but tint the six persistent
// pieces once after construction to a nearly transparent alpha.
void pes_virtual_pad_update_info(void *virtual_pad) {
  static void *tinted_clips[6];
  static const uint32_t clip_offsets[6] = {72, 80, 88, 96, 104, 112};

  pes_virtual_pad_update_original(virtual_pad);
  if (!virtual_pad || !virtual_pad_set_color)
    return;
  for (unsigned int index = 0; index < 6; index++) {
    void *clip = NULL;
    memcpy(&clip, (const uint8_t *)virtual_pad + clip_offsets[index],
           sizeof(clip));
    if (clip && clip != tinted_clips[index]) {
      // The first two clips are the virtual movement-stick layers.  Keep them
      // interactive but completely transparent; 2% alpha is still visible on
      // an OLED panel.  Preserve the established action-button tint.
      const float alpha = index < 2u ? 0.0f : 0.02f;
      virtual_pad_set_color(clip, 1.0f, 1.0f, 1.0f, alpha);
      tinted_clips[index] = clip;
    }
  }
}

static void pes_match_visual_model_action(void *manager) {
  // Always keep native updates/registry locks/lifecycle running. Only suppress
  // the resulting assist draw objects; power/name/2D HUD paths are untouched.
  if (match_visual_model_action_original)
    match_visual_model_action_original(manager);
  pes_hide_pitch_assists(manager,
      __atomic_load_n(&config.player_cursor_show, __ATOMIC_ACQUIRE),
      match_visual_model_set_disp);
}

static void patch_checked_u32(uintptr_t address, uint32_t expected,
                              uint32_t replacement, const char *name) {
  const uint32_t found = *(const uint32_t *)address;
  if (found != expected)
    fatal_error("Unexpected %s instruction at %p: 0x%08x (expected "
                "0x%08x)",
                name, (void *)address, found, expected);
  *(uint32_t *)address = replacement;
}

static uintptr_t *find_vtable_method_slot(so_module *module,
                                           const char *vtable_symbol,
                                           uintptr_t method_runtime,
                                           uint32_t slot_limit) {
  const uintptr_t vtable = so_find_addr(module, vtable_symbol);
  if (!vtable || !method_runtime)
    return NULL;
  for (uint32_t index = 2; index < slot_limit; index++) {
    uintptr_t *slot = (uintptr_t *)(vtable + index * sizeof(uintptr_t));
    if (*slot == method_runtime)
      return slot;
  }
  return NULL;
}

static ObjectInitializerArrayState *find_array_state(Ue4Array *array) {
  ObjectInitializerArrayState *empty = NULL;
  for (int i = 0; i < OBJECT_INITIALIZER_STATE_SLOTS; i++) {
    ObjectInitializerArrayState *state = &object_initializer_states[i];
    Ue4Array *key = __atomic_load_n(&state->array, __ATOMIC_ACQUIRE);
    if (key == array)
      return state;
    if (!key && !empty)
      empty = state;
  }

  if (empty) {
    Ue4Array *expected = NULL;
    if (__atomic_compare_exchange_n(&empty->array, &expected, array, 0,
                                    __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE))
      return empty;
    if (expected == array)
      return empty;
  }
  return NULL;
}

static int fields_are_sane(const Ue4Array *array, int32_t old_num) {
  return old_num >= 0 && old_num < OBJECT_INITIALIZER_MAX_ITEMS &&
         array->num == old_num + 1 && array->max >= 0 &&
         array->max < OBJECT_INITIALIZER_MAX_ITEMS;
}

// Returns the old element index so the assembly shim can repair callers that
// keep it in x19 across ResizeGrow.
int32_t ue4_object_initializer_resize_hook_c(Ue4Array *array,
                                             int32_t old_num) {
  ObjectInitializerArrayState *state = find_array_state(array);
  const void *incoming_data = array->data;
  const int32_t incoming_num = array->num;
  const int32_t incoming_max = array->max;
  const int sane = fields_are_sane(array, old_num);

  int32_t safe_old_num = old_num;
  if (!sane) {
    // The observed crash had both Num and the high half of Data overwritten.
    // Resetting the transient initializer stack is safer than honoring an
    // index that would request hundreds of MiB and write far out of bounds.
    safe_old_num = 0;
    array->num = 1;
    debugPrintf("UE4 ResizeGrow: CORRUPT array=%p data=%p num=%d max=%d "
                "old=%d; reset old=0\n",
                array, incoming_data, incoming_num, incoming_max, old_num);
  }

  void *old_data = NULL;
  int32_t old_capacity = 0;
  if (state && state->data) {
    old_data = state->data;
    old_capacity = state->max;
    if (incoming_data != state->data)
      debugPrintf("UE4 ResizeGrow: repaired Data %p -> %p for array=%p\n",
                  incoming_data, state->data, array);
  } else if (sane && incoming_data &&
             (uintptr_t)incoming_data >= 0x100000000ULL) {
    old_data = (void *)incoming_data;
    old_capacity = incoming_max;
  }

  int32_t required = array->num;
  int32_t new_max = old_capacity > 0
                        ? old_capacity + old_capacity / 2 + 16
                        : 4;
  if (new_max < required)
    new_max = required;
  if (new_max > OBJECT_INITIALIZER_MAX_ITEMS)
    fatal_error("UE4 object-initializer array exceeded safe capacity: %d",
                new_max);

  void *new_data = ue4_fmemory_malloc((uint64_t)new_max * sizeof(void *), 0);
  if (!new_data)
    fatal_error("UE4 object-initializer allocation failed: %d items", new_max);
  memset(new_data, 0, (size_t)new_max * sizeof(void *));

  int32_t copy_count = safe_old_num;
  if (copy_count > old_capacity)
    copy_count = old_capacity;
  if (old_data && copy_count > 0)
    memcpy(new_data, old_data, (size_t)copy_count * sizeof(void *));

  array->data = new_data;
  array->max = new_max;
  if (state) {
    state->data = new_data;
    state->max = new_max;
    state->growths++;
  }

  debugPrintf("UE4 ResizeGrow: array=%p old=%d num=%d max=%d -> data=%p "
              "max=%d growth=%u\n",
              array, safe_old_num, array->num, incoming_max, new_data, new_max,
              state ? state->growths : 0);
  return safe_old_num;
}

extern void ue4_object_initializer_resize_hook(void);

#include "friend_press.inc"
#include "native_pad_lab.inc"

void install_ue4_hooks(so_module *module) {
  install_friend_press_prototype(module);
  install_native_pad_lab(module);
  // The offline bundle already seeds the profile, club, coach, and squad.
  // Retain ModeEntry's command handshake (states 0..2), then send its completed
  // state 5 directly to the normal "proceed" exit. This removes the obsolete
  // season/profile and onboarding screens from start-up without bypassing the
  // login response that populates ParameterMyClub.
  const char *mode_entry_symbol =
      "_ZN4menu19MyClubFlowModeEntry4MainEv";
  const uintptr_t mode_entry_main =
      so_find_addr(module, mode_entry_symbol);
  patch_checked_u32(mode_entry_main + 0x23c,
                    0xf9411a68, // ldr x8, [x19, #560]
                    0x52800268, // mov w8, #19 (proceed)
                    "MyClub ModeEntry direct-menu state");
  patch_checked_u32(mode_entry_main + 0x240,
                    0xf9411669, // ldr x9, [x19, #552]
                    0x14000067, // b state store/return
                    "MyClub ModeEntry direct-menu branch");
  debugPrintf("UE4 patch: completed MyClub ModeEntry goes directly to menu "
              "backing=%p\n",
              (void *)(mode_entry_main + 0x23c));

  // UE4's mobile quality path can return a 5-FPS effective max tick rate on
  // Horizon. Rendering itself is fast, but
  // UpdateTimeAndHandleMaxTickRate then sleeps about 180 ms every gameplay
  // frame. The assembly hook clamps only the final positive effective rate
  // below 30; zero/unlimited and normal 30/60-FPS settings remain untouched.
  const char *tickrate_symbol =
      "_ZN7UEngine30UpdateTimeAndHandleMaxTickRateEv";
  const uintptr_t tickrate_backing = so_find_addr(module, tickrate_symbol);
  const uintptr_t tickrate_runtime = so_find_addr_rx(module, tickrate_symbol);
  const uintptr_t tickrate_site = tickrate_backing + 0x2bc;
  static const uint32_t expected_tickrate_words[4] = {
      0x395e0268, // ldrb w8, [x19, #1920]
      0x36300048, // tbz w8, #6, +8
      0xbd478660, // ldr s0, [x19, #1924]
      0x1e202008, // fcmp s0, #0.0
  };
  if (memcmp((void *)tickrate_site, expected_tickrate_words,
             sizeof(expected_tickrate_words)) != 0)
    fatal_error("Unexpected UEngine tick-rate limiter bytes at %p",
                (void *)tickrate_site);
  ue4_tickrate_resume = tickrate_runtime + 0x2cc;
  hook_arm64(tickrate_site, (uintptr_t)&ue4_tickrate_clamp_hook);
  debugPrintf("UE4 hook: fixed tick-rate clamp backing=%p runtime=%p "
              "hook=%p resume=%p\n",
              (void *)tickrate_site, (void *)(tickrate_runtime + 0x2bc),
              ue4_tickrate_clamp_hook, (void *)ue4_tickrate_resume);

  // Reuse the first/tutorial match builder as a self-contained offline
  // exhibition bootstrap. The stock routine already copies both selected
  // clubs, coaches, formations and every roster player from CommonWork into
  // tmpdb::Match. Normally it is gated by the one-time tutorial save flag,
  // chooses team 108 vs team 100 through two availability booleans, and sets
  // game mode 0x45 (which enters TutorialLoadFirst). The FactoryMobile hook
  // below routes the eFootball tile to MyClub/TutorialMatch; these narrowly
  // checked patches make that node always build Barcelona (108) vs Madrid
  // Chamartin B (109), emit proceed_tutorial, and let Match/MatchSetup enter
  // the ordinary offline MatchIdle path through generic game mode 5. The
  // stock settings dispatcher does not cover mode 5, so its call is replaced
  // with the self-contained SetMatchSettingsBase initializer below.
  const char *tutorial_match_symbol =
      "_ZN4menu23MyClubFlowTutorialMatch4MainEv";
  const uintptr_t tutorial_main =
      so_find_addr(module, tutorial_match_symbol);
  const uintptr_t tutorial_main_runtime =
      so_find_addr_rx(module, tutorial_match_symbol);
  exhibition_flow_listener_instance =
      (void *)so_find_addr_rx(module,
                             "_ZN4flow12FlowListener11s_pInstanceE");
  exhibition_flow_direct_set =
      (void *)so_find_addr_rx(module,
                             "_ZN4flow14FlowTransition9DirectSetEPKc");

  static const uint32_t expected_tutorial_main_entry[4] = {
      0xd101c3ff, // sub sp, sp, #0x70
      0xa9045bf7, // stp x23, x22, [sp, #64]
      0xa90553f5, // stp x21, x20, [sp, #80]
      0xa9067bf3, // stp x19, x30, [sp, #96]
  };
  if (memcmp((void *)tutorial_main, expected_tutorial_main_entry,
             sizeof(expected_tutorial_main_entry)) != 0)
    fatal_error("Unexpected MyClubFlowTutorialMatch::Main entry at %p",
                (void *)tutorial_main);

  patch_checked_u32(tutorial_main + 0x6c,
                    0x1a9f1128, // csel w8, w9, wzr, ne
                    0x2a0903e8, // mov w8, w9 (team 108 << 14)
                    "TutorialMatch home-team");
  patch_checked_u32(tutorial_main + 0x94,
                    0x7100011f, // cmp w8, #0
                    0x11409288, // add w8, w20, #0x24, lsl #12
                    "TutorialMatch away-team constant");
  patch_checked_u32(tutorial_main + 0x98,
                    0x1a9f1288, // csel w8, w20, wzr, ne
                    0xd503201f, // nop; w8 is team 109 << 14
                    "TutorialMatch away-team gate");
  patch_checked_u32(tutorial_main + 0x25c,
                    0x528008a1, // mov w1, #0x45 (first tutorial)
                    0x528000a1, // mov w1, #5 (generic offline match)
                    "TutorialMatch game mode");
  patch_checked_u32(tutorial_main + 0x264,
                    0x973d8635, // bl UtilityMatchSettings::SetMatchSettings
                    0x9406b872, // bl SetMatchSettingsBase
                    "TutorialMatch base settings");
  exhibition_tutorial_main_resume = tutorial_main_runtime + 0x10;
  hook_arm64(tutorial_main,
             (uintptr_t)&pes_exhibition_tutorial_main_hook);
  debugPrintf("UE4 patch: TutorialMatch exhibition bootstrap backing=%p "
              "runtime=%p hook=%p resume=%p teams=108v109 mode=5 scoped=1 "
              "listener=%p DirectSet=%p\n",
              (void *)tutorial_main, (void *)tutorial_main_runtime,
              pes_exhibition_tutorial_main_hook,
              (void *)exhibition_tutorial_main_resume,
              exhibition_flow_listener_instance, exhibition_flow_direct_set);

  // Seed the custom Exhibition roster after MyClubFlowMatchMenu's constructor
  // has created its matchPlan singleton, but before Main state 0 loads it into
  // the visible Team Strategy editor.
  const char *strategy_main_symbol =
      "_ZN4menu19MyClubFlowMatchMenu4MainEv";
  const uintptr_t strategy_main =
      so_find_addr(module, strategy_main_symbol);
  const uintptr_t strategy_main_runtime =
      so_find_addr_rx(module, strategy_main_symbol);
  static const uint32_t expected_strategy_main_entry[4] = {
      0xd10103ff, // sub sp, sp, #0x40
      0xa9037bf3, // stp x19, x30, [sp, #48]
      0x3948a001, // ldrb w1, [x0, #552]
      0xf90013f4, // str x20, [sp, #32]
  };
  if (memcmp((void *)strategy_main, expected_strategy_main_entry,
             sizeof(expected_strategy_main_entry)) != 0)
    fatal_error("Unexpected MyClubFlowMatchMenu::Main entry at %p",
                (void *)strategy_main);
  exhibition_matchplan_get_instance =
      (void *)so_find_addr_rx(module,
                              "_ZN9matchPlan4Data11GetInstanceEv");
  exhibition_matchplan_setup_team =
      (void *)so_find_addr_rx(module,
          "_ZN9matchPlan4Data17SetupDataByTeamIdEN6common6TeamIdE8HomeAway");
  exhibition_matchplan_setup_tmpdb =
      (void *)so_find_addr_rx(module,
          "_ZN9matchPlan4Data23SetupDataFromTmpdbMatchEv");
  exhibition_matchplan_update_tmpdb =
      (void *)so_find_addr_rx(module,
          "_ZN9matchPlan4Data24UpdateTmpdbMatchTeamDataEv");
  exhibition_set_team =
      (void *)so_find_addr_rx(module,
          "_ZN5tmpdb4util17SetExhibitionTeamEN6common6TeamIdEhb");
  exhibition_check_uniform =
      (void *)so_find_addr_rx(module,
          "_ZN5tmpdb4util12checkUniformEN6common6TeamIdES2_b");
  exhibition_match_get_uni_id =
      (void *)so_find_addr_rx(module,
          "_ZNK5tmpdb5Match8GetUniIdE8HomeAway");
  exhibition_match_set_uni_id =
      (void *)so_find_addr_rx(module,
          "_ZN5tmpdb5Match8SetUniIdE8HomeAwayj");
  exhibition_match_get_extra_uniform_list =
      (void *)so_find_addr_rx(module,
          "_ZN5tmpdb5Match24GetExtraUniformUniIdListERK8HomeAwayRKj");
  exhibition_tmpdb_manager_get_instance =
      (void *)so_find_addr_rx(module,
          "_ZN5tmpdb7Manager11GetInstanceEv");
  exhibition_tmpdb_match_get_team =
      (void *)so_find_addr_rx(module,
          "_ZNK5tmpdb5Match7GetTeamERK8HomeAway");
  exhibition_tmpdb_match_set_user_id =
      (void *)so_find_addr_rx(module,
          "_ZN5tmpdb5Match9SetUserIdE8HomeAwayj");
  exhibition_online_parameter_get_instance =
      (void *)so_find_addr_rx(module,
          "_ZN12onlinesystem9Parameter11GetInstanceEv");
  exhibition_parameter_common_get_user_id =
      (void *)so_find_addr_rx(module,
          "_ZN12onlinesystem15ParameterCommon9GetUserIDEv");
  exhibition_get_match_my_side =
      (void *)so_find_addr_rx(module,
          "_ZN10onlinemode13UtilityCommon14GetMatchMySideEv");
  exhibition_commonwork_update_team =
      (void *)so_find_addr_rx(module,
          "_ZNK5tmpdb10CommonWork10UpdateTeamEN6common6TeamIdE");
  exhibition_commonwork_update_player =
      (void *)so_find_addr_rx(module,
          "_ZNK5tmpdb10CommonWork12UpdatePlayerEN6common8PlayerIdE");
  exhibition_get_player_id_by_unique_id =
      (void *)so_find_addr_rx(module,
          "_ZN5tmpdb4util21GetPlayerIdByUniqueIdERKj");
  exhibition_squad_edit_get_squad_data =
      (void *)so_find_addr_rx(module,
          "_ZNK5tmpdb9SquadEdit12GetSquadDataE8HomeAway");
  exhibition_squad_data_get_player_count =
      (void *)so_find_addr_rx(module,
          "_ZNK5tmpdb9SquadData17GetSquadPlayerNumEv");
  exhibition_squad_data_get_player_by_index =
      (void *)so_find_addr_rx(module,
          "_ZNK5tmpdb9SquadData14GetSquadPlayerERKj");
  exhibition_squad_edit_update_player =
      (void *)so_find_addr_rx(module,
          "_ZN5tmpdb9SquadEdit23UpdateMemberTmpdbPlayerERKNS_8PlayerIdERKNS_6PlayerENS_11SquadPlayer14PARAMETER_TYPEE");
  exhibition_get_player_overall =
      (void *)so_find_addr_rx(module,
          "_ZN5tmpdb11utilitycore16GetPlayerOverAllERKNS_6PlayerERK8PositionNS1_13ConditionTypeE");
  exhibition_strategy_main_resume = strategy_main_runtime + 0x10;
  hook_arm64(strategy_main,
             (uintptr_t)&pes_exhibition_strategy_main_hook);
  const uintptr_t strategy_created_site = strategy_main + 0x218;
  static const uint32_t expected_strategy_created[4] = {
      0xb40000a1, // cbz x1, state-2 path
      0xaa1303e0, // mov x0, x19
      0x973df93b, // bl sys::TaskUnit::AddUnit
      0x320003e8, // orr w8, wzr, #1
  };
  if (memcmp((void *)strategy_created_site, expected_strategy_created,
             sizeof(expected_strategy_created)) != 0)
    fatal_error("Unexpected MyClubFlowMatchMenu child-create bytes at %p",
                (void *)strategy_created_site);
  exhibition_strategy_created_resume = strategy_main_runtime + 0x16c;
  hook_arm64(strategy_created_site,
             (uintptr_t)&pes_exhibition_strategy_created_hook);

  const char *strategy_update_symbol =
      "_ZN4menu15MyClubSquadEdit23UpdatePostControlWindowEN10menusystem6Window10PAD_STATUSE";
  const char *strategy_footer_symbol =
      "_ZN4menu15MyClubSquadEdit19PadEventFooterTouchEN10menusystem17MOBILE_FOOTER_KEYE";
  const char *strategy_vtable_symbol = "_ZTVN4menu15MyClubSquadEditE";
  const uintptr_t strategy_update_runtime =
      so_find_addr_rx(module, strategy_update_symbol);
  const uintptr_t strategy_footer_runtime =
      so_find_addr_rx(module, strategy_footer_symbol);
  const uintptr_t strategy_vtable =
      so_find_addr(module, strategy_vtable_symbol);
  uintptr_t *strategy_update_slot = find_vtable_method_slot(
      module, strategy_vtable_symbol, strategy_update_runtime, 128);
  uintptr_t *strategy_footer_slot = find_vtable_method_slot(
      module, strategy_vtable_symbol, strategy_footer_runtime, 128);
  if (!strategy_update_slot || !strategy_footer_slot) {
    debugPrintf("UE4 hook: MyClubSquadEdit vtable slot not found; "
                "native Game Plan retained (update=%p footer=%p)\n",
                (void *)strategy_update_runtime,
                (void *)strategy_footer_runtime);
  } else {
    exhibition_strategy_update_original = (void *)strategy_update_runtime;
    exhibition_strategy_footer_original = (void *)strategy_footer_runtime;
    *strategy_update_slot = (uintptr_t)&pes_exhibition_strategy_update;
    *strategy_footer_slot = (uintptr_t)&pes_exhibition_strategy_footer;
  }
  debugPrintf("UE4 hook: Exhibition Strategy seed backing=%p runtime=%p "
               "hook=%p resume=%p childSite=%p childHook=%p childResume=%p "
               "get=%p setupTeam=%p setupTmpdb=%p setTeam=%p update=%p "
               "vtable=%p post=%p footer=%p\n",
               (void *)strategy_main, (void *)strategy_main_runtime,
               pes_exhibition_strategy_main_hook,
               (void *)exhibition_strategy_main_resume,
              (void *)strategy_created_site,
              pes_exhibition_strategy_created_hook,
              (void *)exhibition_strategy_created_resume,
              exhibition_matchplan_get_instance,
               exhibition_matchplan_setup_team,
               exhibition_matchplan_setup_tmpdb,
               exhibition_set_team,
               exhibition_matchplan_update_tmpdb,
               (void *)strategy_vtable,
               pes_exhibition_strategy_update,
               pes_exhibition_strategy_footer);
  debugPrintf("UE4 hook: Exhibition master roster manager=%p updateTeam=%p "
              "updatePlayer=%p getPlayerId=%p getMatchTeam=%p "
              "setUser=%p getOnlineParam=%p getUser=%p getSide=%p\n",
              exhibition_tmpdb_manager_get_instance,
              exhibition_commonwork_update_team,
              exhibition_commonwork_update_player,
              exhibition_get_player_id_by_unique_id,
              exhibition_tmpdb_match_get_team,
              exhibition_tmpdb_match_set_user_id,
              exhibition_online_parameter_get_instance,
              exhibition_parameter_common_get_user_id,
              exhibition_get_match_my_side);
  debugPrintf("UE4 hook: Exhibition uniforms check=%p getUni=%p\n",
              exhibition_check_uniform, exhibition_match_get_uni_id);

  // Turn the stock Training Team Select window into the Exhibition matchup
  // screen. Both rows launch the normal master-club browser; only wrapper
  // roster entries survive its availability filter. This keeps all touch,
  // controller, badge, name and list rendering inside the game's own UI.
  const char *training_touch_symbol =
      "_ZN4menu29MyClubMatchTrainingTeamSelect13PadEventTouchERKN10menusystem14TouchEventInfoE";
  const char *training_list_symbol =
      "_ZN4menu29MyClubMatchTrainingTeamSelect13SetupListInfoEPN10menusystem8NodePageERKj";
  const char *training_child_symbol =
      "_ZN4menu29MyClubMatchTrainingTeamSelect21ChildPopupEndCallBackERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS2_9AllocatorIcEEEEj";
  const char *training_footer_symbol =
      "_ZN4menu29MyClubMatchTrainingTeamSelect19PadEventFooterTouchEN10menusystem17MOBILE_FOOTER_KEYE";
  const char *filter_teams_symbol =
      "_ZN4menu20MyClubFlowTeamSelect18RemoveUnusableTeamERN5cobra3stl6vectorIN6common6TeamIdENS2_9AllocatorIS5_EEEE";
  const uintptr_t training_touch =
      so_find_addr(module, training_touch_symbol);
  const uintptr_t training_touch_runtime =
      so_find_addr_rx(module, training_touch_symbol);
  const uintptr_t training_list = so_find_addr(module, training_list_symbol);
  const uintptr_t training_list_runtime =
      so_find_addr_rx(module, training_list_symbol);
  const uintptr_t training_child =
      so_find_addr(module, training_child_symbol);
  const uintptr_t training_child_runtime =
      so_find_addr_rx(module, training_child_symbol);
  const uintptr_t training_footer =
      so_find_addr(module, training_footer_symbol);
  const uintptr_t training_footer_runtime =
      so_find_addr_rx(module, training_footer_symbol);
  const uintptr_t filter_teams = so_find_addr(module, filter_teams_symbol);
  const uintptr_t filter_teams_runtime =
      so_find_addr_rx(module, filter_teams_symbol);
  static const uint32_t expected_training_touch[4] = {
      0xd10103ff, 0xa9037bf3, 0xb9400428, 0xf90013f4,
  };
  static const uint32_t expected_training_list[4] = {
      0xa9bc63fc, 0xa9015bf7, 0xa90253f5, 0xa9037bf3,
  };
  static const uint32_t expected_training_child[4] = {
      0xf81e0ff4, 0xa9017bf3, 0x39400028, 0xf9400429,
  };
  static const uint32_t expected_training_footer[4] = {
      0xd10203ff, 0x71000c3f, 0xa9036bfb, 0xa90463f9,
  };
  static const uint32_t expected_filter_teams[4] = {
      0xd101c3ff, 0xa9016ffc, 0xa90267fa, 0xa9035ff8,
  };
  if (memcmp((void *)training_touch, expected_training_touch,
             sizeof(expected_training_touch)) != 0 ||
      memcmp((void *)training_list, expected_training_list,
             sizeof(expected_training_list)) != 0 ||
      memcmp((void *)training_child, expected_training_child,
             sizeof(expected_training_child)) != 0 ||
      memcmp((void *)training_footer, expected_training_footer,
             sizeof(expected_training_footer)) != 0 ||
      memcmp((void *)filter_teams, expected_filter_teams,
             sizeof(expected_filter_teams)) != 0)
    fatal_error("Unexpected Exhibition team-select function bytes");
  patch_checked_u32(training_touch + 0x2c,
                    0x34000448, // cbz row, stock user-team flow
                    0xd503201f, // nop; both rows open master-club picker
                    "Exhibition HOME team picker");
  patch_checked_u32(training_list + 0x58,
                    0x34000688, // cbz row, stock myClub squad formatter
                    0xd503201f, // nop; both rows use master-team formatter
                    "Exhibition HOME team summary");
  exhibition_set_test_match_team_id =
      (void *)so_find_addr_rx(module,
          "_ZN10onlinemode9DebugMode18SetTestMatchTeamIdEj");
  exhibition_training_touch_resume = training_touch_runtime + 0x10;
  exhibition_training_list_resume = training_list_runtime + 0x10;
  exhibition_training_child_resume = training_child_runtime + 0x10;
  exhibition_training_footer_resume = training_footer_runtime + 0x10;
  exhibition_filter_teams_resume = filter_teams_runtime + 0x10;
  hook_arm64(training_touch,
             (uintptr_t)&pes_exhibition_training_touch_hook);
  hook_arm64(training_list,
             (uintptr_t)&pes_exhibition_training_list_hook);
  hook_arm64(training_child,
             (uintptr_t)&pes_exhibition_training_child_hook);
  hook_arm64(training_footer,
             (uintptr_t)&pes_exhibition_training_footer_hook);
  hook_arm64(filter_teams,
             (uintptr_t)&pes_exhibition_filter_teams_hook);
  debugPrintf("UE4 hook: Exhibition matchup UI touch=%p list=%p child=%p "
              "footer=%p filter=%p setTeamId=%p valid=%u clubs\n",
              (void *)training_touch_runtime,
              (void *)training_list_runtime,
              (void *)training_child_runtime,
              (void *)training_footer_runtime,
              (void *)filter_teams_runtime,
              exhibition_set_test_match_team_id,
              (unsigned int)(sizeof(exhibition_master_rosters) /
                             sizeof(exhibition_master_rosters[0])));

  // Convert the stock Match Searching window into the single Exhibition hub.
  // Its native footer already supports four slots; only the Training game mode
  // normally exposes Back/Next. The tail hook enables COM Level/Game Plan
  // after the stock state machine updates, while three class-local vtable
  // entries make the two team panels and popup callbacks interactive.
  const char *search_update_symbol =
      "_ZN4menu20MyClubMatchSearching23UpdatePostControlWindowEN10menusystem6Window10PAD_STATUSE";
  const char *search_footer_symbol =
      "_ZN4menu20MyClubMatchSearching19PadEventFooterTouchEN10menusystem17MOBILE_FOOTER_KEYE";
  const char *search_child_symbol =
      "_ZN4menu20MyClubMatchSearching21ChildPopupEndCallBackERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS2_9AllocatorIcEEEEj";
  const char *base_touch_symbol =
      "_ZN10menusystem12WindowMobile13PadEventTouchERKNS_14TouchEventInfoE";
  const char *search_vtable_symbol =
      "_ZTVN4menu20MyClubMatchSearchingE";
  const uintptr_t search_update = so_find_addr(module, search_update_symbol);
  const uintptr_t search_update_runtime =
      so_find_addr_rx(module, search_update_symbol);
  const uintptr_t search_post_site = search_update + 0x4e0;
  static const uint32_t expected_search_post[4] = {
      0xaa1303e0, 0x973da7ce, 0xa9427bf3, 0xa94153f5,
  };
  if (memcmp((void *)search_post_site, expected_search_post,
             sizeof(expected_search_post)) != 0)
    fatal_error("Unexpected MatchSearching post-control tail at %p",
                (void *)search_post_site);

  const uintptr_t search_footer_runtime =
      so_find_addr_rx(module, search_footer_symbol);
  const uintptr_t search_child_runtime =
      so_find_addr_rx(module, search_child_symbol);
  const uintptr_t base_touch_runtime =
      so_find_addr_rx(module, base_touch_symbol);
  const uintptr_t search_vtable =
      so_find_addr(module, search_vtable_symbol);
  uintptr_t *search_touch_slot =
      (uintptr_t *)(search_vtable + 91 * sizeof(uintptr_t));
  uintptr_t *search_footer_slot =
      (uintptr_t *)(search_vtable + 98 * sizeof(uintptr_t));
  uintptr_t *search_child_slot =
      (uintptr_t *)(search_vtable + 46 * sizeof(uintptr_t));
  if (*search_touch_slot != base_touch_runtime ||
      *search_footer_slot != search_footer_runtime ||
      *search_child_slot != search_child_runtime)
    fatal_error("Unexpected MatchSearching vtable touch=%p footer=%p child=%p",
                (void *)*search_touch_slot, (void *)*search_footer_slot,
                (void *)*search_child_slot);

  exhibition_search_touch_original = (void *)base_touch_runtime;
  exhibition_search_footer_original = (void *)search_footer_runtime;
  exhibition_training_footer_original = (void *)training_footer_runtime;
  *search_touch_slot = (uintptr_t)&pes_exhibition_search_touch;
  *search_footer_slot = (uintptr_t)&pes_exhibition_search_footer;
  *search_child_slot = (uintptr_t)&pes_exhibition_search_child;

  exhibition_search_post_resume = search_update_runtime + 0x4f0;
  exhibition_search_update_disp =
      (void *)so_find_addr_rx(module,
          "_ZN4menu20MyClubMatchSearching18UpdateDispMatchingEv");
  exhibition_search_update_team_info =
      (void *)so_find_addr_rx(module,
          "_ZN4menu20MyClubMatchSearching14UpdateTeamInfoERK8HomeAway");
  exhibition_window_get_window =
      (void *)so_find_addr_rx(module,
          "_ZN10menusystem6Window9GetWindowEv");
  exhibition_holder_get_duplicate =
      (void *)so_find_addr_rx(module,
          "_ZN10menusystem14NodeRectHolder12GetDuplicateEj");
  exhibition_node_set_visible =
      (void *)so_find_addr_rx(module,
          "_ZN10menusystem4Node10SetVisibleEbj");
  match_node_set_alpha = (void *)so_find_addr_rx(
      module, "_ZN10menusystem4Node8SetAlphaEf");
  match_setplay_get_root = (void *)so_find_addr_rx(
      module, "_ZN10menusystem6Window7GetRootEv");
  if (!match_node_set_alpha || !match_setplay_get_root)
    fatal_error("ButtonSetplay visual-only alpha function not found");

  // Vtable dispatch wrapper: no inline trampoline, no altered input state,
  // no camera/render-loop hook and no asset/object pointer retained per match.
  const char *visual_action_symbol = "_ZN7match2D5Model7Manager6ActionEv";
  const char *visual_set_disp_symbol = "_ZN7match2D5Model4Base7SetDispEb";
  const uintptr_t visual_action = so_find_addr(module, visual_action_symbol);
  const uintptr_t visual_set_disp = so_find_addr(module, visual_set_disp_symbol);
  static const uint32_t visual_action_expected[4] = {
      0xa9bf7bf3, 0xb9415808, 0xaa0003f3, 0x71000d1f};
  static const uint32_t visual_set_disp_expected[4] = {
      0xf9400000, 0xb4000060, 0x12000021, 0x16ed7a85};
  if (!visual_action || !visual_set_disp ||
      memcmp((void *)visual_action, visual_action_expected, sizeof(visual_action_expected)) ||
      memcmp((void *)visual_set_disp, visual_set_disp_expected, sizeof(visual_set_disp_expected)))
    fatal_error("Unexpected on-pitch assist model code revision");
  const uintptr_t visual_action_runtime = so_find_addr_rx(module, visual_action_symbol);
  uintptr_t *visual_action_slot = find_vtable_method_slot(
      module, "_ZTVN7match2D5Model7ManagerE", visual_action_runtime, 64);
  if (!visual_action_slot)
    fatal_error("On-pitch assist Model::Manager Action slot not found");
  match_visual_model_action_original = (void *)visual_action_runtime;
  match_visual_model_set_disp = (void *)so_find_addr_rx(module, visual_set_disp_symbol);
  *visual_action_slot = (uintptr_t)&pes_match_visual_model_action;

  // Gate the custom A prompt to the real title-window lifecycle. Initializing
  // it statically made the glyph visible during the long UE4 boot sequence.
  const uintptr_t title_post_init = so_find_addr(
      module, "_ZN4menu9TitleMenu14PostInitMobileEv");
  const uintptr_t title_prompt_ready_site = title_post_init + 0x10;
  static const uint32_t expected_title_prompt_ready[4] = {
      0x320003e8, 0xb9022268, 0xa8c17bf3, 0xd65f03c0,
  };
  if (memcmp((void *)title_prompt_ready_site,
             expected_title_prompt_ready,
             sizeof(expected_title_prompt_ready)) != 0)
    fatal_error("Unexpected TitleMenu::PostInitMobile tail at %p",
                (void *)title_prompt_ready_site);
  hook_arm64(title_prompt_ready_site,
             (uintptr_t)&pes_title_prompt_ready_hook);
  debugPrintf("UE4 menu: title prompt ready hook=%p\n",
              (void *)so_find_addr_rx(
                  module, "_ZN4menu9TitleMenu14PostInitMobileEv"));

  // Build only the Match page, force it selected, and retain just the native
  // Exhibition and Training choices. This is deliberately a UI/setup trim:
  // it avoids entering unsupported myClub pages without claiming to change
  // the separate in-match renderer/simulation cost.
  const char *main_setup_symbol =
      "_ZN4menu10MyClubMain11SetupWindowEv";
  const char *main_swipe_symbol =
      "_ZN4menu10MyClubMain16PadEventSwipeEndEjj";
  const uintptr_t main_setup = so_find_addr(module, main_setup_symbol);
  const uintptr_t main_setup_runtime =
      so_find_addr_rx(module, main_setup_symbol);
  const uintptr_t main_swipe = so_find_addr(module, main_swipe_symbol);
  const uintptr_t main_init = so_find_addr(
      module, "_ZN4menu10MyClubMain10InitMobileEv");
  const uintptr_t main_selected = so_find_addr(
      module,
      "_ZN4menu10MyClubMain15OnSelectedMatchERKN10menusystem14TouchEventInfoE");
  const uintptr_t main_selected_runtime = so_find_addr_rx(
      module,
      "_ZN4menu10MyClubMain15OnSelectedMatchERKN10menusystem14TouchEventInfoE");
  const uintptr_t header_four_visible = so_find_addr(
      module, "_ZN4menu12HeaderWindow26setDefautFourButtonVisibleEb");
  static const uint32_t expected_main_tail[4] = {
      0xa9427bf3, 0xa94153f5, 0xf84307f6, 0xd65f03c0,
  };
  static const uint32_t expected_main_selected[4] = {
      0xf81e0ff4, 0xa9017bf3, 0xb9400834, 0xaa0003f3,
  };
  if (memcmp((void *)(main_setup + 0x11c), expected_main_tail,
             sizeof(expected_main_tail)) != 0)
    fatal_error("Unexpected MyClubMain::SetupWindow tail at %p",
                (void *)(main_setup + 0x11c));
  if (memcmp((void *)main_selected, expected_main_selected,
             sizeof(expected_main_selected)) != 0)
    fatal_error("Unexpected MyClubMain::OnSelectedMatch entry at %p",
                (void *)main_selected);
  patch_checked_u32(main_setup + 0x20, 0x973cd496, 0xd503201f,
                    "MyClubMain Club House setup");
  patch_checked_u32(main_setup + 0x28, 0x973e458c, 0xd503201f,
                    "MyClubMain Contract setup");
  patch_checked_u32(main_setup + 0x30, 0x974087ee, 0xd503201f,
                    "MyClubMain Extras setup");
  patch_checked_u32(main_setup + 0xf4, 0x2a1603e1, 0x2a1f03e1,
                    "MyClubMain selected page");
  patch_checked_u32(main_setup + 0xfc, 0x110006c1, 0x52800021,
                    "MyClubMain swipe page");
  patch_checked_u32(main_swipe, 0xf81e0ff4, 0xd65f03c0,
                    "MyClubMain page swipe disable");
  patch_checked_u32(main_init + 0xe8,
                    0x973e77f0, // bl MyClubMain::DispTutorial
                    0x2a1f03e0, // mov w0, wzr
                    "MyClubMain tutorial popup disable");
  patch_checked_u32(main_init + 0xf0,
                    0x37000060, // tbnz w0, #0, skip first-access
                    0x14000003, // b skip first-access
                    "MyClubMain first-access popup disable");
  const uintptr_t tutorial_clear_dialog = so_find_addr(
      module, "_ZN4menu18MyClubFlowTutorial17CreateClearDialogEv");
  patch_checked_u32(tutorial_clear_dialog,
                    0xf81d0ff6, // str x22, [sp, #-48]!
                    0x2a1f03e0, // mov w0, wzr
                    "MyClubFlowTutorial clear dialog return false");
  patch_checked_u32(tutorial_clear_dialog + 0x4,
                    0xa90153f5, // stp x21, x20, [sp, #16]
                    0xd65f03c0, // ret
                    "MyClubFlowTutorial clear dialog skip");
  patch_checked_u32(header_four_visible + 0x8,
                    0x2a0103f3, // mov w19, w1
                    0x2a1f03f3, // mov w19, wzr
                    "MyClub header four-button visibility");
  main_menu_selected_resume = main_selected_runtime + 0x10;
  hook_arm64(main_selected, (uintptr_t)&pes_main_menu_selected_hook);
  hook_arm64(main_setup + 0x11c,
             (uintptr_t)&pes_main_menu_simplify_hook);
  debugPrintf("UE4 menu: installed direct compact menu setup=%p tail=%p "
              "swipe=%p init=%p selected=%p header=%p tutorialDialog=%p\n",
              (void *)main_setup_runtime,
              (void *)(main_setup_runtime + 0x11c),
              (void *)so_find_addr_rx(module, main_swipe_symbol),
              (void *)so_find_addr_rx(
                  module, "_ZN4menu10MyClubMain10InitMobileEv"),
              (void *)main_selected_runtime,
              (void *)so_find_addr_rx(
                  module,
                  "_ZN4menu12HeaderWindow26setDefautFourButtonVisibleEb"),
              (void *)so_find_addr_rx(
                  module,
                  "_ZN4menu18MyClubFlowTutorial17CreateClearDialogEv"));
  exhibition_text_set_string =
      (void *)so_find_addr_rx(module,
          "_ZN10menusystem12NodeRectText6SetStrERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS2_9AllocatorIcEEEE");
  exhibition_emblem_set_team =
      (void *)so_find_addr_rx(module,
          "_ZN10menusystem18NodeRectEmblemBase11SetCodeTeamERKN6common6TeamIdEbNS_6Symbol23TEAM_NATION_SYMBOL_TYPEEbNS5_17TEAM_SYMBOL_COLORE");
  exhibition_set_pad_key_kind =
      (void *)so_find_addr_rx(module,
          "_ZN10menusystem12WindowMobile19SetPadKeyKindMobileENS_17MOBILE_FOOTER_KEYEb");
  exhibition_set_pad_key_string =
      (void *)so_find_addr_rx(module,
          "_ZN10menusystem12WindowMobile21SetPadKeyStringMobileENS_17MOBILE_FOOTER_KEYEj");
  exhibition_set_pad_key_active =
      (void *)so_find_addr_rx(module,
          "_ZN10menusystem12WindowMobile21SetPadKeyActiveMobileENS_17MOBILE_FOOTER_KEYEb");
  exhibition_team_select_create_child =
      (void *)so_find_addr_rx(module,
          "_ZN4menu20MyClubFlowTeamSelect13CreateAsChildERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS2_9AllocatorIcEEEEbPN10menusystem12WindowMobileEjbbb");
  exhibition_task_add_unit =
      (void *)so_find_addr_rx(module,
          "_ZN3sys8TaskUnit7AddUnitEPS0_");
  main_menu_choice_set_active =
      (void *)so_find_addr_rx(module,
          "_ZN10menusystem4Node9SetActiveEbbj");
  main_menu_graphics_create =
      (void *)so_find_addr_rx(module,
          "_ZN4menu26MyClubMatchGraphicsSetting12CreateObjectERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS2_9AllocatorIcEEEERKb");
  main_menu_save_graphics_quality =
      (void *)so_find_addr_rx(module,
          "_ZN3sys8SaveData19SaveGraphicsQualityEj");
  main_menu_get_graphics_quality =
      (void *)so_find_addr_rx(module,
          "_ZN3sys8SaveData18GetGraphicsQualityEv");
  main_menu_save_frame_rate =
      (void *)so_find_addr_rx(module,
          "_ZN3sys8SaveData13SaveFrameRateEN5basic6Status15FRAME_RATE_MODEE");
  main_menu_set_frame_rate_mode =
      (void *)so_find_addr_rx(module,
          "_ZN5basic6Status16SetFrameRateModeENS0_15FRAME_RATE_MODEE");
  main_menu_get_frame_rate_mode =
      (void *)so_find_addr_rx(module,
          "_ZN5basic6Status16GetFrameRateModeEv");
  main_menu_get_ue_bridge =
      (void *)so_find_addr_rx(module, "_Z19GetUEBridgeInstancev");

  const char *graphics_d1_symbol =
      "_ZN4menu26MyClubMatchGraphicsSettingD1Ev";
  const char *graphics_d0_symbol =
      "_ZN4menu26MyClubMatchGraphicsSettingD0Ev";
  const uintptr_t graphics_d1 = so_find_addr(module, graphics_d1_symbol);
  const uintptr_t graphics_d0 = so_find_addr(module, graphics_d0_symbol);
  const uintptr_t graphics_d1_runtime =
      so_find_addr_rx(module, graphics_d1_symbol);
  const uintptr_t graphics_d0_runtime =
      so_find_addr_rx(module, graphics_d0_symbol);
  static const uint32_t expected_graphics_destructor[4] = {
      0xf81d0ff6, 0xa90153f5, 0xa9027bf3, 0x900163a8,
  };
  if (memcmp((void *)graphics_d1, expected_graphics_destructor,
             sizeof(expected_graphics_destructor)) != 0 ||
      memcmp((void *)graphics_d0, expected_graphics_destructor,
             sizeof(expected_graphics_destructor)) != 0)
    fatal_error("Unexpected graphics settings destructor entry");
  pes_main_menu_graphics_d1_resume = graphics_d1_runtime + 0x10;
  pes_main_menu_graphics_d0_resume = graphics_d0_runtime + 0x10;
  pes_main_menu_graphics_destructor_page =
      (uintptr_t)module->load_virtbase + 0x959a000;
  pes_main_menu_graphics_d0_page = pes_main_menu_graphics_destructor_page;
  hook_arm64(graphics_d1, (uintptr_t)&pes_main_menu_graphics_d1_hook);
  hook_arm64(graphics_d0, (uintptr_t)&pes_main_menu_graphics_d0_hook);

  const uintptr_t graphics_prepare = so_find_addr(
      module, "_ZN4menu26MyClubMatchGraphicsSetting11PrepareDataEv");
  patch_checked_u32(graphics_prepare + 0xd0, 0xeb08013f, 0x1400003d,
                    "graphics High option removal");
  const uintptr_t save_graphics = so_find_addr(
      module, "_ZN3sys8SaveData19SaveGraphicsQualityEj");
  patch_checked_u32(save_graphics + 0x18, 0x71000a7f, 0x7100067f,
                    "graphics quality High rejection");
  patch_checked_u32((uintptr_t)module->load_base + 0x9438cf8, 2, 1,
                    "saved High graphics clamp");
  debugPrintf("UE4 menu: graphics settings factory=%p d1=%p d0=%p; "
              "custom save=%p/%p status=%p/%p bridge=%p; High disabled\n",
              main_menu_graphics_create, (void *)graphics_d1_runtime,
              (void *)graphics_d0_runtime, main_menu_save_graphics_quality,
              main_menu_save_frame_rate, main_menu_set_frame_rate_mode,
              main_menu_get_frame_rate_mode, main_menu_get_ue_bridge);
  exhibition_setup_usable_teams =
      (void *)so_find_addr_rx(module,
          "_ZN10onlinemode13UtilityMyClub20SetupUseableTeamListEv");
  exhibition_team_select_set_usable =
      (void *)so_find_addr_rx(module,
          "_ZN4menu20MyClubFlowTeamSelect17SetUsableteamListEb");
  exhibition_set_test_match_cpu_level =
      (void *)so_find_addr_rx(module,
          "_ZN10onlinemode9DebugMode20SetTestMatchCpuLevelE8CpuLevel");
  exhibition_get_test_match_cpu_level =
      (void *)so_find_addr_rx(module,
          "_ZN10onlinemode9DebugMode20GetTestMatchCpuLevelEv");
  exhibition_match_get_match_level =
      (void *)so_find_addr_rx(module, "_ZNK5tmpdb5Match13GetMatchLevelEv");
  exhibition_match_set_match_level =
      (void *)so_find_addr_rx(module, "_ZN5tmpdb5Match13SetMatchLevelE8CpuLevel");
  exhibition_match_get_time_zone =
      (void *)so_find_addr_rx(module,
          "_ZNK5tmpdb5Match11GetTimeZoneEv");
  exhibition_match_set_time_zone =
      (void *)so_find_addr_rx(module,
          "_ZN5tmpdb5Match11SetTimeZoneEN6common12TimeZoneTypeE");
  exhibition_match_get_match_time =
      (void *)so_find_addr_rx(module,
          "_ZNK5tmpdb5Match12GetMatchTimeEv");
  exhibition_match_set_match_time =
      (void *)so_find_addr_rx(module,
          "_ZN5tmpdb5Match12SetMatchTimeEh");
  exhibition_match_is_ex =
      (void *)so_find_addr_rx(module, "_ZNK5tmpdb5Match4IsExEv");
  exhibition_match_set_ex =
      (void *)so_find_addr_rx(module, "_ZN5tmpdb5Match5SetExEb");
  exhibition_match_is_pk =
      (void *)so_find_addr_rx(module, "_ZNK5tmpdb5Match4IsPkEv");
  exhibition_match_set_pk =
      (void *)so_find_addr_rx(module, "_ZN5tmpdb5Match5SetPkEb");
  exhibition_match_setting_create_child =
      (void *)so_find_addr_rx(
          module,
          "_ZN4menu18MyClubMatchSetting13CreateAsChildERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS2_9AllocatorIcEEEERKb");
  exhibition_is_test_match_original =
      (void *)so_find_addr_rx(
          module, "_ZN10onlinemode13UtilityMyClub11IsTestMatchEv");
  exhibition_status_get_instance =
      (void *)so_find_addr_rx(module,
          "_ZN3sys6Status11GetInstanceEv");
  exhibition_status_set_game_mode =
      (void *)so_find_addr_rx(module,
          "_ZN3sys6Status11SetGameModeEj");
  exhibition_parameter_get_instance =
      (void *)so_find_addr_rx(module,
          "_ZN10onlinemode9Parameter11GetInstanceEb");
  exhibition_parameter_myclub_create_work =
      (void *)so_find_addr_rx(module,
          "_ZN10onlinemode15ParameterMyClub16CreateMyClubWorkEv");

  // The stock Match Settings window exposes its complete offline options only
  // in Test Match. Scope that answer to this child so Exhibition stays in the
  // generic offline game mode used by MatchSetup.
  const uintptr_t is_test_match_plt =
      (uintptr_t)module->load_base + 0x39357f0;
  static const uint32_t expected_is_test_match_plt[4] = {
      0xf002e110, 0xf9472a11, 0x91394210, 0xd61f0220,
  };
  if (memcmp((const void *)is_test_match_plt, expected_is_test_match_plt,
             sizeof(expected_is_test_match_plt)) != 0)
    fatal_error("Unexpected UtilityMyClub::IsTestMatch PLT at %p",
                (void *)is_test_match_plt);
  hook_arm64(is_test_match_plt,
             (uintptr_t)&pes_exhibition_is_test_match);
  debugPrintf("UE4 hook: Exhibition Settings create=%p IsTestMatch=%p "
              "PLT=%p cpu=%p/%p level=%p/%p manager=%p timezone=%p/%p time=%p/%p "
              "extra=%p/%p pk=%p/%p scoped=1\n",
              exhibition_match_setting_create_child,
              exhibition_is_test_match_original,
              (void *)is_test_match_plt,
              exhibition_get_test_match_cpu_level,
              exhibition_set_test_match_cpu_level,
              exhibition_match_get_match_level,
              exhibition_match_set_match_level,
              exhibition_tmpdb_manager_get_instance,
              exhibition_match_get_time_zone,
              exhibition_match_set_time_zone,
              exhibition_match_get_match_time,
              exhibition_match_set_match_time,
              exhibition_match_is_ex,
              exhibition_match_set_ex,
              exhibition_match_is_pk,
              exhibition_match_set_pk);

  // The strategy editor and ProcessMatchSetup each rebuild tmpdb::Match.
  // Commit the custom rules immediately before MatchListener consumes that
  // record, which is the last authoritative hand-off into registry::ModeInfo.
  const char *match_setup_data_symbol =
      "_ZN9game_mode13MatchListener19MatchSetupDataTmpdbEv";
  const uintptr_t match_setup_data =
      so_find_addr(module, match_setup_data_symbol);
  const uintptr_t match_setup_data_runtime =
      so_find_addr_rx(module, match_setup_data_symbol);
  static const uint32_t expected_match_setup_data_entry[4] = {
      0xf81d0ff6, 0xa90153f5, 0xa9027bf3, 0xaa0003f3,
  };
  if (memcmp((void *)match_setup_data, expected_match_setup_data_entry,
             sizeof(expected_match_setup_data_entry)) != 0)
    fatal_error("Unexpected MatchSetupDataTmpdb entry at %p",
                (void *)match_setup_data);
  exhibition_match_setup_data_resume = match_setup_data_runtime + 0x10;
  hook_arm64(match_setup_data,
             (uintptr_t)&pes_exhibition_match_setup_data_hook);

  // The Training search task dereferences ParameterMyClubUserInfo even for a
  // local match. Our offline bootstrap deliberately has no server profile,
  // so intercept only its GetUserName call and provide a valid local cobra
  // string while an Exhibition session is active.
  const char *search_task_init_symbol =
      "_ZN10onlinemode26TaskMatchSearchingTraining7ActInitEv";
  const uintptr_t search_task_init =
      so_find_addr(module, search_task_init_symbol);
  const uintptr_t search_task_init_runtime =
      so_find_addr_rx(module, search_task_init_symbol);
  const uintptr_t search_user_name_site = search_task_init + 0xf0;
  const uintptr_t search_task_ready_site = search_task_init + 0x18c;
  static const uint32_t expected_search_user_name[4] = {
      0xaa1403e0, // mov x0, x20
      0x97361b96, // bl ParameterMyClubUserInfo::GetUserName
      0x39400008, // ldrb w8, [x0]
      0xa940a40a, // ldp x10, x9, [x0, #8]
  };
  if (memcmp((void *)search_user_name_site, expected_search_user_name,
             sizeof(expected_search_user_name)) != 0)
    fatal_error("Unexpected Training search username bytes at %p",
                (void *)search_user_name_site);
  static const uint32_t expected_search_task_ready[4] = {
      0x91401bff, // add sp, sp, #0x6, lsl #12
      0x911e43ff, // add sp, sp, #0x790
      0xa9437bf3, // ldp x19, x30, [sp, #48]
      0xa94253f5, // ldp x21, x20, [sp, #32]
  };
  if (memcmp((void *)search_task_ready_site, expected_search_task_ready,
             sizeof(expected_search_task_ready)) != 0)
    fatal_error("Unexpected Training search task tail at %p",
                (void *)search_task_ready_site);
  exhibition_user_info_get_name =
      (void *)so_find_addr_rx(module,
          "_ZNK10onlinemode23ParameterMyClubUserInfo11GetUserNameEv");
  exhibition_search_user_name_resume = search_task_init_runtime + 0x100;
  exhibition_search_task_ready_resume = search_task_init_runtime + 0x19c;
  hook_arm64(search_user_name_site,
             (uintptr_t)&pes_exhibition_search_user_name_hook);
  hook_arm64(search_task_ready_site,
             (uintptr_t)&pes_exhibition_search_task_ready_hook);
  hook_arm64(search_post_site,
             (uintptr_t)&pes_exhibition_search_post_hook);
  debugPrintf("UE4 hook: Exhibition Matchmaking hub post=%p resume=%p "
              "vtable=%p touch=%p footer=%p child=%p userName=%p\n",
              (void *)(search_update_runtime + 0x4e0),
              (void *)exhibition_search_post_resume, (void *)search_vtable,
              pes_exhibition_search_touch, pes_exhibition_search_footer,
              pes_exhibition_search_child,
              (void *)(search_task_init_runtime + 0xf0));

  const char *string_get_symbol =
      "_ZN8stringdb17StringDataManager9GetStringEj";
  const uintptr_t string_get = so_find_addr(module, string_get_symbol);
  const uintptr_t string_get_runtime =
      so_find_addr_rx(module, string_get_symbol);
  const uintptr_t string_get_site = string_get + 0x10;
  static const uint32_t expected_string_get_site[4] = {
      0xf941ad08, // ldr x8, [x8, #856]
      0x91012015, // add x21, x0, #0x48
      0xaa0003f6, // mov x22, x0
      0xaa1503e0, // mov x0, x21
  };
  if (memcmp((void *)string_get_site, expected_string_get_site,
             sizeof(expected_string_get_site)) != 0)
    fatal_error("Unexpected StringDataManager::GetString bytes at %p",
                (void *)string_get_site);
  exhibition_string_get_resume = string_get_runtime + 0x20;
  hook_arm64(string_get_site,
             (uintptr_t)&pes_exhibition_string_get_hook);
  debugPrintf("UE4 hook: eFootball title -> Exhibition id=0x0460005d "
              "site=%p hook=%p resume=%p\n",
              (void *)(string_get_runtime + 0x10),
              pes_exhibition_string_get_hook,
              (void *)exhibition_string_get_resume);

  const char *resize_symbol =
      "_ZN6TArrayIP18FObjectInitializer17FDefaultAllocatorE10ResizeGrowEi";
  const char *malloc_symbol = "_ZN7FMemory6MallocEyj";
  const uintptr_t resize_backing = so_find_addr(module, resize_symbol);
  const uintptr_t resize_runtime = so_find_addr_rx(module, resize_symbol);

  ue4_fmemory_malloc = (void *)so_find_addr_rx(module, malloc_symbol);
  hook_arm64(resize_backing,
             (uintptr_t)&ue4_object_initializer_resize_hook);
  debugPrintf("UE4 hook: ResizeGrow backing=%p runtime=%p wrapper=%p "
              "FMemory::Malloc=%p\n",
              (void *)resize_backing, (void *)resize_runtime,
              ue4_object_initializer_resize_hook, ue4_fmemory_malloc);

  // Reuse the built-in tutorial-match flow as an offline Exhibition entry.
  // The factory hook changes only the eFootball tile's Divisions destination.
  // TutorialMatch is then made deterministic: it builds the two user-selected
  // validated clubs directly from the game's master database, bypasses stale
  // tutorial flags, and enters the ordinary offline match mode.
  const char *flow_create_symbol =
      "_ZN4menu13FactoryMobile10CreateFlowEPN3sys8TaskUnitERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS5_9AllocatorIcEEEEb";
  const uintptr_t flow_create_backing =
      so_find_addr(module, flow_create_symbol);
  const uintptr_t flow_create_runtime =
      so_find_addr_rx(module, flow_create_symbol);
  static const uint32_t expected_flow_create_entry[4] = {
      0xd101c3ff, // sub sp, sp, #0x70
      0xa9067bf3, // stp x19, x30, [sp, #96]
      0xaa0803f3, // mov x19, x8
      0x12000048, // and w8, w2, #1
  };
  if (memcmp((void *)flow_create_backing, expected_flow_create_entry,
             sizeof(expected_flow_create_entry)) != 0)
    fatal_error("Unexpected FactoryMobile::CreateFlow entry at %p",
                (void *)flow_create_backing);
  exhibition_flow_create_resume = flow_create_runtime + 0x10;
  hook_arm64(flow_create_backing,
             (uintptr_t)&pes_exhibition_flow_create_hook);
  debugPrintf("UE4 hook: Exhibition flow redirect backing=%p runtime=%p "
              "hook=%p resume=%p\n",
              (void *)flow_create_backing, (void *)flow_create_runtime,
              pes_exhibition_flow_create_hook,
              (void *)exhibition_flow_create_resume);

  // Publish a match/mode heartbeat at ScreenTapManager::Update entry, where the
  // original ControlModeInfo* is still x2. The hook preserves all arguments,
  // calls the authoritative IsModeOffence/Defence methods, then replays the
  // displaced prologue.
  const char *screen_tap_update_symbol =
      "_ZN5match16ScreenTapManager6UpdateEPKNS_8registry8RegistryERKNS_15ControlModeInfoERNS1_13ScreenTapInfoEPNS1_12Screen2dInfoEi";
  const uintptr_t screen_tap_backing =
      so_find_addr(module, screen_tap_update_symbol);
  const uintptr_t screen_tap_runtime =
      so_find_addr_rx(module, screen_tap_update_symbol);
  uint32_t *screen_tap_entry = (uint32_t *)screen_tap_backing;
  static const uint32_t expected_screen_tap_entry[4] = {
      0xd10643ff, // sub sp, sp, #0x190
      0x6d0f3bef, // stp d15, d14, [sp, #0xf0]
      0x6d1033ed, // stp d13, d12, [sp, #0x100]
      0x6d112beb, // stp d11, d10, [sp, #0x110]
  };
  if (memcmp(screen_tap_entry, expected_screen_tap_entry,
             sizeof(expected_screen_tap_entry)) != 0)
    fatal_error("Unexpected ScreenTapManager::Update entry at %p",
                (void *)screen_tap_entry);
  mobile_is_mode_offense =
      (void *)so_find_addr_rx(module,
          "_ZNK5match15ControlModeInfo13IsModeOffenceEv");
  mobile_is_mode_defense =
      (void *)so_find_addr_rx(module,
          "_ZNK5match15ControlModeInfo13IsModeDefenceEv");
  mobile_screen_tap_entry_resume = screen_tap_runtime + 0x10;
  hook_arm64((uintptr_t)screen_tap_entry,
             (uintptr_t)&pes_mobile_screen_tap_entry_hook);
  debugPrintf("UE4 hook: ScreenTapManager entry backing=%p runtime=%p "
              "hook=%p resume=%p offense=%p defense=%p\n",
              (void *)screen_tap_backing, (void *)screen_tap_runtime,
              pes_mobile_screen_tap_entry_hook,
              (void *)mobile_screen_tap_entry_resume,
              mobile_is_mode_offense, mobile_is_mode_defense);

  // ButtonSetplay is the authoritative native UI surface for goal kicks,
  // corners, free kicks and throw-ins. Publish its live action vector and
  // consume Joy-Con requests on this UI thread through PadEventTouch.
  const char *button_setplay_need_disp_symbol =
      "_ZN7match2D6Screen13ButtonSetplay8NeedDispEv";
  const char *button_setplay_update_symbol =
      "_ZN7match2D6Screen13ButtonSetplay25UpdatePreControlWindowSubEv";
  const char *button_setplay_touch_sub_symbol =
      "_ZN7match2D6Screen13ButtonSetplay16PadEventTouchSubERKN10menusystem14TouchEventInfoE";
  const uintptr_t button_setplay_need_disp_runtime =
      so_find_addr_rx(module, button_setplay_need_disp_symbol);
  const uintptr_t button_setplay_update_runtime =
      so_find_addr_rx(module, button_setplay_update_symbol);
  const uintptr_t button_setplay_touch_sub_runtime =
      so_find_addr_rx(module, button_setplay_touch_sub_symbol);
  uintptr_t *button_setplay_need_disp_slot = find_vtable_method_slot(
      module, "_ZTVN7match2D6Screen13ButtonSetplayE",
      button_setplay_need_disp_runtime, 128);
  uintptr_t *button_setplay_update_slot = find_vtable_method_slot(
      module, "_ZTVN7match2D6Screen13ButtonSetplayE",
      button_setplay_update_runtime, 128);
  uintptr_t *button_setplay_touch_sub_slot = find_vtable_method_slot(
      module, "_ZTVN7match2D6Screen13ButtonSetplayE",
      button_setplay_touch_sub_runtime, 128);
  if (!button_setplay_need_disp_slot || !button_setplay_update_slot ||
      !button_setplay_touch_sub_slot)
    fatal_error("ButtonSetplay lifecycle vtable slots not found");
  match_button_setplay_need_disp_original =
      (uint32_t (*)(void *))button_setplay_need_disp_runtime;
  match_button_setplay_update_original =
      (void (*)(void *))button_setplay_update_runtime;
  match_button_setplay_touch_sub_original =
      (void (*)(void *, const void *))button_setplay_touch_sub_runtime;
  match_window_set_se =
      (void *)so_find_addr_rx(
          module, "_ZN10menusystem6Window11SetWindowSEEj");
  match_action_button_pad_event_touch =
      (void *)so_find_addr_rx(
          module,
          "_ZN7match2D6Screen16ActionButtonBase13PadEventTouchERKN10menusystem14TouchEventInfoE");
  match_action_button_get_disable_timer =
      (void *)so_find_addr_rx(
          module,
          "_ZN7match2D6Screen16ActionButtonBase21GetDisableButtonTimerENS1_10ButtonTypeE");
  if (!match_action_button_pad_event_touch ||
      !match_action_button_get_disable_timer)
    fatal_error("ButtonSetplay native action dispatcher not found");
  *button_setplay_need_disp_slot =
      (uintptr_t)&pes_match_button_setplay_need_disp;
  *button_setplay_update_slot = (uintptr_t)&pes_match_button_setplay_update;
  *button_setplay_touch_sub_slot =
      (uintptr_t)&pes_match_button_setplay_touch_sub;
  debugPrintf("UE4 input: ButtonSetplay need=%p/%p update=%p/%p "
              "sub=%p/%p touch=%p\n",
              (void *)button_setplay_need_disp_runtime,
              (void *)button_setplay_need_disp_slot,
              (void *)button_setplay_update_runtime,
              (void *)button_setplay_update_slot,
              (void *)button_setplay_touch_sub_runtime,
              (void *)button_setplay_touch_sub_slot,
              match_action_button_pad_event_touch);

  // Observe the two exact set-play state machines through their vtables. The
  // previous implementation replaced MobileSetplayCameraChange's body; these
  // wrappers always execute the original method and only publish a heartbeat.
  const char *goalkick_main_symbol =
      "_ZN5match3pad28ThinkUnitGoalkickPassSupport4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE";
  const uintptr_t goalkick_main_runtime =
      so_find_addr_rx(module, goalkick_main_symbol);
  uintptr_t *goalkick_main_slot = find_vtable_method_slot(
      module, "_ZTVN5match3pad28ThinkUnitGoalkickPassSupportE",
      goalkick_main_runtime, 64);
  if (!goalkick_main_slot)
    fatal_error("GoalkickPassSupport Main vtable slot not found");
  match_goalkick_main_original = (void *)goalkick_main_runtime;
  *goalkick_main_slot = (uintptr_t)&pes_match_goalkick_main;

  const char *corner_main_symbol =
      "_ZN5match3pad26ThinkUnitCornerKickTactics4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE";
  const uintptr_t corner_main_runtime =
      so_find_addr_rx(module, corner_main_symbol);
  uintptr_t *corner_main_slot = find_vtable_method_slot(
      module, "_ZTVN5match3pad26ThinkUnitCornerKickTacticsE",
      corner_main_runtime, 64);
  if (!corner_main_slot)
    fatal_error("CornerKickTactics Main vtable slot not found");
  match_corner_main_original = (void *)corner_main_runtime;
  *corner_main_slot = (uintptr_t)&pes_match_corner_main;
  const char *freekick_main_symbol =
      "_ZN5match3pad24ThinkUnitFreeKickTactics4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE";
  const uintptr_t freekick_main_runtime =
      so_find_addr_rx(module, freekick_main_symbol);
  uintptr_t *freekick_main_slot = find_vtable_method_slot(
      module, "_ZTVN5match3pad24ThinkUnitFreeKickTacticsE",
      freekick_main_runtime, 64);
  if (!freekick_main_slot)
    fatal_error("FreeKickTactics Main vtable slot not found");
  match_freekick_main_original = (void *)freekick_main_runtime;
  *freekick_main_slot = (uintptr_t)&pes_match_freekick_main;

  const char *freekick_is_disp_symbol =
      "_ZNK5match3pad24ThinkUnitFreeKickTactics6IsDispEv";
  const uintptr_t freekick_is_disp_runtime =
      so_find_addr_rx(module, freekick_is_disp_symbol);
  uintptr_t *freekick_is_disp_slot = find_vtable_method_slot(
      module, "_ZTVN5match3pad24ThinkUnitFreeKickTacticsE",
      freekick_is_disp_runtime, 64);
  if (freekick_is_disp_slot) {
    match_freekick_is_disp_original =
        (uint32_t (*)(const void *))freekick_is_disp_runtime;
    *freekick_is_disp_slot = (uintptr_t)&pes_match_freekick_is_disp;
  } else {
    debugPrintf("UE4 input: FreeKickTactics IsDisp vtable slot unavailable; "
                "Main heartbeat only\n");
  }

  const char *kicker_select_main_symbol =
      "_ZN5match3pad21ThinkUnitKickerSelect4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE";
  const uintptr_t kicker_select_main_runtime =
      so_find_addr_rx(module, kicker_select_main_symbol);
  uintptr_t *kicker_select_main_slot = find_vtable_method_slot(
      module, "_ZTVN5match3pad21ThinkUnitKickerSelectE",
      kicker_select_main_runtime, 64);
  if (!kicker_select_main_slot)
    fatal_error("KickerSelect Main vtable slot not found");
  match_kicker_select_main_original = (void *)kicker_select_main_runtime;
  match_kicker_select_is_disp_enable =
      (void *)so_find_addr_rx(
          module,
          "_ZN5match3pad21ThinkUnitKickerSelect12IsDispEnableERKNS0_18ThinkUnitInputDataE");
  *kicker_select_main_slot = (uintptr_t)&pes_match_kicker_select_main;

  const char *goal_demo_pad_main_symbol =
      "_ZN5match3pad28ThinkUnitInteractiveGoalDemo4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE";
  const uintptr_t goal_demo_pad_main_runtime =
      so_find_addr_rx(module, goal_demo_pad_main_symbol);
  uintptr_t *goal_demo_pad_main_slot = find_vtable_method_slot(
      module, "_ZTVN5match3pad28ThinkUnitInteractiveGoalDemoE",
      goal_demo_pad_main_runtime, 64);
  if (!goal_demo_pad_main_slot)
    fatal_error("InteractiveGoalDemo Main vtable slot not found");
  match_goal_demo_pad_main_original = (void *)goal_demo_pad_main_runtime;
  *goal_demo_pad_main_slot = (uintptr_t)&pes_match_goal_demo_pad_main;

  const char *setplay_camera_main_symbol =
      "_ZN5match3pad34ThinkUnitMobileSetplayCameraChange4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE";
  const uintptr_t setplay_camera_main_runtime =
      so_find_addr_rx(module, setplay_camera_main_symbol);
  uintptr_t *setplay_camera_main_slot = find_vtable_method_slot(
      module, "_ZTVN5match3pad34ThinkUnitMobileSetplayCameraChangeE",
      setplay_camera_main_runtime, 64);
  if (!setplay_camera_main_slot)
    fatal_error("MobileSetplayCameraChange Main vtable slot not found");
  match_setplay_camera_main_original = (void *)setplay_camera_main_runtime;
  *setplay_camera_main_slot = (uintptr_t)&pes_match_setplay_camera_main;

  // Penalty kicks use a dedicated mobile swipe path rather than the normal
  // offense/defense buttons. Observe the two native active ThinkUnits so the
  // Android bridge can isolate and translate Joy-Con gestures precisely.
  const char *penalty_kicker_main_symbol =
      "_ZN5match3pad26ThinkUnitMobilePenaltyKick4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE";
  const uintptr_t penalty_kicker_main_runtime =
      so_find_addr_rx(module, penalty_kicker_main_symbol);
  uintptr_t *penalty_kicker_main_slot = find_vtable_method_slot(
      module, "_ZTVN5match3pad26ThinkUnitMobilePenaltyKickE",
      penalty_kicker_main_runtime, 64);
  const char *penalty_goalkeeper_main_symbol =
      "_ZN5match3pad28ThinkUnitMobilePenaltyKickGK4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE";
  const uintptr_t penalty_goalkeeper_main_runtime =
      so_find_addr_rx(module, penalty_goalkeeper_main_symbol);
  uintptr_t *penalty_goalkeeper_main_slot = find_vtable_method_slot(
      module, "_ZTVN5match3pad28ThinkUnitMobilePenaltyKickGKE",
      penalty_goalkeeper_main_runtime, 64);
  const char *penalty_goalkeeper_move_main_symbol =
      "_ZN5match3pad28ThinkUnitMobilePenaltyKickGK32ThinkUnitMobilePenaltyKickGKMove4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE";
  const uintptr_t penalty_goalkeeper_move_main_runtime =
      so_find_addr_rx(module, penalty_goalkeeper_move_main_symbol);
  uintptr_t *penalty_goalkeeper_move_main_slot = find_vtable_method_slot(
      module,
      "_ZTVN5match3pad28ThinkUnitMobilePenaltyKickGK32ThinkUnitMobilePenaltyKickGKMoveE",
      penalty_goalkeeper_move_main_runtime, 64);
  if (!penalty_kicker_main_slot || !penalty_goalkeeper_main_slot ||
      !penalty_goalkeeper_move_main_slot)
    fatal_error("Mobile penalty Main vtable slots not found");
  match_penalty_kicker_main_original = (void *)penalty_kicker_main_runtime;
  match_penalty_goalkeeper_main_original =
      (void *)penalty_goalkeeper_main_runtime;
  match_penalty_goalkeeper_move_main_original =
      (void *)penalty_goalkeeper_move_main_runtime;
  *penalty_kicker_main_slot = (uintptr_t)&pes_match_penalty_kicker_main;
  *penalty_goalkeeper_main_slot =
      (uintptr_t)&pes_match_penalty_goalkeeper_main;
  *penalty_goalkeeper_move_main_slot =
      (uintptr_t)&pes_match_penalty_goalkeeper_move_main;

  debugPrintf("UE4 input: setplay goalkick=%p/%p corner=%p/%p free=%p/%p "
              "kicker=%p/%p goal=%p/%p camera=%p/%p\n",
              (void *)goalkick_main_runtime, (void *)goalkick_main_slot,
              (void *)corner_main_runtime, (void *)corner_main_slot,
              (void *)freekick_main_runtime, (void *)freekick_main_slot,
              (void *)kicker_select_main_runtime,
              (void *)kicker_select_main_slot,
              (void *)goal_demo_pad_main_runtime,
              (void *)goal_demo_pad_main_slot,
              (void *)setplay_camera_main_runtime,
              (void *)setplay_camera_main_slot);
  debugPrintf("UE4 input: penalty kicker=%p/%p goalkeeper=%p/%p move=%p/%p\n",
              (void *)penalty_kicker_main_runtime,
              (void *)penalty_kicker_main_slot,
              (void *)penalty_goalkeeper_main_runtime,
              (void *)penalty_goalkeeper_main_slot,
              (void *)penalty_goalkeeper_move_main_runtime,
              (void *)penalty_goalkeeper_move_main_slot);

  const char *ball_position_broadcast_symbol =
      "_ZN5match6camera6plugin12InplayCamera24GetBallPositionBroadcastERKfRK8HomeAwayPN4math7Vector3ERfb";
  const uintptr_t ball_position_broadcast =
      so_find_addr(module, ball_position_broadcast_symbol);
  const uintptr_t ball_position_broadcast_runtime =
      so_find_addr_rx(module, ball_position_broadcast_symbol);
  static const uint32_t expected_ball_position_broadcast_entry[4] = {
      0xd10703ff, 0x6d123bef, 0x6d1333ed, 0x6d142beb,
  };
  if (memcmp((void *)ball_position_broadcast,
             expected_ball_position_broadcast_entry,
             sizeof(expected_ball_position_broadcast_entry)) != 0)
    fatal_error("Unexpected Broadcast ball-position entry at %p",
                (void *)ball_position_broadcast);
  inplay_ball_position_broadcast_resume =
      ball_position_broadcast_runtime + 0x10;
  match_ball_position_broadcast_original =
      pes_inplay_ball_position_broadcast_original;
  match_ball_info_get_trans =
      (void *)so_find_addr_rx(module,
          "_ZNK5match8registry8BallInfo8GetTransEv");
  hook_arm64(ball_position_broadcast,
             (uintptr_t)&pes_inplay_ball_position_broadcast);

  // Replay owns input from ModeInit until ModeEnd. Hooking its virtual
  // lifecycle is safer than replacing CheckSkip's entry and remains exact
  // even when ScreenTap still reports a gameplay mode during transitions.
  const char *replay_mode_init_symbol =
      "_ZN5match6Replay8ModeInitEPKN5cobra4game7ContextE";
  const char *replay_mode_main_symbol =
      "_ZN5match6Replay8ModeMainEPKN5cobra4game7ContextE";
  const char *replay_mode_end_symbol =
      "_ZN5match6Replay7ModeEndEPKN5cobra4game7ContextE";
  const uintptr_t replay_mode_init_runtime =
      so_find_addr_rx(module, replay_mode_init_symbol);
  const uintptr_t replay_mode_main_runtime =
      so_find_addr_rx(module, replay_mode_main_symbol);
  const uintptr_t replay_mode_end_runtime =
      so_find_addr_rx(module, replay_mode_end_symbol);
  uintptr_t *replay_mode_init_slot = find_vtable_method_slot(
      module, "_ZTVN5match6ReplayE", replay_mode_init_runtime, 64);
  uintptr_t *replay_mode_main_slot = find_vtable_method_slot(
      module, "_ZTVN5match6ReplayE", replay_mode_main_runtime, 64);
  uintptr_t *replay_mode_end_slot = find_vtable_method_slot(
      module, "_ZTVN5match6ReplayE", replay_mode_end_runtime, 64);
  if (!replay_mode_init_slot || !replay_mode_main_slot ||
      !replay_mode_end_slot)
    fatal_error("Replay lifecycle vtable slots not found");
  match_replay_mode_init_original =
      (uint32_t (*)(void *, const void *))replay_mode_init_runtime;
  match_replay_mode_main_original =
      (uint32_t (*)(void *, const void *))replay_mode_main_runtime;
  match_replay_mode_end_original =
      (uint32_t (*)(void *, const void *))replay_mode_end_runtime;
  *replay_mode_init_slot = (uintptr_t)&pes_match_replay_mode_init;
  *replay_mode_main_slot = (uintptr_t)&pes_match_replay_mode_main;
  *replay_mode_end_slot = (uintptr_t)&pes_match_replay_mode_end;

  // Foul/offside/out-of-play demos use native ThinkUnitSkip objects. Queue a
  // Joy-Con request from Android, then return their exact command (43) from
  // Main on the game's thread; no UI member is called cross-thread.
  const char *think_unit_base_main_symbol =
      "_ZN5match3pad13ThinkUnitBase4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE";
  const uintptr_t think_unit_base_main_runtime =
      so_find_addr_rx(module, think_unit_base_main_symbol);
  uintptr_t *demo_skip_main_slot = find_vtable_method_slot(
      module, "_ZTVN5match3pad17ThinkUnitDemoSkipE",
      think_unit_base_main_runtime, 64);
  uintptr_t *outofplay_skip_main_slot = find_vtable_method_slot(
      module, "_ZTVN5match3pad22ThinkUnitOutofPlaySkipE",
      think_unit_base_main_runtime, 64);
  if (!demo_skip_main_slot || !outofplay_skip_main_slot)
    fatal_error("Native demo-skip Main vtable slots not found");
  match_demo_skip_main_original =
      (uint32_t (*)(void *, const void *, uint32_t))
          think_unit_base_main_runtime;
  match_outofplay_skip_main_original =
      (uint32_t (*)(void *, const void *, uint32_t))
          think_unit_base_main_runtime;
  *demo_skip_main_slot = (uintptr_t)&pes_match_demo_skip_main;
  *outofplay_skip_main_slot = (uintptr_t)&pes_match_outofplay_skip_main;
  debugPrintf("UE4 input: replay lifecycle=%p/%p/%p demo=%p/%p\n",
              (void *)replay_mode_init_slot, (void *)replay_mode_main_slot,
              (void *)replay_mode_end_slot, (void *)demo_skip_main_slot,
              (void *)outofplay_skip_main_slot);

  const char *replay_skip_symbol =
      "_ZN5match6Replay9CheckSkipEPKN5cobra4game7ContextE";
  const uintptr_t replay_skip = so_find_addr(module, replay_skip_symbol);
  const uintptr_t replay_skip_runtime =
      so_find_addr_rx(module, replay_skip_symbol);
  static const uint32_t expected_replay_skip_entry[4] = {
      0xf81c0ff8, 0xa9015bf7, 0xa90253f5, 0xa9037bf3,
  };
  if (memcmp((void *)replay_skip, expected_replay_skip_entry,
             sizeof(expected_replay_skip_entry)) != 0)
    fatal_error("Unexpected match::Replay::CheckSkip entry at %p",
                (void *)replay_skip);
  match_replay_check_skip_resume = replay_skip_runtime + 0x10;
  match_goal_demo_get_goal_side =
      (void *)so_find_addr_rx(module,
          "_ZN5match8GoalDemo11GetGoalSideEPKNS_8registry8RegistryE");
  match_goal_demo_is_cpu_goal =
      (void *)so_find_addr_rx(module,
          "_ZN5match8GoalDemo9IsCpuGoalEPKNS_8registry8RegistryE");
  const uintptr_t own_goal_demo = so_find_addr(
      module, "_ZN5match8GoalDemo13IsOwnGoalDemoEv");
  static const uint32_t expected_own_goal_demo_entry[4] = {
      0xb9400808, 0x529fe609, 0x72bfff89, 0x0b090108,
  };
  if (!own_goal_demo ||
      memcmp((const void *)own_goal_demo, expected_own_goal_demo_entry,
             sizeof(expected_own_goal_demo_entry)) != 0)
    fatal_error("Unexpected GoalDemo::IsOwnGoalDemo entry at %p",
                (void *)own_goal_demo);
  hook_arm64(own_goal_demo,
             (uintptr_t)&pes_match_goal_demo_is_own_goal);
  const char *goal_demo_init_symbol =
      "_ZN5match8GoalDemo23InteractiveGoalDemoInitEv";
  const uintptr_t goal_demo_init =
      so_find_addr(module, goal_demo_init_symbol);
  const uintptr_t goal_demo_init_runtime =
      so_find_addr_rx(module, goal_demo_init_symbol);
  static const uint32_t expected_goal_demo_init_entry[4] = {
      0xa9bf7bf3, 0xf9401809, 0xb940380a, 0x320003e8,
  };
  if (!goal_demo_init ||
      memcmp((const void *)goal_demo_init, expected_goal_demo_init_entry,
             sizeof(expected_goal_demo_init_entry)) != 0)
    fatal_error("Unexpected GoalDemo::InteractiveGoalDemoInit entry at %p",
                (void *)goal_demo_init);
  match_goal_demo_init_resume = goal_demo_init_runtime + 0x10;
  hook_arm64(goal_demo_init, (uintptr_t)&pes_match_goal_demo_init_hook);
  match_global_registry_get_instance =
      (void *)so_find_addr_rx(module,
          "_ZN5match8registry14GlobalRegistry19GetInstanceForRetryEv");
  match_global_registry_get_order_info =
      (void *)so_find_addr_rx(
          module,
          "_ZNK5match8registry14GlobalRegistry12GetOrderInfoE8HomeAway");
  match_order_info_get_member_id =
      (void *)so_find_addr_rx(
          module,
          "_ZNK5match8registry9OrderInfo22GetMemberIdFromOrderNoE7OrderNo");
  match_tmpdb_match_get_player =
      (void *)so_find_addr_rx(
          module, "_ZNK5tmpdb5Match9GetPlayerERK8HomeAwayRKj");
  match_cursor_is_user_control_team =
      (void *)so_find_addr_rx(module,
          "_ZNK5match8registry10CursorInfo34IsUserControlTeamWithoutOnlineUserE8HomeAwayNS0_14SupportSetting16CursorChangeTypeE");
  // Replay/GoalDemo transition hooks are intentionally disabled for now.
  // The stable UE4 path handles these screens safely; the direct trampolines
  // were the only new code executed at the crash boundary.
  (void)replay_skip;

  const char *goal_demo_update_symbol =
      "_ZN5match8GoalDemo20UpdateGoalDemo2DInfoEPKNS_8registry8RegistryEPNS1_12Screen2dInfoEPKN5cobra4game7ContextE";
  const uintptr_t goal_demo_update =
      so_find_addr(module, goal_demo_update_symbol);
  const uintptr_t goal_demo_update_runtime =
      so_find_addr_rx(module, goal_demo_update_symbol);
  static const uint32_t expected_goal_demo_update_entry[4] = {
      0xd10443ff, 0xa90b6ffc, 0xa90c67fa, 0xa90d5ff8,
  };
  if (memcmp((void *)goal_demo_update, expected_goal_demo_update_entry,
             sizeof(expected_goal_demo_update_entry)) != 0)
    fatal_error("Unexpected GoalDemo::UpdateGoalDemo2DInfo entry at %p",
                (void *)goal_demo_update);
  match_goal_demo_update_resume = goal_demo_update_runtime + 0x10;
  (void)goal_demo_update;

  // Foul/offside cutscenes use the fixed-demo flow rather than Replay. Make
  // the native eligibility gate report true and route the next controller
  // press through FixDemoManager::Skip.
  const uintptr_t demo_skip_ok = so_find_addr(
      module, "_ZNK5match8registry8MatchEnv12IsDemoSkipOkEv");
  (void)demo_skip_ok;
  const char *flow_check_skip_symbol =
      "_ZN5match4Flow16CheckSkipFixDemoEbb";
  const uintptr_t flow_check_skip =
      so_find_addr(module, flow_check_skip_symbol);
  const uintptr_t flow_check_skip_runtime =
      so_find_addr_rx(module, flow_check_skip_symbol);
  static const uint32_t expected_flow_check_skip[4] = {
      0xf81e0ff4, 0xa9017bf3, 0x39754008, 0xaa0003f3,
  };
  if (memcmp((void *)flow_check_skip, expected_flow_check_skip,
             sizeof(expected_flow_check_skip)) != 0)
    fatal_error("Unexpected Flow::CheckSkipFixDemo entry at %p",
                (void *)flow_check_skip);
  match_flow_check_skip_fix_demo_resume = flow_check_skip_runtime + 0x10;
  // Do not resolve/call FixDemoManager::Skip directly: it is a member method
  // whose manager instance is owned by Flow. The native Flow path consumes the
  // Cobra skip bit emitted by android_shim.c.
  match_fix_demo_skip = NULL;
  (void)flow_check_skip;

  const char *pause_update_symbol =
      "_ZN4menu10MatchPause23UpdatePostControlWindowEN10menusystem6Window10PAD_STATUSE";
  const uintptr_t pause_update = so_find_addr(module, pause_update_symbol);
  const uintptr_t pause_update_runtime =
      so_find_addr_rx(module, pause_update_symbol);
  static const uint32_t expected_pause_update_entry[4] = {
      0xd10143ff, 0xa9025bf7, 0xa90353f5, 0xa9047bf3,
  };
  if (memcmp((void *)pause_update, expected_pause_update_entry,
             sizeof(expected_pause_update_entry)) != 0)
    fatal_error("Unexpected MatchPause update entry at %p",
                (void *)pause_update);
  match_pause_update_resume = pause_update_runtime + 0x10;
  match_pause_pad_event_back =
      (void *)so_find_addr_rx(module, "_ZN4menu10MatchPause12PadEventBackEv");
  match_pause_exec_event_decide =
      (void *)so_find_addr_rx(module,
          "_ZN4menu10MatchPause15ExecEventDecideERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS2_9AllocatorIcEEEE");

  // Keep the native full-screen Pause frontend, but omit the three mobile
  // icons that do not belong to the Switch flow: Controls List, General
  // Settings and Sound. MatchTouchMenuInitParam then lays out the remaining
  // Game Plan, Camera and Top Menu icons normally.
  const uintptr_t pause_get_init = so_find_addr(
      module, "_ZN4menu10MatchPause12GetInitParamEv");
  patch_checked_u32(pause_get_init + 0x580, 0x96edfb7d, 0xd503201f,
                    "MatchPause operation-guide icon");
  patch_checked_u32(pause_get_init + 0x60c, 0x96edfb5a, 0xd503201f,
                    "MatchPause general-settings icon");
  patch_checked_u32(pause_get_init + 0x6bc, 0x96edfb2e, 0xd503201f,
                    "MatchPause sound icon");
  matchplan_squad_load =
      (void *)so_find_addr_rx(module,
          "_ZN9matchPlan16SquadEditUtility30LoadSquadDataFromMatchPlanDataEv");
  matchplan_squad_save =
      (void *)so_find_addr_rx(module,
          "_ZN9matchPlan16SquadEditUtility28SaveSquadDataToMatchPlanDataEv");
  match_squad_data_get_tmpdb_player =
      (void *)so_find_addr_rx(module,
          "_ZNK5tmpdb9SquadData14GetTmpdbPlayerERKNS_8PlayerIdE");
  match_tmpdb_player_get_name =
      (void *)so_find_addr_rx(module, "_ZNK5tmpdb6Player7GetNameEv");
  match_tmpdb_player_get_data =
      (void *)so_find_addr_rx(
          module, "_ZNK5tmpdb10PlayerBase7GetDataEjRj");
  match_squad_data_get_order_no =
      (void *)so_find_addr_rx(module,
          "_ZNK5tmpdb9SquadData15GetSquadOrderNoERKNS_8PlayerIdE");
  match_squad_data_get_member_id =
      (void *)so_find_addr_rx(module,
          "_ZNK5tmpdb9SquadData16GetSquadMemberIdERKNS_8PlayerIdE");
  match_squad_data_is_starting =
      (void *)so_find_addr_rx(module,
          "_ZNK5tmpdb9SquadData21IsExistStartingMemberERKNS_8PlayerIdE");
  match_swap_member_info_construct =
      (void *)so_find_addr_rx(module,
          "_ZN5tmpdb14SwapMemberInfoC1E7OrderNo8MemberIdRKNS_8PlayerIdE");
  match_replace_squad_player =
      (void *)so_find_addr_rx(module,
          "_ZN4menu22MyClubSquadEditUtility18ReplaceSquadPlayerERN5tmpdb9SquadDataERKNS1_14SwapMemberInfoES6_");
  match_squad_data_get_tactics =
      (void *)so_find_addr_rx(module,
          "_ZNK5tmpdb9SquadData14GetTacticsKindEv");
  match_squad_data_set_tactics =
      (void *)so_find_addr_rx(module,
          "_ZN5tmpdb9SquadData14SetTacticsKindENS_5Coach11TacticsKindE");
  hook_arm64(pause_update, (uintptr_t)&pes_match_pause_update_hook);

  const char *squad_edit_update_symbol =
      "_ZN4menu15MyClubSquadEdit23UpdatePostControlWindowEN10menusystem6Window10PAD_STATUSE";
  const uintptr_t squad_edit_update =
      so_find_addr(module, squad_edit_update_symbol);
  const uintptr_t squad_edit_update_runtime =
      so_find_addr_rx(module, squad_edit_update_symbol);
  static const uint32_t expected_squad_edit_update[4] = {
      0xd10283ff, 0xa9046ffc, 0xa90567fa, 0xa9065ff8,
  };
  if (memcmp((void *)squad_edit_update, expected_squad_edit_update,
             sizeof(expected_squad_edit_update)) != 0) {
    debugPrintf("UE4 hook: MyClubSquadEdit update signature mismatch at %p; "
                "native update retained\n",
                (void *)squad_edit_update);
  } else {
    pes_match_squad_edit_update_resume = squad_edit_update_runtime + 0x10;
    hook_arm64(squad_edit_update,
               (uintptr_t)&pes_match_squad_edit_update_hook);
  }

  const uintptr_t pause_camera_update_runtime = so_find_addr_rx(
      module,
      "_ZN4menu28MatchPauseTouchCameraSetting23UpdatePostControlWindowEN10menusystem6Window10PAD_STATUSE");
  uintptr_t *pause_camera_update_slot = find_vtable_method_slot(
      module, "_ZTVN4menu28MatchPauseTouchCameraSettingE",
      pause_camera_update_runtime, 128);
  if (!pause_camera_update_slot) {
    debugPrintf("UE4 hook: camera-setting update vtable slot not found; "
                "camera page remains native\n");
    match_pause_camera_update_original = NULL;
  } else {
    match_pause_camera_update_original = (void *)pause_camera_update_runtime;
    *pause_camera_update_slot = (uintptr_t)&pes_match_pause_camera_update;
  }
  match_pause_camera_swipe =
      (void *)so_find_addr_rx(module,
          "_ZN4menu28MatchPauseTouchCameraSetting16PadEventSwipeEndEjj");
  match_pause_camera_footer =
      (void *)so_find_addr_rx(module,
          "_ZN4menu28MatchPauseTouchCameraSetting19PadEventFooterTouchEN10menusystem17MOBILE_FOOTER_KEYE");

  const char *pause_d1_symbol = "_ZN4menu10MatchPauseD1Ev";
  const char *pause_d0_symbol = "_ZN4menu10MatchPauseD0Ev";
  const uintptr_t pause_d1 = so_find_addr(module, pause_d1_symbol);
  const uintptr_t pause_d0 = so_find_addr(module, pause_d0_symbol);
  const uintptr_t pause_d1_runtime = so_find_addr_rx(module, pause_d1_symbol);
  const uintptr_t pause_d0_runtime = so_find_addr_rx(module, pause_d0_symbol);
  static const uint32_t expected_pause_destructor[4] = {
      0xa9bf7bf3, 0xd000c828, 0xf9426d08, 0xaa0003f3,
  };
  if (memcmp((void *)pause_d1, expected_pause_destructor,
             sizeof(expected_pause_destructor)) != 0 ||
      memcmp((void *)pause_d0, expected_pause_destructor,
             sizeof(expected_pause_destructor)) != 0)
    fatal_error("Unexpected MatchPause destructor entry");
  match_pause_d1_resume = pause_d1_runtime + 0x10;
  match_pause_d0_resume = pause_d0_runtime + 0x10;
  // Displaced ADRP/LDR resolves the MatchPause vtable pointer stored here.
  pes_match_pause_destructor_slot =
      (uintptr_t)module->load_virtbase + 0x95ca4d8;
  hook_arm64(pause_d1, (uintptr_t)&pes_match_pause_d1_hook);
  hook_arm64(pause_d0, (uintptr_t)&pes_match_pause_d0_hook);

  const char *result_full_symbol =
      "_ZN4menu19MatchResultMainMenuC1EPKcb";
  const char *result_half_symbol =
      "_ZN4menu27MatchResultMainMenuHalfTimeC1EPKcb";
  const uintptr_t result_full = so_find_addr(module, result_full_symbol);
  const uintptr_t result_half = so_find_addr(module, result_half_symbol);
  const uintptr_t result_full_runtime =
      so_find_addr_rx(module, result_full_symbol);
  const uintptr_t result_half_runtime =
      so_find_addr_rx(module, result_half_symbol);
  static const uint32_t expected_result_full_entry[4] = {
      0xf81d0ff6, 0xa90153f5, 0xa9027bf3, 0x2a0203f4,
  };
  static const uint32_t expected_result_half_entry[4] = {
      0xa9be53f5, 0xa9017bf3, 0x2a0203f3, 0xaa0103f4,
  };
  if (memcmp((void *)result_full, expected_result_full_entry,
             sizeof(expected_result_full_entry)) != 0 ||
      memcmp((void *)result_half, expected_result_half_entry,
             sizeof(expected_result_half_entry)) != 0)
    fatal_error("Unexpected match result constructor entry");
  match_result_full_resume = result_full_runtime + 0x10;
  match_result_half_resume = result_half_runtime + 0x10;
  match_listener_instance =
      (void **)so_find_addr_rx(module,
          "_ZN9game_mode13MatchListener11s_pInstanceE");
  match_result_exec_event_decide =
      (void *)so_find_addr_rx(module,
          "_ZN4menu19MatchResultMainMenu15ExecEventDecideERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS2_9AllocatorIcEEEE");
  match_result_footer_touch =
      (void *)so_find_addr_rx(module,
          "_ZN4menu22MatchTouchIconMenuBase19PadEventFooterTouchEN10menusystem17MOBILE_FOOTER_KEYE");
  hook_arm64(result_full, (uintptr_t)&pes_match_result_full_hook);
  hook_arm64(result_half, (uintptr_t)&pes_match_result_half_hook);

  const uintptr_t result_update_runtime = so_find_addr_rx(
      module, "_ZN4menu19MatchResultMainMenu22UpdatePreControlWindowEv");
  const uintptr_t result_vtable =
      so_find_addr(module, "_ZTVN4menu19MatchResultMainMenuE");
  uintptr_t *result_update_slot = NULL;
  for (uint32_t index = 2; index < 128; index++) {
    uintptr_t *slot =
        (uintptr_t *)(result_vtable + index * sizeof(uintptr_t));
    if (*slot == result_update_runtime) {
      result_update_slot = slot;
      break;
    }
  }
  if (!result_update_slot)
    fatal_error("MatchResultMainMenu update vtable slot not found");
  match_result_update_original = (void *)result_update_runtime;
  *result_update_slot = (uintptr_t)&pes_match_result_update;

  const char *team_stats_update_symbol =
      "_ZN4menu20MatchResultTeamStats22UpdatePreControlWindowEv";
  const uintptr_t team_stats_update =
      so_find_addr(module, team_stats_update_symbol);
  const uintptr_t team_stats_update_runtime =
      so_find_addr_rx(module, team_stats_update_symbol);
  static const uint32_t expected_team_stats_update[4] = {
      0xf81e0ff4, 0xa9017bf3, 0xaa0003f3, 0x96efd8f7,
  };
  if (memcmp((void *)team_stats_update, expected_team_stats_update,
             sizeof(expected_team_stats_update)) != 0)
    fatal_error("Unexpected MatchResultTeamStats update entry at %p",
                (void *)team_stats_update);
  pes_match_team_stats_update_resume = team_stats_update_runtime + 0x10;
  pes_match_team_stats_debug_aging_get_state = so_find_addr_rx(
      module, "_ZN3sys15DebugAgingState13GetAgingStateEv");
  hook_arm64(team_stats_update,
             (uintptr_t)&pes_match_team_stats_update_hook);

  const char *result_half_update_symbol =
      "_ZN4menu27MatchResultMainMenuHalfTime22UpdatePreControlWindowEv";
  const uintptr_t result_half_update =
      so_find_addr(module, result_half_update_symbol);
  const uintptr_t result_half_update_runtime =
      so_find_addr_rx(module, result_half_update_symbol);
  static const uint32_t expected_result_half_update[4] = {
      0xd10103ff, 0xf90013f4, 0xa9037bf3, 0xaa0003f3,
  };
  if (memcmp((void *)result_half_update, expected_result_half_update,
             sizeof(expected_result_half_update)) != 0)
    fatal_error("Unexpected half-time result update entry at %p",
                (void *)result_half_update);
  match_result_half_update_resume = result_half_update_runtime + 0x10;
  hook_arm64(result_half_update,
             (uintptr_t)&pes_match_result_half_update_hook);

  // The full result screen is intentionally tile-free. Half-time retains
  // only the native Game Plan tile; B is handled by the result controller
  // route and returns to the Top Menu.
  const uintptr_t full_result_init = so_find_addr(
      module, "_ZN4menu19MatchResultMainMenu12GetInitParamEv");
  static const uintptr_t full_result_icon_offsets[] = {
      0xe0, 0x134, 0x18c, 0x1e4, 0x238, 0x28c,
  };
  static const uint32_t full_result_icon_bl[] = {
      0x96ede1da, 0x96ede1c5, 0x96ede1af,
      0x96ede199, 0x96ede184, 0x96ede16f,
  };
  for (uint32_t i = 0; i < sizeof(full_result_icon_offsets) /
                              sizeof(full_result_icon_offsets[0]); i++)
    patch_checked_u32(full_result_init + full_result_icon_offsets[i],
                      full_result_icon_bl[i], 0xd503201f,
                      "full result tile removal");

  const uintptr_t half_result_init = so_find_addr(
      module, "_ZN4menu27MatchResultMainMenuHalfTime12GetInitParamEv");
  static const uintptr_t half_result_icon_offsets[] = {
      0x1e8, 0x23c, 0x294, 0x2e8, 0x33c,
  };
  static const uint32_t half_result_icon_bl[] = {
      0x96eddd8f, 0x96eddd7a, 0x96eddd64,
      0x96eddd4f, 0x96eddd3a,
  };
  for (uint32_t i = 0; i < sizeof(half_result_icon_offsets) /
                              sizeof(half_result_icon_offsets[0]); i++)
    patch_checked_u32(half_result_init + half_result_icon_offsets[i],
                      half_result_icon_bl[i], 0xd503201f,
                      "half result tile removal");

  const char *tutorial_guide_update_symbol =
      "_ZN4menu18MatchTutorialGuide22UpdatePreControlWindowEv";
  const uintptr_t tutorial_guide_update =
      so_find_addr(module, tutorial_guide_update_symbol);
  const uintptr_t tutorial_guide_update_runtime =
      so_find_addr_rx(module, tutorial_guide_update_symbol);
  static const uint32_t expected_tutorial_guide_update[4] = {
      0xd10183ff, 0xa90453f5, 0xa9057bf3, 0xb9424808,
  };
  if (memcmp((void *)tutorial_guide_update,
             expected_tutorial_guide_update,
             sizeof(expected_tutorial_guide_update)) != 0)
    fatal_error("Unexpected MatchTutorialGuide update entry at %p",
                (void *)tutorial_guide_update);
  match_tutorial_guide_update_resume = tutorial_guide_update_runtime + 0x10;
  hook_arm64(tutorial_guide_update,
             (uintptr_t)&pes_match_tutorial_guide_update_hook);

  // First-use set-play/penalty help is owned by a separate in-match window.
  // Its native footer becomes active only on the final tutorial scene; use
  // that exact state for both the A helper lifetime and the Play dispatch.
  const char *inmatch_tutorial_update_symbol =
      "_ZN7match2D6Screen23TutorialInMatchTutorial22UpdatePreControlWindowEv";
  const char *inmatch_tutorial_footer_symbol =
      "_ZN7match2D6Screen23TutorialInMatchTutorial19PadEventFooterTouchEN10menusystem17MOBILE_FOOTER_KEYE";
  const uintptr_t inmatch_tutorial_update_runtime =
      so_find_addr_rx(module, inmatch_tutorial_update_symbol);
  const uintptr_t inmatch_tutorial_footer_runtime =
      so_find_addr_rx(module, inmatch_tutorial_footer_symbol);
  uintptr_t *inmatch_tutorial_update_slot = find_vtable_method_slot(
      module, "_ZTVN7match2D6Screen23TutorialInMatchTutorialE",
      inmatch_tutorial_update_runtime, 128);
  if (!inmatch_tutorial_update_slot)
    fatal_error("TutorialInMatchTutorial update vtable slot not found");
  match_inmatch_tutorial_update_original =
      (void *)inmatch_tutorial_update_runtime;
  match_inmatch_tutorial_footer_touch =
      (void *)inmatch_tutorial_footer_runtime;
  match_inmatch_tutorial_is_explaining =
      (void *)so_find_addr_rx(
          module,
          "_ZN7match2D6Screen23TutorialInMatchTutorial12IsExplainingEv");
  match_window_get_pad_key_active =
      (void *)so_find_addr_rx(
          module,
          "_ZN10menusystem6Window15GetPadKeyActiveENS_12WindowPadKey7PAD_KEYE");
  if (!match_inmatch_tutorial_footer_touch ||
      !match_inmatch_tutorial_is_explaining ||
      !match_window_get_pad_key_active)
    fatal_error("TutorialInMatchTutorial native footer route not found");
  *inmatch_tutorial_update_slot =
      (uintptr_t)&pes_match_inmatch_tutorial_update;
  debugPrintf("UE4 input: replay=%p pause=%p destructor=%p/%p "
              "result=%p/%p halfUpdate=%p\n",
              (void *)replay_skip_runtime, (void *)pause_update_runtime,
              (void *)pause_d1_runtime, (void *)pause_d0_runtime,
              (void *)result_full_runtime, (void *)result_half_runtime,
              (void *)result_half_update_runtime);

  // VirtualPad::NeedDisp also gates ScreenTap updates in this mobile build.
  // Returning false hid the graphics but stopped the offense/defense heartbeat
  // and therefore disabled every synthetic controller touch. Keep it enabled;
  // visual-only hiding must be implemented later through alpha/render state.
  const char *virtual_pad_need_disp_symbol =
      "_ZN7match2D6Screen10VirtualPad8NeedDispEv";
  const uintptr_t virtual_pad_need_disp =
      so_find_addr(module, virtual_pad_need_disp_symbol);
  static const uint32_t expected_virtual_pad_need_disp[2] = {
      0x320003e0, // orr w0, wzr, #1
      0xd65f03c0, // ret
  };
  if (memcmp((void *)virtual_pad_need_disp,
             expected_virtual_pad_need_disp,
             sizeof(expected_virtual_pad_need_disp)) != 0)
    fatal_error("Unexpected VirtualPad::NeedDisp bytes at %p",
                (void *)virtual_pad_need_disp);
  debugPrintf("UE4 input: stock virtual pad retained at %p for ScreenTap "
              "controller routing\n",
              (void *)virtual_pad_need_disp);

  // Do not force SetVisible(false): that also disables the ButtonObject state
  // needed by the synthetic controller touches. Wrap UpdateInfo instead and
  // tint its two movement and four action clips to 2% alpha after the stock
  // routine has made them visible.
  const char *virtual_pad_update_symbol =
      "_ZN7match2D6Screen10VirtualPad10UpdateInfoEv";
  const uintptr_t virtual_pad_update =
      so_find_addr(module, virtual_pad_update_symbol);
  const uintptr_t virtual_pad_update_runtime =
      so_find_addr_rx(module, virtual_pad_update_symbol);
  static const uint32_t expected_virtual_pad_update[4] = {
      0xd10383ff, // sub sp, sp, #0xe0
      0xfd0033ea, // str d10, [sp, #96]
      0x6d0723e9, // stp d9, d8, [sp, #112]
      0xa9086ffc, // stp x28, x27, [sp, #128]
  };
  if (memcmp((const void *)virtual_pad_update, expected_virtual_pad_update,
             sizeof(expected_virtual_pad_update)) != 0)
    fatal_error("Unexpected VirtualPad::UpdateInfo bytes at %p",
                (void *)virtual_pad_update);
  virtual_pad_set_color =
      (void *)so_find_addr_rx(module,
                             "_ZN5flash9MovieClip8SetColorEffff");
  pes_virtual_pad_update_resume = virtual_pad_update_runtime + 0x10;
  hook_arm64(virtual_pad_update, (uintptr_t)&pes_virtual_pad_update_info);
  debugPrintf("UE4 input: virtual pad clips retained and tinted to 2%% alpha "
              "at %p; ScreenTap state remains interactive\n",
              (void *)virtual_pad_update);

  // PES consumes Android/UE gamepad events before they reach gameplay. Inject
  // Switch input into cobra::game::Pad after its clear/touch phase instead, so
  // the game's own edge/repeat logic and context-sensitive actions remain
  // authoritative while the mobile touch overlay stays enabled.
  const char *pad_update_symbol = "_ZN5cobra4game3Pad6UpdateEv";
  const uintptr_t pad_update_backing =
      so_find_addr(module, pad_update_symbol);
  const uintptr_t pad_update_runtime =
      so_find_addr_rx(module, pad_update_symbol);
  uint32_t *pad_hook = (uint32_t *)(pad_update_backing + 0xd4);
  static const uint32_t expected_pad_words[4] = {
      0x2941a66b, // ldp w11, w9, [x19, #12]
      0xaa1f03e8, // mov x8, xzr
      0x9100826a, // add x10, x19, #0x20
      0x0a2b012c, // bic w12, w9, w11
  };
  if (memcmp(pad_hook, expected_pad_words, sizeof(expected_pad_words)) != 0)
    fatal_error("Unexpected cobra::Pad::Update hook bytes at %p",
                (void *)pad_hook);
  cobra_pad_update_resume = pad_update_runtime + 0xe4;
  hook_arm64((uintptr_t)pad_hook, (uintptr_t)&cobra_pad_update_hook);
  debugPrintf("UE4 hook: cobra Pad::Update backing=%p runtime=%p hook=%p "
              "resume=%p\n",
              (void *)pad_update_backing, (void *)pad_update_runtime,
              cobra_pad_update_hook, (void *)cobra_pad_update_resume);

  // Reconnect the mobile cursor to the real-pad route. These two functions are
  // fully replaced, so no displaced instructions need to be replayed.
  const char *cursor_set_pad_symbol =
      "_ZN5match8registry10CursorData8SetPadNoEj";
  const uintptr_t cursor_set_pad_backing =
      so_find_addr(module, cursor_set_pad_symbol);
  const uintptr_t cursor_set_pad_runtime =
      so_find_addr_rx(module, cursor_set_pad_symbol);
  static const uint32_t expected_cursor_words[4] = {
      0x7100003f, // cmp w1, #0
      0x5a9f03e8, // csetm w8, ne
      0xb9001008, // str w8, [x0, #16]
      0xd65f03c0, // ret
  };
  if (memcmp((void *)cursor_set_pad_backing, expected_cursor_words,
             sizeof(expected_cursor_words)) != 0)
    fatal_error("Unexpected CursorData::SetPadNo hook bytes at %p",
                (void *)cursor_set_pad_backing);
  hook_arm64(cursor_set_pad_backing, (uintptr_t)&pes_cursor_set_pad_no);
  debugPrintf("UE4 hook: CursorData::SetPadNo backing=%p runtime=%p "
              "replacement=%p\n",
              (void *)cursor_set_pad_backing, (void *)cursor_set_pad_runtime,
              pes_cursor_set_pad_no);

  const char *real_pad_enable_symbol =
      "_ZN5match8registry8PadInput18SetRealPadIsEnableEjb";
  const uintptr_t real_pad_enable_backing =
      so_find_addr(module, real_pad_enable_symbol);
  const uintptr_t real_pad_enable_runtime =
      so_find_addr_rx(module, real_pad_enable_symbol);
  static const uint32_t expected_enable_words[4] = {
      0x71001c3f, // cmp w1, #7
      0x540000c8, // b.hi return
      0x528d940a, // mov w10, #0x6ca0
      0x12000048, // and w8, w2, #1
  };
  if (memcmp((void *)real_pad_enable_backing, expected_enable_words,
             sizeof(expected_enable_words)) != 0)
    fatal_error("Unexpected PadInput::SetRealPadIsEnable hook bytes at %p",
                (void *)real_pad_enable_backing);
  hook_arm64(real_pad_enable_backing,
             (uintptr_t)&pes_set_real_pad_is_enable);
  debugPrintf("UE4 hook: PadInput::SetRealPadIsEnable backing=%p runtime=%p "
              "replacement=%p\n",
              (void *)real_pad_enable_backing,
              (void *)real_pad_enable_runtime, pes_set_real_pad_is_enable);

  // Let CRI's switcher select AAudio through its normal initialization path.
  // Its success-only warning deadlocks inside this Android-free runtime, so
  // skip that notification while leaving loader failures and SLES fallback
  // untouched.
  // NOTE: the actual criNcv_EnableAAudio_ANDROID(1) call is deferred to
  // ue4_hooks_post_finalize() because the SO code memory is not yet
  // executable at this point (load_base is RW heap; svcMapProcessCodeMemory
  // runs later in so_finalize).  Calling through a heap pointer would crash
  // on real Switch hardware even though Ryujinx tolerates it.
  const uintptr_t aaudio_loader_open = so_find_addr(
      module, "_ZN26criNcvAndroidAAudio_Loader4openEv");
  patch_checked_u32(aaudio_loader_open + 0x42c, 0x96ea80ceu, 0xd503201fu,
                    "AAudio loader success notification");
  aaudio_shim_set_game_state_diagnostics(
      (const uint8_t *)so_try_find_addr_rx(
          module, "_ZN5sound3sys9Interface10m_InitFlagE"),
      (const void *const *)so_try_find_addr_rx(
          module, "_ZN5sound3sys9Interface7m_pFileE"),
      (const uint8_t *)so_try_find_addr_rx(
          module, "_ZN5sound3sys4Load10m_InitFlagE"),
      (const uint8_t *)so_try_find_addr_rx(
          module, "_ZN5sound3sys4load7Manager10m_InitFlagE"),
      (const uint8_t *)so_try_find_addr_rx(
          module, "_ZN5sound3sys12MusicManager15m_IsInitializedE"),
      (const uint64_t *)so_try_find_addr_rx(
          module, "_ZN5sound3sys12MusicManager6m_hCueE"));
  sound_file_binder_get_instance =
      (void *)so_try_find_addr_rx(
          module, "_ZN3sys10FileBinder11GetInstanceEv");
  sound_file_binder_attach_sound_cpk =
      (void *)so_try_find_addr_rx(
          module, "_ZN3sys10FileBinder14AttachSoundCpkEv");
  sound_file_binder_is_ready =
      (void *)so_try_find_addr_rx(module,
                             "_ZN3sys10FileBinder7IsReadyEv");

  int commentary_hooks_ok = 1;
  const uintptr_t commentary_acb_root =
      (uintptr_t)module->load_base + 0x820f8b7;
  static const char expected_commentary_acb_root[] = "cpk_snd/xxx";
  static const char english_commentary_acb_root[] = "cpk_snd/eng";
  if (memcmp((const void *)commentary_acb_root,
             expected_commentary_acb_root,
             sizeof(expected_commentary_acb_root)) != 0) {
    debugPrintf("WARNING: unexpected commentary ACB root at %p, "
                "skipping commentary hooks\n",
                (void *)commentary_acb_root);
    commentary_hooks_ok = 0;
  } else {
    memcpy((void *)commentary_acb_root, english_commentary_acb_root,
           sizeof(english_commentary_acb_root));
  }

  const uintptr_t sound_language_plt =
      (uintptr_t)module->load_base + 0x38083d0;
  const uintptr_t sound_language_name_plt =
      (uintptr_t)module->load_base + 0x390fd50;
  const uintptr_t sound_language_string3_plt =
      (uintptr_t)module->load_base + 0x37e7050;
  const uintptr_t use_commentary_plt =
      (uintptr_t)module->load_base + 0x38f63e0;
  static const uint32_t expected_sound_language_plt[4] = {
      0xd002e5d0, 0xf9422211, 0x91110210, 0xd61f0220,
  };
  static const uint32_t expected_sound_language_name_plt[4] = {
      0xf002e1b0, 0xf9408211, 0x91040210, 0xd61f0220,
  };
  static const uint32_t expected_sound_language_string3_plt[4] = {
      0xd002e650, 0xf9454211, 0x912a0210, 0xd61f0220,
  };
  static const uint32_t expected_use_commentary_plt[4] = {
      0xf002e210, 0xf9422611, 0x91112210, 0xd61f0220,
  };
  if (!commentary_hooks_ok ||
      memcmp((const void *)sound_language_plt,
             expected_sound_language_plt,
             sizeof(expected_sound_language_plt)) != 0 ||
      memcmp((const void *)sound_language_name_plt,
             expected_sound_language_name_plt,
             sizeof(expected_sound_language_name_plt)) != 0 ||
      memcmp((const void *)sound_language_string3_plt,
             expected_sound_language_string3_plt,
             sizeof(expected_sound_language_string3_plt)) != 0 ||
      memcmp((const void *)use_commentary_plt,
             expected_use_commentary_plt,
             sizeof(expected_use_commentary_plt)) != 0) {
    debugPrintf("WARNING: commentary language PLT mismatch, "
                "skipping commentary hooks\n");
    commentary_hooks_ok = 0;
  } else {
    hook_arm64(sound_language_plt,
               (uintptr_t)&pes_sound_language_english);
    hook_arm64(sound_language_name_plt,
               (uintptr_t)&pes_sound_language_name_english);
    hook_arm64(sound_language_string3_plt,
               (uintptr_t)&pes_sound_language_string3_english);
    hook_arm64(use_commentary_plt,
               (uintptr_t)&pes_use_commentary_enabled);
    debugPrintf("UE4 hook: commentary root=cpk_snd/eng language=eng enabled=1 "
                "at %p/%p/%p/%p/%p\n",
                (void *)commentary_acb_root, (void *)sound_language_plt,
                (void *)sound_language_name_plt,
                (void *)sound_language_string3_plt,
                (void *)use_commentary_plt);
  }
#ifdef DEBUG_LOG
  sound_cinf_play_original =
      (void *)so_find_addr_rx(module,
                              "_ZN2KS8CInfBase4PlayERK13_ks_play_infoPy");
  sound_music_set_event_original =
      (void *)so_find_addr_rx(
          module, "_ZN5sound3sys12MusicManager10SetEventIdEi");
  sound_mount_data_original =
      (void *)so_find_addr_rx(
          module, "_ZN2KS8CInfBase9MountDataEPvjS1_PKcttPs");
  sound_file_is_exist_original =
      (void *)so_find_addr_rx(module, "_ZN3sys4File7IsExistEPKc");
  sound_set_game_option_volume_original =
      (void *)so_find_addr_rx(
          module,
          "_ZN5sound3sys9Interface19SetGameOptionVolumeENS1_13E_OPTVOL_TYPEEf");
  sound_set_category_volume_original =
      (void *)so_find_addr_rx(
          module, "_ZN2KS8CInfBase17SetCategoryVolumeEPKcf");
  sound_cri_bind_cpk_original =
      (void *)so_find_addr_rx(module, "criFsBinder_BindCpk");
  sound_get_category_volume =
      (void *)so_find_addr_rx(module,
                              "criAtomExCategory_GetVolumeByName");
  sound_get_category_total_volume =
      (void *)so_find_addr_rx(module,
                              "criAtomExCategory_GetTotalVolumeByName");
  const uintptr_t cinf_play_plt = (uintptr_t)module->load_base + 0x382c5c0;
  const uintptr_t music_set_event_plt =
      (uintptr_t)module->load_base + 0x38dac90;
  const uintptr_t mount_data_plt =
      (uintptr_t)module->load_base + 0x3890f90;
  const uintptr_t file_is_exist_plt =
      (uintptr_t)module->load_base + 0x390dc40;
  const uintptr_t set_game_option_volume_plt =
      (uintptr_t)module->load_base + 0x38c6dd0;
  const uintptr_t set_category_volume_plt =
      (uintptr_t)module->load_base + 0x37e3c10;
  const uintptr_t cri_bind_cpk_plt =
      (uintptr_t)module->load_base + 0x3860390;
  static const uint32_t expected_cinf_play_plt[4] = {
      0x9002e550, 0xf9429e11, 0x9114e210, 0xd61f0220,
  };
  static const uint32_t expected_music_set_event_plt[4] = {
      0xb002e290, 0xf9445211, 0x91228210, 0xd61f0220,
  };
  static const uint32_t expected_mount_data_plt[4] = {
      0xd002e3b0, 0xf9451211, 0x91288210, 0xd61f0220,
  };
  static const uint32_t expected_file_is_exist_plt[4] = {
      0x9002e1d0, 0xf9403e11, 0x9101e210, 0xd61f0220,
  };
  static const uint32_t expected_set_game_option_volume_plt[4] = {
      0xf002e2d0, 0xf944a211, 0x91250210, 0xd61f0220,
  };
  static const uint32_t expected_set_category_volume_plt[4] = {
      0xb002e670, 0xf9403211, 0x91018210, 0xd61f0220,
  };
  static const uint32_t expected_cri_bind_cpk_plt[4] = {
      0xd002e470, 0xf9421211, 0x91108210, 0xd61f0220,
  };
  if (memcmp((const void *)cinf_play_plt, expected_cinf_play_plt,
              sizeof(expected_cinf_play_plt)) != 0 ||
      memcmp((const void *)music_set_event_plt,
             expected_music_set_event_plt,
             sizeof(expected_music_set_event_plt)) != 0 ||
      memcmp((const void *)mount_data_plt, expected_mount_data_plt,
             sizeof(expected_mount_data_plt)) != 0 ||
      memcmp((const void *)file_is_exist_plt, expected_file_is_exist_plt,
             sizeof(expected_file_is_exist_plt)) != 0 ||
      memcmp((const void *)set_game_option_volume_plt,
             expected_set_game_option_volume_plt,
             sizeof(expected_set_game_option_volume_plt)) != 0 ||
      memcmp((const void *)set_category_volume_plt,
             expected_set_category_volume_plt,
             sizeof(expected_set_category_volume_plt)) != 0 ||
      memcmp((const void *)cri_bind_cpk_plt,
             expected_cri_bind_cpk_plt,
             sizeof(expected_cri_bind_cpk_plt)) != 0)
    fatal_error("Unexpected sound diagnostic PLT entries");
  hook_arm64(cinf_play_plt, (uintptr_t)&pes_sound_cinf_play_diagnostic);
  hook_arm64(music_set_event_plt,
             (uintptr_t)&pes_sound_music_set_event_diagnostic);
  hook_arm64(mount_data_plt,
             (uintptr_t)&pes_sound_mount_data_diagnostic);
  hook_arm64(file_is_exist_plt,
             (uintptr_t)&pes_sound_file_is_exist_diagnostic);
  hook_arm64(set_game_option_volume_plt,
             (uintptr_t)&pes_sound_set_game_option_volume_diagnostic);
  hook_arm64(set_category_volume_plt,
             (uintptr_t)&pes_sound_set_category_volume_diagnostic);
  hook_arm64(cri_bind_cpk_plt,
             (uintptr_t)&pes_sound_cri_bind_cpk_diagnostic);
  debugPrintf("UE4 hook: sound diagnostics Play=%p SetEventId=%p "
              "MountData=%p IsExist=%p OptionVolume=%p CategoryVolume=%p "
              "BindCpk=%p\n",
              (void *)cinf_play_plt, (void *)music_set_event_plt,
              (void *)mount_data_plt, (void *)file_is_exist_plt,
              (void *)set_game_option_volume_plt,
              (void *)set_category_volume_plt, (void *)cri_bind_cpk_plt);
#endif
  debugPrintf("UE4 hook: CRI AAudio loader=%p success-notify=nop "
              "(enable deferred to post-finalize)\n",
              (void *)aaudio_loader_open);
}

void ue4_hooks_post_finalize(so_module *module) {
  // Now that so_finalize has mapped the SO into executable code memory,
  // it is safe to call functions inside the SO through load_virtbase (RX)
  // addresses.  Calling through load_base (RW heap) would fault on real
  // Switch hardware because the heap is marked No-eXecute.
  const uintptr_t aaudio_enable_rx =
      so_find_addr_rx(module, "criNcv_EnableAAudio_ANDROID");
  debugPrintf("UE4 post-finalize: criNcv_EnableAAudio_ANDROID at %p\n",
              (void *)aaudio_enable_rx);
  ((void (*)(uint32_t))aaudio_enable_rx)(1);
  debugPrintf("UE4 post-finalize: AAudio enabled\n");
}

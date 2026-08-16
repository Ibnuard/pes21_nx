#include <stdint.h>
#include <string.h>
#include <switch.h>

#include "error.h"
#include "so_util.h"
#include "ue4_hooks.h"
#include "util.h"

#define OBJECT_INITIALIZER_STATE_SLOTS 32
#define OBJECT_INITIALIZER_MAX_ITEMS (1 << 20)

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
static uintptr_t ue4_tickrate_resume;
uintptr_t pes_virtual_pad_update_resume;
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
static void (*exhibition_matchplan_save_squad)(void);
static void (*exhibition_strategy_start_fade)(void *squad_edit);
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
static void (*exhibition_set_test_match_team_id)(uint32_t team_id);
static void (*exhibition_set_test_match_cpu_level)(uint32_t level);
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
static const void *(*exhibition_user_info_get_name)(void *user_info);
static void *(*exhibition_parameter_get_instance)(uint32_t create);
static void (*exhibition_parameter_myclub_create_work)(void *myclub);
static void *(*main_menu_dialog_create)(const void *name,
                                        const unsigned char *modal);
static void (*main_menu_dialog_set_text)(void *dialog, const void *text);
static void (*main_menu_dialog_set_button)(void *dialog, const void *text);
static void (*main_menu_choice_set_active)(void *choice, uint32_t active,
                                           uint32_t reaction,
                                           uint32_t flags);
static uintptr_t main_menu_selected_resume;
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
static _Alignas(4) uint32_t exhibition_requested;
static _Alignas(4) uint32_t exhibition_strategy_pending;
static _Alignas(4) uint32_t exhibition_strategy_auto_proceed;
static _Alignas(4) uint32_t exhibition_session_active;
static _Alignas(4) uint32_t exhibition_team_select_active;
static _Alignas(4) uint32_t exhibition_select_side;
static _Alignas(4) uint32_t exhibition_strategy_action;
static _Alignas(4) uint32_t exhibition_plan_ready;
static _Alignas(4) uint32_t exhibition_return_to_selector;
static _Alignas(4) uint32_t exhibition_searching_active;
static _Alignas(4) uint32_t exhibition_search_refresh_pending;
static _Alignas(4) uint32_t exhibition_search_initial_refresh_ticks;
static _Alignas(4) uint32_t exhibition_search_touch_pending;
static _Alignas(4) uint32_t exhibition_team_picker_open;
#define EXHIBITION_INITIAL_REFRESH_TICKS 180u
#define EXHIBITION_FALLBACK_HOME_TEAM 100u
#define EXHIBITION_FALLBACK_AWAY_TEAM 101u
static _Alignas(4) uint32_t exhibition_home_team_id;
static _Alignas(4) uint32_t exhibition_away_team_id;

enum {
  EXHIBITION_STRATEGY_NONE = 0,
  EXHIBITION_STRATEGY_EDIT = 1,
  EXHIBITION_STRATEGY_START = 2,
};

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
};

static const ExhibitionMasterRoster *exhibition_find_roster(
    uint32_t team_id) {
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
  return exhibition_find_roster(team_id) != NULL;
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

static const char *exhibition_team_name(uint32_t team_id) {
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
  // wrapper-owned literal. The Training matchup footer's stock HOME/AWAY
  // dialog is repurposed as the Exhibition game-plan editor.
  static const char exhibition_label[] __attribute__((aligned(2))) =
      "Exhibition";
  static const char training_label[] __attribute__((aligned(2))) =
      "Training";
  static const char training_description[] __attribute__((aligned(2))) =
      "Practice matches and controls";
  static const char game_plan_label[] __attribute__((aligned(2))) =
      "Game Plan";
  static const char change_team_label[] __attribute__((aligned(2))) =
      "Tap to Change Team";
  static const char proceed_label[] __attribute__((aligned(2))) = "Proceed";
  if (string_id == 0x0460005d)
    return (uintptr_t)exhibition_label | 1u;
  if (string_id == 0x0460005e)
    return (uintptr_t)training_label | 1u;
  if (string_id == 0x045d01d4)
    return (uintptr_t)training_description | 1u;
  if (string_id == 0x01f9003d &&
      __atomic_load_n(&exhibition_session_active, __ATOMIC_ACQUIRE))
    return (uintptr_t)game_plan_label | 1u;
  if (string_id == 0x045e0023 &&
      __atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE))
    return (uintptr_t)change_team_label | 1u;
  if (string_id == 0x7fff0001 &&
      __atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE))
    return (uintptr_t)proceed_label | 1u;
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
      __atomic_store_n(&exhibition_strategy_auto_proceed, 0,
                       __ATOMIC_RELEASE);
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
      __atomic_store_n(&exhibition_strategy_auto_proceed, 0,
                       __ATOMIC_RELEASE);
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
        __atomic_store_n(&exhibition_home_team_id, 0, __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_away_team_id, 0, __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_select_side, 0, __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_strategy_action,
                         EXHIBITION_STRATEGY_NONE, __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_plan_ready, 0, __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_return_to_selector, 0,
                         __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_searching_active, 1,
                         __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_search_refresh_pending, 1,
                         __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_search_initial_refresh_ticks,
                         EXHIBITION_INITIAL_REFRESH_TICKS, __ATOMIC_RELEASE);
        __atomic_store_n(&exhibition_team_select_active, 1,
                         __ATOMIC_RELEASE);
        if (exhibition_status_get_instance && exhibition_status_set_game_mode)
          exhibition_status_set_game_mode(exhibition_status_get_instance(),
                                          72);
        exhibition_prepare_search_parameters();
        exhibition_refresh_selected_tmpdb();
        exhibition_flow_direct_set((unsigned char *)listener + 0x118,
                                   searching_flow);
        *state = 9;
        __atomic_store_n(&exhibition_requested, 0, __ATOMIC_RELEASE);
        debugPrintf("exhibition: TutorialMatch initialized master teams; "
                    "DirectSet -> %s\n",
                    searching_flow);
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

static void exhibition_open_team_picker(void *window, uint32_t side) {
  if (!window || side >= 2 ||
      !__atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE) ||
      !exhibition_team_select_create_child || !exhibition_task_add_unit ||
      !exhibition_setup_usable_teams || !exhibition_team_select_set_usable)
    return;

  if (__atomic_exchange_n(&exhibition_team_picker_open, 1,
                          __ATOMIC_ACQ_REL))
    return;

  const uint32_t selected_team =
      side == 0
          ? __atomic_load_n(&exhibition_home_team_id, __ATOMIC_ACQUIRE)
          : __atomic_load_n(&exhibition_away_team_id, __ATOMIC_ACQUIRE);
  const uint32_t team_id = exhibition_picker_seed_team(selected_team);
  __atomic_store_n(&exhibition_select_side, side, __ATOMIC_RELEASE);
  if (exhibition_set_test_match_team_id)
    exhibition_set_test_match_team_id(team_id);

  unsigned char child_name[24] = {0};
  static const char menu_team_select[] = "menuTeamSelect";
  child_name[0] = (unsigned char)((sizeof(menu_team_select) - 1) << 1);
  memcpy(child_name + 1, menu_team_select, sizeof(menu_team_select) - 1);
  void *child = exhibition_team_select_create_child(
      child_name, 0, window, team_id, 0, 0, 0);
  if (!child) {
    __atomic_store_n(&exhibition_team_picker_open, 0, __ATOMIC_RELEASE);
    return;
  }
  exhibition_task_add_unit(window, child);
  exhibition_setup_usable_teams();
  exhibition_team_select_set_usable(child, 1);
  debugPrintf("exhibition: Matchmaking Change Team side=%u current=%u "
              "seed=%u child=%p\n",
              side, selected_team, team_id, child);
}

void pes_exhibition_search_touch(void *window, const void *touch_info) {
  if (!window || !touch_info ||
      !__atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE)) {
    if (exhibition_search_touch_original)
      exhibition_search_touch_original(window, touch_info);
    return;
  }

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

  static const char team_select_name[] = "menuTeamSelect";
  static const char cpu_level_name[] = "popupSelectCpuLevel";
  if (length == sizeof(team_select_name) - 1 &&
      memcmp(name, team_select_name, sizeof(team_select_name) - 1) == 0) {
    __atomic_store_n(&exhibition_team_picker_open, 0, __ATOMIC_RELEASE);
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
      memcmp(name, cpu_level_name, sizeof(cpu_level_name) - 1) == 0 &&
      exhibition_set_test_match_cpu_level) {
    exhibition_set_test_match_cpu_level(selected_value);
    debugPrintf("exhibition: COM level=%u\n", selected_value);
  }
}

void pes_exhibition_search_footer(void *window, uint32_t footer_key) {
  if (!__atomic_load_n(&exhibition_searching_active, __ATOMIC_ACQUIRE)) {
    if (exhibition_search_footer_original)
      exhibition_search_footer_original(window, footer_key);
    return;
  }

  if ((footer_key == 0 || footer_key == 3) &&
      !exhibition_matchup_ready()) {
    debugPrintf("exhibition: ignored footer key=%u until both teams are "
                "selected\n",
                footer_key);
    return;
  }

  if (footer_key == 2) {
    if (exhibition_training_footer_original)
      exhibition_training_footer_original(window, footer_key);
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
    __atomic_store_n(&exhibition_searching_active, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_team_select_active, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_session_active, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_strategy_auto_proceed, 0,
                     __ATOMIC_RELEASE);
    exhibition_flow_direct_set((unsigned char *)listener + 0x118,
                               main_menu_flow);
    debugPrintf("exhibition: Matchmaking Back -> %s\n", main_menu_flow);
    return;
  }

  if (footer_key == 0 || footer_key == 3) {
    const uint32_t action = footer_key == 3 ? EXHIBITION_STRATEGY_EDIT
                                            : EXHIBITION_STRATEGY_START;
    __atomic_store_n(&exhibition_strategy_auto_proceed, 0,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_strategy_action, action, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_strategy_pending, 1, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_searching_active, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_team_select_active, 0, __ATOMIC_RELEASE);
    exhibition_flow_direct_set((unsigned char *)listener + 0x118,
                               strategy_flow);
    debugPrintf("exhibition: Matchmaking footer key=%u -> Strategy action=%u\n",
                footer_key, action);
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

static void main_menu_make_string_view(unsigned char object[24],
                                       const char *text) {
  const size_t length = text ? strlen(text) : 0;
  if (length <= 23) {
    exhibition_make_short_string(object, text);
    return;
  }

  // Cobra uses libc++'s 24-byte string layout. A long read-only view is safe
  // here because the dialog setters synchronously copy the supplied text.
  const uint64_t long_marker = 1;
  memset(object, 0, 24);
  memcpy(object, &long_marker, sizeof(long_marker));
  memcpy(object + 8, &length, sizeof(length));
  memcpy(object + 16, &text, sizeof(text));
}

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

  const char *description_nodes[] = {"textSmall_item", "textLarge_sub"};
  for (uint32_t i = 0; i < 2; i++) {
    void *node = exhibition_find_root_node(tile, description_nodes[i]);
    if (!node)
      continue;
    exhibition_make_short_string(text, description);
    exhibition_text_set_string(node, text);
  }
}

void pes_main_menu_simplify(void *window) {
  static int logged;
  if (!window || !exhibition_window_get_window ||
      !exhibition_node_set_visible)
    return;

  void *root = exhibition_window_get_window(window);
  if (!root)
    return;

  // Keep the stock 2x2 Match grid and relabel all four choices. Exhibition and
  // Training retain their proven handlers; the other two open local windows.
  void *tab_strip = exhibition_find_root_node(root, "p_tab");
  void *match_page = exhibition_find_root_node(root, "page_0");
  if (tab_strip)
    exhibition_node_set_visible(tab_strip, 0, 2);
  if (match_page) {
    void *tiles[4] = {0};
    for (uint32_t i = 0; i < 4; i++) {
      char choice_name[] = "choice_0";
      choice_name[7] = (char)('0' + i);
      tiles[i] = exhibition_find_root_node(match_page, choice_name);
      if (tiles[i]) {
        exhibition_node_set_visible(tiles[i], 1, 2);
        if (main_menu_choice_set_active)
          main_menu_choice_set_active(tiles[i], 1, 1, 2);
      }
    }
    main_menu_set_tile_text(tiles[0], "Exhibition", "Local match");
    main_menu_set_tile_text(tiles[1], "Credits", "Credits and support");
    main_menu_set_tile_text(tiles[2], "Training", "Practice controls");
    main_menu_set_tile_text(tiles[3], "Version Info", "Build and game version");
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
  if (choice != 1 && choice != 3)
    return main_menu_selected_resume;

  if (!main_menu_dialog_create || !main_menu_dialog_set_text ||
      !main_menu_dialog_set_button || !exhibition_task_add_unit)
    return main_menu_selected_resume;

  static const char credits_body[] =
      "Credits\n\n"
      "Port & Mod by Ibnuard";
  static const char version_body[] =
      "Build & Game Version\n\n"
      "NRO: PES 2021 NX v0.1.96\n"
      "Game: PES 2021 Mobile v5.3.0\n\n"
      "Latest changes:\n"
      "- Direct Start > Menu flow\n"
      "- 38 Exhibition clubs\n"
      "- Credits and version popups\n"
      "- Hidden unused header icons";
  const char *body = choice == 1 ? credits_body : version_body;

  unsigned char dialog_name[24];
  unsigned char dialog_body[24];
  unsigned char dialog_button[24];
  unsigned char modal = 0;
  exhibition_make_short_string(
      dialog_name, choice == 1 ? "popupCredits" : "popupVersionInfo");
  main_menu_make_string_view(dialog_body, body);
  exhibition_make_short_string(dialog_button, "OK");
  void *dialog = main_menu_dialog_create(dialog_name, &modal);
  if (!dialog)
    return main_menu_selected_resume;

  main_menu_dialog_set_text(dialog, dialog_body);
  main_menu_dialog_set_button(dialog, dialog_button);
  exhibition_task_add_unit(window, dialog);
  debugPrintf("UE4 menu: choice=%u opened info dialog=%p\n", choice, dialog);
  return 0;
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
            window, key,
            (key == 0 || key == 3) ? matchup_ready : 1);
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
        debugPrintf("exhibition: reusing edited match plan for start\n");
      }

      if (action == EXHIBITION_STRATEGY_START &&
          __atomic_load_n(&exhibition_plan_ready, __ATOMIC_ACQUIRE)) {
        __atomic_store_n(&exhibition_strategy_auto_proceed, 1,
                         __ATOMIC_RELEASE);
        debugPrintf("exhibition: match plan ready; waiting for stock Strategy "
                    "state 1 before auto Proceed\n");
      }
    }
  }
  return exhibition_strategy_main_resume;
}

// Intercept the exact state-0 exit after MyClubSquadEdit::CreateObject. For a
// direct Exhibition Proceed, reproduce the stock ready path before the new
// Strategy child can render a full frame: register it, save the loaded squad,
// start its native proceed fade, and advance the parent to state 3. The next
// stock Main tick performs stadium/player setup and emits the normal proceed
// event. Game Plan entries continue through the original state-1 UI unchanged.
uintptr_t pes_exhibition_strategy_created_entry(void *strategy_flow,
                                                void *squad_edit) {
  uint32_t state = squad_edit ? 1u : 2u;
  if (strategy_flow && squad_edit && exhibition_task_add_unit)
    exhibition_task_add_unit(strategy_flow, squad_edit);
  if (strategy_flow)
    memcpy((unsigned char *)strategy_flow + 540, &state, sizeof(state));

  if (strategy_flow && squad_edit &&
      __atomic_exchange_n(&exhibition_strategy_auto_proceed, 0,
                          __ATOMIC_ACQ_REL)) {
    if (exhibition_matchplan_save_squad)
      exhibition_matchplan_save_squad();
    if (exhibition_strategy_start_fade)
      exhibition_strategy_start_fade(squad_edit);
    state = 3;
    memcpy((unsigned char *)strategy_flow + 540, &state, sizeof(state));
    __atomic_store_n(&exhibition_strategy_action,
                     EXHIBITION_STRATEGY_NONE, __ATOMIC_RELEASE);
    __atomic_store_n(&exhibition_session_active, 0, __ATOMIC_RELEASE);
    debugPrintf("exhibition: Strategy created and faded in same tick; "
                "stock state=%u squad=%p\n",
                state, squad_edit);
  }
  return exhibition_strategy_created_resume;
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
  const uint64_t packed = (uint64_t)(buttons & 0x0000ffffu) |
                          ((uint64_t)(uint16_t)x << 32) |
                          ((uint64_t)(uint16_t)y << 48);
  __atomic_store_n(&cobra_pad_input, packed, __ATOMIC_RELEASE);
  __atomic_store_n(&cobra_pad_connected, connected != 0, __ATOMIC_RELEASE);
}

static int cobra_controller_is_connected(void) {
  return __atomic_load_n(&cobra_pad_connected, __ATOMIC_ACQUIRE) != 0;
}

uint32_t pes_mobile_control_context(int *mode) {
  const uint32_t generation =
      __atomic_load_n(&mobile_control_generation, __ATOMIC_ACQUIRE);
  if (mode)
    *mode = (int)__atomic_load_n(&mobile_control_mode, __ATOMIC_ACQUIRE);
  return generation;
}

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

// Entry hook for ScreenTapManager::Update. ControlModeInfo is the original x2
// argument here, so its methods provide authoritative offense/defense context
// even while every ButtonObject is idle.
uintptr_t pes_mobile_screen_tap_entry(void *control_mode_ptr) {
  int mode = PES_MOBILE_CONTROL_UNKNOWN;
  if (control_mode_ptr && mobile_is_mode_defense &&
      mobile_is_mode_defense(control_mode_ptr))
    mode = PES_MOBILE_CONTROL_DEFENSE;
  else if (control_mode_ptr && mobile_is_mode_offense &&
           mobile_is_mode_offense(control_mode_ptr))
    mode = PES_MOBILE_CONTROL_OFFENSE;
  __atomic_store_n(&mobile_control_mode, (uint32_t)mode, __ATOMIC_RELEASE);
  __atomic_store_n(&mobile_control_seen_tick, armGetSystemTick(),
                   __ATOMIC_RELEASE);
  const uint32_t generation =
      __atomic_add_fetch(&mobile_control_generation, 1, __ATOMIC_RELEASE);
  static int previous_mode = -1;
  if (mode != previous_mode && mobile_context_log_count < 24) {
    mobile_context_log_count++;
    debugPrintf("input: ScreenTapManager entry control=%p mode=%d "
                "generation=%u\n",
                control_mode_ptr, mode, generation);
    previous_mode = mode;
  }
  return mobile_screen_tap_entry_resume;
}

// The Android/mobile match initializer calls SetPadNo(1), which this binary
// deliberately collapses to -1. Command::ExecCommand then skips the complete
// real-pad path for that cursor. When Switch HID is present, attach that primary
// cursor to port 0; preserve the game's original behavior for every other call.
static void pes_cursor_set_pad_no(void *cursor_ptr, uint32_t requested) {
  if (!cursor_ptr)
    return;
  const int connected = cobra_controller_is_connected();
  const int32_t pad_no = connected && requested == 1 ? 0
                                                     : (requested ? -1 : 0);
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
      (requested_enable != 0 || (connected && pad_no == 0)) ? 1 : 0;
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
    const uint32_t buttons = (uint32_t)packed;
    const int32_t x = (int16_t)(packed >> 32);
    const int32_t y = (int16_t)(packed >> 48);
    int32_t pad_id;
    uint32_t previous;
    uint32_t current;
    memcpy(&pad_id, pad + 4, sizeof(pad_id));
    memcpy(&previous, pad + 12, sizeof(previous));
    memcpy(&current, pad + 16, sizeof(current));
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
      virtual_pad_set_color(clip, 1.0f, 1.0f, 1.0f, 0.02f);
      tinted_clips[index] = clip;
    }
  }
}

static void patch_arm64_branch(uintptr_t source, uintptr_t destination) {
  const intptr_t delta = (intptr_t)destination - (intptr_t)source;
  if ((delta & 3) != 0 || delta < -(1LL << 27) || delta >= (1LL << 27))
    fatal_error("UE4 branch hook is out of range: %p -> %p", (void *)source,
                (void *)destination);
  *(uint32_t *)source =
      0x14000000u | ((uint32_t)(delta >> 2) & 0x03ffffffu);
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

void install_ue4_hooks(so_module *module) {
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
  exhibition_matchplan_save_squad =
      (void *)so_find_addr_rx(module,
          "_ZN9matchPlan16SquadEditUtility28SaveSquadDataToMatchPlanDataEv");
  exhibition_strategy_start_fade =
      (void *)so_find_addr_rx(module,
          "_ZN4menu15MyClubSquadEdit16StartFadeProceedEv");
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
  debugPrintf("UE4 hook: Exhibition Strategy seed backing=%p runtime=%p "
              "hook=%p resume=%p childSite=%p childHook=%p childResume=%p "
              "get=%p setupTeam=%p setupTmpdb=%p setTeam=%p update=%p\n",
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
              exhibition_matchplan_update_tmpdb);
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
  debugPrintf("UE4 hook: Exhibition uniforms check=%p getUni=%p "
              "saveSquad=%p startFade=%p\n",
              exhibition_check_uniform, exhibition_match_get_uni_id,
              exhibition_matchplan_save_squad,
              exhibition_strategy_start_fade);

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
  patch_checked_u32(header_four_visible + 0x8,
                    0x2a0103f3, // mov w19, w1
                    0x2a1f03f3, // mov w19, wzr
                    "MyClub header four-button visibility");
  main_menu_selected_resume = main_selected_runtime + 0x10;
  hook_arm64(main_selected, (uintptr_t)&pes_main_menu_selected_hook);
  hook_arm64(main_setup + 0x11c,
             (uintptr_t)&pes_main_menu_simplify_hook);
  debugPrintf("UE4 menu: installed direct compact menu setup=%p tail=%p "
              "swipe=%p init=%p selected=%p header=%p\n",
              (void *)main_setup_runtime,
              (void *)(main_setup_runtime + 0x11c),
              (void *)so_find_addr_rx(module, main_swipe_symbol),
              (void *)so_find_addr_rx(
                  module, "_ZN4menu10MyClubMain10InitMobileEv"),
              (void *)main_selected_runtime,
              (void *)so_find_addr_rx(
                  module,
                  "_ZN4menu12HeaderWindow26setDefautFourButtonVisibleEb"));
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
  main_menu_dialog_create =
      (void *)so_find_addr_rx(module,
          "_ZN10menusystem13DialogConfirm12CreateObjectERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS2_9AllocatorIcEEEERKb");
  main_menu_dialog_set_text =
      (void *)so_find_addr_rx(module,
          "_ZN10menusystem10DialogBase7SetTextERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS2_9AllocatorIcEEEE");
  main_menu_dialog_set_button =
      (void *)so_find_addr_rx(module,
          "_ZN10menusystem13DialogConfirm13SetButtonTextERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS2_9AllocatorIcEEEE");
  main_menu_choice_set_active =
      (void *)so_find_addr_rx(module,
          "_ZN10menusystem4Node9SetActiveEbbj");
  exhibition_setup_usable_teams =
      (void *)so_find_addr_rx(module,
          "_ZN10onlinemode13UtilityMyClub20SetupUseableTeamListEv");
  exhibition_team_select_set_usable =
      (void *)so_find_addr_rx(module,
          "_ZN4menu20MyClubFlowTeamSelect17SetUsableteamListEb");
  exhibition_set_test_match_cpu_level =
      (void *)so_find_addr_rx(module,
          "_ZN10onlinemode9DebugMode20SetTestMatchCpuLevelE8CpuLevel");
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

  // OpenSL ES is unavailable on Horizon. Route CRI's Android backend to its
  // built-in pseudo voice backend so audio is silent instead of dereferencing
  // the intentionally unsupported slCreateEngine result.
  const uintptr_t sles_register =
      so_find_addr(module, "criNcvAndroidSLES_RegisterInterface");
  const uintptr_t pseudo_register =
      so_find_addr(module, "criNcvPseudo_RegisterInterface");
  patch_arm64_branch(sles_register, pseudo_register);
  debugPrintf("UE4 hook: CRI Android SLES -> pseudo voice (%p -> %p)\n",
              (void *)sles_register, (void *)pseudo_register);
}

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

typedef struct {
  const uint32_t *player_unique_ids;
  const uint8_t *shirt_numbers;
  uint32_t player_count;
} ExhibitionMasterRoster;

// PlayerAssignment.raw is the authoritative base-club membership table. The
// mobile build loads Team.raw and Player.raw, but its old myClub-only startup
// path leaves the Team records' runtime member arrays empty. Keep only the two
// fixed MVP clubs here; every PlayerId is resolved back through CommonWork so
// the match uses the game's real master player records and abilities.
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

// cobra::stl::basic_string uses a one-byte short-string tag or the usual
// [capacity, size, data] long representation. Menu flow names longer than 23
// bytes use the latter. Redirect only the stock eFootball/Divisions target;
// every other flow and all startup/network state remain untouched.
uintptr_t pes_exhibition_redirect_flow(void *flow_name_ptr) {
  static const char online_target[] = "MyClub/MainMenu/MenuOnlineMatchTop";
  static const char divisions_target[] = "MyClub/MainMenu/MenuDivisionsTop";
  static const char replacement[] = "MyClub/TutorialMatch";
  unsigned char *object = flow_name_ptr;
  char *data = NULL;
  size_t length = 0;

  if (object) {
    if (object[0] & 1) {
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
  if (data && (object[0] & 1)) {
    if (length == sizeof(online_target) - 1 &&
        memcmp(data, online_target, sizeof(online_target) - 1) == 0)
      matched_target = online_target;
    else if (length == sizeof(divisions_target) - 1 &&
             memcmp(data, divisions_target,
                    sizeof(divisions_target) - 1) == 0)
      matched_target = divisions_target;
  }
  if (matched_target) {
    const size_t replacement_length = sizeof(replacement) - 1;
    memcpy(data, replacement, sizeof(replacement));
    memcpy(object + 8, &replacement_length, sizeof(replacement_length));
    __atomic_store_n(&exhibition_requested, 1, __ATOMIC_RELEASE);
    debugPrintf("exhibition: redirected %s -> %s\n", matched_target,
                replacement);
  }

  return exhibition_flow_create_resume;
}

// TutorialMatch is also visited by the normal startup flow. Leave that visit
// completely stock. A Divisions/eFootball redirect arms a one-shot request;
// only then change state 0 to the complete local-team initializer (state 3).
// Once the stock graphics/font wait has selected its normal post-tutorial
// route (state 7), schedule the built-in Team Strategy flow directly. State 9
// is outside TutorialMatch's 0..8 dispatcher, so the original Main returns
// without also emitting its stock proceed event while FlowTransition owns the
// fade. This keeps the master-data teams produced by state 3 and avoids the
// invalid myClub squad converter entirely.
uintptr_t pes_exhibition_tutorial_main_entry(void *tutorial_flow) {
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
        static const char strategy_flow[] = "MyClub/Match/MenuMatchMenu";
        __atomic_store_n(&exhibition_strategy_pending, 1, __ATOMIC_RELEASE);
        exhibition_flow_direct_set((unsigned char *)listener + 0x118,
                                   strategy_flow);
        *state = 9;
        __atomic_store_n(&exhibition_requested, 0, __ATOMIC_RELEASE);
        debugPrintf("exhibition: TutorialMatch initialized master teams; "
                    "DirectSet -> %s\n",
                    strategy_flow);
      } else {
        debugPrintf("exhibition: waiting for FlowListener instance=%p "
                    "DirectSet=%p\n",
                    listener, exhibition_flow_direct_set);
      }
    }
  }
  return exhibition_tutorial_main_resume;
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
      void *data = exhibition_matchplan_get_instance
                       ? exhibition_matchplan_get_instance()
                       : NULL;
      if (data && exhibition_set_team &&
          exhibition_matchplan_setup_tmpdb) {
        static const uint32_t barcelona_team_id = 108u << 14;
        static const uint32_t madrid_team_id = 109u << 14;
        static const ExhibitionMasterRoster barcelona_roster = {
            exhibition_barcelona_players, exhibition_barcelona_shirts,
            sizeof(exhibition_barcelona_players) /
                sizeof(exhibition_barcelona_players[0]),
        };
        static const ExhibitionMasterRoster madrid_roster = {
            exhibition_madrid_players, exhibition_madrid_shirts,
            sizeof(exhibition_madrid_players) /
                sizeof(exhibition_madrid_players[0]),
        };
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
            common_work, &barcelona_team_id, &barcelona_roster);
        const uint32_t away_count = exhibition_install_master_roster(
            common_work, &madrid_team_id, &madrid_roster);

        // TutorialMatch called SetExhibitionTeam before the mobile master
        // Team records had member arrays, so tmpdb::Match still contains two
        // empty squads. Re-run the same stock importer now that the authentic
        // PlayerAssignment rosters are installed. Then rebuild matchPlan from
        // tmpdb exactly as MyClubFlowMatchMenu's constructor normally does.
        // This populates the badge, coach, formation and tmpdb Player objects
        // consumed by MyClubSquadEdit, not merely matchPlan's local team copy.
        exhibition_set_team(&barcelona_team_id, 0, 0);
        exhibition_set_team(&madrid_team_id, 1, 0);

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
        debugPrintf("exhibition: Strategy seeded matchPlan=%p "
                    "teams=108v109 players=%uv%u old_mode=%u plan="
                    "0x%x/%u/%u/%p vs 0x%x/%u/%u/%p via refreshed "
                    "tmpdb::Match\n",
                    data, home_count, away_count, data_mode,
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
    }
  }
  return exhibition_strategy_main_resume;
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
  // The offline bundle already seeds a complete UserInfoData identity and a
  // complete MyClub entry.  Even with UtilityCommon::IsNewUser() returning
  // false, ModeEntry can receive a stale season-update action list and route
  // state 5 through SubMainInputUserInfo (the User Profile screen), followed
  // by the old coach/squad onboarding.  Ignore only that pending-list branch.
  // The existing state-6 code still validates the seeded squad and falls back
  // to the game's normal CreateSquad path when it is actually empty, so login
  // and ParameterMyClub initialization are not bypassed.
  const char *mode_entry_symbol =
      "_ZN4menu19MyClubFlowModeEntry4MainEv";
  const uintptr_t mode_entry_main =
      so_find_addr(module, mode_entry_symbol);
  patch_checked_u32(mode_entry_main + 0x248,
                    0x540002a1, // b.ne state 9 (SubMainInputUserInfo)
                    0xd503201f, // nop; continue to state 6 squad validation
                    "MyClub ModeEntry seeded-profile gate");
  debugPrintf("UE4 patch: seeded MyClub profile skips legacy onboarding "
              "backing=%p\n",
              (void *)(mode_entry_main + 0x248));

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
  debugPrintf("UE4 hook: Exhibition Strategy seed backing=%p runtime=%p "
              "hook=%p resume=%p get=%p setupTeam=%p setupTmpdb=%p "
              "setTeam=%p update=%p\n",
              (void *)strategy_main, (void *)strategy_main_runtime,
              pes_exhibition_strategy_main_hook,
              (void *)exhibition_strategy_main_resume,
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
  // TutorialMatch is then made deterministic: it builds Barcelona and Madrid
  // directly from the game's master database, bypasses stale tutorial flags,
  // and enters the ordinary offline match mode.
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

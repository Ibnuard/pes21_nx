// Two-controller native-input experiment. No touch synthesis and no global
// gameplay patches: only tile 2, HOME on pad zero and AWAY on pad one.
static void (*native_lab_list_update_original)(void *, const void *, uint32_t, uint32_t);
static void (*native_lab_sample_original)(void *, uint32_t, const void *, const void *);
static void *(*native_lab_history_get)(void *, int);
static uint32_t native_lab_status;
static uint32_t native_lab_installed;
static uint32_t native_lab_action_hooks_installed;
static uint32_t native_lab_debug_context;
static uint32_t native_lab_debug_stock_mask;
static uint32_t native_lab_debug_route_mask;
static uint32_t native_lab_debug_buttons;
static uint32_t native_lab_debug_native_keys;
static uint32_t native_lab_debug_native_power_milli;
static uint32_t native_lab_debug_native_right_power_milli;
static uint32_t native_lab_debug_last_event;
static uint32_t native_lab_debug_last_command;
static int32_t native_lab_debug_axis_x;
static int32_t native_lab_debug_axis_y;
static int32_t native_lab_debug_right_axis_x;
static int32_t native_lab_debug_right_axis_y;
static uint32_t native_lab_debug_connected;
static uint32_t native_lab_debug_connected_mask;
static uint32_t native_lab_debug_native_sample_mask;
static uint32_t native_lab_debug_owner_mask;
static uint32_t native_lab_debug_route_player_mask;
static uint32_t native_lab_debug_cursor_slots;
static uint32_t native_lab_debug_input_unit_mask;
static uint32_t native_lab_debug_accessor_bind_mask;
static uint32_t native_lab_debug_prime_mask;
static uintptr_t native_lab_input_units[2];
static uint32_t native_lab_debug_setplay_pad;
static uint32_t native_lab_debug_buttons_p2;
static uint32_t native_lab_debug_native_keys_p2;
static uint32_t native_lab_debug_native_power_milli_p2;
static uint32_t native_lab_debug_native_right_power_milli_p2;
static uint32_t native_lab_debug_last_event_p2;
static uint32_t native_lab_debug_last_command_p2;
static int32_t native_lab_debug_axis_x_p2;
static int32_t native_lab_debug_axis_y_p2;
static int32_t native_lab_debug_right_axis_x_p2;
static int32_t native_lab_debug_right_axis_y_p2;

typedef struct {
  uint32_t kind;
  const char *symbol;
  uintptr_t vptr;
} NativeLabUnit;

// Kinds verified against ThinkUnitList's object table, not guessed from names.
static NativeLabUnit native_lab_units[] = {
  {0, "_ZTVN5match3pad18ThinkUnitShortPassE", 0},
  {1, "_ZTVN5match3pad17ThinkUnitLongPassE", 0},
  {2, "_ZTVN5match3pad20ThinkUnitThroughPassE", 0},
  {3, "_ZTVN5match3pad14ThinkUnitShootE", 0},
  {5, "_ZTVN5match3pad14ThinkUnitPressE", 0},
  {6, "_ZTVN5match3pad15ThinkUnitTackleE", 0},
  {7, "_ZTVN5match3pad16ThinkUnitSlidingE", 0},
  {9, "_ZTVN5match3pad20ThinkUnitFriendPressE", 0},
  {10, "_ZTVN5match3pad16ThinkUnitDribbleE", 0},
  {11, "_ZTVN5match3pad17ThinkUnitFreeMoveE", 0},
  {12, "_ZTVN5match3pad21ThinkUnitCursorChangeE", 0},
  {24, "_ZTVN5match3pad20ThinkUnitSuperCancelE", 0},
  {26, "_ZTVN5match3pad21ThinkUnitSetplayGuideE", 0},
  {64, "_ZTVN5match3pad28ThinkUnitGoalkickPassSupportE", 0},
  {65, "_ZTVN5match3pad20ThinkUnitShortCornerE", 0},
  {70, "_ZTVN5match3pad26ThinkUnitCornerKickTacticsE", 0},
  {72, "_ZTVN5match3pad24ThinkUnitFreeKickTacticsE", 0},
  {75, "_ZTVN5match3pad31ThinkUnitFreeKickPositionChangeE", 0},
  {78, "_ZTVN5match3pad20ThinkUnitMobileShootE", 0},
  {79, "_ZTVN5match3pad19ThinkUnitMobilePassE", 0},
  {80, "_ZTVN5match3pad22ThinkUnitMobilePassSubE", 0},
  {81, "_ZTVN5match3pad26ThinkUnitMobileSuperCancelE", 0},
  {82, "_ZTVN5match3pad31ThinkUnitMobileAutoOneTwoReturnE", 0},
  {83, "_ZTVN5match3pad22ThinkUnitMobileDribbleE", 0},
  {84, "_ZTVN5match3pad27ThinkUnitMobileCursorChangeE", 0},
  {85, "_ZTVN5match3pad20ThinkUnitMobilePressE", 0},
  {86, "_ZTVN5match3pad23ThinkUnitMobilePressSubE", 0},
  {87, "_ZTVN5match3pad23ThinkUnitMobilePressSubE", 0},
  {88, "_ZTVN5match3pad22ThinkUnitMobileSlidingE", 0},
  {89, "_ZTVN5match3pad23ThinkUnitMobileFreeMoveE", 0},
  {90, "_ZTVN5match3pad26ThinkUnitMobileSetplayKickE", 0},
  {95, "_ZTVN5match3pad34ThinkUnitMobileSetplayCameraChangeE", 0},
};

static void native_pad_lab_reset(void) {
  __atomic_store_n(&native_lab_status, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_context, PES_SETPLAY_NONE,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_stock_mask, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_route_mask, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_buttons, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_native_keys, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_native_power_milli, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_native_right_power_milli, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_last_event, PES_NATIVE_LAB_EVENT_NONE,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_last_command, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_axis_x, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_axis_y, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_right_axis_x, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_right_axis_y, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_connected, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_connected_mask, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_native_sample_mask, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_owner_mask, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_route_player_mask, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_cursor_slots, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_input_unit_mask, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_accessor_bind_mask, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_prime_mask, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_input_units[0], 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_input_units[1], 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_setplay_pad, UINT32_MAX,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_buttons_p2, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_native_keys_p2, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_native_power_milli_p2, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_native_right_power_milli_p2, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_last_event_p2,
                   PES_NATIVE_LAB_EVENT_NONE, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_last_command_p2, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_axis_x_p2, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_axis_y_p2, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_right_axis_x_p2, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_right_axis_y_p2, 0,
                   __ATOMIC_RELEASE);
}

uint32_t pes_controller_native_pad_lab_status(void) {
  if (!pes_controller_native_pad_lab_active())
    return 0;
  // Latch milestones for one lab session; no per-frame file I/O/log spam.
  if (__atomic_load_n(&cobra_pad_connected, __ATOMIC_ACQUIRE) &&
      __atomic_load_n(&cobra_pad_input, __ATOMIC_ACQUIRE))
    __atomic_fetch_or(&native_lab_status, 1u, __ATOMIC_RELAXED);
  if (pes_controller_native_pad_lab_two_player() &&
      __atomic_load_n(&cobra_pad_connected_p2, __ATOMIC_ACQUIRE) &&
      __atomic_load_n(&cobra_pad_input_p2, __ATOMIC_ACQUIRE))
    __atomic_fetch_or(&native_lab_status, 1u, __ATOMIC_RELAXED);
  return __atomic_load_n(&native_lab_status, __ATOMIC_ACQUIRE) |
         (native_lab_installed && native_lab_action_hooks_installed
              ? 16u
              : 128u);
}

void pes_controller_native_pad_lab_debug_input(uint32_t port,
                                               uint32_t buttons,
                                               int32_t axis_x,
                                               int32_t axis_y,
                                               int32_t right_axis_x,
                                               int32_t right_axis_y,
                                               int connected) {
  if (!pes_controller_native_pad_lab_active() || port > 1)
    return;
  if (connected)
    __atomic_fetch_or(&native_lab_debug_connected_mask, 1u << port,
                      __ATOMIC_RELAXED);
  else
    __atomic_fetch_and(&native_lab_debug_connected_mask, ~(1u << port),
                       __ATOMIC_RELAXED);
  if (port == 1) {
    __atomic_store_n(&native_lab_debug_buttons_p2, buttons,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_debug_axis_x_p2,
                     connected ? axis_x : 0, __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_debug_axis_y_p2,
                     connected ? axis_y : 0, __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_debug_right_axis_x_p2,
                     connected ? right_axis_x : 0, __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_debug_right_axis_y_p2,
                     connected ? right_axis_y : 0, __ATOMIC_RELEASE);
    return;
  }
  __atomic_store_n(&native_lab_debug_buttons, buttons, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_axis_x, connected ? axis_x : 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_axis_y, connected ? axis_y : 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_right_axis_x,
                   connected ? right_axis_x : 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_right_axis_y,
                   connected ? right_axis_y : 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_connected, connected != 0,
                   __ATOMIC_RELEASE);
}

void pes_controller_native_pad_lab_debug_snapshot(
    PesNativePadLabDebug *snapshot) {
  if (!snapshot)
    return;
  memset(snapshot, 0, sizeof(*snapshot));
  snapshot->status = pes_controller_native_pad_lab_status();
  snapshot->context = __atomic_load_n(&native_lab_debug_context,
                                      __ATOMIC_ACQUIRE);
  snapshot->stock_mask = __atomic_load_n(&native_lab_debug_stock_mask,
                                         __ATOMIC_ACQUIRE);
  snapshot->route_mask = __atomic_load_n(&native_lab_debug_route_mask,
                                         __ATOMIC_ACQUIRE);
  snapshot->buttons = __atomic_load_n(&native_lab_debug_buttons,
                                      __ATOMIC_ACQUIRE);
  snapshot->native_keys = __atomic_load_n(&native_lab_debug_native_keys,
                                          __ATOMIC_ACQUIRE);
  snapshot->native_power_milli = __atomic_load_n(
      &native_lab_debug_native_power_milli, __ATOMIC_ACQUIRE);
  snapshot->native_right_power_milli = __atomic_load_n(
      &native_lab_debug_native_right_power_milli, __ATOMIC_ACQUIRE);
  snapshot->last_event = __atomic_load_n(&native_lab_debug_last_event,
                                         __ATOMIC_ACQUIRE);
  snapshot->last_command = __atomic_load_n(&native_lab_debug_last_command,
                                           __ATOMIC_ACQUIRE);
  snapshot->axis_x = __atomic_load_n(&native_lab_debug_axis_x,
                                     __ATOMIC_ACQUIRE);
  snapshot->axis_y = __atomic_load_n(&native_lab_debug_axis_y,
                                     __ATOMIC_ACQUIRE);
  snapshot->right_axis_x = __atomic_load_n(
      &native_lab_debug_right_axis_x, __ATOMIC_ACQUIRE);
  snapshot->right_axis_y = __atomic_load_n(
      &native_lab_debug_right_axis_y, __ATOMIC_ACQUIRE);
  snapshot->connected = __atomic_load_n(&native_lab_debug_connected,
                                        __ATOMIC_ACQUIRE);
  snapshot->connected_mask = __atomic_load_n(
      &native_lab_debug_connected_mask, __ATOMIC_ACQUIRE);
  snapshot->native_sample_mask = __atomic_load_n(
      &native_lab_debug_native_sample_mask, __ATOMIC_ACQUIRE);
  snapshot->owner_mask = __atomic_load_n(&native_lab_debug_owner_mask,
                                         __ATOMIC_ACQUIRE);
  snapshot->route_player_mask = __atomic_load_n(
      &native_lab_debug_route_player_mask, __ATOMIC_ACQUIRE);
  snapshot->cursor_slots = __atomic_load_n(
      &native_lab_debug_cursor_slots, __ATOMIC_ACQUIRE);
  snapshot->input_unit_mask = __atomic_load_n(
      &native_lab_debug_input_unit_mask, __ATOMIC_ACQUIRE);
  snapshot->accessor_bind_mask = __atomic_load_n(
      &native_lab_debug_accessor_bind_mask, __ATOMIC_ACQUIRE);
  snapshot->prime_mask = __atomic_load_n(
      &native_lab_debug_prime_mask, __ATOMIC_ACQUIRE);
  snapshot->setplay_pad = __atomic_load_n(&native_lab_debug_setplay_pad,
                                          __ATOMIC_ACQUIRE);
  snapshot->buttons_p2 = __atomic_load_n(&native_lab_debug_buttons_p2,
                                        __ATOMIC_ACQUIRE);
  snapshot->native_keys_p2 = __atomic_load_n(
      &native_lab_debug_native_keys_p2, __ATOMIC_ACQUIRE);
  snapshot->native_power_milli_p2 = __atomic_load_n(
      &native_lab_debug_native_power_milli_p2, __ATOMIC_ACQUIRE);
  snapshot->native_right_power_milli_p2 = __atomic_load_n(
      &native_lab_debug_native_right_power_milli_p2, __ATOMIC_ACQUIRE);
  snapshot->last_event_p2 = __atomic_load_n(
      &native_lab_debug_last_event_p2, __ATOMIC_ACQUIRE);
  snapshot->last_command_p2 = __atomic_load_n(
      &native_lab_debug_last_command_p2, __ATOMIC_ACQUIRE);
  snapshot->axis_x_p2 = __atomic_load_n(&native_lab_debug_axis_x_p2,
                                        __ATOMIC_ACQUIRE);
  snapshot->axis_y_p2 = __atomic_load_n(&native_lab_debug_axis_y_p2,
                                        __ATOMIC_ACQUIRE);
  snapshot->right_axis_x_p2 = __atomic_load_n(
      &native_lab_debug_right_axis_x_p2, __ATOMIC_ACQUIRE);
  snapshot->right_axis_y_p2 = __atomic_load_n(
      &native_lab_debug_right_axis_y_p2, __ATOMIC_ACQUIRE);
}

// CursorInfo starts with 24 CursorData records at a fixed 0xa0-byte stride.
// The stock mobile tmpdb loader creates only the HOME local-user cursor even
// when matchPlan owns a second pad.  In the isolated 2P lab, clone that fully
// initialized local cursor into an unused record and retarget only the fields
// that identify AWAY, pad No2, and the matching AWAY player slot.  Support and
// key settings therefore remain those produced by the stock loader.
#define NATIVE_LAB_CURSOR_COUNT 24u
#define NATIVE_LAB_CURSOR_SIZE 0xa0u
#define NATIVE_LAB_CURSOR_INVALID_PLAYER 0xffu

static uint32_t native_lab_cursor_player(const unsigned char *cursor) {
  uint32_t player = NATIVE_LAB_CURSOR_INVALID_PLAYER;
  memcpy(&player, cursor + 0x20, sizeof(player));
  return player;
}

static int32_t native_lab_cursor_pad(const unsigned char *cursor) {
  int32_t pad = -1;
  memcpy(&pad, cursor + 0x10, sizeof(pad));
  return pad;
}

static int native_lab_cursor_is_user(const unsigned char *cursor) {
  return cursor[0x0d] == 0 &&
         (native_lab_cursor_pad(cursor) != -1 || cursor[3] != 0);
}

static uint32_t native_lab_scan_cursor_owners(
    const unsigned char *cursor_info, uint32_t *home_slot,
    uint32_t *away_slot) {
  uint32_t mask = 0;
  *home_slot = NATIVE_LAB_CURSOR_COUNT;
  *away_slot = NATIVE_LAB_CURSOR_COUNT;
  for (uint32_t i = 0; i < NATIVE_LAB_CURSOR_COUNT; ++i) {
    const unsigned char *cursor = cursor_info + i * NATIVE_LAB_CURSOR_SIZE;
    if (!native_lab_cursor_is_user(cursor))
      continue;
    const uint32_t player = native_lab_cursor_player(cursor);
    if (cursor[0] == 0) {
      mask |= 1u;
      if (*home_slot == NATIVE_LAB_CURSOR_COUNT ||
          (native_lab_cursor_player(cursor_info +
                                    *home_slot * NATIVE_LAB_CURSOR_SIZE) > 10 &&
           player <= 10))
        *home_slot = i;
    } else if (cursor[0] == 2) {
      mask |= 2u;
      if (*away_slot == NATIVE_LAB_CURSOR_COUNT ||
          (native_lab_cursor_player(cursor_info +
                                    *away_slot * NATIVE_LAB_CURSOR_SIZE) < 11 &&
           player >= 11 && player <= 21))
        *away_slot = i;
    }
  }
  return mask;
}

static uint32_t native_lab_bind_away_cursor(void *cursor_info_ptr,
                                             uint32_t *encoded_slots) {
  if (!cursor_info_ptr || !encoded_slots)
    return 0;
  unsigned char *cursor_info = cursor_info_ptr;
  uint32_t home_slot, away_slot;
  uint32_t owner_mask = native_lab_scan_cursor_owners(
      cursor_info, &home_slot, &away_slot);
  int injected = 0;

  if ((owner_mask & 1u) && !(owner_mask & 2u)) {
    uint32_t target_slot = NATIVE_LAB_CURSOR_COUNT;
    for (uint32_t i = 0; i < NATIVE_LAB_CURSOR_COUNT; ++i) {
      unsigned char *candidate = cursor_info + i * NATIVE_LAB_CURSOR_SIZE;
      if (i != home_slot && candidate[0] == 1 &&
          native_lab_cursor_pad(candidate) == -1 &&
          native_lab_cursor_player(candidate) ==
              NATIVE_LAB_CURSOR_INVALID_PLAYER) {
        target_slot = i;
        break;
      }
    }
    if (target_slot < NATIVE_LAB_CURSOR_COUNT) {
      unsigned char *home = cursor_info + home_slot * NATIVE_LAB_CURSOR_SIZE;
      unsigned char *away = cursor_info + target_slot * NATIVE_LAB_CURSOR_SIZE;
      const uint8_t cursor_no = away[1];
      memcpy(away, home, NATIVE_LAB_CURSOR_SIZE);
      away[0] = 2;       // CursorData side marker: AWAY.
      away[1] = cursor_no; // Keep the destination CursorNo/index.
      away[6] = 0;       // Never make the second pad a coach cursor.
      away[0x0d] = 0;    // Human, not CPU.
      const int32_t pad_no = 1;
      memcpy(away + 0x10, &pad_no, sizeof(pad_no));
      static const uint32_t player_offsets[] = {0x20u, 0x24u, 0x28u};
      for (uint32_t i = 0;
           i < sizeof(player_offsets) / sizeof(player_offsets[0]); ++i) {
        const uint32_t offset = player_offsets[i];
        uint32_t player;
        memcpy(&player, away + offset, sizeof(player));
        if (player <= 10) {
          player += 11;
          memcpy(away + offset, &player, sizeof(player));
        }
      }
      // SetPlayerNo's current field must always be a valid AWAY PlayerNo even
      // if the mobile loader left HOME on automatic/invalid selection.
      uint32_t player = native_lab_cursor_player(away);
      if (player < 11 || player > 21) {
        player = 11;
        memcpy(away + 0x20, &player, sizeof(player));
      }
      away_slot = target_slot;
      injected = 1;
      owner_mask = native_lab_scan_cursor_owners(
          cursor_info, &home_slot, &away_slot);
    }
  } else if ((owner_mask & 2u) && away_slot < NATIVE_LAB_CURSOR_COUNT) {
    // A future stock/local path may create AWAY itself. Preserve the record
    // and only bind its real local pad.
    const int32_t pad_no = 1;
    memcpy(cursor_info + away_slot * NATIVE_LAB_CURSOR_SIZE + 0x10,
           &pad_no, sizeof(pad_no));
  }

  *encoded_slots = (home_slot < NATIVE_LAB_CURSOR_COUNT ? home_slot + 1 : 0) |
                   ((away_slot < NATIVE_LAB_CURSOR_COUNT ? away_slot + 1 : 0)
                    << 8) |
                   (injected ? 1u << 16 : 0);
  return owner_mask;
}

// Called by the post-return assembly trampoline, after every stock tmpdb
// cursor field and support setting has been finalized but before CheckControl
// decides which side is CPU-controlled.
void pes_match_cursor_info_ready(void *cursor_info) {
  if (!pes_controller_native_pad_lab_two_player())
    return;
  uint32_t slots = 0;
  const uint32_t owners = native_lab_bind_away_cursor(cursor_info, &slots);
  __atomic_store_n(&native_lab_debug_cursor_slots, slots,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_debug_owner_mask, owners,
                   __ATOMIC_RELEASE);
  if ((owners & 3u) != 3u)
    __atomic_fetch_or(&native_lab_status, 128u, __ATOMIC_RELAXED);
}

#ifndef NATIVE_PAD_LAB_HOST_TEST
static uint32_t native_lab_input_pad(const void *input) {
  if (!input)
    return 0;
  // ThinkUnitInputData: +0x08 CursorData*, +0x18 PadAccessor*.
  const void *cursor = *(void *const *)((const char *)input + 0x08);
  if (!cursor)
    return 0;
  int32_t pad_no = 0;
  memcpy(&pad_no, (const char *)cursor + 16, sizeof(pad_no));
  return pad_no == 1 ? 1u : 0u;
}

static void native_lab_note_action(const void *input, uint32_t event,
                                   uint32_t command) {
  if (!pes_controller_native_pad_lab_active() ||
      __atomic_load_n(&native_lab_debug_context, __ATOMIC_ACQUIRE) ==
          PES_SETPLAY_NONE)
    return;
  const uint32_t pad = native_lab_input_pad(input);
  __atomic_store_n(&native_lab_debug_setplay_pad, pad, __ATOMIC_RELEASE);
  if (pad == 1) {
    __atomic_store_n(&native_lab_debug_last_command_p2, command,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_debug_last_event_p2, event,
                     __ATOMIC_RELEASE);
  } else {
    __atomic_store_n(&native_lab_debug_last_command, command,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_debug_last_event, event, __ATOMIC_RELEASE);
  }
}
#endif

static void native_lab_sample(void *unit, uint32_t pad_no,
                              const void *config_ptr, const void *match_info) {
  // Pad::Update is Android-primary-only and returns before its normal hook for
  // No2. Prime that existing Cobra object immediately before the real
  // PadInputUnit consumes it; key mapping/history remain entirely stock.
  if (pes_controller_native_pad_lab_two_player() && pad_no == 1 &&
      cobra_pad_prime_native_port(1))
    __atomic_fetch_or(&native_lab_debug_prime_mask, 1u << pad_no,
                      __ATOMIC_RELAXED);
  native_lab_sample_original(unit, pad_no, config_ptr, match_info);
  if (!pes_controller_native_pad_lab_active() || pad_no > 1 || !unit ||
      (pad_no == 1 && !pes_controller_native_pad_lab_two_player()))
    return;
  // PadInput::Update owns one stable PadInputUnit per physical pad. Preserve
  // those canonical addresses so each synchronous ThinkUnit call can use the
  // correct history without fabricating any key or stick state.
  __atomic_store_n(&native_lab_input_units[pad_no], (uintptr_t)unit,
                   __ATOMIC_RELEASE);
  __atomic_fetch_or(&native_lab_debug_input_unit_mask, 1u << pad_no,
                    __ATOMIC_RELAXED);
  const void *history = native_lab_history_get(unit, 0);
  if (history) {
    uint32_t keys;
    float power, right_power;
    memcpy(&keys, history, sizeof(keys));
    memcpy(&power, (const char *)history + 8, sizeof(power));
    memcpy(&right_power, (const char *)history + 16, sizeof(right_power));
    uint32_t power_milli = 0;
    if (power > 0.0f) {
      if (power >= 1.0f)
        power_milli = 1000;
      else
        power_milli = (uint32_t)(power * 1000.0f + 0.5f);
    }
    uint32_t right_power_milli = 0;
    if (right_power > 0.0f) {
      if (right_power >= 1.0f)
        right_power_milli = 1000;
      else
        right_power_milli =
            (uint32_t)(right_power * 1000.0f + 0.5f);
    }
    if (pad_no == 1) {
      __atomic_store_n(&native_lab_debug_native_keys_p2, keys,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_debug_native_power_milli_p2,
                       power_milli, __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_debug_native_right_power_milli_p2,
                       right_power_milli, __ATOMIC_RELEASE);
    } else {
      __atomic_store_n(&native_lab_debug_native_keys, keys,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_debug_native_power_milli, power_milli,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_debug_native_right_power_milli,
                       right_power_milli, __ATOMIC_RELEASE);
    }
    __atomic_fetch_or(&native_lab_debug_native_sample_mask, 1u << pad_no,
                      __ATOMIC_RELAXED);
    if ((keys & 0x003fffffu) || power > 0.01f || right_power > 0.01f)
      __atomic_fetch_or(&native_lab_status, 2u, __ATOMIC_RELAXED);
  }
}

typedef struct {
  void *accessor;
  void *previous_unit;
  uint32_t pad;
  int active;
} NativeLabInputBinding;

static int native_lab_bind_input(const void *input,
                                 NativeLabInputBinding *binding) {
  memset(binding, 0, sizeof(*binding));
  if (!input || !pes_controller_native_pad_lab_active())
    return 0;
  // Verified from ThinkUnitInputData(CommandPlayerInputData const&): the
  // CursorData pointer is +0x08 and the PadAccessor pointer is +0x18.
  void *cursor = *(void *const *)((const char *)input + 0x08);
  void *accessor = *(void *const *)((const char *)input + 0x18);
  const uint32_t player = *(const uint32_t *)((const char *)input + 0x24);
  if (!cursor || !accessor || player >= 22)
    return 0;
  const uint32_t expected_pad = player < 11 ? 0u : 1u;
  if (expected_pad == 1 && !pes_controller_native_pad_lab_two_player())
    return 0;
  const int32_t stored_pad = (int32_t)expected_pad;
  memcpy((char *)cursor + 16, &stored_pad, sizeof(stored_pad));
  binding->pad = expected_pad;
  const uintptr_t target = __atomic_load_n(
      &native_lab_input_units[expected_pad], __ATOMIC_ACQUIRE);
  if (target) {
    // Every PadAccessor method begins by loading PadAccessor[0] and calling
    // PadInputUnit::Get(). Bind only around this side's synchronous update,
    // then restore it so no later mobile/Exhibition code inherits our route.
    memcpy(&binding->previous_unit, accessor,
           sizeof(binding->previous_unit));
    binding->accessor = accessor;
    void *target_unit = (void *)target;
    memcpy(accessor, &target_unit, sizeof(target_unit));
    binding->active = 1;
    __atomic_fetch_or(&native_lab_debug_accessor_bind_mask,
                      1u << expected_pad, __ATOMIC_RELAXED);
  }
  return 1;
}

static void native_lab_restore_input(NativeLabInputBinding *binding) {
  if (!binding->active)
    return;
  memcpy(binding->accessor, &binding->previous_unit,
         sizeof(binding->previous_unit));
  binding->active = 0;
}

static int native_lab_layout_matches(const void *list) {
  for (unsigned i = 0; i < sizeof(native_lab_units)/sizeof(native_lab_units[0]); i++) {
    const NativeLabUnit *expected = &native_lab_units[i];
    const void *unit = *(void *const *)((const char *)list +
                                      0x3bf8 + expected->kind * 8);
    if (!unit || !expected->vptr || *(const uintptr_t *)unit != expected->vptr)
      return 0;
  }
  return 1;
}

static int native_lab_append(uint32_t *entries, uint32_t *count, uint32_t kind) {
  // The original list has 97 entry slots. Preserve ordering and avoid executing
  // a native action twice if another context already selected it.
  if (kind >= 97 || *count >= 97)
    return 0;
  for (uint32_t i = 0; i < *count; i++)
    if (entries[i] == kind)
      return 1;
  entries[(*count)++] = kind;
  return 1;
}

static int native_lab_has_kind(const uint32_t *entries, uint32_t count,
                               uint32_t kind) {
  for (uint32_t i = 0; i < count; i++)
    if (entries[i] == kind)
      return 1;
  return 0;
}

static uint32_t native_lab_setplay_context(const uint32_t *entries,
                                           uint32_t count) {
  if (!native_lab_has_kind(entries, count, 90))
    return PES_SETPLAY_NONE;
  if (native_lab_has_kind(entries, count, 64))
    return PES_SETPLAY_GOAL_KICK;
  if (native_lab_has_kind(entries, count, 65) ||
      native_lab_has_kind(entries, count, 70))
    return PES_SETPLAY_CORNER;
  if (native_lab_has_kind(entries, count, 72) ||
      native_lab_has_kind(entries, count, 75))
    return PES_SETPLAY_FREE_KICK;
  return PES_SETPLAY_NONE;
}

static void native_lab_list_update(void *list, const void *input,
                                   uint32_t previous, uint32_t context) {
  NativeLabInputBinding binding;
  const int local_input = list && native_lab_bind_input(input, &binding);
  native_lab_list_update_original(list, input, previous, context);
  native_lab_restore_input(&binding);
  if (!local_input)
    return;
  __atomic_fetch_or(&native_lab_status, 4u, __ATOMIC_RELAXED);
  if (!native_lab_layout_matches(list)) {
    __atomic_fetch_or(&native_lab_status, 128u, __ATOMIC_RELAXED);
    return; // Keep the stock list intact if the ABI doesn't match.
  }
  const void *cursor = *(void *const *)((const char *)input + 0x08);
  int32_t route_pad = 0;
  memcpy(&route_pad, (const char *)cursor + 16, sizeof(route_pad));
  if (route_pad == 0 || route_pad == 1)
    __atomic_fetch_or(&native_lab_debug_route_player_mask, 1u << route_pad,
                      __ATOMIC_RELAXED);
  uint32_t *stock = list;
  if (stock[0] > 97) {
    __atomic_fetch_or(&native_lab_status, 128u, __ATOMIC_RELAXED);
    return;
  }
  const uint32_t setplay_context =
      native_lab_setplay_context(stock + 1, stock[0]);
  const int native_setplay = setplay_context != PES_SETPLAY_NONE;
  uint32_t stock_mask = 0;
  if (native_lab_has_kind(stock + 1, stock[0], 90))
    stock_mask |= PES_NATIVE_LAB_STOCK_MOBILE_KICK;
  if (native_lab_has_kind(stock + 1, stock[0], 95))
    stock_mask |= PES_NATIVE_LAB_STOCK_MOBILE_CAMERA;
  if (native_lab_has_kind(stock + 1, stock[0], 64))
    stock_mask |= PES_NATIVE_LAB_STOCK_GOALKICK_SUPPORT;
  if (native_lab_has_kind(stock + 1, stock[0], 65))
    stock_mask |= PES_NATIVE_LAB_STOCK_SHORT_CORNER;
  if (native_lab_has_kind(stock + 1, stock[0], 70))
    stock_mask |= PES_NATIVE_LAB_STOCK_CORNER_TACTICS;
  if (native_lab_has_kind(stock + 1, stock[0], 72))
    stock_mask |= PES_NATIVE_LAB_STOCK_FREEKICK_TACTICS;
  if (native_lab_has_kind(stock + 1, stock[0], 75))
    stock_mask |= PES_NATIVE_LAB_STOCK_FREEKICK_POSITION;
  uint32_t entries[97], count = 0, changed = 0;
  for (uint32_t i = 0; i < stock[0]; i++) {
    uint32_t kind = stock[1+i];
    if (native_setplay && kind == 95) {
      // MobileSetplayCameraChange consumes a mobile-only flag. SetplayGuide
      // below owns left-stick aiming in the native candidate.
      changed++;
      continue;
    }
    if (native_setplay && kind == 90) {
      // Native set-play: schedule only existing console ThinkUnits. No touch
      // or swipe is synthesized. Context-specific units remain in stock order.
      if (!native_lab_append(entries, &count, 26) ||
          !native_lab_append(entries, &count, 0) ||
          !native_lab_append(entries, &count, 1) ||
          !native_lab_append(entries, &count, 3))
        return;
      if (setplay_context == PES_SETPLAY_CORNER &&
          !native_lab_append(entries, &count, 70))
        return;
      if (setplay_context == PES_SETPLAY_FREE_KICK &&
          !native_lab_append(entries, &count, 72))
        return;
      changed++;
      continue;
    }
    if (kind >= 78 && kind <= 89) {
      changed++;
      switch (kind) {
        case 78: kind = 3; break;   // Shoot (Y).
        case 79:                   // Pass family: B, A, X.
          if (!native_lab_append(entries, &count, 0) ||
              !native_lab_append(entries, &count, 1))
            return;
          kind = 2;
          break;
        case 80: case 82: continue; // Mobile sub-action/automatic touch return.
        case 81: kind = 24; break;
        case 83: kind = 10; break;  // Dribble reads the real stick history.
        case 84: kind = 12; break;  // Cursor change (L).
        case 85: kind = 5; break;   // Pressure (B).
        case 86: kind = 6; break;   // Tackle (native B timing).
        case 87: kind = 9; break;   // Friend press (Y).
        case 88: kind = 7; break;   // Slide (A).
        case 89: kind = 11; break;  // Free movement.
      }
    }
    if (!native_lab_append(entries, &count, kind))
      return; // Transactional: no partial rewrite on invalid/oversized data.
  }
  if (changed) {
    memcpy(stock + 1, entries, count * sizeof(entries[0]));
    stock[0] = count;
    __atomic_fetch_or(&native_lab_status, 8u, __ATOMIC_RELAXED);
  }
  if (native_setplay) {
    uint32_t route_mask = PES_NATIVE_LAB_ROUTE_SETPLAY_GUIDE |
                          PES_NATIVE_LAB_ROUTE_SHORT_PASS |
                          PES_NATIVE_LAB_ROUTE_LONG_PASS |
                          PES_NATIVE_LAB_ROUTE_SHOOT |
                          PES_NATIVE_LAB_ROUTE_CAMERA_STICK;
    if (setplay_context == PES_SETPLAY_GOAL_KICK)
      route_mask |= PES_NATIVE_LAB_ROUTE_GOALKICK_SUPPORT;
    else if (setplay_context == PES_SETPLAY_CORNER)
      route_mask |= PES_NATIVE_LAB_ROUTE_CORNER_TACTICS;
    else if (setplay_context == PES_SETPLAY_FREE_KICK)
      route_mask |= PES_NATIVE_LAB_ROUTE_FREEKICK_TACTICS;
    __atomic_store_n(&native_lab_debug_context, setplay_context,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_debug_stock_mask, stock_mask,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_debug_route_mask, route_mask,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_debug_last_event,
                     PES_NATIVE_LAB_EVENT_NONE, __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_debug_last_command, 0,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_debug_last_event_p2,
                     PES_NATIVE_LAB_EVENT_NONE, __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_debug_last_command_p2, 0,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_debug_setplay_pad,
                     route_pad == 1 ? 1u : 0u, __ATOMIC_RELEASE);
    __atomic_fetch_or(&native_lab_status, 32u | 64u, __ATOMIC_RELAXED);
  }
}

#ifndef NATIVE_PAD_LAB_HOST_TEST
static uint32_t (*native_lab_guide_main_original)(void *, const void *,
                                                  uint32_t);
static uint32_t (*native_lab_short_press_original)(void *, const void *);
static uint32_t (*native_lab_short_pull_original)(void *, const void *);
static uint32_t (*native_lab_long_press_original)(void *, const void *);
static uint32_t (*native_lab_long_pull_original)(void *, const void *);
static uint32_t (*native_lab_shoot_press_original)(void *, const void *);
static uint32_t (*native_lab_shoot_pull_original)(void *, const void *);
static uint32_t (*native_lab_support_pull_original)(void *, const void *);

static uint32_t native_lab_guide_main(void *unit, const void *input,
                                      uint32_t kind) {
  const uint32_t result = native_lab_guide_main_original
                              ? native_lab_guide_main_original(unit, input,
                                                               kind)
                              : 0;
  if (result)
    native_lab_note_action(input, PES_NATIVE_LAB_EVENT_AIM, result);
  return result;
}

#define NATIVE_LAB_ACTION_WRAPPER(name, event, original)                    \
  static uint32_t name(void *unit, const void *input) {                     \
    const uint32_t result = original ? original(unit, input) : 0;           \
    native_lab_note_action(input, event, result);                           \
    return result;                                                          \
  }

NATIVE_LAB_ACTION_WRAPPER(native_lab_short_press,
                          PES_NATIVE_LAB_EVENT_SHORT_PRESS,
                          native_lab_short_press_original)
NATIVE_LAB_ACTION_WRAPPER(native_lab_short_pull,
                          PES_NATIVE_LAB_EVENT_SHORT_RELEASE,
                          native_lab_short_pull_original)
NATIVE_LAB_ACTION_WRAPPER(native_lab_long_press,
                          PES_NATIVE_LAB_EVENT_LONG_PRESS,
                          native_lab_long_press_original)
NATIVE_LAB_ACTION_WRAPPER(native_lab_long_pull,
                          PES_NATIVE_LAB_EVENT_LONG_RELEASE,
                          native_lab_long_pull_original)
NATIVE_LAB_ACTION_WRAPPER(native_lab_shoot_press,
                          PES_NATIVE_LAB_EVENT_SHOOT_PRESS,
                          native_lab_shoot_press_original)
NATIVE_LAB_ACTION_WRAPPER(native_lab_shoot_pull,
                          PES_NATIVE_LAB_EVENT_SHOOT_RELEASE,
                          native_lab_shoot_pull_original)
NATIVE_LAB_ACTION_WRAPPER(native_lab_support_pull,
                          PES_NATIVE_LAB_EVENT_SUPPORT_RELEASE,
                          native_lab_support_pull_original)

#undef NATIVE_LAB_ACTION_WRAPPER

static uintptr_t *native_lab_method_slot(so_module *module,
                                         const char *vtable,
                                         const char *method) {
  const uintptr_t address = so_try_find_addr_rx(module, method);
  return address ? find_vtable_method_slot(module, vtable, address, 128)
                 : NULL;
}

static int install_native_lab_action_debug(so_module *module) {
  const uintptr_t guide = so_try_find_addr_rx(
      module,
      "_ZN5match3pad21ThinkUnitSetplayGuide4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE");
  uintptr_t *guide_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad21ThinkUnitSetplayGuideE",
      "_ZN5match3pad21ThinkUnitSetplayGuide4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE");
  uintptr_t *short_press_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad18ThinkUnitShortPassE",
      "_ZN5match3pad18ThinkUnitShortPass9ExecPressERKNS0_18ThinkUnitInputDataE");
  uintptr_t *short_pull_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad18ThinkUnitShortPassE",
      "_ZN5match3pad18ThinkUnitShortPass8ExecPullERKNS0_18ThinkUnitInputDataE");
  uintptr_t *long_press_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad17ThinkUnitLongPassE",
      "_ZN5match3pad17ThinkUnitLongPass9ExecPressERKNS0_18ThinkUnitInputDataE");
  uintptr_t *long_pull_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad17ThinkUnitLongPassE",
      "_ZN5match3pad17ThinkUnitLongPass8ExecPullERKNS0_18ThinkUnitInputDataE");
  uintptr_t *shoot_press_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad14ThinkUnitShootE",
      "_ZN5match3pad14ThinkUnitShoot9ExecPressERKNS0_18ThinkUnitInputDataE");
  uintptr_t *shoot_pull_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad14ThinkUnitShootE",
      "_ZN5match3pad14ThinkUnitShoot8ExecPullERKNS0_18ThinkUnitInputDataE");
  uintptr_t *support_pull_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad28ThinkUnitGoalkickPassSupportE",
      "_ZN5match3pad28ThinkUnitGoalkickPassSupport8ExecPullERKNS0_18ThinkUnitInputDataE");
  if (!guide || !guide_slot || !short_press_slot || !short_pull_slot ||
      !long_press_slot || !long_pull_slot || !shoot_press_slot ||
      !shoot_pull_slot || !support_pull_slot)
    return 0;

  native_lab_guide_main_original = (void *)guide;
  native_lab_short_press_original = (void *)*short_press_slot;
  native_lab_short_pull_original = (void *)*short_pull_slot;
  native_lab_long_press_original = (void *)*long_press_slot;
  native_lab_long_pull_original = (void *)*long_pull_slot;
  native_lab_shoot_press_original = (void *)*shoot_press_slot;
  native_lab_shoot_pull_original = (void *)*shoot_pull_slot;
  native_lab_support_pull_original = (void *)*support_pull_slot;
  *guide_slot = (uintptr_t)&native_lab_guide_main;
  *short_press_slot = (uintptr_t)&native_lab_short_press;
  *short_pull_slot = (uintptr_t)&native_lab_short_pull;
  *long_press_slot = (uintptr_t)&native_lab_long_press;
  *long_pull_slot = (uintptr_t)&native_lab_long_pull;
  *shoot_press_slot = (uintptr_t)&native_lab_shoot_press;
  *shoot_pull_slot = (uintptr_t)&native_lab_shoot_pull;
  *support_pull_slot = (uintptr_t)&native_lab_support_pull;
  return 1;
}

static void install_native_pad_lab(so_module *module) {
  // Patch only the two PLT entries. Calling the unmodified exported functions
  // directly from the wrappers keeps native history and mode gates intact.
  const uintptr_t list_plt = (uintptr_t)module->load_base + 0x38cc850;
  const uintptr_t sample_plt = (uintptr_t)module->load_base + 0x38ea5c0;
  const uint32_t list_words[] = {0x9002e2d0, 0xf9434211, 0x911a0210, 0xd61f0220};
  const uint32_t sample_words[] = {0xb002e250, 0xf9429e11, 0x9114e210, 0xd61f0220};
  if (memcmp((void *)list_plt, list_words, sizeof(list_words)) ||
      memcmp((void *)sample_plt, sample_words, sizeof(sample_words)))
    return;
  native_lab_list_update_original = (void *)so_try_find_addr_rx(module,
      "_ZN5match3pad13ThinkUnitList6UpdateERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindEj");
  native_lab_sample_original = (void *)so_try_find_addr_rx(module,
      "_ZN5match8registry12PadInputUnit6UpdateEjPKNS0_9KeyConfigEPKNS0_9MatchInfoE");
  native_lab_history_get = (void *)so_try_find_addr_rx(module,
      "_ZNK5match8registry12PadInputUnit3GetEi");
  cobra_pad_get_pad = (void *)so_try_find_addr_rx(module,
      "_ZN5cobra4game3Pad6GetPadEj");
  if (!native_lab_list_update_original || !native_lab_sample_original ||
      !native_lab_history_get || !cobra_pad_get_pad)
    return;
  for (unsigned i = 0; i < sizeof(native_lab_units)/sizeof(native_lab_units[0]); i++) {
    uintptr_t vt = so_try_find_addr_rx(module, native_lab_units[i].symbol);
    if (!vt)
      return;
    native_lab_units[i].vptr = vt + 16;
  }
  hook_arm64(list_plt, (uintptr_t)&native_lab_list_update);
  hook_arm64(sample_plt, (uintptr_t)&native_lab_sample);
  native_lab_action_hooks_installed = install_native_lab_action_debug(module);
  const char *cursor_info_symbol =
      "_ZN9game_mode13MatchListener22SetCursorInfoFromTmpdbEPN5match8registry10CursorInfoEjib";
  const uintptr_t cursor_info_backing =
      so_find_addr(module, cursor_info_symbol);
  const uintptr_t cursor_info_runtime =
      so_try_find_addr_rx(module, cursor_info_symbol);
  static const uint32_t expected_cursor_info_entry[4] = {
      0xd10783ff, // sub sp, sp, #0x1e0
      0xa9186ffc, // stp x28, x27, [sp, #0x180]
      0xa91967fa, // stp x26, x25, [sp, #0x190]
      0xa91a5ff8, // stp x24, x23, [sp, #0x1a0]
  };
  if (!cursor_info_backing || !cursor_info_runtime ||
      memcmp((const void *)cursor_info_backing, expected_cursor_info_entry,
             sizeof(expected_cursor_info_entry)) != 0)
    fatal_error("Unexpected SetCursorInfoFromTmpdb entry at %p",
                (void *)cursor_info_backing);
  pes_match_cursor_info_from_tmpdb_resume = cursor_info_runtime + 0x10;
  hook_arm64(cursor_info_backing,
             (uintptr_t)&pes_match_cursor_info_from_tmpdb_hook);
  native_lab_installed = 1;
}
#endif

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
static uint32_t native_lab_published_setplay_context;
static uint32_t native_lab_trajectory_enabled;
static uint32_t native_lab_previous_buttons[2];
static uint32_t native_lab_setplay_linger_frames;
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

// The HID polling path latches LS-Y before any ThinkUnit is scheduled. Some
// set-play variants do not call MobileSetplayKick::Main on every idle frame,
// so elevation must not depend on that callback being active.
static float native_lab_normalize_axis(int32_t raw) {
  float axis = (float)raw / 32768.0f;
  const float absolute = axis < 0.0f ? -axis : axis;
  if (absolute <= 0.18f)
    return 0.0f;
  const float clamped = absolute > 1.0f ? 1.0f : absolute;
  const float normalized = (clamped - 0.18f) / 0.82f;
  return axis < 0.0f ? -normalized : normalized;
}

// Keep the set-piece preview and the close-free-kick flight solver within a
// useful gameplay envelope.  The previous 30-degree/4-unit ceiling made a
// fully raised stick produce an exaggerated, almost vertical arc.
#define NATIVE_LAB_TRAJECTORY_MAX_ELEVATION_DEGREES 18.0f
#define NATIVE_LAB_TRAJECTORY_MAX_LIFT 2.4f
// One ThinkUnitList exists per local cursor.  Keep the real unit objects for
// each pad so MobileSetplayKick can delegate to the console press/release
// implementations without adding dormant units to the active list.
enum {
  NATIVE_LAB_ACTION_SHORT = 0,
  NATIVE_LAB_ACTION_LONG,
  NATIVE_LAB_ACTION_SHOOT,
  NATIVE_LAB_ACTION_GUIDE,
  NATIVE_LAB_ACTION_COUNT
};
static uintptr_t native_lab_action_units[2][NATIVE_LAB_ACTION_COUNT];
// ThinkUnitPenaltykick is the stock console press/pull action. Keep its real
// per-list object so the custom gauge can observe native charge without
// fabricating a command or sharing P1 state with P2.
static uintptr_t native_lab_penalty_action_units[2];
// Native penalty objects are optional on this mobile build.  Their indexes
// come from ThinkUnitList's constructor table (object offsets 0x840, 0xab0,
// 0xc08, 0xc40, and 0x1218 respectively).  Keep their ABI gate separate from
// native_lab_units: a penalty mismatch must never disable ordinary gameplay.
enum {
  NATIVE_LAB_KIND_PENALTY_GUIDE = 27,
  NATIVE_LAB_KIND_PENALTY_KICK = 37,
  NATIVE_LAB_KIND_KEEPER_PENALTY_MOVE = 43,
  NATIVE_LAB_KIND_KEEPER_PENALTY_ACTION = 44,
  NATIVE_LAB_KIND_KEEPER_PENALTY_LAYER = 66,
};
enum {
  NATIVE_LAB_PENALTY_READY_KICKER = 1u,
  NATIVE_LAB_PENALTY_READY_KEEPER = 2u,
};
static uint32_t native_lab_penalty_ready_role_mask;
// Keep the real native action unit for each local cursor. Its +0x20 charge is
// the sole source for the pad-owned custom gauge and release power bridge.
static uint32_t native_lab_active_action[2];
// The stock Screen2d gauge is global and keeps snapping P2 charge to P1.
// Publish only pad-owned charge state; overlay.c renders a visual-only HUD bar
// without touching the command or the engine's shared player marker.
static uint32_t native_lab_gauge_owner_pad;
static uint32_t native_lab_gauge_power_milli;
static uint32_t native_lab_gauge_linger_frames;
static uint32_t native_lab_gauge_active_mask;
// Charging is independent from set-play action tokens. The same native
// press/pull wrappers are also used in ordinary Exhibition gameplay, where
// native_lab_active_action is intentionally zero. Without this mask the input
// poll cleared a newly pressed gauge before its next charge sample arrived.
static uint32_t native_lab_gauge_charging_mask;
static uint32_t native_lab_gauge_power_milli_p2;
static uint32_t native_lab_gauge_power_milli_by_pad[2];
static uint32_t native_lab_gauge_linger_frames_by_pad[2];
// PlayerNo that owned the ball/action when charging started. This comes from
// ThinkUnitInputData +0x24 (the field passed by the engine to GetPlayerMove),
// not CursorData +0x20: that cursor field resolves to the team slot/GK on this
// build and caused every custom gauge to follow the goalkeeper.
static uint32_t native_lab_gauge_player_no_by_pad[2];
// A release freezes the bar; it does not dismiss it. The first post-release
// BallInfo sample becomes the origin. Movement alone is insufficient because
// the ball can roll during the kicker's wind-up; completion also requires the
// ball to separate from the closest observed player/ball distance for several
// consecutive render samples. Bit storage keeps the render/input-thread
// handoff atomic.
static uint32_t native_lab_gauge_release_ball_valid_mask;
static uint32_t native_lab_gauge_release_ball_bits[2][3];
static uint32_t native_lab_gauge_release_min_distance_bits[2];
static uint32_t native_lab_gauge_completion_frames[2];
// World-follow anchor published by ModelCursorName::GetPosition. Coordinates
// are display pixels * 1000; the short TTL prevents a stale player position
// from surviving a camera cut, replay, or match teardown.
static int32_t native_lab_gauge_anchor_x_milli[2];
static int32_t native_lab_gauge_anchor_y_milli[2];
static uint32_t native_lab_gauge_anchor_ttl[2];
// ThinkUnitManager creates the PadCommand after a unit returns its release
// command. Keep a one-command token so only that user's close-free-kick command
// receives LS vertical aim; unrelated and CPU kicks are never modified.
static uint32_t native_lab_pending_kick_pad;
static uint32_t native_lab_pending_kick_command;
static uint32_t native_lab_pending_kick_action;
static uint32_t native_lab_pending_kick_power_bits;
static uint32_t native_lab_command_angle_bits[2];
// Stable, stock angle captured once per set-piece owner/player. The command
// angle is written back into MobileSetplayKick, so reading +0x38 again on the
// next frame would otherwise treat our previous override as a new baseline
// and accumulate LS/camera offsets until the preview spins.
static uint32_t native_lab_base_angle_bits[2];
static uint32_t native_lab_base_angle_player[2];
static uint32_t native_lab_command_vertical_bits[2];
static uint32_t native_lab_command_angle_valid_mask;
static uint32_t native_lab_left_aim_latched_mask;
// DrawPassLine derives every preview point from the live player/model state.
// During the kick run-up that state moves and rotates, which made an already
// selected trajectory slide or spin even though the command angle was latched.
// Keep a pad-owned snapshot of the nine world-space points and restore it until
// the ball/action completion clears the cache.
#define NATIVE_LAB_TRAJECTORY_POINT_COUNT 9u
static uint32_t native_lab_trajectory_freeze_mask;
static uint32_t native_lab_trajectory_cache_valid_mask;
static uint32_t native_lab_trajectory_cache_bits
    [2][NATIVE_LAB_TRAJECTORY_POINT_COUNT][3];
// Close free-kick elevation is consumed by the ball-injection pipeline, not
// by PadCommand::SetKick. Keep a short pad-owned token from the shoot release
// until GetBallInjectionSpeedAndRotation has produced the first flight vector.
// This avoids changing ordinary shots, corners, goal kicks, or CPU kicks.
static uint32_t native_lab_free_kick_elevation_bits[2];
static uint32_t native_lab_free_kick_elevation_mask;
static uint32_t native_lab_free_kick_elevation_linger[2];

static void native_lab_clear_trajectory_cache(uint32_t pad) {
  if (pad > 1)
    return;
  __atomic_fetch_and(&native_lab_trajectory_freeze_mask, ~(1u << pad),
                     __ATOMIC_ACQ_REL);
  __atomic_fetch_and(&native_lab_trajectory_cache_valid_mask, ~(1u << pad),
                     __ATOMIC_ACQ_REL);
  for (uint32_t index = 0; index < NATIVE_LAB_TRAJECTORY_POINT_COUNT;
       ++index) {
    for (uint32_t axis = 0; axis < 3; ++axis)
      __atomic_store_n(&native_lab_trajectory_cache_bits[pad][index][axis], 0,
                       __ATOMIC_RELEASE);
  }
}

static void native_lab_clear_trajectory_cache_all(void) {
  native_lab_clear_trajectory_cache(0);
  native_lab_clear_trajectory_cache(1);
}

static void native_lab_cache_trajectory_points(uint32_t pad, void *screen_2d) {
  if (pad > 1 || !screen_2d)
    return;
  // Invalidate first so a concurrent renderer never consumes a half-written
  // point set. Publish valid only after all 27 float bit patterns are stored.
  __atomic_fetch_and(&native_lab_trajectory_cache_valid_mask, ~(1u << pad),
                     __ATOMIC_ACQ_REL);
  for (uint32_t index = 0; index < NATIVE_LAB_TRAJECTORY_POINT_COUNT;
       ++index) {
    for (uint32_t axis = 0; axis < 3; ++axis) {
      uint32_t bits = 0;
      memcpy(&bits,
             (const char *)screen_2d + 0x10f0 + index * 12u + axis * 4u,
             sizeof(bits));
      __atomic_store_n(&native_lab_trajectory_cache_bits[pad][index][axis],
                       bits, __ATOMIC_RELEASE);
    }
  }
  __atomic_fetch_or(&native_lab_trajectory_cache_valid_mask, 1u << pad,
                    __ATOMIC_RELEASE);
}

static int native_lab_restore_trajectory_points(uint32_t pad, void *screen_2d) {
  if (pad > 1 || !screen_2d ||
      !(__atomic_load_n(&native_lab_trajectory_cache_valid_mask,
                        __ATOMIC_ACQUIRE) & (1u << pad)))
    return 0;
  for (uint32_t index = 0; index < NATIVE_LAB_TRAJECTORY_POINT_COUNT;
       ++index) {
    for (uint32_t axis = 0; axis < 3; ++axis) {
      const uint32_t bits = __atomic_load_n(
          &native_lab_trajectory_cache_bits[pad][index][axis],
          __ATOMIC_ACQUIRE);
      memcpy((char *)screen_2d + 0x10f0 + index * 12u + axis * 4u, &bits,
             sizeof(bits));
    }
  }
  return 1;
}

static void native_lab_clear_free_kick_elevation(void) {
  __atomic_store_n(&native_lab_free_kick_elevation_mask, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_free_kick_elevation_bits[0], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_free_kick_elevation_bits[1], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_free_kick_elevation_linger[0], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_free_kick_elevation_linger[1], 0,
                   __ATOMIC_RELEASE);
}

typedef struct {
  void *plugin;
  float yaw;
  uint32_t pad;
  uint64_t last_tick;
} NativeLabCameraState;
static NativeLabCameraState native_lab_corner_camera;
static NativeLabCameraState native_lab_goal_camera;
static NativeLabCameraState native_lab_free_camera;

// Camera and kick units update independently. Publish the bounded RS yaw as
// fixed-point radians so the native PadCommand can inherit the stable V7
// camera angle. LS never moves the camera; it is reserved for kick direction.
static int32_t native_lab_camera_yaw_millirad[2];

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
  {27, "_ZTVN5match3pad25ThinkUnitPenaltykickGuideE", 0},
  {62, "_ZTVN5match3pad33ThinkUnitThrowinBodyAngleRotationE", 0},
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

// Resolved opportunistically during install and checked immediately before a
// penalty list is augmented.  Missing or mismatched entries only disable the
// native penalty route; they are deliberately excluded from the global ABI
// validator above.
static NativeLabUnit native_lab_optional_penalty_units[] = {
  {NATIVE_LAB_KIND_PENALTY_GUIDE,
   "_ZTVN5match3pad25ThinkUnitPenaltykickGuideE", 0},
  {NATIVE_LAB_KIND_PENALTY_KICK,
   "_ZTVN5match3pad20ThinkUnitPenaltykickE", 0},
  {NATIVE_LAB_KIND_KEEPER_PENALTY_MOVE,
   "_ZTVN5match3pad30ThinkUnitKeeperPenaltykickMoveE", 0},
  {NATIVE_LAB_KIND_KEEPER_PENALTY_ACTION,
   "_ZTVN5match3pad32ThinkUnitKeeperPenaltykickActionE", 0},
  {NATIVE_LAB_KIND_KEEPER_PENALTY_LAYER,
   "_ZTVN5match3pad31ThinkUnitKeeperPenaltykickLayerE", 0},
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
  __atomic_store_n(&native_lab_published_setplay_context, PES_SETPLAY_NONE,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_trajectory_enabled, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_penalty_ready_role_mask, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_previous_buttons[0], 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_previous_buttons[1], 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_setplay_linger_frames, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_owner_pad, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_power_milli, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_linger_frames, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_active_mask, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_charging_mask, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_power_milli_p2, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_power_milli_by_pad[0], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_power_milli_by_pad[1], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_linger_frames_by_pad[0], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_linger_frames_by_pad[1], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_player_no_by_pad[0], UINT32_MAX,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_player_no_by_pad[1], UINT32_MAX,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_release_ball_valid_mask, 0,
                   __ATOMIC_RELEASE);
  for (uint32_t pad = 0; pad < 2; ++pad)
    for (uint32_t axis = 0; axis < 3; ++axis)
      __atomic_store_n(&native_lab_gauge_release_ball_bits[pad][axis], 0,
                       __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_release_min_distance_bits[0], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_release_min_distance_bits[1], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_completion_frames[0], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_completion_frames[1], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_anchor_x_milli[0], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_anchor_x_milli[1], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_anchor_y_milli[0], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_anchor_y_milli[1], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_anchor_ttl[0], 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_anchor_ttl[1], 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_pending_kick_pad, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_pending_kick_command, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_pending_kick_action, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_pending_kick_power_bits, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_command_angle_bits[0], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_command_angle_bits[1], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_base_angle_bits[0], 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_base_angle_bits[1], 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_base_angle_player[0], UINT32_MAX,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_base_angle_player[1], UINT32_MAX,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_command_vertical_bits[0], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_command_vertical_bits[1], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_command_angle_valid_mask, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_left_aim_latched_mask, 0,
                   __ATOMIC_RELEASE);
  native_lab_clear_trajectory_cache_all();
  native_lab_clear_free_kick_elevation();
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
  for (uint32_t pad = 0; pad < 2; ++pad) {
    for (uint32_t action = 0; action < NATIVE_LAB_ACTION_COUNT; ++action)
      __atomic_store_n(&native_lab_action_units[pad][action], 0,
                       __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_active_action[pad], 0, __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_penalty_action_units[pad], 0,
                     __ATOMIC_RELEASE);
  }
  memset(&native_lab_corner_camera, 0, sizeof(native_lab_corner_camera));
  memset(&native_lab_goal_camera, 0, sizeof(native_lab_goal_camera));
  memset(&native_lab_free_camera, 0, sizeof(native_lab_free_camera));
  __atomic_store_n(&native_lab_camera_yaw_millirad[0], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_camera_yaw_millirad[1], 0,
                   __ATOMIC_RELEASE);
}

static void native_lab_gauge_clear_pad(uint32_t pad) {
  if (pad > 1)
    return;
  // BallInfo/action completion (or the cancellation safety timeout) releases
  // the trajectory snapshot along with the pad-owned gauge state.
  native_lab_clear_trajectory_cache(pad);
  __atomic_store_n(&native_lab_gauge_power_milli_by_pad[pad], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_linger_frames_by_pad[pad], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_player_no_by_pad[pad], UINT32_MAX,
                   __ATOMIC_RELEASE);
  __atomic_fetch_and(&native_lab_gauge_release_ball_valid_mask,
                     ~(1u << pad), __ATOMIC_ACQ_REL);
  __atomic_store_n(&native_lab_gauge_release_min_distance_bits[pad], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_completion_frames[pad], 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_anchor_ttl[pad], 0,
                   __ATOMIC_RELEASE);
  __atomic_fetch_and(&native_lab_gauge_active_mask, ~(1u << pad),
                     __ATOMIC_ACQ_REL);
  __atomic_fetch_and(&native_lab_gauge_charging_mask, ~(1u << pad),
                     __ATOMIC_ACQ_REL);
  if (pad == 0)
    __atomic_store_n(&native_lab_gauge_power_milli, 0, __ATOMIC_RELEASE);
  else
    __atomic_store_n(&native_lab_gauge_power_milli_p2, 0,
                     __ATOMIC_RELEASE);
  const uint32_t owner = __atomic_load_n(&native_lab_gauge_owner_pad,
                                         __ATOMIC_ACQUIRE);
  if (owner == pad + 1u) {
    const uint32_t active = __atomic_load_n(&native_lab_gauge_active_mask,
                                            __ATOMIC_ACQUIRE) & 3u;
    if (active & (1u << (pad ^ 1u))) {
      const uint32_t other = pad ^ 1u;
      __atomic_store_n(&native_lab_gauge_owner_pad, other + 1u,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_gauge_power_milli,
                       __atomic_load_n(&native_lab_gauge_power_milli_by_pad[
                                           other], __ATOMIC_ACQUIRE),
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_gauge_linger_frames,
                       __atomic_load_n(&native_lab_gauge_linger_frames_by_pad[
                                           other], __ATOMIC_ACQUIRE),
                       __ATOMIC_RELEASE);
    } else {
      __atomic_store_n(&native_lab_gauge_owner_pad, 0, __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_gauge_linger_frames, 0,
                       __ATOMIC_RELEASE);
    }
  }
}

static void native_lab_gauge_observe_released_ball(
    uint32_t pad, float ball_x, float ball_y, float ball_z, float player_x,
    float player_y, float player_z) {
  if (pad > 1)
    return;
  const uint32_t pad_bit = 1u << pad;
  if (!(__atomic_load_n(&native_lab_gauge_active_mask, __ATOMIC_ACQUIRE) &
        pad_bit) ||
      (__atomic_load_n(&native_lab_gauge_charging_mask, __ATOMIC_ACQUIRE) &
       pad_bit))
    return;

  const float sample[3] = {ball_x, ball_y, ball_z};
  uint32_t sample_bits[3];
  memcpy(sample_bits, sample, sizeof(sample_bits));
  const float player_dx = ball_x - player_x;
  const float player_dy = ball_y - player_y;
  const float player_dz = ball_z - player_z;
  const float player_distance_sq =
      player_dx * player_dx + player_dy * player_dy +
      player_dz * player_dz;
  if (!(__atomic_load_n(&native_lab_gauge_release_ball_valid_mask,
                        __ATOMIC_ACQUIRE) & pad_bit)) {
    for (uint32_t axis = 0; axis < 3; ++axis)
      __atomic_store_n(&native_lab_gauge_release_ball_bits[pad][axis],
                       sample_bits[axis], __ATOMIC_RELEASE);
    uint32_t distance_bits;
    memcpy(&distance_bits, &player_distance_sq, sizeof(distance_bits));
    __atomic_store_n(&native_lab_gauge_release_min_distance_bits[pad],
                     distance_bits, __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_gauge_completion_frames[pad], 0,
                     __ATOMIC_RELEASE);
    __atomic_fetch_or(&native_lab_gauge_release_ball_valid_mask, pad_bit,
                      __ATOMIC_ACQ_REL);
    return;
  }

  float origin[3];
  for (uint32_t axis = 0; axis < 3; ++axis) {
    const uint32_t bits = __atomic_load_n(
        &native_lab_gauge_release_ball_bits[pad][axis], __ATOMIC_ACQUIRE);
    memcpy(&origin[axis], &bits, sizeof(bits));
  }
  uint32_t min_distance_bits = __atomic_load_n(
      &native_lab_gauge_release_min_distance_bits[pad], __ATOMIC_ACQUIRE);
  float min_distance_sq;
  memcpy(&min_distance_sq, &min_distance_bits, sizeof(min_distance_sq));
  if (min_distance_sq != min_distance_sq ||
      player_distance_sq < min_distance_sq) {
    min_distance_sq = player_distance_sq;
    memcpy(&min_distance_bits, &min_distance_sq, sizeof(min_distance_bits));
    __atomic_store_n(&native_lab_gauge_release_min_distance_bits[pad],
                     min_distance_bits, __ATOMIC_RELEASE);
  }

  const float dx = ball_x - origin[0];
  const float dy = ball_y - origin[1];
  const float dz = ball_z - origin[2];
  const int ball_moved = dx * dx + dy * dy + dz * dz >= 0.1225f;
  // A 0.70-unit increase from the closest observed foot/ball separation keeps
  // the bar through the run-up and contact animation. Three consecutive
  // samples reject one-frame projection/registry jitter, then completion
  // follows the kicked ball rather than button release.
  const int ball_separated =
      player_distance_sq >= min_distance_sq + 0.49f;
  if (ball_moved && ball_separated) {
    const uint32_t completion_frames = __atomic_add_fetch(
        &native_lab_gauge_completion_frames[pad], 1u, __ATOMIC_ACQ_REL);
    if (completion_frames >= 3u)
      native_lab_gauge_clear_pad(pad);
  } else {
    __atomic_store_n(&native_lab_gauge_completion_frames[pad], 0,
                     __ATOMIC_RELEASE);
  }
}

static void native_lab_gauge_clear_all(void) {
  native_lab_gauge_clear_pad(0);
  native_lab_gauge_clear_pad(1);
  __atomic_store_n(&native_lab_gauge_owner_pad, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_power_milli, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_power_milli_p2, 0,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_gauge_linger_frames, 0,
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
  const uint32_t previous_buttons = __atomic_exchange_n(
      &native_lab_previous_buttons[port], connected ? buttons : 0,
      __ATOMIC_ACQ_REL);
  uint32_t anchor_ttl = __atomic_load_n(
      &native_lab_gauge_anchor_ttl[port], __ATOMIC_ACQUIRE);
  if (anchor_ttl)
    __atomic_fetch_sub(&native_lab_gauge_anchor_ttl[port], 1u,
                       __ATOMIC_ACQ_REL);
  // Keep each pad's last charge visible until BallInfo confirms that the kick
  // happened. This three-second counter is only a safety net for cancelled
  // actions, camera cuts, and match teardown; release itself never clears.
  if (port < 2 && (__atomic_load_n(&native_lab_gauge_active_mask,
                                   __ATOMIC_ACQUIRE) & (1u << port))) {
    uint32_t linger = __atomic_load_n(
        &native_lab_gauge_linger_frames_by_pad[port], __ATOMIC_ACQUIRE);
    if (linger)
      __atomic_fetch_sub(&native_lab_gauge_linger_frames_by_pad[port], 1u,
                         __ATOMIC_ACQ_REL);
    else if (!(__atomic_load_n(&native_lab_gauge_charging_mask,
                               __ATOMIC_ACQUIRE) & (1u << port)))
      native_lab_gauge_clear_pad(port);
    if (__atomic_load_n(&native_lab_gauge_owner_pad, __ATOMIC_ACQUIRE) ==
        port + 1u) {
      __atomic_store_n(&native_lab_gauge_linger_frames, linger,
                       __ATOMIC_RELEASE);
    }
  }
  // ButtonSetplay's surface snapshot can briefly report NONE while its
  // native ThinkUnitList is still active. Keep the last native context for a
  // short, input-thread-paced grace period so the helper never falls back to
  // the exhibition ZR/X/Y legend during that handoff.
  uint32_t setplay_linger = __atomic_load_n(
      &native_lab_setplay_linger_frames, __ATOMIC_ACQUIRE);
  if (setplay_linger) {
    if (__atomic_fetch_sub(&native_lab_setplay_linger_frames, 1u,
                           __ATOMIC_ACQ_REL) == 1u) {
      const uint32_t published = __atomic_load_n(
          &native_lab_published_setplay_context, __ATOMIC_ACQUIRE);
      if (published == PES_SETPLAY_NONE) {
        __atomic_store_n(&native_lab_debug_context, PES_SETPLAY_NONE,
                         __ATOMIC_RELEASE);
        __atomic_store_n(&native_lab_debug_stock_mask, 0,
                         __ATOMIC_RELEASE);
        __atomic_store_n(&native_lab_debug_route_mask, 0,
                         __ATOMIC_RELEASE);
        __atomic_store_n(&native_lab_active_action[0], 0, __ATOMIC_RELEASE);
        __atomic_store_n(&native_lab_active_action[1], 0, __ATOMIC_RELEASE);
        __atomic_store_n(&native_lab_pending_kick_pad, 0,
                         __ATOMIC_RELEASE);
        __atomic_store_n(&native_lab_pending_kick_command, 0,
                         __ATOMIC_RELEASE);
        __atomic_store_n(&native_lab_pending_kick_action, 0,
                         __ATOMIC_RELEASE);
        __atomic_store_n(&native_lab_pending_kick_power_bits, 0,
                         __ATOMIC_RELEASE);
        native_lab_clear_free_kick_elevation();
        native_lab_gauge_clear_all();
      }
    }
  }
  if (connected)
    __atomic_fetch_or(&native_lab_debug_connected_mask, 1u << port,
                      __ATOMIC_RELAXED);
  else
    __atomic_fetch_and(&native_lab_debug_connected_mask, ~(1u << port),
                       __ATOMIC_RELAXED);
  // R toggles the real stock pass/cross trajectory only for the pad that owns
  // the current set play. This is a visual aid; it never changes PadCommand.
  const uint32_t setplay_pad = __atomic_load_n(
      &native_lab_debug_setplay_pad, __ATOMIC_ACQUIRE);
  const uint32_t context = __atomic_load_n(
      &native_lab_debug_context, __ATOMIC_ACQUIRE);
  const uint32_t trajectory_stock_mask = __atomic_load_n(
      &native_lab_debug_stock_mask, __ATOMIC_ACQUIRE);
  const int trajectory_context =
      context == PES_SETPLAY_GOAL_KICK || context == PES_SETPLAY_CORNER ||
      (context == PES_SETPLAY_FREE_KICK &&
       !(trajectory_stock_mask &
         (PES_NATIVE_LAB_STOCK_FREEKICK_TACTICS |
          PES_NATIVE_LAB_STOCK_FREEKICK_POSITION)));
  if (connected && port == setplay_pad && (buttons & (1u << 7)) &&
      !(previous_buttons & (1u << 7)) &&
#ifndef NATIVE_PAD_LAB_HOST_TEST
      pes_controller_penalty_role_for_pad(port) == PES_PENALTY_NONE &&
#endif
      trajectory_context)
    __atomic_fetch_xor(&native_lab_trajectory_enabled, 1u,
                       __ATOMIC_ACQ_REL);
  // Sample elevation directly from the set-play owner's physical LS. This
  // path runs at HID cadence and therefore remains responsive even when the
  // mobile kick ThinkUnit is idle. Neutral does not overwrite the value: the
  // selected height stays frozen through the wind-up and is cleared only on
  // a real context transition/completion.
  const uint32_t active_action = __atomic_load_n(
      &native_lab_active_action[port], __ATOMIC_ACQUIRE);
  if (connected && port == setplay_pad && trajectory_context &&
      !active_action) {
    const float left_y = native_lab_normalize_axis(axis_y);
    if (left_y != 0.0f) {
      const float vertical =
          -left_y * NATIVE_LAB_TRAJECTORY_MAX_ELEVATION_DEGREES;
      uint32_t vertical_bits = 0;
      memcpy(&vertical_bits, &vertical, sizeof(vertical_bits));
      __atomic_store_n(&native_lab_command_vertical_bits[port],
                       vertical_bits, __ATOMIC_RELEASE);
      __atomic_fetch_or(&native_lab_left_aim_latched_mask, 1u << port,
                        __ATOMIC_ACQ_REL);
    }
  }
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

void pes_controller_native_pad_lab_publish_setplay_context(uint32_t context) {
  if (context > PES_SETPLAY_THROW_IN)
    context = PES_SETPLAY_NONE;
  const uint32_t previous = __atomic_exchange_n(
      &native_lab_published_setplay_context, context, __ATOMIC_ACQ_REL);
  if (context != previous) {
    // A new set-play must never inherit the previous action's frozen spline.
    // Do not clear on the first transient NONE sample: ButtonSetplay can emit
    // it during a live run-up, and the existing linger/gauge completion paths
    // will clear the cache once the action has genuinely ended.
    if (context != PES_SETPLAY_NONE)
      native_lab_clear_trajectory_cache_all();
    native_lab_clear_free_kick_elevation();
    const uint32_t show_trajectory =
        context == PES_SETPLAY_GOAL_KICK ||
        context == PES_SETPLAY_CORNER ||
        context == PES_SETPLAY_FREE_KICK;
    __atomic_store_n(&native_lab_trajectory_enabled, show_trajectory,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_command_angle_valid_mask, 0,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_left_aim_latched_mask, 0,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_command_vertical_bits[0], 0,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_command_vertical_bits[1], 0,
                     __ATOMIC_RELEASE);
  }
  if (context == PES_SETPLAY_NONE) {
    const uint32_t previous_debug_context = __atomic_load_n(
        &native_lab_debug_context, __ATOMIC_ACQUIRE);
    // NONE is published every normal-gameplay frame. Do not clear a regular
    // shot/cross gauge or a still-live native set-play helper there. The
    // context linger expires in debug_input once the native list stops
    // refreshing it; an explicit context change still clears all action state.
    const uint32_t existing_linger = __atomic_load_n(
        &native_lab_setplay_linger_frames, __ATOMIC_ACQUIRE);
    if (previous != PES_SETPLAY_NONE ||
        (previous_debug_context != PES_SETPLAY_NONE && !existing_linger)) {
      __atomic_store_n(&native_lab_setplay_linger_frames, 60,
                       __ATOMIC_RELEASE);
    }
  }
}

uint32_t pes_controller_native_pad_lab_setplay_context(void) {
  return __atomic_load_n(&native_lab_debug_context, __ATOMIC_ACQUIRE);
}

int pes_controller_native_pad_lab_trajectory_enabled(void) {
  if (!pes_controller_native_pad_lab_active())
    return 0;
  const uint32_t context = __atomic_load_n(&native_lab_debug_context,
                                           __ATOMIC_ACQUIRE);
  if (context != PES_SETPLAY_GOAL_KICK &&
      context != PES_SETPLAY_CORNER &&
      context != PES_SETPLAY_FREE_KICK)
    return 0;
  if (context == PES_SETPLAY_FREE_KICK &&
      (__atomic_load_n(&native_lab_debug_stock_mask, __ATOMIC_ACQUIRE) &
       (PES_NATIVE_LAB_STOCK_FREEKICK_TACTICS |
        PES_NATIVE_LAB_STOCK_FREEKICK_POSITION)))
    return 0;
  return __atomic_load_n(&native_lab_trajectory_enabled,
                         __ATOMIC_ACQUIRE) != 0;
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
  snapshot->trajectory_enabled =
      pes_controller_native_pad_lab_trajectory_enabled();
  snapshot->gauge_owner_pad = __atomic_load_n(
      &native_lab_gauge_owner_pad, __ATOMIC_ACQUIRE);
  snapshot->gauge_power_milli = __atomic_load_n(
      &native_lab_gauge_power_milli_by_pad[0], __ATOMIC_ACQUIRE);
  snapshot->gauge_active_mask = __atomic_load_n(
      &native_lab_gauge_active_mask, __ATOMIC_ACQUIRE);
  snapshot->gauge_power_milli_p2 = __atomic_load_n(
      &native_lab_gauge_power_milli_by_pad[1], __ATOMIC_ACQUIRE);
  const uint32_t gauge_mask = snapshot->gauge_active_mask & 3u;
  uint32_t anchor_mask = 0;
  for (uint32_t pad = 0; pad < 2; ++pad) {
    if ((gauge_mask & (1u << pad)) &&
        __atomic_load_n(&native_lab_gauge_anchor_ttl[pad],
                        __ATOMIC_ACQUIRE))
      anchor_mask |= 1u << pad;
  }
  snapshot->gauge_anchor_valid_mask = anchor_mask;
  snapshot->gauge_anchor_x_milli = __atomic_load_n(
      &native_lab_gauge_anchor_x_milli[0], __ATOMIC_ACQUIRE);
  snapshot->gauge_anchor_y_milli = __atomic_load_n(
      &native_lab_gauge_anchor_y_milli[0], __ATOMIC_ACQUIRE);
  snapshot->gauge_anchor_x_milli_p2 = __atomic_load_n(
      &native_lab_gauge_anchor_x_milli[1], __ATOMIC_ACQUIRE);
  snapshot->gauge_anchor_y_milli_p2 = __atomic_load_n(
      &native_lab_gauge_anchor_y_milli[1], __ATOMIC_ACQUIRE);
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

static uint32_t native_lab_gauge_release_linger(void) {
  uint32_t gauge_context = __atomic_load_n(
      &native_lab_debug_context, __ATOMIC_ACQUIRE);
  if (gauge_context == PES_SETPLAY_NONE)
    gauge_context = __atomic_load_n(&native_lab_published_setplay_context,
                                    __ATOMIC_ACQUIRE);
  return gauge_context == PES_SETPLAY_GOAL_KICK ||
                 gauge_context == PES_SETPLAY_CORNER ||
                 gauge_context == PES_SETPLAY_FREE_KICK
             ? 900u
             : 180u;
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
  if (!pes_controller_native_pad_lab_active())
    return;
  const uint32_t pad = native_lab_input_pad(input);
  const uint32_t pad_bit = 1u << pad;
  if (event == PES_NATIVE_LAB_EVENT_SHORT_PRESS ||
      event == PES_NATIVE_LAB_EVENT_LONG_PRESS ||
      event == PES_NATIVE_LAB_EVENT_SHOOT_PRESS) {
    // Freeze the last idle preview for this action. Do not clear/rebuild the
    // cache here: by the first post-press 2D update the stock engine may have
    // already rotated the model and raised its spline for the run-up.
    if (!(__atomic_load_n(&native_lab_trajectory_freeze_mask,
                          __ATOMIC_ACQUIRE) & pad_bit)) {
      __atomic_fetch_or(&native_lab_trajectory_freeze_mask, pad_bit,
                        __ATOMIC_ACQ_REL);
    }
    __atomic_fetch_or(&native_lab_gauge_active_mask, pad_bit,
                      __ATOMIC_ACQ_REL);
    __atomic_fetch_or(&native_lab_gauge_charging_mask, pad_bit,
                      __ATOMIC_ACQ_REL);
    __atomic_store_n(&native_lab_gauge_power_milli_by_pad[pad], 0,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_gauge_linger_frames_by_pad[pad], 0,
                     __ATOMIC_RELEASE);
    uint32_t player_no = UINT32_MAX;
    if (input)
      memcpy(&player_no, (const char *)input + 0x24,
             sizeof(player_no));
    if (player_no > 21u)
      player_no = UINT32_MAX;
    __atomic_store_n(&native_lab_gauge_player_no_by_pad[pad], player_no,
                     __ATOMIC_RELEASE);
    __atomic_fetch_and(&native_lab_gauge_release_ball_valid_mask, ~pad_bit,
                       __ATOMIC_ACQ_REL);
    __atomic_store_n(&native_lab_gauge_release_min_distance_bits[pad], 0,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_gauge_completion_frames[pad], 0,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_gauge_owner_pad, pad + 1u,
                     __ATOMIC_RELEASE);
    if (pad == 0)
      __atomic_store_n(&native_lab_gauge_power_milli, 0,
                       __ATOMIC_RELEASE);
    else
      __atomic_store_n(&native_lab_gauge_power_milli_p2, 0,
                       __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_gauge_linger_frames, 0,
                     __ATOMIC_RELEASE);
  } else if (event == PES_NATIVE_LAB_EVENT_SHORT_RELEASE ||
             event == PES_NATIVE_LAB_EVENT_LONG_RELEASE ||
             event == PES_NATIVE_LAB_EVENT_SHOOT_RELEASE) {
    __atomic_fetch_or(&native_lab_gauge_active_mask, pad_bit,
                      __ATOMIC_ACQ_REL);
    __atomic_fetch_and(&native_lab_gauge_charging_mask, ~pad_bit,
                       __ATOMIC_ACQ_REL);
    // Far free-kick takers can have a run-up longer than the ordinary
    // three-second cancellation guard. BallInfo remains the primary completion
    // signal; this longer set-play-only fallback cannot cut the bar before
    // contact, while ordinary gameplay retains the tested 180-frame lifetime.
    const uint32_t release_linger = native_lab_gauge_release_linger();
    uint32_t expected = pad + 1u;
    if (__atomic_load_n(&native_lab_gauge_owner_pad, __ATOMIC_ACQUIRE) ==
        expected)
      __atomic_store_n(&native_lab_gauge_linger_frames, release_linger,
                       __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_gauge_linger_frames_by_pad[pad],
                     release_linger,
                     __ATOMIC_RELEASE);
    __atomic_fetch_and(&native_lab_gauge_release_ball_valid_mask, ~pad_bit,
                       __ATOMIC_ACQ_REL);
    __atomic_store_n(&native_lab_gauge_release_min_distance_bits[pad], 0,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_gauge_completion_frames[pad], 0,
                     __ATOMIC_RELEASE);
  }
  if (__atomic_load_n(&native_lab_debug_context, __ATOMIC_ACQUIRE) ==
      PES_SETPLAY_NONE)
    return;
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
  // Set-play may sample ahead of Cobra's mobile update. Prime either local
  // port immediately before the genuine PadInputUnit consumes it; KeyConfig,
  // press/release history, and stick conversion all remain stock.
  if (pad_no <= 1 && pes_controller_native_pad_lab_active() &&
      (pad_no == 0 || pes_controller_native_pad_lab_two_player()) &&
      cobra_pad_prime_native_port(pad_no))
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

static const NativeLabUnit *native_lab_optional_penalty_unit(uint32_t kind) {
  for (unsigned i = 0;
       i < sizeof(native_lab_optional_penalty_units) /
               sizeof(native_lab_optional_penalty_units[0]);
       ++i) {
    if (native_lab_optional_penalty_units[i].kind == kind)
      return &native_lab_optional_penalty_units[i];
  }
  return NULL;
}

static int native_lab_optional_penalty_matches(const void *list,
                                               uint32_t kind) {
  const NativeLabUnit *expected = native_lab_optional_penalty_unit(kind);
  if (!list || !expected || !expected->vptr)
    return 0;
  const void *unit = *(void *const *)((const char *)list + 0x3bf8 +
                                     kind * sizeof(uintptr_t));
  return unit && *(const uintptr_t *)unit == expected->vptr;
}

static int native_lab_penalty_suite_matches(const void *list,
                                            uint32_t role) {
  if (!native_lab_optional_penalty_matches(
          list, NATIVE_LAB_KIND_PENALTY_GUIDE))
    return 0;
  if (role == PES_PENALTY_KICKER)
    return native_lab_optional_penalty_matches(
        list, NATIVE_LAB_KIND_PENALTY_KICK);
  if (role == PES_PENALTY_GOALKEEPER)
    return native_lab_optional_penalty_matches(
               list, NATIVE_LAB_KIND_KEEPER_PENALTY_MOVE) &&
           native_lab_optional_penalty_matches(
               list, NATIVE_LAB_KIND_KEEPER_PENALTY_ACTION) &&
           native_lab_optional_penalty_matches(
               list, NATIVE_LAB_KIND_KEEPER_PENALTY_LAYER);
  return 0;
}

int pes_controller_native_penalty_ready(uint32_t pad, uint32_t role) {
  if (pad > 1u)
    return 0;
  const uint32_t role_bit = role == PES_PENALTY_KICKER
                                ? NATIVE_LAB_PENALTY_READY_KICKER
                                : role == PES_PENALTY_GOALKEEPER
                                      ? NATIVE_LAB_PENALTY_READY_KEEPER
                                      : 0u;
  if (!role_bit)
    return 0;
  const uint32_t mask = __atomic_load_n(
      &native_lab_penalty_ready_role_mask, __ATOMIC_ACQUIRE);
  return (mask & (role_bit << (pad * 2u))) != 0;
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
  uint32_t published = __atomic_load_n(
      &native_lab_published_setplay_context, __ATOMIC_ACQUIRE);
#ifndef NATIVE_PAD_LAB_HOST_TEST
  if (published == PES_SETPLAY_NONE)
    published = pes_controller_setplay_context();
#endif
  const int has_setplay_unit =
      native_lab_has_kind(entries, count, 62) ||
      native_lab_has_kind(entries, count, 64) ||
      native_lab_has_kind(entries, count, 65) ||
      native_lab_has_kind(entries, count, 70) ||
      native_lab_has_kind(entries, count, 72) ||
      native_lab_has_kind(entries, count, 75) ||
      native_lab_has_kind(entries, count, 90);
  // A semantic ButtonSetplay snapshot can lead/lag the native list by a
  // frame, but it must never turn an ordinary gameplay list into a set-piece.
  // Only apply the short context grace when a real set-play unit is present.
  if (has_setplay_unit && published == PES_SETPLAY_NONE &&
      __atomic_load_n(&native_lab_setplay_linger_frames, __ATOMIC_ACQUIRE))
    published = __atomic_load_n(&native_lab_debug_context, __ATOMIC_ACQUIRE);
  if (!native_lab_has_kind(entries, count, 90)) {
    // Throw-ins use their own native body-angle unit and do not always carry
    // MobileSetplayKick in the reduced mobile list.
    if (published == PES_SETPLAY_THROW_IN &&
        native_lab_has_kind(entries, count, 62))
      return PES_SETPLAY_THROW_IN;
    return (published != PES_SETPLAY_NONE && has_setplay_unit)
               ? published
               : PES_SETPLAY_NONE;
  }
  if (native_lab_has_kind(entries, count, 64))
    return PES_SETPLAY_GOAL_KICK;
  if (native_lab_has_kind(entries, count, 65) ||
      native_lab_has_kind(entries, count, 70))
    return PES_SETPLAY_CORNER;
  if (native_lab_has_kind(entries, count, 72) ||
      native_lab_has_kind(entries, count, 75))
    return PES_SETPLAY_FREE_KICK;
  // Close-range free kicks use a reduced list without tactics/position-change
  // markers on this mobile build. ButtonSetplay still publishes the semantic
  // context, so use it only as a fallback while MobileSetplayKick is present.
  if (published == PES_SETPLAY_GOAL_KICK ||
      published == PES_SETPLAY_CORNER ||
      published == PES_SETPLAY_FREE_KICK ||
      published == PES_SETPLAY_THROW_IN)
    return published;
  return PES_SETPLAY_NONE;
}

static void native_lab_list_update(void *list, const void *input,
                                   uint32_t previous, uint32_t context) {
  NativeLabInputBinding binding;
  const int local_input = list && native_lab_bind_input(input, &binding);
  if (local_input && native_lab_layout_matches(list)) {
    static const uint32_t action_kinds[NATIVE_LAB_ACTION_COUNT] = {
        0, 1, 3, 26};
    for (uint32_t action = 0; action < NATIVE_LAB_ACTION_COUNT; ++action) {
      const uintptr_t unit = *(const uintptr_t *)((const char *)list +
          0x3bf8 + action_kinds[action] * sizeof(uintptr_t));
      __atomic_store_n(&native_lab_action_units[binding.pad][action], unit,
                       __ATOMIC_RELEASE);
    }
    const uintptr_t penalty_action = native_lab_optional_penalty_matches(
            list, NATIVE_LAB_KIND_PENALTY_KICK)
        ? *(const uintptr_t *)((const char *)list + 0x3bf8 +
                              NATIVE_LAB_KIND_PENALTY_KICK *
                                  sizeof(uintptr_t))
        : 0;
    __atomic_store_n(&native_lab_penalty_action_units[binding.pad],
                     penalty_action, __ATOMIC_RELEASE);
  }
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
  const int native_penalty_kicker =
      native_lab_has_kind(stock + 1, stock[0], 91);
  const int native_penalty_goalkeeper =
      native_lab_has_kind(stock + 1, stock[0], 92) ||
      native_lab_has_kind(stock + 1, stock[0], 93);
#ifndef NATIVE_PAD_LAB_HOST_TEST
  // ThinkUnitList is the only callback that remains pad-owned throughout the
  // penalty idle/aim transition.  Publish from its already-bound local pad so
  // both P1 and P2 retain the correct kicker/keeper role between animations.
  if (route_pad == 0 || route_pad == 1) {
    // Some shootout templates carry both mobile penalty units in the same
    // local list. Presence alone is then ambiguous; let the exact Main
    // callback heartbeat classify the active role instead of making both pads
    // look like kickers (the failure mode where P2 keeper LS shot with P1).
    const int penalty_role_count = native_penalty_kicker +
                                   (native_penalty_goalkeeper ? 1 : 0);
    if (penalty_role_count == 1 && native_penalty_kicker)
      match_native_penalty_publish_for_pad(PES_PENALTY_KICKER,
                                           (uint32_t)route_pad);
    else if (penalty_role_count == 1 && native_penalty_goalkeeper)
      match_native_penalty_publish_for_pad(PES_PENALTY_GOALKEEPER,
                                           (uint32_t)route_pad);
  }
#endif
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
  const int route_setplay_guide =
      native_setplay && setplay_context != PES_SETPLAY_THROW_IN;
  const int route_throwin_aim =
      setplay_context == PES_SETPLAY_THROW_IN &&
      native_lab_has_kind(stock + 1, stock[0], 90);
  for (uint32_t i = 0; i < stock[0]; i++) {
    uint32_t kind = stock[1+i];
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
    // Normalize an existing native guide too; different set-play variants can
    // supply it in different positions. It is appended after kind 90 below.
    if ((route_setplay_guide && kind == 26) ||
        (route_throwin_aim && kind == 62)) {
      changed++;
      continue;
    }
    if (!native_lab_append(entries, &count, kind))
      return; // Transactional: no partial rewrite on invalid/oversized data.
    // Directional units run after MobileSetplayKick. A non-zero guide command
    // before kind 90 prevented its Pull/Release command from ever executing,
    // leaving A/B charging forever. The guide still publishes native LS aim
    // on idle frames, while a kick release always has first priority.
    if (kind == 90) {
      if (route_setplay_guide) {
        if (!native_lab_append(entries, &count, 26))
          return;
        changed++;
      } else if (route_throwin_aim) {
        if (!native_lab_append(entries, &count, 62))
          return;
        changed++;
      }
    }
  }
  // Keep the mobile penalty units for lifecycle/Update2D.  Append dormant
  // console actions only after their exact per-object vptrs match.  This is a
  // local, non-fatal ABI gate: a future mobile layout can fall back to touch
  // for penalties without turning normal P1/P2 gameplay into ABI ERROR.
  const int native_penalty_kicker_ready =
      native_penalty_kicker &&
      native_lab_penalty_suite_matches(list, PES_PENALTY_KICKER);
  const int native_penalty_goalkeeper_ready =
      native_penalty_goalkeeper &&
      native_lab_penalty_suite_matches(list, PES_PENALTY_GOALKEEPER);
  if (native_penalty_kicker_ready) {
    if (!native_lab_append(entries, &count,
                           NATIVE_LAB_KIND_PENALTY_GUIDE) ||
        !native_lab_append(entries, &count,
                           NATIVE_LAB_KIND_PENALTY_KICK))
      return;
    if (route_pad == 0 || route_pad == 1)
      __atomic_fetch_or(&native_lab_penalty_ready_role_mask,
                        NATIVE_LAB_PENALTY_READY_KICKER <<
                            ((uint32_t)route_pad * 2u),
                        __ATOMIC_ACQ_REL);
    changed++;
  }
  if (native_penalty_goalkeeper_ready) {
    if (!native_lab_append(entries, &count,
                           NATIVE_LAB_KIND_KEEPER_PENALTY_MOVE) ||
        !native_lab_append(entries, &count,
                           NATIVE_LAB_KIND_KEEPER_PENALTY_ACTION) ||
        !native_lab_append(entries, &count,
                           NATIVE_LAB_KIND_KEEPER_PENALTY_LAYER))
      return;
    if (route_pad == 0 || route_pad == 1)
      __atomic_fetch_or(&native_lab_penalty_ready_role_mask,
                        NATIVE_LAB_PENALTY_READY_KEEPER <<
                            ((uint32_t)route_pad * 2u),
                        __ATOMIC_ACQ_REL);
    changed++;
  }
  if (changed) {
    memcpy(stock + 1, entries, count * sizeof(entries[0]));
    stock[0] = count;
    __atomic_fetch_or(&native_lab_status, 8u, __ATOMIC_RELAXED);
  }
  if (native_setplay) {
    uint32_t route_mask = PES_NATIVE_LAB_ROUTE_MOBILE_KICK_BRIDGE |
                          PES_NATIVE_LAB_ROUTE_SHORT_PASS |
                          PES_NATIVE_LAB_ROUTE_LONG_PASS |
                          PES_NATIVE_LAB_ROUTE_SHOOT |
                          PES_NATIVE_LAB_ROUTE_CAMERA_STICK;
    if (setplay_context == PES_SETPLAY_THROW_IN)
      route_mask |= PES_NATIVE_LAB_ROUTE_THROWIN_AIM;
    else
      route_mask |= PES_NATIVE_LAB_ROUTE_SETPLAY_GUIDE;
    if (setplay_context == PES_SETPLAY_GOAL_KICK)
      route_mask |= PES_NATIVE_LAB_ROUTE_GOALKICK_SUPPORT;
    else if (setplay_context == PES_SETPLAY_CORNER)
      route_mask |= PES_NATIVE_LAB_ROUTE_CORNER_TACTICS;
    else if (setplay_context == PES_SETPLAY_FREE_KICK)
      route_mask |= PES_NATIVE_LAB_ROUTE_FREEKICK_TACTICS;
    const uint32_t previous_context = __atomic_exchange_n(
        &native_lab_debug_context, setplay_context, __ATOMIC_ACQ_REL);
    __atomic_store_n(&native_lab_setplay_linger_frames, 60,
                     __ATOMIC_RELEASE);
    if (previous_context != setplay_context) {
      native_lab_clear_free_kick_elevation();
      native_lab_gauge_clear_all();
      __atomic_store_n(&native_lab_trajectory_enabled, 1,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_command_angle_valid_mask, 0,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_left_aim_latched_mask, 0,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_command_vertical_bits[0], 0,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_command_vertical_bits[1], 0,
                       __ATOMIC_RELEASE);
    }
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
  } else if (route_pad == 0 || route_pad == 1) {
    // In 2P, the attacking set-play list and the defending ordinary list are
    // updated independently. Only the pad that owns the current set play may
    // tear it down; otherwise the defender clears the attacker's context each
    // frame, restores the old ZR/X/Y touch legend, and resets a charging gauge.
    // Once the owner's own list returns to ordinary gameplay, clear the
    // helper/trajectory/action state immediately so it cannot linger.
    __atomic_store_n(&native_lab_active_action[route_pad], 0,
                     __ATOMIC_RELEASE);
    const uint32_t previous_context = __atomic_load_n(
        &native_lab_debug_context, __ATOMIC_ACQUIRE);
    const uint32_t setplay_pad = __atomic_load_n(
        &native_lab_debug_setplay_pad, __ATOMIC_ACQUIRE);
    if (previous_context != PES_SETPLAY_NONE &&
        setplay_pad == (uint32_t)route_pad) {
      __atomic_store_n(&native_lab_debug_context, PES_SETPLAY_NONE,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_debug_stock_mask, 0, __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_debug_route_mask, 0, __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_debug_setplay_pad, UINT32_MAX,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_trajectory_enabled, 0,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_setplay_linger_frames, 0,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_command_angle_valid_mask, 0,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_left_aim_latched_mask, 0,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_pending_kick_pad, 0, __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_pending_kick_command, 0,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_pending_kick_action, 0,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_pending_kick_power_bits, 0,
                       __ATOMIC_RELEASE);
      native_lab_clear_free_kick_elevation();
      __atomic_store_n(&native_lab_gauge_owner_pad, 0,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_gauge_power_milli, 0,
                       __ATOMIC_RELEASE);
      __atomic_store_n(&native_lab_gauge_linger_frames, 0,
                       __ATOMIC_RELEASE);
    }
  }
}

static float native_lab_stable_setplay_base_angle(uint32_t pad,
                                                   uint32_t player,
                                                   float stock_angle,
                                                   int *same_target_out) {
  const uint32_t valid = __atomic_load_n(
      &native_lab_command_angle_valid_mask, __ATOMIC_ACQUIRE);
  const uint32_t base_player = __atomic_load_n(
      &native_lab_base_angle_player[pad], __ATOMIC_ACQUIRE);
  const int same_target = (valid & (1u << pad)) && base_player == player;
  float base_angle = stock_angle;
  if (same_target) {
    const uint32_t base_bits = __atomic_load_n(
        &native_lab_base_angle_bits[pad], __ATOMIC_ACQUIRE);
    memcpy(&base_angle, &base_bits, sizeof(base_angle));
  } else {
    uint32_t base_bits = 0;
    memcpy(&base_bits, &stock_angle, sizeof(base_bits));
    __atomic_store_n(&native_lab_base_angle_bits[pad], base_bits,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_base_angle_player[pad], player,
                     __ATOMIC_RELEASE);
    // A changed taker starts from its own stock direction and height.
    __atomic_fetch_and(&native_lab_left_aim_latched_mask, ~(1u << pad),
                       __ATOMIC_ACQ_REL);
    __atomic_store_n(&native_lab_command_vertical_bits[pad], 0,
                     __ATOMIC_RELEASE);
  }
  if (same_target_out)
    *same_target_out = same_target;
  return base_angle;
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
static uint32_t (*native_lab_penalty_press_original)(void *, const void *);
static uint32_t (*native_lab_penalty_pull_original)(void *, const void *);
static uint32_t (*native_lab_support_pull_original)(void *, const void *);
static uint32_t (*native_lab_mobile_kick_main_original)(void *, const void *,
                                                        uint32_t);
// Reuse the owned mobile binary's boundary filter for corner aim after the
// physical LS has produced an angle; no gesture state is synthesized.
static float (*native_lab_mobile_filter_angle_abi)(void *, const void *, float);
static void (*native_lab_short_update_2d_original)(void *, const void *,
                                                   void *);
static void (*native_lab_long_update_2d_original)(void *, const void *,
                                                  void *);
static void (*native_lab_shoot_update_2d_original)(void *, const void *,
                                                   void *);
static void (*native_lab_mobile_kick_update_2d_original)(void *, const void *,
                                                         void *);
static void (*native_lab_penalty_update_2d_original)(void *, const void *,
                                                     void *);
static void (*native_lab_draw_pass_line)(uint32_t, uint32_t, uint32_t,
                                         uint32_t, float, const void *, void *);
static void (*native_lab_set_kick_original)(void *, uint32_t, float, float,
                                             float, uint32_t, float, float,
                                             uint32_t, uint32_t);
static void (*native_lab_set_kick_no_player_original)(
    void *, uint32_t, float, float, float, uint32_t, float, float,
    uint32_t);
// This is the last native stage before ActionBall receives its flight vector.
// PadCommand's final float is a horizontal auxiliary vector, so it cannot
// carry the LS-Y free-kick height.  The game computes the real vertical speed
// in GetBallInjectionSpeedAndRotation instead.
static void (*native_lab_ball_injection_original)(const void *, void *, void *);
static void (*native_lab_corner_camera_update_original)(void *, void *);
static void (*native_lab_goal_camera_update_original)(void *, void *);
static void (*native_lab_free_camera_update_original)(void *, void *);

static void native_lab_publish_setplay_trajectory(const void *input,
                                                   void *screen_2d);

static uint32_t native_lab_guide_main(void *unit, const void *input,
                                      uint32_t kind) {
  if (pes_controller_native_pad_lab_active() &&
      __atomic_load_n(&native_lab_debug_context, __ATOMIC_ACQUIRE) !=
          PES_SETPLAY_NONE) {
    // Stock SetplayGuide consumes LS and changes the mobile camera target.
    // Native lab owns aim through PadCommand instead, so do not execute the
    // guide at all while a native set play is active.
    (void)unit;
    (void)input;
    (void)kind;
    return 0;
  }
  return native_lab_guide_main_original
             ? native_lab_guide_main_original(unit, input, kind)
             : 0;
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
NATIVE_LAB_ACTION_WRAPPER(native_lab_penalty_press,
                          PES_NATIVE_LAB_EVENT_SHOOT_PRESS,
                          native_lab_penalty_press_original)
NATIVE_LAB_ACTION_WRAPPER(native_lab_penalty_pull,
                          PES_NATIVE_LAB_EVENT_SHOOT_RELEASE,
                          native_lab_penalty_pull_original)
NATIVE_LAB_ACTION_WRAPPER(native_lab_support_pull,
                          PES_NATIVE_LAB_EVENT_SUPPORT_RELEASE,
                          native_lab_support_pull_original)

#undef NATIVE_LAB_ACTION_WRAPPER

// Capture only the genuine native unit charge. The custom renderer consumes
// this state and never writes Screen2d trajectory/gauge data, so a later P1
// update cannot steal P2's gauge and this cannot affect the kick command.
static void native_lab_track_action_power(const void *power_unit,
                                          const void *input,
                                          void *screen_2d) {
  // native_lab_gauge_owner_pad remains the latest-action presentation owner;
  // per-pad state below is what prevents P2 from being projected onto P1.
  // Screen2dInfo +0x10b9 is only an output of MobileShoot::Update2DInfo.
  // Native Short/Long/Shoot Update2DInfo are no-op methods, so after the
  // mobile-to-native migration this byte is not a usable lifecycle source;
  // keep it hidden and use native power + BallInfo completion instead.
  if (screen_2d && pes_controller_native_pad_lab_active()) {
    const uint8_t hidden = 0;
    memcpy((char *)screen_2d + 0x10b9, &hidden, sizeof(hidden));
  }
  if (!power_unit || !input || !pes_controller_native_pad_lab_active())
    return;
  const uint32_t pad = native_lab_input_pad(input);
  if (!(__atomic_load_n(&native_lab_gauge_active_mask, __ATOMIC_ACQUIRE) &
        (1u << pad)))
    return;
  float power = 0.0f;
  memcpy(&power, (const char *)power_unit + 0x20, sizeof(power));
  if (!(power > 0.0f) &&
      __atomic_load_n(&native_lab_gauge_linger_frames_by_pad[pad],
                      __ATOMIC_ACQUIRE))
    return;
  if (!(power > 0.0f))
    power = 0.0f;
  if (power > 1.0f)
    power = 1.0f;
  const uint32_t power_milli = (uint32_t)(power * 1000.0f + 0.5f);
  __atomic_store_n(&native_lab_gauge_power_milli_by_pad[pad], power_milli,
                   __ATOMIC_RELEASE);
  if (pad == 0)
    __atomic_store_n(&native_lab_gauge_power_milli, power_milli,
                     __ATOMIC_RELEASE);
  else
    __atomic_store_n(&native_lab_gauge_power_milli_p2, power_milli,
                     __ATOMIC_RELEASE);
}

static void native_lab_publish_setplay_trajectory(const void *input,
                                                   void *screen_2d) {
  if (!input || !screen_2d || !native_lab_draw_pass_line ||
      !pes_controller_native_pad_lab_trajectory_enabled())
    return;
#ifndef NATIVE_PAD_LAB_HOST_TEST
  // Pause, Game Plan and other modal windows own the whole foreground. Do not
  // leave the in-match set-play spline visible behind those native screens.
  if (pes_controller_virtual_cursor_context() != PES_VIRTUAL_CURSOR_NONE)
    return;
#endif
  const uint32_t pad = native_lab_input_pad(input);
  const uint32_t owner = __atomic_load_n(&native_lab_debug_setplay_pad,
                                         __ATOMIC_ACQUIRE);
  const uint32_t valid = __atomic_load_n(
      &native_lab_command_angle_valid_mask, __ATOMIC_ACQUIRE);
  if (pad != owner || !(valid & (1u << pad)))
    return;
  const uint32_t pad_bit = 1u << pad;
  const uint32_t freeze_mask = __atomic_load_n(
      &native_lab_trajectory_freeze_mask, __ATOMIC_ACQUIRE);
  const int restore_frozen =
      (freeze_mask & pad_bit) &&
      (__atomic_load_n(&native_lab_trajectory_cache_valid_mask,
                       __ATOMIC_ACQUIRE) & pad_bit);
  uint32_t player = 0;
  memcpy(&player, (const char *)input + 0x24, sizeof(player));
  const void *registry = *(void *const *)input;
  if (!registry || player >= 22)
    return;
  float angle = 0.0f;
  const uint32_t angle_bits = __atomic_load_n(
      &native_lab_command_angle_bits[pad], __ATOMIC_ACQUIRE);
  memcpy(&angle, &angle_bits, sizeof(angle));
  uint32_t vertical_bits = __atomic_load_n(
      &native_lab_command_vertical_bits[pad], __ATOMIC_ACQUIRE);
  float vertical = 0.0f;
  memcpy(&vertical, &vertical_bits, sizeof(vertical));
  // Native LongPass produces the cross-style curved world trail. 0xff asks
  // DrawPassLine to derive the target from our angle instead of another player.
  // This is the stock white renderer used by the mobile set-piece preview.
  native_lab_draw_pass_line(0x50u, 0u, player, 0xffu, angle, registry,
                            screen_2d);
  if (restore_frozen &&
      native_lab_restore_trajectory_points(pad, screen_2d))
    return;

  // The 0xff angle-only path in DrawPassLine stops after roughly 15 metres.
  // Preserve its stock nine-point curve, but extend X/Z about the ball so the
  // preview reaches a useful set-piece target instead of ending at the wall.
  // Corner and close free kick need about one penalty-area depth; goal kick is
  // kept longer while it remains available as a diagnostic trajectory.
  const uint32_t context = __atomic_load_n(
      &native_lab_debug_context, __ATOMIC_ACQUIRE);
  const float target_distance = context == PES_SETPLAY_GOAL_KICK
                                    ? 42.0f
                                    : context == PES_SETPLAY_CORNER ? 34.0f
                                                                    : 30.0f;
  float start_x = 0.0f;
  float start_z = 0.0f;
  float end_x = 0.0f;
  float end_z = 0.0f;
  memcpy(&start_x, (char *)screen_2d + 0x10f0, sizeof(start_x));
  memcpy(&start_z, (char *)screen_2d + 0x10f8, sizeof(start_z));
  memcpy(&end_x, (char *)screen_2d + 0x1150, sizeof(end_x));
  memcpy(&end_z, (char *)screen_2d + 0x1158, sizeof(end_z));
  const float current_dx = end_x - start_x;
  const float current_dz = end_z - start_z;
  const float current_distance =
      sqrtf(current_dx * current_dx + current_dz * current_dz);
  if (isfinite(current_distance) && current_distance > 0.01f) {
    const float distance_scale = target_distance / current_distance;
    for (uint32_t index = 1; index < 9; ++index) {
      float x = 0.0f;
      float z = 0.0f;
      memcpy(&x, (char *)screen_2d + 0x10f0 + index * 12u, sizeof(x));
      memcpy(&z, (char *)screen_2d + 0x10f8 + index * 12u, sizeof(z));
      x = start_x + (x - start_x) * distance_scale;
      z = start_z + (z - start_z) * distance_scale;
      memcpy((char *)screen_2d + 0x10f0 + index * 12u, &x, sizeof(x));
      memcpy((char *)screen_2d + 0x10f8 + index * 12u, &z, sizeof(z));
    }
  }

  if (vertical != 0.0f) {
    // DrawPassLine has no elevation parameter, but it publishes the same nine
    // world-space spline points that the stock renderer consumes at +0x10f0.
    // Bend only the interior points with a sine envelope: the ball and endpoint
    // stay on the ground while LS-Y raises/lowers the white trajectory. This
    // preserves the native colour/material and avoids the cyan DrawShootLine
    // variant, whose command kind is intended for a different mobile action.
    // Mobile swipe elevation uses screen-space Y (up is negative), whereas the
    // white spline stores world-space Y (up is positive). Invert it here so a
    // physical LS-up raises both the native kick command and its preview.
    const float lift_scale = NATIVE_LAB_TRAJECTORY_MAX_LIFT /
                             NATIVE_LAB_TRAJECTORY_MAX_ELEVATION_DEGREES;
    const float lift = fmaxf(-NATIVE_LAB_TRAJECTORY_MAX_LIFT,
                             fminf(NATIVE_LAB_TRAJECTORY_MAX_LIFT,
                                   -vertical * lift_scale));
    float start_y = 0.0f;
    float end_y = 0.0f;
    memcpy(&start_y, (char *)screen_2d + 0x10f4, sizeof(start_y));
    memcpy(&end_y, (char *)screen_2d + 0x1154, sizeof(end_y));
    const float pi = 3.14159265358979323846f;
    for (uint32_t index = 1; index < 8; ++index) {
      const float t = (float)index / 8.0f;
      float y = 0.0f;
      memcpy(&y, (char *)screen_2d + 0x10f4 + index * 12u, sizeof(y));
      y += lift * sinf(pi * t);
      // LS-down may flatten the stock arc, but never push its preview below the
      // straight ground line between the ball and the target.
      const float floor_y = start_y + (end_y - start_y) * t;
      if (y < floor_y)
        y = floor_y;
      memcpy((char *)screen_2d + 0x10f4 + index * 12u, &y, sizeof(y));
    }
  }
  // While idle this continuously records the final, user-selected preview.
  // If an action begins before any idle frame was available, the same write
  // provides a one-frame fallback; subsequent active frames restore it.
  native_lab_cache_trajectory_points(pad, screen_2d);
}

#define NATIVE_LAB_GAUGE_WRAPPER(name, original)                         \
  static void name(void *unit, const void *input, void *screen_2d) {      \
    if (original)                                                        \
      original(unit, input, screen_2d);                                  \
    native_lab_track_action_power(unit, input, screen_2d);               \
    if (!(__atomic_load_n(&native_lab_debug_stock_mask, __ATOMIC_ACQUIRE) & \
          PES_NATIVE_LAB_STOCK_MOBILE_KICK))                             \
      native_lab_publish_setplay_trajectory(input, screen_2d);            \
  }

NATIVE_LAB_GAUGE_WRAPPER(native_lab_short_update_2d,
                         native_lab_short_update_2d_original)
NATIVE_LAB_GAUGE_WRAPPER(native_lab_long_update_2d,
                         native_lab_long_update_2d_original)
NATIVE_LAB_GAUGE_WRAPPER(native_lab_shoot_update_2d,
                         native_lab_shoot_update_2d_original)

#undef NATIVE_LAB_GAUGE_WRAPPER

static void native_lab_mobile_kick_update_2d(void *unit, const void *input,
                                              void *screen_2d) {
  if (native_lab_mobile_kick_update_2d_original)
    native_lab_mobile_kick_update_2d_original(unit, input, screen_2d);
  native_lab_track_action_power(NULL, input, screen_2d);
  native_lab_publish_setplay_trajectory(input, screen_2d);
  const uint32_t pad = native_lab_input_pad(input);
  const uint32_t action = __atomic_load_n(&native_lab_active_action[pad],
                                           __ATOMIC_ACQUIRE);
  if (!action || action > NATIVE_LAB_ACTION_SHOOT + 1u)
    return;
  const void *power_unit = (const void *)__atomic_load_n(
      &native_lab_action_units[pad][action - 1u], __ATOMIC_ACQUIRE);
  native_lab_track_action_power(power_unit, input, screen_2d);
}

static void native_lab_penalty_update_2d(void *unit, const void *input,
                                         void *screen_2d) {
  if (native_lab_penalty_update_2d_original)
    native_lab_penalty_update_2d_original(unit, input, screen_2d);
  const uint32_t pad = native_lab_input_pad(input);
  const void *power_unit = (const void *)__atomic_load_n(
      &native_lab_penalty_action_units[pad], __ATOMIC_ACQUIRE);
  native_lab_track_action_power(power_unit, input, screen_2d);
}

// ThinkUnitManager owns the real native PadCommand. The mobile gesture route
// normally populates its angle, but our physical Short/Long/Shoot unit returns
// only a command kind. Patch the exact release command with the direct native
// set-play angle, native hold power, and LS-Y height.
// No touch/swipe event is synthesized. The mobile unit's presentation-only
// elevation cache is mirrored for the debug trail; charge remains untouched.
static void native_lab_adjust_kick(uint32_t kind, float *angle,
                                   float *kick_power, float *vertical) {
  const uint32_t pending_command = __atomic_load_n(
      &native_lab_pending_kick_command, __ATOMIC_ACQUIRE);
  const uint32_t pending_pad = __atomic_load_n(
      &native_lab_pending_kick_pad, __ATOMIC_ACQUIRE);
  const uint32_t pending_action = __atomic_load_n(
      &native_lab_pending_kick_action, __ATOMIC_ACQUIRE);
  if (pending_pad && pending_command == kind) {
    const uint32_t context = __atomic_load_n(
        &native_lab_debug_context, __ATOMIC_ACQUIRE);
    const uint32_t pad = pending_pad - 1u;
    if (context == PES_SETPLAY_GOAL_KICK || context == PES_SETPLAY_CORNER ||
        context == PES_SETPLAY_FREE_KICK) {
      const uint32_t angle_bits = __atomic_load_n(
          &native_lab_command_angle_bits[pad], __ATOMIC_ACQUIRE);
      if (__atomic_load_n(&native_lab_command_angle_valid_mask,
                          __ATOMIC_ACQUIRE) & (1u << pad))
        memcpy(angle, &angle_bits, sizeof(*angle));
    }
    if (kick_power && pending_action &&
        pending_action <= NATIVE_LAB_ACTION_SHOOT + 1u) {
      float native_power = 0.0f;
      const uint32_t power_bits = __atomic_load_n(
          &native_lab_pending_kick_power_bits, __ATOMIC_ACQUIRE);
      memcpy(&native_power, &power_bits, sizeof(native_power));
      if (!(native_power > 0.0f)) {
        const void *power_unit = (const void *)__atomic_load_n(
            &native_lab_action_units[pad][pending_action - 1u],
            __ATOMIC_ACQUIRE);
        if (power_unit)
          memcpy(&native_power, (const char *)power_unit + 0x20,
                 sizeof(native_power));
      }
      if (native_power > 1.0f)
        native_power = 1.0f;
      if (native_power > 0.0f)
        *kick_power = native_power;
    }
    if (context == PES_SETPLAY_GOAL_KICK || context == PES_SETPLAY_CORNER ||
        context == PES_SETPLAY_FREE_KICK) {
      const uint32_t vertical_bits = __atomic_load_n(
          &native_lab_command_vertical_bits[pad], __ATOMIC_ACQUIRE);
      memcpy(vertical, &vertical_bits, sizeof(*vertical));
      // Only a Y/shoot release in a close free kick should override the
      // flight solver. B/A passes keep the stock elevation, and the token is
      // explicitly disarmed for them so a previous shot cannot leak forward.
      const int close_free_kick_shoot =
          context == PES_SETPLAY_FREE_KICK &&
          pending_action == NATIVE_LAB_ACTION_SHOOT + 1u;
      float requested_elevation = 0.0f;
      memcpy(&requested_elevation, &vertical_bits,
             sizeof(requested_elevation));
      if (close_free_kick_shoot && isfinite(requested_elevation) &&
          fabsf(requested_elevation) > 0.01f) {
        __atomic_store_n(&native_lab_free_kick_elevation_bits[pad],
                         vertical_bits, __ATOMIC_RELEASE);
        __atomic_store_n(&native_lab_free_kick_elevation_linger[pad], 120u,
                         __ATOMIC_RELEASE);
        __atomic_fetch_or(&native_lab_free_kick_elevation_mask, 1u << pad,
                          __ATOMIC_ACQ_REL);
      } else {
        __atomic_store_n(&native_lab_free_kick_elevation_linger[pad], 0,
                         __ATOMIC_RELEASE);
        __atomic_fetch_and(&native_lab_free_kick_elevation_mask,
                           ~(1u << pad), __ATOMIC_ACQ_REL);
      }
    }
    __atomic_store_n(&native_lab_pending_kick_pad, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_pending_kick_command, 0,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_pending_kick_action, 0,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_pending_kick_power_bits, 0,
                     __ATOMIC_RELEASE);
  }
}

static void native_lab_set_kick(void *command, uint32_t kind, float angle,
                                float stick_power, float kick_power,
                                uint32_t kick_flags, float vertical,
                                float aux_power, uint32_t target,
                                uint32_t player) {
  native_lab_adjust_kick(kind, &angle, &kick_power, &vertical);
  if (native_lab_set_kick_original)
    native_lab_set_kick_original(command, kind, angle, stick_power,
                                 kick_power, kick_flags, vertical, aux_power,
                                 target, player);
}

// CreateCommand uses this overload for another subset of pass/shot kinds.
// Hook both overloads so LS aim cannot silently fall back to the stock straight
// angle depending on whether B, A, or Y produced the release command.
static void native_lab_set_kick_no_player(
    void *command, uint32_t kind, float angle, float stick_power,
    float kick_power, uint32_t kick_flags, float vertical, float aux_power,
    uint32_t target) {
  native_lab_adjust_kick(kind, &angle, &kick_power, &vertical);
  if (native_lab_set_kick_no_player_original)
    native_lab_set_kick_no_player_original(
        command, kind, angle, stick_power, kick_power, kick_flags, vertical,
        aux_power, target);
}

// Apply the requested close-free-kick pitch after the stock solver has built
// its world-space flight vector.  `speed` is math::Vector3 (x/y/z): x/z are
// the ground-plane components and y is the vertical component.  Replacing y
// from the horizontal magnitude preserves the native direction and power,
// while making the preview's LS-Y height affect the actual kick.
static void native_lab_ball_injection(const void *input, void *speed,
                                      void *rotation) {
  if (native_lab_ball_injection_original)
    native_lab_ball_injection_original(input, speed, rotation);
  if (!speed || __atomic_load_n(&native_lab_debug_context, __ATOMIC_ACQUIRE) !=
                   PES_SETPLAY_FREE_KICK)
    return;
  const uint32_t armed = __atomic_load_n(
      &native_lab_free_kick_elevation_mask, __ATOMIC_ACQUIRE);
  if (!armed)
    return;
  uint32_t pad = UINT32_MAX;
  for (uint32_t candidate = 0; candidate < 2; ++candidate) {
    if (!(armed & (1u << candidate)))
      continue;
    const uint32_t linger = __atomic_load_n(
        &native_lab_free_kick_elevation_linger[candidate],
        __ATOMIC_ACQUIRE);
    if (!linger) {
      __atomic_fetch_and(&native_lab_free_kick_elevation_mask,
                         ~(1u << candidate), __ATOMIC_ACQ_REL);
      continue;
    }
    __atomic_fetch_sub(&native_lab_free_kick_elevation_linger[candidate], 1u,
                       __ATOMIC_ACQ_REL);
    pad = candidate;
    break;
  }
  if (pad == UINT32_MAX)
    return;
  uint32_t elevation_bits = __atomic_load_n(
      &native_lab_free_kick_elevation_bits[pad], __ATOMIC_ACQUIRE);
  float elevation_degrees = 0.0f;
  memcpy(&elevation_degrees, &elevation_bits, sizeof(elevation_degrees));
  if (!isfinite(elevation_degrees))
    return;
  if (elevation_degrees > NATIVE_LAB_TRAJECTORY_MAX_ELEVATION_DEGREES)
    elevation_degrees = NATIVE_LAB_TRAJECTORY_MAX_ELEVATION_DEGREES;
  else if (elevation_degrees < -NATIVE_LAB_TRAJECTORY_MAX_ELEVATION_DEGREES)
    elevation_degrees = -NATIVE_LAB_TRAJECTORY_MAX_ELEVATION_DEGREES;
  float *velocity = (float *)speed;
  const float horizontal =
      sqrtf(velocity[0] * velocity[0] + velocity[2] * velocity[2]);
  if (!isfinite(horizontal) || horizontal <= 0.001f)
    return;
  const float pitch = elevation_degrees * 0.0174532925199433f;
  const float vertical = horizontal * tanf(pitch);
  if (isfinite(vertical))
    velocity[1] = vertical;
  if (__atomic_load_n(&native_lab_free_kick_elevation_linger[pad],
                      __ATOMIC_ACQUIRE) == 0)
    __atomic_fetch_and(&native_lab_free_kick_elevation_mask, ~(1u << pad),
                       __ATOMIC_ACQ_REL);
}

static uint32_t native_lab_setplay_button_action(uint32_t context,
                                                  uint32_t buttons) {
  // Throw-in uses the mobile presentation's B normal / Y long convention.
  // The other set plays retain B short / A long; near free kicks additionally
  // expose Y shoot.
  if (buttons & (1u << 0))
    return NATIVE_LAB_ACTION_SHORT + 1u;
  if (context == PES_SETPLAY_THROW_IN && (buttons & (1u << 2)))
    return NATIVE_LAB_ACTION_LONG + 1u;
  if (buttons & (1u << 1))
    return NATIVE_LAB_ACTION_LONG + 1u;
  if (context == PES_SETPLAY_FREE_KICK && (buttons & (1u << 2)))
    return NATIVE_LAB_ACTION_SHOOT + 1u;
  return 0;
}

static uint32_t native_lab_exec_setplay_action(uint32_t pad,
                                                uint32_t action,
                                                int pressed,
                                                const void *input) {
  if (pad > 1 || action == 0 || action > NATIVE_LAB_ACTION_SHOOT + 1u)
    return 0;
  void *unit = (void *)__atomic_load_n(
      &native_lab_action_units[pad][action - 1u], __ATOMIC_ACQUIRE);
  if (!unit)
    return 0;
  uint32_t result = 0;
  uint32_t event = PES_NATIVE_LAB_EVENT_NONE;
  float release_power = 0.0f;
  if (!pressed)
    memcpy(&release_power, (const char *)unit + 0x20,
           sizeof(release_power));
  switch (action - 1u) {
  case NATIVE_LAB_ACTION_SHORT:
    result = pressed ? native_lab_short_press_original(unit, input)
                     : native_lab_short_pull_original(unit, input);
    event = pressed ? PES_NATIVE_LAB_EVENT_SHORT_PRESS
                    : PES_NATIVE_LAB_EVENT_SHORT_RELEASE;
    break;
  case NATIVE_LAB_ACTION_LONG:
    result = pressed ? native_lab_long_press_original(unit, input)
                     : native_lab_long_pull_original(unit, input);
    event = pressed ? PES_NATIVE_LAB_EVENT_LONG_PRESS
                    : PES_NATIVE_LAB_EVENT_LONG_RELEASE;
    break;
  case NATIVE_LAB_ACTION_SHOOT:
    result = pressed ? native_lab_shoot_press_original(unit, input)
                     : native_lab_shoot_pull_original(unit, input);
    event = pressed ? PES_NATIVE_LAB_EVENT_SHOOT_PRESS
                    : PES_NATIVE_LAB_EVENT_SHOOT_RELEASE;
    break;
  default:
    return 0;
  }
  if (!pressed && result) {
    uint32_t power_bits = 0;
    memcpy(&power_bits, &release_power, sizeof(power_bits));
    __atomic_store_n(&native_lab_pending_kick_pad, pad + 1u,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_pending_kick_command, result,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_pending_kick_action, action,
                     __ATOMIC_RELEASE);
    __atomic_store_n(&native_lab_pending_kick_power_bits, power_bits,
                     __ATOMIC_RELEASE);
  }
  native_lab_note_action(input, event, result);
  if (pressed)
    native_lab_track_action_power(unit, input, NULL);
  return result;
}

static void native_lab_apply_native_kick_angle(void *unit, const void *input,
                                               uint32_t pad,
                                               uint32_t context) {
  if (!unit || !input || pad > 1)
    return;
  float stock_angle = 0.0f;
  memcpy(&stock_angle, (const char *)unit + 0x38, sizeof(stock_angle));
  const float camera_yaw_degrees =
      (float)__atomic_load_n(&native_lab_camera_yaw_millirad[pad],
                             __ATOMIC_ACQUIRE) /
      1000.0f * 57.2957795131f;
  const int32_t raw_left_x = __atomic_load_n(
      pad == 1 ? &native_lab_debug_axis_x_p2 : &native_lab_debug_axis_x,
      __ATOMIC_ACQUIRE);
  const int32_t raw_left_y = __atomic_load_n(
      pad == 1 ? &native_lab_debug_axis_y_p2 : &native_lab_debug_axis_y,
      __ATOMIC_ACQUIRE);
  const float left_x = native_lab_normalize_axis(raw_left_x);
  const float left_y = native_lab_normalize_axis(raw_left_y);
  const uint32_t latched = __atomic_load_n(
      &native_lab_left_aim_latched_mask, __ATOMIC_ACQUIRE);
  uint32_t player = UINT32_MAX;
  memcpy(&player, (const char *)input + 0x24, sizeof(player));
  int same_target = 0;
  const float base_angle = native_lab_stable_setplay_base_angle(
      pad, player, stock_angle, &same_target);
  float desired = base_angle + camera_yaw_degrees;
  if (left_x != 0.0f) {
    // Horizontal direction and vertical lift are independent, matching the
    // mobile swipe's X/Z semantics. A bounded offset prevents a corner from
    // rotating through the taker's back.
    desired -= left_x * (context == PES_SETPLAY_CORNER ? 75.0f : 60.0f);
  } else if (same_target && (latched & (1u << pad))) {
    const uint32_t previous_bits = __atomic_load_n(
        &native_lab_command_angle_bits[pad], __ATOMIC_ACQUIRE);
    memcpy(&desired, &previous_bits, sizeof(desired));
  }
  if (context == PES_SETPLAY_CORNER && native_lab_mobile_filter_angle_abi)
    desired = native_lab_mobile_filter_angle_abi(unit, input, desired);
  if (left_y != 0.0f) {
    const float vertical =
        -left_y * NATIVE_LAB_TRAJECTORY_MAX_ELEVATION_DEGREES;
    uint32_t vertical_bits = 0;
    memcpy(&vertical_bits, &vertical, sizeof(vertical_bits));
    __atomic_store_n(&native_lab_command_vertical_bits[pad], vertical_bits,
                     __ATOMIC_RELEASE);
  }
  // ThinkUnitManager forwards MobileSetplayKick +0x38 as PadCommand angle and
  // +0x44 as its signed vertical/elevation parameter. Mirror both pad-owned
  // values after the original Main() call so close free kicks execute along
  // the same horizontal and vertical direction shown by the white preview.
  const uint32_t vertical_bits = __atomic_load_n(
      &native_lab_command_vertical_bits[pad], __ATOMIC_ACQUIRE);
  float latched_vertical = 0.0f;
  memcpy(&latched_vertical, &vertical_bits, sizeof(latched_vertical));
  memcpy((char *)unit + 0x44, &latched_vertical, sizeof(latched_vertical));
  if (left_x != 0.0f || left_y != 0.0f) {
    __atomic_fetch_or(&native_lab_left_aim_latched_mask, 1u << pad,
                      __ATOMIC_ACQ_REL);
  }
  while (desired < 0.0f)
    desired += 360.0f;
  while (desired >= 360.0f)
    desired -= 360.0f;
  memcpy((char *)unit + 0x38, &desired, sizeof(desired));
  uint32_t angle_bits = 0;
  memcpy(&angle_bits, &desired, sizeof(angle_bits));
  __atomic_store_n(&native_lab_command_angle_bits[pad], angle_bits,
                   __ATOMIC_RELEASE);
  __atomic_fetch_or(&native_lab_command_angle_valid_mask, 1u << pad,
                    __ATOMIC_RELEASE);
}

static uint32_t native_lab_mobile_kick_main(void *unit, const void *input,
                                            uint32_t kind) {
  // Always retain MobileSetplayKick's initialization and touch-independent
  // state.  Only its returned command is overridden while a physical kick is
  // charging/releasing or the native SetplayGuide has a stick command.
  const uint32_t stock = native_lab_mobile_kick_main_original
                             ? native_lab_mobile_kick_main_original(
                                   unit, input, kind)
                             : 0;
  if (!pes_controller_native_pad_lab_active())
    return stock;
  const uint32_t context = __atomic_load_n(&native_lab_debug_context,
                                           __ATOMIC_ACQUIRE);
  if (context == PES_SETPLAY_NONE)
    return stock;
  const uint32_t pad = native_lab_input_pad(input);
  const uint32_t buttons = __atomic_load_n(
      pad == 1 ? &native_lab_debug_buttons_p2 : &native_lab_debug_buttons,
      __ATOMIC_ACQUIRE);
  const uint32_t action = native_lab_setplay_button_action(context, buttons);
  const uint32_t previous = __atomic_load_n(
      &native_lab_active_action[pad], __ATOMIC_ACQUIRE);

  if (previous && previous != action) {
    __atomic_store_n(&native_lab_active_action[pad], 0, __ATOMIC_RELEASE);
    // Keep the final aim/elevation captured during the press through the
    // release command.  The automatic run-up may rotate the player's model,
    // but it must not rewrite the selected trajectory.
    return native_lab_exec_setplay_action(pad, previous, 0, input);
  }
  if (previous && action)
    return native_lab_exec_setplay_action(pad, action, 1, input);

  // Idle frames and the first press frame are the only times the stick may
  // change the command.  Once `previous` is active, the angle and height stay
  // frozen until the native release has completed.
  native_lab_apply_native_kick_angle(unit, input, pad, context);
  if (action) {
    __atomic_store_n(&native_lab_active_action[pad], action,
                     __ATOMIC_RELEASE);
    return native_lab_exec_setplay_action(pad, action, 1, input);
  }

  return stock;
}

// draw::CameraParameter begins with look-at XYZ followed by position XYZ.
// Hooking the active camera plugin after its stock Update avoids the mobile
// swipe/ButtonObject path entirely and keeps every camera's own limits/init.
typedef struct {
  float look_x, look_y, look_z;
  float position_x, position_y, position_z;
} NativeLabCameraParameter;

static void native_lab_apply_camera_stick(void *plugin, void *parameter_ptr,
                                          uint32_t expected_context,
                                          NativeLabCameraState *state) {
  const int lab_active = pes_controller_native_pad_lab_active();
  const uint32_t active_context = __atomic_load_n(
      &native_lab_debug_context, __ATOMIC_ACQUIRE);
  if (!parameter_ptr || !lab_active || active_context != expected_context) {
    // An inactive camera plugin can still receive Update around transitions.
    // Never let it zero the yaw published by the currently active plugin.
    if (state->plugin && state->pad < 2 &&
        (!lab_active || active_context == PES_SETPLAY_NONE))
      __atomic_store_n(&native_lab_camera_yaw_millirad[state->pad], 0,
                       __ATOMIC_RELEASE);
    memset(state, 0, sizeof(*state));
    return;
  }
  const uint32_t pad = __atomic_load_n(&native_lab_debug_setplay_pad,
                                       __ATOMIC_ACQUIRE) == 1 ? 1u : 0u;
  const uint64_t now = armGetSystemTick();
  if (state->plugin != plugin || state->pad != pad ||
      (state->last_tick &&
       armTicksToNs(now - state->last_tick) > 400000000ULL)) {
    if (state->plugin && state->pad < 2)
      __atomic_store_n(&native_lab_camera_yaw_millirad[state->pad], 0,
                       __ATOMIC_RELEASE);
    state->plugin = plugin;
    state->yaw = 0.0f;
    state->pad = pad;
  }
  state->last_tick = now;
  const int32_t raw_x = __atomic_load_n(
      pad == 1 ? &native_lab_debug_right_axis_x_p2
               : &native_lab_debug_right_axis_x,
      __ATOMIC_ACQUIRE);
  // Exact hardware-tested V7 camera baseline. RS accumulates a bounded orbit
  // around the stock ball pivot and remains at that yaw after stick release.
  // LS is intentionally absent from this plugin hook.
  float axis_x = (float)raw_x / 32768.0f;
  const float absolute_x = fabsf(axis_x);
  if (absolute_x > 0.18f) {
    const float clamped = absolute_x > 1.0f ? 1.0f : absolute_x;
    axis_x = copysignf((clamped - 0.18f) / 0.82f, axis_x);
    state->yaw += axis_x * 0.025f;
    if (state->yaw > 0.55f)
      state->yaw = 0.55f;
    else if (state->yaw < -0.55f)
      state->yaw = -0.55f;
  }
  __atomic_store_n(&native_lab_camera_yaw_millirad[pad],
                   (int32_t)(state->yaw * 1000.0f), __ATOMIC_RELEASE);

  // The stock plugin already points `look` at the ball. Rotate only the camera
  // position around that pivot; RS vertical is intentionally ignored.
  NativeLabCameraParameter *parameter = parameter_ptr;
  const float relative_x = parameter->position_x - parameter->look_x;
  const float relative_z = parameter->position_z - parameter->look_z;
  const float cosine = cosf(state->yaw);
  const float sine = sinf(state->yaw);
  parameter->position_x = parameter->look_x +
                          relative_x * cosine - relative_z * sine;
  parameter->position_z = parameter->look_z +
                          relative_x * sine + relative_z * cosine;
}

#define NATIVE_LAB_CAMERA_WRAPPER(name, original, context, state)          \
  static void name(void *plugin, void *parameter) {                        \
    if (original)                                                          \
      original(plugin, parameter);                                         \
    native_lab_apply_camera_stick(plugin, parameter, context, &state);      \
  }

NATIVE_LAB_CAMERA_WRAPPER(native_lab_corner_camera_update,
                          native_lab_corner_camera_update_original,
                          PES_SETPLAY_CORNER, native_lab_corner_camera)
NATIVE_LAB_CAMERA_WRAPPER(native_lab_goal_camera_update,
                          native_lab_goal_camera_update_original,
                          PES_SETPLAY_GOAL_KICK, native_lab_goal_camera)
NATIVE_LAB_CAMERA_WRAPPER(native_lab_free_camera_update,
                          native_lab_free_camera_update_original,
                          PES_SETPLAY_FREE_KICK, native_lab_free_camera)

#undef NATIVE_LAB_CAMERA_WRAPPER

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
  uintptr_t *penalty_press_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad20ThinkUnitPenaltykickE",
      "_ZN5match3pad20ThinkUnitPenaltykick9ExecPressERKNS0_18ThinkUnitInputDataE");
  uintptr_t *penalty_pull_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad20ThinkUnitPenaltykickE",
      "_ZN5match3pad20ThinkUnitPenaltykick8ExecPullERKNS0_18ThinkUnitInputDataE");
  uintptr_t *support_pull_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad28ThinkUnitGoalkickPassSupportE",
      "_ZN5match3pad28ThinkUnitGoalkickPassSupport8ExecPullERKNS0_18ThinkUnitInputDataE");
  uintptr_t *mobile_kick_main_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad26ThinkUnitMobileSetplayKickE",
      "_ZN5match3pad26ThinkUnitMobileSetplayKick4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE");
  const char *base_update_2d =
      "_ZN5match3pad13ThinkUnitBase12Update2DInfoERKNS0_18ThinkUnitInputDataEPNS_8registry12Screen2dInfoE";
  uintptr_t *short_update_2d_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad18ThinkUnitShortPassE", base_update_2d);
  uintptr_t *long_update_2d_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad17ThinkUnitLongPassE", base_update_2d);
  uintptr_t *shoot_update_2d_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad14ThinkUnitShootE", base_update_2d);
  uintptr_t *mobile_kick_update_2d_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad26ThinkUnitMobileSetplayKickE",
      "_ZN5match3pad26ThinkUnitMobileSetplayKick12Update2DInfoERKNS0_18ThinkUnitInputDataEPNS_8registry12Screen2dInfoE");
  uintptr_t *penalty_update_2d_slot = native_lab_method_slot(
      module, "_ZTVN5match3pad26ThinkUnitMobilePenaltyKickE",
      "_ZN5match3pad26ThinkUnitMobilePenaltyKick12Update2DInfoERKNS0_18ThinkUnitInputDataEPNS_8registry12Screen2dInfoE");
  const uintptr_t draw_pass_line = so_try_find_addr_rx(
      module,
      "_ZN5match3pad12DrawPassLineENS_14PadCommandKindEh8PlayerNoS2_fPKNS_8registry8RegistryEPNS3_12Screen2dInfoE");
  const uintptr_t mobile_filter_angle = so_try_find_addr_rx(
      module,
      "_ZN5match3pad26ThinkUnitMobileSetplayKick11FilterAngleERKNS0_18ThinkUnitInputDataEf");
  const uintptr_t set_kick = so_try_find_addr_rx(
      module,
      "_ZN5match8registry10PadCommand7SetKickENS_14PadCommandKindEfffhffhh");
  const uintptr_t set_kick_no_player = so_try_find_addr_rx(
      module,
      "_ZN5match8registry10PadCommand7SetKickENS_14PadCommandKindEfffhffh");
  const uintptr_t ball_injection = so_try_find_addr_rx(
      module,
      "_ZN5match32GetBallInjectionSpeedAndRotationERKNS_23InputBallInjectionSpeedERN4math7Vector3ES5_");
  uintptr_t *corner_camera_slot = native_lab_method_slot(
      module, "_ZTVN5match6camera6plugin16CornerKickCameraE",
      "_ZN5match6camera6plugin16CornerKickCamera6UpdateERN4draw15CameraParameterE");
  uintptr_t *goal_camera_slot = native_lab_method_slot(
      module, "_ZTVN5match6camera6plugin14GoalKickCameraE",
      "_ZN5match6camera6plugin14GoalKickCamera6UpdateERN4draw15CameraParameterE");
  uintptr_t *free_camera_slot = native_lab_method_slot(
      module, "_ZTVN5match6camera6plugin14FreeKickCameraE",
      "_ZN5match6camera6plugin14FreeKickCamera6UpdateERN4draw15CameraParameterE");
  if (!guide || !guide_slot || !short_press_slot || !short_pull_slot ||
      !long_press_slot || !long_pull_slot || !shoot_press_slot ||
      !shoot_pull_slot || !penalty_press_slot || !penalty_pull_slot ||
      !support_pull_slot || !mobile_kick_main_slot ||
      !short_update_2d_slot || !long_update_2d_slot ||
      !shoot_update_2d_slot || !mobile_kick_update_2d_slot ||
      !penalty_update_2d_slot || !draw_pass_line ||
      !mobile_filter_angle || !set_kick ||
      !set_kick_no_player || !ball_injection ||
      !corner_camera_slot ||
      !goal_camera_slot || !free_camera_slot)
    return 0;

  const uintptr_t set_kick_plt =
      (uintptr_t)module->load_base + 0x38619b0;
  const uint32_t set_kick_plt_words[] = {
      0xb002e470, 0xf9479a11, 0x913cc210, 0xd61f0220};
  const uintptr_t set_kick_no_player_plt =
      (uintptr_t)module->load_base + 0x391ed80;
  const uint32_t set_kick_no_player_plt_words[] = {
      0xf002e170, 0xf9448e11, 0x91246210, 0xd61f0220};
  const uintptr_t ball_injection_plt =
      (uintptr_t)module->load_base + 0x38b4850;
  const uint32_t ball_injection_plt_words[] = {
      0x9002e330, 0xf9434211, 0x911a0210, 0xd61f0220};
  if (memcmp((const void *)set_kick_plt, set_kick_plt_words,
             sizeof(set_kick_plt_words)) ||
      memcmp((const void *)set_kick_no_player_plt,
             set_kick_no_player_plt_words,
             sizeof(set_kick_no_player_plt_words)) ||
      memcmp((const void *)ball_injection_plt, ball_injection_plt_words,
             sizeof(ball_injection_plt_words)))
    return 0;

  native_lab_guide_main_original = (void *)guide;
  native_lab_short_press_original = (void *)*short_press_slot;
  native_lab_short_pull_original = (void *)*short_pull_slot;
  native_lab_long_press_original = (void *)*long_press_slot;
  native_lab_long_pull_original = (void *)*long_pull_slot;
  native_lab_shoot_press_original = (void *)*shoot_press_slot;
  native_lab_shoot_pull_original = (void *)*shoot_pull_slot;
  native_lab_penalty_press_original = (void *)*penalty_press_slot;
  native_lab_penalty_pull_original = (void *)*penalty_pull_slot;
  native_lab_support_pull_original = (void *)*support_pull_slot;
  native_lab_mobile_kick_main_original = (void *)*mobile_kick_main_slot;
  native_lab_mobile_filter_angle_abi = (void *)mobile_filter_angle;
  native_lab_short_update_2d_original = (void *)*short_update_2d_slot;
  native_lab_long_update_2d_original = (void *)*long_update_2d_slot;
  native_lab_shoot_update_2d_original = (void *)*shoot_update_2d_slot;
  native_lab_mobile_kick_update_2d_original =
      (void *)*mobile_kick_update_2d_slot;
  native_lab_penalty_update_2d_original =
      (void *)*penalty_update_2d_slot;
  native_lab_draw_pass_line = (void *)draw_pass_line;
  native_lab_set_kick_original = (void *)set_kick;
  native_lab_set_kick_no_player_original = (void *)set_kick_no_player;
  native_lab_ball_injection_original = (void *)ball_injection;
  native_lab_corner_camera_update_original = (void *)*corner_camera_slot;
  native_lab_goal_camera_update_original = (void *)*goal_camera_slot;
  native_lab_free_camera_update_original = (void *)*free_camera_slot;
  *guide_slot = (uintptr_t)&native_lab_guide_main;
  *short_press_slot = (uintptr_t)&native_lab_short_press;
  *short_pull_slot = (uintptr_t)&native_lab_short_pull;
  *long_press_slot = (uintptr_t)&native_lab_long_press;
  *long_pull_slot = (uintptr_t)&native_lab_long_pull;
  *shoot_press_slot = (uintptr_t)&native_lab_shoot_press;
  *shoot_pull_slot = (uintptr_t)&native_lab_shoot_pull;
  *penalty_press_slot = (uintptr_t)&native_lab_penalty_press;
  *penalty_pull_slot = (uintptr_t)&native_lab_penalty_pull;
  *support_pull_slot = (uintptr_t)&native_lab_support_pull;
  *mobile_kick_main_slot = (uintptr_t)&native_lab_mobile_kick_main;
  *short_update_2d_slot = (uintptr_t)&native_lab_short_update_2d;
  *long_update_2d_slot = (uintptr_t)&native_lab_long_update_2d;
  *shoot_update_2d_slot = (uintptr_t)&native_lab_shoot_update_2d;
  *mobile_kick_update_2d_slot =
      (uintptr_t)&native_lab_mobile_kick_update_2d;
  *penalty_update_2d_slot = (uintptr_t)&native_lab_penalty_update_2d;
  *corner_camera_slot = (uintptr_t)&native_lab_corner_camera_update;
  *goal_camera_slot = (uintptr_t)&native_lab_goal_camera_update;
  *free_camera_slot = (uintptr_t)&native_lab_free_camera_update;
  hook_arm64(set_kick_plt, (uintptr_t)&native_lab_set_kick);
  hook_arm64(set_kick_no_player_plt,
             (uintptr_t)&native_lab_set_kick_no_player);
  hook_arm64(ball_injection_plt, (uintptr_t)&native_lab_ball_injection);
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
  for (unsigned i = 0;
       i < sizeof(native_lab_optional_penalty_units) /
               sizeof(native_lab_optional_penalty_units[0]);
       ++i) {
    const uintptr_t vt = so_try_find_addr_rx(
        module, native_lab_optional_penalty_units[i].symbol);
    // Optional by design: zero leaves only the penalty route on its mobile
    // fallback and cannot fail native gameplay installation.
    native_lab_optional_penalty_units[i].vptr = vt ? vt + 16 : 0;
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

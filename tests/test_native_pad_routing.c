// Host tests execute the SAME adapter compiled into the Switch NRO.
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../source/ue4_hooks.h"
#define NATIVE_PAD_LAB_HOST_TEST
static int active;
static int two_player;
static uint64_t cobra_pad_input;
static uint32_t cobra_pad_connected;
static uint64_t cobra_pad_input_p2;
static uint32_t cobra_pad_connected_p2;
int pes_controller_native_pad_lab_active(void) { return active; }
int pes_controller_native_pad_lab_two_player(void) {
  return active && two_player;
}
#include "../source/native_pad_lab.inc"

static _Alignas(8) unsigned char list[0x3f00], before[sizeof(list)];
static _Alignas(8) unsigned char input[0x80], cursor[0xa0];
static _Alignas(8) unsigned char cursor_info[24 * 0xa0];
static uintptr_t objects[97];
static uint32_t history[5], history_p2[5];
static void *accessor, *original_input_unit;
static int calls, sample_calls, prime_calls;
int cobra_pad_prime_native_port(uint32_t port) {
  assert(port <= 1);
  prime_calls++;
  return 1;
}

static void stock_list(void *p, const void *in, uint32_t previous, uint32_t context) {
  assert(p == list && in == input && previous == 61 && context == 7);
  const uint32_t player = *(const uint32_t *)(input + 0x24);
  if (active && *(void **)(input + 0x18) &&
      (player < 11 || two_player))
    assert(accessor == (player < 11 ? (void *)history
                                   : (void *)history_p2));
  calls++;
}
static void stock_sample(void *p, uint32_t pad, const void *c, const void *m) {
  assert(p == history && c == cursor && m == input);
  assert(pad < 4);
  sample_calls++;
}
static void *get_history(void *p, int back) {
  assert(p == history && back == 0);
  return p;
}
static void setup(void) {
  memset(list, 0, sizeof(list));
  memset(input, 0, sizeof(input));
  memset(cursor, 0, sizeof(cursor));
  memset(history, 0, sizeof(history));
  memset(history_p2, 0, sizeof(history_p2));
  active = 1;
  two_player = 1;
  native_lab_installed = 1;
  native_lab_action_hooks_installed = 1;
  calls = sample_calls = prime_calls = 0;
  native_pad_lab_reset();
  native_lab_list_update_original = stock_list;
  native_lab_sample_original = stock_sample;
  native_lab_history_get = get_history;
  original_input_unit = &objects[96];
  accessor = original_input_unit;
  *(void **)(input+0x08) = cursor;
  *(void **)(input+0x18) = &accessor;
  *(uint32_t *)(input+0x24) = 4;
  __atomic_store_n(&native_lab_input_units[0], (uintptr_t)history,
                   __ATOMIC_RELEASE);
  __atomic_store_n(&native_lab_input_units[1], (uintptr_t)history_p2,
                   __ATOMIC_RELEASE);
  for (unsigned i = 0; i < sizeof(native_lab_units)/sizeof(native_lab_units[0]); i++) {
    NativeLabUnit *unit = &native_lab_units[i];
    unit->vptr = 1000+unit->kind;
    objects[unit->kind] = unit->vptr;
    *(void **)(list+0x3bf8+unit->kind*8) = &objects[unit->kind];
  }
  for (unsigned i = 0;
       i < sizeof(native_lab_optional_penalty_units) /
               sizeof(native_lab_optional_penalty_units[0]);
       ++i) {
    NativeLabUnit *unit = &native_lab_optional_penalty_units[i];
    unit->vptr = 1000 + unit->kind;
    objects[unit->kind] = unit->vptr;
    *(void **)(list + 0x3bf8 + unit->kind * 8) = &objects[unit->kind];
  }
}
static void run(const uint32_t *entries, uint32_t n) {
  *(uint32_t *)list = n;
  memcpy(list+4, entries, n*4);
  memcpy(before, list, sizeof(list));
  native_lab_list_update(list, input, 61, 7);
  assert(calls == 1);
  assert(accessor == original_input_unit); // Scoped binding was restored.
}
static void unchanged(void) { assert(!memcmp(list, before, sizeof(list))); }

static void setup_cursor_info(void) {
  memset(cursor_info, 0, sizeof(cursor_info));
  for (uint32_t i = 0; i < 24; ++i) {
    unsigned char *entry = cursor_info + i * 0xa0;
    const int32_t no_pad = -1;
    const uint32_t no_player = 0xff;
    entry[0] = 1;
    entry[1] = (uint8_t)i;
    memcpy(entry + 0x10, &no_pad, sizeof(no_pad));
    memcpy(entry + 0x20, &no_player, sizeof(no_player));
  }
  unsigned char *home = cursor_info + 3 * 0xa0;
  const int32_t home_pad = 0;
  const uint32_t home_player = 4;
  home[0] = 0;
  memcpy(home + 0x10, &home_pad, sizeof(home_pad));
  memcpy(home + 0x20, &home_player, sizeof(home_player));
  memset(home + 0x6c, 0x5a, 0x34); // Stock support settings must be cloned.
}

int main(void) {
  setup();
  setup_cursor_info();
  pes_match_cursor_info_ready(cursor_info);
  PesNativePadLabDebug debug;
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.owner_mask == 3u);
  assert((debug.cursor_slots & 0xffu) == 4u); // HOME CursorNo 3, encoded +1.
  assert(((debug.cursor_slots >> 8) & 0xffu) == 1u); // First empty slot.
  assert(debug.cursor_slots & (1u << 16));
  unsigned char *away_cursor = cursor_info;
  assert(away_cursor[0] == 2 && away_cursor[1] == 0 &&
         away_cursor[6] == 0 && away_cursor[0x0d] == 0);
  assert(native_lab_cursor_pad(away_cursor) == 1);
  assert(native_lab_cursor_player(away_cursor) == 15);
  assert(!memcmp(away_cursor + 0x6c, cursor_info + 3 * 0xa0 + 0x6c, 0x34));
  const uint32_t first_slots = debug.cursor_slots;
  pes_match_cursor_info_ready(cursor_info); // Idempotent: keep stock AWAY.
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.owner_mask == 3u && debug.cursor_slots == (first_slots & 0xffffu));

  const uint32_t attack[] = {94,78,79,80,83,57};
  const uint32_t expected[] = {94,3,0,1,2,10,57};
  setup(); run(attack,6);
  assert(*(uint32_t *)list == 7);
  assert(!memcmp(list+4, expected, sizeof(expected)));
  assert(!memcmp(list+0x188, before+0x188, sizeof(list)-0x188));
  assert((pes_controller_native_pad_lab_status() & 12) == 12);

  const uint32_t defence[] = {84,85,86,87,88,89};
  const uint32_t expected_defence[] = {12,5,6,9,7,11};
  setup(); run(defence,6);
  assert(*(uint32_t *)list == 6);
  assert(!memcmp(list+4, expected_defence, sizeof(expected_defence)));

  // Mobile penalty remains for lifecycle/Update2D, while the native console
  // guide/action are appended. Execution reads this pad's real PadAccessor.
  const uint32_t penalty[] = {91};
  const uint32_t expected_penalty[] = {91,27,37};
  setup(); run(penalty,1);
  assert(*(uint32_t *)list == 3);
  assert(!memcmp(list+4, expected_penalty, sizeof(expected_penalty)));
  assert(native_lab_penalty_action_units[0] == (uintptr_t)&objects[37]);
  assert(pes_controller_native_penalty_ready(0, PES_PENALTY_KICKER));

  // Keeper uses the three native console layers; no mobile ScreenTap is
  // needed, and an ambiguous list can safely carry both role suites.
  const uint32_t penalty_keeper[] = {92,93};
  const uint32_t expected_penalty_keeper[] = {92,93,43,44,66};
  setup(); run(penalty_keeper,2);
  assert(*(uint32_t *)list == 5);
  assert(!memcmp(list+4, expected_penalty_keeper,
                 sizeof(expected_penalty_keeper)));
  const uint32_t penalty_both[] = {91,92,93};
  const uint32_t expected_penalty_both[] = {91,92,93,27,37,43,44,66};
  setup(); run(penalty_both,3);
  assert(*(uint32_t *)list == 8);
  assert(!memcmp(list+4, expected_penalty_both,
                 sizeof(expected_penalty_both)));

  // Optional penalty ABI failure is local and non-fatal. It must neither
  // rewrite the penalty list nor raise global ABI ERROR for normal gameplay.
  setup();
  objects[NATIVE_LAB_KIND_PENALTY_KICK] = 0;
  run(penalty, 1);
  assert(*(uint32_t *)list == 1 && ((uint32_t *)list)[1] == 91);
  assert(!(pes_controller_native_pad_lab_status() & 128u));
  assert(!pes_controller_native_penalty_ready(0, PES_PENALTY_KICKER));

  // MobileSetplayKick must run before SetplayGuide so its Pull/Release command
  // cannot be masked by a non-zero LS guide command. The real guide still runs
  // on idle frames and RS retains the stable V7 camera angle.
  const uint32_t goal_kick[] = {61,60,95,64,90,96};
  setup(); run(goal_kick,6);
  const uint32_t expected_goal_kick[] = {61,60,95,64,90,26,96};
  assert(*(uint32_t *)list == 7);
  assert(!memcmp(list+4, expected_goal_kick, sizeof(expected_goal_kick)));
  assert(native_lab_action_units[0][NATIVE_LAB_ACTION_SHORT] ==
         (uintptr_t)&objects[0]);
  assert(native_lab_action_units[0][NATIVE_LAB_ACTION_LONG] ==
         (uintptr_t)&objects[1]);
  assert(native_lab_action_units[0][NATIVE_LAB_ACTION_SHOOT] ==
         (uintptr_t)&objects[3]);
  assert(native_lab_action_units[0][NATIVE_LAB_ACTION_GUIDE] ==
         (uintptr_t)&objects[26]);
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.context == PES_SETPLAY_GOAL_KICK);
  assert(debug.stock_mask == (PES_NATIVE_LAB_STOCK_MOBILE_KICK |
                              PES_NATIVE_LAB_STOCK_MOBILE_CAMERA |
                              PES_NATIVE_LAB_STOCK_GOALKICK_SUPPORT));
  assert(debug.route_mask == (PES_NATIVE_LAB_ROUTE_MOBILE_KICK_BRIDGE |
                              PES_NATIVE_LAB_ROUTE_SHORT_PASS |
                              PES_NATIVE_LAB_ROUTE_LONG_PASS |
                              PES_NATIVE_LAB_ROUTE_SHOOT |
                              PES_NATIVE_LAB_ROUTE_GOALKICK_SUPPORT |
                              PES_NATIVE_LAB_ROUTE_CAMERA_STICK |
                              PES_NATIVE_LAB_ROUTE_SETPLAY_GUIDE));
  assert(debug.trajectory_enabled == 1);
  assert((debug.status & (32u|64u)) == (32u|64u));
  pes_controller_native_pad_lab_debug_input(0, 0x15u, -1234, 2345,
                                             3456, -4567, 1);
  pes_controller_native_pad_lab_debug_input(1, 0x2au, 111, -222,
                                             -333, 444, 1);
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.buttons == 0x15u && debug.axis_x == -1234 &&
         debug.axis_y == 2345 && debug.right_axis_x == 3456 &&
         debug.right_axis_y == -4567 && debug.connected == 1);
  assert(debug.connected_mask == 3u && debug.buttons_p2 == 0x2au &&
         debug.axis_x_p2 == 111 && debug.axis_y_p2 == -222 &&
         debug.right_axis_x_p2 == -333 && debug.right_axis_y_p2 == 444);

  const uint32_t corner[] = {61,60,95,65,70,90,96};
  setup(); run(corner,7);
  const uint32_t expected_corner[] = {61,60,95,65,70,90,26,96};
  assert(*(uint32_t *)list == 8);
  assert(!memcmp(list+4, expected_corner, sizeof(expected_corner)));
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.trajectory_enabled == 1);
  assert(debug.context == PES_SETPLAY_CORNER);
  assert(debug.stock_mask == (PES_NATIVE_LAB_STOCK_MOBILE_KICK |
                              PES_NATIVE_LAB_STOCK_MOBILE_CAMERA |
                              PES_NATIVE_LAB_STOCK_SHORT_CORNER |
                              PES_NATIVE_LAB_STOCK_CORNER_TACTICS));
  assert(debug.route_mask == (PES_NATIVE_LAB_ROUTE_MOBILE_KICK_BRIDGE |
                              PES_NATIVE_LAB_ROUTE_SHORT_PASS |
                              PES_NATIVE_LAB_ROUTE_LONG_PASS |
                              PES_NATIVE_LAB_ROUTE_SHOOT |
                              PES_NATIVE_LAB_ROUTE_CAMERA_STICK |
                              PES_NATIVE_LAB_ROUTE_CORNER_TACTICS |
                              PES_NATIVE_LAB_ROUTE_SETPLAY_GUIDE));

  // The other local player's ordinary defensive list must not tear down the
  // corner owner. This used to clear the native helper every frame and the
  // following attacking update then cleared the frozen/charging gauge.
  native_lab_gauge_active_mask = 1u;
  native_lab_gauge_charging_mask = 0u;
  native_lab_gauge_power_milli_by_pad[0] = 800u;
  native_lab_gauge_linger_frames_by_pad[0] = 180u;
  *(uint32_t *)(input + 0x24) = 15;
  *(int32_t *)(cursor + 16) = 1;
  calls = 0;
  run(defence, 6);
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.context == PES_SETPLAY_CORNER);
  assert(debug.setplay_pad == 0u);
  assert(debug.gauge_active_mask & 1u);
  *(uint32_t *)(input + 0x24) = 4;
  *(int32_t *)(cursor + 16) = 0;
  calls = 0;
  run(corner, 7);
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.context == PES_SETPLAY_CORNER);
  assert(debug.gauge_active_mask & 1u);

  pes_controller_native_pad_lab_debug_input(0, 1u << 7, 0, 0, 0, 0, 1);
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.trajectory_enabled == 0); // Owner toggles the real trail off.
  pes_controller_native_pad_lab_debug_input(0, 0, 0, 0, 0, 0, 1);
  pes_controller_native_pad_lab_debug_input(0, 1u << 7, 0, 0, 0, 0, 1);
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.trajectory_enabled == 1);

  // The set-play owner's own ordinary list remains authoritative at action
  // end, so the helper cannot leak into open play.
  *(uint32_t *)(input + 0x24) = 4;
  *(int32_t *)(cursor + 16) = 0;
  calls = 0;
  run(defence, 6);
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.context == PES_SETPLAY_NONE);

  const uint32_t free_kick[] = {61,60,95,72,75,90,96};
  setup(); run(free_kick,7);
  const uint32_t expected_free_kick[] = {61,60,95,72,75,90,26,96};
  assert(*(uint32_t *)list == 8);
  assert(!memcmp(list+4, expected_free_kick, sizeof(expected_free_kick)));
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.context == PES_SETPLAY_FREE_KICK);
  assert(debug.stock_mask == (PES_NATIVE_LAB_STOCK_MOBILE_KICK |
                              PES_NATIVE_LAB_STOCK_MOBILE_CAMERA |
                              PES_NATIVE_LAB_STOCK_FREEKICK_TACTICS |
                              PES_NATIVE_LAB_STOCK_FREEKICK_POSITION));
  assert(debug.route_mask == (PES_NATIVE_LAB_ROUTE_MOBILE_KICK_BRIDGE |
                              PES_NATIVE_LAB_ROUTE_SHORT_PASS |
                              PES_NATIVE_LAB_ROUTE_LONG_PASS |
                              PES_NATIVE_LAB_ROUTE_SHOOT |
                              PES_NATIVE_LAB_ROUTE_CAMERA_STICK |
                              PES_NATIVE_LAB_ROUTE_FREEKICK_TACTICS |
                              PES_NATIVE_LAB_ROUTE_SETPLAY_GUIDE));
  pes_controller_native_pad_lab_publish_setplay_context(
      PES_SETPLAY_FREE_KICK);
  pes_controller_native_pad_lab_debug_input(1, 1u << 7, 0, 0, 0, 0, 1);
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  // Far free kicks intentionally expose no trajectory preview at all.
  assert(debug.trajectory_enabled == 0);

  // The close-range free-kick variant omits the tactics/position units. Its
  // semantic ButtonSetplay context is a guarded fallback only while kind 90
  // (MobileSetplayKick) is actually in the stock list.
  const uint32_t close_free_kick[] = {61,60,95,90,96};
  setup();
  pes_controller_native_pad_lab_publish_setplay_context(
      PES_SETPLAY_FREE_KICK);
  run(close_free_kick,5);
  const uint32_t expected_close_free_kick[] = {61,60,95,90,26,96};
  assert(*(uint32_t *)list == 6);
  assert(!memcmp(list+4, expected_close_free_kick,
                 sizeof(expected_close_free_kick)));
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.context == PES_SETPLAY_FREE_KICK);
  assert(debug.stock_mask == (PES_NATIVE_LAB_STOCK_MOBILE_KICK |
                              PES_NATIVE_LAB_STOCK_MOBILE_CAMERA));

  // MobileSetplayKick +0x38 contains our previous frame after write-back.
  // Holding a small LS-X offset must therefore reuse the separately captured
  // stock baseline instead of accumulating the offset and spinning each tick.
  const float stock_angle = 90.0f;
  int same_target = 0;
  const float first_base = native_lab_stable_setplay_base_angle(
      0, 4, stock_angle, &same_target);
  assert(!same_target && fabsf(first_base - stock_angle) < 0.0001f);
  native_lab_command_angle_valid_mask = 1u;
  const float overwritten_previous_frame = 12.5f;
  const float second_base = native_lab_stable_setplay_base_angle(
      0, 4, overwritten_previous_frame, &same_target);
  assert(same_target && fabsf(second_base - stock_angle) < 0.0001f);
  const float small_left_x = native_lab_normalize_axis(8192);
  const float first_angle = first_base - small_left_x * 60.0f;
  const float second_angle = second_base - small_left_x * 60.0f;
  assert(fabsf(first_angle - second_angle) < 0.0001f);

  // Variants that already contain a guide are normalized as well. A guide
  // before kind 90 could otherwise consume LS and mask the kick release.
  const uint32_t existing_guide[] = {61,60,95,26,90,96};
  setup();
  pes_controller_native_pad_lab_publish_setplay_context(
      PES_SETPLAY_FREE_KICK);
  run(existing_guide,6);
  assert(*(uint32_t *)list == 6);
  assert(!memcmp(list+4, expected_close_free_kick,
                 sizeof(expected_close_free_kick)));

  // Throw-ins use their dedicated body-angle unit. The reduced list can omit
  // MobileSetplayKick entirely and must still retain the semantic context.
  const uint32_t throw_in[] = {61,60,62,96};
  setup();
  pes_controller_native_pad_lab_publish_setplay_context(PES_SETPLAY_THROW_IN);
  run(throw_in,4);
  unchanged();
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.context == PES_SETPLAY_THROW_IN);
  assert(debug.route_mask & PES_NATIVE_LAB_ROUTE_THROWIN_AIM);

  const uint32_t throw_with_kick[] = {61,60,62,90,96};
  const uint32_t expected_throw_with_kick[] = {61,60,90,62,96};
  setup();
  pes_controller_native_pad_lab_publish_setplay_context(PES_SETPLAY_THROW_IN);
  run(throw_with_kick,5);
  assert(*(uint32_t *)list == 5);
  assert(!memcmp(list+4, expected_throw_with_kick,
                 sizeof(expected_throw_with_kick)));

  const uint32_t no_mobile_kick[] = {61,60,95,96};
  setup();
  pes_controller_native_pad_lab_publish_setplay_context(
      PES_SETPLAY_FREE_KICK);
  run(no_mobile_kick,4);
  unchanged();
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.context == PES_SETPLAY_NONE);

  setup(); active = 0; run(attack,6); unchanged(); // Exhibition.
  assert(pes_controller_native_pad_lab_status() == 0);
  setup(); two_player = 0; *(uint32_t *)(input+0x24) = 11;
  run(attack,6); unchanged(); // Away stays CPU outside the 2P lab.
  setup(); *(uint32_t *)(input+0x24) = 11; *(int32_t *)(cursor+16) = -1;
  run(attack,6); // Away is rewritten through native pad one in 2P lab.
  assert(*(uint32_t *)list == 7);
  assert(!memcmp(list+4, expected, sizeof(expected)));
  assert(*(int32_t *)(cursor+16) == 1);
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert((debug.accessor_bind_mask & 2u) &&
         (debug.route_player_mask & 2u));
  setup(); *(int32_t *)(cursor+16) = -1; run(attack,6);
  assert(*(int32_t *)(cursor+16) == 0); // Home ownership is repaired to P1.
  setup(); *(void **)(input+0x18) = NULL; run(attack,6); unchanged();
  setup(); objects[10] = 123; run(attack,6); unchanged(); // Unexpected ABI.
  assert(pes_controller_native_pad_lab_status() & 128);

  // Keep context scheduling; an idle/cinematic list must not gain move/shoot.
  const uint32_t cinematic[] = {28,29,94,95};
  setup(); run(cinematic,4); unchanged();
  const uint32_t duplicate[] = {0,78,79};
  setup(); run(duplicate,3);
  assert(*(uint32_t *)list == 4); // Short pass selected only once.
  const uint32_t invalid[] = {78,999};
  setup(); run(invalid,2); unchanged(); // No partial write.
  setup(); *(uint32_t *)list = 98; memcpy(before,list,sizeof(list));
  native_lab_list_update(list,input,61,7); unchanged();

  // Native sampler is forwarded, observed, NEVER fabricated or patched.
  setup(); history[0] = 1u << 14;
  uint32_t copy[5]; memcpy(copy,history,sizeof(copy));
  native_lab_sample(history,0,cursor,input);
  assert(sample_calls == 1 && (pes_controller_native_pad_lab_status() & 2));
  assert(prime_calls == 1);
  assert(!memcmp(history,copy,sizeof(copy)));
  native_pad_lab_reset();
  native_lab_sample(history,1,cursor,input);
  assert(pes_controller_native_pad_lab_status() & 2);
  assert(prime_calls == 2);
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.native_sample_mask == 2u && debug.prime_mask == 2u &&
         debug.native_keys_p2 == (1u << 14));
  const uint32_t latched_status = native_lab_status;
  active = 0; native_lab_sample(history,0,cursor,input);
  assert(native_lab_status == latched_status && sample_calls == 3);
  setup();
  float power = .75f, right_power = .625f;
  memcpy(history+2,&power,4);
  memcpy(history+4,&right_power,4);
  native_lab_sample(history,0,cursor,input);
  assert(pes_controller_native_pad_lab_status() & 2);
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert(debug.native_power_milli == 750);
  assert(debug.native_right_power_milli == 625);
  assert(debug.gauge_owner_pad == 0);
  assert(debug.gauge_power_milli == 0);

  // A normal-gameplay native press has no set-play active_action token. Its
  // independent charging bit must keep the per-pad gauge alive until release,
  // then the pad-local linger owns the final value.
  native_pad_lab_reset();
  active = 1;
  native_lab_gauge_active_mask = 1u;
  native_lab_gauge_charging_mask = 1u;
  native_lab_gauge_power_milli_by_pad[0] = 625u;
  native_lab_gauge_anchor_x_milli[0] = 640000;
  native_lab_gauge_anchor_y_milli[0] = 400000;
  native_lab_gauge_anchor_ttl[0] = 12u;
  pes_controller_native_pad_lab_debug_input(0, 0, 0, 0, 0, 0, 1);
  pes_controller_native_pad_lab_debug_snapshot(&debug);
  assert((debug.gauge_active_mask & 1u) &&
         (debug.gauge_anchor_valid_mask & 1u) &&
         debug.gauge_power_milli == 625u &&
         debug.gauge_anchor_x_milli == 640000);
  native_lab_gauge_charging_mask = 0;
  native_lab_gauge_linger_frames_by_pad[0] = 2u;
  pes_controller_native_pad_lab_debug_input(0, 0, 0, 0, 0, 0, 1);
  pes_controller_native_pad_lab_debug_input(0, 0, 0, 0, 0, 0, 1);
  assert(native_lab_gauge_active_mask & 1u);
  pes_controller_native_pad_lab_debug_input(0, 0, 0, 0, 0, 0, 1);
  assert(!(native_lab_gauge_active_mask & 1u));

  // Set-play releases use a longer cancellation guard so a far free-kick
  // taker's run-up cannot expire the bar before contact. Ordinary gameplay
  // keeps the shorter baseline guard.
  native_pad_lab_reset();
  native_lab_debug_context = PES_SETPLAY_FREE_KICK;
  assert(native_lab_gauge_release_linger() == 900u);
  native_pad_lab_reset();
  assert(native_lab_gauge_release_linger() == 180u);

  // Release freezes the gauge. Ball movement during a wind-up is not enough:
  // the ball must also separate from the nearest observed foot position for
  // three consecutive samples before the completed action removes the bar.
  native_lab_gauge_active_mask = 1u;
  native_lab_gauge_charging_mask = 0u;
  native_lab_gauge_power_milli_by_pad[0] = 800u;
  native_lab_gauge_linger_frames_by_pad[0] = 180u;
  native_lab_gauge_observe_released_ball(0, 10.0f, 0.0f, 20.0f,
                                         9.5f, 0.0f, 20.0f);
  assert(native_lab_gauge_active_mask & 1u);
  native_lab_gauge_observe_released_ball(0, 10.1f, 0.0f, 20.1f,
                                         9.6f, 0.0f, 20.1f);
  assert(native_lab_gauge_active_mask & 1u);
  native_lab_gauge_observe_released_ball(0, 10.4f, 0.0f, 20.0f,
                                         9.9f, 0.0f, 20.0f);
  assert(native_lab_gauge_active_mask & 1u);
  native_lab_gauge_observe_released_ball(0, 11.2f, 0.0f, 20.0f,
                                         10.0f, 0.0f, 20.0f);
  assert(native_lab_gauge_active_mask & 1u);
  native_lab_gauge_observe_released_ball(0, 11.3f, 0.0f, 20.0f,
                                         10.0f, 0.0f, 20.0f);
  assert(native_lab_gauge_active_mask & 1u);
  native_lab_gauge_observe_released_ball(0, 11.4f, 0.0f, 20.0f,
                                         10.0f, 0.0f, 20.0f);
  assert(!(native_lab_gauge_active_mask & 1u));
  puts("native-pad routing: pass (scope, types, actions, history, reset, bounds)");
  return 0;
}

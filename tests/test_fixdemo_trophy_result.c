#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "competition_frontend.h"

enum { FIXDEMO_TROPHY_PROPS_PENDING, FIXDEMO_TROPHY_PROPS_READY,
       FIXDEMO_TROPHY_PROPS_FAILED };
static int props_state, props_begin_ok = 1, final_ok = 1, fail_allocation;
static uint64_t props_epoch;
static unsigned creates, fallbacks, deletes, starts, ends, flows, cancels;
static unsigned status_polls, peek_polls, native_ready_calls;
static unsigned props_start_calls;
static unsigned ending_calls, match_fallbacks, read_locks, read_unlocks, active_reads;
static unsigned environment_calls;
static unsigned listener_calls, wait_calls, pre_calls, overview_started;
static int result_enabled, expire_during_create;
static uint64_t test_clock;
static uint32_t listener_scene, listener_side;
static uintptr_t listener_caller;
static int missing_ending_record;
static int fail_ordinary_allocation;
static unsigned char fade_memory[8], fade_table[0x50];
static void *fade_instance;
static unsigned fade_cancels, fade_phase;
static uint32_t ending_scene = 0x70004, ending_side = 0;
static uintptr_t ending_caller;
static char diagnostic_log[8192];
static int props_start_ok = 1;
static int expected_winner, invalidate_during_score;
static unsigned char owner_memory[0x200], candidate_memory[0x2a0], ordinary[0x2b8];
static unsigned char registry_memory[0x940], global_memory[0x5160];
static unsigned char match_memory[0x1330], record_memory[0x750cc + 2 * 0x4ba90];
static unsigned char listener_memory[0x1bc00];
static const void *expected_environment = (void *)(uintptr_t)0x2340;
static uint32_t expected_kind = 5, expected_category = 0;
static int playing_allowed;
static uint64_t scene_runtime_ms(void) { return test_clock; }

int competition_frontend_cup_live_final_context(CompetitionCupFinalContext *context) {
  memset(context, 0, sizeof(*context));
  if (!final_ok) return 0;
  context->native_home_team = 101; context->native_away_team = 107;
  return 1;
}
static uint32_t exhibition_native_team_id(uint32_t logical) {
  return logical == 101 ? 900u << 14 : logical == 107 ? 901u << 14 : 0;
}
static int fixdemo_trophy_props_begin(uint64_t epoch) {
  if (!props_begin_ok) return 0;
  props_epoch = epoch; return 1;
}
static int fixdemo_trophy_props_status(uint64_t epoch) {
  ++status_polls;
  return epoch == props_epoch ? props_state : FIXDEMO_TROPHY_PROPS_FAILED;
}
static int fixdemo_trophy_props_peek(uint64_t epoch) {
  ++peek_polls;
  return epoch == props_epoch ? props_state : FIXDEMO_TROPHY_PROPS_FAILED;
}
static int fixdemo_trophy_props_started(uint64_t epoch) {
  ++props_start_calls;
  return props_start_ok && epoch == props_epoch && props_state == FIXDEMO_TROPHY_PROPS_READY;
}
static void fixdemo_trophy_props_cancel(uint64_t epoch) {
  ++cancels;
  if (props_epoch == epoch) props_epoch = 0;
}
static void fixdemo_trophy_note(const char *message) {
  assert(message && *message);
  if (strlen(diagnostic_log) + strlen(message) + 2 < sizeof(diagnostic_log)) {
    strcat(diagnostic_log, message);
    strcat(diagnostic_log, "\n");
  }
}

#define PESNX_TROPHY_RESULT_TEST 1
#include "fixdemo_trophy_result.inc"

static void pointer(void *base, size_t offset, const void *value) {
  memcpy((unsigned char *)base + offset, &value, sizeof(value));
}
static void word(void *base, size_t offset, uint32_t value) {
  memcpy((unsigned char *)base + offset, &value, sizeof(value));
}
static const void *global_registry(void) { return global_memory; }
static const uint32_t *team_id(const void *stats, uint32_t side) {
  assert(stats == record_memory + 0x750cc && side < 2);
  return (const uint32_t *)((const unsigned char *)stats + side * 0x4ba90 + 0x28);
}
static const void *team_stats(const void *stats, uint32_t side) {
  assert(side < 2); return (const unsigned char *)stats + side * 0x4ba90;
}
static uint32_t score(const void *team, uint32_t half) {
  assert(half == 5 || half == 4);
  if (invalidate_during_score)
    __atomic_store_n(&fixdemo_trophy_live_token, 0, __ATOMIC_RELEASE);
  return fixdemo_trophy_word(team, half == 5 ? 0x100 : 0x104);
}
static void *match_create(uint32_t scene, uint32_t side) {
  assert(!active_reads && read_locks == read_unlocks);
  if (scene != 0x70007) {
    assert(scene == ending_scene && side == ending_side);
    ++match_fallbacks;
    return fail_ordinary_allocation ? NULL : ordinary;
  }
  assert(scene == 0x70007 && side == (uint32_t)expected_winner);
  if (expire_during_create) {
    test_clock += 60001;
    assert(!fixdemo_trophy_pre_result((void *)(uintptr_t)0x5550));
    assert(fixdemo_trophy_ui_active() && !overview_started && result_enabled);
  }
  ++creates; return fail_allocation ? NULL : candidate_memory;
}
static void *result_create(uint32_t scene, uint32_t side) {
  assert(scene == 0x80001 && side <= 2); ++fallbacks;
  return fail_ordinary_allocation ? NULL : ordinary;
}
static void create_owner(void *owner, const void *registry, const void *environment,
                          uint32_t kind, uint32_t category) {
  assert(owner == owner_memory && registry == registry_memory);
  assert(environment == expected_environment && kind == expected_kind && category == expected_category);
  assert(fixdemo_trophy_result_scope && fixdemo_trophy_result_scope->registry == registry);
  void *result = fixdemo_trophy_result_at(0x80001, 2, fixdemo_trophy_result_caller);
  pointer(owner, 0x1e0, result);
}
static void delete_manager(void *manager) {
  assert(manager == candidate_memory);
  assert(props_epoch == 0); /* cancellation precedes native deletion */
  ++deletes;
}
static void start_manager(void *manager) { assert(manager == candidate_memory); ++starts; }
static void end_manager(void *manager) { assert(manager == candidate_memory); ++ends; }
static int cut_ready(void *manager, void *cut, uint32_t number, uint32_t first) {
  (void)manager; (void)cut; (void)number; (void)first;
  ++native_ready_calls; return 1;
}
static void read_lock(void *base, void **destination) {
  assert(destination != (void **)(listener_memory + 0x1b338));
  assert(destination != (void **)(listener_memory + 0x1b9c8));
  if (base == listener_memory + 0x1b308) {
    assert(!(active_reads & 1u)); active_reads |= 1u;
    *destination = match_memory;
  } else {
    assert(base == listener_memory + 0x1b998 && !(active_reads & 2u));
    active_reads |= 2u;
    *destination = missing_ending_record ? NULL : record_memory;
  }
  ++read_locks;
}
static void read_unlock(void *base) {
  const unsigned bit = base == listener_memory + 0x1b308 ? 1u : 2u;
  assert(bit == 1u || base == listener_memory + 0x1b998);
  assert(active_reads & bit); active_reads &= ~bit;
  ++read_unlocks;
}
static void set_environment(void *listener) {
  assert(listener == listener_memory && !active_reads);
  ++environment_calls;
}
static int cancel_base_fade(void *fade, uint32_t level) {
  assert(fade == fade_memory && level == 1); ++fade_cancels;
  fade_phase = 0; return 1;
}
static int cancel_mobile_fade(void *fade, uint32_t level) {
  return cancel_base_fade(fade, level);
}
static int base_fade_end(void *fade, uint32_t level) {
  assert(fade == fade_memory && level == 1); return 1;
}
static int mobile_fade_end(void *fade, uint32_t level) {
  assert(fade == fade_memory && level == 1); return fade_phase == 0 || fade_phase == 2;
}
static void set_step(void *listener, uint8_t step) {
  assert(listener == listener_memory);
  if (step == 6) {
    assert(!fixdemo_trophy_pointer(listener, 0x19018));
    assert(!fade_instance || (fade_phase == 0 && fade_cancels == 1));
  } else if (step == 1) {
    assert(fixdemo_trophy_pointer(listener, 0x19018) == ordinary && !props_epoch);
  } else {
    assert(step == 3 && !fixdemo_trophy_pointer(listener, 0x19018));
    assert(listener_memory[0x11c] == 1 && !fade_cancels);
  }
  listener_memory[0x119] = (unsigned char)step;
}
static void wait_result(void *listener, const void *context) {
  assert(listener == listener_memory && context == (void *)(uintptr_t)0x4440);
  ++wait_calls;
  if (listener_memory[0x118] && listener_memory[0x118] != 21 &&
      !listener_memory[0x18ff2] && listener_memory[0x18ff0] && listener_memory[0x18ff3]) {
    /* The native event flag is published before MatchTop next dispatches19. */
    result_enabled = 1;
    listener_memory[0x18ff2] = 1;
    listener_memory[0x118] = 19;
  }
}
static uint32_t pre_result(void *process) {
  assert(process == (void *)(uintptr_t)0x5550);
  ++pre_calls;
  if (!result_enabled) return 0;
  result_enabled = 0;
  ++overview_started;
  return 1;
}
static void listener_result(void *listener, const void *context) {
  assert(listener == listener_memory && context == (void *)(uintptr_t)0x4440);
  assert(fixdemo_trophy_listener_scope && fixdemo_trophy_listener_scope->listener == listener);
  ++listener_calls;
  const unsigned step = listener_memory[0x119];
  if (!step) {
    set_environment(listener);
    pointer(listener, 0x19018, fixdemo_trophy_result_at(listener_scene, listener_side, listener_caller));
    listener_memory[0x119] = 1;
  } else if (step == 1 || step == 2) {
    void *manager = fixdemo_trophy_pointer(listener, 0x19018);
    assert(manager); /* The native loader's unguarded read must never see NULL. */
    if (manager == candidate_memory) {
      if (candidate_memory[0x55]) {
        word(candidate_memory, 0x1dc, 4);
      } else {
        playing_allowed = fixdemo_trophy_cut_ready(manager, NULL, 0, 1);
        if (playing_allowed) {
          candidate_memory[0x54] = 1;
          listener_memory[0x119] = 2;
          if (!fixdemo_trophy_started) fixdemo_trophy_start(manager);
        }
      }
    } else {
      assert(manager == ordinary);
      ordinary[0x54] = 1;
      listener_memory[0x119] = 2;
    }
  } else if (step == 3) {
    assert(listener_memory[0x11c] == 1);
    listener_memory[0x119] = 5;
  } else {
    assert(step == 5 && !fixdemo_trophy_pointer(listener, 0x19018));
    assert(listener_memory[0x11c] == 1);
    listener_memory[0x118] = 17;
  }
}
static void ending(void *listener, const void *context) {
  assert(listener == listener_memory && context == (void *)(uintptr_t)0x4440);
  assert(fixdemo_trophy_ending_scope && fixdemo_trophy_ending_scope->listener == listener);
  ++ending_calls;
  if (!listener_memory[0x119]) {
    set_environment(listener);
    pointer(listener, 0x19018, fixdemo_trophy_match_at(ending_scene, ending_side, ending_caller));
    listener_memory[0x119] = 1;
  } else if (!fixdemo_trophy_pointer(listener, 0x19018)) {
    assert(listener_memory[0x119] == 6 || listener_memory[0x119] == 7);
    if (listener_memory[0x119] == 6) listener_memory[0x119] = 7;
    else listener_memory[0x118] = 19;
  } else if (fixdemo_trophy_pointer(listener, 0x19018) == candidate_memory) {
    playing_allowed = fixdemo_trophy_cut_ready(candidate_memory, NULL, 0, 1);
    if (playing_allowed && !fixdemo_trophy_started && !candidate_memory[0x55])
      fixdemo_trophy_start(candidate_memory);
  }
}
static void flow(void *owner, void *info, uint32_t active, const void *context) {
  assert(owner == owner_memory && info == (void *)(uintptr_t)0x1110);
  assert(active == 1 && context == (void *)(uintptr_t)0x3330);
  ++flows;
  if (fixdemo_trophy_pointer(owner, 0x1e0) == candidate_memory) {
    playing_allowed = fixdemo_trophy_cut_ready(candidate_memory, NULL, 0, 1);
    if (playing_allowed && !fixdemo_trophy_started) fixdemo_trophy_start(candidate_memory);
  }
}
static void configure(void) {
  fixdemo_trophy_create_original = create_owner;
  fixdemo_trophy_flow_original = flow;
  fixdemo_trophy_ending_original = ending;
  fixdemo_trophy_listener_original = listener_result;
  fixdemo_trophy_wait_result_original = wait_result;
  fixdemo_trophy_pre_result_original = pre_result;
  fixdemo_trophy_set_environment = set_environment;
  fixdemo_trophy_set_step = set_step;
  fixdemo_trophy_fade_instance = &fade_instance;
  fixdemo_trophy_fade_cancel[0] = (uintptr_t)cancel_base_fade;
  fixdemo_trophy_fade_cancel[1] = (uintptr_t)cancel_mobile_fade;
  fixdemo_trophy_fade_is_end[0] = (uintptr_t)base_fade_end;
  fixdemo_trophy_fade_is_end[1] = (uintptr_t)mobile_fade_end;
  fixdemo_trophy_read_lock = read_lock;
  fixdemo_trophy_read_unlock = read_unlock;
  fixdemo_trophy_result_original = result_create;
  fixdemo_trophy_match_original = match_create;
  fixdemo_trophy_global_registry = global_registry;
  fixdemo_trophy_stats_team_id = team_id;
  fixdemo_trophy_stats_team = team_stats;
  fixdemo_trophy_score = score;
  fixdemo_trophy_cut_ready_original = cut_ready;
  fixdemo_trophy_delete_original = delete_manager;
  fixdemo_trophy_destruct_original = delete_manager;
  fixdemo_trophy_start_original = start_manager;
  fixdemo_trophy_end_original = end_manager;
  fixdemo_trophy_result_caller = 0x620c1a4;
  fixdemo_trophy_ending_caller = 0x7bf3c78;
  fixdemo_trophy_listener_caller = 0x7bf3340;
  fixdemo_trophy_result_installed = 1;
  (void)&fixdemo_trophy_result_create;
  (void)&fixdemo_trophy_match_create;
}
static void reset_case(void) {
  fixdemo_trophy_end_match();
  memset(owner_memory, 0, sizeof(owner_memory));
  memset(candidate_memory, 0, sizeof(candidate_memory));
  memset(ordinary, 0, sizeof(ordinary));
  memset(registry_memory, 0, sizeof(registry_memory));
  memset(global_memory, 0, sizeof(global_memory));
  memset(listener_memory, 0, sizeof(listener_memory));
  memset(match_memory, 0, sizeof(match_memory));
  memset(diagnostic_log, 0, sizeof(diagnostic_log));
  memset(record_memory, 0, sizeof(record_memory));
  pointer(registry_memory, 0x1d0, record_memory);
  pointer(global_memory, 0x4f0, match_memory);
  registry_memory[0x939] = global_memory[0x5150] = 1;
  word(match_memory, 0x1168, 10);
  ending_scene = 0x70004; ending_side = 0;
  word(match_memory, 0x1324, ending_scene); word(match_memory, 0x1328, ending_side);
  listener_memory[0x1b300] = listener_memory[0x1b990] = 1;
  pointer(listener_memory, 0x1b338, (void *)(uintptr_t)0xdead0001);
  pointer(listener_memory, 0x1b9c8, (void *)(uintptr_t)0xdead0002);
  ending_caller = fixdemo_trophy_ending_caller;
  listener_caller = fixdemo_trophy_listener_caller;
  listener_scene = 0x80001; listener_side = 2;
  word(match_memory, 0x132c, listener_side);
  listener_calls = wait_calls = pre_calls = overview_started = 0;
  result_enabled = expire_during_create = 0; test_clock = 100;
  ending_calls = match_fallbacks = read_locks = read_unlocks = active_reads = 0;
  environment_calls = missing_ending_record = 0;
  fail_ordinary_allocation = 0;
  fade_instance = fade_memory; fade_cancels = 0; fade_phase = 3;
  pointer(fade_memory, 0, fade_table);
  pointer(fade_table, 0x20, (const void *)(uintptr_t)cancel_mobile_fade);
  pointer(fade_table, 0x48, (const void *)(uintptr_t)mobile_fade_end);
  void *home = record_memory + 0x750cc, *away = record_memory + 0x750cc + 0x4ba90;
  word(home, 0x28, 900u << 14); word(away, 0x28, 901u << 14);
  word(home, 0x100, 2); word(away, 0x100, 1);
  final_ok = props_begin_ok = props_start_ok = 1;
  fail_allocation = invalidate_during_score = expected_winner = playing_allowed = 0;
  props_state = FIXDEMO_TROPHY_PROPS_PENDING;
  creates = fallbacks = deletes = starts = ends = flows = cancels = 0;
  status_polls = peek_polls = native_ready_calls = 0;
  props_start_calls = 0;
  fixdemo_trophy_begin_match();
}
static void create(void) {
  fixdemo_trophy_create(owner_memory, registry_memory, expected_environment,
                        expected_kind, expected_category);
  assert(fixdemo_trophy_result_scope == NULL); /* no borrowed pointer escapes */
}
static void run_frame(void) {
  fixdemo_trophy_flow(owner_memory, (void *)(uintptr_t)0x1110, 1,
                      (void *)(uintptr_t)0x3330);
}
static void run_ending(void) {
  fixdemo_trophy_ending(listener_memory, (void *)(uintptr_t)0x4440);
  assert(fixdemo_trophy_ending_scope == NULL);
  assert(!active_reads && read_locks == read_unlocks);
  assert(fixdemo_trophy_pointer(listener_memory, 0x1b338) == (void *)(uintptr_t)0xdead0001);
  assert(fixdemo_trophy_pointer(listener_memory, 0x1b9c8) == (void *)(uintptr_t)0xdead0002);
}
static void arm_listener(void) {
  listener_memory[0x118] = 14;
  listener_memory[0x18ff0] = listener_memory[0x18ff3] = 1;
  fixdemo_trophy_wait_result(listener_memory, (void *)(uintptr_t)0x4440);
}
static void run_listener(void) {
  fixdemo_trophy_listener(listener_memory, (void *)(uintptr_t)0x4440);
  assert(fixdemo_trophy_listener_scope == NULL);
  assert(!active_reads && read_locks == read_unlocks);
  assert(fixdemo_trophy_pointer(listener_memory, 0x1b338) == (void *)(uintptr_t)0xdead0001);
  assert(fixdemo_trophy_pointer(listener_memory, 0x1b9c8) == (void *)(uintptr_t)0xdead0002);
}
static uint32_t run_pre_result(void) {
  return fixdemo_trophy_pre_result((void *)(uintptr_t)0x5550);
}

static void check_listener_result(void) {
  reset_case(); arm_listener();
  assert(fixdemo_trophy_ui_active() && result_enabled && !overview_started);
  assert(strstr(diagnostic_log, "wait-result-entry token="));
  assert(strstr(diagnostic_log, "before-native-result-enable"));
  assert(!run_pre_result() && !pre_calls && result_enabled);
  run_listener();
  assert(creates == 1 && !fallbacks && read_locks == 4);
  assert(fixdemo_trophy_owner_kind == FIXDEMO_TROPHY_OWNER_LISTENER_RESULT);
  assert(fixdemo_trophy_pointer(listener_memory, 0x19018) == candidate_memory);
  assert(!fixdemo_trophy_pointer(listener_memory, 0x1e0));
  for (int i = 0; i != 30; ++i) { run_listener(); assert(!run_pre_result()); }
  assert(!starts && !overview_started && read_locks == 4);
  props_state = FIXDEMO_TROPHY_PROPS_READY; run_listener();
  assert(starts == 1 && fixdemo_trophy_latch.consumed && candidate_memory[0x54]);
  props_state = FIXDEMO_TROPHY_PROPS_PENDING; run_listener();
  assert(playing_allowed && !deletes && !run_pre_result());
  fixdemo_trophy_end(candidate_memory); run_listener();
  assert(ends == 1 && deletes == 1 && fallbacks == 1 && environment_calls == 2);
  assert(fixdemo_trophy_pointer(listener_memory, 0x19018) == ordinary);
  assert(ordinary[0x54] && listener_memory[0x118] == 19 && !fade_cancels);
  assert(!fixdemo_trophy_ui_active() && !fixdemo_trophy_request_skip());
  assert(run_pre_result() && overview_started == 1 && !result_enabled);
  run_listener(); assert(!run_pre_result() && deletes == 1 && creates == 1);

  /* The shared native listener remains ordinary at halftime, even when this
   * match is the bracket's final. Its END10 call can arm later in that token. */
  reset_case(); word(match_memory, 0x1168, 2); arm_listener();
  assert(!fixdemo_trophy_ui_active());
  run_listener(); assert(!creates && fallbacks == 1 && run_pre_result());
  listener_memory[0x119] = listener_memory[0x18ff2] = 0;
  pointer(listener_memory, 0x19018, NULL); word(match_memory, 0x1168, 10);
  arm_listener(); run_listener(); assert(creates == 1 && fixdemo_trophy_ui_active());

  /* Every non-END phase and missing final/identity/registry input fails closed. */
  for (uint32_t phase = 0; phase != 12; ++phase) {
    if (phase == 10) continue;
    reset_case(); word(match_memory, 0x1168, phase); arm_listener(); run_listener();
    assert(!creates && !fixdemo_trophy_ui_active() && fallbacks == 1 && run_pre_result());
  }
  for (int bad = 0; bad != 10; ++bad) {
    reset_case();
    if (bad == 0) final_ok = 0;
    if (bad == 1) listener_memory[0x1b300] = 0;
    if (bad == 2) listener_memory[0x1b990] = 0;
    if (bad == 3) word(record_memory + 0x750cc, 0x28, 101);
    if (bad == 4) word(record_memory + 0x750cc, 0x100, 1);
    if (bad == 5) word(match_memory, 0x132c, 3);
    if (bad == 6) missing_ending_record = 1;
    if (bad == 7) invalidate_during_score = 1;
    if (bad == 8) fixdemo_trophy_end_match();
    if (bad == 9) word(record_memory + 0x750cc, 0x104, 100);
    arm_listener(); run_listener();
    assert(!creates && !fixdemo_trophy_ui_active() && fallbacks == 1 && run_pre_result());
  }

  /* Readiness reporting is bounded but distinguishes entry from readiness. */
  reset_case();
  fixdemo_trophy_wait_result(listener_memory, (void *)(uintptr_t)0x4440);
  const size_t first_log = strlen(diagnostic_log);
  for (int i = 0; i != 50; ++i)
    fixdemo_trophy_wait_result(listener_memory, (void *)(uintptr_t)0x4440);
  assert(strlen(diagnostic_log) == first_log && !read_locks);
  arm_listener(); assert(strlen(diagnostic_log) > first_log && fixdemo_trophy_ui_active());
  const size_t ready_log = strlen(diagnostic_log);
  for (int i = 0; i != 50; ++i)
    fixdemo_trophy_wait_result(listener_memory, (void *)(uintptr_t)0x4440);
  assert(strlen(diagnostic_log) == ready_log);
  for (int bad = 0; bad != 5; ++bad) {
    reset_case();
    listener_memory[0x118] = 14;
    listener_memory[0x18ff0] = listener_memory[0x18ff3] = 1;
    if (bad == 0) listener_memory[0x118] = 0;
    if (bad == 1) listener_memory[0x118] = 21;
    if (bad == 2) listener_memory[0x18ff2] = 1;
    if (bad == 3) listener_memory[0x18ff0] = 0;
    if (bad == 4) listener_memory[0x18ff3] = 0;
    fixdemo_trophy_wait_result(listener_memory, (void *)(uintptr_t)0x4440);
    assert(!fixdemo_trophy_ui_active() && !read_locks && !result_enabled);
  }

  /* Invocation provenance remains mandatory and the native requested side
   * is independently verified; a selected side never determines the winner. */
  reset_case();
  assert(fixdemo_trophy_result_at(0x80001, 2, fixdemo_trophy_listener_caller) == ordinary);
  assert(!creates && !read_locks);
  for (uint32_t side = 0; side != 3; ++side) {
    reset_case(); listener_side = side; word(match_memory, 0x132c, side);
    word(record_memory + 0x750cc, 0x100, 0); expected_winner = 1;
    arm_listener(); run_listener(); assert(creates == 1);
  }
  reset_case(); arm_listener(); word(match_memory, 0x132c, 1); run_listener();
  assert(!creates && fallbacks == 1 && !fixdemo_trophy_ui_active() && run_pre_result());
  reset_case(); arm_listener(); listener_caller -= 4; run_listener();
  assert(!creates && fallbacks == 1); /* unknown caller cannot opt into the scene */
  test_clock += 60001; assert(run_pre_result()); /* no factory: bounded fail-open */
  reset_case(); arm_listener(); final_ok = 0; run_listener();
  assert(!creates && fallbacks == 1 && run_pre_result()); /* revalidate at factory */
  reset_case();
  word(record_memory + 0x750cc, 0x100, 1);
  word(record_memory + 0x750cc, 0x104, 3);
  word(record_memory + 0x750cc + 0x4ba90, 0x104, 4);
  expected_winner = 1; arm_listener(); run_listener(); assert(creates == 1);

  /* Both time and poll bounds release an absent factory, then reject a late
   * factory. If native allocation has claimed the token, owner cleanup wins. */
  for (int use_time = 0; use_time != 2; ++use_time) {
    reset_case(); arm_listener();
    if (use_time) test_clock += 60001;
    else __atomic_store_n(&fixdemo_trophy_ui_polls, 3600u, __ATOMIC_RELAXED);
    assert(run_pre_result() && !fixdemo_trophy_ui_active());
    run_listener(); assert(!creates && fallbacks == 1);
  }
  reset_case(); arm_listener(); expire_during_create = 1; run_listener();
  assert(creates == 1 && !overview_started && fixdemo_trophy_ui_active());
  run_listener(); assert(deletes == 1 && fallbacks == 1 && run_pre_result());
  reset_case(); arm_listener(); test_clock += 60001;
  assert(run_pre_result()); fail_ordinary_allocation = 1; run_listener();
  assert(!creates && fallbacks == 1 && !fixdemo_trophy_pointer(listener_memory, 0x19018));
  const unsigned expired_calls = listener_calls;
  run_listener(); assert(listener_calls == expired_calls);
  listener_memory[0x11c] = 1; run_listener(); run_listener();
  assert(listener_memory[0x118] == 17 && !deletes && !fade_cancels);

  /* Skip is published by input as a token and applied on the owner queue. */
  reset_case(); assert(!fixdemo_trophy_request_skip()); arm_listener();
  assert(fixdemo_trophy_request_skip()); run_listener();
  assert(!creates && fallbacks == 1 && run_pre_result());
  for (int after_start = 0; after_start != 2; ++after_start) {
    reset_case(); arm_listener(); run_listener();
    if (after_start) { props_state = FIXDEMO_TROPHY_PROPS_READY; run_listener(); }
    assert(fixdemo_trophy_request_skip() && !candidate_memory[0x55]);
    run_listener(); assert(candidate_memory[0x55] && !deletes && !run_pre_result());
    run_listener(); assert(deletes == 1 && fallbacks == 1 && run_pre_result());
  }

  /* Rejections, loader failures, later failures and NULL ordinary backgrounds
   * all keep the native result UI/close lifecycle, never Ending's steps6/7. */
  for (int fail = 0; fail != 5; ++fail) {
    reset_case(); arm_listener();
    if (fail == 0) fail_allocation = 1;
    if (fail == 1) props_begin_ok = 0;
    run_listener();
    if (fail >= 2) {
      if (fail == 3) { props_state = FIXDEMO_TROPHY_PROPS_READY; run_listener(); }
      if (fail == 4) { props_state = FIXDEMO_TROPHY_PROPS_READY; props_start_ok = 0; run_listener(); }
      else props_state = FIXDEMO_TROPHY_PROPS_FAILED;
      run_listener();
    }
    assert(!fixdemo_trophy_ui_active() && fallbacks == 1 && run_pre_result());
    assert(deletes == (fail >= 2 ? 1u : 0u) && !fade_cancels);
  }
  for (int initial_null = 0; initial_null != 2; ++initial_null) {
    reset_case(); arm_listener();
    fail_allocation = initial_null; fail_ordinary_allocation = 1;
    run_listener();
    if (!initial_null) { props_state = FIXDEMO_TROPHY_PROPS_FAILED; run_listener(); }
    assert(!fixdemo_trophy_ui_active() && !fixdemo_trophy_pointer(listener_memory, 0x19018));
    assert(run_pre_result() && overview_started == 1);
    const unsigned before = listener_calls;
    for (int i = 0; i != 10; ++i) run_listener();
    assert(listener_calls == before && listener_memory[0x118] == 19);
    listener_memory[0x11c] = 1; run_listener();
    assert(listener_memory[0x119] == 5); run_listener();
    assert(listener_memory[0x118] == 17 && !fade_cancels);
    assert(deletes == (initial_null ? 0u : 1u));
  }
  reset_case(); arm_listener(); run_listener();
  pointer(listener_memory, 0x19018, ordinary); run_listener();
  assert(!fixdemo_trophy_manager && !props_epoch && !deletes && run_pre_result());
  reset_case(); arm_listener(); run_listener(); const uint64_t old = fixdemo_trophy_live_token;
  fixdemo_trophy_end_match(); assert(!fixdemo_trophy_ui_active() && !deletes);
  fixdemo_trophy_begin_match(); assert(fixdemo_trophy_live_token > old && !fixdemo_trophy_request_skip());
}

static void check_ending(void) {
  reset_case(); run_ending();
  assert(creates == 1 && !fallbacks && !match_fallbacks && read_locks == 2);
  assert(fixdemo_trophy_owner_kind == FIXDEMO_TROPHY_OWNER_ENDING);
  assert(fixdemo_trophy_pointer(listener_memory, 0x19018) == candidate_memory);
  assert(!fixdemo_trophy_pointer(listener_memory, 0x1e0));
  assert(strstr(diagnostic_log, "match-token-begin token="));
  assert(strstr(diagnostic_log, "ending-entry token="));
  assert(strstr(diagnostic_log, "factory-snapshot boundary=1"));
  for (int i = 0; i != 30; ++i) run_ending();
  assert(read_locks == 2 && !starts); /* capture once, never cached in frame loop */
  const size_t logged = strlen(diagnostic_log);
  for (int i = 0; i != 30; ++i) run_ending();
  assert(strlen(diagnostic_log) == logged); /* no per-frame log I/O */
  props_state = FIXDEMO_TROPHY_PROPS_READY; run_ending();
  assert(starts == 1 && fixdemo_trophy_latch.consumed);
  assert(!fade_cancels); /* success never cancels a native fade */
  props_state = FIXDEMO_TROPHY_PROPS_PENDING; run_ending();
  assert(playing_allowed && !deletes);
  fixdemo_trophy_end(candidate_memory); fixdemo_trophy_delete(candidate_memory);
  assert(ends == 1 && deletes == 1 && !props_epoch);

  for (unsigned permission = 0; permission != 4; ++permission) {
    reset_case(); ending_scene = 0x6000f; ending_side = 1;
    word(match_memory, 0x1324, ending_scene); word(match_memory, 0x1328, ending_side);
    run_ending();
    candidate_memory[0x54] = (unsigned char)(permission & 1);
    candidate_memory[0x55] = (unsigned char)(permission >> 1);
    listener_memory[0x119] = 6;
    props_state = FIXDEMO_TROPHY_PROPS_FAILED;
    fixdemo_trophy_watch_owner(listener_memory, FIXDEMO_TROPHY_OWNER_FLOW, 0x1e0);
    assert(!deletes && fixdemo_trophy_manager == candidate_memory);
    run_ending();
    assert(deletes == 1 && match_fallbacks == 1 && !fallbacks && environment_calls == 2);
    assert(fixdemo_trophy_pointer(listener_memory, 0x19018) == ordinary);
    assert(listener_memory[0x119] == 6);
    assert(ordinary[0x54] == (permission & 1) && ordinary[0x55] == (permission >> 1));
    run_ending(); assert(deletes == 1 && match_fallbacks == 1);
  }
  reset_case(); run_ending(); props_state = FIXDEMO_TROPHY_PROPS_READY; run_ending();
  props_state = FIXDEMO_TROPHY_PROPS_FAILED; run_ending();
  assert(deletes == 1 && match_fallbacks == 1 && fixdemo_trophy_latch.consumed);

  for (int bad = 0; bad != 12; ++bad) {
    reset_case();
    if (bad == 0) listener_memory[0x1b300] = 0;
    if (bad == 1) listener_memory[0x1b990] = 0;
    if (bad == 2) final_ok = 0;
    if (bad == 3) word(match_memory, 0x1324, 0x60008);
    if (bad == 4) word(match_memory, 0x1328, 2);
    if (bad == 5) word(match_memory, 0x1168, 9);
    if (bad == 6) word(record_memory + 0x750cc, 0x28, 101);
    if (bad == 7) word(record_memory + 0x750cc, 0x100, 1);
    if (bad == 8) invalidate_during_score = 1;
    if (bad == 9) missing_ending_record = 1;
    if (bad == 10) ending_caller -= 4;
    if (bad == 11) fixdemo_trophy_end_match();
    run_ending();
    assert(!creates && match_fallbacks == 1 && !fallbacks && !active_reads);
    if (bad == 2) assert(strstr(diagnostic_log, "ending-rejected no-live-cup-final"));
    if (bad == 11) assert(strstr(diagnostic_log, "ending-rejected match-lifetime"));
  }
  reset_case();
  assert(fixdemo_trophy_match_at(ending_scene, ending_side, ending_caller) == ordinary);
  assert(!creates && !read_locks); /* correct PC without invocation scope is insufficient */
  reset_case(); fail_allocation = 1; run_ending();
  assert(creates == 1 && match_fallbacks == 1 && cancels == 1);
  reset_case(); fail_allocation = fail_ordinary_allocation = 1; run_ending();
  assert(creates == 1 && match_fallbacks == 1 && !fixdemo_trophy_manager);
  assert(listener_memory[0x119] == 6 && !fixdemo_trophy_pointer(listener_memory, 0x19018));
  run_ending(); assert(listener_memory[0x119] == 7);
  run_ending(); assert(listener_memory[0x118] == 19 && !deletes);
  reset_case(); run_ending(); fail_ordinary_allocation = 1;
  props_state = FIXDEMO_TROPHY_PROPS_FAILED; run_ending();
  assert(deletes == 1 && match_fallbacks == 1 && listener_memory[0x119] == 7);
  run_ending(); assert(listener_memory[0x118] == 19 && deletes == 1);
  for (int variant = 0; variant != 2; ++variant) {
    reset_case(); fail_allocation = fail_ordinary_allocation = 1;
    if (!variant) {
      pointer(fade_table, 0x20, (const void *)(uintptr_t)cancel_base_fade);
      pointer(fade_table, 0x48, (const void *)(uintptr_t)base_fade_end);
    } else {
      fade_instance = NULL;
    }
    run_ending(); assert(listener_memory[0x119] == 6);
    assert(fade_cancels == (variant ? 0u : 1u));
  }
  reset_case(); props_begin_ok = 0; run_ending();
  assert(!creates && match_fallbacks == 1);
  reset_case();
  word(record_memory + 0x750cc, 0x100, 1);
  word(record_memory + 0x750cc, 0x104, 3);
  word(record_memory + 0x750cc + 0x4ba90, 0x104, 4);
  expected_winner = 1; run_ending(); assert(creates == 1);
  reset_case(); run_ending(); pointer(listener_memory, 0x19018, ordinary);
  run_ending(); assert(!deletes && !fixdemo_trophy_manager && !props_epoch);
}

int main(void) {
  configure();
  reset_case(); create();
  assert(creates == 1 && fallbacks == 0 && !fixdemo_trophy_latch.consumed);
  run_frame(); assert(!playing_allowed && !starts && status_polls == 1);
  props_state = FIXDEMO_TROPHY_PROPS_READY; run_frame();
  assert(playing_allowed && starts == 1 && fixdemo_trophy_latch.consumed);
  fixdemo_trophy_end(candidate_memory); assert(ends == 1);
  fixdemo_trophy_delete(candidate_memory);
  assert(deletes == 1 && !fixdemo_trophy_manager && !props_epoch);
  create(); assert(fallbacks == 1 && creates == 1); /* one-shot same token */

  reset_case();
  word(record_memory + 0x750cc, 0x100, 1);
  word(record_memory + 0x750cc, 0x104, 3);
  word(record_memory + 0x750cc + 0x4ba90, 0x104, 4);
  expected_winner = 1; create(); assert(creates == 1); /* PK-only winner */
  fixdemo_trophy_destruct(candidate_memory); assert(!props_epoch && deletes == 1);

  for (uint32_t phase = 0; phase <= 11; ++phase) {
    if (phase == 10) continue;
    reset_case(); word(match_memory, 0x1168, phase); create();
    assert(!creates && fallbacks == 1);
  }
  for (int bad = 0; bad != 7; ++bad) {
    reset_case();
    if (bad == 0) registry_memory[0x939] = 0;
    if (bad == 1) global_memory[0x5150] = 0;
    if (bad == 2) word(record_memory + 0x750cc, 0x28, 101); /* logical!=physical */
    if (bad == 3) final_ok = 0;
    if (bad == 4) word(record_memory + 0x750cc, 0x100, 1); /* tied/no PK */
    if (bad == 5) invalidate_during_score = 1;
    if (bad == 6) pointer(registry_memory, 0x1d0, NULL);
    create(); assert(!creates && fallbacks == 1);
  }
  reset_case();
  FixdemoTrophyResultScope scope = {owner_memory, registry_memory, fixdemo_trophy_live_token};
  fixdemo_trophy_result_scope = &scope;
  assert(fixdemo_trophy_result_at(0x80001, 2, 0x7bf3340) == ordinary); /* half-time */
  scope.token--;
  assert(fixdemo_trophy_result_at(0x80001, 2, fixdemo_trophy_result_caller) == ordinary);
  fixdemo_trophy_result_scope = NULL;
  assert(!creates && fallbacks == 2);

  reset_case(); fail_allocation = 1; create();
  assert(creates == 1 && fallbacks == 1 && cancels == 1 && !fixdemo_trophy_latch.consumed);
  reset_case(); props_begin_ok = 0; create(); assert(!creates && fallbacks == 1);

  reset_case(); create(); props_state = FIXDEMO_TROPHY_PROPS_FAILED; run_frame();
  assert(deletes == 1 && fallbacks == 1 && flows == 1 && !fixdemo_trophy_latch.consumed);
  assert(fixdemo_trophy_pointer(owner_memory, 0x1e0) == ordinary);
  run_frame(); assert(deletes == 1 && fallbacks == 1); /* no duplicate teardown */

  for (unsigned permission = 0; permission != 4; ++permission) {
    reset_case(); create();
    candidate_memory[0x54] = (unsigned char)(permission & 1);
    candidate_memory[0x55] = (unsigned char)(permission >> 1);
    word(owner_memory, 0x1d8, 10); /* native Flow already published Start/Skip */
    props_state = FIXDEMO_TROPHY_PROPS_FAILED; run_frame();
    assert(ordinary[0x54] == (permission & 1) && ordinary[0x55] == (permission >> 1));
    assert(fixdemo_trophy_word(owner_memory, 0x1d8) == 10);
  }

  reset_case(); create(); props_state = FIXDEMO_TROPHY_PROPS_READY; run_frame();
  props_state = FIXDEMO_TROPHY_PROPS_PENDING; /* legitimate prop-free later cut */
  run_frame();
  assert(playing_allowed && !deletes && !fallbacks && status_polls == 1 && props_start_calls == 1);
  props_state = FIXDEMO_TROPHY_PROPS_FAILED; /* genuine later reload failure */
  run_frame(); assert(deletes == 1 && fallbacks == 1 && fixdemo_trophy_latch.consumed);

  reset_case(); create(); props_state = FIXDEMO_TROPHY_PROPS_READY; props_start_ok = 0;
  run_frame(); assert(fixdemo_trophy_abort && !fixdemo_trophy_latch.consumed);
  run_frame(); assert(deletes == 1 && fallbacks == 1);

  reset_case(); create(); pointer(owner_memory, 0x1e0, ordinary);
  run_frame(); assert(!deletes && !fixdemo_trophy_manager && !props_epoch);
  reset_case(); create(); const uint64_t before = fixdemo_trophy_live_token;
  fixdemo_trophy_end_match(); assert(!deletes && !fixdemo_trophy_manager && !props_epoch);
  fixdemo_trophy_begin_match(); assert(fixdemo_trophy_live_token > before);
  check_ending();
  check_listener_result();
  puts("trophy result capture, native ownership and fallback: pass");
  return 0;
}

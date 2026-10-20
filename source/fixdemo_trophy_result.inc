/* Explicit, hash-pinned trophy canary. Included after the prop runtime and the
 * common package validator. No hooks are installed in an ordinary runtime.
 *
 * The supported Mobile ABI is checked before any patch is written. Registry
 * pointers are borrowed only during CreateFixDemo or read through registered
 * listener components during MatchEndingDemo. Only value snapshots and the
 * native scene's existing owner identity survive either invocation. Native
 * Flow/MatchListener own execution, Skip, virtual deletion and FPS restoration.
 */
#include "fixdemo_ceremony_policy.h"

typedef struct FixdemoTrophyResultScope {
  void *owner;
  const void *registry;
  uint64_t token;
} FixdemoTrophyResultScope;

typedef struct FixdemoTrophyEndingScope {
  void *listener;
  uint64_t token;
  uint32_t null_factory;
} FixdemoTrophyEndingScope;

enum {
  FIXDEMO_TROPHY_OWNER_NONE,
  FIXDEMO_TROPHY_OWNER_FLOW,
  FIXDEMO_TROPHY_OWNER_ENDING,
  FIXDEMO_TROPHY_OWNER_LISTENER_RESULT
};

static __thread const FixdemoTrophyResultScope *fixdemo_trophy_result_scope;
static __thread FixdemoTrophyEndingScope *fixdemo_trophy_ending_scope;
static __thread FixdemoTrophyEndingScope *fixdemo_trophy_listener_scope;
static void (*fixdemo_trophy_create_original)(void *, const void *, const void *,
                                               uint32_t, uint32_t);
static void (*fixdemo_trophy_flow_original)(void *, void *, uint32_t, const void *);
static void (*fixdemo_trophy_ending_original)(void *, const void *);
static void (*fixdemo_trophy_listener_original)(void *, const void *);
static void (*fixdemo_trophy_wait_result_original)(void *, const void *);
static uint32_t (*fixdemo_trophy_pre_result_original)(void *);
static void (*fixdemo_trophy_read_lock)(void *, void **);
static void (*fixdemo_trophy_read_unlock)(void *);
static void (*fixdemo_trophy_set_environment)(void *);
static void (*fixdemo_trophy_set_step)(void *, uint8_t);
static const void *fixdemo_trophy_fade_instance;
static uintptr_t fixdemo_trophy_fade_cancel[2], fixdemo_trophy_fade_is_end[2];
static void *(*fixdemo_trophy_result_original)(uint32_t, uint32_t);
static void *(*fixdemo_trophy_match_original)(uint32_t, uint32_t);
static const void *(*fixdemo_trophy_global_registry)(void);
static const uint32_t *(*fixdemo_trophy_stats_team_id)(const void *, uint32_t);
static const void *(*fixdemo_trophy_stats_team)(const void *, uint32_t);
static uint32_t (*fixdemo_trophy_score)(const void *, uint32_t);
static int (*fixdemo_trophy_cut_ready_original)(void *, void *, uint32_t, uint32_t);
static void (*fixdemo_trophy_delete_original)(void *);
static void (*fixdemo_trophy_destruct_original)(void *);
static void (*fixdemo_trophy_start_original)(void *);
static void (*fixdemo_trophy_end_original)(void *);
static uintptr_t fixdemo_trophy_result_caller, fixdemo_trophy_ending_caller;
static uintptr_t fixdemo_trophy_listener_caller;
static uint64_t fixdemo_trophy_serial, fixdemo_trophy_live_token;
static uint64_t fixdemo_trophy_failed_token;
static FixdemoCeremonyLatch fixdemo_trophy_latch;
static FixdemoCeremonyPlan fixdemo_trophy_plan;
static void *fixdemo_trophy_owner, *fixdemo_trophy_manager;
static uint32_t fixdemo_trophy_started, fixdemo_trophy_abort;
static uint32_t fixdemo_trophy_finished;
static uint32_t fixdemo_trophy_owner_kind, fixdemo_trophy_fallback_scene;
static uint32_t fixdemo_trophy_fallback_side, fixdemo_trophy_ending_steps;
static uint32_t fixdemo_trophy_wait_logged;
static uint32_t fixdemo_trophy_diagnostics = 24u;
static int fixdemo_trophy_result_installed;
/* The process/UI queue sees only atomic token values, never listener or model
 * pointers. The serialized listener queue owns the remaining metadata. */
static uint64_t fixdemo_trophy_ui_token, fixdemo_trophy_ui_skip;
static uint64_t fixdemo_trophy_ui_timeout, fixdemo_trophy_ui_since;
static uint64_t fixdemo_trophy_ui_waiting_token;
static uint32_t fixdemo_trophy_ui_polls;
static void *fixdemo_trophy_ui_owner;
static uint64_t fixdemo_trophy_empty_result_token;
static void *fixdemo_trophy_empty_result_owner;

static int fixdemo_trophy_ui_active(void) {
  const uint64_t token = __atomic_load_n(&fixdemo_trophy_ui_token, __ATOMIC_ACQUIRE);
  return token && token == __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE);
}

static int fixdemo_trophy_request_skip(void) {
  const uint64_t token = __atomic_load_n(&fixdemo_trophy_ui_token, __ATOMIC_ACQUIRE);
  if (!token || token != __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE)) return 0;
  __atomic_store_n(&fixdemo_trophy_ui_skip, token, __ATOMIC_RELEASE);
  return 1;
}

static void fixdemo_trophy_release_ui(void) {
  __atomic_store_n(&fixdemo_trophy_ui_token, 0, __ATOMIC_RELEASE);
  __atomic_store_n(&fixdemo_trophy_ui_waiting_token, 0, __ATOMIC_RELEASE);
  fixdemo_trophy_ui_owner = NULL;
}

/* Canary-only, bounded lifecycle diagnostics. No per-frame filesystem writes. */
static void fixdemo_trophy_diagnostic(const char *message) {
  if (fixdemo_trophy_diagnostics) {
    --fixdemo_trophy_diagnostics;
    fixdemo_trophy_note(message);
  }
}

static void *fixdemo_trophy_pointer(const void *base, size_t offset) {
  void *value = NULL;
  if (base) memcpy(&value, (const unsigned char *)base + offset, sizeof(value));
  return value;
}

static uint32_t fixdemo_trophy_word(const void *base, size_t offset) {
  uint32_t value = UINT32_MAX;
  if (base) memcpy(&value, (const unsigned char *)base + offset, sizeof(value));
  return value;
}

static void fixdemo_trophy_forget_candidate(void) {
  /* Invalidate asynchronous notifications BEFORE any native destructor. No
   * deletion happens here: only the proven native owner may release objects. */
  if (fixdemo_trophy_plan.match_token)
    fixdemo_trophy_props_cancel(fixdemo_trophy_plan.match_token);
  fixdemo_trophy_owner = NULL;
  fixdemo_trophy_manager = NULL;
  fixdemo_trophy_owner_kind = FIXDEMO_TROPHY_OWNER_NONE;
  fixdemo_trophy_started = fixdemo_trophy_abort = fixdemo_trophy_finished = 0;
  memset(&fixdemo_trophy_plan, 0, sizeof(fixdemo_trophy_plan));
}

/* Call on the serialized match lifecycle, not from an input/render thread.
 * Invalidation never reads an old native pointer or invents a second owner. */
static void fixdemo_trophy_end_match(void) {
  if (!fixdemo_trophy_result_installed) return;
  if (__atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE))
    fixdemo_trophy_diagnostic("match-token-ended");
  __atomic_store_n(&fixdemo_trophy_live_token, 0, __ATOMIC_RELEASE);
  fixdemo_trophy_release_ui();
  fixdemo_trophy_empty_result_token = 0;
  fixdemo_trophy_empty_result_owner = NULL;
  fixdemo_trophy_forget_candidate();
}

static void fixdemo_trophy_begin_match(void) {
  if (!fixdemo_trophy_result_installed) return;
  fixdemo_trophy_end_match();
  if (fixdemo_trophy_serial == UINT64_MAX) return;
  const uint64_t token = ++fixdemo_trophy_serial;
  if (!fixdemo_ceremony_begin_match(&fixdemo_trophy_latch, token)) return;
  fixdemo_trophy_failed_token = 0;
  fixdemo_trophy_ending_steps = 0;
  fixdemo_trophy_wait_logged = 0;
  fixdemo_trophy_diagnostics = 24u;
  __atomic_store_n(&fixdemo_trophy_live_token, token, __ATOMIC_RELEASE);
  char message[80];
  snprintf(message, sizeof(message), "match-token-begin token=%llu",
           (unsigned long long)token);
  fixdemo_trophy_diagnostic(message);
}

/* Both entry adapters call this only with currently readable native records.
 * It copies values, validates physical IDs and retains no native data pointer. */
static int fixdemo_trophy_snapshot(const void *record, const void *match,
    const CompetitionCupFinalContext *final, FixdemoCeremonySnapshot *snapshot) {
  if (!record || !match) {
    fixdemo_trophy_diagnostic("factory-rejected missing-current-record");
    return 0;
  }
  const void *stats = (const unsigned char *)record + 0x750cc;
  snapshot->phase = fixdemo_trophy_word(match, 0x1168);
  int32_t goals[2], shootout[2];
  for (uint32_t index = 0; index != 2; ++index) {
    const uint32_t logical = index ? final->native_away_team : final->native_home_team;
    const uint32_t physical = exhibition_native_team_id(logical);
    const uint32_t *observed = fixdemo_trophy_stats_team_id(stats, index);
    const void *team = fixdemo_trophy_stats_team(stats, index);
    if (!physical || !observed || *observed != physical || !team) {
      fixdemo_trophy_diagnostic("factory-rejected current-team-mismatch");
      return 0;
    }
    const uint32_t full = fixdemo_trophy_score(team, 5u);
    const uint32_t pk = fixdemo_trophy_score(team, 4u);
    if (full > 99u || pk > 99u) {
      fixdemo_trophy_diagnostic("factory-rejected invalid-score");
      return 0;
    }
    goals[index] = (int32_t)full;
    shootout[index] = (int32_t)pk;
  }
  snapshot->native_home_team = final->native_home_team;
  snapshot->native_away_team = final->native_away_team;
  snapshot->home_goals = goals[0]; snapshot->away_goals = goals[1];
  snapshot->home_shootout = shootout[0]; snapshot->away_shootout = shootout[1];
  snapshot->shootout_fresh = snapshot->shootout_only = snapshot->fresh = 1u;
  return 1;
}

static int fixdemo_trophy_plan_snapshot(const CompetitionCupFinalContext *final,
    const FixdemoCeremonySnapshot *snapshot, FixdemoCeremonyPlan *plan) {
  FixdemoCeremonyContext context = {
    snapshot->match_token, final->native_home_team, final->native_away_team, 1u
  };
  const int accepted = fixdemo_ceremony_plan(&context, snapshot, &fixdemo_trophy_latch, plan);
  char message[224];
  snprintf(message, sizeof(message),
           "factory-snapshot boundary=%u token=%llu phase=%u scene=%x side=%u teams=%u/%u goals=%d/%d pk=%d/%d accepted=%d",
           snapshot->boundary, (unsigned long long)snapshot->match_token,
           snapshot->phase, snapshot->original_scene, snapshot->original_side,
           final->native_home_team, final->native_away_team, snapshot->home_goals,
           snapshot->away_goals, snapshot->home_shootout, snapshot->away_shootout,
           accepted);
  fixdemo_trophy_diagnostic(message);
  return accepted;
}

static int fixdemo_trophy_capture(uint32_t scene, uint32_t side,
                                  uintptr_t caller, FixdemoCeremonyPlan *plan) {
  const FixdemoTrophyResultScope *scope = fixdemo_trophy_result_scope;
  const uint64_t token = __atomic_load_n(&fixdemo_trophy_live_token,
                                        __ATOMIC_ACQUIRE);
  CompetitionCupFinalContext final = {0};
  const char *rejected = NULL;
  if (!scope || !scope->owner || !scope->registry) rejected = "missing-create-scope";
  else if (!token || token != scope->token || token == fixdemo_trophy_failed_token) rejected = "match-lifetime";
  else if (caller != fixdemo_trophy_result_caller) rejected = "caller";
  else if (scene != FIXDEMO_CEREMONY_RESULT_SCENE || side != FIXDEMO_CEREMONY_NEUTRAL_SIDE) rejected = "scene-or-side";
  else if (!competition_frontend_cup_live_final_context(&final)) rejected = "no-live-cup-final";
  if (rejected) {
    char message[192];
    snprintf(message, sizeof(message), "result-rejected %s scene=%x side=%u caller=%s scope=%u token=%llu",
             rejected, scene, side, caller == fixdemo_trophy_result_caller ? "flow" :
             caller == fixdemo_trophy_listener_caller ? "listener" : "other",
             scope != NULL, (unsigned long long)token);
    fixdemo_trophy_diagnostic(message);
    return 0;
  }

  /* Native Registry::OpenRead publishes +0x939 only after acquiring its
   * selected read slots; RecordInfo is +0x1d0. GlobalRegistry publishes +0x5150
   * after its MatchInfo read lock (+0x4f0). We borrow that same game-thread
   * invocation: never close the engine's lock, and never open a nested one. */
  const unsigned char *registry = scope->registry;
  const unsigned char *global = fixdemo_trophy_global_registry();
  if (!global || registry[0x939] != 1u || global[0x5150] != 1u) {
    fixdemo_trophy_diagnostic("result-rejected registry-read-scope");
    return 0;
  }
  const void *record = fixdemo_trophy_pointer(registry, 0x1d0);
  const void *match = fixdemo_trophy_pointer(global, 0x4f0);
  /* The two audited GetMatchStats overloads return RecordInfo + 0x750cc.
   * Read this live, still-locked record directly without invoking unrelated
   * pause instrumentation, and retain no pointer afterwards. */
  FixdemoCeremonySnapshot snapshot = {
    .match_token = token, .original_scene = scene, .original_side = side,
    .caller_verified = 1u
  };
  if (!fixdemo_trophy_snapshot(record, match, &final, &snapshot)) return 0;
  /* Fail closed if an unexpected callback invalidated the match lifetime or
   * released either native read scope while the getters were executing. */
  if (scope != fixdemo_trophy_result_scope ||
      token != __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE) ||
      registry[0x939] != 1u || global[0x5150] != 1u) {
    fixdemo_trophy_diagnostic("result-rejected invalidated-read-scope");
    return 0;
  }
  return fixdemo_trophy_plan_snapshot(&final, &snapshot, plan);
}

static int fixdemo_trophy_capture_ending(uint32_t scene, uint32_t side,
    uintptr_t caller, FixdemoCeremonyPlan *plan) {
  const FixdemoTrophyEndingScope *scope = fixdemo_trophy_ending_scope;
  const uint64_t token = __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE);
  if (!scope || !scope->listener)
    return 0; /* Other native Match factories are ordinary, including prematch. */
  if (caller != fixdemo_trophy_ending_caller) {
    fixdemo_trophy_diagnostic("ending-rejected caller");
    return 0;
  }
  if (!token || token != scope->token || token == fixdemo_trophy_failed_token) {
    fixdemo_trophy_diagnostic("ending-rejected match-lifetime");
    return 0;
  }
  CompetitionCupFinalContext final = {0};
  if (!competition_frontend_cup_live_final_context(&final)) {
    fixdemo_trophy_diagnostic("ending-rejected no-live-cup-final");
    return 0;
  }
  unsigned char *listener = scope->listener;
  /* InitRegistry registers MatchInfo Copy and RecordInfo Pointer components.
   * Their Base subobjects are +0x1b308/+0x1b998. The audited ReadLock publishes
   * the current buffer into our LOCAL pointers; do not borrow or overwrite
   * the listener's cached read slots (+0x1b338/+0x1b9c8). ReadUnlock balances
   * our two invocations before any native scene creation. */
  if (listener[0x1b300] != 1u || listener[0x1b990] != 1u) {
    fixdemo_trophy_diagnostic("ending-rejected unregistered-current-records");
    return 0;
  }
  void *match = NULL, *record = NULL;
  void *match_base = listener + 0x1b308;
  void *record_base = listener + 0x1b998;
  fixdemo_trophy_read_lock(match_base, &match);
  fixdemo_trophy_read_lock(record_base, &record);
  FixdemoCeremonySnapshot snapshot = {
    .match_token = token, .original_scene = scene, .original_side = side,
    .caller_verified = 1u, .boundary = FIXDEMO_CEREMONY_BOUNDARY_ENDING_FACTORY
  };
  const int request_matches = match &&
      fixdemo_trophy_word(match, 0x1324) == scene &&
      fixdemo_trophy_word(match, 0x1328) == side;
  const int captured = request_matches &&
      fixdemo_trophy_snapshot(record, match, &final, &snapshot);
  const int still_current = scope == fixdemo_trophy_ending_scope &&
      token == __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE) &&
      listener[0x1b300] == 1u && listener[0x1b990] == 1u;
  fixdemo_trophy_read_unlock(record_base);
  fixdemo_trophy_read_unlock(match_base);
  if (!request_matches || !captured || !still_current) {
    fixdemo_trophy_diagnostic(!request_matches ? "ending-rejected current-request-mismatch" :
                             !captured ? "ending-rejected current-snapshot" :
                                         "ending-rejected invalidated-read-scope");
    return 0;
  }
  snapshot.native_request_verified = 1u;
  return fixdemo_trophy_plan_snapshot(&final, &snapshot, plan);
}

/* Read the listener's registered components into invocation-local pointers.
 * In the factory scope the native MatchInfo read is already live; this ABI's
 * ReadLock is a pointer accessor and ReadUnlock is a no-op. Neither adapter
 * retains a borrowed record or changes the listener's published read slot. */
static int fixdemo_trophy_capture_listener(void *listener, uint64_t token,
    uint32_t scene, uint32_t side, FixdemoCeremonyPlan *plan) {
  if (!listener || !token || token != __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE) ||
      token == fixdemo_trophy_failed_token ||
      token == __atomic_load_n(&fixdemo_trophy_ui_timeout, __ATOMIC_ACQUIRE)) return 0;
  CompetitionCupFinalContext final = {0};
  if (!competition_frontend_cup_live_final_context(&final)) {
    fixdemo_trophy_diagnostic("listener-result-rejected no-live-cup-final");
    return 0;
  }
  unsigned char *owner = listener;
  if (owner[0x1b300] != 1u || owner[0x1b990] != 1u) {
    fixdemo_trophy_diagnostic("listener-result-rejected unregistered-current-records");
    return 0;
  }
  void *match = NULL, *record = NULL;
  fixdemo_trophy_read_lock(owner + 0x1b308, &match);
  fixdemo_trophy_read_lock(owner + 0x1b998, &record);
  const uint32_t requested_side = fixdemo_trophy_word(match, 0x132c);
  FixdemoCeremonySnapshot snapshot = {
    .match_token = token, .original_scene = scene,
    .original_side = side == UINT32_MAX ? requested_side : side,
    .caller_verified = 1u, .boundary = FIXDEMO_CEREMONY_BOUNDARY_LISTENER_RESULT,
    .native_request_verified = requested_side <= 2u &&
        (side == UINT32_MAX || side == requested_side)
  };
  const int captured = snapshot.native_request_verified &&
      fixdemo_trophy_snapshot(record, match, &final, &snapshot);
  const int current = token == __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE) &&
      owner[0x1b300] == 1u && owner[0x1b990] == 1u;
  fixdemo_trophy_read_unlock(owner + 0x1b998);
  fixdemo_trophy_read_unlock(owner + 0x1b308);
  if (!captured || !current) {
    fixdemo_trophy_diagnostic("listener-result-rejected current-record-or-side");
    return 0;
  }
  return fixdemo_trophy_plan_snapshot(&final, &snapshot, plan);
}

static void fixdemo_trophy_wait_result(void *listener, const void *context) {
  const uint64_t token = __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE);
  const unsigned char *owner = listener;
  const int ready = owner && owner[0x118] != 0u && owner[0x118] != 21u &&
      !owner[0x18ff2] && owner[0x18ff0] && owner[0x18ff3];
  if (fixdemo_trophy_result_installed && owner && token &&
      (!(fixdemo_trophy_wait_logged & 1u) || (ready && !(fixdemo_trophy_wait_logged & 2u)))) {
    char message[144];
    fixdemo_trophy_wait_logged |= 1u | (ready ? 2u : 0u);
    snprintf(message, sizeof(message),
        "wait-result-entry token=%llu state=%u flags=%u/%u/%u ready=%d",
        (unsigned long long)token, owner[0x118], owner[0x18ff0],
        owner[0x18ff2], owner[0x18ff3], ready);
    fixdemo_trophy_diagnostic(message);
  }
  /* Exactly the native readiness flags preceding PushFlowEvent/SetResultEnable.
   * Arm BEFORE the original call; the separate process queue must not consume
   * ResultEnable in the gap before state 19 reaches its factory next frame. */
  if (fixdemo_trophy_result_installed && owner && token &&
      !__atomic_load_n(&fixdemo_trophy_ui_token, __ATOMIC_ACQUIRE) &&
      ready) {
    FixdemoCeremonyPlan plan;
    if (fixdemo_trophy_capture_listener(listener, token,
          FIXDEMO_CEREMONY_RESULT_SCENE, UINT32_MAX, &plan)) {
      fixdemo_trophy_ui_owner = listener;
      __atomic_store_n(&fixdemo_trophy_ui_since, scene_runtime_ms(), __ATOMIC_RELAXED);
      __atomic_store_n(&fixdemo_trophy_ui_polls, 0u, __ATOMIC_RELAXED);
      __atomic_store_n(&fixdemo_trophy_ui_waiting_token, token, __ATOMIC_RELAXED);
      __atomic_store_n(&fixdemo_trophy_ui_skip, 0u, __ATOMIC_RELAXED);
      __atomic_store_n(&fixdemo_trophy_ui_token, token, __ATOMIC_RELEASE);
      fixdemo_trophy_diagnostic("listener-result UI-held before-native-result-enable");
    }
  }
  fixdemo_trophy_wait_result_original(listener, context);
}

static uint32_t fixdemo_trophy_pre_result(void *process) {
  const uint64_t token = __atomic_load_n(&fixdemo_trophy_ui_token, __ATOMIC_ACQUIRE);
  if (token && token == __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE)) {
    const uint32_t polls = __atomic_add_fetch(&fixdemo_trophy_ui_polls, 1u, __ATOMIC_RELAXED);
    const uint64_t since = __atomic_load_n(&fixdemo_trophy_ui_since, __ATOMIC_RELAXED);
    if (polls <= 3600u && scene_runtime_ms() - since <= 60000u) return 0;
    /* Only signal the owning listener. An active manager must be destroyed
     * on that queue before the overview is released. If no factory arrived,
     * fail open now and reject any later factory for the expired token. */
    __atomic_store_n(&fixdemo_trophy_ui_timeout, token, __ATOMIC_RELEASE);
    uint64_t waiting = token;
    if (!__atomic_compare_exchange_n(&fixdemo_trophy_ui_waiting_token, &waiting,
          0u, 0, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE)) return 0;
    uint64_t expected = token;
    __atomic_compare_exchange_n(&fixdemo_trophy_ui_token, &expected, 0u, 0,
                                __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE);
  }
  return fixdemo_trophy_pre_result_original(process);
}

static void *fixdemo_trophy_create_candidate(const FixdemoCeremonyPlan *plan,
    void *owner, uint32_t kind, uint32_t scene, uint32_t side) {
  if (!fixdemo_trophy_props_begin(plan->match_token)) {
    fixdemo_trophy_diagnostic("candidate-rejected prop-epoch");
    return NULL;
  }
  void *candidate = fixdemo_trophy_match_original(plan->scene, plan->winner_side);
  if (!candidate) {
    fixdemo_trophy_props_cancel(plan->match_token);
    fixdemo_trophy_diagnostic("candidate-create-failed native-fallback");
    return NULL;
  }
  fixdemo_trophy_plan = *plan;
  fixdemo_trophy_owner = owner;
  fixdemo_trophy_owner_kind = kind;
  fixdemo_trophy_fallback_scene = scene;
  fixdemo_trophy_fallback_side = side;
  fixdemo_trophy_manager = candidate;
  fixdemo_trophy_started = fixdemo_trophy_abort = fixdemo_trophy_finished = 0u;
  fixdemo_trophy_note("candidate-created awaiting-two-bound-meshes");
  return candidate;
}

static void *fixdemo_trophy_listener_result_at(uint32_t scene, uint32_t side,
                                             uintptr_t caller) {
  FixdemoTrophyEndingScope *scope = fixdemo_trophy_listener_scope;
  FixdemoCeremonyPlan plan;
  uint64_t waiting = scope ? scope->token : 0;
  const int held = scope && scope->token && scope->listener == fixdemo_trophy_ui_owner &&
      scope->token == __atomic_load_n(&fixdemo_trophy_ui_token, __ATOMIC_ACQUIRE);
  const int expired = scope && scope->token && scope->listener == fixdemo_trophy_ui_owner &&
      scope->token == __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE) &&
      scope->token == __atomic_load_n(&fixdemo_trophy_ui_timeout, __ATOMIC_ACQUIRE);
  if (!scope || caller != fixdemo_trophy_listener_caller || !held ||
      fixdemo_trophy_manager ||
      scope->token == __atomic_load_n(&fixdemo_trophy_ui_skip, __ATOMIC_ACQUIRE) ||
      !fixdemo_trophy_capture_listener(scope->listener, scope->token, scene, side, &plan) ||
      !__atomic_compare_exchange_n(&fixdemo_trophy_ui_waiting_token, &waiting,
          0u, 0, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE)) {
    char message[144];
    snprintf(message, sizeof(message), "listener-result-rejected hold=%d caller=%u scene=%x side=%u",
             held, caller == fixdemo_trophy_listener_caller, scene, side);
    fixdemo_trophy_diagnostic(message);
    void *fallback = fixdemo_trophy_result_original(scene, side);
    /* A timed-out UI wait may have released the overview before this factory
     * arrives. Its same-token ordinary background can still fail allocation;
     * keep that canary's native step-1 NULL read out of the close lifecycle. */
    if (!fallback && (held || expired)) scope->null_factory = 1u;
    if (held) {
      fixdemo_trophy_failed_token = scope->token;
      fixdemo_trophy_release_ui();
    }
    return fallback;
  }
  /* This CAS and the process timeout compete for the same waiting token.
   * Once construction owns it, the process can signal an abort but cannot
   * expose the overview while native allocation/cleanup is still in flight. */
  void *candidate = fixdemo_trophy_create_candidate(&plan, scope->listener,
      FIXDEMO_TROPHY_OWNER_LISTENER_RESULT, scene, side);
  if (candidate) return candidate;
  fixdemo_trophy_failed_token = scope->token;
  void *fallback = fixdemo_trophy_result_original(scene, side);
  if (!fallback) scope->null_factory = 1u;
  fixdemo_trophy_release_ui();
  return fallback;
}

static void *fixdemo_trophy_result_at(uint32_t scene, uint32_t side,
                                      uintptr_t caller) {
  FixdemoCeremonyPlan plan;
  if (fixdemo_trophy_result_installed && fixdemo_trophy_listener_scope &&
      caller == fixdemo_trophy_listener_caller) {
    /* Listener result ownership and its earlier UI hold are a separate
     * contract; they never borrow the Flow/CreateFixDemo registry scope. */
    return fixdemo_trophy_listener_result_at(scene, side, caller);
  }
  if (!fixdemo_trophy_result_installed || fixdemo_trophy_manager ||
      !fixdemo_trophy_capture(scene, side, caller, &plan))
    return fixdemo_trophy_result_original(scene, side);
  void *candidate = fixdemo_trophy_create_candidate(&plan,
      fixdemo_trophy_result_scope->owner, FIXDEMO_TROPHY_OWNER_FLOW, scene, side);
  /* The original CreateFixDemo stores this exact pointer at owner+0x1e0.
   * Allocation does not consume the ceremony success latch. */
  return candidate ? candidate : fixdemo_trophy_result_original(scene, side);
}

static void *fixdemo_trophy_match_at(uint32_t scene, uint32_t side,
                                     uintptr_t caller) {
  FixdemoCeremonyPlan plan;
  if (!fixdemo_trophy_result_installed || fixdemo_trophy_manager ||
      !fixdemo_trophy_capture_ending(scene, side, caller, &plan))
    return fixdemo_trophy_match_original(scene, side);
  void *candidate = fixdemo_trophy_create_candidate(&plan,
      fixdemo_trophy_ending_scope->listener, FIXDEMO_TROPHY_OWNER_ENDING, scene, side);
  /* Native MatchEndingDemo stores this return value at listener+0x19018. */
  if (candidate) return candidate;
  void *fallback = fixdemo_trophy_match_original(scene, side);
  if (!fallback) {
    /* The native factory tail still stores NULL and sets step 1. Defer the
     * checked empty-owner cleanup until that tail has returned to our scope. */
    fixdemo_trophy_ending_scope->null_factory = 1u;
    fixdemo_trophy_failed_token = plan.match_token;
  }
  return fallback;
}

static __attribute__((noinline)) void *fixdemo_trophy_match_create(
    uint32_t scene, uint32_t side) {
  return fixdemo_trophy_match_at(scene, side,
                                (uintptr_t)__builtin_return_address(0));
}

static __attribute__((noinline)) void *fixdemo_trophy_result_create(
    uint32_t scene, uint32_t side) {
  return fixdemo_trophy_result_at(scene, side,
                                 (uintptr_t)__builtin_return_address(0));
}

static void fixdemo_trophy_create(void *owner, const void *registry,
                                  const void *environment, uint32_t kind,
                                  uint32_t wait_category) {
  const FixdemoTrophyResultScope scope = {
    owner, registry,
    __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE)
  };
  const FixdemoTrophyResultScope *previous = fixdemo_trophy_result_scope;
  fixdemo_trophy_result_scope = &scope;
  /* FixDemoEnvWork is a 24-byte C++ value, passed indirectly in x2 by AAPCS64.
   * Preserve all five native argument registers, and let the native factory
   * perform its own scene ownership assignment. */
  fixdemo_trophy_create_original(owner, registry, environment, kind, wait_category);
  fixdemo_trophy_result_scope = previous;
}

static void fixdemo_trophy_delete(void *manager) {
  if (manager == fixdemo_trophy_manager) {
    fixdemo_trophy_note(fixdemo_trophy_started ? "candidate-delete-after-start"
                                             : "candidate-delete-before-start");
    fixdemo_trophy_forget_candidate();
  }
  fixdemo_trophy_delete_original(manager);
}

static void fixdemo_trophy_destruct(void *manager) {
  if (manager == fixdemo_trophy_manager) fixdemo_trophy_forget_candidate();
  fixdemo_trophy_destruct_original(manager);
}

static void fixdemo_trophy_start(void *manager) {
  if (manager == fixdemo_trophy_manager && !fixdemo_trophy_started) {
    if (fixdemo_trophy_props_peek(fixdemo_trophy_plan.match_token) ==
        FIXDEMO_TROPHY_PROPS_READY &&
        fixdemo_trophy_props_started(fixdemo_trophy_plan.match_token) &&
        fixdemo_ceremony_backend_result(&fixdemo_trophy_latch,
                                        &fixdemo_trophy_plan, 1)) {
      fixdemo_trophy_started = 1u;
      fixdemo_trophy_note("ceremony-start meshes-ready winner-verified");
    } else {
      fixdemo_trophy_abort = 1u;
      fixdemo_trophy_note("ceremony-start-rejected readiness-changed");
    }
  }
  /* Preserve the native 30-FPS cinematic request and its saved restore value. */
  fixdemo_trophy_start_original(manager);
}

static void fixdemo_trophy_end(void *manager) {
  fixdemo_trophy_end_original(manager);
  if (manager == fixdemo_trophy_manager) {
    fixdemo_trophy_finished = 1u;
    fixdemo_trophy_note("ceremony-end native-fps-restored");
  }
}

static int fixdemo_trophy_cut_ready(void *manager, void *cut, uint32_t number,
                                    uint32_t first) {
  const int native_ready = fixdemo_trophy_cut_ready_original(manager, cut, number, first);
  if (manager != fixdemo_trophy_manager) return native_ready;
  /* Native loading still runs, but the first cut cannot start with missing
   * props. Later cuts may legitimately retire either prop; their native
   * per-object IsReady checks remain authoritative without requiring both
   * original objects to remain alive across the whole scene. */
  return native_ready && !fixdemo_trophy_abort &&
         (fixdemo_trophy_started ||
          fixdemo_trophy_props_peek(fixdemo_trophy_plan.match_token) ==
              FIXDEMO_TROPHY_PROPS_READY);
}

static void fixdemo_trophy_empty_ending(void *listener) {
  /* The native fade singleton may be Manager or ManagerMobile. Cancel only
   * the existing object's audited level-1 fade, through its native virtual
   * method (the Mobile implementation owns its mutex). This makes the native
   * step-7 IsEnd check complete even if a candidate failed mid-fade. */
  void *fade = fixdemo_trophy_pointer(fixdemo_trophy_fade_instance, 0);
  if (fade) {
    const void *table = fixdemo_trophy_pointer(fade, 0);
    const uintptr_t cancel = (uintptr_t)fixdemo_trophy_pointer(table, 0x20);
    const uintptr_t is_end = (uintptr_t)fixdemo_trophy_pointer(table, 0x48);
    if ((cancel == fixdemo_trophy_fade_cancel[0] && is_end == fixdemo_trophy_fade_is_end[0]) ||
        (cancel == fixdemo_trophy_fade_cancel[1] && is_end == fixdemo_trophy_fade_is_end[1])) {
      ((int (*)(void *, uint32_t))cancel)(fade, 1u);
    } else {
      fixdemo_trophy_diagnostic("empty-ending unsupported-fade native-wait-retained");
    }
  }
  /* Native step 6 is explicitly NULL-capable. It advances to the ordinary
   * listener's step 7/result path; do not change MatchTop/Cup state here. */
  fixdemo_trophy_set_step(listener, 6u);
}

static void fixdemo_trophy_watch_owner(void *owner, uint32_t kind, size_t slot) {
  if (kind == fixdemo_trophy_owner_kind && owner == fixdemo_trophy_owner &&
      fixdemo_trophy_manager) {
    /* Only inspect the owner passed to this native invocation. Never dereference
     * a saved owner from an asynchronous completion, HUD or renderer callback. */
    void *manager = fixdemo_trophy_pointer(owner, slot);
    if (manager != fixdemo_trophy_manager) {
      fixdemo_trophy_note("candidate-owner-replaced ignored");
      fixdemo_trophy_forget_candidate();
    } else if (fixdemo_trophy_abort ||
               (fixdemo_trophy_started ?
                fixdemo_trophy_props_peek(fixdemo_trophy_plan.match_token) :
                fixdemo_trophy_props_status(fixdemo_trophy_plan.match_token)) ==
                   FIXDEMO_TROPHY_PROPS_FAILED) {
      /* Base-manager +0x54 is Flow's start permission; +0x55 is its Skip
       * request. Flow state 10 keeps executing its manager but does not publish
       * the start byte again. Retain those two native permissions when swapping
       * a failed candidate, otherwise a fresh result can wait forever. */
      unsigned char permissions[2];
      memcpy(permissions, (const unsigned char *)manager + 0x54, sizeof(permissions));
      const uint32_t scene = fixdemo_trophy_fallback_scene;
      const uint32_t side = fixdemo_trophy_fallback_side;
      fixdemo_trophy_failed_token = fixdemo_trophy_plan.match_token;
      fixdemo_trophy_forget_candidate();
      /* This is BEFORE the native owner reads its manager, never inside a virtual
       * Exec call. Its native destructor restores FPS and releases the candidate
       * before the ordinary result is allocated. No two live managers share the
       * global FixDemo slot. Native Flow/MatchListener steps are retained. */
      void *none = NULL;
      memcpy((unsigned char *)owner + slot, &none, sizeof(none));
      fixdemo_trophy_delete_original(manager);
      void *fallback;
      if (kind == FIXDEMO_TROPHY_OWNER_ENDING) {
        /* Recreate the original ending request with native SetOutMatch env,
         * as this listener's initial factory branch does. Never substitute
         * Result for a listener-owned Match or force a MatchTop transition. */
        fixdemo_trophy_set_environment(owner);
        fallback = fixdemo_trophy_match_original(scene, side);
      } else {
        fallback = fixdemo_trophy_result_original(scene, side);
      }
      if (fallback)
        memcpy((unsigned char *)fallback + 0x54, permissions, sizeof(permissions));
      memcpy((unsigned char *)owner + slot, &fallback, sizeof(fallback));
      if (!fallback && kind == FIXDEMO_TROPHY_OWNER_ENDING) {
        /* Audited native step 6 explicitly handles an empty owner, advances
         * to step 7, and lets the listener finish its usual result transition.
         * No MatchTop state, competition state or save is forced here. */
        fixdemo_trophy_empty_ending(owner);
        fixdemo_trophy_note("original-ending-unavailable native-empty-owner-cleanup");
        return;
      }
      fixdemo_trophy_note(kind == FIXDEMO_TROPHY_OWNER_ENDING ?
          "candidate-failed native-deleted original-ending-restored" :
          "candidate-failed native-deleted ordinary-result-restored");
    }
  }
}

static void fixdemo_trophy_flow(void *owner, void *info, uint32_t active,
                                const void *context) {
  fixdemo_trophy_watch_owner(owner, FIXDEMO_TROPHY_OWNER_FLOW, 0x1e0);
  fixdemo_trophy_flow_original(owner, info, active, context);
}

static void fixdemo_trophy_ending(void *listener, const void *context) {
  if (!fixdemo_trophy_result_installed) {
    fixdemo_trophy_ending_original(listener, context);
    return;
  }
  fixdemo_trophy_watch_owner(listener, FIXDEMO_TROPHY_OWNER_ENDING, 0x19018);
  FixdemoTrophyEndingScope scope = {
    listener, __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE), 0u
  };
  /* GetMatchStep on the pinned ABI reads this byte. Each distinct native step
   * logs once per match, including a zero-token entry, never each frame. */
  if (listener) {
    const uint32_t step = ((const unsigned char *)listener)[0x119];
    const uint32_t bit = UINT32_C(1) << (step < 31u ? step : 31u);
    if (!(fixdemo_trophy_ending_steps & bit)) {
      char message[96];
      fixdemo_trophy_ending_steps |= bit;
      snprintf(message, sizeof(message), "ending-entry token=%llu step=%u",
               (unsigned long long)scope.token, step);
      fixdemo_trophy_diagnostic(message);
    }
  }
  FixdemoTrophyEndingScope *previous = fixdemo_trophy_ending_scope;
  fixdemo_trophy_ending_scope = &scope;
  fixdemo_trophy_ending_original(listener, context);
  if (scope.null_factory && scope.token && listener &&
      scope.token == __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE) &&
      !fixdemo_trophy_pointer(listener, 0x19018)) {
    fixdemo_trophy_empty_ending(listener);
    fixdemo_trophy_note("initial-ending-unavailable native-empty-owner-cleanup");
  }
  fixdemo_trophy_ending_scope = previous;
}

static void fixdemo_trophy_listener(void *listener, const void *context) {
  const uint64_t token = __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE);
  if (listener && fixdemo_trophy_owner_kind == FIXDEMO_TROPHY_OWNER_LISTENER_RESULT &&
      listener == fixdemo_trophy_owner && fixdemo_trophy_manager) {
    void *manager = fixdemo_trophy_pointer(listener, 0x19018);
    if (manager != fixdemo_trophy_manager) {
      fixdemo_trophy_failed_token = token;
      fixdemo_trophy_forget_candidate();
      fixdemo_trophy_release_ui();
      fixdemo_trophy_diagnostic("listener-result owner-replaced UI-released");
    } else {
      /* Input/UI queues publish tokens only. The current native owner alone
       * applies the same Skip permission consumed by Manager::Exec/ExecMain. */
      if (token == __atomic_load_n(&fixdemo_trophy_ui_skip, __ATOMIC_ACQUIRE))
        ((unsigned char *)manager)[0x55] = 1u;
      const int failed = fixdemo_trophy_abort ||
          token == __atomic_load_n(&fixdemo_trophy_ui_timeout, __ATOMIC_ACQUIRE) ||
          (fixdemo_trophy_started ? fixdemo_trophy_props_peek(token) :
                                   fixdemo_trophy_props_status(token)) == FIXDEMO_TROPHY_PROPS_FAILED;
      /* Exec's state 4 is terminal, including Skip before StartDemoEvent.
       * A natural EndDemoEvent also means the native FPS has been restored. */
      const int finished = fixdemo_trophy_finished || fixdemo_trophy_word(manager, 0x1dc) == 4u;
      if (failed || finished) {
        const uint32_t scene = fixdemo_trophy_fallback_scene, side = fixdemo_trophy_fallback_side;
        fixdemo_trophy_failed_token = token;
        fixdemo_trophy_forget_candidate();
        void *none = NULL;
        memcpy((unsigned char *)listener + 0x19018, &none, sizeof(none));
        fixdemo_trophy_delete_original(manager);
        fixdemo_trophy_set_environment(listener);
        void *ordinary = fixdemo_trophy_result_original(scene, side);
        memcpy((unsigned char *)listener + 0x19018, &ordinary, sizeof(ordinary));
        if (ordinary) {
          /* Replay only the native background loader/start-permission step.
           * MatchTop stays state 19 and the unchanged UI process proceeds. */
          fixdemo_trophy_set_step(listener, 1u);
        } else {
          fixdemo_trophy_empty_result_token = token;
          fixdemo_trophy_empty_result_owner = listener;
        }
        fixdemo_trophy_release_ui();
        fixdemo_trophy_diagnostic(failed ? "listener-result candidate-failed ordinary-overview-released" :
                                           "listener-result candidate-finished ordinary-overview-released");
      }
    }
  }
  if (listener && token && token == fixdemo_trophy_empty_result_token &&
      listener == fixdemo_trophy_empty_result_owner && !fixdemo_trophy_pointer(listener, 0x19018)) {
    /* Native step 1 dereferences its manager. For our failed replacement only,
     * keep the background empty while the ordinary overview accepts input.
     * Its usual close flag then enters the listener's NULL-safe step 3 fade
     * and step 5 cleanup, not MatchEndingDemo's unrelated steps 6/7. */
    if (((const unsigned char *)listener)[0x11c] != 1u) return;
    fixdemo_trophy_set_step(listener, 3u);
    fixdemo_trophy_empty_result_token = 0;
    fixdemo_trophy_empty_result_owner = NULL;
    fixdemo_trophy_diagnostic("listener-result empty-background native-close-cleanup");
  }
  FixdemoTrophyEndingScope scope = {listener, token, 0u};
  FixdemoTrophyEndingScope *previous = fixdemo_trophy_listener_scope;
  fixdemo_trophy_listener_scope = &scope;
  fixdemo_trophy_listener_original(listener, context);
  if (scope.null_factory && token && listener &&
      token == __atomic_load_n(&fixdemo_trophy_live_token, __ATOMIC_ACQUIRE) &&
      !fixdemo_trophy_pointer(listener, 0x19018)) {
    fixdemo_trophy_empty_result_token = token;
    fixdemo_trophy_empty_result_owner = listener;
    fixdemo_trophy_diagnostic("listener-result unavailable ordinary-UI-no-background");
  }
  fixdemo_trophy_listener_scope = previous;
}

#ifndef PESNX_TROPHY_RESULT_TEST
/* Whole-function fingerprints are project-authored ABI checks, not copied game
 * code. The independent package gate additionally checks the complete ELF SHA.
 * prepare() is read-only; commit() writes only after BOTH subsystems prepared. */
typedef struct {
  const char *name;
  uint32_t rva, size;
  uint64_t fnv1a;
} FixdemoTrophyResultABI;
static const FixdemoTrophyResultABI fixdemo_trophy_result_abi[] = {
  {"_ZN5match7FixDemo13CreateFixDemoEPKNS_8registry8RegistryENS_14FixDemoEnvWorkENS_13FIX_DEMO_KINDENS1_11WaitControl8CategoryE", 0x620c0c0, 0x1f0, UINT64_C(0xf9e19e2caf75035a)},
  {"_ZN5match4Flow11ExecFixDemoEPNS_8registry11FixDemoInfoEbPKN5cobra4game7ContextE", 0x620c3ac, 0xb34, UINT64_C(0x63db8864aa9df323)},
  {"_ZN5match8registry8Registry8OpenReadEv", 0x67e69a0, 0x4a8, UINT64_C(0x5a7570e7ec169658)},
  {"_ZN5match8registry8Registry9CloseReadEv", 0x67e62e8, 0x17c, UINT64_C(0x5057004465939ba0)},
  {"_ZN5match8registry14GlobalRegistry8OpenReadEv", 0x67e2a8c, 0x12a8, UINT64_C(0x278f8d59614419e4)},
  {"_ZN5match8registry14GlobalRegistry9CloseReadEv", 0x67e3d4c, 0x3e8, UINT64_C(0xc4e928f080d4190c)},
  {"_ZNK5match6output14StatsMatchInfo9GetTeamIdE8HomeAway", 0x66b4230, 0x24, UINT64_C(0x4c9a9845dace7b22)},
  {"_ZNK5match6output14StatsMatchInfo11GetTeamInfoE8HomeAway", 0x66b426c, 0x18, UINT64_C(0x0d725feca8b82613)},
  {"_ZNK5match6output13StatsTeamInfo8GetScoreE8HalfKind", 0x66b5698, 0xac, UINT64_C(0xbba098f87f85b650)},
  {"_ZN12FixDemoMatch6CreateEj8HomeAway", 0x7b8ad88, 0x80, UINT64_C(0x1762e12e0f98caf1)},
  {"_ZN13FixDemoResult6CreateEj8HomeAway", 0x7b8f0f4, 0x98, UINT64_C(0xae2ea38aedaca22a)},
  {"_ZN12FixDemoMatchD0Ev", 0x7b8ccb4, 0x44, UINT64_C(0x6a5b3fc833a259a2)},
  {"_ZN12FixDemoMatchD2Ev", 0x7b8cc78, 0x3c, UINT64_C(0x9d15b870e4d0a8fb)},
  {"_ZN12FixDemoMatch14StartDemoEventEv", 0x7b8c530, 0x5c, UINT64_C(0xa95314abfe21c2ae)},
  {"_ZN12FixDemoMatch12EndDemoEventEv", 0x7b8c58c, 0x28, UINT64_C(0xc3c517ad65e85225)},
  {"_ZN14FixDemoManager10IsReadyCutEP11FixDemoMainhb", 0x7b835cc, 0x164, UINT64_C(0x59e065b1d255797e)},
  {"_ZN14FixDemoManager4ExecEPN5match8registry11FixDemoInfoE", 0x7b822f0, 0x2d0, UINT64_C(0x13545572c87dcaae)},
  {"_ZN5match8registry14GlobalRegistry19GetInstanceForRetryEv", 0x67e129c, 0x10, UINT64_C(0xbc5a6399d0ab61a8)},
  {"_ZN9game_mode13MatchListener15MatchEndingDemoEPKN5cobra4game7ContextE", 0x7bf3504, 0x79c, UINT64_C(0x8427abb9ccd964cf)},
  {"_ZN9game_mode13MatchListener12InitRegistryEPKN5cobra4game7ContextE", 0x7bc3b28, 0x1894, UINT64_C(0x6e76d39693ab4415)},
  {"_ZN9game_mode13MatchListener13SetFixDemoEnvEv", 0x7bf231c, 0x5a4, UINT64_C(0xc54bdd7af205aeee)},
  {"_ZN9game_mode13MatchListener12GetMatchStepEv", 0x7bc35ac, 0x8, UINT64_C(0x5829ab6e82c82e52)},
  {"_ZN6common8Registry7Manager8ReadLockEPNS0_4BaseEPPv", 0x7ae8158, 0x20, UINT64_C(0x930ec3d701592be1)},
  {"_ZN6common8Registry7Manager10ReadUnlockEPNS0_4BaseE", 0x7ae8178, 0x4, UINT64_C(0x2fe42bc03800fb45)},
  {"_ZN9game_mode13MatchListener12SetMatchStepEh", 0x7bc35a4, 0x8, UINT64_C(0xd26d817cb1a99063)},
  {"_ZN4fade7Manager6CancelENS_5LEVELE", 0x7b497f8, 0x8, UINT64_C(0x8c910b777aa0dc7a)},
  {"_ZN4fade13ManagerMobile6CancelENS_5LEVELE", 0x7b4a1e8, 0x5c, UINT64_C(0x02e757011521c660)},
  {"_ZN4fade7Manager5IsEndENS_5LEVELE", 0x7b49820, 0x8, UINT64_C(0x8c910b777aa0dc7a)},
  {"_ZN4fade13ManagerMobile5IsEndENS_5LEVELE", 0x7b4a244, 0x6c, UINT64_C(0x361209766ee28a93)},
  {"_ZN4fade8FadeImpl6cancelEv", 0x7b4a82c, 0x14, UINT64_C(0x471a9708993fd09e)},
  {"_ZNK4fade8FadeImpl5IsEndEv", 0x7b4a898, 0x20, UINT64_C(0x7eedac85921a097b)},
  {"_ZN4fade8FadeImpl6CreateENS_7FADE_IDE", 0x7b4a72c, 0x40, UINT64_C(0xa3312b05ea7a1bc9)},
  {"_ZN9game_mode13MatchListener19WaitSendMatchResultEPKN5cobra4game7ContextE", 0x7be13e4, 0xf0, UINT64_C(0xb6e76da23eafe8b0)},
  {"_ZN9game_mode13MatchListener17MatchHalfTimeDemoEPKN5cobra4game7ContextE", 0x7bf30c4, 0x440, UINT64_C(0xb58fa74eaf59ef49)},
  {"_ZN7process23ProcessMatchPreHalfTime4MainEv", 0x6cb2d4c, 0x8c, UINT64_C(0x7a1bc7dcf1987951)},
};
static const uint32_t fixdemo_trophy_result_plt_rvas[8] = {
  0x37e2a40, 0x39040c0, 0x391c230, 0x391bc10, 0x381e6e0, 0x383dba0,
  0x38dbec0, 0x3822010
};
static const uint32_t fixdemo_trophy_result_plt_words[8][4] = {
  {0xb002e670, 0xf943be11, 0x911de210, 0xd61f0220},
  {0x9002e1f0, 0xf9415e11, 0x910ae210, 0xd61f0220},
  {0x9002e190, 0xf941ba11, 0x910dc210, 0xd61f0220},
  {0xb002e190, 0xf9403211, 0x91018210, 0xd61f0220},
  {0xf002e570, 0xf942e611, 0x91172210, 0xd61f0220},
  {0x9002e510, 0xf9401611, 0x9100a210, 0xd61f0220},
  {0xb002e290, 0xf940de11, 0x9106e210, 0xd61f0220},
  {0xb002e570, 0xf9413211, 0x91098210, 0xd61f0220},
};
static uintptr_t fixdemo_trophy_result_patch[8], *fixdemo_trophy_result_slots[4];
static uintptr_t *fixdemo_trophy_pre_result_slot;
static int fixdemo_trophy_result_prepared;

static int fixdemo_trophy_result_prepare(so_module *module) {
  if (fixdemo_trophy_result_installed) return 1;
  fixdemo_trophy_result_prepared = 0;
  if (!module || !fixdemo_trophy_canary_validated ||
      strcmp(fixdemo_trophy_verified_elf_sha256,
             "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187")) return 0;
  uintptr_t methods[sizeof(fixdemo_trophy_result_abi) / sizeof(fixdemo_trophy_result_abi[0])];
  for (size_t i = 0; i < sizeof(methods) / sizeof(methods[0]); ++i) {
    const FixdemoTrophyResultABI *check = &fixdemo_trophy_result_abi[i];
    methods[i] = so_try_find_addr_rx(module, check->name);
    if (!methods[i]) return 0;
    const uintptr_t backing = so_find_addr(module, check->name);
    if (backing != (uintptr_t)module->load_base + check->rva) return 0;
    uint64_t hash = UINT64_C(0xcbf29ce484222325);
    for (uint32_t byte = 0; byte < check->size; ++byte)
      hash = (hash ^ ((const unsigned char *)backing)[byte]) * UINT64_C(0x100000001b3);
    if (hash != check->fnv1a) return 0;
  }
  for (uint32_t i = 0; i < 8; ++i) {
    fixdemo_trophy_result_patch[i] = (uintptr_t)module->load_base + fixdemo_trophy_result_plt_rvas[i];
    if (memcmp((const void *)fixdemo_trophy_result_patch[i],
               fixdemo_trophy_result_plt_words[i], 16)) return 0;
  }
  for (uint32_t i = 0; i < 4; ++i) {
    fixdemo_trophy_result_slots[i] = find_vtable_method_slot(
        module, "_ZTV12FixDemoMatch", methods[11 + i], 29u);
    if (!fixdemo_trophy_result_slots[i]) return 0;
  }
  const uintptr_t pre_result_table = so_find_addr(module, "_ZTVN7process23ProcessMatchPreHalfTimeE");
  fixdemo_trophy_pre_result_slot = find_vtable_method_slot(module,
      "_ZTVN7process23ProcessMatchPreHalfTimeE", methods[34], 33u);
  if (pre_result_table != (uintptr_t)module->load_base + 0x942f4f8 ||
      (uintptr_t)fixdemo_trophy_pre_result_slot != pre_result_table + 0xe0) return 0;
  const char *fade_tables[2] = {"_ZTVN4fade7ManagerE", "_ZTVN4fade13ManagerMobileE"};
  const uintptr_t fade_rvas[2] = {0x948ff30, 0x948ffb8};
  for (uint32_t i = 0; i < 2; ++i) {
    const uintptr_t table = so_find_addr(module, fade_tables[i]);
    if (table != (uintptr_t)module->load_base + fade_rvas[i] ||
        (uintptr_t)fixdemo_trophy_pointer((const void *)table, 0x30) != methods[25 + i] ||
        (uintptr_t)fixdemo_trophy_pointer((const void *)table, 0x58) != methods[27 + i])
      return 0;
    fixdemo_trophy_fade_cancel[i] = methods[25 + i];
    fixdemo_trophy_fade_is_end[i] = methods[27 + i];
  }
  const uintptr_t fade_instance = so_find_addr(module, "_ZN4fade7Manager11m_pInstanceE");
  if (fade_instance != (uintptr_t)module->load_base + 0x9ca22e0) return 0;
  fixdemo_trophy_fade_instance = (const void *)fade_instance;
  fixdemo_trophy_create_original = (void *)methods[0];
  fixdemo_trophy_flow_original = (void *)methods[1];
  fixdemo_trophy_stats_team_id = (void *)methods[6];
  fixdemo_trophy_stats_team = (void *)methods[7];
  fixdemo_trophy_score = (void *)methods[8];
  fixdemo_trophy_match_original = (void *)methods[9];
  fixdemo_trophy_result_original = (void *)methods[10];
  fixdemo_trophy_delete_original = (void *)methods[11];
  fixdemo_trophy_destruct_original = (void *)methods[12];
  fixdemo_trophy_start_original = (void *)methods[13];
  fixdemo_trophy_end_original = (void *)methods[14];
  fixdemo_trophy_cut_ready_original = (void *)methods[15];
  fixdemo_trophy_global_registry = (void *)methods[17];
  fixdemo_trophy_ending_original = (void *)methods[18];
  fixdemo_trophy_set_environment = (void *)methods[20];
  fixdemo_trophy_read_lock = (void *)methods[22];
  fixdemo_trophy_read_unlock = (void *)methods[23];
  fixdemo_trophy_set_step = (void *)methods[24];
  fixdemo_trophy_result_caller = methods[0] + 0xe4;
  fixdemo_trophy_ending_caller = methods[18] + 0x774;
  fixdemo_trophy_wait_result_original = (void *)methods[32];
  fixdemo_trophy_listener_original = (void *)methods[33];
  fixdemo_trophy_pre_result_original = (void *)methods[34];
  fixdemo_trophy_listener_caller = methods[33] + 0x27c;
  fixdemo_trophy_result_prepared = 1;
  return 1;
}

static void fixdemo_trophy_result_commit(void) {
  if (!fixdemo_trophy_result_prepared || fixdemo_trophy_result_installed) return;
  const uintptr_t hooks[8] = {
    (uintptr_t)&fixdemo_trophy_create, (uintptr_t)&fixdemo_trophy_result_create,
    (uintptr_t)&fixdemo_trophy_flow, (uintptr_t)&fixdemo_trophy_cut_ready,
    (uintptr_t)&fixdemo_trophy_ending, (uintptr_t)&fixdemo_trophy_match_create,
    (uintptr_t)&fixdemo_trophy_wait_result, (uintptr_t)&fixdemo_trophy_listener
  };
  const uintptr_t virtuals[4] = {
    (uintptr_t)&fixdemo_trophy_delete, (uintptr_t)&fixdemo_trophy_destruct,
    (uintptr_t)&fixdemo_trophy_start, (uintptr_t)&fixdemo_trophy_end
  };
  for (uint32_t i = 0; i < 8; ++i)
    hook_arm64(fixdemo_trophy_result_patch[i], hooks[i]);
  for (uint32_t i = 0; i < 4; ++i) {
    *fixdemo_trophy_result_slots[i] = virtuals[i];
  }
  *fixdemo_trophy_pre_result_slot = (uintptr_t)&fixdemo_trophy_pre_result;
  fixdemo_trophy_result_installed = 1;
  fixdemo_trophy_note("result-listener-UI-and-ending-boundaries-installed opt-in-cup-final-only");
}
#endif

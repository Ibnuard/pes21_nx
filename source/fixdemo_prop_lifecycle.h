/* Bounded metadata handoff between native PES and UE callback lifetimes.
 * All addresses are identity values here; this file never dereferences them.
 * Callers may inspect native memory only through their current native callback
 * argument, not through a saved identity. No callback/native call runs locked.
 */
#ifndef PESNX_FIXDEMO_PROP_LIFECYCLE_H
#define PESNX_FIXDEMO_PROP_LIFECYCLE_H

#include <stdint.h>
#include <string.h>

enum FixDemoTrophyPropStatus {
  FIXDEMO_TROPHY_PROPS_PENDING,
  FIXDEMO_TROPHY_PROPS_READY,
  FIXDEMO_TROPHY_PROPS_FAILED
};
enum { FIXDEMO_PROP_WAIT_POLLS = 900, FIXDEMO_PROP_WAIT_MS = 15000 };

typedef struct {
  uint64_t epoch, generation, started_ms;
  uintptr_t owner, demo, model, ue;
  uint32_t key, kind, polls, ready;
} FixDemoPropTicket;

typedef struct {
  unsigned char lock;
  uint64_t epoch, failed_epoch; /* The only fields read without the lock. */
  uint64_t next_generation, started_ms;
  uint32_t polls, ready_mask, started;
  FixDemoPropTicket slots[2];
} FixDemoPropLifecycle;

static inline uint64_t fixdemo_prop_lifecycle_epoch(const FixDemoPropLifecycle *state) {
  return __atomic_load_n(&state->epoch, __ATOMIC_ACQUIRE);
}

static inline void fixdemo_prop_lifecycle_fail(FixDemoPropLifecycle *state, uint64_t epoch) {
  /* Read the tag before checking the epoch. A callback may pause across
   * cancel/begin; a newer failure must make its stale publication fail CAS,
   * then the epoch recheck must stop it from overwriting that newer tag. */
  uint64_t expected = __atomic_load_n(&state->failed_epoch, __ATOMIC_ACQUIRE);
  for (unsigned i = 0; i < 256u; ++i) {
    if (!epoch || fixdemo_prop_lifecycle_epoch(state) != epoch || expected == epoch) return;
    if (__atomic_compare_exchange_n(&state->failed_epoch, &expected, epoch, 0,
        __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE)) return;
  }
}

/* Contention cannot hang a native callback. A missed observation fails this
 * candidate rather than accepting an unobserved mesh. Critical sections contain
 * at most two metadata records, with no allocator, filesystem or native call. */
static inline int fixdemo_prop_lifecycle_lock(FixDemoPropLifecycle *state) {
  for (unsigned i = 0; i < 256u; ++i)
    if (!__atomic_test_and_set(&state->lock, __ATOMIC_ACQUIRE)) return 1;
  fixdemo_prop_lifecycle_fail(state, fixdemo_prop_lifecycle_epoch(state));
  return 0;
}

static inline void fixdemo_prop_lifecycle_unlock(FixDemoPropLifecycle *state) {
  __atomic_clear(&state->lock, __ATOMIC_RELEASE);
}

static inline int fixdemo_prop_lifecycle_begin(FixDemoPropLifecycle *state,
    uint64_t epoch, uint64_t now_ms) {
  if (!epoch || !fixdemo_prop_lifecycle_lock(state)) return 0;
  int ok = !fixdemo_prop_lifecycle_epoch(state) && state->next_generation != UINT64_MAX;
  if (ok) {
    memset(state->slots, 0, sizeof(state->slots));
    state->started_ms = now_ms;
    state->polls = state->ready_mask = state->started = 0;
    __atomic_store_n(&state->failed_epoch, 0, __ATOMIC_RELEASE);
    __atomic_store_n(&state->epoch, epoch, __ATOMIC_RELEASE);
  }
  fixdemo_prop_lifecycle_unlock(state);
  return ok;
}

static inline void fixdemo_prop_lifecycle_cancel(FixDemoPropLifecycle *state, uint64_t epoch) {
  uint64_t expected = epoch;
  /* Invalidate even if metadata is contended: native destruction must never
   * leave an active observer. The next begin resets records while locked. */
  if (!epoch || !__atomic_compare_exchange_n(&state->epoch, &expected, 0, 0,
      __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE) || !fixdemo_prop_lifecycle_lock(state)) return;
  if (!fixdemo_prop_lifecycle_epoch(state)) {
    memset(state->slots, 0, sizeof(state->slots));
    state->ready_mask = 0;
  }
  fixdemo_prop_lifecycle_unlock(state);
}

static inline int fixdemo_prop_lifecycle_register(FixDemoPropLifecycle *state,
    uint64_t epoch, uint32_t kind, uintptr_t owner, uintptr_t demo, uintptr_t model,
    uint32_t key, uint64_t now_ms) {
  if (!epoch || kind < 1u || kind > 2u || !owner || !demo || !model || key >= 192u ||
      !fixdemo_prop_lifecycle_lock(state)) return 0;
  FixDemoPropTicket *slot = &state->slots[kind - 1u];
  int ok = fixdemo_prop_lifecycle_epoch(state) == epoch && !slot->owner &&
      state->next_generation != UINT64_MAX;
  if (ok) {
    state->ready_mask &= ~(1u << (kind - 1u));
    *slot = (FixDemoPropTicket){.epoch = epoch, .generation = ++state->next_generation,
        .started_ms = now_ms, .owner = owner, .demo = demo, .model = model,
        .key = key, .kind = kind};
  } else fixdemo_prop_lifecycle_fail(state, epoch);
  fixdemo_prop_lifecycle_unlock(state);
  return ok;
}

/* Select by a live callback argument only: 0=owner, 1=model, 2=UE object. */
static inline int fixdemo_prop_lifecycle_find(FixDemoPropLifecycle *state,
    uintptr_t current, unsigned field, FixDemoPropTicket *ticket) {
  if (!current || !ticket || field > 2u || !fixdemo_prop_lifecycle_epoch(state) ||
      !fixdemo_prop_lifecycle_lock(state)) return 0;
  int found = 0;
  for (unsigned i = 0; i < 2u; ++i) {
    const FixDemoPropTicket *slot = &state->slots[i];
    const uintptr_t id = field == 0 ? slot->owner : field == 1 ? slot->model : slot->ue;
    if (id == current && slot->epoch == fixdemo_prop_lifecycle_epoch(state)) {
      *ticket = *slot;
      found = 1;
      break;
    }
  }
  fixdemo_prop_lifecycle_unlock(state);
  return found;
}

static inline int fixdemo_prop_lifecycle_same(const FixDemoPropTicket *a,
    const FixDemoPropTicket *b) {
  return a->epoch && a->epoch == b->epoch && a->generation == b->generation &&
      a->owner == b->owner && a->demo == b->demo && a->model == b->model &&
      a->key == b->key && a->kind == b->kind;
}

static inline int fixdemo_prop_lifecycle_bind(FixDemoPropLifecycle *state,
    const FixDemoPropTicket *ticket, uintptr_t ue) {
  if (!ticket || ticket->kind < 1u || ticket->kind > 2u || !ue ||
      !fixdemo_prop_lifecycle_lock(state)) return 0;
  FixDemoPropTicket *slot = &state->slots[ticket->kind - 1u];
  int ok = fixdemo_prop_lifecycle_epoch(state) == ticket->epoch &&
      fixdemo_prop_lifecycle_same(slot, ticket) && (!slot->ue || slot->ue == ue);
  if (ok) slot->ue = ue;
  else fixdemo_prop_lifecycle_fail(state, ticket->epoch);
  fixdemo_prop_lifecycle_unlock(state);
  return ok;
}

/* Called only after the actual UE LoadImpl returns and its component-bound
 * mesh was checked on that same native callback thread. A stale completion
 * does not touch the replacement generation, even at reused addresses. */
static inline int fixdemo_prop_lifecycle_complete(FixDemoPropLifecycle *state,
    const FixDemoPropTicket *ticket, int bound_mesh) {
  if (!ticket || ticket->kind < 1u || ticket->kind > 2u ||
      !fixdemo_prop_lifecycle_lock(state)) return 0;
  FixDemoPropTicket *slot = &state->slots[ticket->kind - 1u];
  int accepted = fixdemo_prop_lifecycle_epoch(state) == ticket->epoch &&
      fixdemo_prop_lifecycle_same(slot, ticket) && ticket->ue && slot->ue == ticket->ue;
  if (accepted) {
    if (bound_mesh == 1) {
      slot->ready = 1;
      state->ready_mask |= 1u << (ticket->kind - 1u);
    } else fixdemo_prop_lifecycle_fail(state, ticket->epoch);
  }
  fixdemo_prop_lifecycle_unlock(state);
  return accepted;
}

static inline void fixdemo_prop_lifecycle_retire(FixDemoPropLifecycle *state,
    uintptr_t owner, uint64_t now_ms) {
  if (!owner || !fixdemo_prop_lifecycle_epoch(state) || !fixdemo_prop_lifecycle_lock(state)) return;
  for (unsigned i = 0; i < 2u; ++i)
    if (state->slots[i].owner == owner) {
      if (state->ready_mask == 3u) {
        state->started_ms = now_ms;
        state->polls = 0;
      }
      state->ready_mask &= ~(1u << i);
      memset(&state->slots[i], 0, sizeof(state->slots[i]));
    }
  fixdemo_prop_lifecycle_unlock(state);
}

static inline int fixdemo_prop_lifecycle_owner_ready(FixDemoPropLifecycle *state,
    const FixDemoPropTicket *ticket, uintptr_t demo, uintptr_t model, uint32_t key,
    uint64_t now_ms) {
  if (!ticket || ticket->kind < 1u || ticket->kind > 2u ||
      !fixdemo_prop_lifecycle_lock(state)) return 0;
  FixDemoPropTicket *slot = &state->slots[ticket->kind - 1u];
  int valid = fixdemo_prop_lifecycle_epoch(state) == ticket->epoch &&
      fixdemo_prop_lifecycle_same(slot, ticket) && demo == slot->demo &&
      model == slot->model && key == slot->key;
  int ready = valid && slot->ready;
  if (!valid || (!ready && (++slot->polls > FIXDEMO_PROP_WAIT_POLLS ||
      now_ms < slot->started_ms || now_ms - slot->started_ms > FIXDEMO_PROP_WAIT_MS)))
    fixdemo_prop_lifecycle_fail(state, ticket->epoch);
  if (__atomic_load_n(&state->failed_epoch, __ATOMIC_ACQUIRE) == ticket->epoch) ready = 0;
  fixdemo_prop_lifecycle_unlock(state);
  return ready;
}

static inline enum FixDemoTrophyPropStatus fixdemo_prop_lifecycle_check(
    FixDemoPropLifecycle *state, uint64_t epoch, uint64_t now_ms, int count_frame) {
  if (!epoch || fixdemo_prop_lifecycle_epoch(state) != epoch ||
      !fixdemo_prop_lifecycle_lock(state)) return FIXDEMO_TROPHY_PROPS_FAILED;
  if (count_frame) ++state->polls;
  if (!state->started && state->ready_mask != 3u && (state->polls > FIXDEMO_PROP_WAIT_POLLS ||
      now_ms < state->started_ms || now_ms - state->started_ms > FIXDEMO_PROP_WAIT_MS))
    fixdemo_prop_lifecycle_fail(state, epoch);
  for (unsigned i = 0; i < 2u; ++i) {
    const FixDemoPropTicket *slot = &state->slots[i];
    if (slot->owner && !slot->ready && (now_ms < slot->started_ms ||
        now_ms - slot->started_ms > FIXDEMO_PROP_WAIT_MS))
      fixdemo_prop_lifecycle_fail(state, epoch);
  }
  enum FixDemoTrophyPropStatus result =
      __atomic_load_n(&state->failed_epoch, __ATOMIC_ACQUIRE) == epoch ?
      FIXDEMO_TROPHY_PROPS_FAILED : state->ready_mask == 3u || state->started ?
      FIXDEMO_TROPHY_PROPS_READY : FIXDEMO_TROPHY_PROPS_PENDING;
  fixdemo_prop_lifecycle_unlock(state);
  return result;
}

static inline int fixdemo_prop_lifecycle_started(FixDemoPropLifecycle *state, uint64_t epoch) {
  if (!epoch || !fixdemo_prop_lifecycle_lock(state)) return 0;
  const int ready = fixdemo_prop_lifecycle_epoch(state) == epoch && state->ready_mask == 3u &&
      __atomic_load_n(&state->failed_epoch, __ATOMIC_ACQUIRE) != epoch;
  if (ready) state->started = 1;
  else fixdemo_prop_lifecycle_fail(state, epoch);
  fixdemo_prop_lifecycle_unlock(state);
  return ready;
}

static inline enum FixDemoTrophyPropStatus fixdemo_prop_lifecycle_status(
    FixDemoPropLifecycle *state, uint64_t epoch, uint64_t now_ms) {
  return fixdemo_prop_lifecycle_check(state, epoch, now_ms, 1);
}

static inline enum FixDemoTrophyPropStatus fixdemo_prop_lifecycle_peek(
    FixDemoPropLifecycle *state, uint64_t epoch, uint64_t now_ms) {
  return fixdemo_prop_lifecycle_check(state, epoch, now_ms, 0);
}

#endif

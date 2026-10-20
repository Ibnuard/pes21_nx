#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* Deterministically pause an atomic load after its value was captured. This
 * schedules cancel/begin/failure exactly inside an old callback's epoch check;
 * the production implementation still uses the compiler atomics directly. */
static uint64_t test_atomic_load(const uint64_t *value, int order);
#define __atomic_load_n(value, order) test_atomic_load((value), (order))
#include "../source/fixdemo_prop_lifecycle.h"
#undef __atomic_load_n

static const uint64_t *interleave_load;
static void (*interleave_action)(void);
static FixDemoPropLifecycle *interleave_state;

static uint64_t test_atomic_load(const uint64_t *value, int order) {
  const uint64_t captured = __atomic_load_n(value, order);
  if (value == interleave_load && interleave_action) {
    void (*action)(void) = interleave_action;
    interleave_action = NULL;
    action();
  }
  return captured;
}

static void replace_epoch_and_fail(void) {
  fixdemo_prop_lifecycle_cancel(interleave_state, 7);
  assert(fixdemo_prop_lifecycle_begin(interleave_state, 8, 101));
  fixdemo_prop_lifecycle_fail(interleave_state, 8);
  assert(fixdemo_prop_lifecycle_status(interleave_state, 8, 101) == FIXDEMO_TROPHY_PROPS_FAILED);
}

static void test_failure_epoch_race(void) {
  FixDemoPropLifecycle s = {0};
  assert(fixdemo_prop_lifecycle_begin(&s, 7, 100));
  interleave_state = &s;
  interleave_load = &s.epoch;
  interleave_action = replace_epoch_and_fail;
  fixdemo_prop_lifecycle_fail(&s, 7);
  assert(!interleave_action);
  assert(fixdemo_prop_lifecycle_epoch(&s) == 8);
  assert(__atomic_load_n(&s.failed_epoch, __ATOMIC_ACQUIRE) == 8);
  assert(fixdemo_prop_lifecycle_status(&s, 8, 102) == FIXDEMO_TROPHY_PROPS_FAILED);
  interleave_load = NULL;
  interleave_state = NULL;
}

static FixDemoPropTicket register_prop(FixDemoPropLifecycle *s, unsigned kind) {
  const uintptr_t base = 0x10000u * kind;
  assert(fixdemo_prop_lifecycle_register(s, 7, kind, base, base + 8, base + 16, kind, 100));
  FixDemoPropTicket t;
  assert(fixdemo_prop_lifecycle_find(s, base + 16, 1, &t));
  assert(fixdemo_prop_lifecycle_bind(s, &t, base + 24));
  assert(fixdemo_prop_lifecycle_find(s, base + 24, 2, &t));
  return t;
}

static void test_readiness(void) {
  FixDemoPropLifecycle s = {0};
  assert(!fixdemo_prop_lifecycle_begin(&s, 0, 100));
  assert(fixdemo_prop_lifecycle_begin(&s, 7, 100));
  assert(!fixdemo_prop_lifecycle_begin(&s, 8, 100));
  assert(fixdemo_prop_lifecycle_peek(&s, 7, 100) == FIXDEMO_TROPHY_PROPS_PENDING);
  FixDemoPropTicket a = register_prop(&s, 1), b = register_prop(&s, 2);
  assert(!fixdemo_prop_lifecycle_owner_ready(&s, &a, a.demo, a.model, a.key, 101));
  assert(fixdemo_prop_lifecycle_complete(&s, &a, 1));
  assert(fixdemo_prop_lifecycle_owner_ready(&s, &a, a.demo, a.model, a.key, 102));
  assert(fixdemo_prop_lifecycle_status(&s, 7, 102) == FIXDEMO_TROPHY_PROPS_PENDING);
  assert(fixdemo_prop_lifecycle_complete(&s, &b, 1));
  assert(fixdemo_prop_lifecycle_status(&s, 7, 103) == FIXDEMO_TROPHY_PROPS_READY);
  assert(fixdemo_prop_lifecycle_status(&s, 7, 1000000) == FIXDEMO_TROPHY_PROPS_READY);
  assert(!fixdemo_prop_lifecycle_owner_ready(&s, &a, a.demo, a.model, a.key + 1, 104));
  assert(fixdemo_prop_lifecycle_status(&s, 7, 104) == FIXDEMO_TROPHY_PROPS_FAILED);
}

static void test_bounds(void) {
  FixDemoPropLifecycle s = {0};
  assert(fixdemo_prop_lifecycle_begin(&s, 7, 100));
  for (unsigned i = 0; i < 2000; ++i)
    assert(fixdemo_prop_lifecycle_peek(&s, 7, 101) == FIXDEMO_TROPHY_PROPS_PENDING);
  for (unsigned i = 0; i < FIXDEMO_PROP_WAIT_POLLS; ++i)
    assert(fixdemo_prop_lifecycle_status(&s, 7, 101) == FIXDEMO_TROPHY_PROPS_PENDING);
  assert(fixdemo_prop_lifecycle_status(&s, 7, 101) == FIXDEMO_TROPHY_PROPS_FAILED);
  fixdemo_prop_lifecycle_cancel(&s, 7);
  assert(fixdemo_prop_lifecycle_begin(&s, 7, 100));
  assert(fixdemo_prop_lifecycle_peek(&s, 7, 15100) == FIXDEMO_TROPHY_PROPS_PENDING);
  assert(fixdemo_prop_lifecycle_peek(&s, 7, 15101) == FIXDEMO_TROPHY_PROPS_FAILED);
  fixdemo_prop_lifecycle_cancel(&s, 7);
  assert(fixdemo_prop_lifecycle_begin(&s, 7, 100));
  FixDemoPropTicket a = register_prop(&s, 1);
  assert(!fixdemo_prop_lifecycle_owner_ready(&s, &a, a.demo, a.model, a.key, 15101));
  assert(fixdemo_prop_lifecycle_status(&s, 7, 15101) == FIXDEMO_TROPHY_PROPS_FAILED);
  fixdemo_prop_lifecycle_cancel(&s, 7);
  assert(fixdemo_prop_lifecycle_begin(&s, 7, 100));
  assert(fixdemo_prop_lifecycle_peek(&s, 7, 99) == FIXDEMO_TROPHY_PROPS_FAILED);
}

static void test_teardown(void) {
  FixDemoPropLifecycle s = {0};
  assert(fixdemo_prop_lifecycle_begin(&s, 7, 100));
  FixDemoPropTicket old = register_prop(&s, 1);
  fixdemo_prop_lifecycle_retire(&s, old.owner, 101);
  FixDemoPropTicket replacement = register_prop(&s, 1);
  assert(replacement.generation != old.generation);
  assert(!fixdemo_prop_lifecycle_complete(&s, &old, 1));
  assert(!fixdemo_prop_lifecycle_complete(&s, &old, 0));
  assert(fixdemo_prop_lifecycle_peek(&s, 7, 101) == FIXDEMO_TROPHY_PROPS_PENDING);
  assert(fixdemo_prop_lifecycle_complete(&s, &replacement, 1));
  fixdemo_prop_lifecycle_cancel(&s, 999);
  assert(fixdemo_prop_lifecycle_epoch(&s) == 7);
  fixdemo_prop_lifecycle_cancel(&s, 7);
  assert(!fixdemo_prop_lifecycle_complete(&s, &replacement, 1));
  assert(fixdemo_prop_lifecycle_begin(&s, 8, 102));
  assert(!fixdemo_prop_lifecycle_complete(&s, &replacement, 0));
  assert(fixdemo_prop_lifecycle_peek(&s, 8, 102) == FIXDEMO_TROPHY_PROPS_PENDING);
  /* Even cancellation while another metadata operation owns the lock must
   * invalidate observers before native destruction proceeds. */
  s.lock = 1;
  fixdemo_prop_lifecycle_cancel(&s, 8);
  assert(!fixdemo_prop_lifecycle_epoch(&s));
  s.lock = 0;
  assert(fixdemo_prop_lifecycle_begin(&s, 9, 104));
}

static void test_failure(void) {
  FixDemoPropLifecycle s = {0};
  assert(fixdemo_prop_lifecycle_begin(&s, 7, 100));
  FixDemoPropTicket a = register_prop(&s, 1);
  assert(fixdemo_prop_lifecycle_complete(&s, &a, 0));
  assert(!fixdemo_prop_lifecycle_owner_ready(&s, &a, a.demo, a.model, a.key, 101));
  assert(fixdemo_prop_lifecycle_status(&s, 7, 101) == FIXDEMO_TROPHY_PROPS_FAILED);
  fixdemo_prop_lifecycle_cancel(&s, 7);
  assert(fixdemo_prop_lifecycle_begin(&s, 7, 100));
  a = register_prop(&s, 1);
  assert(!fixdemo_prop_lifecycle_bind(&s, &a, a.ue + 8));
  assert(fixdemo_prop_lifecycle_status(&s, 7, 101) == FIXDEMO_TROPHY_PROPS_FAILED);
  fixdemo_prop_lifecycle_cancel(&s, 7);
  assert(fixdemo_prop_lifecycle_begin(&s, 7, 100));
  s.lock = 1;
  assert(fixdemo_prop_lifecycle_status(&s, 7, 100) == FIXDEMO_TROPHY_PROPS_FAILED);
  s.lock = 0;
}

static void test_cut_reload(void) {
  FixDemoPropLifecycle s = {0};
  assert(fixdemo_prop_lifecycle_begin(&s, 7, 100));
  FixDemoPropTicket a = register_prop(&s, 1), b = register_prop(&s, 2);
  assert(fixdemo_prop_lifecycle_complete(&s, &a, 1));
  assert(fixdemo_prop_lifecycle_complete(&s, &b, 1));
  assert(fixdemo_prop_lifecycle_status(&s, 7, 20000) == FIXDEMO_TROPHY_PROPS_READY);
  fixdemo_prop_lifecycle_retire(&s, a.owner, 20000);
  assert(fixdemo_prop_lifecycle_status(&s, 7, 20001) == FIXDEMO_TROPHY_PROPS_PENDING);
  assert(fixdemo_prop_lifecycle_register(&s, 7, 1, a.owner, a.demo, a.model, a.key, 20000));
  FixDemoPropTicket newer;
  assert(fixdemo_prop_lifecycle_find(&s, a.model, 1, &newer));
  assert(fixdemo_prop_lifecycle_bind(&s, &newer, a.ue));
  assert(fixdemo_prop_lifecycle_find(&s, a.ue, 2, &newer));
  assert(!fixdemo_prop_lifecycle_complete(&s, &a, 1));
  assert(fixdemo_prop_lifecycle_peek(&s, 7, 20001) == FIXDEMO_TROPHY_PROPS_PENDING);
  assert(fixdemo_prop_lifecycle_complete(&s, &newer, 1));
  assert(fixdemo_prop_lifecycle_peek(&s, 7, 20002) == FIXDEMO_TROPHY_PROPS_READY);
  fixdemo_prop_lifecycle_retire(&s, b.owner, 20003);
  assert(fixdemo_prop_lifecycle_status(&s, 7, 35004) == FIXDEMO_TROPHY_PROPS_FAILED);
}

static void test_started(void) {
  FixDemoPropLifecycle s = {0};
  assert(fixdemo_prop_lifecycle_begin(&s, 7, 100));
  FixDemoPropTicket a = register_prop(&s, 1), b = register_prop(&s, 2);
  assert(fixdemo_prop_lifecycle_complete(&s, &a, 1));
  assert(fixdemo_prop_lifecycle_complete(&s, &b, 1));
  assert(!fixdemo_prop_lifecycle_started(&s, 8));
  assert(fixdemo_prop_lifecycle_started(&s, 7));
  fixdemo_prop_lifecycle_retire(&s, a.owner, 20000);
  fixdemo_prop_lifecycle_retire(&s, b.owner, 20000);
  assert(fixdemo_prop_lifecycle_peek(&s, 7, 1000000) == FIXDEMO_TROPHY_PROPS_READY);
  assert(fixdemo_prop_lifecycle_register(&s, 7, 1, a.owner, a.demo, a.model, a.key, 1000000));
  assert(fixdemo_prop_lifecycle_peek(&s, 7, 1000001) == FIXDEMO_TROPHY_PROPS_READY);
  assert(fixdemo_prop_lifecycle_peek(&s, 7, 1015001) == FIXDEMO_TROPHY_PROPS_FAILED);
}

int main(int argc, char **argv) {
  assert(argc == 2);
  if (!strcmp(argv[1], "readiness")) test_readiness();
  else if (!strcmp(argv[1], "bounds")) test_bounds();
  else if (!strcmp(argv[1], "teardown")) test_teardown();
  else if (!strcmp(argv[1], "failure")) test_failure();
  else if (!strcmp(argv[1], "failure-epoch-race")) test_failure_epoch_race();
  else if (!strcmp(argv[1], "cut-reload")) test_cut_reload();
  else if (!strcmp(argv[1], "started")) test_started();
  else return 2;
  puts("prop lifecycle: pass");
  return 0;
}

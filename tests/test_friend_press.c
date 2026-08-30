// Host test of the adapter's gates/restoration, not the proprietary ThinkUnit.
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef struct { int unused; } so_module;
static uint64_t clock_ms;
static uint64_t armGetSystemTick(void) { return clock_ms * 1000000; }
static uint64_t armTicksToNs(uint64_t ticks) { return ticks; }
static uintptr_t so_try_find_addr_rx(so_module *m, const char *s) {
  (void)m; (void)s; return 0;
}
static uintptr_t so_find_addr(so_module *m, const char *s) {
  (void)m; (void)s; return 0;
}
static uintptr_t *find_vtable_method_slot(so_module *m, const char *s,
                                         uintptr_t p, int n) {
  (void)m; (void)s; (void)p; (void)n; return NULL;
}
static uint32_t defense;
static uint32_t mode_defense(const void *p) { (void)p; return defense; }
static uint32_t (*mobile_is_mode_defense)(const void *) = mode_defense;

#include "friend_press.inc"

static uint32_t history[2], observed_current, observed_previous;
static uint8_t observed_double;
static int missing_history;
static void *get_history(void *p, int index) {
  assert(p == history);
  return missing_history ? NULL : &history[index];
}
static int original_main(void *unit, const void *input, uint32_t kind) {
  (void)input;
  assert(kind == 42);
  observed_current = history[0];
  observed_previous = history[1];
  observed_double = *((uint8_t *)unit + 0x38);
  return 6;
}

int main(void) {
  _Alignas(8) uint8_t input[0x40] = {0}, cursor[0x20] = {0}, unit[0x40] = {0};
  void *accessor = history;
  void *accessor_ptr = &accessor, *cursor_ptr = cursor;
  memcpy(input + 8, &accessor_ptr, sizeof(accessor_ptr));
  memcpy(input + 0x18, &cursor_ptr, sizeof(cursor_ptr));
  uint32_t pad_id = 3;
  memcpy(unit + 8, &pad_id, sizeof(pad_id));
  unit[0x38] = 1;
  history[0] = 2;
  history[1] = 4;
  native_friend_press_main = original_main;
  native_pad_input_get = get_history;
  install_friend_press_prototype(NULL); // Missing native symbols: no patch.
  assert(!friend_press_installed);
  defense = 1;
  clock_ms = 1000;
  pes_controller_friend_press_update(1, clock_ms);
  assert(pes_friend_press_main(unit, input, 42) == 6);
  assert(observed_current == 10 && observed_previous == 12 && !observed_double);
  assert(history[0] == 2 && history[1] == 4 && unit[0x38] == 1);
  clock_ms = 1101;
  pes_friend_press_main(unit, input, 42);
  assert(observed_current == 2 && observed_previous == 4 && observed_double == 1);
  pes_controller_friend_press_update(1, clock_ms);
  defense = 0;
  pes_friend_press_main(unit, input, 42);
  assert(observed_current == 2);
  defense = 1;
  int32_t remote = 1;
  memcpy(cursor + 16, &remote, sizeof(remote));
  pes_friend_press_main(unit, input, 42);
  assert(observed_current == 2);
  memset(cursor + 16, 0, sizeof(remote));
  missing_history = 1;
  pes_friend_press_main(unit, input, 42);
  assert(observed_current == 2);
  missing_history = 0;
  pes_controller_friend_press_update(0, clock_ms);
  pes_friend_press_main(unit, input, 42);
  assert(observed_current == 2);
  puts("PASS FriendPress adapter: held, expiry, release, defense/local gates, history restoration");
}

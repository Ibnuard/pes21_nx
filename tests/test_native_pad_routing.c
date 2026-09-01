// Host tests execute the SAME adapter compiled into the Switch NRO.
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define NATIVE_PAD_LAB_HOST_TEST
static int active;
static uint64_t cobra_pad_input;
static uint32_t cobra_pad_connected;
static int pes_controller_native_pad_lab_active(void) { return active; }
#include "../source/native_pad_lab.inc"

static _Alignas(8) unsigned char list[0x3f00], before[sizeof(list)];
static _Alignas(8) unsigned char input[0x80], cursor[0xa0];
static uintptr_t objects[97];
static uint32_t history[5];
static void *accessor;
static int calls, sample_calls;

static void stock_list(void *p, const void *in, uint32_t previous, uint32_t context) {
  assert(p == list && in == input && previous == 61 && context == 7);
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
  active = 1;
  native_lab_installed = 1;
  calls = sample_calls = 0;
  native_pad_lab_reset();
  native_lab_list_update_original = stock_list;
  native_lab_sample_original = stock_sample;
  native_lab_history_get = get_history;
  accessor = history;
  *(void **)(input+8) = &accessor;
  *(void **)(input+0x18) = cursor;
  *(uint32_t *)(input+0x24) = 4;
  for (unsigned i = 0; i < sizeof(native_lab_units)/sizeof(native_lab_units[0]); i++) {
    NativeLabUnit *unit = &native_lab_units[i];
    unit->vptr = 1000+unit->kind;
    objects[unit->kind] = unit->vptr;
    *(void **)(list+0x3bf8+unit->kind*8) = &objects[unit->kind];
  }
}
static void run(const uint32_t *entries, uint32_t n) {
  *(uint32_t *)list = n;
  memcpy(list+4, entries, n*4);
  memcpy(before, list, sizeof(list));
  native_lab_list_update(list, input, 61, 7);
  assert(calls == 1);
}
static void unchanged(void) { assert(!memcmp(list, before, sizeof(list))); }

int main(void) {
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

  setup(); active = 0; run(attack,6); unchanged(); // Exhibition.
  assert(pes_controller_native_pad_lab_status() == 0);
  setup(); *(uint32_t *)(input+0x24) = 11; run(attack,6); unchanged(); // Away CPU.
  setup(); *(int32_t *)(cursor+16) = 1; run(attack,6); unchanged(); // Not pad0.
  setup(); *(int32_t *)(cursor+16) = -1; run(attack,6); unchanged(); // Unowned.
  setup(); accessor = NULL; run(attack,6); unchanged();
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
  assert(!memcmp(history,copy,sizeof(copy)));
  native_pad_lab_reset();
  native_lab_sample(history,1,cursor,input);
  assert(!(pes_controller_native_pad_lab_status() & 2));
  active = 0; native_lab_sample(history,0,cursor,input);
  assert(native_lab_status == 0 && sample_calls == 3);
  setup(); float power = .75f; memcpy(history+2,&power,4);
  native_lab_sample(history,0,cursor,input);
  assert(pes_controller_native_pad_lab_status() & 2);
  puts("native-pad routing: pass (scope, types, actions, history, reset, bounds)");
  return 0;
}

#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif

typedef struct { void *load_base, *load_virtbase; size_t load_size; } so_module;
static int missing_method = -1, missing_vtable, native_calls[3];
static const char *const method_names[] = {
  "_ZN15FixDemoEntrance10SetSceneIdEv",
  "_ZN15FixDemoEntrance14StartDemoEventEv",
  "_ZN15FixDemoEntrance12EndDemoEventEv",
};
static size_t symbol_offset(const char *name) {
  if (!strcmp(name, "_ZTV15FixDemoEntrance")) return missing_vtable ? 0 : 0x400;
  for (int i = 0; i < 3; ++i)
    if (!strcmp(name, method_names[i])) return missing_method == i ? 0 : 0x100 * (i + 1);
  assert(0); return 0;
}
static uintptr_t so_try_find_addr_rx(so_module *module, const char *name) {
  size_t offset = symbol_offset(name);
  return offset ? (uintptr_t)module->load_virtbase + offset : 0;
}
static uintptr_t so_find_addr(so_module *module, const char *name) {
  size_t offset = symbol_offset(name); assert(offset);
  return (uintptr_t)module->load_base + offset;
}
static uintptr_t *find_vtable_method_slot(so_module *module,
    const char *name, uintptr_t method, uint32_t limit) {
  uintptr_t *table = (void *)so_find_addr(module, name);
  for (uint32_t i = 2; i < limit; ++i) if (table[i] == method) return &table[i];
  return NULL;
}
#include "../source/fixdemo_scene_trace.inc"

static uint32_t test_scene = 777;
static void original_select(void *manager) {
  ++native_calls[0];
  const uint32_t *pointer = &test_scene;
  memcpy((char *)manager + 8, &pointer, sizeof(pointer));
  test_scene = 65537;
}
static void original_start(void *manager) { (void)manager; ++native_calls[1]; }
static void original_end(void *manager) { (void)manager; ++native_calls[2]; }

int main(int argc, char **argv) {
  assert(argc == 2);
  const char *scenario = argv[1];
  so_module module = {.load_size = 4096};
  module.load_base = calloc(1, module.load_size); assert(module.load_base);
#ifdef _WIN32
  SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
  module.load_virtbase = VirtualAlloc(NULL, module.load_size, MEM_RESERVE, PAGE_NOACCESS);
  assert(module.load_virtbase);
#else
  module.load_virtbase = mmap(NULL, module.load_size, PROT_NONE,
      MAP_PRIVATE | MAP_ANONYMOUS, -1, 0); assert(module.load_virtbase != MAP_FAILED);
#endif
  const uint32_t words[][8] = {
    {0xa9bf7bf3,0xaa0003f3,0x96e78401,0xf9400668,0x320083e9,0xb9000109,0xa8c17bf3,0xd65f03c0},
    {0xa9bf7bf3,0xaa0003f3,0x96ea4709,0x96e7768c,0x36000060,0xa8c17bf3,0xd65f03c0,0x96ea4704},
    {0xb9410c08,0x34000108,0xa9bf7bf3,0xaa0003f3,0x96ea46f4,0xbd410e60,0x7e21d800,0xa8c17bf3},
  };
  uintptr_t *vtable = (void *)((char *)module.load_base + 0x400);
  for (int i = 0; i < 3; ++i) {
    memcpy((char *)module.load_base + 0x100 * (i + 1), words[i], 32);
    vtable[2+i] = (uintptr_t)module.load_virtbase + 0x100 * (i + 1);
  }
  if (!strcmp(scenario,"missing-vtable")) missing_vtable = 1;
  int index;
  if (sscanf(scenario,"missing-method-%d", &index) == 1) missing_method = index;
  if (sscanf(scenario,"bad-opcode-%d", &index) == 1)
    memset((char *)module.load_base + 0x100 * (index + 1), 0, 4);
  if (sscanf(scenario,"bad-slot-%d", &index) == 1) vtable[2+index] = 0;
  uintptr_t before[32]; memcpy(before, vtable, sizeof(before));
  install_fixdemo_scene_trace(&module);
  const int enabled = !strcmp(scenario,"enabled");
  assert(fixdemo_trace_installed == enabled);
  assert(native_calls[0] == 0 && native_calls[1] == 0 && native_calls[2] == 0);
  if (!enabled) assert(!memcmp(before, vtable, sizeof(before)));
  else {
    assert(vtable[2] == (uintptr_t)&fixdemo_trace_select);
    assert(vtable[3] == (uintptr_t)&fixdemo_trace_start);
    assert(vtable[4] == (uintptr_t)&fixdemo_trace_end);
    assert((uintptr_t)fixdemo_trace_select_original == before[2]);
    assert((uintptr_t)fixdemo_trace_start_original == before[3]);
    assert((uintptr_t)fixdemo_trace_end_original == before[4]);
    install_fixdemo_scene_trace(&module); /* Idempotent; no wrapper recursion. */
    assert((uintptr_t)fixdemo_trace_select_original == before[2]);
    fixdemo_trace_select_original = original_select;
    fixdemo_trace_start_original = original_start;
    fixdemo_trace_end_original = original_end;
    unsigned char manager[24] = {0};
    fixdemo_trace_select(manager);
    assert(test_scene == 65537);
    fixdemo_trace_start(manager); fixdemo_trace_end(manager);
    assert(native_calls[0] == 1 && native_calls[1] == 1 && native_calls[2] == 1);
    assert(fixdemo_trace_scene(NULL) == 0);
    for (int i = 0; i < 200; ++i) fixdemo_trace_note("bounded",65537);
  }
#ifdef _WIN32
  VirtualFree(module.load_virtbase, 0, MEM_RELEASE);
#else
  munmap(module.load_virtbase, module.load_size);
#endif
  free(module.load_base);
  puts("fixdemo trace: pass");
  return 0;
}

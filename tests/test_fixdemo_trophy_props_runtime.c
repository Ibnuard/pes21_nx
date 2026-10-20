/* Synthetic callback lifetimes: no native game code, filesystem, or install. */
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

typedef struct { void *load_base, *load_virtbase; } so_module;
static uintptr_t so_try_find_addr_rx(so_module *m, const char *s) { (void)m; (void)s; return 0; }
static uintptr_t so_find_addr(so_module *m, const char *s) { (void)m; (void)s; return 0; }
static uintptr_t *find_vtable_method_slot(so_module *m, const char *s, uintptr_t p, unsigned n) {
  (void)m; (void)s; (void)p; (void)n; return NULL;
}
static unsigned patches;
static void hook_arm64(uintptr_t a, uintptr_t b) { (void)a; (void)b; ++patches; }
static uint64_t fake_ms = 100;
static uint64_t armGetSystemTick(void) { return fake_ms * 1000000u; }
static uint64_t armTicksToNs(uint64_t t) { return t; }
static int fixdemo_trophy_canary_validated;
static char fixdemo_trophy_verified_elf_sha256[65];
static unsigned notes;
static void fixdemo_trophy_note(const char *event) { assert(event); ++notes; }
#include "../source/fixdemo_trophy_props.inc"

typedef union { uint64_t align; unsigned char data[2048]; } Storage;
typedef struct { Storage owner, model, ue, impl, actor, component; } Rig;
static Rig rigs[2];
static unsigned creates, hidden, deleted, updates, callbacks;
static int native_ready = 1, load_failure;

static void pointer(void *base, unsigned offset, const void *value) {
  memcpy((char *)base + offset, &value, sizeof(value));
}
static void original_create(void *owner, int type, const char *path, void *skel, void *colors) {
  assert(owner && path); (void)type; (void)skel; (void)colors; ++creates;
}
static void *assign(void *out, const char *text, size_t size) {
  unsigned char *s = out;
  char *p = malloc(size + 1); assert(p);
  memcpy(p, text, size + 1); memset(s, 0, 24); s[0] = 1;
  memcpy(s + 8, &size, sizeof(size)); pointer(s, 16, p); return out;
}
static void construct(void *demo) { memset(demo, 0, 24); }
static int init(void *demo, void *input) {
  const FixDemoPropBackendLoadId *id = input;
  const unsigned which = id->object_id - 1u;
  assert(which < 2);
  pointer(demo, 8, rigs[which].model.data);
  const uint32_t key = which + 1;
  memcpy((char *)demo + 16, &key, sizeof(key));
  const char *name;
  memcpy(&name, id->name.bytes + 16, sizeof(name));
  strcpy((char *)rigs[which].impl.data, name);
  return 1;
}
static void display(void *demo, int visible) { assert(demo && !visible); ++hidden; }
static void delete_demo(void *demo) { ++deleted; free(demo); }
static int ready(void *owner) { assert(owner); return native_ready; }
static void model_update(void *model) {
  ++updates;
  for (unsigned i = 0; i < 2; ++i)
    if (model == rigs[i].model.data) pointer(model, 24, rigs[i].ue.data);
}
static void callback(void *ue, void *data) {
  assert(data == (void *)(uintptr_t)77); ++callbacks;
  for (unsigned i = 0; i < 2; ++i) {
    if (ue != rigs[i].ue.data) continue;
    pointer(rigs[i].impl.data, 520, rigs[i].actor.data);
    pointer(rigs[i].actor.data, 816, rigs[i].component.data);
    const void *mesh = load_failure ? NULL : (void *)(uintptr_t)(0x100000u * (i + 1u));
    pointer(rigs[i].actor.data, 824, mesh);
    pointer(rigs[i].component.data, 1456, mesh);
  }
}
static void destroy(void *owner) {
  void *demo = NULL;
  memcpy(&demo, (char *)owner + 184, sizeof(demo));
  if (demo) { delete_demo(demo); pointer(owner, 184, NULL); }
  FixDemoPropBackendString *name = (void *)((char *)owner + 248);
  fixdemo_prop_backend_release_string(&fixdemo_trophy_prop_ops, name);
}
static void setup(void) {
  fixdemo_trophy_prop_ops = (FixDemoPropBackendOps){original_create, assign, free,
      malloc, construct, init, display, delete_demo};
  fixdemo_trophy_prop_ready_original = ready;
  fixdemo_trophy_prop_destroy_original = destroy;
  fixdemo_trophy_prop_model_update_original = model_update;
  fixdemo_trophy_prop_ue_callback_original = callback;
  fixdemo_trophy_prop_installed = 1;
  for (unsigned i = 0; i < 2; ++i) {
    const uint16_t id = i + 1;
    memcpy(rigs[i].owner.data + 232, &id, sizeof(id));
    pointer(rigs[i].ue.data, 8, rigs[i].impl.data);
  }
}
static void create(unsigned i) {
  fixdemo_trophy_prop_game_scope = 1;
  fixdemo_trophy_prop_create(rigs[i].owner.data, 0,
      fixdemo_prop_mappings[i].runtime_path, NULL, NULL);
  fixdemo_trophy_prop_game_scope = 0;
}
static void update(unsigned i) {
  fixdemo_trophy_prop_model_update(rigs[i].model.data);
  fixdemo_trophy_prop_ue_callback(rigs[i].ue.data, (void *)(uintptr_t)77);
}
static void teardown(void) {
  fixdemo_trophy_props_cancel(7);
  for (unsigned i = 0; i < 2; ++i) fixdemo_trophy_prop_destroy(rigs[i].owner.data);
}

int main(int argc, char **argv) {
  assert(argc == 2); setup();
  if (!strcmp(argv[1], "inactive")) {
    create(0);
    assert(creates == 1 && hidden == 0 && !notes);
    fixdemo_trophy_prop_model_update(rigs[0].model.data);
    fixdemo_trophy_prop_ue_callback(rigs[0].ue.data, (void *)(uintptr_t)77);
    assert(updates == 1 && callbacks == 1 && !notes);
    assert(!fixdemo_trophy_props_prepare(NULL));
    fixdemo_trophy_props_commit(); assert(!patches);
  } else if (!strcmp(argv[1], "ready")) {
    assert(fixdemo_trophy_props_begin(7)); create(0); create(1);
    assert(hidden == 2 && !fixdemo_trophy_prop_ready(rigs[0].owner.data));
    update(0);
    assert(fixdemo_trophy_prop_ready(rigs[0].owner.data));
    assert(fixdemo_trophy_props_peek(7) == FIXDEMO_TROPHY_PROPS_PENDING);
    update(1);
    assert(fixdemo_trophy_props_status(7) == FIXDEMO_TROPHY_PROPS_READY);
    assert(notes == 2); teardown(); assert(deleted == 2);
  } else if (!strcmp(argv[1], "fast-or-cached")) {
    assert(fixdemo_trophy_props_begin(7));
    /* A registered UE callback can finish before our Create returns, or the
     * native load cache can supply an existing mesh. The next callback must
     * establish proof without forcing another LoadImpl invocation. */
    for (unsigned i = 0; i < 2; ++i) {
      strcpy((char *)rigs[i].impl.data, fixdemo_prop_mappings[i].ue_name);
      callback(rigs[i].ue.data, (void *)(uintptr_t)77);
      create(i);
      update(i);
    }
    assert(fixdemo_trophy_props_status(7) == FIXDEMO_TROPHY_PROPS_READY);
    teardown();
  } else if (!strcmp(argv[1], "missing-mesh")) {
    assert(fixdemo_trophy_props_begin(7)); create(0); load_failure = 1; update(0);
    assert(fixdemo_trophy_props_status(7) == FIXDEMO_TROPHY_PROPS_FAILED);
    assert(!fixdemo_trophy_prop_ready(rigs[0].owner.data)); teardown();
  } else if (!strcmp(argv[1], "late-callback")) {
    assert(fixdemo_trophy_props_begin(7)); create(0);
    fixdemo_trophy_prop_model_update(rigs[0].model.data);
    teardown();
    fixdemo_trophy_prop_ue_callback(rigs[0].ue.data, (void *)(uintptr_t)77);
    assert(!notes);
    assert(fixdemo_trophy_props_begin(8));
    assert(fixdemo_trophy_props_status(8) == FIXDEMO_TROPHY_PROPS_PENDING);
    fixdemo_trophy_props_cancel(8);
  } else return 2;
  puts("prop runtime callbacks: pass");
  return 0;
}

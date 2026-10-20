/* Exact-package canary for the two cooked trophy props. Included after the
 * common trophy configuration. No hooks are installed without its file proof.
 *
 * PES side: DataManager::UpdateInGameThread owns the native mutex around Exec.
 * UE side: OnHandleCallback calls LoadImpl synchronously. We inspect the actual
 * bound mesh at that boundary only. Identity/readiness crosses threads through
 * bounded metadata records; no saved UObject is dereferenced on the PES side.
 * ObjectModel::Update publishes the current UE identity. The native callback
 * manager runs registered handlers even when hidden; the next callback covers
 * a fast first load as well as a model reused from the native cache.
 */
#define PESNX_FIXDEMO_PROP_BACKEND_RUNTIME 1
#include "fixdemo_prop_backend.h"
#undef PESNX_FIXDEMO_PROP_BACKEND_RUNTIME
#include "fixdemo_prop_lifecycle.h"

static FixDemoPropLifecycle fixdemo_trophy_prop_lifecycle;
static FixDemoPropBackendOps fixdemo_trophy_prop_ops;
static int (*fixdemo_trophy_prop_exec_original)(void *, int);
static int (*fixdemo_trophy_prop_ready_original)(void *);
static void (*fixdemo_trophy_prop_destroy_original)(void *);
static void (*fixdemo_trophy_prop_model_update_original)(void *);
static void (*fixdemo_trophy_prop_ue_callback_original)(void *, void *);
static uintptr_t fixdemo_trophy_prop_game_returns[3];
static uintptr_t fixdemo_trophy_prop_plts[5];
static uintptr_t *fixdemo_trophy_prop_ue_callback_slot;
static uintptr_t *fixdemo_trophy_prop_destroy_slot;
static int fixdemo_trophy_prop_prepared, fixdemo_trophy_prop_installed;
static __thread unsigned fixdemo_trophy_prop_game_scope;

static uint64_t fixdemo_trophy_prop_now_ms(void) {
  return armTicksToNs(armGetSystemTick()) / 1000000u;
}

static int fixdemo_trophy_props_begin(uint64_t epoch) {
  return fixdemo_trophy_prop_installed && fixdemo_prop_lifecycle_begin(
      &fixdemo_trophy_prop_lifecycle, epoch, fixdemo_trophy_prop_now_ms());
}

static enum FixDemoTrophyPropStatus fixdemo_trophy_props_status(uint64_t epoch) {
  return fixdemo_prop_lifecycle_status(&fixdemo_trophy_prop_lifecycle,
      epoch, fixdemo_trophy_prop_now_ms());
}

static enum FixDemoTrophyPropStatus fixdemo_trophy_props_peek(uint64_t epoch) {
  return fixdemo_prop_lifecycle_peek(&fixdemo_trophy_prop_lifecycle,
      epoch, fixdemo_trophy_prop_now_ms());
}

static void fixdemo_trophy_props_cancel(uint64_t epoch) {
  fixdemo_prop_lifecycle_cancel(&fixdemo_trophy_prop_lifecycle, epoch);
}

static int fixdemo_trophy_props_started(uint64_t epoch) {
  return fixdemo_prop_lifecycle_started(&fixdemo_trophy_prop_lifecycle, epoch);
}

static int fixdemo_trophy_prop_exec(void *manager, int background) {
  const unsigned previous = fixdemo_trophy_prop_game_scope;
  /* Returning through this exact audited call proves that the native mutex is
   * held. A generic bool or a guessed thread ID is not equivalent evidence. */
  const uintptr_t caller = (uintptr_t)__builtin_return_address(0);
  fixdemo_trophy_prop_game_scope = background == 0 &&
      (caller == fixdemo_trophy_prop_game_returns[0] ||
       caller == fixdemo_trophy_prop_game_returns[1] ||
       caller == fixdemo_trophy_prop_game_returns[2]);
  const int result = fixdemo_trophy_prop_exec_original(manager, background);
  fixdemo_trophy_prop_game_scope = previous;
  return result;
}

static void fixdemo_trophy_prop_create(void *owner, int type, const char *path,
    void *skeleton, void *colors) {
  const uint64_t epoch = fixdemo_prop_lifecycle_epoch(&fixdemo_trophy_prop_lifecycle);
  if (!epoch) {
    fixdemo_trophy_prop_ops.create(owner, type, path, skeleton, colors);
    return;
  }
  fixdemo_prop_lifecycle_retire(&fixdemo_trophy_prop_lifecycle,
      (uintptr_t)owner, fixdemo_trophy_prop_now_ms());
  const size_t length = path ? strnlen(path, 128u) : 0u;
  const FixDemoPropMapping *mapping = fixdemo_prop_lookup(path, length, 0);
  if (!mapping || !fixdemo_trophy_prop_game_scope) {
    fixdemo_trophy_prop_ops.create(owner, type, path, skeleton, colors);
    if (mapping) fixdemo_prop_lifecycle_fail(&fixdemo_trophy_prop_lifecycle, epoch);
    return;
  }
  const enum FixDemoPropBackendResult result = fixdemo_prop_backend_candidate(
      &fixdemo_trophy_prop_ops, FIXDEMO_PROP_VALIDATED_BUT_INACTIVE, 1, owner,
      FIXDEMO_PROP_OWNER_MIN_BYTES, type, path, length, skeleton, colors);
  if (result != FIXDEMO_PROP_BACKEND_ATTACHED_HIDDEN) {
    fixdemo_prop_lifecycle_fail(&fixdemo_trophy_prop_lifecycle, epoch);
    fixdemo_trophy_note(mapping->kind == FIXDEMO_PROP_CUP ? "cup-create-failed" : "podium-create-failed");
    return;
  }
  /* Still on the live CreateObject argument and native locked queue boundary. */
  uintptr_t demo = 0, model = 0;
  uint32_t key = FIXDEMO_PROP_INVALID_LOAD_KEY;
  memcpy(&demo, (const char *)owner + 184u, sizeof(demo));
  memcpy(&model, (const void *)(demo + 8u), sizeof(model));
  memcpy(&key, (const void *)(demo + 16u), sizeof(key));
  if (!fixdemo_prop_lifecycle_register(&fixdemo_trophy_prop_lifecycle, epoch,
      mapping->kind, (uintptr_t)owner, demo, model, key, fixdemo_trophy_prop_now_ms()))
    fixdemo_prop_lifecycle_fail(&fixdemo_trophy_prop_lifecycle, epoch);
}

static int fixdemo_trophy_prop_ready(void *owner) {
  const int native_ready = fixdemo_trophy_prop_ready_original(owner);
  FixDemoPropTicket ticket;
  if (!fixdemo_prop_lifecycle_find(&fixdemo_trophy_prop_lifecycle,
      (uintptr_t)owner, 0u, &ticket)) return native_ready;
  if (!fixdemo_trophy_prop_game_scope) {
    /* ObjectData::IsReadyObject also polls outside DataManager's queue. Use
     * only synchronized identities here: native create/destructor wrappers
     * invalidate them before replacement. Never walk saved native pointers. */
    return native_ready && fixdemo_prop_lifecycle_owner_ready(
        &fixdemo_trophy_prop_lifecycle, &ticket, ticket.demo, ticket.model,
        ticket.key, fixdemo_trophy_prop_now_ms());
  }
  uintptr_t demo = 0, model = 0;
  uint32_t key = FIXDEMO_PROP_INVALID_LOAD_KEY;
  memcpy(&demo, (const char *)owner + 184u, sizeof(demo));
  /* A replacement demo is never dereferenced using the old ticket. */
  if (demo == ticket.demo) {
    memcpy(&model, (const void *)(demo + 8u), sizeof(model));
    memcpy(&key, (const void *)(demo + 16u), sizeof(key));
  }
  const int actual_ready = fixdemo_prop_lifecycle_owner_ready(
      &fixdemo_trophy_prop_lifecycle, &ticket, demo, model, key, fixdemo_trophy_prop_now_ms());
  return native_ready && actual_ready;
}

static void fixdemo_trophy_prop_destroy(void *owner) {
  fixdemo_prop_lifecycle_retire(&fixdemo_trophy_prop_lifecycle,
      (uintptr_t)owner, fixdemo_trophy_prop_now_ms());
  fixdemo_trophy_prop_destroy_original(owner);
}

static void fixdemo_trophy_prop_model_update(void *model) {
  fixdemo_trophy_prop_model_update_original(model);
  FixDemoPropTicket ticket;
  if (!fixdemo_prop_lifecycle_find(&fixdemo_trophy_prop_lifecycle,
      (uintptr_t)model, 1u, &ticket)) return;
  uintptr_t ue = 0;
  /* This is the live ObjectModel callback argument after its native update.
   * Publish only numeric identity; never inspect UE memory on this thread. */
  memcpy(&ue, (const char *)model + 24u, sizeof(ue));
  if (ue && !fixdemo_prop_lifecycle_bind(&fixdemo_trophy_prop_lifecycle, &ticket, ue))
    fixdemo_prop_lifecycle_fail(&fixdemo_trophy_prop_lifecycle, ticket.epoch);
}

/* This function is only called with the currently executing UEObject callback
 * argument. It deliberately does not walk owner/demo/model across threads. */
static int fixdemo_trophy_prop_bound_mesh(void *ue, const FixDemoPropTicket *ticket) {
  uintptr_t impl = 0, actor = 0, component = 0, asset = 0, bound = 0;
  if (!ue || ticket->kind < 1u || ticket->kind > 2u) return 0;
  memcpy(&impl, (const char *)ue + 8u, sizeof(impl));
  if (!impl) return 0;
  const char *name = fixdemo_prop_mappings[ticket->kind - 1u].ue_name;
  if (memcmp((const void *)impl, name, strlen(name) + 1u)) return 0;
  memcpy(&actor, (const void *)(impl + 520u), sizeof(actor));
  if (!actor) return -1; /* Still pending: native loader has not spawned it. */
  memcpy(&component, (const void *)(actor + 816u), sizeof(component));
  memcpy(&asset, (const void *)(actor + 824u), sizeof(asset));
  if (!component || !asset) return 0;
  memcpy(&bound, (const void *)(component + 1456u), sizeof(bound));
  return bound == asset;
}

static void fixdemo_trophy_prop_ue_callback(void *ue, void *data) {
  FixDemoPropTicket ticket;
  const int tracked = fixdemo_prop_lifecycle_find(&fixdemo_trophy_prop_lifecycle,
      (uintptr_t)ue, 2u, &ticket);
  fixdemo_trophy_prop_ue_callback_original(ue, data);
  if (tracked && fixdemo_prop_lifecycle_epoch(&fixdemo_trophy_prop_lifecycle) == ticket.epoch) {
    const int bound = fixdemo_trophy_prop_bound_mesh(ue, &ticket);
    if (bound >= 0 && fixdemo_prop_lifecycle_complete(&fixdemo_trophy_prop_lifecycle, &ticket, bound) && !ticket.ready)
      fixdemo_trophy_note(ticket.kind == FIXDEMO_PROP_CUP ?
          (bound ? "cup-mesh-ready" : "cup-mesh-failed") :
          (bound ? "podium-mesh-ready" : "podium-mesh-failed"));
  }
}

typedef struct {
  const char *symbol;
  uint32_t rva, plt, words[4], plt_words[4];
} FixDemoTrophyPropHook;
static const FixDemoTrophyPropHook fixdemo_trophy_prop_hooks[] = {
  {"_ZN7fixdemo11DataManager4ExecEb", 0x7b57ec4u, 0x38e5420u,
   {0xa9be53f5,0xa9017bf3,0xaa0003f3,0x91002000}, {0xf002e250,0xf9463611,0x9131a210,0xd61f0220}},
  {"_ZN13FixDemoObject12CreateObjectENS_4TYPEEPKcPN5cobra3And8SkelFileEPNS3_6texlib5ColorE", 0x7b8d8f8u, 0x3898250u,
   {0xd10483ff,0xa90f5bf7,0xa91053f5,0xa9117bf3}, {0xd002e390,0xf941c211,0x910e0210,0xd61f0220}},
  {"_ZN13FixDemoObject7IsReadyEv", 0x7b8e0c0u, 0x37fb8f0u,
   {0xf81e0ff4,0xa9017bf3,0xaa0003f3,0xf9405c00}, {0x9002e610,0xf9476a11,0x913b4210,0xd61f0220}},
  {"_ZN13FixDemoObjectD2Ev", 0x7b8d82cu, 0x3844ed0u,
   {0xa9bf7bf3,0xb000d208,0xaa0003f3,0xf9405c00}, {0x9002e4f0,0xf944e211,0x91270210,0xd61f0220}},
  {"_ZN6render11ObjectModel6UpdateEv", 0x7e145f8u, 0x3809510u,
   {0xfc190fe8,0xa9016ffc,0xa90267fa,0xa9035ff8}, {0xb002e5d0,0xf9467211,0x91338210,0xd61f0220}},
};

static int fixdemo_trophy_prop_read_symbol(void *context, const char *symbol,
    uint32_t offset, unsigned char bytes[32], uint64_t *rva) {
  so_module *module = context;
  const uintptr_t rx = so_try_find_addr_rx(module, symbol);
  if (!rx) return 0;
  *rva = rx - (uintptr_t)module->load_virtbase;
  memcpy(bytes, (const void *)(so_find_addr(module, symbol) + offset), 32u);
  return 1;
}

static int fixdemo_trophy_props_prepare(so_module *module) {
  fixdemo_trophy_prop_prepared = 0;
  if (!module || fixdemo_trophy_prop_installed || !fixdemo_trophy_canary_validated) return 0;
  const FixDemoPropAbiEvidence abi = {fixdemo_trophy_verified_elf_sha256, 64u, 64u, 183u, 1u,
      fixdemo_trophy_prop_read_symbol, module};
  if (!fixdemo_prop_validate_abi(&abi)) return 0;
  uintptr_t original[5];
  for (unsigned i = 0; i < 5u; ++i) {
    const FixDemoTrophyPropHook *entry = &fixdemo_trophy_prop_hooks[i];
    original[i] = so_try_find_addr_rx(module, entry->symbol);
    if (original[i] != (uintptr_t)module->load_virtbase + entry->rva ||
        memcmp((const void *)so_find_addr(module, entry->symbol), entry->words, sizeof(entry->words))) return 0;
    fixdemo_trophy_prop_plts[i] = (uintptr_t)module->load_base + entry->plt;
    if (memcmp((const void *)fixdemo_trophy_prop_plts[i], entry->plt_words, sizeof(entry->plt_words))) return 0;
  }
  /* Mutex + original-call provenance (UpdateInGameThread), queue split (Exec),
   * and UE callback's actual LoadImpl call are independently fingerprinted. */
  static const struct { const char *name; uint32_t rva, offset, words[4]; } boundaries[] = {
    {"_ZN7fixdemo11DataManager18UpdateInGameThreadEv",0x7b56f84u,0x8u,
     {0xb000d1e0,0xf947c800,0x96f27d07,0xb000d028}},
    {"_ZN14FixDemoCutFile4ExecEv",0x7b63c48u,0x18u,
     {0x9000d180,0xf947c800,0x96f249d2,0x9000cfc8}},
    {"_ZN11FixDemoMain4ExecEv",0x7b70870u,0x28u,
     {0xf000d100,0xf947c800,0x96f216c4,0xf000cf48}},
    {"_ZN8UEObject16OnHandleCallbackEPN8UESystem17UECallbackDefDataE",0x3f01600u,0x78u,
     {0xaa1303e0,0x97e4c711,0xf9400668,0x3908091f}},
  };
  for (unsigned i = 0; i < sizeof(boundaries)/sizeof(boundaries[0]); ++i) {
    const uintptr_t rx = so_try_find_addr_rx(module, boundaries[i].name);
    if (rx != (uintptr_t)module->load_virtbase + boundaries[i].rva ||
        memcmp((const void *)(so_find_addr(module, boundaries[i].name) + boundaries[i].offset),
            boundaries[i].words, sizeof(boundaries[i].words))) return 0;
  }
  const char *callback_name = "_ZN8UEObject16OnHandleCallbackEPN8UESystem17UECallbackDefDataE";
  const uintptr_t ue_callback = so_try_find_addr_rx(module, callback_name);
  static const uint32_t ue_callback_words[] = {0xd10203ff,0xfd001bea,0x6d0423e9,0xa90557f6};
  if (ue_callback != (uintptr_t)module->load_virtbase + 0x3f01600u ||
      memcmp((const void *)so_find_addr(module, callback_name), ue_callback_words, sizeof(ue_callback_words)) ||
      !so_try_find_addr_rx(module, "_ZTV8UEObject") || !so_try_find_addr_rx(module, "_ZTV13FixDemoObject")) return 0;
  fixdemo_trophy_prop_ue_callback_slot = find_vtable_method_slot(module, "_ZTV8UEObject", ue_callback, 15u);
  fixdemo_trophy_prop_destroy_slot = find_vtable_method_slot(module, "_ZTV13FixDemoObject", original[3], 6u);
  if (!fixdemo_trophy_prop_ue_callback_slot || !fixdemo_trophy_prop_destroy_slot) return 0;
  static const struct { const char *name; uint32_t rva; } dependencies[] = {
    {"_ZNSt6__ndk112basic_stringIcNS_11char_traitsIcEEN5cobra3stl9AllocatorIcEEE6assignEPKcm",0x61ec5f0u},
    {"BasicFree",0x61b8fb8u}, {"_Znwm",0x61b8d98u},
    {"_ZN4draw10DemoObjectC1Ev",0x7e225c4u},
    {"_ZN4draw10DemoObject4InitERNS_4load16DemoObjectLoadIdE",0x7e22664u},
    {"_ZN4draw10DemoObject7SetDispEb",0x7e2274cu}, {"_ZN4draw10DemoObjectD0Ev",0x7e22624u},
  };
  uintptr_t deps[7];
  for (unsigned i = 0; i < 7u; ++i) {
    deps[i] = so_try_find_addr_rx(module, dependencies[i].name);
    if (deps[i] != (uintptr_t)module->load_virtbase + dependencies[i].rva) return 0;
  }
  fixdemo_trophy_prop_exec_original = (void *)original[0];
  fixdemo_trophy_prop_ops.create = (void *)original[1];
  fixdemo_trophy_prop_ready_original = (void *)original[2];
  fixdemo_trophy_prop_destroy_original = (void *)original[3];
  fixdemo_trophy_prop_model_update_original = (void *)original[4];
  fixdemo_trophy_prop_ue_callback_original = (void *)ue_callback;
  fixdemo_trophy_prop_ops.assign_string = (void *)deps[0];
  fixdemo_trophy_prop_ops.basic_free = (void *)deps[1];
  fixdemo_trophy_prop_ops.allocate_demo = (void *)deps[2];
  fixdemo_trophy_prop_ops.construct_demo = (void *)deps[3];
  fixdemo_trophy_prop_ops.init_demo = (void *)deps[4];
  fixdemo_trophy_prop_ops.set_display = (void *)deps[5];
  fixdemo_trophy_prop_ops.delete_demo = (void *)deps[6];
  fixdemo_trophy_prop_game_returns[0] = (uintptr_t)module->load_virtbase + 0x7b56fb8u;
  fixdemo_trophy_prop_game_returns[1] = (uintptr_t)module->load_virtbase + 0x7b63c88u;
  fixdemo_trophy_prop_game_returns[2] = (uintptr_t)module->load_virtbase + 0x7b708c0u;
  fixdemo_trophy_prop_prepared = 1;
  return 1;
}

/* Parent commits only after both props and result-factory prepare succeed. */
static void fixdemo_trophy_props_commit(void) {
  if (!fixdemo_trophy_prop_prepared || fixdemo_trophy_prop_installed) return;
  const uintptr_t hooks[] = {(uintptr_t)&fixdemo_trophy_prop_exec,
      (uintptr_t)&fixdemo_trophy_prop_create, (uintptr_t)&fixdemo_trophy_prop_ready,
      (uintptr_t)&fixdemo_trophy_prop_destroy, (uintptr_t)&fixdemo_trophy_prop_model_update};
  for (unsigned i = 0; i < 5u; ++i) hook_arm64(fixdemo_trophy_prop_plts[i], hooks[i]);
  *fixdemo_trophy_prop_ue_callback_slot = (uintptr_t)&fixdemo_trophy_prop_ue_callback;
  *fixdemo_trophy_prop_destroy_slot = (uintptr_t)&fixdemo_trophy_prop_destroy;
  fixdemo_trophy_prop_installed = 1;
  fixdemo_trophy_note("props-hooks-installed");
}

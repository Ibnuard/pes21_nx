/* Isolated candidate for the native DemoObject route; NOT a runtime feature.
 *
 * Only probe translation units may opt into this implementation. The wrapper
 * does not include it, and the production preflight activation gate stays OFF.
 * No hooks, UObjects, renderer queues or per-frame transforms are installed.
 * A future integration still needs cooked-asset, thread/lifetime and hardware
 * validation in addition to the static ABI and bounded probes in the tests.
 *
 * Mobile A279...D187 evidence: FixDemoObject::CreateObject 0x7b8d8f8;
 * draw::DemoObject ctor 0x7e225c4, Init 0x7e22664, D0 0x7e22624.
 * Init returns 1 even when the manager returns its invalid key (192), so its
 * result alone cannot establish a model, much less a loaded render mesh.
 */
#ifndef PESNX_FIXDEMO_PROP_BACKEND_H
#define PESNX_FIXDEMO_PROP_BACKEND_H

#include "fixdemo_prop_bridge.inc"

#if defined(PESNX_FIXDEMO_PROP_BACKEND_PROBE) && PESNX_FIXDEMO_PROP_BACKEND_PROBE == 1

enum {
  FIXDEMO_PROP_OWNER_MIN_BYTES = 296,
  FIXDEMO_PROP_DEMO_BYTES = 24,
  FIXDEMO_PROP_INVALID_LOAD_KEY = 192
};

typedef union {
  uint64_t alignment;
  unsigned char bytes[24];
} FixDemoPropBackendString;

typedef struct {
  uint16_t object_id;
  unsigned char padding0[6];
  FixDemoPropBackendString name;
  uint32_t mode;
  unsigned char has_color, padding1[3], color[16];
} FixDemoPropBackendLoadId;

_Static_assert(sizeof(FixDemoPropBackendLoadId) == 56, "native DemoObjectLoadId size");
_Static_assert(offsetof(FixDemoPropBackendLoadId, name) == 8, "native string offset");
_Static_assert(offsetof(FixDemoPropBackendLoadId, mode) == 32, "native mode offset");
_Static_assert(offsetof(FixDemoPropBackendLoadId, has_color) == 36, "native color flag");
_Static_assert(offsetof(FixDemoPropBackendLoadId, color) == 40, "native color offset");

typedef struct {
  FixDemoPropNativeCreate create;
  /* Native Cobra-allocator string::assign returns the string object itself.
   * New string storage must use BasicMalloc's allocator, paired with basic_free. */
  void *(*assign_string)(void *, const char *, size_t);
  void (*basic_free)(void *);
  void *(*allocate_demo)(size_t);       /* Native operator new. */
  void (*construct_demo)(void *);
  int (*init_demo)(void *, void *);     /* DemoObject::Init(DemoObjectLoadId&). */
  void (*set_display)(void *, int);
  void (*delete_demo)(void *);          /* Native deleting destructor D0, not free(). */
} FixDemoPropBackendOps;

enum FixDemoPropBackendResult {
  FIXDEMO_PROP_BACKEND_NO_ORIGINAL,
  FIXDEMO_PROP_BACKEND_FORWARDED,
  FIXDEMO_PROP_BACKEND_BAD_OWNER,
  FIXDEMO_PROP_BACKEND_ASSIGN_FAILED,
  FIXDEMO_PROP_BACKEND_ALLOCATION_FAILED,
  FIXDEMO_PROP_BACKEND_LOAD_FAILED,
  FIXDEMO_PROP_BACKEND_OWNER_CHANGED,
  FIXDEMO_PROP_BACKEND_ATTACHED_HIDDEN
};

/* Exactly the native 24-byte CobraString ownership rule used by the verified
 * FixDemoObject destructor: low flag bit selects BasicFree(pointer at +16).
 * A moved-from string is zeroed, so no second owner can release its buffer. */
static inline void fixdemo_prop_backend_release_string(
    const FixDemoPropBackendOps *ops, FixDemoPropBackendString *value) {
  if (value->bytes[0] & 1u) {
    void *buffer = NULL;
    memcpy(&buffer, value->bytes + 16, sizeof(buffer));
    ops->basic_free(buffer);
  }
  memset(value, 0, sizeof(*value));
}

static inline int fixdemo_prop_backend_slots_empty(const unsigned char *owner) {
  uintptr_t slots[3];
  memcpy(slots, owner + 184, sizeof(slots));
  return !slots[0] && !slots[1] && !slots[2];
}

/* Probe caller contract: owner is a live, constructed native FixDemoObject,
 * owner_size describes readable/writable storage, colors (if used) has 16
 * readable bytes, and the entire operation owns a non-reentrant serialized
 * game-thread lifetime boundary. The size and epoch checks cannot supply it.
 * Every callback must be bound to the verified target's native ABI. This
 * candidate is not reachable through the production activation gate.
 */
static inline enum FixDemoPropBackendResult fixdemo_prop_backend_candidate(
    const FixDemoPropBackendOps *ops, enum FixDemoPropPreflight preflight,
    int serialized_game_thread, void *owner, size_t owner_size, int type,
    const char *path, size_t path_length, void *skeleton, void *colors) {
  if (!ops || !fixdemo_prop_forward_create(ops->create, owner, type, path, skeleton, colors))
    return FIXDEMO_PROP_BACKEND_NO_ORIGINAL;
  const FixDemoPropMapping *mapping = fixdemo_prop_lookup(path, path_length, 0);
  if (preflight != FIXDEMO_PROP_VALIDATED_BUT_INACTIVE || serialized_game_thread != 1 ||
      !mapping || !ops->assign_string || !ops->basic_free || !ops->allocate_demo ||
      !ops->construct_demo || !ops->init_demo || !ops->set_display || !ops->delete_demo)
    return FIXDEMO_PROP_BACKEND_FORWARDED;
  if (sizeof(uintptr_t) != 8 || !owner || ((uintptr_t)owner & 7u) ||
      owner_size < FIXDEMO_PROP_OWNER_MIN_BYTES ||
      (uintptr_t)owner > UINTPTR_MAX - (FIXDEMO_PROP_OWNER_MIN_BYTES - 1u))
    return FIXDEMO_PROP_BACKEND_BAD_OWNER;
  unsigned char *bytes = owner;
  if (!fixdemo_prop_backend_slots_empty(bytes)) return FIXDEMO_PROP_BACKEND_BAD_OWNER;

  FixDemoPropBackendLoadId previous, staged = {0};
  memcpy(&previous, bytes + 240, sizeof(previous));
  memcpy(&staged.object_id, bytes + 232, sizeof(staged.object_id));
  staged.mode = previous.mode < 2u ? previous.mode : 0u;
  staged.has_color = (unsigned char)(type == 1 && colors != NULL);
  if (staged.has_color) memcpy(staged.color, colors, sizeof(staged.color));
  if (ops->assign_string(&staged.name, mapping->ue_name, strlen(mapping->ue_name)) != &staged.name) {
    fixdemo_prop_backend_release_string(ops, &staged.name);
    return FIXDEMO_PROP_BACKEND_ASSIGN_FAILED;
  }
  void *demo = ops->allocate_demo(FIXDEMO_PROP_DEMO_BYTES);
  if (!demo) {
    fixdemo_prop_backend_release_string(ops, &staged.name);
    return FIXDEMO_PROP_BACKEND_ALLOCATION_FAILED;
  }
  ops->construct_demo(demo);
  const int initialized = ops->init_demo(demo, &staged);
  ops->set_display(demo, 0);
  uintptr_t model = 0;
  uint32_t key = FIXDEMO_PROP_INVALID_LOAD_KEY;
  memcpy(&model, (const unsigned char *)demo + 8, sizeof(model));
  memcpy(&key, (const unsigned char *)demo + 16, sizeof(key));
  enum FixDemoPropBackendResult result = FIXDEMO_PROP_BACKEND_LOAD_FAILED;
  if (initialized == 1 && model && !(model & 7u) && key < FIXDEMO_PROP_INVALID_LOAD_KEY) {
    uint16_t current_id;
    memcpy(&current_id, bytes + 232, sizeof(current_id));
    if (fixdemo_prop_backend_slots_empty(bytes) && current_id == staged.object_id &&
        !memcmp(bytes + 240, &previous, sizeof(previous))) {
      /* Move only after complete staging. Keep the previous native string's
       * owner in the local copy until the new owner fields are consistent. */
      memcpy(bytes + 240, &staged, sizeof(staged));
      memset(&staged.name, 0, sizeof(staged.name));
      memcpy(bytes + 184, &demo, sizeof(demo));
      fixdemo_prop_backend_release_string(ops, &previous.name);
      /* Native DrawModel still consumes the root/captain animation. The
       * existing virtual teardown now owns demo and the moved native string. */
      return FIXDEMO_PROP_BACKEND_ATTACHED_HIDDEN;
    }
    result = FIXDEMO_PROP_BACKEND_OWNER_CHANGED;
  }
  ops->delete_demo(demo);
  fixdemo_prop_backend_release_string(ops, &staged.name);
  return result;
}

#endif /* isolated backend probe only */
#endif

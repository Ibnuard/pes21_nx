#include <stdint.h>
#include <string.h>

#include "error.h"
#include "so_util.h"
#include "ue4_hooks.h"
#include "util.h"

#define OBJECT_INITIALIZER_STATE_SLOTS 32
#define OBJECT_INITIALIZER_MAX_ITEMS (1 << 20)

typedef struct {
  void *data;
  int32_t num;
  int32_t max;
} Ue4Array;

typedef struct {
  Ue4Array *array;
  void *data;
  int32_t max;
  uint32_t growths;
} ObjectInitializerArrayState;

static ObjectInitializerArrayState object_initializer_states[
    OBJECT_INITIALIZER_STATE_SLOTS];
static void *(*ue4_fmemory_malloc)(uint64_t size, uint32_t alignment);

static void patch_arm64_branch(uintptr_t source, uintptr_t destination) {
  const intptr_t delta = (intptr_t)destination - (intptr_t)source;
  if ((delta & 3) != 0 || delta < -(1LL << 27) || delta >= (1LL << 27))
    fatal_error("UE4 branch hook is out of range: %p -> %p", (void *)source,
                (void *)destination);
  *(uint32_t *)source =
      0x14000000u | ((uint32_t)(delta >> 2) & 0x03ffffffu);
}

static ObjectInitializerArrayState *find_array_state(Ue4Array *array) {
  ObjectInitializerArrayState *empty = NULL;
  for (int i = 0; i < OBJECT_INITIALIZER_STATE_SLOTS; i++) {
    ObjectInitializerArrayState *state = &object_initializer_states[i];
    Ue4Array *key = __atomic_load_n(&state->array, __ATOMIC_ACQUIRE);
    if (key == array)
      return state;
    if (!key && !empty)
      empty = state;
  }

  if (empty) {
    Ue4Array *expected = NULL;
    if (__atomic_compare_exchange_n(&empty->array, &expected, array, 0,
                                    __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE))
      return empty;
    if (expected == array)
      return empty;
  }
  return NULL;
}

static int fields_are_sane(const Ue4Array *array, int32_t old_num) {
  return old_num >= 0 && old_num < OBJECT_INITIALIZER_MAX_ITEMS &&
         array->num == old_num + 1 && array->max >= 0 &&
         array->max < OBJECT_INITIALIZER_MAX_ITEMS;
}

// Returns the old element index so the assembly shim can repair callers that
// keep it in x19 across ResizeGrow.
int32_t ue4_object_initializer_resize_hook_c(Ue4Array *array,
                                             int32_t old_num) {
  ObjectInitializerArrayState *state = find_array_state(array);
  const void *incoming_data = array->data;
  const int32_t incoming_num = array->num;
  const int32_t incoming_max = array->max;
  const int sane = fields_are_sane(array, old_num);

  int32_t safe_old_num = old_num;
  if (!sane) {
    // The observed crash had both Num and the high half of Data overwritten.
    // Resetting the transient initializer stack is safer than honoring an
    // index that would request hundreds of MiB and write far out of bounds.
    safe_old_num = 0;
    array->num = 1;
    debugPrintf("UE4 ResizeGrow: CORRUPT array=%p data=%p num=%d max=%d "
                "old=%d; reset old=0\n",
                array, incoming_data, incoming_num, incoming_max, old_num);
  }

  void *old_data = NULL;
  int32_t old_capacity = 0;
  if (state && state->data) {
    old_data = state->data;
    old_capacity = state->max;
    if (incoming_data != state->data)
      debugPrintf("UE4 ResizeGrow: repaired Data %p -> %p for array=%p\n",
                  incoming_data, state->data, array);
  } else if (sane && incoming_data &&
             (uintptr_t)incoming_data >= 0x100000000ULL) {
    old_data = (void *)incoming_data;
    old_capacity = incoming_max;
  }

  int32_t required = array->num;
  int32_t new_max = old_capacity > 0
                        ? old_capacity + old_capacity / 2 + 16
                        : 4;
  if (new_max < required)
    new_max = required;
  if (new_max > OBJECT_INITIALIZER_MAX_ITEMS)
    fatal_error("UE4 object-initializer array exceeded safe capacity: %d",
                new_max);

  void *new_data = ue4_fmemory_malloc((uint64_t)new_max * sizeof(void *), 0);
  if (!new_data)
    fatal_error("UE4 object-initializer allocation failed: %d items", new_max);
  memset(new_data, 0, (size_t)new_max * sizeof(void *));

  int32_t copy_count = safe_old_num;
  if (copy_count > old_capacity)
    copy_count = old_capacity;
  if (old_data && copy_count > 0)
    memcpy(new_data, old_data, (size_t)copy_count * sizeof(void *));

  array->data = new_data;
  array->max = new_max;
  if (state) {
    state->data = new_data;
    state->max = new_max;
    state->growths++;
  }

  debugPrintf("UE4 ResizeGrow: array=%p old=%d num=%d max=%d -> data=%p "
              "max=%d growth=%u\n",
              array, safe_old_num, array->num, incoming_max, new_data, new_max,
              state ? state->growths : 0);
  return safe_old_num;
}

extern void ue4_object_initializer_resize_hook(void);

void install_ue4_hooks(so_module *module) {
  const char *resize_symbol =
      "_ZN6TArrayIP18FObjectInitializer17FDefaultAllocatorE10ResizeGrowEi";
  const char *malloc_symbol = "_ZN7FMemory6MallocEyj";
  const uintptr_t resize_backing = so_find_addr(module, resize_symbol);
  const uintptr_t resize_runtime = so_find_addr_rx(module, resize_symbol);

  ue4_fmemory_malloc = (void *)so_find_addr_rx(module, malloc_symbol);
  hook_arm64(resize_backing,
             (uintptr_t)&ue4_object_initializer_resize_hook);
  debugPrintf("UE4 hook: ResizeGrow backing=%p runtime=%p wrapper=%p "
              "FMemory::Malloc=%p\n",
              (void *)resize_backing, (void *)resize_runtime,
              ue4_object_initializer_resize_hook, ue4_fmemory_malloc);

  // OpenSL ES is unavailable on Horizon. Route CRI's Android backend to its
  // built-in pseudo voice backend so audio is silent instead of dereferencing
  // the intentionally unsupported slCreateEngine result.
  const uintptr_t sles_register =
      so_find_addr(module, "criNcvAndroidSLES_RegisterInterface");
  const uintptr_t pseudo_register =
      so_find_addr(module, "criNcvPseudo_RegisterInterface");
  patch_arm64_branch(sles_register, pseudo_register);
  debugPrintf("UE4 hook: CRI Android SLES -> pseudo voice (%p -> %p)\n",
              (void *)sles_register, (void *)pseudo_register);
}

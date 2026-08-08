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

static _Alignas(8) uint64_t cobra_pad_input;
static _Alignas(4) uint32_t cobra_pad_connected;
static uintptr_t cobra_pad_update_resume;
static uintptr_t mobile_screen_tap_entry_resume;
static uint32_t (*mobile_is_mode_offense)(const void *control_mode);
static uint32_t (*mobile_is_mode_defense)(const void *control_mode);
static _Alignas(4) uint32_t mobile_control_mode;
static _Alignas(4) uint32_t mobile_control_generation;
static uint64_t cobra_pad_last_applied = UINT64_MAX;
static unsigned int cobra_pad_apply_log_count;
static unsigned int cursor_pad_log_count;
static unsigned int real_pad_log_count;
static unsigned int mobile_context_log_count;

static int32_t clamp_pad_value(int32_t value) {
  if (value < 0)
    return 0;
  if (value > 0x7fff)
    return 0x7fff;
  return value;
}

void cobra_pad_set_input(uint32_t buttons, int32_t up, int32_t down,
                         int32_t left, int32_t right, int connected) {
  const int16_t x = (int16_t)(clamp_pad_value(right) -
                              clamp_pad_value(left));
  const int16_t y = (int16_t)(clamp_pad_value(down) -
                              clamp_pad_value(up));
  const uint64_t packed = (uint64_t)(buttons & 0x0000ffffu) |
                          ((uint64_t)(uint16_t)x << 32) |
                          ((uint64_t)(uint16_t)y << 48);
  __atomic_store_n(&cobra_pad_input, packed, __ATOMIC_RELEASE);
  __atomic_store_n(&cobra_pad_connected, connected != 0, __ATOMIC_RELEASE);
}

static int cobra_controller_is_connected(void) {
  return __atomic_load_n(&cobra_pad_connected, __ATOMIC_ACQUIRE) != 0;
}

uint32_t pes_mobile_control_context(int *mode) {
  const uint32_t generation =
      __atomic_load_n(&mobile_control_generation, __ATOMIC_ACQUIRE);
  if (mode)
    *mode = (int)__atomic_load_n(&mobile_control_mode, __ATOMIC_ACQUIRE);
  return generation;
}

// Entry hook for ScreenTapManager::Update. ControlModeInfo is the original x2
// argument here, so its methods provide authoritative offense/defense context
// even while every ButtonObject is idle.
uintptr_t pes_mobile_screen_tap_entry(void *control_mode_ptr) {
  int mode = PES_MOBILE_CONTROL_UNKNOWN;
  if (control_mode_ptr && mobile_is_mode_defense &&
      mobile_is_mode_defense(control_mode_ptr))
    mode = PES_MOBILE_CONTROL_DEFENSE;
  else if (control_mode_ptr && mobile_is_mode_offense &&
           mobile_is_mode_offense(control_mode_ptr))
    mode = PES_MOBILE_CONTROL_OFFENSE;
  __atomic_store_n(&mobile_control_mode, (uint32_t)mode, __ATOMIC_RELEASE);
  const uint32_t generation =
      __atomic_add_fetch(&mobile_control_generation, 1, __ATOMIC_RELEASE);
  static int previous_mode = -1;
  if (mode != previous_mode && mobile_context_log_count < 24) {
    mobile_context_log_count++;
    debugPrintf("input: ScreenTapManager entry control=%p mode=%d "
                "generation=%u\n",
                control_mode_ptr, mode, generation);
    previous_mode = mode;
  }
  return mobile_screen_tap_entry_resume;
}

// The Android/mobile match initializer calls SetPadNo(1), which this binary
// deliberately collapses to -1. Command::ExecCommand then skips the complete
// real-pad path for that cursor. When Switch HID is present, attach that primary
// cursor to port 0; preserve the game's original behavior for every other call.
static void pes_cursor_set_pad_no(void *cursor_ptr, uint32_t requested) {
  if (!cursor_ptr)
    return;
  const int connected = cobra_controller_is_connected();
  const int32_t pad_no = connected && requested == 1 ? 0
                                                     : (requested ? -1 : 0);
  memcpy((unsigned char *)cursor_ptr + 16, &pad_no, sizeof(pad_no));
  if (cursor_pad_log_count < 16) {
    cursor_pad_log_count++;
    debugPrintf("input: CursorData::SetPadNo cursor=%p requested=%u "
                "connected=%d stored=%d\n",
                cursor_ptr, requested, connected, pad_no);
  }
}

// Mobile setup also disables all real-pad slots. Keep port 0 enabled only while
// Ryujinx/libnx reports a controller, leaving the other seven ports and the
// no-controller touch-only behavior unchanged.
static void pes_set_real_pad_is_enable(void *pad_input_ptr, uint32_t pad_no,
                                       uint32_t requested_enable) {
  if (!pad_input_ptr || pad_no > 7)
    return;
  const int connected = cobra_controller_is_connected();
  const uint8_t enabled =
      (requested_enable != 0 || (connected && pad_no == 0)) ? 1 : 0;
  *((unsigned char *)pad_input_ptr + 0x86ca0 + pad_no) = enabled;
  if ((pad_no == 0 || requested_enable) && real_pad_log_count < 24) {
    real_pad_log_count++;
    debugPrintf("input: PadInput::SetRealPadIsEnable object=%p pad=%u "
                "requested=%u connected=%d stored=%u\n",
                pad_input_ptr, pad_no, requested_enable != 0, connected,
                enabled);
  }
}

// Called on cobra's game thread at the end of Pad::Update's clear/touch phase,
// immediately before the game computes clicked/released/repeated edges.
uintptr_t cobra_pad_apply_input(void *pad_ptr) {
  unsigned char *pad = pad_ptr;
  if (pad) {
    const uint64_t packed =
        __atomic_load_n(&cobra_pad_input, __ATOMIC_ACQUIRE);
    const uint32_t buttons = (uint32_t)packed;
    const int32_t x = (int16_t)(packed >> 32);
    const int32_t y = (int16_t)(packed >> 48);
    int32_t pad_id;
    uint32_t previous;
    uint32_t current;
    memcpy(&pad_id, pad + 4, sizeof(pad_id));
    memcpy(&previous, pad + 12, sizeof(previous));
    memcpy(&current, pad + 16, sizeof(current));
    const uint32_t current_before = current;
    current |= buttons;
    memcpy(pad + 16, &current, sizeof(current));
    for (int index = 0; index < 16; index++) {
      const int32_t value = buttons & (1u << index) ? 0x7fff : 0;
      memcpy(pad + 140 + index * 4, &value, sizeof(value));
    }
    const int32_t directions[4] = {
        y < 0 ? -y : 0,
        y > 0 ? y : 0,
        x < 0 ? -x : 0,
        x > 0 ? x : 0,
    };
    memcpy(pad + 140 + 16 * 4, directions, sizeof(directions));
    if (packed != cobra_pad_last_applied && cobra_pad_apply_log_count < 64) {
      cobra_pad_apply_log_count++;
      debugPrintf("input: cobra apply pad=%p id=%d packed=0x%llx "
                  "buttons=0x%x previous=0x%x current=0x%x->0x%x "
                  "axis=%d,%d raw=%d,%d,%d,%d resume=%p\n",
                  pad_ptr, pad_id, (unsigned long long)packed, buttons,
                  previous, current_before, current, x, y, directions[0],
                  directions[1], directions[2], directions[3],
                  (void *)cobra_pad_update_resume);
      cobra_pad_last_applied = packed;
    }
  }
  return cobra_pad_update_resume;
}

extern void cobra_pad_update_hook(void);
extern void pes_mobile_screen_tap_entry_hook(void);

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

  // Publish a match/mode heartbeat at ScreenTapManager::Update entry, where the
  // original ControlModeInfo* is still x2. The hook preserves all arguments,
  // calls the authoritative IsModeOffence/Defence methods, then replays the
  // displaced prologue.
  const char *screen_tap_update_symbol =
      "_ZN5match16ScreenTapManager6UpdateEPKNS_8registry8RegistryERKNS_15ControlModeInfoERNS1_13ScreenTapInfoEPNS1_12Screen2dInfoEi";
  const uintptr_t screen_tap_backing =
      so_find_addr(module, screen_tap_update_symbol);
  const uintptr_t screen_tap_runtime =
      so_find_addr_rx(module, screen_tap_update_symbol);
  uint32_t *screen_tap_entry = (uint32_t *)screen_tap_backing;
  static const uint32_t expected_screen_tap_entry[4] = {
      0xd10643ff, // sub sp, sp, #0x190
      0x6d0f3bef, // stp d15, d14, [sp, #0xf0]
      0x6d1033ed, // stp d13, d12, [sp, #0x100]
      0x6d112beb, // stp d11, d10, [sp, #0x110]
  };
  if (memcmp(screen_tap_entry, expected_screen_tap_entry,
             sizeof(expected_screen_tap_entry)) != 0)
    fatal_error("Unexpected ScreenTapManager::Update entry at %p",
                (void *)screen_tap_entry);
  mobile_is_mode_offense =
      (void *)so_find_addr_rx(module,
          "_ZNK5match15ControlModeInfo13IsModeOffenceEv");
  mobile_is_mode_defense =
      (void *)so_find_addr_rx(module,
          "_ZNK5match15ControlModeInfo13IsModeDefenceEv");
  mobile_screen_tap_entry_resume = screen_tap_runtime + 0x10;
  hook_arm64((uintptr_t)screen_tap_entry,
             (uintptr_t)&pes_mobile_screen_tap_entry_hook);
  debugPrintf("UE4 hook: ScreenTapManager entry backing=%p runtime=%p "
              "hook=%p resume=%p offense=%p defense=%p\n",
              (void *)screen_tap_backing, (void *)screen_tap_runtime,
              pes_mobile_screen_tap_entry_hook,
              (void *)mobile_screen_tap_entry_resume,
              mobile_is_mode_offense, mobile_is_mode_defense);

  // PES consumes Android/UE gamepad events before they reach gameplay. Inject
  // Switch input into cobra::game::Pad after its clear/touch phase instead, so
  // the game's own edge/repeat logic and context-sensitive actions remain
  // authoritative while the mobile touch overlay stays enabled.
  const char *pad_update_symbol = "_ZN5cobra4game3Pad6UpdateEv";
  const uintptr_t pad_update_backing =
      so_find_addr(module, pad_update_symbol);
  const uintptr_t pad_update_runtime =
      so_find_addr_rx(module, pad_update_symbol);
  uint32_t *pad_hook = (uint32_t *)(pad_update_backing + 0xd4);
  static const uint32_t expected_pad_words[4] = {
      0x2941a66b, // ldp w11, w9, [x19, #12]
      0xaa1f03e8, // mov x8, xzr
      0x9100826a, // add x10, x19, #0x20
      0x0a2b012c, // bic w12, w9, w11
  };
  if (memcmp(pad_hook, expected_pad_words, sizeof(expected_pad_words)) != 0)
    fatal_error("Unexpected cobra::Pad::Update hook bytes at %p",
                (void *)pad_hook);
  cobra_pad_update_resume = pad_update_runtime + 0xe4;
  hook_arm64((uintptr_t)pad_hook, (uintptr_t)&cobra_pad_update_hook);
  debugPrintf("UE4 hook: cobra Pad::Update backing=%p runtime=%p hook=%p "
              "resume=%p\n",
              (void *)pad_update_backing, (void *)pad_update_runtime,
              cobra_pad_update_hook, (void *)cobra_pad_update_resume);

  // Reconnect the mobile cursor to the real-pad route. These two functions are
  // fully replaced, so no displaced instructions need to be replayed.
  const char *cursor_set_pad_symbol =
      "_ZN5match8registry10CursorData8SetPadNoEj";
  const uintptr_t cursor_set_pad_backing =
      so_find_addr(module, cursor_set_pad_symbol);
  const uintptr_t cursor_set_pad_runtime =
      so_find_addr_rx(module, cursor_set_pad_symbol);
  static const uint32_t expected_cursor_words[4] = {
      0x7100003f, // cmp w1, #0
      0x5a9f03e8, // csetm w8, ne
      0xb9001008, // str w8, [x0, #16]
      0xd65f03c0, // ret
  };
  if (memcmp((void *)cursor_set_pad_backing, expected_cursor_words,
             sizeof(expected_cursor_words)) != 0)
    fatal_error("Unexpected CursorData::SetPadNo hook bytes at %p",
                (void *)cursor_set_pad_backing);
  hook_arm64(cursor_set_pad_backing, (uintptr_t)&pes_cursor_set_pad_no);
  debugPrintf("UE4 hook: CursorData::SetPadNo backing=%p runtime=%p "
              "replacement=%p\n",
              (void *)cursor_set_pad_backing, (void *)cursor_set_pad_runtime,
              pes_cursor_set_pad_no);

  const char *real_pad_enable_symbol =
      "_ZN5match8registry8PadInput18SetRealPadIsEnableEjb";
  const uintptr_t real_pad_enable_backing =
      so_find_addr(module, real_pad_enable_symbol);
  const uintptr_t real_pad_enable_runtime =
      so_find_addr_rx(module, real_pad_enable_symbol);
  static const uint32_t expected_enable_words[4] = {
      0x71001c3f, // cmp w1, #7
      0x540000c8, // b.hi return
      0x528d940a, // mov w10, #0x6ca0
      0x12000048, // and w8, w2, #1
  };
  if (memcmp((void *)real_pad_enable_backing, expected_enable_words,
             sizeof(expected_enable_words)) != 0)
    fatal_error("Unexpected PadInput::SetRealPadIsEnable hook bytes at %p",
                (void *)real_pad_enable_backing);
  hook_arm64(real_pad_enable_backing,
             (uintptr_t)&pes_set_real_pad_is_enable);
  debugPrintf("UE4 hook: PadInput::SetRealPadIsEnable backing=%p runtime=%p "
              "replacement=%p\n",
              (void *)real_pad_enable_backing,
              (void *)real_pad_enable_runtime, pes_set_real_pad_is_enable);

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

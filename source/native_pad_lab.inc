// Single-player native-input experiment. No touch synthesis and no global
// gameplay patches: only tile 2, local home player, cursor bound to pad zero.
static void (*native_lab_list_update_original)(void *, const void *, uint32_t, uint32_t);
static void (*native_lab_sample_original)(void *, uint32_t, const void *, const void *);
static void *(*native_lab_history_get)(void *, int);
static uint32_t native_lab_status;
static uint32_t native_lab_installed;

typedef struct {
  uint32_t kind;
  const char *symbol;
  uintptr_t vptr;
} NativeLabUnit;

// Kinds verified against ThinkUnitList's object table, not guessed from names.
static NativeLabUnit native_lab_units[] = {
  {0, "_ZTVN5match3pad18ThinkUnitShortPassE", 0},
  {1, "_ZTVN5match3pad17ThinkUnitLongPassE", 0},
  {2, "_ZTVN5match3pad20ThinkUnitThroughPassE", 0},
  {3, "_ZTVN5match3pad14ThinkUnitShootE", 0},
  {5, "_ZTVN5match3pad14ThinkUnitPressE", 0},
  {6, "_ZTVN5match3pad15ThinkUnitTackleE", 0},
  {7, "_ZTVN5match3pad16ThinkUnitSlidingE", 0},
  {9, "_ZTVN5match3pad20ThinkUnitFriendPressE", 0},
  {10, "_ZTVN5match3pad16ThinkUnitDribbleE", 0},
  {11, "_ZTVN5match3pad17ThinkUnitFreeMoveE", 0},
  {12, "_ZTVN5match3pad21ThinkUnitCursorChangeE", 0},
  {24, "_ZTVN5match3pad20ThinkUnitSuperCancelE", 0},
  {78, "_ZTVN5match3pad20ThinkUnitMobileShootE", 0},
  {79, "_ZTVN5match3pad19ThinkUnitMobilePassE", 0},
  {80, "_ZTVN5match3pad22ThinkUnitMobilePassSubE", 0},
  {81, "_ZTVN5match3pad26ThinkUnitMobileSuperCancelE", 0},
  {82, "_ZTVN5match3pad31ThinkUnitMobileAutoOneTwoReturnE", 0},
  {83, "_ZTVN5match3pad22ThinkUnitMobileDribbleE", 0},
  {84, "_ZTVN5match3pad27ThinkUnitMobileCursorChangeE", 0},
  {85, "_ZTVN5match3pad20ThinkUnitMobilePressE", 0},
  {86, "_ZTVN5match3pad23ThinkUnitMobilePressSubE", 0},
  {87, "_ZTVN5match3pad23ThinkUnitMobilePressSubE", 0},
  {88, "_ZTVN5match3pad22ThinkUnitMobileSlidingE", 0},
  {89, "_ZTVN5match3pad23ThinkUnitMobileFreeMoveE", 0},
};

static void native_pad_lab_reset(void) {
  __atomic_store_n(&native_lab_status, 0, __ATOMIC_RELEASE);
}

uint32_t pes_controller_native_pad_lab_status(void) {
  if (!pes_controller_native_pad_lab_active())
    return 0;
  // Latch milestones for one lab session; no per-frame file I/O/log spam.
  if (__atomic_load_n(&cobra_pad_connected, __ATOMIC_ACQUIRE) &&
      __atomic_load_n(&cobra_pad_input, __ATOMIC_ACQUIRE))
    __atomic_fetch_or(&native_lab_status, 1u, __ATOMIC_RELAXED);
  return __atomic_load_n(&native_lab_status, __ATOMIC_ACQUIRE) |
         (native_lab_installed ? 16u : 128u);
}

static void native_lab_sample(void *unit, uint32_t pad_no,
                              const void *config_ptr, const void *match_info) {
  native_lab_sample_original(unit, pad_no, config_ptr, match_info);
  if (!pes_controller_native_pad_lab_active() || pad_no != 0 || !unit)
    return;
  const void *history = native_lab_history_get(unit, 0);
  if (history) {
    uint32_t keys;
    float power;
    memcpy(&keys, history, sizeof(keys));
    memcpy(&power, (const char *)history + 8, sizeof(power));
    if ((keys & 0x003fffffu) || power > 0.01f)
      __atomic_fetch_or(&native_lab_status, 2u, __ATOMIC_RELAXED);
  }
}

static int native_lab_local_input(const void *input) {
  if (!input || !pes_controller_native_pad_lab_active())
    return 0;
  const void *cursor = *(void *const *)((const char *)input + 0x18);
  const void *accessor = *(void *const *)((const char *)input + 8);
  const uint32_t player = *(const uint32_t *)((const char *)input + 0x24);
  return cursor && accessor && *(void *const *)accessor && player < 11 &&
         *(const int32_t *)((const char *)cursor + 16) == 0;
}

static int native_lab_layout_matches(const void *list) {
  for (unsigned i = 0; i < sizeof(native_lab_units)/sizeof(native_lab_units[0]); i++) {
    const NativeLabUnit *expected = &native_lab_units[i];
    const void *unit = *(void *const *)((const char *)list +
                                      0x3bf8 + expected->kind * 8);
    if (!unit || !expected->vptr || *(const uintptr_t *)unit != expected->vptr)
      return 0;
  }
  return 1;
}

static int native_lab_append(uint32_t *entries, uint32_t *count, uint32_t kind) {
  // The original list has 97 entry slots. Preserve ordering and avoid executing
  // a native action twice if another context already selected it.
  if (kind >= 97 || *count >= 97)
    return 0;
  for (uint32_t i = 0; i < *count; i++)
    if (entries[i] == kind)
      return 1;
  entries[(*count)++] = kind;
  return 1;
}

static void native_lab_list_update(void *list, const void *input,
                                   uint32_t previous, uint32_t context) {
  native_lab_list_update_original(list, input, previous, context);
  if (!list || !native_lab_local_input(input))
    return;
  __atomic_fetch_or(&native_lab_status, 4u, __ATOMIC_RELAXED);
  if (!native_lab_layout_matches(list)) {
    __atomic_fetch_or(&native_lab_status, 128u, __ATOMIC_RELAXED);
    return; // Keep the stock list intact if the ABI doesn't match.
  }
  uint32_t *stock = list;
  if (stock[0] > 97) {
    __atomic_fetch_or(&native_lab_status, 128u, __ATOMIC_RELAXED);
    return;
  }
  uint32_t entries[97], count = 0, changed = 0;
  for (uint32_t i = 0; i < stock[0]; i++) {
    uint32_t kind = stock[1+i];
    if (kind >= 78 && kind <= 89) {
      changed++;
      switch (kind) {
        case 78: kind = 3; break;   // Shoot (Y).
        case 79:                   // Pass family: B, A, X.
          if (!native_lab_append(entries, &count, 0) ||
              !native_lab_append(entries, &count, 1))
            return;
          kind = 2;
          break;
        case 80: case 82: continue; // Mobile sub-action/automatic touch return.
        case 81: kind = 24; break;
        case 83: kind = 10; break;  // Dribble reads the real stick history.
        case 84: kind = 12; break;  // Cursor change (L).
        case 85: kind = 5; break;   // Pressure (B).
        case 86: kind = 6; break;   // Tackle (native B timing).
        case 87: kind = 9; break;   // Friend press (Y).
        case 88: kind = 7; break;   // Slide (A).
        case 89: kind = 11; break;  // Free movement.
      }
    }
    if (!native_lab_append(entries, &count, kind))
      return; // Transactional: no partial rewrite on invalid/oversized data.
  }
  if (changed) {
    memcpy(stock + 1, entries, count * sizeof(entries[0]));
    stock[0] = count;
    __atomic_fetch_or(&native_lab_status, 8u, __ATOMIC_RELAXED);
  }
}

#ifndef NATIVE_PAD_LAB_HOST_TEST
static void install_native_pad_lab(so_module *module) {
  // Patch only the two PLT entries. Calling the unmodified exported functions
  // directly from the wrappers keeps native history and mode gates intact.
  const uintptr_t list_plt = (uintptr_t)module->load_base + 0x38cc850;
  const uintptr_t sample_plt = (uintptr_t)module->load_base + 0x38ea5c0;
  const uint32_t list_words[] = {0x9002e2d0, 0xf9434211, 0x911a0210, 0xd61f0220};
  const uint32_t sample_words[] = {0xb002e250, 0xf9429e11, 0x9114e210, 0xd61f0220};
  if (memcmp((void *)list_plt, list_words, sizeof(list_words)) ||
      memcmp((void *)sample_plt, sample_words, sizeof(sample_words)))
    return;
  native_lab_list_update_original = (void *)so_try_find_addr_rx(module,
      "_ZN5match3pad13ThinkUnitList6UpdateERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindEj");
  native_lab_sample_original = (void *)so_try_find_addr_rx(module,
      "_ZN5match8registry12PadInputUnit6UpdateEjPKNS0_9KeyConfigEPKNS0_9MatchInfoE");
  native_lab_history_get = (void *)so_try_find_addr_rx(module,
      "_ZNK5match8registry12PadInputUnit3GetEi");
  if (!native_lab_list_update_original || !native_lab_sample_original ||
      !native_lab_history_get)
    return;
  for (unsigned i = 0; i < sizeof(native_lab_units)/sizeof(native_lab_units[0]); i++) {
    uintptr_t vt = so_try_find_addr_rx(module, native_lab_units[i].symbol);
    if (!vt)
      return;
    native_lab_units[i].vptr = vt + 16;
  }
  hook_arm64(list_plt, (uintptr_t)&native_lab_list_update);
  hook_arm64(sample_plt, (uintptr_t)&native_lab_sample);
  native_lab_installed = 1;
}
#endif

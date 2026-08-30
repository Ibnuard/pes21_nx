// Candidate native FriendPress prototype. Only this ThinkUnit sees the injected
// key, only for the local cursor, while Y is held in live mobile defense.
// All native mode/cutscene gates still run. Other controls retain touch input.
static _Alignas(8) uint64_t friend_press_until_ms;
static int (*native_friend_press_main)(void *, const void *, uint32_t);
static void *(*native_pad_input_get)(void *, int);
static uint32_t friend_press_installed;

void pes_controller_friend_press_update(int held, uint64_t now_ms) {
  __atomic_store_n(&friend_press_until_ms, held ? now_ms + 100 : 0,
                   __ATOMIC_RELEASE);
}

static int pes_friend_press_main(void *unit, const void *input, uint32_t kind) {
  const uint64_t until =
      __atomic_load_n(&friend_press_until_ms, __ATOMIC_ACQUIRE);
  if (!until || armTicksToNs(armGetSystemTick()) / 1000000ULL > until ||
      !input || !unit || !mobile_is_mode_defense ||
      !mobile_is_mode_defense((const char *)input + 0x28))
    return native_friend_press_main(unit, input, kind);

  void *cursor = *(void *const *)((const char *)input + 0x18);
  void *accessor = *(void *const *)((const char *)input + 8);
  const uint32_t pad_id = *(const uint32_t *)((const char *)unit + 8);
  if (!cursor || *(const int32_t *)((const char *)cursor + 16) != 0 ||
      !accessor || !*(void **)accessor || pad_id >= 31)
    return native_friend_press_main(unit, input, kind);

  uint32_t *current = native_pad_input_get(*(void **)accessor, 0);
  uint32_t *previous = native_pad_input_get(*(void **)accessor, 1);
  if (!current || !previous || current == previous)
    return native_friend_press_main(unit, input, kind);
  const uint32_t mask = 1u << pad_id;
  const uint32_t old_current = *current, old_previous = *previous;
  // A held key, not a synthetic double-click: double-click asks for a separate
  // multi-player pressure action (native return code 7 rather than 6).
  *current |= mask;
  *previous |= mask;
  const uint8_t old_double = *((uint8_t *)unit + 0x38);
  *((uint8_t *)unit + 0x38) = 0;
  const int result = native_friend_press_main(unit, input, kind);
  *((uint8_t *)unit + 0x38) = old_double;
  *current = old_current;
  *previous = old_previous;
  return result;
}

static void install_friend_press_prototype(so_module *module) {
  const char *symbol = "_ZN5match3pad20ThinkUnitFriendPress4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE";
  const uintptr_t original = so_try_find_addr_rx(module, symbol);
  const uintptr_t getter = so_try_find_addr_rx(
      module, "_ZNK5match8registry12PadInputUnit3GetEi");
  const uintptr_t backing = original ? so_find_addr(module, symbol) : 0;
  // Verify the binary layout whose cursor/input offsets the adapter uses.
  const uint32_t expected[] = {0xf81e0ff4, 0xa9017bf3, 0xaa0003f3, 0xaa0103f4};
  if (!original || !getter || !backing ||
      memcmp((const void *)backing, expected, sizeof(expected)) != 0)
    return;
  uintptr_t *slot = find_vtable_method_slot(module,
      "_ZTVN5match3pad20ThinkUnitFriendPressE", original, 21);
  if (!slot)
    return;
  native_friend_press_main = (void *)original;
  native_pad_input_get = (void *)getter;
  *slot = (uintptr_t)&pes_friend_press_main;
  friend_press_installed = 1;
}

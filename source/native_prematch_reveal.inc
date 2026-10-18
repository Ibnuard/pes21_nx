/* The native entrance starts before DemoMatchCard::NeedDisp can report the
 * match card. Reveal that first stadium preview, retaining the native scene,
 * camera, Start/End FPS handling and user-controlled Skip lifecycle. */
static void (*native_entrance_start_original)(void *);
static int native_prematch_reveal_installed;

static void native_prematch_entrance_start(void *entrance) {
  native_entrance_start_original(entrance);
  if (__atomic_load_n(&kickoff_loading_armed, __ATOMIC_ACQUIRE)) {
    kickoff_loading_reveal();
    scene_runtime_note("native prematch", "entrance started; VS cover released");
  }
}

static void install_native_prematch_reveal(so_module *module) {
  if (native_prematch_reveal_installed) return;
  const char *name = "_ZN15FixDemoEntrance14StartDemoEventEv";
  const char *vtable = "_ZTV15FixDemoEntrance";
  static const uint32_t expected_start[8] = {
    0xa9bf7bf3, 0xaa0003f3, 0x96ea4709, 0x96e7768c,
    0x36000060, 0xa8c17bf3, 0xd65f03c0, 0x96ea4704,
  };
  const uintptr_t runtime = so_try_find_addr_rx(module, name);
  if (!runtime || !so_try_find_addr_rx(module, vtable)) return;
  const uintptr_t backing = so_find_addr(module, name);
  if (!backing || memcmp((const void *)backing, expected_start,
                         sizeof(expected_start))) return;
  uintptr_t *slot = find_vtable_method_slot(module, vtable, runtime, 32u);
  if (!slot) return;
  native_entrance_start_original = (void *)runtime;
  *slot = (uintptr_t)&native_prematch_entrance_start;
  native_prematch_reveal_installed = 1;
}

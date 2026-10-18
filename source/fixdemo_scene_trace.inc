/* Opt-in entrance canary observations. These callbacks never select a scene,
 * allocate native actors, change match state or bypass the native Skip path.
 * Default installations (no marker) do not patch or log anything. */
static void (*fixdemo_trace_select_original)(void *);
static void (*fixdemo_trace_start_original)(void *);
static void (*fixdemo_trace_end_original)(void *);
static uint32_t fixdemo_trace_events;
static int fixdemo_trace_installed;

static void fixdemo_trace_note(const char *event, uint32_t scene) {
  /* Event callbacks only, not a frame callback; bounded even over many games.
   * No native pointer is retained and no proprietary asset is written. */
  if (__atomic_fetch_add(&fixdemo_trace_events, 1u, __ATOMIC_RELAXED) >= 128u)
    return;
  FILE *file = fopen("cinematic-trace.log", "ab");
  if (!file) return;
  if (fseek(file, 0, SEEK_END) == 0 && ftell(file) < 16384)
    fprintf(file, "%s scene=%u\n", event, scene);
  fclose(file);
}

static uint32_t fixdemo_trace_scene(const void *manager) {
  /* SetSceneId's checked ldr x8,[x19,#8]; str w9,[x8]. */
  const uint32_t *scene = NULL;
  if (manager) memcpy(&scene, (const char *)manager + 8, sizeof(scene));
  return scene ? *scene : 0u;
}

static void fixdemo_trace_select(void *manager) {
  fixdemo_trace_select_original(manager);
  fixdemo_trace_note("entrance-selected", fixdemo_trace_scene(manager));
}

static void fixdemo_trace_start(void *manager) {
  const uint32_t scene = fixdemo_trace_scene(manager);
  fixdemo_trace_note("entrance-start-enter", scene);
  fixdemo_trace_start_original(manager);
  fixdemo_trace_note("entrance-start-return", scene);
}

static void fixdemo_trace_end(void *manager) {
  const uint32_t scene = fixdemo_trace_scene(manager);
  fixdemo_trace_note("entrance-end-enter", scene);
  /* This native method restores the pre-entrance PES thread FPS. Never omit
   * it, including after Skip, or the next match can inherit a stale rate. */
  fixdemo_trace_end_original(manager);
  fixdemo_trace_note("entrance-end-return", scene);
}

static void install_fixdemo_scene_trace(so_module *module) {
  if (fixdemo_trace_installed) return;
  FILE *marker = fopen("cinematic-trace.txt", "rb");
  if (!marker) return;
  static const char expected[] = "PESNX_CINEMATIC_TRACE_V1\n";
  char text[sizeof(expected)] = {0};
  const size_t length = fread(text, 1, sizeof(text), marker);
  fclose(marker);
  if (length != sizeof(expected) - 1 ||
      memcmp(text, expected, sizeof(expected) - 1)) return;

  static const char *const names[] = {
    "_ZN15FixDemoEntrance10SetSceneIdEv",
    "_ZN15FixDemoEntrance14StartDemoEventEv",
    "_ZN15FixDemoEntrance12EndDemoEventEv",
  };
  static const uint32_t expected_words[][8] = {
    {0xa9bf7bf3, 0xaa0003f3, 0x96e78401, 0xf9400668,
     0x320083e9, 0xb9000109, 0xa8c17bf3, 0xd65f03c0},
    {0xa9bf7bf3, 0xaa0003f3, 0x96ea4709, 0x96e7768c,
     0x36000060, 0xa8c17bf3, 0xd65f03c0, 0x96ea4704},
    {0xb9410c08, 0x34000108, 0xa9bf7bf3, 0xaa0003f3,
     0x96ea46f4, 0xbd410e60, 0x7e21d800, 0xa8c17bf3},
  };
  const char *vtable = "_ZTV15FixDemoEntrance";
  if (!so_try_find_addr_rx(module, vtable)) return;
  uintptr_t methods[3], *slots[3];
  for (uint32_t i = 0; i < 3u; ++i) {
    methods[i] = so_try_find_addr_rx(module, names[i]);
    if (!methods[i]) return;
    /* Before so_finalize, RX may be inaccessible. Inspect only the writable
     * backing; bind eventual original calls to RX without executing them. */
    const uintptr_t backing = so_find_addr(module, names[i]);
    if (memcmp((const void *)backing, expected_words[i],
               sizeof(expected_words[i]))) return;
    slots[i] = find_vtable_method_slot(module, vtable, methods[i], 32u);
    if (!slots[i]) return;
  }
  /* All signatures and all slots must pass before the first write. */
  fixdemo_trace_select_original = (void *)methods[0];
  fixdemo_trace_start_original = (void *)methods[1];
  fixdemo_trace_end_original = (void *)methods[2];
  *slots[0] = (uintptr_t)&fixdemo_trace_select;
  *slots[1] = (uintptr_t)&fixdemo_trace_start;
  *slots[2] = (uintptr_t)&fixdemo_trace_end;
  fixdemo_trace_installed = 1;
  FILE *log = fopen("cinematic-trace.log", "wb");
  if (log) {
    fputs("PESNX cinematic trace v1; observations only, not scene validation\n", log);
    fclose(log);
  }
}

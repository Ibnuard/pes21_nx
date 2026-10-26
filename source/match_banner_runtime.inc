/* FootballNX27 lower match banner. Keep DemoScoreVersus' complete native
 * setup, scores, crests, goal-scorer logic and animation. Only its live title
 * is replaced after SetupInfo, using the same native text setter and holder
 * as the original. No screen/root pointer is retained after this callback. */
static void (*match_banner_setup_original)(void *);
static void (*match_banner_set_text)(void *, void *, const void *, const void *);

static const char *match_banner_competition_name(void) {
  const char *name = NULL;
  if (ml_frontend_match_active())
    name = ml_frontend_match_competition_name();
  else if (competition_frontend_cup_match_active())
    name = competition_frontend_cup_name();
  else if (competition_frontend_league_match_active())
    name = competition_frontend_league_name();
  /* Team membership can select a licensed TOP scorebar in Exhibition. It
   * does not turn that fixture into a league/cup match. */
  return name && name[0] ? name : "Exhibition";
}

static int match_banner_borrow_string(unsigned char value[24],
                                    const char *text) {
  const size_t length = text ? strnlen(text, 256) : 0;
  if (!length || length >= 256) return 0;
  memset(value, 0, 24);
  if (length <= 22) {
    value[0] = (unsigned char)(length << 1);
    memcpy(value + 1, text, length);
  } else {
    /* Read-only borrowed long string. SetTextByString -> NodeRectText::SetStr
     * copies synchronously. Never invoke a native destructor on this view. */
    const uint64_t capacity = ((uint64_t)length + 1u) | 1u;
    const uint64_t bytes = (uint64_t)length;
    memcpy(value, &capacity, 8);
    memcpy(value + 8, &bytes, 8);
    memcpy(value + 16, &text, sizeof(text));
  }
  return 1;
}

static void match_banner_setup(void *screen) {
  if (match_banner_setup_original) match_banner_setup_original(screen);
  if (!screen || !match_banner_set_text) return;
  void *root = NULL;
  memcpy(&root, (unsigned char *)screen + 0x10, sizeof(root));
  if (!root) return;
  _Alignas(8) unsigned char key[24], title[24];
  if (!match_banner_borrow_string(key, "competitionName") ||
      !match_banner_borrow_string(title, match_banner_competition_name()))
    return;
  match_banner_set_text(screen, (unsigned char *)root + 0x90, key, title);
}

#ifndef PESNX_MATCH_BANNER_HOST_TEST
static void install_match_banner_runtime(so_module *module) {
  const char *setup_symbol = "_ZN7match2D6Screen15DemoScoreVersus9SetupInfoEv";
  const char *setter_symbol =
      "_ZN7match2D6Screen4Base15SetTextByStringEPN10menusystem14NodeRectHolderERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS6_9AllocatorIcEEEESF_";
  const uintptr_t setup = so_try_find_addr_rx(module, setup_symbol);
  const uintptr_t setter = so_try_find_addr_rx(module, setter_symbol);
  if (!setup || !setter) {
    scene_runtime_note("match banner", "title exports absent; native retained");
    return;
  }
  /* RW backing is readable before native RX publication. Call targets remain
   * RX addresses; never dereference them during startup admission. */
  const uintptr_t setup_rw = so_find_addr(module, setup_symbol);
  const uintptr_t setter_rw = so_find_addr(module, setter_symbol);
  /* Measured v5.3.0 functions; refuse a different ABI before touching a slot. */
  const uint32_t setup_words[] = {0xd10243ff, 0xa9065bf7, 0xa90753f5,
                                  0xa9087bf3, 0xf9401c14};
  const uint32_t setter_words[] = {0xf81e0ff4, 0xa9017bf3, 0xb4000281,
                                   0xf9400028, 0x39400049};
  if (!setup_rw || !setter_rw ||
      setup_rw != (uintptr_t)module->load_base + 0x7cbf944 ||
      setter_rw != (uintptr_t)module->load_base + 0x7cb86ec ||
      memcmp((void *)setup_rw, setup_words, sizeof(setup_words)) ||
      memcmp((void *)setter_rw, setter_words, sizeof(setter_words))) {
    scene_runtime_note("match banner", "title ABI absent/incompatible; native retained");
    return;
  }
  uintptr_t *slot = find_vtable_method_slot(module,
      "_ZTVN7match2D6Screen15DemoScoreVersusE", setup, 26);
  if (!slot) {
    scene_runtime_note("match banner", "title lifecycle slot absent; native retained");
    return;
  }
  match_banner_setup_original = (void *)setup;
  match_banner_set_text = (void *)setter;
  *slot = (uintptr_t)&match_banner_setup;
  scene_runtime_note("match banner", "FootballNX27 native animation; fixture competition title");
}
#endif

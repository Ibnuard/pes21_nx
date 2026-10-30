/* Serialized game-owner adapter. Only menu music is muted; the existing
 * mixer retains SFX/commentary. Native queries are bounded independently of
 * the number of Pad::Update callbacks in a frame. */
static int (*playlist_native_acf_registered)(int);
static void (*playlist_native_mute)(const char *, int);
static int (*playlist_native_is_muted)(const char *);
static float (*playlist_native_volume)(const char *);
static const char playlist_native_category[] = "OptVol_Menu_Music";
static int playlist_native_owned, playlist_native_previous_mute;
static int playlist_native_failed, playlist_native_starved;
static uint32_t playlist_native_revision, playlist_native_attempts;
static uint32_t playlist_native_input_notices;
static uint64_t playlist_native_next_check, playlist_native_empty_since;
static float playlist_native_gain;

static int custom_playlist_native_available(void) {
  return playlist_native_acf_registered && playlist_native_mute &&
      playlist_native_is_muted && playlist_native_volume;
}

static void custom_playlist_native_release(void) {
  custom_playlist_set_audible(0, 0.f);
  if (playlist_native_owned && custom_playlist_native_available() &&
      playlist_native_acf_registered(0))
    playlist_native_mute(playlist_native_category, playlist_native_previous_mute);
  playlist_native_owned = 0;
  playlist_native_starved = 0;
}

static void custom_playlist_native_fail(const char *reason) {
  custom_playlist_native_release();
  playlist_native_failed = 1;
  /* One fault record per enabled session, never per frame/audio callback. */
  scene_runtime_note("custom playlist fallback", reason);
}

static void custom_playlist_native_tick(int menu_active, uint64_t now) {
  custom_playlist_publish(menu_active, now);
  const uint32_t revision = custom_playlist_revision();
  if (revision != playlist_native_revision) {
    custom_playlist_native_release();
    playlist_native_revision = revision;
    playlist_native_failed = 0;
    playlist_native_attempts = 0;
    playlist_native_input_notices = 0;
    playlist_native_next_check = 0;
  }
  if (!custom_playlist_enabled() || !menu_active) {
    custom_playlist_native_release();
    playlist_native_attempts = 0;
    playlist_native_next_check = 0;
    return;
  }
  if (playlist_native_failed) return; /* OFF -> ON starts a fresh attempt. */
  const uint32_t input_notices = custom_playlist_input_warnings();
  const uint32_t new_notices = input_notices & ~playlist_native_input_notices;
  if (new_notices & CUSTOM_PLAYLIST_INPUT_FORMAT)
    scene_runtime_note("custom playlist input",
        "skipped non-MP3 content; convert AAC/MP4 to MP3 instead of renaming the extension");
  if (new_notices & CUSTOM_PLAYLIST_INPUT_DECODE)
    scene_runtime_note("custom playlist input",
        "skipped failed decoder stream; no repeat attempt until OFF/ON");
  playlist_native_input_notices |= input_notices;
  if (!custom_playlist_ready()) {
    custom_playlist_set_audible(0, 0.f);
    if (playlist_native_owned) {
      /* Brief decoder starvation must not restart native BGM over and over.
       * The output gate stays closed until the normal prefill is ready. */
      if (!playlist_native_starved) {
        playlist_native_starved = 1;
        playlist_native_empty_since = now;
      } else if (now >= playlist_native_empty_since &&
                 now - playlist_native_empty_since >= 750u) {
        custom_playlist_native_fail("PCM unavailable for 750 ms; native music restored until OFF/ON");
      }
    }
    return;
  }
  playlist_native_starved = 0;
  if (now < playlist_native_next_check) {
    if (playlist_native_owned)
      custom_playlist_set_audible(1, playlist_native_gain);
    return;
  }
  playlist_native_next_check = now + 500u;
  /* MusicManager::Init does not imply that the CRI category table exists.
   * notify=0 is a safe probe even before ACF registration. */
  if (!custom_playlist_native_available() || !playlist_native_acf_registered(0)) {
    custom_playlist_set_audible(0, 0.f);
    playlist_native_owned = 0;
    return;
  }
  if (playlist_native_owned && !playlist_native_is_muted(playlist_native_category))
    playlist_native_owned = 0; /* Native playback control took ownership. */
  if (!playlist_native_owned) {
    if (playlist_native_attempts >= 3u) {
      custom_playlist_native_fail("native music ownership changed repeatedly; stopped retrying until OFF/ON");
      return;
    }
    playlist_native_previous_mute = playlist_native_is_muted(playlist_native_category);
    /* On this native build Mute changes the volume returned by GetVolume to
     * ~-96 dB. Capture the gain BEFORE muting; never feed that muted value
     * back into custom PCM. SetVolume while muted updates the restore cache. */
    float gain = playlist_native_previous_mute ? 0.f :
        playlist_native_volume(playlist_native_category) *
        playlist_native_volume("DefVol_Menu_Music");
    if (!isfinite(gain) || gain < 0.f) gain = 0.f;
    if (gain > 1.f) gain = 1.f;
    playlist_native_gain = gain;
    ++playlist_native_attempts;
    playlist_native_mute(playlist_native_category, 1);
    if (!playlist_native_is_muted(playlist_native_category)) {
      custom_playlist_native_fail("native menu music mute not acknowledged; stopped retrying until OFF/ON");
      return;
    }
    playlist_native_owned = 1;
  }
  custom_playlist_set_audible(1, playlist_native_gain);
}

static void custom_playlist_native_install(so_module *module) {
  /* Bind only the locally audited bodies. IsAcfRegistered's notify argument
   * is an internal native ABI, not an assumed SDK signature. */
  static const struct {
    const char *name;
    uint32_t rva, bytes;
    uint64_t fnv;
  } checks[] = {
    {"criAtomEx_IsAcfRegistered", 0x750f854, 0x44, UINT64_C(0x077e2ca84ca368ef)},
    {"criAtomExCategory_MuteByName", 0x750cbfc, 0x50, UINT64_C(0x08af5c32184f8165)},
    {"criAtomExCategory_IsMutedByName", 0x750cc4c, 0x98, UINT64_C(0xc3163b9e72ec8220)},
    {"criAtomExCategory_GetVolumeByName", 0x750c4a4, 0xac, UINT64_C(0xc7c7a9da2ced689d)},
  };
  if (!module) return;
  uintptr_t methods[4] = {0};
  for (uint32_t i = 0; i < 4u; ++i) {
    methods[i] = so_try_find_addr_rx(module, checks[i].name);
    if (!methods[i]) return;
    const uintptr_t backing = so_find_addr(module, checks[i].name);
    if (backing != (uintptr_t)module->load_base + checks[i].rva ||
        trophy_audio_hash((const void *)backing, checks[i].bytes) != checks[i].fnv)
      return;
  }
  playlist_native_acf_registered = (void *)methods[0];
  playlist_native_mute = (void *)methods[1];
  playlist_native_is_muted = (void *)methods[2];
  playlist_native_volume = (void *)methods[3];
}

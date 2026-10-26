/* Include after fixdemo_trophy_result.inc. Native mixer, no second device or
 * playlist/global-volume writes. All native calls run on the ceremony owner.
 * The optional bounded memory bank remains cached until process exit so a native
 * asynchronous fade can never read a freed allocation. */
static int32_t (*fixdemo_audio_mount)(void *, uint32_t, void *, const char *, int16_t *);
static int32_t (*fixdemo_audio_play)(const char *, uint64_t *, int32_t, int32_t);
static int32_t (*fixdemo_audio_stop)(uint64_t, int32_t, int32_t);
static int32_t (*fixdemo_audio_existing)(const char *);
static int32_t (*fixdemo_audio_status)(uint64_t, uint32_t *);
static int32_t (*fixdemo_audio_position)(uint64_t, int64_t *);
static float (*fixdemo_audio_category_volume)(const char *);
/* Original native WaveVoicePoolConfig: identifier, voices, then the five
 * WavePlayerConfig words (channels/rate/streaming/renderer/decode latency).
 * Native CreateWavePlayerPool registers format mask0x20. The existing
 * StandardPlayerPool attaches only ADX/HCA and cannot admit WAVE itself. */
typedef struct FixdemoWavePoolConfig {
  uint32_t identifier, voices, channels, rate, streaming, renderer, latency;
} FixdemoWavePoolConfig;
_Static_assert(sizeof(FixdemoWavePoolConfig) == 28, "native WAVE pool ABI");
static int32_t (*fixdemo_audio_wave_pool_size)(const FixdemoWavePoolConfig *);
static void *(*fixdemo_audio_wave_pool_allocate)(const FixdemoWavePoolConfig *, void *, int32_t);
static void *fixdemo_audio_wave_pool, *fixdemo_audio_wave_pool_work;
static uint32_t fixdemo_audio_wave_pool_attempted;
static void *fixdemo_audio_bank;
static int16_t fixdemo_audio_mount_id = -1;
static uint32_t fixdemo_audio_attempted_mount;
static uint64_t fixdemo_audio_watch_handle, fixdemo_audio_watch_started_ms;
static uint32_t fixdemo_audio_watch_sample;

static int fixdemo_audio_ensure_wave_pool(void) {
  if (fixdemo_audio_wave_pool) return 1;
  if (fixdemo_audio_wave_pool_attempted || !fixdemo_audio_wave_pool_size ||
      !fixdemo_audio_wave_pool_allocate) return 0;
  fixdemo_audio_wave_pool_attempted = 1u;
  /* identifier0 is the native unspecified cue pool. The native format mask
   * selects this one WAVE voice; ADX/HCA requests cannot select this pool.
   * Renderer2 is the native software/ASR mixer used by ordinary native pools;
   * this creates no second audio device or renderer configuration. */
  static const FixdemoWavePoolConfig config = {0, 1, 2, 44100, 0, 2, 0};
  const int32_t bytes = fixdemo_audio_wave_pool_size(&config);
  if (bytes <= 0 || bytes > 1024 * 1024) {
    char message[112];
    snprintf(message, sizeof(message), "music-wave-pool worksize-rejected=%d optional-music-unavailable", bytes);
    fixdemo_trophy_note(message);
    return 0;
  }
  void *work = calloc(1u, (size_t)bytes);
  if (!work) return 0;
  void *pool = fixdemo_audio_wave_pool_allocate(&config, work, bytes);
  if (!pool) {
    /* With caller-owned work the native wrapper does not free this pointer;
     * incomplete native pools destroy their created players before returning. */
    free(work);
    fixdemo_trophy_note("music-wave-pool allocation-rejected optional-music-unavailable");
    return 0;
  }
  /* Native allocator registers the pool. Keep its caller-owned backing alive
   * for process lifetime, like the mounted bank. Teardown stops the handle;
   * it never frees memory still referenced by a mixer/fade. */
  fixdemo_audio_wave_pool = pool;
  fixdemo_audio_wave_pool_work = work;
  char message[176];
  snprintf(message, sizeof(message),
      "music-wave-pool voices=1 channels=2 rate=44100 streaming=0 identifier=0 work=%d format-mask=20 cached-native-mixer", bytes);
  fixdemo_trophy_note(message);
  return 1;
}

/* CheckRequire returns this exact value when the tagged playback handle is no
 * longer registered. It is not a boolean failure and must not poison the next
 * ceremony. Unknown failures still retain ownership and forbid new playback. */
#define FIXDEMO_AUDIO_RETIRED UINT32_C(0x80000010)

static int fixdemo_audio_read_status(uint64_t handle, uint32_t *flags) {
  *flags = 0;
  return fixdemo_audio_status ? fixdemo_audio_status(handle, flags) : -1;
}

/* Called only by the serialized native ceremony owner. At most six bounded
 * observations per playback; no per-frame mixer queries or log writes. */
static void fixdemo_trophy_audio_observe(uint64_t now_ms) {
  static const uint32_t delays[] = {0, 100, 1000, 4000, 10000, 16000};
  if (!fixdemo_audio_watch_handle || fixdemo_audio_watch_sample >= 6u) return;
  if (!fixdemo_audio_watch_started_ms) fixdemo_audio_watch_started_ms = now_ms;
  const uint64_t elapsed = now_ms - fixdemo_audio_watch_started_ms;
  if (elapsed < delays[fixdemo_audio_watch_sample]) return;
  uint32_t flags = 0;
  int64_t position = -1;
  const int32_t result = fixdemo_audio_read_status(fixdemo_audio_watch_handle, &flags);
  const int32_t position_result = fixdemo_audio_position ?
      fixdemo_audio_position(fixdemo_audio_watch_handle, &position) : -1;
  const float gain = fixdemo_audio_category_volume ?
      fixdemo_audio_category_volume("DefVol_Menu_Music") : -1.0f;
  char message[256];
  snprintf(message, sizeof(message),
      "music-observe elapsed=%llu status=%08x flags=%08x playing=%u position-result=%08x position=%lld menu-music-gain-x10000=%d",
      (unsigned long long)elapsed, (uint32_t)result, flags,
      !result && !!(flags & (1u << 20)), (uint32_t)position_result,
      (long long)position, (int)(gain * 10000.0f));
  fixdemo_trophy_note(message);
  ++fixdemo_audio_watch_sample;
  if ((uint32_t)result == FIXDEMO_AUDIO_RETIRED)
    fixdemo_audio_watch_handle = 0;
}

static void fixdemo_audio_note(void *context, const char *text) {
  (void)context;
  fixdemo_trophy_note(text);
}

static int fixdemo_audio_native_play(void *context, uint64_t *handle) {
  (void)context;
  if (!handle || !fixdemo_audio_play || !fixdemo_audio_mount ||
      !fixdemo_audio_existing) return -1;
  *handle = 0;
  if (!fixdemo_audio_bank) {
    if (fixdemo_audio_attempted_mount) return -1;
    fixdemo_audio_attempted_mount = 1u;
    size_t bytes = 0;
    void *bank = nx_asset_read(TROPHY_AUDIO_ASSET, TROPHY_AUDIO_MAX_BANK_BYTES, &bytes);
    if (!bank || bytes != TROPHY_AUDIO_BYTES ||
        trophy_audio_hash(bank, (uint32_t)bytes) != TROPHY_AUDIO_FNV) {
      free(bank);
      fixdemo_trophy_note("music-bank absent-or-damaged native-ceremony-retained");
      return -1;
    }
    if (TROPHY_AUDIO_ENCODE_TYPE == 20u && !fixdemo_audio_ensure_wave_pool()) {
      free(bank);
      return -1;
    }
    int16_t mount = -1;
    /* The native five-argument overload supplies its audited defaults
     * (group 0xffff / flags 0); do not reserve an existing mount group. */
    const int32_t result = fixdemo_audio_mount(bank, (uint32_t)bytes, NULL, NULL, &mount);
    if (result) {
      /* The native failure branch has no registered ACB and frees its work
       * allocation before returning. Our input allocation remains ours. */
      free(bank);
      fixdemo_trophy_note("music-bank native-mount-rejected");
      return -1;
    }
    fixdemo_audio_bank = bank;
    fixdemo_audio_mount_id = mount;
    __atomic_store_n(&trophy_audio_bank_mounted, 1u, __ATOMIC_RELEASE);
    if (mount < 0) {
      /* Zero means LoadAcbData accepted the allocation. An unexpected ID must
       * never make its now registered source buffer eligible for free/retry. */
      fixdemo_trophy_note("music-bank accepted-unexpected-id cached-without-playback");
      return -1;
    }
    char message[112];
    snprintf(message, sizeof(message), "music-bank mounted=%d bytes=%u exact-user-HCA-v94 gain-db-x100=-1200",
             fixdemo_audio_mount_id, (uint32_t)bytes);
    fixdemo_trophy_note(message);
  }
  if (fixdemo_audio_mount_id < 0 ||
      (TROPHY_AUDIO_ENCODE_TYPE == 20u && !fixdemo_audio_wave_pool)) return -1;
  if (!(fixdemo_audio_existing(TROPHY_AUDIO_CUE) & 1)) {
    fixdemo_trophy_note("music-bank owned-cue-not-found");
    return -1;
  }
  const int32_t result = fixdemo_audio_play(TROPHY_AUDIO_CUE, handle, 0, 0);
  char message[128];
  snprintf(message, sizeof(message), "music-native-play result=%d handle=%llu mount=%d",
           result, (unsigned long long)*handle, fixdemo_audio_mount_id);
  fixdemo_trophy_note(message);
  if (!result && *handle) {
    fixdemo_audio_watch_handle = *handle;
    fixdemo_audio_watch_started_ms = 0;
    fixdemo_audio_watch_sample = 0;
  }
  return result;
}

static int fixdemo_audio_native_stop(void *context, uint64_t handle, uint32_t fade) {
  (void)context;
  const int32_t result = fixdemo_audio_stop ?
      fixdemo_audio_stop(handle, (int32_t)fade, 0) : -1;
  uint32_t flags = 0;
  const int32_t status_result = fixdemo_audio_read_status(handle, &flags);
  char message[192];
  snprintf(message, sizeof(message),
      "music-native-stop result=%08x status=%08x flags=%08x handle=%llu fade=%u",
      (uint32_t)result, (uint32_t)status_result, flags,
      (unsigned long long)handle, fade);
  fixdemo_trophy_note(message);
  if (!result || ((uint32_t)result == FIXDEMO_AUDIO_RETIRED &&
                  (uint32_t)status_result == FIXDEMO_AUDIO_RETIRED)) {
    if (fixdemo_audio_watch_handle == handle) fixdemo_audio_watch_handle = 0;
    if (result) fixdemo_trophy_note("music-stop handle-already-retired native-confirmed");
    return 0;
  }
  return result;
}

static void fixdemo_trophy_audio_install(so_module *module) {
  /* All nine complete native bodies are checked in readable backing; only
   * executable mappings become call targets. This adds no native patch. */
  static const struct {
    const char *name;
    uint32_t rva, bytes;
    uint64_t fnv;
  } checks[] = {
    {"_ZN2KS8CInfBase9MountDataEPvjS1_PKcPs", 0x77e4c90, 0x10, UINT64_C(0x9bdd49ca07a9b0c3)},
    {"_ZN5sound3sys9Interface7PlayBgmEPKcPyii", 0x6d00214, 0xb4, UINT64_C(0x7d6facbb99145319)},
    {"_ZN5sound3sys9Interface4StopEyii", 0x6d003e8, 0x1c, UINT64_C(0xf6ff621af0d3a391)},
    {"_ZN5sound3sys9Interface10IsExistingEPKc", 0x6d004ec, 0x44, UINT64_C(0xaf5dcafef3170be3)},
    {"_ZN5sound3sys9Interface9GetStatusEyPj", 0x6d00480, 0x20, UINT64_C(0x8b2db63ac314e144)},
    {"_ZN2KS8CInfBase15GetPlayPositionEyPx", 0x77e4b48, 0x14, UINT64_C(0xc9d04bf96671de06)},
    {"criAtomExCategory_GetTotalVolumeByName", 0x750c678, 0xa8, UINT64_C(0x851d549d63dfa64d)},
    {"criAtomExVoicePool_CalculateWorkSizeForWaveVoicePool", 0x7dfac14, 0x64, UINT64_C(0x3ccc0a45c9fa1f8f)},
    {"criAtomExVoicePool_AllocateWaveVoicePool", 0x7dfac78, 0x12c, UINT64_C(0x6342883cfaa9d68f)},
  };
  if (!module || !fixdemo_trophy_result_prepared ||
      strcmp(fixdemo_trophy_verified_elf_sha256,
          "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187")) return;
  uintptr_t methods[9] = {0};
  for (uint32_t i = 0; i < 9; ++i) {
    methods[i] = so_try_find_addr_rx(module, checks[i].name);
    if (!methods[i]) {
      fixdemo_trophy_note("music-ABI-symbol-absent native-ceremony-retained");
      return;
    }
    const uintptr_t backing = so_find_addr(module, checks[i].name);
    if (backing != (uintptr_t)module->load_base + checks[i].rva ||
        trophy_audio_hash((const void *)backing, checks[i].bytes) != checks[i].fnv) {
      fixdemo_trophy_note("music-ABI-rejected native-ceremony-retained");
      return;
    }
  }
  fixdemo_audio_mount = (void *)methods[0];
  fixdemo_audio_play = (void *)methods[1];
  fixdemo_audio_stop = (void *)methods[2];
  fixdemo_audio_existing = (void *)methods[3];
  fixdemo_audio_status = (void *)methods[4];
  fixdemo_audio_position = (void *)methods[5];
  fixdemo_audio_category_volume = (void *)methods[6];
  fixdemo_audio_wave_pool_size = (void *)methods[7];
  fixdemo_audio_wave_pool_allocate = (void *)methods[8];
  fixdemo_trophy_audio.ops = (TrophyAudioOps){fixdemo_audio_native_play,
      fixdemo_audio_native_stop, fixdemo_audio_note, NULL};
  fixdemo_trophy_note("music-optional user-HCA-v94 own-cue-gain=-12dB existing-native-pool ABI-bound");
}

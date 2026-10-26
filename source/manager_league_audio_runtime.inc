/* Optional native mixer bridge. Included once by ue4_hooks.c after loader and
 * nx_asset_read declarations. Publication never calls native code. Only the
 * serialized native owner calls pump; mounted source data lives to process exit.
 * This adapter does not change the accepted trophy pool or create a new pool. */
#include "manager_league_audio_policy.h"
#include "manager_league_audio_catalog.h"

static int32_t (*mla_native_mount)(void *, uint32_t, void *, const char *, int16_t *);
static int32_t (*mla_native_play)(const char *, uint64_t *, int32_t, int32_t, uint32_t);
static int32_t (*mla_native_stop)(uint64_t, int32_t, int32_t);
static int32_t (*mla_native_existing)(const char *);
static int32_t (*mla_native_status)(uint64_t, uint32_t *);
static int32_t (*mla_native_position)(uint64_t, int64_t *);
static void *mla_bank;
static int16_t mla_mount_id = -1;
static uint32_t mla_attempted, mla_mounted, mla_ready, mla_snapshot_lock, mla_published;
static ManagerLeagueAudioFrame mla_snapshot;
static ManagerLeagueAudioPolicy mla_policy;
static struct {uint64_t handle,started;uint32_t clip,samples;} mla_watch[3];
static uint64_t mla_owner_now;

static void mla_note(const char *message) {
  static uint32_t count;
  if(count>=192u)return;
  if(!count) {
    remove("manager-audio-runtime.previous.log");
    (void)rename("manager-audio-runtime.log","manager-audio-runtime.previous.log");
  }
  FILE *f=fopen("manager-audio-runtime.log","ab");
  if(f){if(!fseek(f,0,SEEK_END) && ftell(f)<65536)fprintf(f,"%llu %s\n",(unsigned long long)mla_owner_now,message);fclose(f);}
  ++count;
  scene_runtime_note("manager audio",message);
}

static uint64_t mla_hash(const void *data, uint32_t bytes) {
  const uint8_t *p = data;
  uint64_t h = UINT64_C(0xcbf29ce484222325);
  for (uint32_t i = 0; i < bytes; ++i) h = (h ^ p[i]) * UINT64_C(0x100000001b3);
  return h;
}

void manager_league_audio_publish(const ManagerLeagueAudioFrame *frame) {
  /* A contended publication is skipped, never a render/input-thread spin. The
   * owner sees the prior complete snapshot and its finite stale timeout. */
  if (__atomic_exchange_n(&mla_snapshot_lock, 1u, __ATOMIC_ACQUIRE)) return;
  if (frame) mla_snapshot = *frame;
  else memset(&mla_snapshot, 0, sizeof(mla_snapshot));
  mla_published = 1u;
  __atomic_store_n(&mla_snapshot_lock, 0u, __ATOMIC_RELEASE);
}

static uint32_t mla_clip_duration(void *context, uint32_t clip) {
  (void)context;
  return clip < MLA_CLIP_COUNT ? mla_clips[clip].duration : 0u;
}

static int mla_ensure_bank(void) {
  if (mla_bank) return mla_mount_id >= 0;
  if (mla_attempted || !mla_ready) return 0;
  mla_attempted = 1u;
  size_t bytes = 0;
  void *data = nx_asset_read(MLA_ASSET, MLA_BANK_MAX_BYTES, &bytes);
  if (!data || bytes != MLA_BANK_BYTES || mla_hash(data, (uint32_t)bytes) != MLA_BANK_FNV) {
    free(data);
    mla_note("optional bank absent-or-damaged; visual match retained");
    return 0;
  }
  int16_t mount = -1;
  const int32_t result = mla_native_mount(data, (uint32_t)bytes, NULL, NULL, &mount);
  if (result) {
    free(data); /* Native rejected mount has no registered reader of our input. */
    mla_note("optional native mount rejected; visual match retained");
    return 0;
  }
  /* Success registers the native ACB source even if an unexpected ID is
   * returned. Never free/retry that asynchronous source allocation. */
  mla_bank = data;
  mla_mount_id = mount;
  __atomic_store_n(&mla_mounted, 1u, __ATOMIC_RELEASE);
  mla_note(mount >= 0 ?
      "private HCA bank mounted; native mixer; device audibility unverified" :
      "native mount accepted unexpected ID; cached without playback");
  return mount >= 0;
}

static int mla_play(void *context, uint32_t clip, uint64_t *handle) {
  (void)context;
  if (!handle) return -1;
  *handle = 0;
  if (clip >= MLA_CLIP_COUNT || !mla_clips[clip].cue || !mla_ensure_bank() ||
      !(mla_native_existing(mla_clips[clip].cue) & 1)) return -1;
  const int32_t result = mla_native_play(mla_clips[clip].cue, handle, 0, 0, 0);
  if(!result && *handle) {
    const uint32_t slot=clip==MLA_BED ? 0u : clip>=MLA_SPEECH_SHOT ? 1u : 2u;
    mla_watch[slot].handle=*handle;mla_watch[slot].started=mla_owner_now;
    mla_watch[slot].clip=clip;mla_watch[slot].samples=0;
  }
  static uint32_t journal;
  if (journal++ < 16u) {
    char message[160];
    snprintf(message, sizeof(message), "cue=%u request=%08x handle=%llu (queued request; not audibility proof)",
        clip, (uint32_t)result, (unsigned long long)*handle);
    mla_note(message);
  }
  return result;
}

static int mla_stop(void *context, uint64_t handle, uint32_t fade) {
  (void)context;
  const int32_t result = mla_native_stop(handle, (int32_t)fade, 0);
  if (!result) return 0;
  uint32_t flags = 0;
  /* Exact native CheckRequire result: completed/naturally retired handles are
   * normal, not a stop failure. Other errors retain the owned handle. */
  const int32_t status = mla_native_status(handle, &flags);
  if ((uint32_t)result == UINT32_C(0x80000010) &&
      (uint32_t)status == UINT32_C(0x80000010)) return 0;
  char message[144];
  snprintf(message, sizeof(message), "stop-rejected result=%08x status=%08x flags=%08x; owned handles retained",
      (uint32_t)result, (uint32_t)status, flags);
  mla_note(message);
  return result;
}

static void manager_league_audio_native_pump(uint64_t now_ms) {
  if (!mla_ready || __atomic_exchange_n(&mla_snapshot_lock, 1u, __ATOMIC_ACQUIRE)) return;
  ManagerLeagueAudioFrame frame = mla_snapshot;
  const uint32_t published = mla_published;
  __atomic_store_n(&mla_snapshot_lock, 0u, __ATOMIC_RELEASE);
  if (!published) return;
  if (now_ms < frame.monotonic_ms || now_ms - frame.monotonic_ms > 2000u)
    frame.visible_watch = 0; /* Lost/late UI publication cannot leave speech playing. */
  frame.monotonic_ms = now_ms;
  mla_owner_now=now_ms;
  manager_league_audio_step(&mla_policy, &frame);
  /* Observe the actual asynchronous voice, not just queue admission. No
   * retry/pool/gain change is inferred from a retired or failed request. */
  for(uint32_t i=0;i<3;i++) {
    if(!mla_watch[i].handle || mla_watch[i].samples>=2u ||
       now_ms-mla_watch[i].started<(mla_watch[i].samples ? 1000u : 100u))continue;
    uint32_t flags=0;int64_t position=-1;
    const int32_t status=mla_native_status(mla_watch[i].handle,&flags);
    const int32_t read=mla_native_position(mla_watch[i].handle,&position);
    char message[240];snprintf(message,sizeof(message),
        "observe cue=%u elapsed=%llu status=%08x flags=%08x playing=%u position-result=%08x position=%lld route=BUS8",
        mla_watch[i].clip,(unsigned long long)(now_ms-mla_watch[i].started),(uint32_t)status,flags,
        !status && !!(flags&(1u<<20)),(uint32_t)read,(long long)position);
    mla_note(message);mla_watch[i].samples++;
  }
}

static int manager_league_audio_plain_hca_header(const void *first, uint32_t first_bytes,
    const void *second, uint32_t second_bytes) {
  if (!__atomic_load_n(&mla_mounted, __ATOMIC_ACQUIRE) || !first ||
      first_bytes > UINT32_MAX - second_bytes || first_bytes + second_bytes < 96u ||
      (second_bytes && !second)) return 0;
  uint8_t header[96];
  const uint32_t take = first_bytes > 96u ? 96u : first_bytes;
  memcpy(header, first, take);
  if (take < 96u) memcpy(header + take, second, 96u - take);
  if (memcmp(header, "HCA\0", 4)) return 0;
  const uint64_t hash = mla_hash(header, sizeof(header));
  for (uint32_t i = 0; i < MLA_CLIP_COUNT; ++i)
    if (mla_clips[i].duration && hash == mla_clips[i].header_fnv) return 1;
  return 0;
}

static void manager_league_audio_native_install(so_module *module, const char *elf_sha256) {
  static const struct { const char *name; uint32_t rva, bytes; uint64_t fnv; } checks[] = {
    {"_ZN2KS8CInfBase9MountDataEPvjS1_PKcPs", 0x77e4c90, 0x10, UINT64_C(0x9bdd49ca07a9b0c3)},
    {"_ZN5sound3sys9Interface4PlayEPKcPyiij", 0x6cfff3c, 0x88, UINT64_C(0x1754719cc571d7a7)},
    {"_ZN5sound3sys9Interface4StopEyii", 0x6d003e8, 0x1c, UINT64_C(0xf6ff621af0d3a391)},
    {"_ZN5sound3sys9Interface10IsExistingEPKc", 0x6d004ec, 0x44, UINT64_C(0xaf5dcafef3170be3)},
    {"_ZN5sound3sys9Interface9GetStatusEyPj", 0x6d00480, 0x20, UINT64_C(0x8b2db63ac314e144)},
    {"_ZN2KS8CInfBase15GetPlayPositionEyPx", 0x77e4b48, 0x14, UINT64_C(0xc9d04bf96671de06)},
  };
  if (mla_ready || !module || !elf_sha256 || strcmp(elf_sha256,
      "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187")) return;
  uintptr_t methods[6];
  for (uint32_t i = 0; i < 6; ++i) {
    methods[i] = so_try_find_addr_rx(module, checks[i].name);
    const uintptr_t backing = so_find_addr(module, checks[i].name);
    if (!methods[i] || backing != (uintptr_t)module->load_base + checks[i].rva ||
        mla_hash((const void *)backing, checks[i].bytes) != checks[i].fnv) {
      mla_note("optional native ABI rejected; visual match retained");
      return;
    }
  }
  mla_native_mount = (void *)methods[0];
  mla_native_play = (void *)methods[1];
  mla_native_stop = (void *)methods[2];
  mla_native_existing = (void *)methods[3];
  mla_native_status = (void *)methods[4];
  mla_native_position = (void *)methods[5];
  mla_policy.ops = (ManagerLeagueAudioOps){mla_play, mla_stop, mla_clip_duration, NULL};
  mla_ready = 1u;
  mla_note("v95 owner-safe event mixer armed; BUS8 route candidate; no global gain or pool changes");
}

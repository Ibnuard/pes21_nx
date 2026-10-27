/* Owner publishes events; the existing AudioOut callback blends reviewed PCM.
 * No CRI voice pool, second device, native category or playlist mutation.
 * Bank loading/logging runs on the game owner; the callback does bounded math. */
#include "manager_league_audio_policy.h"
#include "manager_league_audio_catalog.h"
#include "manager_league_pcm_mixer.h"

static uint32_t mla_ready, mla_attempted, mla_snapshot_lock, mla_published, mla_pcm_lock;
static uint32_t mla_watch_active, mla_output_stale;
static uint64_t mla_owner_now, mla_publication_ms;
static ManagerLeagueAudioFrame mla_snapshot;
static ManagerLeagueAudioPolicy mla_policy;
static MlaPcmMixer mla_pcm;
static struct {uint64_t handle, started, source_before; uint32_t clip, samples;} mla_watch[3];

static void mla_note(const char *message) {
  static uint32_t count;
  if (count >= 384u) return;
  if (!count) {
    remove("manager-audio-runtime.previous.log");
    (void)rename("manager-audio-runtime.log", "manager-audio-runtime.previous.log");
  }
  FILE *f = fopen("manager-audio-runtime.log", "ab");
  if (f) {
    if (!fseek(f, 0, SEEK_END) && ftell(f) < 65536)
      fprintf(f, "%llu %s\n", (unsigned long long)mla_owner_now, message);
    fclose(f);
  }
  ++count;
  scene_runtime_note("manager audio", message);
}
static uint64_t mla_hash(const void *data, uint32_t bytes) {
  const uint8_t *p = data;
  uint64_t h = UINT64_C(0xcbf29ce484222325);
  for (uint32_t i = 0; i < bytes; ++i) h = (h ^ p[i]) * UINT64_C(0x100000001b3);
  return h;
}
void manager_league_audio_publish(const ManagerLeagueAudioFrame *frame) {
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
  if (mla_pcm.bank) return 1;
  if (mla_attempted || !mla_ready) return 0;
  mla_attempted = 1u;
  size_t bytes = 0;
  void *data = nx_asset_read_production(MLA_ASSET, MLA_BANK_MAX_BYTES, &bytes);
  MlaPcmMixer verified = {0};
  if (!data || bytes != MLA_BANK_BYTES || mla_hash(data, (uint32_t)bytes) != MLA_BANK_FNV ||
      !mla_pcm_bind(&verified, data, (uint32_t)bytes)) {
    free(data);
    mla_note("exact PCM bank absent-or-damaged; native audio retained; no repeated load");
    return 0;
  }
  /* The callback only sees a completely validated, process-lifetime source.
   * Loading and hashing finish before taking this short publication lock. */
  if (__atomic_exchange_n(&mla_pcm_lock, 1u, __ATOMIC_ACQUIRE)) {
    free(data);
    mla_attempted = 0u; /* No source was published; a later owner tick may try. */
    return 0;
  }
  mla_pcm = verified;
  __atomic_store_n(&mla_pcm_lock, 0u, __ATOMIC_RELEASE);
  mla_note("exact v96 PCM source ready; 13 recordings; existing AudioOut blend; zero CRI pools");
  return 1;
}
/* These operations run only while the owner holds mla_pcm_lock. The policy
 * retains its once-only event ordering; handles belong exclusively to PCM. */
static int mla_play(void *context, uint32_t clip, uint64_t *handle) {
  (void)context;
  const int result = mla_pcm_start(&mla_pcm, clip, handle);
  if (!result && *handle) {
    const uint32_t slot = clip == MLA_BED ? 0u : clip >= MLA_SPEECH_SHOT ? 1u : 2u;
    mla_watch[slot].handle = *handle;
    mla_watch[slot].started = mla_owner_now;
    mla_watch[slot].source_before = mla_pcm.source_frames[clip];
    mla_watch[slot].clip = clip;
    mla_watch[slot].samples = 0;
  }
  return result;
}
static int mla_stop(void *context, uint64_t handle, uint32_t fade) {
  (void)context;
  return mla_pcm_stop(&mla_pcm, handle, fade);
}

/* The one existing AudioOut output buffer calls this after native resampling
 * and before submission. Neither side spins: contention skips one short block
 * or one owner tick. No allocation, logging, native request or file I/O here. */
void manager_league_audio_mix_pcm(int16_t *output, uint32_t frames, uint64_t now_ms) {
  if (!__atomic_load_n(&mla_ready, __ATOMIC_ACQUIRE) ||
      __atomic_exchange_n(&mla_pcm_lock, 1u, __ATOMIC_ACQUIRE)) return;
  const uint32_t current = mla_watch_active && now_ms >= mla_publication_ms &&
      now_ms - mla_publication_ms <= 2000u;
  if (mla_watch_active && !current) mla_output_stale = 1u;
  mla_pcm_mix(&mla_pcm, output, frames, current);
  __atomic_store_n(&mla_pcm_lock, 0u, __ATOMIC_RELEASE);
}
static void manager_league_audio_native_pump(uint64_t now_ms) {
  if (!mla_ready || __atomic_exchange_n(&mla_snapshot_lock, 1u, __ATOMIC_ACQUIRE)) return;
  ManagerLeagueAudioFrame frame = mla_snapshot;
  const uint32_t published = mla_published;
  __atomic_store_n(&mla_snapshot_lock, 0u, __ATOMIC_RELEASE);
  if (!published) return;
  if (now_ms < frame.monotonic_ms || now_ms - frame.monotonic_ms > 2000u)
    frame.visible_watch = 0;
  frame.monotonic_ms = now_ms;
  mla_owner_now = now_ms;
  if (frame.visible_watch && !mla_ensure_bank()) return;
  if (__atomic_exchange_n(&mla_pcm_lock, 1u, __ATOMIC_ACQUIRE)) return;
  mla_publication_ms = now_ms;
  mla_watch_active = frame.visible_watch && !frame.paused && !!frame.fixture_token && !!mla_pcm.bank;
  if (mla_output_stale) {
    mla_policy.anchored = 0u; /* Rejoin after callback timeout without stale speech. */
    mla_output_stale = 0u;
  }
  manager_league_audio_step(&mla_policy, &frame);
  /* Read only bounded counters under the lock, then write the journal after
   * unlocking. A request alone is never labelled audible device playback. */
  struct {uint32_t clip; uint64_t elapsed, source, mixed, nonzero; uint32_t peak;} notes[3];
  uint32_t count = 0;
  for (uint32_t i = 0; i < 3; ++i) {
    static const uint32_t short_delays[] = {0u, 20u, 100u};
    static const uint32_t long_delays[] = {0u, 100u, 1000u};
    if (!mla_watch[i].handle || mla_watch[i].samples >= 3u) continue;
    const uint32_t clip = mla_watch[i].clip;
    const uint64_t elapsed = now_ms - mla_watch[i].started;
    const uint32_t *delays = mla_clips[clip].duration < 250u ? short_delays : long_delays;
    if (elapsed < delays[mla_watch[i].samples]) continue;
    notes[count].clip = clip;
    notes[count].elapsed = elapsed;
    notes[count].source = mla_pcm.source_frames[clip] - mla_watch[i].source_before;
    notes[count].mixed = mla_pcm.mixed_frames;
    notes[count].nonzero = mla_pcm.nonzero_samples;
    notes[count].peak = mla_pcm.peak;
    ++count;
    ++mla_watch[i].samples;
  }
  __atomic_store_n(&mla_pcm_lock, 0u, __ATOMIC_RELEASE);
  for (uint32_t i = 0; i < count; ++i) {
    char message[232];
    snprintf(message, sizeof(message),
        "pcm-output cue=%u elapsed=%llu source-frames=%llu blended-frames=%llu nonzero-samples=%llu peak=%u (pre-AudioOut; listening required)",
        notes[i].clip, (unsigned long long)notes[i].elapsed, (unsigned long long)notes[i].source,
        (unsigned long long)notes[i].mixed, (unsigned long long)notes[i].nonzero, notes[i].peak);
    mla_note(message);
  }
}
static int manager_league_audio_plain_hca_header(const void *first, uint32_t first_bytes,
    const void *second, uint32_t second_bytes) {
  (void)first; (void)first_bytes; (void)second; (void)second_bytes;
  return 0; /* Manager introduces no HCA decoder exception. */
}
static void manager_league_audio_native_install(so_module *module, const char *elf_sha256) {
  if (mla_ready || !module || !elf_sha256 || strcmp(elf_sha256,
      "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187")) return;
  mla_policy.ops = (ManagerLeagueAudioOps){mla_play, mla_stop, mla_clip_duration, NULL};
  __atomic_store_n(&mla_ready, 1u, __ATOMIC_RELEASE);
  mla_note("v99 reviewed PCM AudioOut blend armed; zero native voice pools; watch-only smooth music duck");
}

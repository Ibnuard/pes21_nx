/* Optional ceremony-owned native audio. No game audio is linked here. */
#ifndef PESNX_TROPHY_AUDIO_POLICY_H
#define PESNX_TROPHY_AUDIO_POLICY_H
#include <stdint.h>
#include <string.h>
#include "trophy_audio_catalog.h"
#ifndef TROPHY_AUDIO_ENCODE_TYPE
#define TROPHY_AUDIO_ENCODE_TYPE 2u
#endif
#ifndef TROPHY_AUDIO_MAX_BANK_BYTES
#define TROPHY_AUDIO_MAX_BANK_BYTES (2u * 1024u * 1024u)
#endif

typedef struct TrophyAudioOps {
  int (*play)(void *, uint64_t *);
  int (*stop)(void *, uint64_t, uint32_t);
  void (*note)(void *, const char *);
  void *context;
} TrophyAudioOps;

typedef struct TrophyAudioState {
  TrophyAudioOps ops;
  uint64_t attempted_token, playing_token, handle;
  uint32_t failed_stop;
} TrophyAudioState;

/* Decoder threads read only this published flag. The bounded bank allocation
 * remains mounted/cached for process lifetime; no fade reads freed bank bytes.
 * Every active playback handle is still owned/stopped by its ceremony token. */
static uint32_t trophy_audio_bank_mounted;

static inline uint64_t trophy_audio_hash(const void *data, uint32_t size) {
  const unsigned char *bytes = data;
  uint64_t hash = UINT64_C(0xcbf29ce484222325);
  for (uint32_t i = 0; i < size; ++i)
    hash = (hash ^ bytes[i]) * UINT64_C(0x100000001b3);
  return hash;
}

static inline int trophy_audio_plain_hca_header(const void *first,
    int64_t first_size, const void *second, int64_t second_size) {
  if (!__atomic_load_n(&trophy_audio_bank_mounted, __ATOMIC_ACQUIRE) ||
      first_size < 0 || second_size < 0) return 0;
#if TROPHY_AUDIO_ENCODE_TYPE == 2u
  const uint32_t first_bytes = !first ? 0u :
      first_size < TROPHY_AUDIO_HEADER_BYTES ? (uint32_t)first_size : TROPHY_AUDIO_HEADER_BYTES;
  if (first_bytes < TROPHY_AUDIO_HEADER_BYTES &&
      (!second || second_size < (int64_t)(TROPHY_AUDIO_HEADER_BYTES - first_bytes))) return 0;
  unsigned char header[TROPHY_AUDIO_HEADER_BYTES];
  if (first_bytes) memcpy(header, first, first_bytes);
  if (first_bytes < TROPHY_AUDIO_HEADER_BYTES)
    memcpy(header + first_bytes, second, TROPHY_AUDIO_HEADER_BYTES - first_bytes);
  return !memcmp(header, "HCA\0\x02\0\x01\x04", 8) &&
      !memcmp(header + 56, "ciph\0\0", 6) &&
      trophy_audio_hash(header, sizeof(header)) == TROPHY_AUDIO_HEADER_FNV;
#else
  /* The current user-supplied cue uses a native non-HCA codec. It never enters
   * HCA cipher admission; unrelated HCA voices retain their existing policy. */
  (void)first; (void)first_size; (void)second; (void)second_size;
  return 0;
#endif
}

static inline void trophy_audio_note(TrophyAudioState *state, const char *text) {
  if (state->ops.note) state->ops.note(state->ops.context, text);
}

/* Serialized native owner only. UI input merely publishes a Skip token. */
static inline int trophy_audio_stop(TrophyAudioState *state) {
  if (!state || !state->handle) return 1;
  if (state->failed_stop) return 0;
  if (!state->ops.stop || state->ops.stop(state->ops.context, state->handle, 250u)) {
    state->failed_stop = 1u;
    trophy_audio_note(state, "music-stop-failed owned-handle-retained no-new-playback");
    return 0;
  }
  state->handle = state->playing_token = 0;
  trophy_audio_note(state, "music-stop requested-owned-handle fade=250");
  return 1;
}

static inline int trophy_audio_start(TrophyAudioState *state, uint64_t token) {
  if (!state || !token || token == state->attempted_token || !state->ops.play) return 0;
  if (!trophy_audio_stop(state)) return 0;
  state->attempted_token = token;
  uint64_t handle = 0;
  if (state->ops.play(state->ops.context, &handle) || !handle) {
    /* A native failure with a published handle still needs owned cleanup. */
    state->handle = handle;
    if (handle) trophy_audio_stop(state);
    trophy_audio_note(state, "music-unavailable ceremony-continues");
    return 0;
  }
  state->handle = handle;
  state->playing_token = token;
  trophy_audio_note(state, "music-request queued-native-mixer owned-token audible-unverified");
  return 1;
}
#endif

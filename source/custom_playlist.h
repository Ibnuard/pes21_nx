/* User-owned menu music. No recording is embedded or required by the wrapper. */
#ifndef PESNX_CUSTOM_PLAYLIST_H
#define PESNX_CUSTOM_PLAYLIST_H

#include <stdint.h>

/* Startup/shutdown and control calls belong to one serialized game owner.
 * init starts one worker; scanning, opening and MP3 decoding stay on that
 * worker, with a scheduling yield between bounded decoder slices. A missing
 * or empty directory is valid and leaves native BGM available.
 * Top-level .mp3 files play in filename order, with a bounded 128-file list.
 * Returns 1 when the worker was created, otherwise 0 (native BGM fallback). */
int custom_playlist_init(const char *directory, int enabled);
void custom_playlist_shutdown(void);

/* Idempotent while unchanged. OFF -> ON rescans the directory and starts a
 * new generation, discarding PCM from the previous enabled session. */
void custom_playlist_enable(int enabled);
/* Nonblocking adapter snapshots. The revision changes on init and each
 * OFF/ON transition, so a failed native acquisition can wait for a new session.
 * enabled is false when worker creation failed or shutdown has completed. */
uint32_t custom_playlist_revision(void);
int custom_playlist_enabled(void);

enum {
  CUSTOM_PLAYLIST_INPUT_FORMAT = 1u,
  CUSTOM_PLAYLIST_INPUT_DECODE = 2u
};
/* Latched worker notices for this generation; no paths or audio data. A
 * recognised non-MPEG container never reaches the decoder. Failed files are
 * skipped until OFF/ON, while healthy tracks can continue looping. */
uint32_t custom_playlist_input_warnings(void);

/* Publish on the game owner while menus are visible. A false publication
 * immediately closes the custom output gate; decoded music pauses in place.
 * Both supplied timestamps use the same monotonic clock as mix_pcm. */
void custom_playlist_publish(int menu_active, uint64_t monotonic_ms);

/* True only with fresh menu ownership and buffered, current-generation PCM.
 * Before making custom audio audible, the game owner must successfully mute
 * only native menu BGM. On a short underrun, close the custom output gate;
 * the owner may retain its native mute for a bounded refill window (750 ms)
 * before restoring native BGM. OFF/menu exit releases ownership immediately. */
int custom_playlist_ready(void);
void custom_playlist_set_audible(int audible, float gain);

/* Existing final AudioOut stereo signed-16 buffer, 48 kHz. This callback only
 * performs bounded saturating addition under a try-lock: no allocation,
 * storage access, decoder/native calls or waiting. A stale heartbeat or a
 * closed output gate leaves both the native buffer and PCM position intact. */
void custom_playlist_mix_pcm(int16_t *output, uint32_t frames,
                             uint64_t monotonic_ms);

#endif

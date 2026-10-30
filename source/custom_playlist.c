/* User-supplied MP3 -> bounded menu PCM -> the existing AudioOut buffer.
 * The decoder owns all filesystem access. Native BGM ownership stays with
 * the game owner; this module never changes a native sound category. */
#include "custom_playlist.h"

#include <dirent.h>
#include <mpg123.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>

enum {
  CP_RATE = 48000,
  CP_RING_FRAMES = CP_RATE * 2,
  CP_PREFILL_FRAMES = CP_RATE / 5,
  CP_CHUNK_FRAMES = 2048,
  CP_DECODE_SLICE_CHUNKS = 2,
  CP_ATTACK_FRAMES = CP_RATE / 100,
  CP_HEARTBEAT_MS = 1000,
  CP_MAX_TRACKS = 128,
  CP_NAME_BYTES = 256,
  CP_DIRECTORY_BYTES = 512,
  CP_PATH_BYTES = CP_DIRECTORY_BYTES + CP_NAME_BYTES + 1
};

static struct {
  pthread_t thread;
  char directory[CP_DIRECTORY_BYTES];
  uint32_t started, stop, enabled, generation, menu_active, audible;
  uint32_t gain, output_serial;
  uint64_t publication_ms, local_publication_ms;
  /* These three atomics let the owner make a nonblocking readiness check. */
  uint32_t pcm_generation, buffered_frames, pcm_lock, input_warnings;
  /* Ring metadata and samples are accessed only under pcm_lock. */
  uint32_t read_at, write_at, count, mix_serial, attack;
  int16_t ring[CP_RING_FRAMES * 2];
} cp;

static pthread_once_t cp_mpg_once = PTHREAD_ONCE_INIT;
static int cp_mpg_result = MPG123_ERR;

static void cp_mpg_init_once(void) {
  /* libmpg123 is also used by native imports. Never call mpg123_exit here. */
  cp_mpg_result = mpg123_init();
}

static uint64_t cp_now_ms(void) {
  struct timespec now;
  if (clock_gettime(CLOCK_MONOTONIC, &now)) return 0;
  return (uint64_t)now.tv_sec * 1000u + (uint64_t)now.tv_nsec / 1000000u;
}

static void cp_wait(unsigned milliseconds) {
  struct timespec delay = {
    (time_t)(milliseconds / 1000u), (long)(milliseconds % 1000u) * 1000000L
  };
  (void)nanosleep(&delay, NULL);
}

static int cp_try_lock(void) {
  return !__atomic_exchange_n(&cp.pcm_lock, 1u, __ATOMIC_ACQUIRE);
}

static void cp_unlock(void) {
  __atomic_store_n(&cp.pcm_lock, 0u, __ATOMIC_RELEASE);
}

static int cp_current_menu(uint64_t now_ms, uint64_t seen_ms) {
  return __atomic_load_n(&cp.started, __ATOMIC_ACQUIRE) &&
      __atomic_load_n(&cp.enabled, __ATOMIC_ACQUIRE) &&
      __atomic_load_n(&cp.menu_active, __ATOMIC_ACQUIRE) &&
      now_ms >= seen_ms && now_ms - seen_ms <= CP_HEARTBEAT_MS;
}

static int cp_local_menu(void) {
  return cp_current_menu(cp_now_ms(),
      __atomic_load_n(&cp.local_publication_ms, __ATOMIC_ACQUIRE));
}

static int cp_reset_ring(uint32_t generation) {
  if (!cp_try_lock()) return 0;
  cp.read_at = cp.write_at = cp.count = cp.attack = 0;
  cp.mix_serial = 0;
  __atomic_store_n(&cp.buffered_frames, 0u, __ATOMIC_RELEASE);
  __atomic_store_n(&cp.input_warnings, 0u, __ATOMIC_RELEASE);
  __atomic_store_n(&cp.pcm_generation, generation, __ATOMIC_RELEASE);
  cp_unlock();
  return 1;
}

/* Called by the sole decoder worker. A pending decoded chunk remains local
 * on contention/full ring; it is never dropped or decoded a second time. */
static uint32_t cp_push(const int16_t *samples, uint32_t frames,
                        uint32_t generation) {
  if (!cp_try_lock()) return 0;
  if (generation != __atomic_load_n(&cp.generation, __ATOMIC_ACQUIRE) ||
      generation != __atomic_load_n(&cp.pcm_generation, __ATOMIC_ACQUIRE)) {
    cp_unlock();
    return 0;
  }
  if (frames > CP_RING_FRAMES - cp.count) frames = CP_RING_FRAMES - cp.count;
  uint32_t first = CP_RING_FRAMES - cp.write_at;
  if (first > frames) first = frames;
  memcpy(cp.ring + cp.write_at * 2u, samples, first * 2u * sizeof(*samples));
  if (frames > first)
    memcpy(cp.ring, samples + first * 2u,
           (frames - first) * 2u * sizeof(*samples));
  cp.write_at = (cp.write_at + frames) % CP_RING_FRAMES;
  cp.count += frames;
  __atomic_store_n(&cp.buffered_frames, cp.count, __ATOMIC_RELEASE);
  cp_unlock();
  return frames;
}

static int cp_ascii_lower(unsigned char c) {
  return c >= 'A' && c <= 'Z' ? c + 'a' - 'A' : c;
}

static int cp_mp3_name(const char *name) {
  const size_t length = strlen(name);
  return length > 4u && length < CP_NAME_BYTES && name[0] != '.' &&
      name[length - 4u] == '.' &&
      cp_ascii_lower((unsigned char)name[length - 3u]) == 'm' &&
      cp_ascii_lower((unsigned char)name[length - 2u]) == 'p' &&
      name[length - 1u] == '3';
}

static int cp_name_compare(const void *left, const void *right) {
  const unsigned char *a = left, *b = right;
  for (size_t index = 0; a[index] || b[index]; ++index) {
    const int delta = cp_ascii_lower(a[index]) - cp_ascii_lower(b[index]);
    if (delta) return delta;
  }
  return strcmp(left, right);
}

static int cp_path(char path[CP_PATH_BYTES], const char *name) {
  const int length = snprintf(path, CP_PATH_BYTES, "%s/%s", cp.directory, name);
  return length > 0 && (size_t)length < CP_PATH_BYTES;
}

static uint32_t cp_scan(char tracks[CP_MAX_TRACKS][CP_NAME_BYTES]) {
  DIR *directory = opendir(cp.directory);
  if (!directory) return 0;
  const uint32_t generation = __atomic_load_n(&cp.generation, __ATOMIC_ACQUIRE);
  uint32_t count = 0;
  struct dirent *entry;
  while ((entry = readdir(directory)) != NULL) {
    if (__atomic_load_n(&cp.stop, __ATOMIC_ACQUIRE) ||
        generation != __atomic_load_n(&cp.generation, __ATOMIC_ACQUIRE)) break;
    if (!cp_mp3_name(entry->d_name)) continue;
    char path[CP_PATH_BYTES];
    struct stat status;
    if (!cp_path(path, entry->d_name) || stat(path, &status) ||
        !S_ISREG(status.st_mode) || status.st_size <= 0) continue;
    if (count < CP_MAX_TRACKS) {
      strcpy(tracks[count++], entry->d_name);
    } else {
      /* Keep the first 128 in filename order even if readdir order changes. */
      uint32_t largest = 0;
      for (uint32_t index = 1; index < count; ++index)
        if (cp_name_compare(tracks[index], tracks[largest]) > 0) largest = index;
      if (cp_name_compare(entry->d_name, tracks[largest]) < 0)
        strcpy(tracks[largest], entry->d_name);
    }
  }
  closedir(directory);
  qsort(tracks, count, CP_NAME_BYTES, cp_name_compare);
  return count;
}

/* An extension is not a codec. In particular mpg123 may find false MPEG
 * sync words inside AAC/MP4, emit clipped garbage and spend seconds trying
 * to resynchronise. Reject recognisable non-MPEG containers BEFORE mpg123
 * sees them. This is a bounded signature check, not a complete MP3 parser;
 * ID3 and ordinary MPEG streams retain the decoder's existing handling. */
static int cp_input_allowed(const char *path) {
  unsigned char header[12];
  FILE *file = fopen(path, "rb");
  if (!file) return 0;
  const size_t length = fread(header, 1u, sizeof(header), file);
  const int failed = ferror(file);
  fclose(file);
  if (failed || !length) return 0;
  const int mp4 = length >= 8u &&
      (!memcmp(header + 4, "ftyp", 4) || !memcmp(header + 4, "styp", 4) ||
       !memcmp(header + 4, "moov", 4) || !memcmp(header + 4, "moof", 4) ||
       !memcmp(header + 4, "mdat", 4));
  const int other_container = length >= 4u &&
      (!memcmp(header, "OggS", 4) || !memcmp(header, "fLaC", 4) ||
       !memcmp(header, "caff", 4) || !memcmp(header, "RIFF", 4) ||
       !memcmp(header, "FORM", 4));
  /* ADTS has a 12-bit sync word but layer bits 00, unlike MPEG audio. */
  const int adts = length >= 2u && header[0] == 0xffu &&
      (header[1] & 0xf6u) == 0xf0u;
  if (!mp4 && !other_container && !adts) return 1;
  __atomic_fetch_or(&cp.input_warnings, CUSTOM_PLAYLIST_INPUT_FORMAT, __ATOMIC_RELEASE);
  return 0;
}

static mpg123_handle *cp_open(const char *name) {
  char path[CP_PATH_BYTES];
  if (!cp_path(path, name) || !cp_input_allowed(path)) return NULL;
  int error = 0;
  mpg123_handle *decoder = mpg123_new(NULL, &error);
  if (!decoder) return NULL;
  /* Bound index/junk work and skip cover-art metadata; the worker never
   * loads a complete file. Only 48 kHz stereo signed-16 may enter the ring. */
  if (mpg123_param(decoder, MPG123_ADD_FLAGS,
                   MPG123_FORCE_STEREO | MPG123_QUIET | MPG123_SKIP_ID3V2 |
                   MPG123_NO_PEEK_END, 0.0) != MPG123_OK ||
      mpg123_param(decoder, MPG123_FORCE_RATE, CP_RATE, 0.0) != MPG123_OK ||
      mpg123_param(decoder, MPG123_INDEX_SIZE, 0, 0.0) != MPG123_OK ||
      mpg123_param(decoder, MPG123_RESYNC_LIMIT, 16384, 0.0) != MPG123_OK ||
      mpg123_format_none(decoder) != MPG123_OK ||
      mpg123_format(decoder, CP_RATE, MPG123_STEREO, MPG123_ENC_SIGNED_16) != MPG123_OK ||
      mpg123_open(decoder, path) != MPG123_OK) {
    mpg123_delete(decoder);
    return NULL;
  }
  return decoder;
}

static int cp_format_valid(mpg123_handle *decoder) {
  long rate = 0;
  int channels = 0, encoding = 0;
  return mpg123_getformat(decoder, &rate, &channels, &encoding) == MPG123_OK &&
      rate == CP_RATE && channels == MPG123_STEREO && encoding == MPG123_ENC_SIGNED_16;
}

static void *cp_worker(void *unused) {
  (void)unused;
  char tracks[CP_MAX_TRACKS][CP_NAME_BYTES];
  int16_t chunk[CP_CHUNK_FRAMES * 2];
  mpg123_handle *decoder = NULL;
  uint32_t generation = 0, total = 0, next_track = 0, active_track = 0, usable = 0;
  uint32_t pending = 0, pending_at = 0, track_frames = 0, empty_reads = 0;
  uint32_t decode_slice = 0;
  int exhausted = 0, end_after_chunk = 0, track_failed = 0;
  pthread_once(&cp_mpg_once, cp_mpg_init_once);
  while (!__atomic_load_n(&cp.stop, __ATOMIC_ACQUIRE)) {
    const uint32_t requested = __atomic_load_n(&cp.generation, __ATOMIC_ACQUIRE);
    if (generation != requested) {
      if (decoder) mpg123_delete(decoder);
      decoder = NULL;
      if (!cp_reset_ring(requested)) { cp_wait(5); continue; }
      generation = requested;
      total = next_track = active_track = usable = pending = pending_at = track_frames = empty_reads = 0;
      decode_slice = 0;
      exhausted = end_after_chunk = track_failed = 0;
      if (__atomic_load_n(&cp.enabled, __ATOMIC_ACQUIRE) && cp_mpg_result == MPG123_OK)
        total = cp_scan(tracks);
      usable = total;
      if (!total) exhausted = 1;
    }
    if (!cp_local_menu() || exhausted) { decode_slice = 0; cp_wait(50); continue; }
    if (pending) {
      const uint32_t written = cp_push(chunk + pending_at * 2u, pending, generation);
      pending -= written;
      pending_at += written;
      if (pending) { decode_slice = 0; cp_wait(10); continue; }
      pending_at = 0;
    }
    if (end_after_chunk) {
      if (decoder) mpg123_delete(decoder);
      decoder = NULL;
      /* Partial PCM is not proof of a healthy track. A decoder error after
       * some frames previously reopened the same bad file forever. Keep
       * failed tracks out of this session, even beside a healthy loop. */
      if (track_failed || !track_frames) {
        tracks[active_track][0] = '\0';
        if (!--usable) exhausted = 1;
        __atomic_fetch_or(&cp.input_warnings, CUSTOM_PLAYLIST_INPUT_DECODE, __ATOMIC_RELEASE);
      }
      track_frames = empty_reads = 0;
      end_after_chunk = track_failed = 0;
      continue;
    }
    if (__atomic_load_n(&cp.buffered_frames, __ATOMIC_ACQUIRE) >=
        CP_RING_FRAMES - CP_CHUNK_FRAMES) { decode_slice = 0; cp_wait(10); continue; }
    if (!decoder) {
      while (!tracks[next_track][0]) next_track = (next_track + 1u) % total;
      active_track = next_track;
      decoder = cp_open(tracks[active_track]);
      next_track = (next_track + 1u) % total;
      if (!decoder) {
        tracks[active_track][0] = '\0';
        if (!--usable) exhausted = 1;
        continue;
      }
    }
    size_t bytes = 0;
    const int result = mpg123_read(decoder, (unsigned char *)chunk, sizeof(chunk), &bytes);
    if (bytes > sizeof(chunk) || bytes % (sizeof(int16_t) * 2u) ||
        ((bytes || result == MPG123_NEW_FORMAT) && !cp_format_valid(decoder))) {
      bytes = 0;
      end_after_chunk = track_failed = 1;
    } else {
      pending = (uint32_t)(bytes / (sizeof(int16_t) * 2u));
      track_frames += pending;
      if (pending) empty_reads = 0;
      else if (++empty_reads > 8u) end_after_chunk = track_failed = 1;
      if (result != MPG123_OK && result != MPG123_NEW_FORMAT && result != MPG123_DONE)
        track_failed = 1;
      if (result != MPG123_OK && result != MPG123_NEW_FORMAT) end_after_chunk = 1;
    }
    /* A cold two-second ring previously decoded about 47 chunks without a
     * scheduling point. libnx pthreads share the engine/AAudio priority, so
     * give other runnable workers a turn after at most two decoder calls.
     * The 200 ms ready threshold and ring size remain unchanged. */
    if (++decode_slice >= CP_DECODE_SLICE_CHUNKS) {
      decode_slice = 0;
      cp_wait(1);
    }
  }
  if (decoder) mpg123_delete(decoder);
  return NULL;
}

int custom_playlist_init(const char *directory, int enabled) {
  if (__atomic_load_n(&cp.started, __ATOMIC_ACQUIRE)) return 1;
  if (!directory || !*directory || strlen(directory) >= sizeof(cp.directory)) return 0;
  strcpy(cp.directory, directory);
  __atomic_store_n(&cp.stop, 0u, __ATOMIC_RELEASE);
  __atomic_store_n(&cp.enabled, !!enabled, __ATOMIC_RELEASE);
  __atomic_store_n(&cp.menu_active, 0u, __ATOMIC_RELEASE);
  __atomic_store_n(&cp.audible, 0u, __ATOMIC_RELEASE);
  __atomic_add_fetch(&cp.generation, 1u, __ATOMIC_ACQ_REL);
  __atomic_store_n(&cp.started, 1u, __ATOMIC_RELEASE);
  pthread_attr_t attributes;
  pthread_attr_init(&attributes);
  pthread_attr_setstacksize(&attributes, 256u * 1024u);
  const int result = pthread_create(&cp.thread, &attributes, cp_worker, NULL);
  pthread_attr_destroy(&attributes);
  if (result) {
    __atomic_store_n(&cp.started, 0u, __ATOMIC_RELEASE);
    __atomic_store_n(&cp.stop, 1u, __ATOMIC_RELEASE);
    return 0;
  }
  return 1;
}

void custom_playlist_shutdown(void) {
  if (!__atomic_load_n(&cp.started, __ATOMIC_ACQUIRE)) return;
  __atomic_store_n(&cp.audible, 0u, __ATOMIC_RELEASE);
  __atomic_store_n(&cp.menu_active, 0u, __ATOMIC_RELEASE);
  __atomic_store_n(&cp.stop, 1u, __ATOMIC_RELEASE);
  pthread_join(cp.thread, NULL);
  __atomic_store_n(&cp.started, 0u, __ATOMIC_RELEASE);
}

void custom_playlist_enable(int enabled) {
  const uint32_t value = !!enabled;
  if (__atomic_load_n(&cp.enabled, __ATOMIC_ACQUIRE) == value) return;
  __atomic_store_n(&cp.audible, 0u, __ATOMIC_RELEASE);
  __atomic_store_n(&cp.enabled, value, __ATOMIC_RELEASE);
  __atomic_add_fetch(&cp.generation, 1u, __ATOMIC_ACQ_REL);
}

uint32_t custom_playlist_revision(void) {
  return __atomic_load_n(&cp.generation, __ATOMIC_ACQUIRE);
}

int custom_playlist_enabled(void) {
  return __atomic_load_n(&cp.started, __ATOMIC_ACQUIRE) &&
      __atomic_load_n(&cp.enabled, __ATOMIC_ACQUIRE);
}

uint32_t custom_playlist_input_warnings(void) {
  if (__atomic_load_n(&cp.pcm_generation, __ATOMIC_ACQUIRE) !=
      __atomic_load_n(&cp.generation, __ATOMIC_ACQUIRE)) return 0;
  return __atomic_load_n(&cp.input_warnings, __ATOMIC_ACQUIRE);
}

void custom_playlist_publish(int menu_active, uint64_t now_ms) {
  if (!menu_active) __atomic_store_n(&cp.audible, 0u, __ATOMIC_RELEASE);
  __atomic_store_n(&cp.publication_ms, now_ms, __ATOMIC_RELEASE);
  __atomic_store_n(&cp.local_publication_ms, cp_now_ms(), __ATOMIC_RELEASE);
  __atomic_store_n(&cp.menu_active, !!menu_active, __ATOMIC_RELEASE);
}

int custom_playlist_ready(void) {
  if (!cp_local_menu() ||
      __atomic_load_n(&cp.pcm_generation, __ATOMIC_ACQUIRE) !=
      __atomic_load_n(&cp.generation, __ATOMIC_ACQUIRE)) return 0;
  const uint32_t frames = __atomic_load_n(&cp.buffered_frames, __ATOMIC_ACQUIRE);
  return frames >= CP_PREFILL_FRAMES ||
      (frames && __atomic_load_n(&cp.audible, __ATOMIC_ACQUIRE));
}

void custom_playlist_set_audible(int audible, float gain) {
  if (!audible || !custom_playlist_ready()) {
    __atomic_store_n(&cp.audible, 0u, __ATOMIC_RELEASE);
    return;
  }
  const uint32_t value = !(gain > 0.0f) ? 0u : gain >= 1.0f ? 32768u :
      (uint32_t)(gain * 32768.0f);
  __atomic_store_n(&cp.gain, value, __ATOMIC_RELEASE);
  if (!__atomic_load_n(&cp.audible, __ATOMIC_ACQUIRE))
    __atomic_add_fetch(&cp.output_serial, 1u, __ATOMIC_ACQ_REL);
  __atomic_store_n(&cp.audible, 1u, __ATOMIC_RELEASE);
}

void custom_playlist_mix_pcm(int16_t *output, uint32_t frames, uint64_t now_ms) {
  if (!output || !frames || !__atomic_load_n(&cp.audible, __ATOMIC_ACQUIRE) ||
      !cp_current_menu(now_ms, __atomic_load_n(&cp.publication_ms, __ATOMIC_ACQUIRE)) ||
      !cp_try_lock()) return;
  if (__atomic_load_n(&cp.pcm_generation, __ATOMIC_ACQUIRE) !=
      __atomic_load_n(&cp.generation, __ATOMIC_ACQUIRE)) {
    cp_unlock();
    return;
  }
  const uint32_t serial = __atomic_load_n(&cp.output_serial, __ATOMIC_ACQUIRE);
  if (cp.mix_serial != serial) { cp.mix_serial = serial; cp.attack = 0; }
  const uint32_t gain = __atomic_load_n(&cp.gain, __ATOMIC_ACQUIRE);
  if (frames > cp.count) frames = cp.count;
  for (uint32_t frame = 0; frame < frames; ++frame) {
    if (cp.attack < CP_ATTACK_FRAMES) ++cp.attack;
    const int32_t envelope = (int32_t)(gain * cp.attack / CP_ATTACK_FRAMES);
    for (uint32_t channel = 0; channel < 2u; ++channel) {
      const int32_t value = output[frame * 2u + channel] +
          (int32_t)cp.ring[cp.read_at * 2u + channel] * envelope / 32768;
      output[frame * 2u + channel] =
          (int16_t)(value < -32768 ? -32768 : value > 32767 ? 32767 : value);
    }
    cp.read_at = (cp.read_at + 1u) % CP_RING_FRAMES;
  }
  cp.count -= frames;
  __atomic_store_n(&cp.buffered_frames, cp.count, __ATOMIC_RELEASE);
  cp_unlock();
}

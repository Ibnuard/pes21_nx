#include "aaudio_shim.h"

#include <malloc.h>
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <switch.h>
#include <time.h>

#include "util.h"

enum {
  AAUDIO_OK = 0,
  AAUDIO_ERROR_INTERNAL = -896,
  AAUDIO_ERROR_INVALID_STATE = -895,
  AAUDIO_ERROR_INVALID_HANDLE = -892,
  AAUDIO_ERROR_UNIMPLEMENTED = -890,
  AAUDIO_ERROR_UNAVAILABLE = -889,
  AAUDIO_FORMAT_UNSPECIFIED = 0,
  AAUDIO_FORMAT_PCM_I16 = 1,
  AAUDIO_FORMAT_PCM_FLOAT = 2,
  AAUDIO_DIRECTION_OUTPUT = 0,
  AAUDIO_STREAM_STATE_UNINITIALIZED = 0,
  AAUDIO_STREAM_STATE_UNKNOWN = 1,
  AAUDIO_STREAM_STATE_OPEN = 2,
  AAUDIO_STREAM_STATE_STARTING = 3,
  AAUDIO_STREAM_STATE_STARTED = 4,
  AAUDIO_STREAM_STATE_PAUSING = 5,
  AAUDIO_STREAM_STATE_PAUSED = 6,
  AAUDIO_STREAM_STATE_FLUSHING = 7,
  AAUDIO_STREAM_STATE_FLUSHED = 8,
  AAUDIO_STREAM_STATE_STOPPING = 9,
  AAUDIO_STREAM_STATE_STOPPED = 10,
  AAUDIO_STREAM_STATE_CLOSING = 11,
  AAUDIO_STREAM_STATE_CLOSED = 12,
  AAUDIO_CALLBACK_RESULT_CONTINUE = 0,
  AAUDIO_AUDOUT_BUFFER_COUNT = 4,
  AAUDIO_AUDOUT_SAMPLE_RATE = 48000,
  AAUDIO_AUDOUT_CHANNEL_COUNT = 2,
  AAUDIO_AUDOUT_BUFFER_FRAMES = 1024,
  AAUDIO_DEFAULT_SAMPLE_RATE = 48000,
  AAUDIO_DEFAULT_CHANNEL_COUNT = 2,
  AAUDIO_DEFAULT_CALLBACK_FRAMES = 256,
  AAUDIO_MAX_CALLBACK_FRAMES = 8192,
};

typedef struct {
  AudioOutBuffer nx;
  uint64_t source_frames;
} AAudioOutputBuffer;

struct AAudioStreamBuilder {
  int32_t device_id;
  int32_t direction;
  int32_t format;
  int32_t channel_count;
  int32_t buffer_capacity_frames;
  int32_t frames_per_callback;
  int32_t sharing_mode;
  int32_t performance_mode;
  int32_t sample_rate;
  AAudioDataCallback data_callback;
  void *data_user;
  AAudioErrorCallback error_callback;
  void *error_user;
};

struct AAudioStream {
  int32_t device_id;
  int32_t direction;
  int32_t format;
  int32_t channel_count;
  int32_t buffer_capacity_frames;
  int32_t buffer_size_frames;
  int32_t frames_per_callback;
  int32_t output_buffer_frames;
  int32_t sharing_mode;
  int32_t performance_mode;
  int32_t sample_rate;
  AAudioDataCallback data_callback;
  void *data_user;
  AAudioErrorCallback error_callback;
  void *error_user;
  pthread_t thread;
  _Alignas(4) int32_t state;
  _Alignas(4) int32_t requested_state;
  _Alignas(4) int32_t initialized;
  _Alignas(4) int32_t closing;
  _Alignas(4) int32_t xrun_count;
  _Alignas(8) int64_t frames_read;
  _Alignas(8) int64_t frames_written;
  void *callback_buffer;
  size_t callback_buffer_size;
  int32_t callback_buffer_position;
  int32_t callback_buffer_valid;
  int32_t current_left;
  int32_t current_right;
  int32_t next_left;
  int32_t next_right;
  uint64_t resample_phase;
  int resampler_initialized;
  int queue_active;
  int audout_started;
  AAudioOutputBuffer output_buffers[AAUDIO_AUDOUT_BUFFER_COUNT];
#ifdef DEBUG_LOG
  uint32_t debug_callback_count;
  uint32_t debug_output_buffer_count;
  uint32_t debug_released_buffer_count;
  uint64_t debug_frames_analyzed;
  uint64_t debug_next_state_frame;
  uint64_t debug_pcm_window_frames;
  uint64_t debug_pcm_window_absolute_total;
  uint64_t debug_pcm_window_samples;
  uint64_t debug_heartbeat_frames;
  int32_t debug_pcm_window_peak;
  int32_t debug_peak_max;
  int debug_pcm_reported;
  int debug_quiet_reported;
#endif
  struct AAudioStream *next;
};

static pthread_mutex_t aaudio_mutex = PTHREAD_MUTEX_INITIALIZER;
static int aaudio_audout_initialized;
static AAudioStream *aaudio_streams;
#ifdef DEBUG_LOG
static const uint8_t *aaudio_game_interface_init;
static const void *const *aaudio_game_interface_file;
static const uint8_t *aaudio_game_load_init;
static const uint8_t *aaudio_game_load_manager_init;
static const uint8_t *aaudio_game_music_init;
static const uint64_t *aaudio_game_music_cue;
#endif

void aaudio_shim_set_game_state_diagnostics(
    const uint8_t *interface_init, const void *const *interface_file,
    const uint8_t *load_init, const uint8_t *load_manager_init,
    const uint8_t *music_init, const uint64_t *music_cue) {
#ifdef DEBUG_LOG
  aaudio_game_interface_init = interface_init;
  aaudio_game_interface_file = interface_file;
  aaudio_game_load_init = load_init;
  aaudio_game_load_manager_init = load_manager_init;
  aaudio_game_music_init = music_init;
  aaudio_game_music_cue = music_cue;
  debugPrintf("AAudio: game diagnostics interface=%p file=%p load=%p "
              "manager=%p music=%p cue=%p\n",
              interface_init, interface_file, load_init, load_manager_init,
              music_init, music_cue);
#else
  (void)interface_init;
  (void)interface_file;
  (void)load_init;
  (void)load_manager_init;
  (void)music_init;
  (void)music_cue;
#endif
}

static void aaudio_sleep_ns(int64_t nanoseconds) {
  if (nanoseconds <= 0)
    return;
  if (nanoseconds > 10000000LL)
    nanoseconds = 10000000LL;
  svcSleepThread(nanoseconds);
}

static size_t aaudio_sample_size(int32_t format) {
  return format == AAUDIO_FORMAT_PCM_FLOAT ? sizeof(float) : sizeof(int16_t);
}

static int aaudio_ensure_audout(void) {
  pthread_mutex_lock(&aaudio_mutex);
  if (!aaudio_audout_initialized) {
    const Result rc = audoutInitialize();
    debugPrintf("AAudio: audoutInitialize -> %08x\n", rc);
    if (R_SUCCEEDED(rc)) {
      const u32 rate = audoutGetSampleRate();
      const u32 channels = audoutGetChannelCount();
      const PcmFormat format = audoutGetPcmFormat();
      debugPrintf("AAudio: audout device rate=%u channels=%u format=%u "
                  "state=%u\n",
                  rate, channels, format, audoutGetDeviceState());
      if (rate == AAUDIO_AUDOUT_SAMPLE_RATE &&
          channels == AAUDIO_AUDOUT_CHANNEL_COUNT &&
          format == PcmFormat_Int16) {
        aaudio_audout_initialized = 1;
      } else {
        audoutExit();
      }
    }
  }
  const int available = aaudio_audout_initialized;
  pthread_mutex_unlock(&aaudio_mutex);
  return available;
}

static void aaudio_report_error(AAudioStream *stream, int32_t error) {
  if (stream->error_callback)
    stream->error_callback(stream, stream->error_user, error);
}

#ifdef DEBUG_LOG
static void aaudio_debug_game_state(AAudioStream *stream) {
  if (!aaudio_game_interface_init)
    return;
  const uint8_t interface_init =
      __atomic_load_n(aaudio_game_interface_init, __ATOMIC_RELAXED);
  const void *interface_file = aaudio_game_interface_file
                                   ? __atomic_load_n(aaudio_game_interface_file,
                                                     __ATOMIC_RELAXED)
                                   : NULL;
  const uint8_t load_init = aaudio_game_load_init
                                ? __atomic_load_n(aaudio_game_load_init,
                                                  __ATOMIC_RELAXED)
                                : 0;
  const uint8_t manager_init =
      aaudio_game_load_manager_init
          ? __atomic_load_n(aaudio_game_load_manager_init, __ATOMIC_RELAXED)
          : 0;
  const uint8_t music_init = aaudio_game_music_init
                                 ? __atomic_load_n(aaudio_game_music_init,
                                                   __ATOMIC_RELAXED)
                                 : 0;
  const uint64_t music_cue = aaudio_game_music_cue
                                 ? __atomic_load_n(aaudio_game_music_cue,
                                                   __ATOMIC_RELAXED)
                                 : 0;
  debugPrintf("AAudio: game sound state interface=%u file=%p load=%u "
              "manager=%u music=%u cue=0x%llx\n",
              interface_init, interface_file, load_init, manager_init,
              music_init, (unsigned long long)music_cue);
  stream->debug_next_state_frame =
      stream->debug_frames_analyzed + (uint64_t)stream->sample_rate * 5;
}

static void aaudio_debug_pcm(AAudioStream *stream, const void *data,
                             int32_t frames) {
  int32_t peak = 0;
  uint64_t absolute_total = 0;
  const size_t sample_count = (size_t)frames * stream->channel_count;
  if (stream->format == AAUDIO_FORMAT_PCM_I16) {
    const int16_t *samples = data;
    for (size_t index = 0; index < sample_count; index++) {
      int32_t magnitude = samples[index];
      if (magnitude < 0)
        magnitude = -magnitude;
      absolute_total += (uint32_t)magnitude;
      if (magnitude > peak)
        peak = magnitude;
    }
  } else {
    const float *samples = data;
    for (size_t index = 0; index < sample_count; index++) {
      float magnitude = samples[index];
      if (magnitude < 0.0f)
        magnitude = -magnitude;
      if (magnitude > 1.0f)
        magnitude = 1.0f;
      const int32_t scaled = (int32_t)(magnitude * 32767.0f);
      absolute_total += (uint32_t)scaled;
      if (scaled > peak)
        peak = scaled;
    }
  }

  stream->debug_frames_analyzed += frames;
  if (stream->debug_frames_analyzed >= stream->debug_next_state_frame)
    aaudio_debug_game_state(stream);
  if (peak > stream->debug_peak_max)
    stream->debug_peak_max = peak;
  const uint32_t mean_absolute =
      sample_count ? (uint32_t)(absolute_total / sample_count) : 0;
  if (!stream->debug_pcm_reported && peak >= 64 && mean_absolute >= 2) {
    stream->debug_pcm_reported = 1;
    debugPrintf("AAudio: audible PCM stream=%p callbacks=%u peak=%d "
                "mean_abs=%u\n",
                stream, stream->debug_callback_count, peak, mean_absolute);
  } else if (!stream->debug_quiet_reported &&
             stream->debug_frames_analyzed >=
                 (uint64_t)stream->sample_rate * 2) {
    stream->debug_quiet_reported = 1;
    debugPrintf("AAudio: first 2 seconds below audible threshold stream=%p "
                "peak_max=%d\n",
                stream, stream->debug_peak_max);
  }

  stream->debug_pcm_window_frames += frames;
  stream->debug_pcm_window_absolute_total += absolute_total;
  stream->debug_pcm_window_samples += sample_count;
  if (peak > stream->debug_pcm_window_peak)
    stream->debug_pcm_window_peak = peak;
  if (stream->debug_pcm_window_frames >= (uint64_t)stream->sample_rate * 5) {
    const uint32_t window_mean =
        stream->debug_pcm_window_samples
            ? (uint32_t)(stream->debug_pcm_window_absolute_total /
                         stream->debug_pcm_window_samples)
            : 0;
    debugPrintf("AAudio: PCM window stream=%p peak=%d mean_abs=%u "
                "frames=%llu\n",
                stream, stream->debug_pcm_window_peak, window_mean,
                (unsigned long long)stream->debug_pcm_window_frames);
    stream->debug_pcm_window_frames = 0;
    stream->debug_pcm_window_absolute_total = 0;
    stream->debug_pcm_window_samples = 0;
    stream->debug_pcm_window_peak = 0;
  }
}
#endif

static int aaudio_refill_callback_buffer(AAudioStream *stream) {
  memset(stream->callback_buffer, 0, stream->callback_buffer_size);
  int32_t result = AAUDIO_CALLBACK_RESULT_CONTINUE;
#ifdef DEBUG_LOG
  const uint32_t callback_index = ++stream->debug_callback_count;
  if (callback_index <= 16 || (callback_index & 8191u) == 0)
    debugPrintf("AAudio: callback stream=%p callback=%u frames=%d\n",
                stream, callback_index, stream->frames_per_callback);
#endif
  if (stream->data_callback) {
    result = stream->data_callback(stream, stream->data_user,
                                   stream->callback_buffer,
                                   stream->frames_per_callback);
  }
  if (result != AAUDIO_CALLBACK_RESULT_CONTINUE) {
    debugPrintf("AAudio: callback requested stop stream=%p result=%d\n",
                stream, result);
    return 0;
  }
#ifdef DEBUG_LOG
  aaudio_debug_pcm(stream, stream->callback_buffer,
                   stream->frames_per_callback);
#endif
  stream->callback_buffer_position = 0;
  stream->callback_buffer_valid = stream->frames_per_callback;
  __atomic_add_fetch(&stream->frames_written, stream->frames_per_callback,
                     __ATOMIC_RELEASE);
  return 1;
}

static int32_t aaudio_float_to_s16(float value) {
  if (value > 1.0f)
    value = 1.0f;
  else if (value < -1.0f)
    value = -1.0f;
  return (int32_t)(value * 32767.0f);
}

static int aaudio_next_source_frame(AAudioStream *stream, int32_t *left,
                                    int32_t *right) {
  if (stream->callback_buffer_position >= stream->callback_buffer_valid &&
      !aaudio_refill_callback_buffer(stream))
    return 0;

  const int32_t frame = stream->callback_buffer_position++;
  if (stream->format == AAUDIO_FORMAT_PCM_I16) {
    const int16_t *samples = stream->callback_buffer;
    *left = samples[(size_t)frame * stream->channel_count];
    *right = stream->channel_count == 1
                 ? *left
                 : samples[(size_t)frame * stream->channel_count + 1];
  } else {
    const float *samples = stream->callback_buffer;
    *left = aaudio_float_to_s16(
        samples[(size_t)frame * stream->channel_count]);
    *right = stream->channel_count == 1
                 ? *left
                 : aaudio_float_to_s16(
                       samples[(size_t)frame * stream->channel_count + 1]);
  }
  return 1;
}

static void aaudio_reset_resampler(AAudioStream *stream) {
  stream->callback_buffer_position = 0;
  stream->callback_buffer_valid = 0;
  stream->resample_phase = 0;
  stream->resampler_initialized = 0;
}

static int aaudio_render_output(AAudioStream *stream, int16_t *output,
                                uint64_t *source_frames) {
  if (!stream->resampler_initialized) {
    if (!aaudio_next_source_frame(stream, &stream->current_left,
                                  &stream->current_right) ||
        !aaudio_next_source_frame(stream, &stream->next_left,
                                  &stream->next_right))
      return 0;
    stream->resampler_initialized = 1;
  }

  uint64_t advanced = 0;
  for (int32_t frame = 0; frame < AAUDIO_AUDOUT_BUFFER_FRAMES; frame++) {
    const int64_t left_delta = stream->next_left - stream->current_left;
    const int64_t right_delta = stream->next_right - stream->current_right;
    output[(size_t)frame * 2] =
        (int16_t)(stream->current_left +
                  left_delta * (int64_t)stream->resample_phase /
                      AAUDIO_AUDOUT_SAMPLE_RATE);
    output[(size_t)frame * 2 + 1] =
        (int16_t)(stream->current_right +
                  right_delta * (int64_t)stream->resample_phase /
                      AAUDIO_AUDOUT_SAMPLE_RATE);

    stream->resample_phase += (uint32_t)stream->sample_rate;
    while (stream->resample_phase >= AAUDIO_AUDOUT_SAMPLE_RATE) {
      stream->resample_phase -= AAUDIO_AUDOUT_SAMPLE_RATE;
      stream->current_left = stream->next_left;
      stream->current_right = stream->next_right;
      if (!aaudio_next_source_frame(stream, &stream->next_left,
                                    &stream->next_right))
        return 0;
      advanced++;
    }
  }
  *source_frames = advanced;
  return 1;
}

static int aaudio_fill_output_buffer(AAudioStream *stream,
                                     AAudioOutputBuffer *buffer) {
  uint64_t source_frames = 0;
  if (!aaudio_render_output(stream, buffer->nx.buffer, &source_frames))
    return 0;
  buffer->source_frames = source_frames;
  buffer->nx.data_size =
      AAUDIO_AUDOUT_BUFFER_FRAMES * AAUDIO_AUDOUT_CHANNEL_COUNT *
      sizeof(int16_t);
#ifdef DEBUG_LOG
  stream->debug_output_buffer_count++;
#endif
  const Result rc = audoutAppendAudioOutBuffer(&buffer->nx);
  if (R_FAILED(rc)) {
    debugPrintf("AAudio: audoutAppendAudioOutBuffer failed: %08x\n", rc);
    __atomic_add_fetch(&stream->xrun_count, 1, __ATOMIC_RELAXED);
    aaudio_report_error(stream, AAUDIO_ERROR_INTERNAL);
    return 0;
  }
  return 1;
}

static void aaudio_stop_and_flush(AAudioStream *stream) {
  if (stream->audout_started) {
    const Result stop_rc = audoutStopAudioOut();
    if (R_FAILED(stop_rc))
      debugPrintf("AAudio: audoutStopAudioOut failed: %08x\n", stop_rc);
    stream->audout_started = 0;
  }
  if (stream->queue_active) {
    bool flushed = false;
    const Result flush_rc = audoutFlushAudioOutBuffers(&flushed);
    debugPrintf("AAudio: audout flush rc=%08x flushed=%d\n", flush_rc,
                flushed);
    stream->queue_active = 0;
  }
}

static int aaudio_start_output(AAudioStream *stream) {
  if (!stream->queue_active) {
    aaudio_reset_resampler(stream);
    stream->queue_active = 1;
    for (int index = 0; index < AAUDIO_AUDOUT_BUFFER_COUNT; index++) {
      if (!aaudio_fill_output_buffer(stream, &stream->output_buffers[index])) {
        aaudio_stop_and_flush(stream);
        return 0;
      }
    }
  }
  if (!stream->audout_started) {
    const Result rc = audoutStartAudioOut();
    debugPrintf("AAudio: audoutStartAudioOut -> %08x\n", rc);
    if (R_FAILED(rc)) {
      aaudio_report_error(stream, AAUDIO_ERROR_UNAVAILABLE);
      return 0;
    }
    stream->audout_started = 1;
  }
  return 1;
}

static void aaudio_release_and_requeue(AAudioStream *stream,
                                       AudioOutBuffer *released) {
  if (!released)
    return;
  AAudioOutputBuffer *buffer = (AAudioOutputBuffer *)released;
  __atomic_add_fetch(&stream->frames_read, buffer->source_frames,
                     __ATOMIC_RELEASE);
#ifdef DEBUG_LOG
  stream->debug_released_buffer_count++;
  stream->debug_heartbeat_frames += AAUDIO_AUDOUT_BUFFER_FRAMES;
  if (stream->debug_heartbeat_frames >=
      (uint64_t)AAUDIO_AUDOUT_SAMPLE_RATE * 5) {
    debugPrintf("AAudio: audout heartbeat stream=%p callbacks=%u filled=%u "
                "released=%u written=%lld read=%lld xruns=%d\n",
                stream, stream->debug_callback_count,
                stream->debug_output_buffer_count,
                stream->debug_released_buffer_count,
                (long long)__atomic_load_n(&stream->frames_written,
                                            __ATOMIC_ACQUIRE),
                (long long)__atomic_load_n(&stream->frames_read,
                                            __ATOMIC_ACQUIRE),
                __atomic_load_n(&stream->xrun_count, __ATOMIC_ACQUIRE));
    stream->debug_heartbeat_frames = 0;
  }
#endif
  if (!aaudio_fill_output_buffer(stream, buffer))
    __atomic_store_n(&stream->requested_state, AAUDIO_STREAM_STATE_STOPPED,
                     __ATOMIC_RELEASE);
}

static void *aaudio_stream_thread(void *argument) {
  AAudioStream *stream = argument;
  debugPrintf("AAudio: audout output thread begin stream=%p\n", stream);
  __atomic_store_n(&stream->initialized, 1, __ATOMIC_RELEASE);

  int32_t applied_state = AAUDIO_STREAM_STATE_OPEN;
  while (!__atomic_load_n(&stream->closing, __ATOMIC_ACQUIRE)) {
    const int32_t requested =
        __atomic_load_n(&stream->requested_state, __ATOMIC_ACQUIRE);
    if (requested != applied_state) {
      if (requested == AAUDIO_STREAM_STATE_STARTED) {
        if (!aaudio_start_output(stream)) {
          __atomic_store_n(&stream->requested_state,
                           AAUDIO_STREAM_STATE_STOPPED, __ATOMIC_RELEASE);
          applied_state = AAUDIO_STREAM_STATE_STOPPED;
        } else {
          applied_state = AAUDIO_STREAM_STATE_STARTED;
        }
      } else if (requested == AAUDIO_STREAM_STATE_PAUSED) {
        if (stream->audout_started) {
          audoutStopAudioOut();
          stream->audout_started = 0;
        }
        applied_state = AAUDIO_STREAM_STATE_PAUSED;
      } else if (requested == AAUDIO_STREAM_STATE_FLUSHED) {
        aaudio_stop_and_flush(stream);
        aaudio_reset_resampler(stream);
        applied_state = AAUDIO_STREAM_STATE_FLUSHED;
      } else if (requested == AAUDIO_STREAM_STATE_STOPPED) {
        aaudio_stop_and_flush(stream);
        applied_state = AAUDIO_STREAM_STATE_STOPPED;
      }
      __atomic_store_n(&stream->state, applied_state, __ATOMIC_RELEASE);
    }

    if (applied_state != AAUDIO_STREAM_STATE_STARTED) {
      aaudio_sleep_ns(1000000LL);
      continue;
    }

    AudioOutBuffer *released = NULL;
    u32 released_count = 0;
    Result rc = audoutWaitPlayFinish(&released, &released_count, 10000000ULL);
    if (R_FAILED(rc))
      continue;
    aaudio_release_and_requeue(stream, released);

    while (!__atomic_load_n(&stream->closing, __ATOMIC_ACQUIRE)) {
      released = NULL;
      released_count = 0;
      rc = audoutGetReleasedAudioOutBuffer(&released, &released_count);
      if (R_FAILED(rc) || !released || released_count == 0)
        break;
      aaudio_release_and_requeue(stream, released);
    }
  }

  __atomic_store_n(&stream->state, AAUDIO_STREAM_STATE_CLOSING,
                   __ATOMIC_RELEASE);
  aaudio_stop_and_flush(stream);
  __atomic_store_n(&stream->state, AAUDIO_STREAM_STATE_CLOSED,
                   __ATOMIC_RELEASE);
  return NULL;
}

int32_t AAudio_createStreamBuilder(AAudioStreamBuilder **builder) {
  debugPrintf("AAudio: create builder out=%p\n", builder);
  if (!builder)
    return AAUDIO_ERROR_INVALID_HANDLE;
  AAudioStreamBuilder *created = calloc(1, sizeof(*created));
  if (!created)
    return AAUDIO_ERROR_INTERNAL;
  created->direction = AAUDIO_DIRECTION_OUTPUT;
  created->format = AAUDIO_FORMAT_UNSPECIFIED;
  *builder = created;
  debugPrintf("AAudio: created builder=%p\n", created);
  return AAUDIO_OK;
}

int32_t AAudioStreamBuilder_openStream(AAudioStreamBuilder *builder,
                                       AAudioStream **stream_out) {
  debugPrintf("AAudio: open requested builder=%p out=%p rate=%d channels=%d "
              "format=%d callback_frames=%d\n",
              builder, stream_out, builder ? builder->sample_rate : 0,
              builder ? builder->channel_count : 0,
              builder ? builder->format : 0,
              builder ? builder->frames_per_callback : 0);
  if (!builder || !stream_out)
    return AAUDIO_ERROR_INVALID_HANDLE;
  if (builder->direction != AAUDIO_DIRECTION_OUTPUT ||
      !aaudio_ensure_audout())
    return AAUDIO_ERROR_UNAVAILABLE;

  pthread_mutex_lock(&aaudio_mutex);
  const int stream_busy = aaudio_streams != NULL;
  pthread_mutex_unlock(&aaudio_mutex);
  if (stream_busy) {
    debugPrintf("AAudio: audout supports one active stream\n");
    return AAUDIO_ERROR_UNAVAILABLE;
  }

  AAudioStream *stream = calloc(1, sizeof(*stream));
  if (!stream)
    return AAUDIO_ERROR_INTERNAL;
  stream->device_id = builder->device_id;
  stream->direction = builder->direction;
  stream->format = builder->format == AAUDIO_FORMAT_UNSPECIFIED
                       ? AAUDIO_FORMAT_PCM_I16
                       : builder->format;
  stream->channel_count = builder->channel_count > 0
                              ? builder->channel_count
                              : AAUDIO_DEFAULT_CHANNEL_COUNT;
  stream->frames_per_callback = builder->frames_per_callback > 0
                                    ? builder->frames_per_callback
                                    : AAUDIO_DEFAULT_CALLBACK_FRAMES;
  stream->sample_rate = builder->sample_rate > 0
                            ? builder->sample_rate
                            : AAUDIO_DEFAULT_SAMPLE_RATE;
  if ((stream->format != AAUDIO_FORMAT_PCM_I16 &&
       stream->format != AAUDIO_FORMAT_PCM_FLOAT) ||
      stream->channel_count < 1 || stream->channel_count > 2 ||
      stream->frames_per_callback > AAUDIO_MAX_CALLBACK_FRAMES ||
      stream->sample_rate <= 0 || stream->sample_rate > 192000) {
    free(stream);
    return AAUDIO_ERROR_UNIMPLEMENTED;
  }

  stream->output_buffer_frames = AAUDIO_DEFAULT_CALLBACK_FRAMES;
  const int32_t minimum_capacity =
      (AAUDIO_AUDOUT_BUFFER_FRAMES * AAUDIO_AUDOUT_BUFFER_COUNT *
       stream->sample_rate + AAUDIO_AUDOUT_SAMPLE_RATE - 1) /
      AAUDIO_AUDOUT_SAMPLE_RATE;
  stream->buffer_capacity_frames = builder->buffer_capacity_frames;
  if (stream->buffer_capacity_frames < minimum_capacity)
    stream->buffer_capacity_frames = minimum_capacity;
  stream->buffer_size_frames = stream->buffer_capacity_frames;
  stream->sharing_mode = builder->sharing_mode;
  stream->performance_mode = builder->performance_mode;
  stream->data_callback = builder->data_callback;
  stream->data_user = builder->data_user;
  stream->error_callback = builder->error_callback;
  stream->error_user = builder->error_user;
  stream->callback_buffer_size =
      (size_t)stream->frames_per_callback * stream->channel_count *
      aaudio_sample_size(stream->format);
  stream->callback_buffer = malloc(stream->callback_buffer_size);
  if (!stream->callback_buffer) {
    free(stream);
    return AAUDIO_ERROR_INTERNAL;
  }

  const size_t audout_data_size =
      AAUDIO_AUDOUT_BUFFER_FRAMES * AAUDIO_AUDOUT_CHANNEL_COUNT *
      sizeof(int16_t);
  for (int index = 0; index < AAUDIO_AUDOUT_BUFFER_COUNT; index++) {
    AAudioOutputBuffer *buffer = &stream->output_buffers[index];
    buffer->nx.buffer = memalign(0x1000, audout_data_size);
    if (!buffer->nx.buffer) {
      for (int release = 0; release < index; release++)
        free(stream->output_buffers[release].nx.buffer);
      free(stream->callback_buffer);
      free(stream);
      return AAUDIO_ERROR_INTERNAL;
    }
    memset(buffer->nx.buffer, 0, audout_data_size);
    buffer->nx.next = NULL;
    buffer->nx.buffer_size = audout_data_size;
    buffer->nx.data_size = audout_data_size;
    buffer->nx.data_offset = 0;
  }

  stream->state = AAUDIO_STREAM_STATE_OPEN;
  stream->requested_state = AAUDIO_STREAM_STATE_OPEN;
  pthread_attr_t attributes;
  pthread_attr_init(&attributes);
  pthread_attr_setstacksize(&attributes, 256 * 1024);
  const int thread_result = pthread_create(
      &stream->thread, &attributes, aaudio_stream_thread, stream);
  pthread_attr_destroy(&attributes);
  if (thread_result != 0) {
    for (int index = 0; index < AAUDIO_AUDOUT_BUFFER_COUNT; index++)
      free(stream->output_buffers[index].nx.buffer);
    free(stream->callback_buffer);
    free(stream);
    return AAUDIO_ERROR_UNAVAILABLE;
  }

  for (unsigned int attempt = 0; attempt < 1000; attempt++) {
    if (__atomic_load_n(&stream->initialized, __ATOMIC_ACQUIRE) != 0)
      break;
    aaudio_sleep_ns(1000000LL);
  }
  if (__atomic_load_n(&stream->initialized, __ATOMIC_ACQUIRE) != 1) {
    __atomic_store_n(&stream->closing, 1, __ATOMIC_RELEASE);
    pthread_join(stream->thread, NULL);
    for (int index = 0; index < AAUDIO_AUDOUT_BUFFER_COUNT; index++)
      free(stream->output_buffers[index].nx.buffer);
    free(stream->callback_buffer);
    free(stream);
    return AAUDIO_ERROR_UNAVAILABLE;
  }

  pthread_mutex_lock(&aaudio_mutex);
  stream->next = aaudio_streams;
  aaudio_streams = stream;
  pthread_mutex_unlock(&aaudio_mutex);
  *stream_out = stream;
  debugPrintf("AAudio: opened audout stream=%p source_rate=%d output_rate=%d "
              "channels=%d format=%d callback_frames=%d capacity=%d\n",
              stream, stream->sample_rate, AAUDIO_AUDOUT_SAMPLE_RATE,
              stream->channel_count, stream->format,
              stream->frames_per_callback, stream->buffer_capacity_frames);
  return AAUDIO_OK;
}

#define AAUDIO_BUILDER_SETTER(name, field)                                  \
  void name(AAudioStreamBuilder *builder, int32_t value) {                  \
    if (builder)                                                             \
      builder->field = value;                                                \
  }

AAUDIO_BUILDER_SETTER(AAudioStreamBuilder_setChannelCount, channel_count)
AAUDIO_BUILDER_SETTER(AAudioStreamBuilder_setSamplesPerFrame, channel_count)
AAUDIO_BUILDER_SETTER(AAudioStreamBuilder_setBufferCapacityInFrames,
                      buffer_capacity_frames)
AAUDIO_BUILDER_SETTER(AAudioStreamBuilder_setDeviceId, device_id)
AAUDIO_BUILDER_SETTER(AAudioStreamBuilder_setDirection, direction)
AAUDIO_BUILDER_SETTER(AAudioStreamBuilder_setFormat, format)
AAUDIO_BUILDER_SETTER(AAudioStreamBuilder_setFramesPerDataCallback,
                      frames_per_callback)
AAUDIO_BUILDER_SETTER(AAudioStreamBuilder_setSharingMode, sharing_mode)
AAUDIO_BUILDER_SETTER(AAudioStreamBuilder_setPerformanceMode,
                      performance_mode)
AAUDIO_BUILDER_SETTER(AAudioStreamBuilder_setSampleRate, sample_rate)

#undef AAUDIO_BUILDER_SETTER

int32_t AAudioStreamBuilder_delete(AAudioStreamBuilder *builder) {
  free(builder);
  return AAUDIO_OK;
}

int32_t AAudioStreamBuilder_setDataCallback(AAudioStreamBuilder *builder,
                                            AAudioDataCallback callback,
                                            void *user_data) {
  if (!builder)
    return AAUDIO_ERROR_INVALID_HANDLE;
  builder->data_callback = callback;
  builder->data_user = user_data;
  return AAUDIO_OK;
}

int32_t AAudioStreamBuilder_setErrorCallback(AAudioStreamBuilder *builder,
                                             AAudioErrorCallback callback,
                                             void *user_data) {
  if (!builder)
    return AAUDIO_ERROR_INVALID_HANDLE;
  builder->error_callback = callback;
  builder->error_user = user_data;
  return AAUDIO_OK;
}

int32_t AAudioStream_read(AAudioStream *stream, void *buffer,
                          int32_t num_frames, int64_t timeout_nanoseconds) {
  (void)stream;
  (void)buffer;
  (void)num_frames;
  (void)timeout_nanoseconds;
  return AAUDIO_ERROR_UNIMPLEMENTED;
}

int32_t AAudioStream_write(AAudioStream *stream, const void *buffer,
                           int32_t num_frames, int64_t timeout_nanoseconds) {
  (void)stream;
  (void)buffer;
  (void)timeout_nanoseconds;
  return num_frames;
}

int32_t AAudioStream_waitForStateChange(AAudioStream *stream,
                                        int32_t input_state,
                                        int32_t *next_state,
                                        int64_t timeout_nanoseconds) {
  if (!stream || !next_state)
    return AAUDIO_ERROR_INVALID_HANDLE;
  const uint64_t start = armGetSystemTick();
  while (1) {
    const int32_t state = __atomic_load_n(&stream->state, __ATOMIC_ACQUIRE);
    if (state != input_state) {
      *next_state = state;
      return AAUDIO_OK;
    }
    if (timeout_nanoseconds == 0 ||
        (timeout_nanoseconds > 0 &&
         (int64_t)armTicksToNs(armGetSystemTick() - start) >=
             timeout_nanoseconds)) {
      *next_state = state;
      return AAUDIO_OK;
    }
    aaudio_sleep_ns(1000000LL);
  }
}

int32_t AAudioStream_getTimestamp(AAudioStream *stream, int32_t clock_id,
                                  int64_t *frame_position,
                                  int64_t *time_nanoseconds) {
  if (!stream || !frame_position || !time_nanoseconds)
    return AAUDIO_ERROR_INVALID_HANDLE;
  struct timespec now;
  if (clock_gettime(clock_id, &now) != 0)
    clock_gettime(CLOCK_MONOTONIC, &now);
  *frame_position = __atomic_load_n(&stream->frames_read, __ATOMIC_ACQUIRE);
  *time_nanoseconds = (int64_t)now.tv_sec * 1000000000LL + now.tv_nsec;
  return AAUDIO_OK;
}

#define AAUDIO_STREAM_GETTER(name, field, invalid)                          \
  int32_t name(AAudioStream *stream) {                                      \
    return stream ? stream->field : invalid;                                \
  }

AAUDIO_STREAM_GETTER(AAudioStream_getFormat, format, AAUDIO_ERROR_INVALID_HANDLE)
AAUDIO_STREAM_GETTER(AAudioStream_getChannelCount, channel_count,
                     AAUDIO_ERROR_INVALID_HANDLE)
AAUDIO_STREAM_GETTER(AAudioStream_getSamplesPerFrame, channel_count,
                     AAUDIO_ERROR_INVALID_HANDLE)
AAUDIO_STREAM_GETTER(AAudioStream_getBufferSizeInFrames, buffer_size_frames,
                     AAUDIO_ERROR_INVALID_HANDLE)
AAUDIO_STREAM_GETTER(AAudioStream_getDeviceId, device_id,
                     AAUDIO_ERROR_INVALID_HANDLE)
AAUDIO_STREAM_GETTER(AAudioStream_getDirection, direction,
                     AAUDIO_ERROR_INVALID_HANDLE)
AAUDIO_STREAM_GETTER(AAudioStream_getBufferCapacityInFrames,
                     buffer_capacity_frames, AAUDIO_ERROR_INVALID_HANDLE)
AAUDIO_STREAM_GETTER(AAudioStream_getPerformanceMode, performance_mode,
                     AAUDIO_ERROR_INVALID_HANDLE)
AAUDIO_STREAM_GETTER(AAudioStream_getSampleRate, sample_rate,
                     AAUDIO_ERROR_INVALID_HANDLE)
AAUDIO_STREAM_GETTER(AAudioStream_getSharingMode, sharing_mode,
                     AAUDIO_ERROR_INVALID_HANDLE)

#undef AAUDIO_STREAM_GETTER

int32_t AAudioStream_getFramesPerBurst(AAudioStream *stream) {
  if (!stream)
    return AAUDIO_ERROR_INVALID_HANDLE;
  return stream->output_buffer_frames;
}

int64_t AAudioStream_getFramesRead(AAudioStream *stream) {
  return stream
             ? __atomic_load_n(&stream->frames_read, __ATOMIC_ACQUIRE)
             : AAUDIO_ERROR_INVALID_HANDLE;
}

int64_t AAudioStream_getFramesWritten(AAudioStream *stream) {
  return stream
             ? __atomic_load_n(&stream->frames_written, __ATOMIC_ACQUIRE)
             : AAUDIO_ERROR_INVALID_HANDLE;
}

int32_t AAudioStream_getState(AAudioStream *stream) {
  return stream ? __atomic_load_n(&stream->state, __ATOMIC_ACQUIRE)
                : AAUDIO_STREAM_STATE_UNINITIALIZED;
}

int32_t AAudioStream_getXRunCount(AAudioStream *stream) {
  return stream ? __atomic_load_n(&stream->xrun_count, __ATOMIC_ACQUIRE)
                : AAUDIO_ERROR_INVALID_HANDLE;
}

static int32_t aaudio_request_state(AAudioStream *stream,
                                    int32_t transition_state,
                                    int32_t target_state) {
  if (!stream)
    return AAUDIO_ERROR_INVALID_HANDLE;
  const int32_t state = __atomic_load_n(&stream->state, __ATOMIC_ACQUIRE);
  if (state == AAUDIO_STREAM_STATE_CLOSING ||
      state == AAUDIO_STREAM_STATE_CLOSED)
    return AAUDIO_ERROR_INVALID_STATE;
  __atomic_store_n(&stream->state, transition_state, __ATOMIC_RELEASE);
  __atomic_store_n(&stream->requested_state, target_state, __ATOMIC_RELEASE);
  return AAUDIO_OK;
}

int32_t AAudioStream_requestStart(AAudioStream *stream) {
  debugPrintf("AAudio: request start stream=%p\n", stream);
  return aaudio_request_state(stream, AAUDIO_STREAM_STATE_STARTING,
                              AAUDIO_STREAM_STATE_STARTED);
}

int32_t AAudioStream_requestPause(AAudioStream *stream) {
  return aaudio_request_state(stream, AAUDIO_STREAM_STATE_PAUSING,
                              AAUDIO_STREAM_STATE_PAUSED);
}

int32_t AAudioStream_requestFlush(AAudioStream *stream) {
  return aaudio_request_state(stream, AAUDIO_STREAM_STATE_FLUSHING,
                              AAUDIO_STREAM_STATE_FLUSHED);
}

int32_t AAudioStream_requestStop(AAudioStream *stream) {
  return aaudio_request_state(stream, AAUDIO_STREAM_STATE_STOPPING,
                              AAUDIO_STREAM_STATE_STOPPED);
}

int32_t AAudioStream_setBufferSizeInFrames(AAudioStream *stream,
                                           int32_t num_frames) {
  if (!stream)
    return AAUDIO_ERROR_INVALID_HANDLE;
  if (num_frames < stream->output_buffer_frames)
    num_frames = stream->output_buffer_frames;
  if (num_frames > stream->buffer_capacity_frames)
    num_frames = stream->buffer_capacity_frames;
  stream->buffer_size_frames = num_frames;
  return num_frames;
}

int32_t AAudioStream_close(AAudioStream *stream) {
  if (!stream)
    return AAUDIO_ERROR_INVALID_HANDLE;

  pthread_mutex_lock(&aaudio_mutex);
  AAudioStream **link = &aaudio_streams;
  while (*link && *link != stream)
    link = &(*link)->next;
  if (*link == stream)
    *link = stream->next;
  pthread_mutex_unlock(&aaudio_mutex);

  __atomic_store_n(&stream->closing, 1, __ATOMIC_RELEASE);
  pthread_join(stream->thread, NULL);
  debugPrintf("AAudio: closed stream=%p written=%lld read=%lld xruns=%d\n",
              stream, (long long)stream->frames_written,
              (long long)stream->frames_read, stream->xrun_count);
  for (int index = 0; index < AAUDIO_AUDOUT_BUFFER_COUNT; index++)
    free(stream->output_buffers[index].nx.buffer);
  free(stream->callback_buffer);
  free(stream);
  return AAUDIO_OK;
}

const char *AAudio_convertResultToText(int32_t result) {
  switch (result) {
    case AAUDIO_OK:
      return "AAUDIO_OK";
    case AAUDIO_ERROR_INVALID_STATE:
      return "AAUDIO_ERROR_INVALID_STATE";
    case AAUDIO_ERROR_INVALID_HANDLE:
      return "AAUDIO_ERROR_INVALID_HANDLE";
    case AAUDIO_ERROR_UNIMPLEMENTED:
      return "AAUDIO_ERROR_UNIMPLEMENTED";
    case AAUDIO_ERROR_UNAVAILABLE:
      return "AAUDIO_ERROR_UNAVAILABLE";
    default:
      return "AAUDIO_ERROR_INTERNAL";
  }
}

const char *AAudio_convertStreamStateToText(int32_t state) {
  static const char *const names[] = {
      "UNINITIALIZED", "UNKNOWN", "OPEN",    "STARTING", "STARTED",
      "PAUSING",      "PAUSED",  "FLUSHING", "FLUSHED",  "STOPPING",
      "STOPPED",      "CLOSING", "CLOSED",
  };
  return state >= 0 && state < (int32_t)(sizeof(names) / sizeof(names[0]))
             ? names[state]
             : "UNKNOWN";
}

void aaudio_shim_shutdown(void) {
  while (1) {
    pthread_mutex_lock(&aaudio_mutex);
    AAudioStream *stream = aaudio_streams;
    pthread_mutex_unlock(&aaudio_mutex);
    if (!stream)
      break;
    AAudioStream_close(stream);
  }

  pthread_mutex_lock(&aaudio_mutex);
  if (aaudio_audout_initialized) {
    audoutExit();
    aaudio_audout_initialized = 0;
  }
  pthread_mutex_unlock(&aaudio_mutex);
}

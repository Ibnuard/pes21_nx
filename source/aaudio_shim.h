#ifndef PES21_NX_AAUDIO_SHIM_H
#define PES21_NX_AAUDIO_SHIM_H

#include <stdint.h>

typedef struct AAudioStreamBuilder AAudioStreamBuilder;
typedef struct AAudioStream AAudioStream;

typedef int32_t (*AAudioDataCallback)(AAudioStream *stream, void *user_data,
                                     void *audio_data, int32_t num_frames);
typedef void (*AAudioErrorCallback)(AAudioStream *stream, void *user_data,
                                    int32_t error);

int32_t AAudio_createStreamBuilder(AAudioStreamBuilder **builder);
int32_t AAudioStreamBuilder_openStream(AAudioStreamBuilder *builder,
                                       AAudioStream **stream);
void AAudioStreamBuilder_setChannelCount(AAudioStreamBuilder *builder,
                                         int32_t channel_count);
void AAudioStreamBuilder_setSamplesPerFrame(AAudioStreamBuilder *builder,
                                            int32_t channel_count);
void AAudioStreamBuilder_setBufferCapacityInFrames(
    AAudioStreamBuilder *builder, int32_t capacity);
void AAudioStreamBuilder_setDeviceId(AAudioStreamBuilder *builder,
                                     int32_t device_id);
void AAudioStreamBuilder_setDirection(AAudioStreamBuilder *builder,
                                      int32_t direction);
void AAudioStreamBuilder_setFormat(AAudioStreamBuilder *builder,
                                   int32_t format);
void AAudioStreamBuilder_setFramesPerDataCallback(
    AAudioStreamBuilder *builder, int32_t frames);
void AAudioStreamBuilder_setSharingMode(AAudioStreamBuilder *builder,
                                        int32_t sharing_mode);
void AAudioStreamBuilder_setPerformanceMode(AAudioStreamBuilder *builder,
                                            int32_t performance_mode);
void AAudioStreamBuilder_setSampleRate(AAudioStreamBuilder *builder,
                                       int32_t sample_rate);
int32_t AAudioStreamBuilder_delete(AAudioStreamBuilder *builder);
int32_t AAudioStreamBuilder_setDataCallback(AAudioStreamBuilder *builder,
                                            AAudioDataCallback callback,
                                            void *user_data);
int32_t AAudioStreamBuilder_setErrorCallback(AAudioStreamBuilder *builder,
                                             AAudioErrorCallback callback,
                                             void *user_data);

int32_t AAudioStream_read(AAudioStream *stream, void *buffer,
                          int32_t num_frames, int64_t timeout_nanoseconds);
int32_t AAudioStream_write(AAudioStream *stream, const void *buffer,
                           int32_t num_frames, int64_t timeout_nanoseconds);
int32_t AAudioStream_waitForStateChange(AAudioStream *stream,
                                        int32_t input_state,
                                        int32_t *next_state,
                                        int64_t timeout_nanoseconds);
int32_t AAudioStream_getTimestamp(AAudioStream *stream, int32_t clock_id,
                                  int64_t *frame_position,
                                  int64_t *time_nanoseconds);
int32_t AAudioStream_getFormat(AAudioStream *stream);
int32_t AAudioStream_getChannelCount(AAudioStream *stream);
int32_t AAudioStream_getSamplesPerFrame(AAudioStream *stream);
int32_t AAudioStream_close(AAudioStream *stream);
int32_t AAudioStream_getBufferSizeInFrames(AAudioStream *stream);
int32_t AAudioStream_getDeviceId(AAudioStream *stream);
int32_t AAudioStream_getDirection(AAudioStream *stream);
int32_t AAudioStream_getBufferCapacityInFrames(AAudioStream *stream);
int32_t AAudioStream_getFramesPerBurst(AAudioStream *stream);
int64_t AAudioStream_getFramesRead(AAudioStream *stream);
int64_t AAudioStream_getFramesWritten(AAudioStream *stream);
int32_t AAudioStream_getPerformanceMode(AAudioStream *stream);
int32_t AAudioStream_getSampleRate(AAudioStream *stream);
int32_t AAudioStream_getSharingMode(AAudioStream *stream);
int32_t AAudioStream_getState(AAudioStream *stream);
int32_t AAudioStream_getXRunCount(AAudioStream *stream);
int32_t AAudioStream_requestStart(AAudioStream *stream);
int32_t AAudioStream_requestPause(AAudioStream *stream);
int32_t AAudioStream_requestFlush(AAudioStream *stream);
int32_t AAudioStream_requestStop(AAudioStream *stream);
int32_t AAudioStream_setBufferSizeInFrames(AAudioStream *stream,
                                           int32_t num_frames);
const char *AAudio_convertResultToText(int32_t result);
const char *AAudio_convertStreamStateToText(int32_t state);

void aaudio_shim_set_game_state_diagnostics(
    const uint8_t *interface_init, const void *const *interface_file,
    const uint8_t *load_init, const uint8_t *load_manager_init,
    const uint8_t *music_init, const uint64_t *music_cue);
void aaudio_shim_shutdown(void);

#endif

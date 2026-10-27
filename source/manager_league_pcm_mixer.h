/* Owned PCM is blended into the existing 48 kHz stereo AudioOut buffer.
 * Pure bounded math: no allocation, file I/O, device or native mixer calls. */
#ifndef PESNX_MANAGER_LEAGUE_PCM_MIXER_H
#define PESNX_MANAGER_LEAGUE_PCM_MIXER_H
#include <stdint.h>
#include <string.h>
#include "manager_league_audio.h"
#include "manager_league_pcm_catalog.h"

enum { MLA_PCM_VOICES = 6, MLA_PCM_ATTACK = 480, MLA_PCM_RELEASE = 4800,
       MLA_PCM_UNITY = 32768, MLA_PCM_WATCH_NATIVE_GAIN = 6554 };
typedef struct MlaPcmVoice {
  uint64_t handle;
  uint32_t clip, position, attack, release, release_total;
} MlaPcmVoice;
typedef struct MlaPcmMixer {
  const uint8_t *bank;
  MlaPcmVoice voices[MLA_PCM_VOICES];
  uint64_t serial, mixed_frames, nonzero_samples, source_frames[MLA_CLIP_COUNT];
  uint32_t native_gain, peak;
} MlaPcmMixer;

static inline uint32_t mla_pcm_le32(const uint8_t *p) {
  return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static inline int mla_pcm_bind(MlaPcmMixer *m, const void *data, uint32_t bytes) {
  if (!m || !data || m->bank) return 0;
  const uint8_t *bank = data;
  for (uint32_t i = 0; i < MLA_CLIP_COUNT; ++i) {
    const MlaPcmClip c = mla_pcm_clips[i];
    if (!c.frames) continue;
    const uint64_t end = (uint64_t)c.wave_offset + 44u + (uint64_t)c.frames * 4u;
    if (end > bytes || c.wave_offset % 4u || c.frames > 1440000u) return 0;
    const uint8_t *w = bank + c.wave_offset;
    static const uint8_t format[] = {16,0,0,0,1,0,2,0,128,187,0,0,0,238,2,0,4,0,16,0};
    if (memcmp(w, "RIFF", 4) || mla_pcm_le32(w + 4) != c.frames * 4u + 36u ||
        memcmp(w + 8, "WAVEfmt ", 8) || memcmp(w + 16, format, sizeof(format)) ||
        memcmp(w + 36, "data", 4) || mla_pcm_le32(w + 40) != c.frames * 4u) return 0;
  }
  m->bank = data;
  m->native_gain = MLA_PCM_UNITY;
  return 1;
}
static inline int mla_pcm_start(MlaPcmMixer *m, uint32_t clip, uint64_t *handle) {
  if (!handle) return -1;
  *handle = 0;
  if (!m->bank || clip >= MLA_CLIP_COUNT || !mla_pcm_clips[clip].frames) return -1;
  for (uint32_t i = 0; i < MLA_PCM_VOICES; ++i) if (!m->voices[i].handle) {
    uint64_t serial = ++m->serial;
    if (!serial) serial = ++m->serial;
    m->voices[i] = (MlaPcmVoice){.handle=serial, .clip=clip, .attack=MLA_PCM_ATTACK};
    *handle = serial;
    return 0;
  }
  return -1;
}
static inline int mla_pcm_stop(MlaPcmMixer *m, uint64_t handle, uint32_t fade_ms) {
  for (uint32_t i = 0; i < MLA_PCM_VOICES; ++i) {
    MlaPcmVoice *v = &m->voices[i];
    if (v->handle != handle || !handle) continue;
    if (!fade_ms) memset(v, 0, sizeof(*v));
    else if (!v->release) v->release = v->release_total = fade_ms > 100u ? MLA_PCM_RELEASE : fade_ms * 48u;
    return 0;
  }
  return 0; /* Already completed owned IDs are harmless; never native handles. */
}
static inline uint32_t mla_pcm_active(const MlaPcmMixer *m) {
  uint32_t active = 0;
  for (uint32_t i = 0; i < MLA_PCM_VOICES; ++i) active += !!m->voices[i].handle;
  return active;
}
static inline int16_t mla_pcm_s16(const uint8_t *p) {
  const uint32_t raw = (uint32_t)p[0] | (uint32_t)p[1] << 8;
  return (int16_t)(raw < 32768u ? (int32_t)raw : (int32_t)raw - 65536);
}
static inline void mla_pcm_mix(MlaPcmMixer *m, int16_t *output, uint32_t frames, uint32_t watch) {
  if (!m || !m->bank || !output || !frames || frames > 8192u) return;
  if (!watch) for (uint32_t i = 0; i < MLA_PCM_VOICES; ++i)
    if (m->voices[i].handle && !m->voices[i].release)
      mla_pcm_stop(m, m->voices[i].handle, 100u);
  if (!watch && m->native_gain == MLA_PCM_UNITY && !mla_pcm_active(m)) return;
  const uint32_t target = watch ? MLA_PCM_WATCH_NATIVE_GAIN : MLA_PCM_UNITY;
  for (uint32_t f = 0; f < frames; ++f) {
    if (m->native_gain < target) m->native_gain += target - m->native_gain > 6u ? 6u : target - m->native_gain;
    else if (m->native_gain > target) m->native_gain -= m->native_gain - target > 6u ? 6u : m->native_gain - target;
    int32_t sample[2] = {
      (int32_t)((int64_t)output[f * 2u] * m->native_gain / MLA_PCM_UNITY),
      (int32_t)((int64_t)output[f * 2u + 1u] * m->native_gain / MLA_PCM_UNITY)};
    for (uint32_t i = 0; i < MLA_PCM_VOICES; ++i) {
      MlaPcmVoice *v = &m->voices[i];
      if (!v->handle) continue;
      const MlaPcmClip c = mla_pcm_clips[v->clip];
      if (v->position >= c.frames) {
        if (v->clip == MLA_BED && !v->release) v->position = 0;
        else { memset(v, 0, sizeof(*v)); continue; }
      }
      uint32_t gain = MLA_PCM_UNITY;
      if (v->attack) gain = (MLA_PCM_ATTACK - v->attack--) * MLA_PCM_UNITY / MLA_PCM_ATTACK;
      if (v->release) gain = gain * v->release / v->release_total;
      const uint8_t *pcm = m->bank + c.wave_offset + 44u + v->position * 4u;
      sample[0] += (int32_t)((int64_t)mla_pcm_s16(pcm) * gain / MLA_PCM_UNITY);
      sample[1] += (int32_t)((int64_t)mla_pcm_s16(pcm + 2) * gain / MLA_PCM_UNITY);
      ++v->position;
      ++m->source_frames[v->clip];
      if (v->release && !--v->release) memset(v, 0, sizeof(*v));
    }
    for (uint32_t ch = 0; ch < 2; ++ch) {
      int32_t s = sample[ch];
      if (s > 32767) s = 32767;
      else if (s < -32768) s = -32768;
      output[f * 2u + ch] = (int16_t)s;
      const uint32_t magnitude = (uint32_t)(s < 0 ? -s : s);
      m->nonzero_samples += !!magnitude;
      if (magnitude > m->peak) m->peak = magnitude;
    }
  }
  m->mixed_frames += frames;
}
#endif

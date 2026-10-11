#ifndef PESNX_STADIUM_ENVIRONMENT_H
#define PESNX_STADIUM_ENVIRONMENT_H
#include <stdint.h>
#include "match_environment.h"

/* Zero is the accepted Fine/Summer/Normal/Normal presentation. Unknown
 * imported settings use that baseline rather than amplifying shader inputs. */
static inline uint32_t stadium_environment_key(uint32_t weather, uint32_t season,
                                               uint32_t turf, uint32_t condition) {
  if (weather >= NX_WEATHER_COUNT) weather = 0;
  const uint32_t rain = weather == NX_WEATHER_RAIN;
  if (weather >= NX_WEATHER_RAIN) condition = 2;
  weather = weather != NX_WEATHER_FINE;
  if (season > 1u) season = 0;
  if (turf > 2u) turf = 1;
  if (condition > 2u) condition = 1;
  return weather | (season << 1) | (turf << 2) | (condition << 4) | (rain << 6);
}
static inline void stadium_environment_uniform(uint32_t key, float out[4]) {
  /* x: 0 Fine, 1 Cloudy, 2 Rainy. Lighting clamps cloud to one. */
  out[0] = (float)((key & 1u) + ((key >> 6) & 1u));
  out[1] = (float)((key >> 1) & 1u);
  out[2] = (float)((key >> 2) & 3u) - 1.0f;
  out[3] = (float)((key >> 4) & 3u) - 1.0f;
}

/* These factors depend only on the selected climate and Day receiver gate.
 * Calculate when a program's settings change, not at every shaded pixel.
 * Three vec4s hold direct/ambient RGB, rain RGB and the turf scalars. */
static inline void stadium_environment_light_uniform(const float climate[4],
                                                      int day, float out[12]) {
  const float winter = day ? climate[1] : 0.0f;
  const int rain = climate[0] > 1.5f;
  float cloud = day ? (climate[0] < 1.0f ? climate[0] : 1.0f) : 0.0f;
  if (rain) cloud *= 1.0f - 0.92f * climate[1];
  const float season[3] = {1.0f - 0.07f * winter,
                          1.0f - 0.025f * winter, 1.0f + 0.05f * winter};
  const float cool[3] = {day ? 1.0f : 0.97f, day ? 1.0f : 1.02f,
                        day ? 1.0f : 1.07f};
  float rain_scale[3];
  for (unsigned i = 0; i < 3; ++i) {
    rain_scale[i] = rain ? 0.84f + (cool[i] - 0.84f) * climate[1] : 1.0f;
    const float scale = season[i] * rain_scale[i];
    out[i] = scale * (1.0f - 0.38f * cloud);
    out[4 + i] = scale * (1.0f + 0.10f * cloud);
  }
  out[3] = rain_scale[0];
  out[7] = rain_scale[1];
  out[8] = rain_scale[2];
  out[9] = 0.16f + 0.055f * climate[2];
  const float wet = climate[3];
  out[10] = 1.0f - wet * (wet < 0.0f ? 0.025f : 0.08f);
  out[11] = 0.025f + wet * (wet < 0.0f ? 0.015f : 0.065f);
}
#endif

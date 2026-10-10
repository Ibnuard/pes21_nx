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
#endif

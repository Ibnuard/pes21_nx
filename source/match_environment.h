#ifndef PESNX_MATCH_ENVIRONMENT_H
#define PESNX_MATCH_ENVIRONMENT_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>

enum { NX_WEATHER_FINE, NX_WEATHER_CLOUDY, NX_WEATHER_RAIN, NX_WEATHER_COUNT };
typedef struct {
  uint32_t weather, season, turf, condition, change, raining, wet;
} NxMatchEnvironment;

static inline const char *nx_weather_label(uint32_t choice) {
  static const char *const labels[] = {"FINE", "CLOUDY", "RAINY"};
  return labels[choice < NX_WEATHER_COUNT ? choice : NX_WEATHER_FINE];
}
static inline NxMatchEnvironment nx_match_environment(
    uint32_t choice, uint32_t season, uint32_t turf, uint32_t condition) {
  NxMatchEnvironment e = {0};
  if (choice >= NX_WEATHER_COUNT) choice = NX_WEATHER_FINE;
  e.season = season <= 1u ? season : 0u;
  e.turf = turf <= 2u ? turf : 1u;
  e.condition = condition <= 2u ? condition : 1u;
  /* common::WeatherType is Fine/Rain/Snow, not the UI's Fine/Cloudy.
   * Overcast is a lighting choice. Precipitation makes the ground wet;
   * Winter without precipitation retains the selected surface condition. */
  e.weather = choice == NX_WEATHER_RAIN ? 1u : 0u;
  e.raining = e.weather != 0u;
  if (e.raining) e.condition = 2u;
  e.wet = e.condition == 2u;
  e.change = e.raining ? 2u : 0u; /* native ALWAYS / NONE */
  return e;
}

/* common::InitParam POD, verified against native SetStadiumInitParam.
 * Preserve every unrelated field, including stadium/banner/team data. */
static inline int nx_environment_write_snapshot(void *snapshot, size_t size,
                                                NxMatchEnvironment e) {
  if (!snapshot || size != 0xa8u) return 0;
  unsigned char *p = (unsigned char *)snapshot;
  memcpy(p + 0x08, &e.weather, 4);
  memcpy(p + 0x0c, &e.season, 4);
  memcpy(p + 0x78, &e.turf, 4);
  memcpy(p + 0x7c, &e.condition, 4);
  return 1;
}
#endif

#ifndef PES21_COMPETITION_SEED_H
#define PES21_COMPETITION_SEED_H
#include <stdint.h>
#include <time.h>

/* Sample only when creating a competition, never while loading or rendering.
 * The persisted seed keeps simulation/reloads reproducible. Clock + serial
 * also distinguishes consecutive creations within one wall-clock second. */
static inline uint32_t competition_new_seed(uint32_t salt) {
  static uint32_t serial, previous;
  const uint64_t now = (uint64_t)time(NULL);
  uint32_t seed = salt ^ (uint32_t)now ^ (uint32_t)(now >> 32) ^
      (uint32_t)clock() ^ (++serial * 0x9e3779b9u);
  seed = (seed ^ (seed >> 16)) * 0x7feb352du;
  seed = (seed ^ (seed >> 15)) * 0x846ca68bu;
  seed ^= seed >> 16;
  if (!seed || seed == previous) seed = previous + 1u;
  previous = seed ? seed : 1u;
  return previous;
}
#endif

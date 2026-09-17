#ifndef PES_PERF_MATCH_POLICY_H
#define PES_PERF_MATCH_POLICY_H
#include <stdint.h>
#include <string.h>

// Histogram upper bounds, not exact percentiles. No allocation/sorting in-game.
typedef struct {
  uint64_t frames, ns, swap_ns, max_ns, buckets[7];
  uint64_t draws, vertices, driver_ns, depth_draws, depth_vertices;
  uint64_t roof_seen, roof_suppressed;
  unsigned depth_width, depth_height;
} PerfMatchWindow;
static inline void perf_match_sample(PerfMatchWindow *w, uint64_t ns, uint64_t swap) {
  static const uint64_t bounds[] = {16667000, 33334000, 50000000,
                                  66667000, 100000000, 200000000};
  unsigned bucket = 0;
  while (bucket < 6 && ns > bounds[bucket]) ++bucket;
  ++w->buckets[bucket];
  ++w->frames;
  w->ns += ns;
  w->swap_ns += swap;
  if (ns > w->max_ns) w->max_ns = ns;
}
static inline unsigned perf_match_p95_upper_ms(const PerfMatchWindow *w) {
  static const unsigned upper[] = {17, 34, 50, 67, 100, 200, 0};
  uint64_t sum = 0, target = (w->frames * 95u + 99u) / 100u;
  if (!target) return 0;
  for (unsigned i=0; i<7; ++i) {
    sum += w->buckets[i];
    if (sum >= target) return upper[i]; // zero means >200 ms
  }
  return 0;
}
#endif

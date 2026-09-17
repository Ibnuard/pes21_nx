#ifndef PES_PERF_MATCH_H
#define PES_PERF_MATCH_H
#include <stdint.h>
#ifdef PERF_TRACE
void perf_match_draw(uint64_t vertices, uint64_t driver_ns);
void perf_match_target(int depth_only, unsigned width, unsigned height);
void perf_match_roof(int suppressed);
void perf_match_frame(uint64_t begin_ns, uint64_t end_ns, uint64_t key);
#endif
#endif

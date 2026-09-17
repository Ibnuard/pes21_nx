#include "perf_match.h"
#ifdef PERF_TRACE
#include <stdio.h>
#include "perf_match_policy.h"
#include "perf_trace.h"

// Per render thread. Target classification is supplied at framebuffer exit
// using attachment queries already required by the High compositor. There is
// no GPU readback, glFinish, timer query, or extra per-draw GL query.
static __thread struct {
  uint64_t draws, vertices, driver_ns;
} target;
static __thread PerfMatchWindow pending, window;
static __thread uint64_t previous_begin, window_key;
static uint64_t roof_seen, roof_suppressed;

void perf_match_draw(uint64_t vertices, uint64_t driver_ns) {
  ++target.draws;
  target.vertices += vertices;
  target.driver_ns += driver_ns;
}
void perf_match_target(int depth_only, unsigned width, unsigned height) {
  pending.draws += target.draws;
  pending.vertices += target.vertices;
  pending.driver_ns += target.driver_ns;
  if (depth_only && target.draws) {
    pending.depth_draws += target.draws;
    pending.depth_vertices += target.vertices;
    if ((uint64_t)width*height > (uint64_t)pending.depth_width*pending.depth_height) {
      pending.depth_width=width; pending.depth_height=height;
    }
  }
  memset(&target,0,sizeof(target));
}
void perf_match_roof(int suppressed) {
  __atomic_fetch_add(&roof_seen,1,__ATOMIC_RELAXED);
  if (suppressed) __atomic_fetch_add(&roof_suppressed,1,__ATOMIC_RELAXED);
}
static void perf_match_report(const char *reason) {
  if (!window.frames) return;
  char line[1024];
  const uint32_t s=(uint32_t)window_key;
  const double n=(double)window.frames;
  snprintf(line,sizeof(line),
      "[STADIUMPERF] v=6 reason=%s match=%llu day=%u roof=%u cam=%u footballnx=%u "
      "quality=%u fps_mode=%u paused=%u camera_recent=%u frames=%llu "
      "fps=%.2f frame_ms=%.2f p95_upper_ms=%u max_ms=%.2f swap_ms=%.2f "
      "draws=%.1f vertices=%.0f draw_cpu_ms=%.2f depth_draws=%.1f depth_vertices=%.0f "
      "depth_vp=%ux%u roof_seen=%llu roof_suppressed=%llu\n",
      reason,(unsigned long long)(window_key>>32),s&1u,(s>>1)&1u,(s>>2)&31u,
      (s>>7)&1u,(s>>8)&15u,(s>>12)&1u,(s>>13)&1u,(s>>14)&1u,
      (unsigned long long)window.frames, window.ns ? n*1e9/window.ns : 0,
      window.ns/n/1e6,perf_match_p95_upper_ms(&window),window.max_ns/1e6,
      window.swap_ns/n/1e6,window.draws/n,window.vertices/n,window.driver_ns/n/1e6,
      window.depth_draws/n,window.depth_vertices/n,window.depth_width,window.depth_height,
      (unsigned long long)window.roof_seen,
      (unsigned long long)window.roof_suppressed);
  perf_trace_log_line(line);
}
void perf_match_frame(uint64_t begin_ns, uint64_t end_ns, uint64_t key) {
  // The final/default FBO may not transition before SwapBuffers.
  perf_match_target(0,0,0);
  pending.roof_seen = __atomic_exchange_n(&roof_seen,0,__ATOMIC_RELAXED);
  pending.roof_suppressed = __atomic_exchange_n(&roof_suppressed,0,__ATOMIC_RELAXED);
  if (!previous_begin || key != window_key) {
    perf_match_report("state-change");
    memset(&window,0,sizeof(window));
    memset(&pending,0,sizeof(pending));
    window_key=key;
    previous_begin=begin_ns;
    return; // Never attribute a transition frame to either lighting state.
  }
  perf_match_sample(&window,begin_ns-previous_begin,end_ns-begin_ns);
  previous_begin=begin_ns;
  window.draws+=pending.draws; window.vertices+=pending.vertices;
  window.driver_ns+=pending.driver_ns; window.depth_draws+=pending.depth_draws;
  window.depth_vertices+=pending.depth_vertices;
  window.roof_seen+=pending.roof_seen; window.roof_suppressed+=pending.roof_suppressed;
  if ((uint64_t)pending.depth_width*pending.depth_height >
      (uint64_t)window.depth_width*window.depth_height) {
    window.depth_width=pending.depth_width; window.depth_height=pending.depth_height;
  }
  memset(&pending,0,sizeof(pending));
  if (window.ns >= 5000000000ULL) {
    perf_match_report("window");
    memset(&window,0,sizeof(window));
  }
}
#endif

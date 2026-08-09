#ifndef PES21_NX_PERF_TRACE_H
#define PES21_NX_PERF_TRACE_H

#include <stdint.h>

enum PerfTraceKind {
  PERF_TRACE_NANOSLEEP = 1,
  PERF_TRACE_USLEEP,
  PERF_TRACE_SLEEP,
  PERF_TRACE_CLOCK_NANOSLEEP,
  PERF_TRACE_COND_WAIT,
  PERF_TRACE_COND_TIMEDWAIT,
  PERF_TRACE_LOOPER,
  PERF_TRACE_FRAME,
  PERF_TRACE_SWAP,
};

#ifdef PERF_TRACE
uint64_t perf_trace_now_ns(void);
void perf_trace_record(enum PerfTraceKind kind, const void *caller,
                       uint64_t requested_ns, uint64_t elapsed_ns, int result);
void perf_trace_report(void);
#else
static inline uint64_t perf_trace_now_ns(void) { return 0; }
static inline void perf_trace_record(enum PerfTraceKind kind,
                                     const void *caller,
                                     uint64_t requested_ns,
                                     uint64_t elapsed_ns, int result) {
  (void)kind;
  (void)caller;
  (void)requested_ns;
  (void)elapsed_ns;
  (void)result;
}
static inline void perf_trace_report(void) {}
#endif

#endif

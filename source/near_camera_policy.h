#ifndef PES_NEAR_CAMERA_POLICY_H
#define PES_NEAR_CAMERA_POLICY_H
#include <math.h>
#include <stdint.h>
#include <string.h>

#define NX_NEAR_ZONES 10u
#define NX_NEAR_BINS 12u
static const uint32_t nx_near_bin_us[NX_NEAR_BINS]={
  10000,14000,16667,18000,20000,25000,30000,35000,50000,100000,250000,1000000
};
/* Native Y-up camera target, not a guessed ball pointer. +Z is the normal
 * near touchline; mirrored cameras invert it. 0 also covers invalid samples. */
static inline unsigned nx_near_zone(const float *p) {
  if (!p) return 0;
  for (unsigned i=0;i<6;++i) if (!isfinite(p[i])) return 0;
  if (fabsf(p[0])>65 || fabsf(p[2])>45 || fabsf(p[5])<40) return 0;
  const unsigned x=p[0]<-25?0:p[0]>25?2:1;
  const float z=p[5]<0?-p[2]:p[2];
  const unsigned row=z<-10?0:z>10?2:1;
  return 1+row*3+x;
}
typedef struct {
  uint64_t draws, elements, draw_ns, first_draw, uploads, bytes, upload_ns,
           maps, mapped_bytes, flushes;
  uint64_t map_calls, map_failures, unmap_calls, unmap_failures,
           error_checks, errors, first_error;
  uint64_t blend_requests, blend_skipped;
} NxNearFrame;
typedef struct {
  uint64_t frames, interval_ns, worst_ns, over20, over30, swap_ns, span_ns;
  NxNearFrame work;
  uint64_t gpu_samples, gpu_ns, gpu_worst_ns;
  uint64_t intervals[NX_NEAR_BINS];
} NxNearWindow;
static inline void nx_near_accumulate(NxNearWindow *w,const NxNearFrame *f,
    uint64_t interval,uint64_t swap,uint64_t span) {
  ++w->frames; w->interval_ns+=interval; w->swap_ns+=swap; w->span_ns+=span;
  if (interval>w->worst_ns) w->worst_ns=interval;
  w->over20+=interval>20000000u; w->over30+=interval>30000000u;
  unsigned bin=0;
  while(bin<NX_NEAR_BINS-1 && interval>(uint64_t)nx_near_bin_us[bin]*1000u) ++bin;
  ++w->intervals[bin];
#define ADD(field) w->work.field+=f->field
  ADD(draws); ADD(elements); ADD(draw_ns); ADD(uploads); ADD(bytes);
  ADD(upload_ns); ADD(maps); ADD(mapped_bytes); ADD(flushes);
  ADD(map_calls); ADD(map_failures); ADD(unmap_calls); ADD(unmap_failures);
  ADD(error_checks); ADD(errors);
  ADD(blend_requests); ADD(blend_skipped);
  if (!w->work.first_error) w->work.first_error=f->first_error;
#undef ADD
}
/* Quantile bucket upper bounds, not exact per-frame percentiles. The last
 * bucket uses the observed worst so even >1s stalls are not underreported. */
static inline uint64_t nx_near_quantile_upper(const NxNearWindow *w,unsigned percent) {
  if (!w->frames || percent>100u || !percent) return 0;
  const uint64_t rank=w->frames/100u*percent+(w->frames%100u*percent+99u)/100u;
  uint64_t count=0;
  for (unsigned i=0;i<NX_NEAR_BINS;++i) {
    count+=w->intervals[i];
    if (count>=rank) return i==NX_NEAR_BINS-1 ? (w->worst_ns+999u)/1000u : nx_near_bin_us[i];
  }
  return 0;
}
#endif

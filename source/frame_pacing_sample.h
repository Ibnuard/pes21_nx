#ifndef PESNX_FRAME_PACING_SAMPLE_H
#define PESNX_FRAME_PACING_SAMPLE_H
#include <stdint.h>
typedef struct {
  uint64_t previous, total, worst;
  uint32_t frames, over20, over30, session, weather, season;
} NxFramePacingSample;
/* Presentation intervals, NOT GPU time or simulation FPS. No I/O in play. */
static inline void nx_frame_pacing_add(NxFramePacingSample *s,uint64_t now) {
  if(s->previous && now>s->previous) {
    uint64_t dt=now-s->previous;
    s->total+=dt;++s->frames;
    if(dt>s->worst)s->worst=dt;
    s->over20+=dt>20000000u;s->over30+=dt>30000000u;
  }
  s->previous=now;
}
#endif

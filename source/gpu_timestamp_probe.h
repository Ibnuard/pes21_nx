#ifndef PESNX_GPU_TIMESTAMP_PROBE_H
#define PESNX_GPU_TIMESTAMP_PROBE_H
#include <stdint.h>
#include <string.h>

/* Diagnostic only. Timestamp pairs do not nest the game's elapsed queries.
 * Results are read only after BOTH availability flags are true. A full ring
 * skips a sample; it never waits for the GPU or substitutes a CPU duration. */
#define NX_GPU_SLOTS 4u
#define NX_GPU_PERIOD 30u
typedef struct {
  void (*counter)(unsigned, unsigned);
  void (*available)(unsigned, unsigned, unsigned *);
  void (*result)(unsigned, unsigned, uint64_t *);
} NxGpuApi;
typedef struct {
  unsigned query[2], pending;
  uint64_t tag;
} NxGpuSample;
typedef struct {
  NxGpuSample samples[NX_GPU_SLOTS];
  unsigned frame, active, enabled;
} NxGpuProbe;

static inline void nx_gpu_begin(NxGpuProbe *p,const NxGpuApi *api,uint64_t tag) {
  if (!p->enabled || p->active || p->frame++ % NX_GPU_PERIOD) return;
  for (unsigned i=0;i<NX_GPU_SLOTS;++i) if (!p->samples[i].pending) {
    p->active=i+1; p->samples[i].tag=tag;
    api->counter(p->samples[i].query[0],0x8e28u); /* GL_TIMESTAMP */
    return;
  }
}
static inline void nx_gpu_end(NxGpuProbe *p,const NxGpuApi *api) {
  if (!p->active) return;
  NxGpuSample *s=&p->samples[p->active-1];
  api->counter(s->query[1],0x8e28u); s->pending=1; p->active=0;
}
static inline int nx_gpu_poll(NxGpuProbe *p,const NxGpuApi *api,unsigned i,
                               uint64_t *tag,uint64_t *ns) {
  NxGpuSample *s=&p->samples[i];
  if (!s->pending) return 0;
  unsigned a=0,b=0;
  api->available(s->query[0],0x8867u,&a); /* GL_QUERY_RESULT_AVAILABLE */
  api->available(s->query[1],0x8867u,&b);
  if (!a || !b) return 0;
  uint64_t begin=0,end=0;
  api->result(s->query[0],0x8866u,&begin); /* GL_QUERY_RESULT */
  api->result(s->query[1],0x8866u,&end); s->pending=0;
  if (end<begin) return 0;
  *tag=s->tag; *ns=end-begin; return 1;
}
static inline void nx_gpu_discard(NxGpuProbe *p) {
  for (unsigned i=0;i<NX_GPU_SLOTS;++i) p->samples[i].pending=0;
  p->active=0;
}
#endif

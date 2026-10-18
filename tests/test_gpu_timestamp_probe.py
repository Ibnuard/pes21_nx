"""Nonblocking GPU samples must never read an unavailable result."""
from pathlib import Path
import shutil
import unittest
from test_result_flow import build_and_run

ROOT=Path(__file__).resolve().parents[1]


class GpuProbeTests(unittest.TestCase):
    def test_async_ring_saturation_disjoint_and_clock_reversal(self):
        cc=shutil.which('gcc')
        if not cc: self.skipTest('host gcc unavailable')
        build_and_run(cc,'#include "'+(ROOT/'source/gpu_timestamp_probe.h').as_posix()+'"\n'+r'''
#include <assert.h>
static unsigned counters,reads,ready[8];
static uint64_t values[8];
static void counter(unsigned id,unsigned kind) {assert(id && kind==0x8e28); ++counters;}
static void available(unsigned id,unsigned kind,unsigned *p) {assert(kind==0x8867);*p=ready[id-1];}
static void result(unsigned id,unsigned kind,uint64_t *p) {
  assert(kind==0x8866 && ready[id-1]); ++reads; *p=values[id-1];
}
int main(void) {
  NxGpuApi api={counter,available,result}; NxGpuProbe p={0}; uint64_t tag=0,ns=0;
  for(unsigned i=0;i<NX_GPU_SLOTS;++i) {
    p.samples[i].query[0]=i*2+1; p.samples[i].query[1]=i*2+2;
  }
  nx_gpu_begin(&p,&api,99); assert(!counters); p.enabled=1;
  for(unsigned i=0;i<120;++i) {nx_gpu_begin(&p,&api,100+i);nx_gpu_end(&p,&api);}
  assert(counters==8); // four pairs, one per thirty rendered frames
  for(unsigned i=0;i<120;++i) {nx_gpu_begin(&p,&api,900+i);nx_gpu_end(&p,&api);}
  assert(counters==8); // GPU behind: skip samples instead of waiting/reusing
  ready[0]=1; values[0]=1000;
  assert(!nx_gpu_poll(&p,&api,0,&tag,&ns) && !reads);
  ready[1]=1; values[1]=17000;
  assert(nx_gpu_poll(&p,&api,0,&tag,&ns) && tag==100 && ns==16000 && reads==2);
  assert(!nx_gpu_poll(&p,&api,0,&tag,&ns));
  ready[2]=ready[3]=1;values[2]=2000;values[3]=1000;
  assert(!nx_gpu_poll(&p,&api,1,&tag,&ns)); // invalid/reversed GPU clock
  nx_gpu_discard(&p);
  for(unsigned i=0;i<4;++i) assert(!nx_gpu_poll(&p,&api,i,&tag,&ns));
  unsigned before=counters; p.frame=0;
  nx_gpu_begin(&p,&api,777); nx_gpu_begin(&p,&api,888);nx_gpu_end(&p,&api);nx_gpu_end(&p,&api);
  assert(counters==before+2 && p.samples[0].tag==777);
}
''')

    def test_gpu_and_cpu_reports_remain_distinct_and_production_is_gated(self):
        source=(ROOT/'source/imports.c').read_text()
        self.assertIn('#ifdef NEAR_CAMERA_TRACE\n#include "gpu_timestamp_probe.inc"',source)
        probe=(ROOT/'source/gpu_timestamp_probe.inc').read_text()
        for forbidden in ('glFinish(', 'glReadPixels(', 'glFlush(', 'fopen(', 'malloc('):
            self.assertNotIn(forbidden,probe)
        self.assertIn('GL_EXT_disjoint_timer_query',probe)
        self.assertIn('GL_GPU_DISJOINT_EXT',probe)
        self.assertIn('nx_gpu_discard(p)',probe)
        self.assertIn('nx_gpu_check_owner',probe)

"""Low-overhead profiling: window math, state separation and release isolation."""
from pathlib import Path
import shutil
import unittest
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]

class StadiumPerfTests(unittest.TestCase):
    def run_c(self, body):
        cc = shutil.which('gcc')
        if not cc: self.skipTest('gcc unavailable')
        build_and_run(cc, '#include <assert.h>\n' + body)

    def test_window_histogram(self):
        self.run_c(f'#include "{(ROOT/"source/perf_match_policy.h").as_posix()}"\n' + r'''
int main(void) {
  PerfMatchWindow w={0};
  for(unsigned i=0;i<95;++i) perf_match_sample(&w,16666667,1000000);
  for(unsigned i=0;i<5;++i) perf_match_sample(&w,90000000,3000000);
  assert(w.frames==100 && w.max_ns==90000000 && w.swap_ns==110000000);
  assert(perf_match_p95_upper_ms(&w)==17);
  perf_match_sample(&w,250000000,1000000);
  assert(perf_match_p95_upper_ms(&w)==100);
  memset(&w,0,sizeof(w));
  assert(!perf_match_p95_upper_ms(&w));
  perf_match_sample(&w,250000000,1);
  assert(!perf_match_p95_upper_ms(&w)); // explicitly >200 ms, not zero latency
}
''')

    def test_render_counts_and_state_change_never_mix_day_night(self):
        self.run_c(r'''
#define PERF_TRACE 1
#include <stdio.h>
#include <string.h>
static char line[2048]; static unsigned reports;
void perf_trace_log_line(const char *s) {snprintf(line,sizeof(line),"%s",s);++reports;}
''' + f'#include "{(ROOT/"source/perf_match.c").as_posix()}"\n' + r'''
int main(void) {
  const uint64_t day=(1ULL<<32)|1u|(12u<<2)|(2u<<8)|(1u<<14);
  const uint64_t night=day&~1ULL;
  uint64_t t=1000000000;
  perf_match_frame(t,t+1000000,day); // transition sample excluded
  for(unsigned i=0;i<50;++i) {
    perf_match_draw(300,5000); perf_match_target(1,4096,2048);
    perf_match_draw(6,2000); // final default framebuffer accounted at swap
    perf_match_roof(1);
    t+=100000000; perf_match_frame(t,t+2000000,day);
  }
  assert(reports==1 && strstr(line,"fps=10.00") && strstr(line,"day=1 roof=0 cam=12"));
  assert(strstr(line,"draws=2.0 vertices=306") && strstr(line,"depth_draws=1.0"));
  assert(strstr(line,"depth_vp=4096x2048 roof_seen=50 roof_suppressed=50"));
  t+=100000000; perf_match_draw(200,4); perf_match_frame(t,t+100,day);
  perf_match_roof(0); // transition frame must not contaminate previous window
  t+=100000000; perf_match_frame(t,t+100,night);
  assert(reports==2 && strstr(line,"reason=state-change") && strstr(line,"day=1"));
  assert(strstr(line,"roof_seen=0 roof_suppressed=0"));
  assert(window.frames==0 && window_key==night && pending.draws==0);
  t+=100000000; perf_match_frame(t,t+100,night);
  assert(window.frames==1 && window.draws==0);
}
''')

    def test_no_extra_gpu_queries_or_readback_and_all_draw_routes_counted(self):
        profiler = (ROOT/'source/perf_match.c').read_text()
        for forbidden in ('glReadPixels(', 'glFinish(', 'glGetQueryObject', 'glGetIntegerv('):
            self.assertNotIn(forbidden, profiler)
        imports = (ROOT/'source/imports.c').read_text()
        self.assertEqual(imports.count('perf_match_draw('),4)
        self.assertIn('color_type == GL_NONE && depth != GL_NONE', imports)
        self.assertIn('perf_match_frame(swap_begin_ns, swap_end_ns, match_perf_key)', imports)
        logger = (ROOT/'source/perf_trace.c').read_text()
        self.assertIn('fopen("perf.log", "w")', logger)
        self.assertIn('5000000000ULL', logger)
        self.assertIn('mutexLock(&trace_file_mutex)', logger)

    def test_profiling_translation_unit_is_empty_without_opt_in(self):
        self.run_c(f'#include "{(ROOT/"source/perf_match.c").as_posix()}"\nint main(void){{return 0;}}')

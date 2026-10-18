"""Exercise the production upload budget and quiet per-region trace."""
from pathlib import Path
import shutil
import unittest
from test_result_flow import build_and_run
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


class NearCameraTests(unittest.TestCase):
    def run_c(self, body):
        compiler = shutil.which('gcc')
        if not compiler:
            self.skipTest('gcc required for the C policy harness')
        build_and_run(compiler, body)

    def test_loading_flush_bound_live_frames_and_context_isolation(self):
        self.run_c('#include <assert.h>\n#include "' +
                   (ROOT / 'source/gl_upload_budget.h').as_posix() + '"\n' + r'''
int main(void) {
  NxUploadBudget b={0}; unsigned flushed=0;
  for(unsigned i=0;i<2048;++i) flushed+=nx_upload_due(&b,1);
  assert(flushed==4); // unswapped loading still submits every 512 uploads
  for(unsigned frame=0;frame<600;++frame) {
    for(unsigned i=0;i<120;++i) assert(!nx_upload_due(&b,1));
    nx_upload_presented(&b,1,1);
  } // old lifetime counter forces 140 additional flushes in these frames
  for(unsigned i=0;i<511;++i) assert(!nx_upload_due(&b,2));
  nx_upload_presented(&b,1,1); // swap on 1 cannot consume context 2's work
  assert(nx_upload_due(&b,2));
  for(unsigned i=0;i<511;++i) assert(!nx_upload_due(&b,1));
  nx_upload_presented(&b,1,0); // failed presentation is not a submission
  assert(nx_upload_due(&b,1));
  assert(!nx_upload_due(&b,1)); nx_upload_forget(&b,1);
  for(unsigned i=0;i<511;++i) assert(!nx_upload_due(&b,1));
  assert(nx_upload_due(&b,1)); // reused context starts with an empty budget
  for(unsigned i=3;i<9;++i) assert(!nx_upload_due(&b,i));
  assert(nx_upload_due(&b,99)); // table exhaustion safely submits
}
''')

    def test_camera_geometry_and_mirrored_view(self):
        self.run_c('#include <assert.h>\n#include "' +
                   (ROOT / 'source/near_camera_policy.h').as_posix() + '"\n' + r'''
int main(void) {
  float p[6]={0,0,24,0,20,55};
  assert(nx_near_zone(p)==8); p[0]=-40; assert(nx_near_zone(p)==7);
  p[0]=40; assert(nx_near_zone(p)==9); p[2]=-24; assert(nx_near_zone(p)==3);
  p[5]=-55; assert(nx_near_zone(p)==9); p[0]=p[2]=0; assert(nx_near_zone(p)==5);
  p[5]=0; assert(nx_near_zone(p)==0); p[5]=55; p[2]=NAN; assert(!nx_near_zone(p));
  p[2]=0; p[0]=100; assert(!nx_near_zone(p)); assert(!nx_near_zone(0));
}
''')

    def test_frame_time_histogram_quantiles_and_long_stall(self):
        self.run_c('#include <assert.h>\n#include "' +
                   (ROOT / 'source/near_camera_policy.h').as_posix() + '"\n' + r'''
int main(void) {
  NxNearWindow w={0};NxNearFrame f={0};
  assert(!nx_near_quantile_upper(&w,95));
  for(unsigned i=0;i<95;++i)nx_near_accumulate(&w,&f,16666667,0,0);
  for(unsigned i=0;i<4;++i)nx_near_accumulate(&w,&f,25000000,0,0);
  nx_near_accumulate(&w,&f,1500000000,0,0);
  assert(w.frames==100 && w.over20==5 && w.over30==1);
  assert(nx_near_quantile_upper(&w,50)==16667);
  assert(nx_near_quantile_upper(&w,95)==16667);
  assert(nx_near_quantile_upper(&w,99)==25000);
  assert(nx_near_quantile_upper(&w,100)==1500000);
  assert(!nx_near_quantile_upper(&w,0) && !nx_near_quantile_upper(&w,101));
}
''')

    def test_no_live_writes_zone_state_transitions_uploads_and_stale_camera(self):
        self.run_c(r'''
#define NEAR_CAMERA_TRACE 1
#define PESNX_NEAR_HOST_TEST 1
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned writes;
static char reports[20000];
static void scene_runtime_note(const char *area,const char *s) {
  assert(!strcmp(area,"near-camera")); ++writes; strcat(reports,s); strcat(reports,"\n");
}
''' + '#include "' + (ROOT / 'source/near_camera_trace.c').as_posix() + '"\n' + r'''
int main(void) {
  NxNearContext c={.live=1,.session=1,.day=1,.quality=2};
  float p[6]={0,0,20,0,20,55}; uint64_t t=1000000000;
  nx_near_camera(p,6,t); nx_near_swap(t,t+1000,1024,576,1,nx_near_view_sample(),&c);
  for(unsigned i=0;i<10;++i) {
    t+=25000000; nx_near_camera(p,6,t);
    nx_near_draw(t-5000000,t-4500000,600);
    nx_near_upload(100000,8192,0); nx_near_upload(50000,4096,1);
    nx_near_map_result(i!=2); nx_near_unmap_result(i!=3);
    nx_near_error_result(i==4?1282:0);
    nx_near_blend(0);nx_near_blend(1);nx_near_blend(1);
    if(i==5) nx_near_flush();
    nx_near_swap(t,t+2000000,1024,576,1,nx_near_view_sample(),&c);
  }
  assert(!writes && near_trace.zones[8].frames==10);
  nx_near_gpu_support(1);nx_near_gpu(9000000,nx_near_view_sample());
  assert(near_trace.zones[8].gpu_samples==1 && near_trace.zones[8].gpu_ns==9000000);
  nx_near_gpu(1000,(134u<<8)|8u); // another camera cannot contaminate this window
  assert(near_trace.zones[8].gpu_samples==1);
  assert(near_trace.zones[8].work.flushes==1);
  p[2]=-20; t+=16000000; nx_near_camera(p,6,t);
  nx_near_swap(t,t+1,1024,576,1,nx_near_view_sample(),&c); // crossover never contaminates near/far
  assert(!near_trace.zones[2].frames);
  t+=16000000; nx_near_camera(p,6,t); nx_near_swap(t,t+1,1024,576,1,nx_near_view_sample(),&c);
  assert(near_trace.zones[2].frames==1 && !writes);
  c.live=0; nx_near_swap(t+16000000,t+16000001,1024,576,1,nx_near_view_sample(),&c);
  assert(writes==2 && strstr(reports,"zone=near_middle frames=10 avg_us=25000"));
  assert(strstr(reports,"draws_x10=10 submitted_elements=600 draw_cpu_us=500"));
  assert(strstr(reports,"upload_bytes=8192 maps_x10=10 mapped_bytes=4096 upload_cpu_us=150"));
  assert(strstr(reports,"forced_flushes=1") && !near_trace.previous);
  assert(strstr(reports,"gpu_supported=1 gpu_samples=1 gpu_avg_us=9000 gpu_worst_us=9000"));
  assert(strstr(reports,"map_calls=10 map_failures=1 unmap_calls=10 unmap_failures=1"));
  assert(strstr(reports,"gl_error_checks=10 gl_errors=1 first_gl_error=1282"));
  assert(strstr(reports,"blend_requests=30 blend_skipped=20"));
  nx_near_swap(t+20000000,t+20000001,1024,576,1,nx_near_view_sample(),&c); assert(writes==2);
  c.live=1; c.day=0;
  t+=1000000000; nx_near_swap(t,t+1,1024,576,1,nx_near_view_sample(),&c);
  t+=16000000; nx_near_swap(t,t+1,1024,576,1,nx_near_view_sample(),&c);
  assert(near_trace.zones[0].frames==1); // no stale position inheritance
  c.session=2; nx_near_swap(t+16000000,t+16000001,1024,576,1,nx_near_view_sample(),&c);
  assert(!near_trace.zones[0].frames && writes==2); // no live state-change flush
  t+=32000000; nx_near_swap(t,t+1,1024,576,0,nx_near_view_sample(),&c);
  assert(!near_trace.previous);
}
''')

    def test_disabled_trace_and_production_routes(self):
        self.run_c('#include "' + (ROOT / 'source/near_camera_trace.c').as_posix() +
                   '"\nint main(void) {return 0;}')
        imports = (ROOT / 'source/imports.c').read_text()
        self.assertEqual(imports.count('  NX_NEAR_DRAW('), 6)
        self.assertIn('#elif defined(NEAR_CAMERA_TRACE)\n'
                      '  if (name && !strcmp(name, "glDrawArrays")', imports)
        self.assertIn('nx_upload_presented(&gl_upload_budget,submitted_context,result && presented_current)', imports)
        self.assertIn('if (result) {\n    nx_upload_forget', imports)
        code = (ROOT / 'source/near_camera_trace.c').read_text()
        for forbidden in ('fopen(', 'glFinish(', 'glReadPixels(', 'glGet', 'malloc(', 'mutex'):
            self.assertNotIn(forbidden, code)
        self.assertIn('if (!c->live)', code)

    def test_dynamic_measurement_preserves_exact_driver_calls(self):
        imports = (ROOT / 'source/imports.c').read_text()
        wrappers = '\n'.join(function(imports, name) for name in (
            'glDrawArrays_near', 'glDrawElements_near', 'glBufferData_near',
            'glBufferSubData_near', 'glMapBufferRange_near', 'glUnmapBuffer_near'))
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
typedef unsigned GLenum, GLuint, GLbitfield;
typedef int GLint, GLsizei; typedef intptr_t GLintptr, GLsizeiptr;
typedef unsigned char GLboolean;
static unsigned calls, draws, uploads, mapped, total;
static void nx_near_map_result(int success) {assert(success);}
static void nx_near_unmap_result(int success) {assert(success);}
#define NX_NEAR_BEGIN() ((void)0)
#define NX_NEAR_DRAW(n) (++draws,total+=(n))
#define NX_NEAR_UPLOAD(n,m) (++uploads,mapped+=(m))
static void glDrawArrays(GLenum m,GLint f,GLsizei n) {assert(m==4&&f==9&&n==30);++calls;}
static void glDrawElements(GLenum m,GLsizei n,GLenum t,const void *p) {assert(m==4&&n==60&&t==2&&p==(void *)16);++calls;}
static void glBufferData(GLenum t,GLsizeiptr n,const void *p,GLenum u) {assert(t==1&&n==40&&p==(void *)3&&u==7);++calls;}
static void glBufferSubData(GLenum t,GLintptr o,GLsizeiptr n,const void *p) {assert(t==1&&o==8&&n==20&&p==(void *)3);++calls;}
static void *near_map_buffer_range_real(GLenum t,GLintptr o,GLsizeiptr n,GLbitfield a) {assert(t==1&&o==8&&n==20&&a==15);++calls;return (void *)3;}
static GLboolean near_unmap_buffer_real(GLenum t) {assert(t==1);++calls;return 1;}
''' + wrappers + r'''
int main(void) {
 glDrawArrays_near(4,9,30); glDrawElements_near(4,60,2,(void *)16);
 glBufferData_near(1,40,(void *)3,7); glBufferSubData_near(1,8,20,(void *)3);
 assert(glMapBufferRange_near(1,8,20,15)==(void *)3); assert(glUnmapBuffer_near(1)==1);
 assert(calls==6&&draws==2&&total==90&&uploads==4&&mapped==2);
}
''')

    def test_buffer_aliases_preserve_failures_and_never_add_driver_queries(self):
        imports=(ROOT/'source/imports.c').read_text()
        names=('glMapBufferRange_near','glMapBufferRangeEXT_near',
               'glMapBufferOES_near','glUnmapBuffer_near','glUnmapBufferOES_near','glGetError_near')
        wrappers='\n'.join(function(imports,n) for n in names)
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
typedef unsigned GLenum,GLbitfield;
typedef intptr_t GLintptr,GLsizeiptr;
typedef unsigned char GLboolean;
static unsigned calls[6], maps, map_failures, unmaps, unmap_failures, errors;
#define NX_NEAR_BEGIN() ((void)0)
#define NX_NEAR_UPLOAD(n,m) ((void)0)
static void nx_near_map_result(int s) {maps++;map_failures+=!s;}
static void nx_near_unmap_result(int s) {unmaps++;unmap_failures+=!s;}
static void nx_near_error_result(unsigned e) {errors+=e==1282;}
static void *near_map_buffer_range_real(GLenum t,GLintptr o,GLsizeiptr n,GLbitfield a) {
 assert(t==1&&o==8&&n==20&&a==15);calls[0]++;return (void*)3;
}
static void *near_map_buffer_range_ext_real(GLenum t,GLintptr o,GLsizeiptr n,GLbitfield a) {
 assert(t==1&&o==8&&n==20&&a==15);calls[1]++;return NULL;
}
static void *near_map_buffer_oes_real(GLenum t,GLenum a) {
 assert(t==1&&a==0x88b9);calls[2]++;return (void*)7;
}
static GLboolean near_unmap_buffer_real(GLenum t) {assert(t==1);calls[3]++;return 0;}
static GLboolean near_unmap_buffer_oes_real(GLenum t) {assert(t==1);calls[4]++;return 1;}
static GLenum glGetError(void) {calls[5]++;return 1282;}
''' + wrappers + r'''
int main(void) {
 assert(glMapBufferRange_near(1,8,20,15)==(void*)3);
 assert(glMapBufferRangeEXT_near(1,8,20,15)==NULL);
 assert(glMapBufferOES_near(1,0x88b9)==(void*)7);
 assert(!glUnmapBuffer_near(1));assert(glUnmapBufferOES_near(1));
 assert(glGetError_near()==1282);
 for(unsigned i=0;i<6;i++)assert(calls[i]==1);
 assert(maps==3&&map_failures==1&&unmaps==2&&unmap_failures==1&&errors==1);
}
''')
        for name in ('glMapBufferRangeEXT','glMapBufferOES','glUnmapBufferOES','glGetError'):
            self.assertIn('"'+name+'"',function(imports,'eglGetProcAddress_diag'))


if __name__ == '__main__':
    unittest.main()

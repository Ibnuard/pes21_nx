"""Binary loading must invalidate wrapper uniforms without changing driver calls."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_gameplan_editor import function
from test_roof_uniform import CACHE, ENVIRONMENT, SOURCE


class ProgramBinaryCacheTests(unittest.TestCase):
    def test_real_wrappers_with_binary_reload_worker_and_context_switch(self):
        compiler = shutil.which('gcc')
        if not compiler:
            self.skipTest('host gcc required')
        binary = SOURCE[SOURCE.index('typedef void (*GLProgramBinaryProc)'):
                        SOURCE.index('static volatile uint64_t gl_diag_draw_arrays')]
        prelude = r'''
#include <assert.h>
#include <string.h>
#include <pthread.h>
#include <stdio.h>
static void scene_runtime_note(const char *a,const char *b) {(void)a;(void)b;}
typedef unsigned GLuint, GLenum;
typedef int GLint, GLsizei;
typedef float GLfloat;
typedef void (*__eglMustCastToProperFunctionPointerType)(void);
typedef void *EGLDisplay, *EGLSurface, *EGLContext;
typedef int EGLBoolean, EGLint;
#define EGL_NO_CONTEXT ((void *)0)
#define EGL_NO_SURFACE ((void *)0)
#define EGL_SUCCESS 0x3000
#define EGL_TRUE 1
#define MC_SLOTS 4
static __thread void *thread_key, *current_context;
static __thread int g_mc_tls_slot;
static __thread void *g_mc_tls_key;
static struct {
  void *key; EGLDisplay dpy; EGLSurface draw,read; EGLContext ctx;
  GLuint program;
} g_mc[MC_SLOTS];
static __thread struct {int have_prog;GLuint prog;} glc;
static EGLSurface main_window_surface;
static int driver_location=2, queries, writes, use_calls, enabled;
static int core_calls, oes_calls, native_error, native_reject;
static int context_resets, egl_error_reads, last_location=-1;
static float applied;
static GLuint expected_program;
static GLenum expected_format;
static const void *expected_binary;
static GLsizei expected_length;
static uint64_t expected_generation;
static int mc_current_slot(void) {return g_mc_tls_slot;}
static void *mc_thread_key(void) {return thread_key;}
static int fake_pbuffer(EGLSurface surface) {(void)surface;return 0;}
static EGLContext eglGetCurrentContext(void) {return current_context;}
static EGLBoolean eglMakeCurrent(EGLDisplay d,EGLSurface a,EGLSurface b,EGLContext c) {
  (void)d;(void)a;(void)b;current_context=c;return 1;
}
static EGLint eglGetError(void) {egl_error_reads++;return EGL_SUCCESS;}
static void gl_log_context_once(EGLContext c) {(void)c;}
static void debugPrintf(const char *f,...) {(void)f;}
static void gl_state_cache_reset(void) {context_resets++;memset(&glc,0,sizeof(glc));}
static int pes_controller_stadium_is_day(void) {return 1;}
static int pes_controller_roof_shadow_enabled(void) {return enabled;}
static int pes_controller_night_lighting_balance_enabled(void) {return 0;}
static int pes_controller_day_stadium_lite_enabled(void) {return 0;}
static int pes_controller_stadium_canary_active(void) {return 0;}
static unsigned pes_controller_stadium_weather(void) {return 0;}
static unsigned pes_controller_stadium_season(void) {return 0;}
static unsigned pes_controller_stadium_turf_length(void) {return 0;}
static unsigned pes_controller_stadium_pitch_condition(void) {return 0;}
static unsigned pes_controller_cloud_shadow_step(void) {return 0;}
static void glUniform2f(GLint p,float a,float b) {(void)p;(void)a;(void)b;assert(0);}
static void glUseProgram(GLuint p) {assert(p==7 && current_context);use_calls++;}
static GLint glGetUniformLocation(GLuint p,const char *name) {
  assert(p==7);queries++;
  return strcmp(name,"nxRoofDisabled") ? -1 : driver_location;
}
static void glUniform1f(GLint location,float value) {
  assert(location==driver_location);writes++;last_location=location;applied=value;
}
static void glUniform4fv(GLint location,int count,const float *values) {
  (void)location;(void)count;(void)values;assert(0);
}
'''
        driver = r'''
/* Model the specified binary-load effects. The driver is deliberately separate
 * from the wrapper, and can reject a call while leaving its GL error pending. */
static void binary_driver(GLuint p,GLenum f,const void *b,GLsizei n,int oes) {
  assert(p==expected_program && f==expected_format && b==expected_binary && n==expected_length);
  assert(gl_program_generation==expected_generation); /* publish AFTER return */
  if (oes) oes_calls++; else core_calls++;
  if (native_reject) {native_error=0x0501;return;}
  driver_location=*(const int *)b;applied=0.f;last_location=-1;
}
static void binary_core(GLuint p,GLenum f,const void *b,GLsizei n) {binary_driver(p,f,b,n,0);}
static void binary_oes(GLuint p,GLenum f,const void *b,GLsizei n) {binary_driver(p,f,b,n,1);}
static void expect_call(GLuint p,GLenum f,const void *b,GLsizei n) {
  expected_program=p;expected_format=f;expected_binary=b;expected_length=n;
  expected_generation=gl_program_generation;
}
'''
        body = r'''
static GLProgramBinaryProc resolved_core, resolved_oes;
static void *load_on_shared_context(void *blob) {
  thread_key=(void *)2;
  assert(eglMakeCurrent_dedup((void *)1,0,0,(void *)22));
  resolved_oes(7,44,blob,sizeof(int));
  return NULL;
}
static unsigned lookup_start;
static void *resolve_on_native_queue(void *unused) {
  (void)unused;
  while(!__atomic_load_n(&lookup_start,__ATOMIC_ACQUIRE)) {}
  for(int i=0;i<1000;i++) {
    assert((GLProgramBinaryProc)gl_program_binary_proc("glProgramBinary",
      (__eglMustCastToProperFunctionPointerType)binary_core)==resolved_core);
    assert((GLProgramBinaryProc)gl_program_binary_proc("glProgramBinaryOES",
      (__eglMustCastToProperFunctionPointerType)binary_oes)==resolved_oes);
  }
  return NULL;
}
int main(void) {
  thread_key=(void *)1;
  assert(eglMakeCurrent_dedup((void *)1,(void *)2,(void *)2,(void *)11));
  assert(!gl_program_binary_proc(NULL,(__eglMustCastToProperFunctionPointerType)binary_core));
  assert(!gl_program_binary_proc("glProgramBinary",NULL));
  assert(!gl_program_binary_proc("glProgramBinaryOES",NULL));
  assert(!gl_program_binary_proc("glGetProgramBinary",(__eglMustCastToProperFunctionPointerType)binary_core));
  resolved_core=(GLProgramBinaryProc)gl_program_binary_proc("glProgramBinary",(__eglMustCastToProperFunctionPointerType)binary_core);
  resolved_oes=(GLProgramBinaryProc)gl_program_binary_proc("glProgramBinaryOES",(__eglMustCastToProperFunctionPointerType)binary_oes);
  assert(resolved_core && resolved_oes && resolved_core!=resolved_oes);
  assert(gl_program_binary_real==binary_core && gl_program_binary_oes_real==binary_oes);
  glUseProgram_c(7);assert(queries==8 && writes==1 && applied==1.f && last_location==2);
  int blob=11;
  expect_call(7,33,&blob,sizeof(blob));resolved_core(7,33,&blob,sizeof(blob));
  assert(core_calls==1 && oes_calls==0 && applied==0.f);
  assert(gl_program_generation==expected_generation+1);
  glUseProgram_c(7);assert(queries==16 && writes==2 && applied==1.f && last_location==11);
  /* Same executable/layout still resets all values; it must be re-uploaded. */
  expect_call(7,33,&blob,sizeof(blob));resolved_core(7,33,&blob,sizeof(blob));
  glUseProgram_c(7);assert(queries==24 && writes==3 && applied==1.f);
  /* OES keeps its own driver entry and invalidates the already-warm other TLS. */
  blob=17;expect_call(7,44,&blob,sizeof(blob));
  pthread_t loader;assert(!pthread_create(&loader,NULL,load_on_shared_context,&blob));
  assert(!pthread_join(loader,NULL));
  assert(core_calls==2 && oes_calls==1 && current_context==(void *)11);
  glUseProgram_c(7);assert(queries==32 && writes==4 && last_location==17 && applied==1.f);
  /* Native rejection and exact invalid arguments are forwarded, not consumed. */
  native_reject=1;expect_call(0,99,NULL,-3);resolved_core(0,99,NULL,-3);
  assert(core_calls==3 && oes_calls==1 && native_error==0x0501);
  assert(gl_program_generation==expected_generation+1 && queries==32 && writes==4);
  assert(!gl_program_binary_proc("glProgramBinary",NULL));
  assert(gl_program_binary_real==binary_core); /* no unsupported advertisement */
  native_reject=0;native_error=0;
  glUseProgram_c(7);assert(queries==40 && writes==5 && applied==1.f);
  /* A distinct context/share-group can reuse GLuint7 without a binary call.
   * Exercise the existing real make-current wrapper's TLS invalidation too. */
  const uint64_t generation=gl_program_generation;
  driver_location=29;applied=0.f;
  assert(eglMakeCurrent_dedup((void *)1,(void *)2,(void *)2,(void *)33));
  assert(gl_program_generation==generation);
  glUseProgram_c(7);assert(queries==48 && writes==6 && last_location==29 && applied==1.f);
  const int warm_queries=queries,warm_writes=writes,warm_uses=use_calls;
  for(int i=0;i<1000;i++)glUseProgram_c(7);
  assert(queries==warm_queries && writes==warm_writes && use_calls==warm_uses+1000);
  assert(context_resets==3 && egl_error_reads==0 && native_error==0);
  /* Native lookup queues may republish the driver while the draw/upload
   * queue uses a previously returned wrapper. Keep both APIs independent. */
  pthread_t lookup;assert(!pthread_create(&lookup,NULL,resolve_on_native_queue,NULL));
  __atomic_store_n(&lookup_start,1,__ATOMIC_RELEASE);
  for(int i=0;i<1000;i++) {
    const GLenum format=i%2 ? 44u : 33u;
    expect_call(7,format,&blob,sizeof(blob));
    (i%2 ? resolved_oes : resolved_core)(7,format,&blob,sizeof(blob));
  }
  assert(!pthread_join(lookup,NULL));
  assert(core_calls==503 && oes_calls==501 && native_error==0);
  glUseProgram_c(7);assert(queries==warm_queries+8 && applied==1.f);
  return 0;
}
'''
        harness = (ENVIRONMENT + prelude + CACHE + driver + binary
                   + function(SOURCE, 'glUseProgram_c')
                   + function(SOURCE, 'eglMakeCurrent_dedup') + body)
        with tempfile.TemporaryDirectory(prefix='gl-program-binary-') as tmp:
            source = Path(tmp) / 'replay.c'
            exe = Path(tmp) / 'replay.exe'
            source.write_text(harness, encoding='utf-8')
            subprocess.run([compiler, '-std=c11', '-pthread', str(source),
                            '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_dynamic_route_preserves_unsupported_entries_and_native_pointer_symbol(self):
        resolver = function(SOURCE, 'eglGetProcAddress_diag')
        self.assertIn('proc = eglGetProcAddress(name);', resolver)
        self.assertIn('gl_program_binary_proc(name, proc)', resolver)
        self.assertIn('if (binary) return binary;', resolver)
        # The target's glProgramBinary is a native function-pointer DATA symbol,
        # not an undefined static GL import. Do not override it with code.
        self.assertNotIn('{ "glProgramBinary",', SOURCE)
        self.assertNotIn('{ "glProgramBinaryOES",', SOURCE)


if __name__ == '__main__':
    unittest.main()

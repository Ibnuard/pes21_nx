"""Observe native first/warm-launch outcomes without consuming extra GL errors."""
from pathlib import Path
import shutil
import unittest
from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]
PROBE = (ROOT / 'source/gl_startup_audit.inc').read_text()
IMPORTS = (ROOT / 'source/imports.c').read_text()
PRELUDE = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef unsigned GLuint, GLenum, GLbitfield;
typedef int GLint;
typedef long GLintptr, GLsizeiptr;
typedef unsigned char GLboolean;
typedef void (*__eglMustCastToProperFunctionPointerType)(void);
#define GL_FALSE 0
#define GL_LINK_STATUS 0x8b82
#define PESNX_BUILD_ID "host-test"
static unsigned pending=0x0502, errors, program_queries, notes;
static int current_slot=3, native_linked;
static char last_note[1024];
static int mc_current_slot(void) { return current_slot; }
static GLenum glGetError(void) { ++errors; unsigned r=pending; pending=0; return r; }
static void glGetProgramiv(GLuint p,GLenum n,GLint *v) {
  assert(p==19 && n==GL_LINK_STATUS); ++program_queries;
  if(v)*v=native_linked;
}
static void scene_runtime_note(const char *area,const char *message) {
  ++notes; snprintf(last_note,sizeof(last_note),"%s: %s",area,message);
}
'''


class StartupRenderAuditTests(unittest.TestCase):
    def replay(self, body):
        gcc = shutil.which('gcc')
        if not gcc:
            self.skipTest('host gcc required')
        build_and_run(gcc, PRELUDE + PROBE + body)

    def test_exact_native_queries_and_pause_only_bounded_output(self):
        self.replay(r'''
int main(void) {
  assert(glGetError_startup()==0x0502 && errors==1);
  assert(glGetError_startup()==0 && errors==2);
  GLint v=9;
  glGetProgramiv_startup(19,GL_LINK_STATUS,&v);
  assert(v==0 && program_queries==1);
  native_linked=1; glGetProgramiv_startup(19,GL_LINK_STATUS,&v);
  assert(v==1 && program_queries==2);
  assert(nx_start_counts[NX_START_ERROR_QUERY]==2);
  assert(nx_start_counts[NX_START_ERROR]==1);
  assert(nx_start_counts[NX_START_LINK_QUERY]==2);
  assert(nx_start_counts[NX_START_LINK_REJECT]==1);
  assert(!notes && nx_start_events[0].code==0x0502);
  assert(nx_start_events[0].slot==3 && nx_start_events[1].kind==NX_START_LINK_REJECT);
  for(int i=0;i<1000;i++)nx_start_present(1,1);
  assert(!notes && errors==2 && program_queries==2);
  nx_start_present(0,1); assert(notes==5);
  unsigned old=notes;
  for(int i=0;i<1000;i++)nx_start_present(0,1);
  assert(notes==old);
  for(int i=0;i<100;i++){nx_start_present(1,1);nx_start_present(0,1);}
  assert(notes==old+14 && errors==2 && program_queries==2);
  for(int i=0;i<100;i++)nx_start_failure(NX_START_MAP_FAIL,0,1);
  assert(nx_start_event_next==102); /* Storage still bounded to sixteen. */
}
''')

    def test_core_ext_oes_arguments_results_and_unsupported_lookups(self):
        self.replay(r'''
static unsigned core,ext,oes,unmap_calls;
static void *mapped=(void *)0x123;
static void *core_map(GLenum t,GLintptr o,GLsizeiptr n,GLbitfield a) {
  assert(t==7 && o==-2 && n==31 && a==9);++core;return mapped;
}
static void *ext_map(GLenum t,GLintptr o,GLsizeiptr n,GLbitfield a) {
  assert(t==8 && o==4 && n==-3 && a==11);++ext;return 0;
}
static void *oes_map(GLenum t,GLenum a) {assert(t==9 && a==5);++oes;return mapped;}
static GLboolean unmap(GLenum t) {assert(t==7);++unmap_calls;return 0;}
int main(void) {
  assert(!nx_start_proc(0,(__eglMustCastToProperFunctionPointerType)core_map));
  assert(!nx_start_proc("glMapBufferRange",0));
  assert(!nx_start_proc("unrelated",(__eglMustCastToProperFunctionPointerType)core_map));
  NxStartMap c=(NxStartMap)nx_start_proc("glMapBufferRange",(__eglMustCastToProperFunctionPointerType)core_map);
  NxStartMap e=(NxStartMap)nx_start_proc("glMapBufferRangeEXT",(__eglMustCastToProperFunctionPointerType)ext_map);
  NxStartMapOes o=(NxStartMapOes)nx_start_proc("glMapBufferOES",(__eglMustCastToProperFunctionPointerType)oes_map);
  NxStartUnmap u=(NxStartUnmap)nx_start_proc("glUnmapBuffer",(__eglMustCastToProperFunctionPointerType)unmap);
  NxStartUnmap uo=(NxStartUnmap)nx_start_proc("glUnmapBufferOES",(__eglMustCastToProperFunctionPointerType)unmap);
  assert(c(7,-2,31,9)==mapped && e(8,4,-3,11)==0 && o(9,5)==mapped);
  assert(!u(7) && !uo(7) && core==1 && ext==1 && oes==1 && unmap_calls==2);
  assert(nx_start_counts[NX_START_MAP]==3 && nx_start_counts[NX_START_MAP_FAIL]==1);
  assert(nx_start_counts[NX_START_UNMAP]==2 && nx_start_counts[NX_START_UNMAP_FAIL]==2);
  assert(nx_start_events[0].route==2 && nx_start_events[1].route==1 && nx_start_events[2].route==3);
  assert(!notes && errors==0 && program_queries==0);
  assert(nx_start_proc("glGetError",(__eglMustCastToProperFunctionPointerType)glGetError)==(__eglMustCastToProperFunctionPointerType)glGetError_startup);
}
''')

    def test_observation_has_no_driver_readback_wait_or_draw_calls(self):
        for forbidden in ('glFinish(', 'glFlush(', 'glReadPixels(', 'glGetIntegerv(',
                          'glGetShaderiv(', 'glDraw', 'glGetProgramInfoLog('):
            self.assertNotIn(forbidden, PROBE)
        # The two native result queries are each delegated exactly once.
        self.assertEqual(PROBE.count('glGetError();'), 1)
        self.assertEqual(PROBE.count('glGetProgramiv(p,name,value);'), 1)
        self.assertIn('#ifdef STARTUP_RENDER_AUDIT\n#include "gl_startup_audit.inc"', IMPORTS)
        resolver = function(IMPORTS, 'eglGetProcAddress_diag')
        self.assertIn('nx_start_proc(name,proc)', resolver)
        self.assertIn('STARTUP_RENDER_AUDIT', function(IMPORTS, 'eglSwapBuffers_cache'))


if __name__ == '__main__':
    unittest.main()

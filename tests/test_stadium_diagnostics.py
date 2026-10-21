"""Diagnostic sampling must be bounded and leave render/camera values alone."""
from pathlib import Path
import shutil
import unittest
from test_result_flow import build_and_run, function

ROOT = Path(__file__).resolve().parents[1]
POLICY = (ROOT / 'source/stadium_diagnostic_policy.h').read_text()
GL = (ROOT / 'source/imports.c').read_text()
HOOKS = (ROOT / 'source/ue4_hooks.c').read_text()


class StadiumDiagnosticsTests(unittest.TestCase):
    def run_c(self, source):
        compiler = shutil.which('gcc')
        if not compiler:
            self.skipTest('gcc unavailable')
        build_and_run(compiler, '#include <assert.h>\n' + POLICY + source)

    def test_sampling_limits_and_source_features(self):
        self.run_c(r'''
int main(void) {
  StadiumDiagnosticGate gate = {0};
  assert(stadium_diagnostic_due(&gate, 0, 1, 0, 500));
  for (int i=1; i<500; ++i)
    assert(!stadium_diagnostic_due(&gate, i, 1, 0, 500));
  assert(stadium_diagnostic_due(&gate, 500, 1, 0, 500));
  assert(stadium_diagnostic_due(&gate, 501, 1, 1, 500)); // setting changed
  assert(stadium_diagnostic_due(&gate, 502, 2, 1, 500)); // new owner
  assert(stadium_diagnostic_due(&gate, 1, 2, 1, 500));   // clock reset
  assert(stadium_diagnostic_features("unrelated shader") == 0);
  assert(stadium_diagnostic_features("nxRoofDisabled MobileDirectionalLight texture(ps1,in_TEXCOORD0.zw)") == 7);
  assert(stadium_diagnostic_hash("a b\nc\r\td") == stadium_diagnostic_hash("abcd"));
}
''')

    def test_optional_camera_snapshot_is_read_only_without_ball_probes(self):
        self.assertNotIn('stadium_diag_camera_target(', HOOKS)
        self.assertNotIn('stadium_diag_camera_final(', HOOKS)
        self.run_c(r'''
#define NEAR_CAMERA_TRACE 1
#define DEBUG_LOG 1
static uint64_t now;
static unsigned snapshots;
static uint32_t pause_camera_dynamic_wide_custom;
static uint32_t pause_camera_stadium_v2;
static uint64_t armGetSystemTick(void) {return now;}
static uint64_t armTicksToNs(uint64_t n) {return n;}
static void native_update(void *c,void *p) {(void)c;(void)p;}
static void (*match_inplay_camera_update_original)(void*,void*)=native_update;
static unsigned footballnx_tribune_view(float *p) {assert(0);return 0;}
static void stadium_v2_begin(void *c,void *p) {(void)c;(void)p;} // Native choice, V2 disabled.
static void stadium_v2_end(void) {}
static void stadium_camera_begin(void *c,void *p) {(void)c;(void)p;}
static void stadium_camera_end(void) {}
static void nx_near_camera(const float *p,unsigned id,uint64_t tick) {
  assert(p[0]==4 && p[5]==55 && (id==1 || id==(pause_camera_stadium_v2?134u:6u)) && tick==now);
  ++snapshots;
}
''' + function(HOOKS, 'pes_inplay_camera_update') + r'''
int main(void) {
  uint32_t camera[8]={0}; float p[16]={4,1,8,20,30,55}, saved[16];
  memcpy(saved,p,sizeof(p));
  for(unsigned frame=0;frame<1000;++frame) {
    camera[2]=(frame&1)?1:6; now=frame*16000000ULL;
    pause_camera_stadium_v2=!!(frame&2);
    pes_inplay_camera_update(camera,p);
    assert(!memcmp(p,saved,sizeof(p)));
    assert(camera[2]==((frame&1)?1u:6u));
  }
  assert(snapshots==1000);
  pes_inplay_camera_update(NULL,p);pes_inplay_camera_update(camera,NULL);
  assert(snapshots==1000);
}
''')

    def test_draw_probe_restores_active_texture_and_does_not_write_uniform(self):
        probe_struct = GL[GL.index('typedef struct {\n  GLuint program;\n  EGLContext context;'):
                          GL.index('static void stadium_diag_forget(GLuint program) {')]
        self.run_c(r'''
#include <stdio.h>
#include <stdarg.h>
typedef unsigned GLuint;
typedef unsigned GLenum;
typedef int GLint;
typedef int GLsizei;
typedef float GLfloat;
typedef void *EGLContext;
#define GL_CURRENT_PROGRAM 1
#define GL_FRAMEBUFFER_BINDING 2
#define GL_ACTIVE_TEXTURE 3
#define GL_TEXTURE_BINDING_2D 4
#define GL_BLEND 5
#define GL_DEPTH_TEST 6
#define GL_TEXTURE0 100
static int active=107, queries, classifications, logs, roof=0;
static uint64_t now;
static struct {GLuint program; EGLContext ctx;} g_mc[1];
static int mc_current_slot(void) {return 0;}
static uint64_t armGetSystemTick(void) {return now;}
static uint64_t armTicksToNs(uint64_t n) {return n;}
static unsigned pes_controller_stadium_is_day(void) {return 1;}
static unsigned pes_controller_roof_shadow_enabled(void) {return roof;}
static unsigned stadium_diag_program(GLuint p) {++classifications; return 7;}
static int debugPrintf(char *format, ...) {(void)format; return ++logs;}
static void glGetIntegerv(GLenum e, GLint *out) {
  ++queries; *out=e==GL_ACTIVE_TEXTURE ? active : e==GL_CURRENT_PROGRAM ? 7 : 9;
}
static GLint glGetUniformLocation(GLuint p, const char *n) {
  assert(p==7); return !strcmp(n,"nxRoofDisabled") ? 2 : !strcmp(n,"ps1") ? 3 : -1;
}
static void glGetUniformfv(GLuint p, GLint loc, GLfloat *v) {assert(loc==2); *v=1;}
static void glGetUniformiv(GLuint p, GLint loc, GLint *v) {assert(loc==3); *v=1;}
static void glActiveTexture(GLenum unit) {active=unit;}
static int glIsEnabled(GLenum e) {return 0;}
''' + probe_struct + function(GL, 'stadium_diag_draw') + r'''
int main(void) {
  g_mc[0].program=7; g_mc[0].ctx=(void*)1;
  stadium_diag_draw("test",100);
  assert(classifications==1 && active==107 && queries==4 && logs==2);
  now=1000000000;
  stadium_diag_draw("test",100);
  assert(classifications==1 && queries==4 && logs==2);
  roof=1; stadium_diag_draw("test",100);
  assert(active==107 && queries==8 && logs==4);
  g_mc[0].ctx=(void*)2; stadium_diag_draw("test",100);
  assert(classifications==2 && active==107);
}
''')

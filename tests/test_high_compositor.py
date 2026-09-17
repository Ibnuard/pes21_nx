"""Exercise source selection using the observed High multipass layout."""
import re
import shutil
import unittest
from pathlib import Path
from test_result_flow import build_and_run, function


class HighCompositorTests(unittest.TestCase):
    def test_selects_current_frame_scene_not_bloom(self):
        compiler = shutil.which('gcc')
        if not compiler:
            self.skipTest('gcc unavailable')
        source = (Path(__file__).resolve().parents[1]/'source/imports.c').read_text()
        struct = re.search(r'typedef struct \{\s*int matched;.*?\} GLComposeExperiment;', source, re.S)[0]
        cache = source[source.index('static struct {\n  void *key;'):source.index('static __thread int g_mc_tls_slot')]
        build_and_run(compiler, r'''
#include <assert.h>
#include <string.h>
typedef unsigned GLuint;
typedef unsigned GLenum;
typedef int GLint;
typedef int GLsizei;
typedef void *EGLDisplay;
typedef void *EGLSurface;
typedef void *EGLContext;
#define MC_SLOTS 1
static int mc_current_slot(void) {return 0;}
''' + struct + cache + function(source, 'gl_diag_prepare_compose_experiment') + r'''
static void setup(void) {
  memset(g_mc,0,sizeof(g_mc));
  g_mc[0].viewport[2]=1024; g_mc[0].viewport[3]=576;
  g_mc[0].texture2d[0]=297; g_mc[0].texture2d[1]=85;
  g_mc[0].sampler[1]=6;
  g_mc[0].completed_scene[0].texture=85;
  g_mc[0].completed_scene[0].framebuffer=8;
  g_mc[0].completed_scene[0].width=1024;
  g_mc[0].completed_scene[0].height=576;
}
int main(void) {
  setup();
  GLComposeExperiment e=gl_diag_prepare_compose_experiment(3);
  assert(e.matched && e.texture==85 && e.source_framebuffer==8 && e.sampler==6);
  assert(!gl_diag_prepare_compose_experiment(3).matched);
  setup(); assert(!gl_diag_prepare_compose_experiment(6).matched);
  setup(); g_mc[0].completed_scene[0].width=256;
  assert(!gl_diag_prepare_compose_experiment(3).matched);
  setup(); g_mc[0].framebuffer=9;
  assert(!gl_diag_prepare_compose_experiment(3).matched);
  setup(); memset(g_mc[0].completed_scene,0,sizeof(g_mc[0].completed_scene));
  assert(!gl_diag_prepare_compose_experiment(3).matched);
  g_mc[0].scene_texture=297; g_mc[0].scene_framebuffer=10;
  g_mc[0].scene_compose_pending=1;
  e=gl_diag_prepare_compose_experiment(3);
  assert(e.matched && e.texture==297); // original single-source path retained
}
''')

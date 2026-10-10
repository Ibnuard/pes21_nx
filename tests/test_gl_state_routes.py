"""Mixing imported and resolved core GL calls must restore actual draw state."""
from pathlib import Path
import shutil
import unittest
from test_gameplan_editor import function
from test_result_flow import build_and_run

SOURCE = (Path(__file__).resolve().parents[1]/'source/imports.c').read_text()


class GLStateRouteTests(unittest.TestCase):
    def test_high_texture_unit_does_not_replace_compose_texture(self):
        gcc = shutil.which('gcc')
        if not gcc:
            self.skipTest('gcc unavailable')
        helpers = ''.join(function(SOURCE, n) for n in
                          ('glActiveTexture_c', 'glBindTexture_c'))
        build_and_run(gcc, r'''
#include <assert.h>
typedef unsigned GLenum;
typedef unsigned GLuint;
#define GL_TEXTURE0 0x84c0
#define GL_TEXTURE_2D 0x0de1
static struct {unsigned active_texture; GLuint texture2d[8];} g_mc[1];
static struct {int have_active; GLenum active;} glc;
static int glc_enabled=1;
static unsigned actual_unit, active_calls;
static GLuint actual_textures[16];
static int mc_current_slot(void) {return 0;}
static void glActiveTexture(GLenum unit) {
  actual_unit=unit-GL_TEXTURE0;assert(actual_unit<16);++active_calls;
}
static void glBindTexture(GLenum target, GLuint texture) {
  assert(target==GL_TEXTURE_2D);actual_textures[actual_unit]=texture;
}
''' + helpers + r'''
int main(void) {
  glActiveTexture_c(GL_TEXTURE0+1);glBindTexture_c(GL_TEXTURE_2D,7);
  glActiveTexture_c(GL_TEXTURE0+12);glBindTexture_c(GL_TEXTURE_2D,99);
  assert(g_mc[0].texture2d[1]==7 && actual_textures[1]==7);
  assert(g_mc[0].active_texture==12 && actual_textures[12]==99);
  glActiveTexture_c(GL_TEXTURE0+12);glBindTexture_c(GL_TEXTURE_2D,100);
  assert(active_calls==2 && g_mc[0].texture2d[1]==7);
  glActiveTexture_c(GL_TEXTURE0+1);glBindTexture_c(GL_TEXTURE_2D,8);
  assert(g_mc[0].texture2d[1]==8 && actual_textures[1]==8);
  assert(actual_textures[12]==100 && active_calls==3);
}
''')

    def test_rebinding_same_texture_name_acquires_shared_upload(self):
        gcc = shutil.which('gcc')
        if not gcc:
            self.skipTest('gcc unavailable')
        build_and_run(gcc, r'''
#include <assert.h>
typedef unsigned GLenum;
typedef unsigned GLuint;
#define GL_TEXTURE_2D 0x0de1
static struct {unsigned active_texture; GLuint texture2d[8];} g_mc[1];
static int calls, shared_version=1, acquired_version;
static int mc_current_slot(void) {return 0;}
static void glBindTexture(GLenum target, GLuint texture) {
  assert(target==GL_TEXTURE_2D && texture==7);
  calls++;acquired_version=shared_version;
}
''' + function(SOURCE, 'glBindTexture_c') + r'''
int main(void) {
  glBindTexture_c(GL_TEXTURE_2D,7);
  assert(acquired_version==1 && g_mc[0].texture2d[0]==7);
  shared_version=2; // Worker replaces storage or recycles the name.
  glBindTexture_c(GL_TEXTURE_2D,7);
  assert(acquired_version==2 && calls==2);
}
''')

    def test_dynamic_depth_and_enable_restore_after_other_material(self):
        gcc = shutil.which('gcc')
        if not gcc:
            self.skipTest('gcc unavailable')
        helpers = ''.join(function(SOURCE, n) for n in
            ('glEnable_c', 'glDisable_c', 'glDepthMask_c', 'gl_cached_state_proc'))
        build_and_run(gcc, r'''
#include <assert.h>
#include <string.h>
typedef unsigned GLenum;
typedef unsigned char GLboolean;
typedef void (*__eglMustCastToProperFunctionPointerType)(void);
#define GL_TRUE 1
#define GL_FALSE 0
#define GLC_MAXCAPS 24
static int glc_enabled=1, glc_ncaps, enabled, depth, calls;
static struct {GLenum cap;GLboolean on;} glc_caps[GLC_MAXCAPS];
static struct {int have_dmask;GLboolean dmask;} glc;
static void glEnable(GLenum cap) {(void)cap;enabled=1;calls++;}
static void glDisable(GLenum cap) {(void)cap;enabled=0;calls++;}
static void glDepthMask(GLboolean value) {depth=value;calls++;}
#define STUB(n) static void n(void) {}
STUB(glBlendFunc_c) STUB(glBlendFuncSeparate_c) STUB(glDepthFunc_c)
STUB(glCullFace_c) STUB(glFrontFace_c) STUB(glColorMask_c)
STUB(glActiveTexture_c) STUB(glBindTexture_c) STUB(glDeleteTextures_c)
''' + helpers + r'''
int main(void) {
  void (*resolved_disable)(GLenum)=(void (*)(GLenum))gl_cached_state_proc("glDisable");
  void (*resolved_depth)(GLboolean)=(void (*)(GLboolean))gl_cached_state_proc("glDepthMask");
  assert(resolved_disable && resolved_depth);
  glEnable_c(7);glDepthMask_c(1);assert(enabled && depth);
  resolved_disable(7);resolved_depth(0);assert(!enabled && !depth);
  glEnable_c(7);glDepthMask_c(1);assert(enabled && depth && calls==6);
  glEnable_c(7);glDepthMask_c(1);assert(calls==6); // Retain redundant-call savings.
  assert(!gl_cached_state_proc(NULL) && !gl_cached_state_proc("glUnrelated"));
  assert(gl_cached_state_proc("glDeleteTextures")==glDeleteTextures_c);
  // The v8 release routing remains native for these dynamically resolved APIs.
  assert(!gl_cached_state_proc("glBindFramebuffer"));
  assert(!gl_cached_state_proc("glViewport"));
  assert(!gl_cached_state_proc("glDrawArrays"));
  assert(!gl_cached_state_proc("glDrawElements"));
}
''')

    def test_resolver_uses_shared_state_routes_only_if_driver_supports_them(self):
        resolver = function(SOURCE, 'eglGetProcAddress_diag')
        self.assertIn('gl_cached_state_proc(name)', resolver)
        self.assertIn('if (proc && cached) return cached;', resolver)

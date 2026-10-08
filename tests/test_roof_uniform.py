"""Roof preference must reach reused GL programs without recompiling shaders."""
from pathlib import Path
import shutil
import unittest
from test_gameplan_editor import function
from test_result_flow import build_and_run

SOURCE = (Path(__file__).resolve().parents[1]/'source/imports.c').read_text()

class RoofUniformTests(unittest.TestCase):
    def test_updates_cached_program_and_invalidates_deleted_name(self):
        gcc = shutil.which('gcc')
        if not gcc:
            self.skipTest('gcc unavailable')
        build_and_run(gcc, r'''
#include <assert.h>
#include <string.h>
typedef unsigned GLuint;
typedef int GLint;
typedef float GLfloat;
static int glc_enabled=1, binds, queries, sets, night_sets, day=1, enabled=1, high=1;
static float applied, night_applied;
static struct {int have_prog; GLuint prog;} glc;
static struct {GLuint program;} g_mc[1];
static struct {GLuint program; GLint location,night_location; int valid,night_value;} roof_uniforms[128];
static int mc_current_slot(void) {return 0;}
static int pes_controller_stadium_is_day(void) {return day;}
static int pes_controller_roof_shadow_enabled(void) {return enabled;}
static int pes_controller_night_lighting_balance_enabled(void) {return high && !day;}
static void glUseProgram(GLuint p) {(void)p; ++binds;}
static void glDeleteProgram(GLuint p) {(void)p;}
static GLint glGetUniformLocation(GLuint p, const char *name) {
  ++queries;
  if(!strcmp(name,"nxRoofDisabled"))return p==7 ? 2 : -1;
  assert(!strcmp(name,"nxNightIndirect")); return p==7 ? 3 : -1;
}
static void glUniform1f(GLint loc, float value) {
  if(loc==2) {++sets;applied=value;}
  else {assert(loc==3);++night_sets;night_applied=value;}
}
''' + function(SOURCE,'glUseProgram_c') + function(SOURCE,'glDeleteProgram_c') + r'''
int main(void) {
  glUseProgram_c(7); assert(applied==0 && binds==1 && queries==2);
  assert(night_sets==1 && night_applied==0);
  enabled=0; glUseProgram_c(7); assert(applied==1 && binds==1 && queries==2);
  assert(night_sets==1);
  day=0; glUseProgram_c(7); assert(applied==0 && binds==1 && queries==2);
  assert(night_sets==2 && night_applied==1);
  day=1; enabled=1; glUseProgram_c(7); assert(applied==0);
  assert(night_sets==3 && night_applied==0);
  glUseProgram_c(9); assert(sets==4);
  glDeleteProgram_c(7); glUseProgram_c(7); assert(queries==6 && night_sets==4);
  high=0;day=0;glUseProgram_c(7);assert(night_applied==0 && night_sets==4);
  high=1;glUseProgram_c(7);assert(night_applied==1 && night_sets==5);
  glUseProgram_c(0); assert(queries==6);
}
''')

    def test_dynamic_and_import_routes_both_deliver_uniform(self):
        resolver = function(SOURCE,'eglGetProcAddress_diag')
        for api, wrapper in (('glUseProgram','glUseProgram_c'),
                             ('glLinkProgram','glLinkProgram_diag'),
                             ('glDeleteProgram','glDeleteProgram_c')):
            self.assertIn(f'!strcmp(name, "{api}")', resolver)
            self.assertIn(f'&{wrapper}', resolver)
            self.assertIn(f'{{ "{api}", (uintptr_t)&{wrapper} }}', SOURCE)

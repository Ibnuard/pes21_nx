"""Roof preference must reach reused GL programs without recompiling shaders."""
from pathlib import Path
import shutil
import unittest
from test_gameplan_editor import function
from test_result_flow import build_and_run

SOURCE = (Path(__file__).resolve().parents[1]/'source/imports.c').read_text()
ENVIRONMENT = (Path(__file__).resolve().parents[1]/'source/stadium_environment.h').read_text()
ENVIRONMENT = ENVIRONMENT.replace('#include "match_environment.h"',
    (Path(__file__).resolve().parents[1]/'source/match_environment.h').read_text())
CACHE = SOURCE[SOURCE.index('static __thread struct {\n  GLuint program;'):SOURCE.index('static void glUseProgram_c')]

class RoofUniformTests(unittest.TestCase):
    def test_updates_cached_program_and_invalidates_deleted_name(self):
        gcc = shutil.which('gcc')
        if not gcc:
            self.skipTest('gcc unavailable')
        build_and_run(gcc, ENVIRONMENT + r'''
#include <assert.h>
#include <string.h>
typedef unsigned GLuint;
typedef int GLint;
typedef float GLfloat;
static int binds, queries, sets, night_sets, day_sets, day=1, enabled=1, high=1;
static int climate_sets, profile_sets, profile;
static unsigned weather, season, turf=1, condition=1;
static float applied, night_applied, day_applied;
static float climate_applied[4], profile_applied;
static struct {int have_prog; GLuint prog;} glc;
static struct {GLuint program;} g_mc[1];
''' + CACHE + r'''
static int mc_current_slot(void) {return 0;}
static int pes_controller_stadium_is_day(void) {return day;}
static int pes_controller_roof_shadow_enabled(void) {return enabled;}
static int pes_controller_night_lighting_balance_enabled(void) {return high && !day;}
static int pes_controller_day_stadium_lite_enabled(void) {return high && day;}
static int pes_controller_stadium_canary_active(void) {return profile;}
static unsigned pes_controller_stadium_weather(void) {return weather;}
static unsigned pes_controller_stadium_season(void) {return season;}
static unsigned pes_controller_stadium_turf_length(void) {return turf;}
static unsigned pes_controller_stadium_pitch_condition(void) {return condition;}
static void glUseProgram(GLuint p) {(void)p; ++binds;}
static void glDeleteProgram(GLuint p) {(void)p;}
static GLint glGetUniformLocation(GLuint p, const char *name) {
  ++queries;
  if(!strcmp(name,"nxRoofDisabled"))return p==7 ? 2 : -1;
  if(!strcmp(name,"nxDayStadium"))return p==7 ? 4 : -1;
  if(!strcmp(name,"nxStadiumClimate"))return p==7 ? 5 : -1;
  if(!strcmp(name,"nxStadiumProfile"))return p==7 ? 6 : -1;
  assert(!strcmp(name,"nxNightIndirect")); return p==7 ? 3 : -1;
}
static void glUniform1f(GLint loc, float value) {
  if(loc==2) {++sets;applied=value;}
  else if(loc==4) {++day_sets;day_applied=value;}
  else if(loc==6) {++profile_sets;profile_applied=value;}
  else {assert(loc==3);++night_sets;night_applied=value;}
}
static void glUniform4fv(GLint loc, int count, const GLfloat *value) {
  assert(loc==5 && count==1);++climate_sets;
  memcpy(climate_applied,value,sizeof(climate_applied));
}
''' + function(SOURCE,'glUseProgram_c') + function(SOURCE,'glDeleteProgram_c') + r'''
int main(void) {
  glUseProgram_c(7); assert(applied==0 && binds==1 && queries==5);
  assert(night_sets==1 && night_applied==0);
  assert(day_sets==1 && day_applied==1);
  assert(climate_sets==1 && profile_sets==1 && profile_applied==0);
  for(int i=0;i<4;i++)assert(climate_applied[i]==0);
  enabled=0; glUseProgram_c(7); assert(applied==1 && binds==2 && queries==5);
  assert(night_sets==1);
  day=0; glUseProgram_c(7); assert(applied==0 && binds==3 && queries==5);
  assert(night_sets==2 && night_applied==1);
  assert(day_sets==2 && day_applied==0);
  day=1; enabled=1; glUseProgram_c(7); assert(applied==0);
  assert(night_sets==3 && night_applied==0);
  glUseProgram_c(9); assert(sets==3);
  for(int n=0;n<1000;n++)glUseProgram_c(7);
  assert(sets==3); // unchanged roof setting never resubmitted per draw
  glDeleteProgram_c(7); glUseProgram_c(7); assert(queries==15 && night_sets==4);
  high=0;day=0;glUseProgram_c(7);assert(night_applied==0 && night_sets==4);
  high=1;glUseProgram_c(7);assert(night_applied==1 && night_sets==5);
  assert(climate_sets==2 && profile_sets==2);
  weather=season=1;turf=0;condition=2;profile=1;
  glUseProgram_c(7);
  assert(climate_sets==3 && profile_sets==3 && profile_applied==1);
  assert(climate_applied[0]==1 && climate_applied[1]==1);
  assert(climate_applied[2]==-1 && climate_applied[3]==1);
  glUseProgram_c(7);assert(climate_sets==3 && profile_sets==3 && queries==15);
  weather=season=0;turf=condition=1;profile=0;
  glUseProgram_c(7);assert(climate_sets==4 && profile_sets==4);
  for(int i=0;i<4;i++)assert(climate_applied[i]==0);
  glUseProgram_c(0); assert(queries==15);
  // Relink/delete on the upload context invalidates this thread's locations.
  __atomic_add_fetch(&gl_program_generation,1,__ATOMIC_RELEASE);
  glUseProgram_c(7); assert(queries==20 && climate_sets==5);
  // Reused program distinguishes Rainy from Cloudy, even with Wet selected.
  weather=NX_WEATHER_RAIN;season=1;condition=2;
  glUseProgram_c(7);assert(climate_sets==6 && climate_applied[0]==2);
  assert(climate_applied[1]==1 && climate_applied[3]==1);
  weather=NX_WEATHER_CLOUDY;
  glUseProgram_c(7);assert(climate_sets==7 && climate_applied[0]==1);
  weather=NX_WEATHER_FINE;
  glUseProgram_c(7);assert(climate_sets==8 && climate_applied[0]==0);
  assert(climate_applied[3]==1); // wet Fine never implies haze/snow
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
        for reset in ('eglMakeCurrent_dedup','eglDestroyContext_cache'):
            self.assertIn('memset(roof_uniforms, 0, sizeof(roof_uniforms))',function(SOURCE,reset))

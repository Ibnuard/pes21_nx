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
ENVIRONMENT += (Path(__file__).resolve().parents[1]/'source/stadium_roof_profiles.h').read_text()
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
static int climate_sets, profile_sets, profile, light_sets;
static int shell_sets;
static int cloud_sets;static unsigned cloud_step;
static float cloud_phase,cloud_enabled;
static float shell_applied[16];
static unsigned weather, season, turf=1, condition=1;
static float applied, night_applied, day_applied;
static float climate_applied[4], profile_applied;
static float light_applied[12];
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
static unsigned pes_controller_cloud_shadow_step(void) {return cloud_step;}
static void glUseProgram(GLuint p) {(void)p; ++binds;}
static void glDeleteProgram(GLuint p) {(void)p;}
static GLint glGetUniformLocation(GLuint p, const char *name) {
  ++queries;
  if(!strcmp(name,"nxRoofDisabled"))return p==7 ? 2 : -1;
  if(!strcmp(name,"nxDayStadium"))return p==7 ? 4 : -1;
  if(!strcmp(name,"nxStadiumClimate"))return p==7 ? 5 : -1;
  if(!strcmp(name,"nxStadiumProfile"))return p==7 ? 6 : -1;
  if(!strcmp(name,"nxStadiumLight[0]"))return (p==7 || p==135) ? 7 : -1;
  if(!strcmp(name,"nxShellRoof[0]"))return p==7 ? 8 : -1;
  if(!strcmp(name,"nxCloudMotion"))return p==7 ? 9 : -1;
  assert(!strcmp(name,"nxNightIndirect")); return p==7 ? 3 : -1;
}
static void glUniform1f(GLint loc, float value) {
  if(loc==2) {++sets;applied=value;}
  else if(loc==4) {++day_sets;day_applied=value;}
  else if(loc==6) {++profile_sets;profile_applied=value;}
  else {assert(loc==3);++night_sets;night_applied=value;}
}
static void glUniform2f(GLint loc,float phase,float enabled) {
 assert(loc==9);++cloud_sets;cloud_phase=phase;cloud_enabled=enabled;
}
static void glUniform4fv(GLint loc, int count, const GLfloat *value) {
  if(loc==8) {assert(count==4);++shell_sets;memcpy(shell_applied,value,sizeof(shell_applied));return;}
  if(loc==7) {
    assert(count==3);++light_sets;memcpy(light_applied,value,sizeof(light_applied));return;
  }
  assert(loc==5 && count==1);++climate_sets;
  memcpy(climate_applied,value,sizeof(climate_applied));
}
''' + function(SOURCE,'glUseProgram_c') + function(SOURCE,'glDeleteProgram_c') + r'''
int main(void) {
  glUseProgram_c(7); assert(applied==0 && binds==1 && queries==8);
  assert(light_sets==1 && light_applied[0]==1 && light_applied[6]==1);
  assert(night_sets==1 && night_applied==0);
  assert(day_sets==1 && day_applied==1);
  assert(climate_sets==1 && profile_sets==1 && profile_applied==0);
  for(int i=0;i<4;i++)assert(climate_applied[i]==0);
  enabled=0; glUseProgram_c(7); assert(applied==1 && binds==2 && queries==8);
  assert(night_sets==1);
  day=0; glUseProgram_c(7); assert(applied==0 && binds==3 && queries==8);
  assert(light_sets==2); // time change uploads even with identical climate key
  assert(night_sets==2 && night_applied==1);
  assert(day_sets==2 && day_applied==0);
  day=1; enabled=1; glUseProgram_c(7); assert(applied==0);
  assert(night_sets==3 && night_applied==0);
  glUseProgram_c(9); assert(sets==3);
  const int stable_light_sets=light_sets;
  const int stable_shell_sets=shell_sets;
  for(int n=0;n<1000;n++)glUseProgram_c(7);
  assert(sets==3); // unchanged roof setting never resubmitted per draw
  assert(light_sets==stable_light_sets);
  assert(shell_sets==stable_shell_sets); // geometry upload is never per draw
  glDeleteProgram_c(7); glUseProgram_c(7); assert(queries==24 && night_sets==4);
  high=0;day=0;glUseProgram_c(7);assert(night_applied==0 && night_sets==4);
  high=1;glUseProgram_c(7);assert(night_applied==1 && night_sets==5);
  assert(climate_sets==2 && profile_sets==2);
  weather=season=1;turf=0;condition=2;profile=1;
  glUseProgram_c(7);
  assert(climate_sets==3 && profile_sets==3 && profile_applied==1);
  assert(climate_applied[0]==1 && climate_applied[1]==1);
  assert(climate_applied[2]==-1 && climate_applied[3]==1);
  glUseProgram_c(7);assert(climate_sets==3 && profile_sets==3 && queries==24);
  float expected_light[12];stadium_environment_light_uniform(climate_applied,high && day,expected_light);
  assert(!memcmp(expected_light,light_applied,sizeof(expected_light)));
  weather=season=0;turf=condition=1;profile=0;
  glUseProgram_c(7);assert(climate_sets==4 && profile_sets==4);
  for(int i=0;i<4;i++)assert(climate_applied[i]==0);
  glUseProgram_c(0); assert(queries==24);
  // Relink/delete on the upload context invalidates this thread's locations.
  __atomic_add_fetch(&gl_program_generation,1,__ATOMIC_RELEASE);
  glUseProgram_c(7); assert(queries==32 && climate_sets==5);
  // Reused program distinguishes Rainy from Cloudy, even with Wet selected.
  weather=NX_WEATHER_RAIN;season=1;condition=2;
  glUseProgram_c(7);assert(climate_sets==6 && climate_applied[0]==2);
  assert(climate_applied[1]==1 && climate_applied[3]==1);
  weather=NX_WEATHER_CLOUDY;
  glUseProgram_c(7);assert(climate_sets==7 && climate_applied[0]==1);
  weather=NX_WEATHER_FINE;
  glUseProgram_c(7);assert(climate_sets==8 && climate_applied[0]==0);
  assert(climate_applied[3]==1); // wet Fine never implies haze/snow
  // Programs sharing a bucket must not keep querying and uploading on every
  // switch. This reproduces the old direct-mapped cache's collision pattern.
  const unsigned colliding[4]={7,135,263,391};
  for(unsigned i=0;i<4;i++)glUseProgram_c(colliding[i]);
  const int warm_queries=queries,warm_lights=light_sets,warm_climate=climate_sets;
  const int warm_binds=binds;
  for(unsigned i=0;i<4000;i++)glUseProgram_c(colliding[i%4]);
  assert(queries==warm_queries && light_sets==warm_lights && climate_sets==warm_climate);
  assert(binds==warm_binds+4000); // acquire native shared-program updates every time
  // A program can retain only precomputed light after GLSL optimization.
  weather=NX_WEATHER_RAIN;season=0;day=1;glUseProgram_c(135);
  assert(light_sets==warm_lights+1 && climate_sets==warm_climate);
  assert(light_applied[0]<.53f && light_applied[4]>.92f);
  day=0;glUseProgram_c(135);assert(light_sets==warm_lights+2);
  assert(light_applied[0]==.84f && light_applied[4]==.84f);
  // Fifth collision may evict an entry, but reacquiring it re-uploads current
  // values. Deletion/relink invalidation still crosses shared contexts.
  glUseProgram_c(519);glUseProgram_c(7);
  assert(queries>warm_queries && climate_sets==warm_climate+1);
  glDeleteProgram_c(135);glUseProgram_c(135);
  assert(light_applied[0]==.84f);
  // Sparse installed menus resolve to a stable stadium ID before upload.
  for(profile=2;profile<14;profile++) {
    const int before=shell_sets;
    glUseProgram_c(7);
    float expected[16];stadium_roof_uniform_season(profile,season,expected);
    assert(!memcmp(expected,shell_applied,sizeof(expected)) && shell_sets==before+1);
    assert(shell_applied[3]>1500 && shell_applied[3]<8000);
    if(profile==12)assert(shell_applied[7]==-50 && shell_applied[11]==-1850);
    for(int draw=0;draw<1000;draw++)glUseProgram_c(7);
    assert(shell_sets==before+1);
  }
  profile=13;season=1;
  const int before_winter=shell_sets;
  glUseProgram_c(7);assert(shell_sets==before_winter+1 && shell_applied[9]==-1550);
  for(int draw=0;draw<2000;draw++)glUseProgram_c(7);
  assert(shell_sets==before_winter+1);
  weather=NX_WEATHER_CLOUDY;glUseProgram_c(7);
  assert(shell_sets==before_winter+1); // weather does not resubmit geometry
  season=0;glUseProgram_c(7);
  assert(shell_sets==before_winter+2 && shell_applied[9]==-2200);
  // Cloud phase uploads only when its quarter-second step changes. Reused
  // draws, Night, Fine, Rainy and programs with no pitch receiver stay quiet.
  day=1;weather=NX_WEATHER_CLOUDY;cloud_step=120;glUseProgram_c(7);
  assert(cloud_enabled==1 && cloud_phase==.25f);
  const int before_cloud=cloud_sets;
  for(int draw=0;draw<4000;draw++)glUseProgram_c(7);
  assert(cloud_sets==before_cloud);
  cloud_step++;glUseProgram_c(7);assert(cloud_sets==before_cloud+1);
  day=0;glUseProgram_c(7);assert(cloud_enabled==0);
  const int at_night=cloud_sets;
  cloud_step++;glUseProgram_c(7);assert(cloud_sets==at_night);
  day=1;weather=NX_WEATHER_RAIN;glUseProgram_c(7);assert(cloud_sets==at_night);
  weather=NX_WEATHER_FINE;glUseProgram_c(7);assert(cloud_sets==at_night);
  weather=NX_WEATHER_CLOUDY;glUseProgram_c(135);assert(cloud_sets==at_night);
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

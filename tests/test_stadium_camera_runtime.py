"""Execute the real acquisition adapter inside the real Update wrapper.

Only engine-boundary functions are simulated. Native geometry/optics output is
an arbitrary byte pattern so overwriting a final pose cannot pass unnoticed.
"""
from pathlib import Path
import shutil
import unittest
from test_result_flow import build_and_run, function

ROOT = Path(__file__).resolve().parents[1]


class StadiumRuntimeTests(unittest.TestCase):
    def test_native_update_refreshes_registry_before_target_correction(self):
        cc = shutil.which('gcc')
        if not cc:
            self.skipTest('requires installed host gcc')
        source = (ROOT/'source/ue4_hooks.c').read_text()
        update = function(source, 'pes_inplay_camera_update')
        target_callback = function(source, 'pes_stadium_v2_target')
        self.assertIn('stadium_camera_begin(camera, parameter)', update)
        self.assertIn('stadium_camera_end()', update)
        include = (ROOT/'source/stadium_camera_runtime.inc').as_posix()
        v2_header = (ROOT/'source/stadium_v2_camera.h').as_posix()
        build_and_run(cc, r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <stddef.h>
static uint32_t pause_camera_stadium_v2, pause_camera_dynamic_wide_custom;
static unsigned live_surface=1, tmpdb_type=12, have_tmpdb=1;
static unsigned calls, composed;
static unsigned char match_info[0x1200];
static float sampled_ball[3], last_target[3];
static const float acquired[3]={24.f,.2f,9.f};
static float native_pose[16];
static int pes_controller_match_hud_inplay(void) {return live_surface;}
static unsigned char *pause_settings_tmpdb_camera(uint8_t *type) {
  static unsigned char tmpdb;
  *type=(uint8_t)tmpdb_type;
  return have_tmpdb?&tmpdb:NULL;
}
#include "''' + include + r'''"
#include "''' + v2_header + r'''"
typedef struct {
  StadiumV2Camera motion;
  uintptr_t owner;
  unsigned active,target_ready;
} StadiumV2Scope;
static StadiumV2Scope stadium_v2_scope;
''' + target_callback + r'''
static void original(void *camera,void *parameter) {
  ++calls;
  // The real native Update obtains its MatchInfo copy AFTER wrapper entry.
  const void *copy=match_info;
  if(camera) memcpy((char*)camera+0x238,&copy,sizeof(copy));
  memcpy(last_target,acquired,sizeof(last_target));
  pes_stadium_v2_target(camera,last_target,sampled_ball);
  if(parameter) memcpy(parameter,native_pose,sizeof(native_pose));
}
static void (*match_inplay_camera_update_original)(void*,void*)=original;
static unsigned footballnx_tribune_view(float *p) {++composed; p[13]=.75f; return 1;}
''' + update + r'''
int main(void) {
  unsigned char camera[0x300]={0}, parameter[0x60]={0};
  uint32_t phase=1; memcpy(match_info+0x116c,&phase,sizeof(phase));
  for(unsigned n=0;n<16;++n) native_pose[n]=100.f+(float)n;
  const float samples[][3]={{-51,1.5f,2},{51,1.5f,-2},{-48,.5f,1},{4,.2f,-14}};
  for(unsigned k=0;k<4;++k) for(unsigned id=0;id<14;++id)
  for(unsigned custom=0;custom<2;++custom) {
    memcpy(sampled_ball,samples[k],sizeof(sampled_ball));
    memcpy(camera+8,&id,sizeof(id));
    memset(camera+0x238,0,sizeof(void*));
    pause_camera_dynamic_wide_custom=custom;
    unsigned before=calls, painted=composed;
    pes_inplay_camera_update(camera,parameter);
    assert(calls==before+1 && !stadium_camera_scope.active && !stadium_camera_scope.owner);
    assert(!memcmp(last_target,id==6?sampled_ball:acquired,sizeof(last_target)));
    assert(composed==painted+(id==5 && custom));
    for(unsigned n=0;n<16;++n) {
      float value;memcpy(&value,parameter+n*sizeof(float),sizeof(value));
      assert(value==((id==5 && custom && n==13)?.75f:native_pose[n]));
    }
  }
  unsigned id=6; memcpy(camera+8,&id,sizeof(id));
  pause_camera_dynamic_wide_custom=0;
  for(unsigned context=0;context<7;++context) {
    live_surface=1;tmpdb_type=12;have_tmpdb=1;phase=1;pause_camera_stadium_v2=0;
    uint32_t follow=0;
    switch(context) {
      case 0: live_surface=0; break; // replay, demos, pause, stale HUD etc.
      case 1: tmpdb_type=5; break;
      case 2: have_tmpdb=0; break;
      case 3: phase=3; break; // set-piece owner
      case 4: pause_camera_stadium_v2=1; break;
      case 5: follow=1; break;
      case 6: phase=2; break; // non-live transition
    }
    memcpy(parameter+0x48,&follow,sizeof(follow));
    memcpy(match_info+0x116c,&phase,sizeof(phase));
    pes_inplay_camera_update(camera,parameter);
    assert(!memcmp(last_target,acquired,sizeof(last_target)));
    assert(!stadium_camera_scope.active && !stadium_camera_scope.owner);
  }
  live_surface=1;tmpdb_type=12;have_tmpdb=1;phase=1;pause_camera_stadium_v2=0;
  uint32_t follow=0;
  memcpy(parameter+0x48,&follow,sizeof(follow));
  memcpy(match_info+0x116c,&phase,sizeof(phase));
  sampled_ball[0]=NAN;
  pes_inplay_camera_update(camera,parameter);
  assert(!memcmp(last_target,acquired,sizeof(last_target)));
  assert(!stadium_camera_scope.active && !stadium_camera_scope.owner);
  sampled_ball[0]=2;
  pes_inplay_camera_update(NULL,parameter);
  pes_inplay_camera_update(camera,NULL);
  assert(!stadium_camera_scope.active && !stadium_camera_scope.owner);
  match_inplay_camera_update_original=NULL;
  pes_inplay_camera_update(camera,parameter);
  assert(!stadium_camera_scope.active && !stadium_camera_scope.owner);
  return 0;
}
''')


if __name__ == '__main__':
    unittest.main()

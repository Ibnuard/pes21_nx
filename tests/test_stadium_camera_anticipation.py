"""Native composition is retained: no final eye translation or global AI patch."""
from pathlib import Path
import shutil
import unittest
from test_result_flow import build_and_run, function

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'source/ue4_hooks.c').read_text()


class AnticipationTests(unittest.TestCase):
    def run_c(self, text):
        cc = shutil.which('gcc')
        if not cc:
            self.skipTest('gcc unavailable')
        build_and_run(cc, r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <string.h>
''' + text)

    def test_pose_stays_native_even_at_near_touchline(self):
        self.run_c(r'''
static __thread struct {void *camera;float ball[3];uint32_t ready,sampled;} match_broadcast_frame;
static uint32_t pause_camera_dynamic_wide_custom;
static unsigned mode,original_calls;
static const float native_pose[8]={2.4f,.5f,14.4f,.94f,22.5f,70.f,55.f,1.f};
static void native_update(void *camera,void *parameter) {
  ++original_calls;
  assert(!match_broadcast_frame.sampled && !match_broadcast_frame.ready);
  assert(match_broadcast_frame.camera==camera);
  memcpy(parameter,native_pose,sizeof(native_pose));
  if (mode==0) return;
  match_broadcast_frame.sampled=1;match_broadcast_frame.ready=mode!=2;
  match_broadcast_frame.ball[0]=-5.f;match_broadcast_frame.ball[2]=29.f;
}
static void (*match_inplay_camera_update_original)(void*,void*)=native_update;
static uint32_t footballnx_tribune_view(float *p) {assert(0);return 0;}
''' + function(SOURCE, 'pes_inplay_camera_update') + r'''
int main(void) {
  unsigned char camera[32]={0};float p[8]={0};
  for (mode=0;mode<3;++mode) {
    match_broadcast_frame.camera=camera;
    match_broadcast_frame.sampled=match_broadcast_frame.ready=1;
    pes_inplay_camera_update(camera,p);
    assert(!memcmp(p,native_pose,sizeof(p))); // eye Z must stay 70, not 80
    assert(!match_broadcast_frame.sampled && !match_broadcast_frame.camera);
  }
  assert(original_calls==3);
}
''')

    def test_native_future_vector_and_shared_trace_are_not_hooked(self):
        # This value doubles as a speed cap for selected touch kinds near
        # midfield. A zero vector is NOT equivalent to no camera prediction.
        self.assertNotIn('pes_broadcast_future_move(', SOURCE)
        self.assertNotIn('hook_arm64(future_move_plt', SOURCE)
        self.assertNotIn('module->load_base + 0x37ec320', SOURCE)
        self.assertNotIn('hook_arm64(gc_view_trace', SOURCE)

    def test_fixed_footballnx_angle_does_not_follow_stale_custom_values(self):
        body = function(SOURCE, 'pes_inplay_camera_update')
        self.assertIn('footballnx_tribune_view((float *)parameter)', body)
        self.assertNotIn('camera + 0x14', body)

    def test_native_ball_route_preserves_camera_flags_and_other_camera_types(self):
        self.run_c(r'''
static uint32_t match_broadcast_anticipation_enabled;
static __thread struct {void *camera;float ball[3];uint32_t ready,sampled;} match_broadcast_frame;
''' + function(SOURCE, 'pes_stadium_ball_target_mode') + r'''
int main(void) {
  unsigned char camera[64]={0},before[64];
  for(unsigned id=0;id<14;id++) for(unsigned bits=0;bits<16;bits++) {
    memcpy(camera+8,&id,4);camera[0x24]=(bits&1)?3:0;
    match_broadcast_frame.camera=(bits&2)?camera:0;
    match_broadcast_frame.ready=!!(bits&4);
    match_broadcast_anticipation_enabled=!!(bits&8);
    memcpy(before,camera,64);
    unsigned override=id==6 && (bits&2) && (bits&4) && (bits&8);
    assert(pes_stadium_ball_target_mode(camera)==(override?1:camera[0x24]));
    assert(!memcmp(before,camera,64));
  }
  assert(!pes_stadium_ball_target_mode(0));
}
''')

    def test_no_final_pose_bias_and_native_camera_pipeline_is_preserved(self):
        self.assertNotIn('match_broadcast_stabilize_final', SOURCE)
        wrapper=function(SOURCE,'pes_inplay_camera_update')
        self.assertNotIn('limit_anticipation(',wrapper)
        self.assertIn('match_inplay_camera_update_original(camera, parameter)',wrapper)
        self.assertIn('footballnx_tribune_view((float *)parameter)',wrapper)

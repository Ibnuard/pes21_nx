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
static uint32_t pause_dynamic_wide_apply_angle(float *p,float angle) {assert(0);return 0;}
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
        self.assertIn('const float panning = 0.6f', body)
        self.assertNotIn('camera + 0x14', body)

    def test_horizontal_soft_limit_not_a_ball_lock_and_preserves_native_z(self):
        self.run_c(function(SOURCE, 'match_broadcast_limit_anticipation') + r'''
int main(void) {
  const float ball[3]={20.f,.1f,29.f};
  float natural[3]={16.f,.5f,14.f};
  assert(!match_broadcast_limit_anticipation(natural,ball));
  float lead[3]={0.f,.5f,14.f};
  assert(match_broadcast_limit_anticipation(lead,ball));
  assert(lead[0]>10 && lead[0]<14); // not locked to ball X=20
  assert(lead[1]==.5f && lead[2]==14.f);
  float prev=0;
  for (unsigned i=0;i<4000;++i) {
    float b[3]={0,0,0},p[3]={i*.01f,7,19};
    match_broadcast_limit_anticipation(p,b);
    assert(p[0]>=prev && p[0]-prev<=.01001f); // continuous, no deadzone snap
    assert(p[1]==7 && p[2]==19 && p[0]<=10.001f);
    prev=p[0];
  }
}
''')

    def test_no_final_pose_bias_and_native_camera_pipeline_is_preserved(self):
        self.assertNotIn('match_broadcast_stabilize_final', SOURCE)
        wrapper=function(SOURCE,'pes_inplay_camera_update')
        self.assertNotIn('limit_anticipation(',wrapper)
        self.assertIn('match_inplay_camera_update_original(camera, parameter)',wrapper)
        self.assertIn('pause_dynamic_wide_apply_angle((float *)parameter, panning)',wrapper)

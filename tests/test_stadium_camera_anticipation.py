"""Native camera ownership when Stadium V2 is off; no shared predictor patches."""
from pathlib import Path
import shutil
import unittest
from test_result_flow import build_and_run, function

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'source/ue4_hooks.c').read_text()


class AnticipationTests(unittest.TestCase):
    def test_native_pose_survives_every_preset_and_custom_flag(self):
        cc = shutil.which('gcc')
        if not cc:
            self.skipTest('gcc unavailable')
        build_and_run(cc, r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
static uint32_t pause_camera_dynamic_wide_custom;
static unsigned original_calls, composed;
static float native_pose[16];
static void native_update(void *camera, void *parameter) {
  ++original_calls;
  if (parameter) memcpy(parameter,native_pose,sizeof(native_pose));
}
static void (*match_inplay_camera_update_original)(void*,void*)=native_update;
static unsigned footballnx_tribune_view(float *p) {++composed; p[13]=.75f; return 1;}
static void stadium_v2_begin(void *c,void *p) {(void)c;(void)p;} // V2 disabled; adapter tested separately.
static void stadium_v2_end(void) {}
// This test isolates final-pose ownership; acquisition is exercised by the
// real normal-Stadium adapter in test_stadium_camera_runtime.py.
static void stadium_camera_begin(void *c,void *p) {(void)c;(void)p;}
static void stadium_camera_end(void) {}
''' + function(SOURCE, 'pes_inplay_camera_update') + r'''
int main(void) {
  unsigned char camera[32]={0}; float p[16];
  // Includes static kickoff, either touchline, high ball and both goals.
  for(unsigned sample=0; sample<9; ++sample) {
    for(unsigned i=0;i<16;++i) native_pose[i]=(float)(sample*16+i);
    for(unsigned custom=0;custom<2;++custom) for(unsigned id=0;id<14;++id) {
      memcpy(camera+8,&id,4); pause_camera_dynamic_wide_custom=custom;
      unsigned before=composed;
      pes_inplay_camera_update(camera,p);
      assert(composed==before+(custom && id==5));
      for(unsigned i=0;i<16;++i)
        assert(p[i]==((custom && id==5 && i==13)?.75f:native_pose[i]));
    }
  }
  assert(original_calls==9*2*14);
  unsigned before=composed;
  pes_inplay_camera_update(NULL,p);
  pes_inplay_camera_update(camera,NULL);
  assert(composed==before);
}
''')

    def test_no_additional_camera_ball_path_is_installed(self):
        for removed in ('pes_inplay_ball_position_broadcast',
                        'match_broadcast_ball_tracking_ready',
                        'pes_stadium_ball_target_mode', 'match_broadcast_frame',
                        'stadium_ball_target_live_resume'):
            self.assertNotIn(removed, SOURCE)
        assembly = (ROOT / 'source/cobra_pad_hook.s').read_text()
        self.assertNotIn('pes_inplay_ball_position_broadcast_original', assembly)
        self.assertFalse((ROOT / 'source/stadium_target_hook.s').exists())
        update = function(SOURCE, 'pes_inplay_camera_update')
        self.assertNotIn('match_ball_info_get_trans', update)
        self.assertNotIn('memset', update)
        self.assertEqual(update.count('match_inplay_camera_update_original(camera, parameter)'), 1)

    def test_native_future_vector_is_not_hooked(self):
        for removed in ('pes_broadcast_future_move(', 'hook_arm64(future_move_plt',
                        'module->load_base + 0x37ec320',
                        'hook_arm64(ball_position_broadcast'):
            self.assertNotIn(removed, SOURCE)

    def test_stadium_registry_height_is_not_forced(self):
        conversion = function(SOURCE, 'pause_set_tmpdb_camera_settings')
        self.assertNotIn('type == 12u', conversion)
        self.assertNotIn('fixed[copies', conversion)
        self.assertIn('pause_set_tmpdb_camera_original(registry_camera, tmpdb_camera,', conversion)
        self.assertIn('if (tmpdb[0] != 5u)', conversion)

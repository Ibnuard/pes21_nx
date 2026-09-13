"""Run the actual horizontal profile -> native camera input pipeline."""
from pathlib import Path
import re
import shutil
import unittest
from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]

class SingleJoyCameraTests(unittest.TestCase):
    def test_rotated_left_and_right_joycon_sticks_route_to_camera(self):
        cc = shutil.which('gcc')
        if not cc: self.skipTest('host gcc unavailable')
        shim = (ROOT / 'source/android_shim.c').read_text()
        native = (ROOT / 'source/native_pad_lab.inc').read_text()
        code = r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef uint64_t u64;
typedef uint32_t u32;
typedef struct { int32_t x,y; } HidAnalogStickState;
typedef enum { CONTROLLER_PROFILE_FULL, CONTROLLER_PROFILE_SINGLE_LEFT, CONTROLLER_PROFILE_SINGLE_RIGHT } ControllerProfile;
#define PES_CONTROLLER_PROFILE_FULL 0
static uint32_t profiles[2];
static int active=1;
static uint32_t native_lab_debug_context=2, native_lab_debug_stock_mask=0;
static uint32_t native_lab_debug_setplay_pad=0, native_lab_single_camera_mask;
#define PES_SETPLAY_GOAL_KICK 1
#define PES_SETPLAY_CORNER 2
#define PES_SETPLAY_FREE_KICK 3
#define PES_NATIVE_LAB_STOCK_FREEKICK_TACTICS 1
#define PES_NATIVE_LAB_STOCK_FREEKICK_POSITION 2
#define PES_PENALTY_NONE 0
static uint32_t penalty[2];
static uint32_t pes_controller_penalty_role_for_pad(uint32_t p) { return penalty[p]; }
static uint32_t android_controller_profile(uint32_t p) { return profiles[p]; }
static int pes_controller_native_pad_lab_active(void) { return active; }
static int32_t captured[2][4];
static uint32_t keys[2];
static void pes_controller_native_pad_lab_debug_input(uint32_t p,uint32_t k,int32_t x,int32_t y,int32_t rx,int32_t ry,int connected) {
  keys[p]=k; captured[p][0]=x;captured[p][1]=y;captured[p][2]=rx;captured[p][3]=ry;
  if(!connected) assert(!x && !y && !rx && !ry);
}
static void cobra_pad_set_native_input_for_port(uint32_t p,uint32_t k,int32_t up,int32_t down,int32_t left,int32_t right,int32_t rup,int32_t rdown,int32_t rleft,int32_t rright,int connected) {
  (void)connected; assert(k==keys[p]);
  assert(right-left==captured[p][0] && up-down==captured[p][1]);
  assert(rright-rleft==captured[p][2] && rup-rdown==captured[p][3]);
}
'''
        buttons = ['B','A','Y','X','L','ZL','StickL','R','ZR','StickR','Up','Down','Left','Right','Plus','Minus','AnySL','AnySR']
        code += '\n'.join(f'#define HidNpadButton_{b} (1ULL << {i})' for i,b in enumerate(buttons))+'\n'
        styles = ['NpadFullKey','NpadHandheld','NpadJoyDual','NpadJoyLeft','NpadJoyRight']
        code += '\n'.join(f'#define HidNpadStyleTag_{s} (1u << {i})' for i,s in enumerate(styles))+'\n'
        for name in ['controller_profile_from_style','controller_profile_map_stick','native_lab_map_hid_buttons']:
            code += function(shim,name)+'\n'
        code += function(native,'pes_controller_native_pad_lab_route_camera_stick')+'\n'
        code += function(shim,'emit_native_lab_pad_input')+'\n'
        code += r'''
int main(void) {
  assert(controller_profile_from_style(HidNpadStyleTag_NpadJoyDual|HidNpadStyleTag_NpadJoyLeft)==CONTROLLER_PROFILE_FULL);
  for(unsigned p=0;p<2;p++) for(unsigned side=1;side<=2;side++) {
    native_lab_debug_setplay_pad=p;
    profiles[p]=controller_profile_from_style(side==1 ? HidNpadStyleTag_NpadJoyLeft : HidNpadStyleTag_NpadJoyRight);
    assert(profiles[p]==side);
    HidAnalogStickState ls={12000,16000},rs={12000,16000}; int have_l=1,have_r=1;
    controller_profile_map_stick(profiles[p],&ls,&have_l,&rs,&have_r);
    assert(have_l && !have_r && rs.x==0 && rs.y==0);
    assert(ls.x==(side==1 ? -16000 : 16000) && ls.y==(side==1 ? 12000 : -12000));
    const u64 shoulders[]={HidNpadButton_R,HidNpadButton_AnySR};
    for(unsigned i=0;i<2;i++) {
      emit_native_lab_pad_input(p,&ls,&rs,1,shoulders[i]|HidNpadButton_Y);
      assert(captured[p][0]==0 && captured[p][1]==0);
      assert(captured[p][2]==ls.x && captured[p][3]==ls.y && keys[p]==4);
    }
    emit_native_lab_pad_input(p,&ls,&rs,1,0);
    assert(captured[p][0]==ls.x && captured[p][1]==ls.y && captured[p][2]==0 && captured[p][3]==0);
    emit_native_lab_pad_input(p,&ls,&rs,1,HidNpadButton_AnySL|HidNpadButton_AnySR);
    assert(captured[p][0]==ls.x && captured[p][2]==0); // taker chord wins
    penalty[p]=1;
    emit_native_lab_pad_input(p,&ls,&rs,1,HidNpadButton_R);
    assert(captured[p][0]==ls.x && captured[p][2]==0); // penalty never remapped
    penalty[p]=0;
    emit_native_lab_pad_input(p,&ls,&rs,0,HidNpadButton_R);
    assert(!(native_lab_single_camera_mask & (1u<<p)));
  }
  profiles[0]=CONTROLLER_PROFILE_FULL; native_lab_debug_setplay_pad=0;
  HidAnalogStickState ls={10000,20000},rs={-13000,14000};
  emit_native_lab_pad_input(0,&ls,&rs,1,HidNpadButton_R);
  assert(captured[0][0]==10000 && captured[0][1]==20000 && captured[0][2]==-13000 && captured[0][3]==14000);
}
'''
        build_and_run(cc, code)

    def test_helper_changes_with_setplay_owner_profile(self):
        overlay = (ROOT/'source/overlay.c').read_text()
        self.assertIn('single_joy_setplay ? "SR+LS" : "RS"', overlay)
        self.assertIn('camera ? "SR"', overlay)
        self.assertIn('camera ? "LS"', overlay)
        self.assertIn('"HOLD: CAMERA / AIM"', overlay)

if __name__ == '__main__': unittest.main()

"""Executable regressions for stamina snapshots and set-piece aim/curve."""
from pathlib import Path
import shutil
import unittest
from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]

class OnfieldTests(unittest.TestCase):
    def setUp(self):
        self.cc = shutil.which("gcc")
        if not self.cc: self.skipTest("host gcc unavailable")

    def test_height_intent_and_native_pitch_owner(self):
        route = (ROOT / 'source/native_pad_lab.inc').read_text()
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
''' + f'#include "{(ROOT / "source/setplay_aim.h").as_posix()}"\n' + r'''
#define NATIVE_LAB_TRAJECTORY_MAX_ELEVATION_DEGREES 18.0f
#define PES_SETPLAY_CORNER 2
#define PES_SETPLAY_FREE_KICK 3
static uint32_t native_lab_free_kick_elevation_mask=1;
static uint32_t native_lab_free_kick_elevation_linger[2]={120,0};
static uint32_t native_lab_free_kick_elevation_bits[2];
static uint32_t native_lab_setplay_flight_curl_bits[2];
static uint32_t native_lab_setplay_flight_context[2];
static uint32_t native_lab_free_kick_player[2]={4,17};
static void (*native_lab_ball_injection_original)(const void*,void*,void*);
''' + function(route, 'native_lab_ball_injection') + r'''
int main(void) {
  assert(pes_setplay_height_intent(0,1));
  assert(pes_setplay_height_intent(0,-1));
  assert(!pes_setplay_height_intent(1,.4f));
  assert(!pes_setplay_height_intent(-1,-.4f));
  assert(!pes_setplay_height_intent(0,0));
  unsigned char input[64]={0};
  float pitch=18, curl=.5f, speed[3]={0,0,20}, rotation[3]={1,0,3};
  memcpy(native_lab_free_kick_elevation_bits,&pitch,4);
  memcpy(native_lab_setplay_flight_curl_bits,&curl,4);
  native_lab_setplay_flight_context[0]=2;
  uint32_t player=17; memcpy(input+0x30,&player,4);
  native_lab_ball_injection(input,speed,rotation);
  assert(speed[1]==0 && native_lab_free_kick_elevation_linger[0]==120);
  player=4; memcpy(input+0x30,&player,4);
  native_lab_ball_injection(input,speed,rotation);
  assert(speed[1]==0 && speed[0]==0 && speed[2]==20);
  assert(rotation[0]==1 && rotation[1]>1.49f && rotation[1]<1.51f && rotation[2]==3);
  native_lab_setplay_flight_context[0]=PES_SETPLAY_FREE_KICK;
  rotation[1]=0;
  native_lab_ball_injection(input,speed,rotation);
  assert(rotation[1]>1.49f && rotation[1]<1.51f);
  speed[1]=.324f; rotation[1]=-12.0f;
  native_lab_ball_injection(input,speed,rotation);
  assert(speed[1]==.324f && rotation[1]>-10.51f && rotation[1]<-10.49f);
  assert(native_lab_free_kick_elevation_linger[0]==120);
  native_lab_free_kick_elevation_mask=0; speed[1]=0;
  native_lab_ball_injection(input,speed,rotation); assert(speed[1]==0);
}
'''
        build_and_run(self.cc, code)

    def test_stamina_overlay_snapshot_abi_is_disabled(self):
        hooks = (ROOT / "source/ue4_hooks.c").read_text()
        header = (ROOT / "source/ue4_hooks.h").read_text()
        typedef = header[header.index("typedef struct {\n  float x;"):
                         header.index("} PesStaminaBarSnapshot;") +
                         len("} PesStaminaBarSnapshot;")]
        code = r'''
#include <assert.h>
#include <stdint.h>
''' + typedef + "\n" + function(hooks, "pes_controller_stamina_bars") + r'''
int main(void) {
  PesStaminaBarSnapshot bars[4]={{0}};
  assert(pes_controller_stamina_bars(bars,4)==0);
  assert(pes_controller_stamina_bars(0,0)==0);
}
'''
        build_and_run(self.cc, code)
        self.assertNotIn('pause_stamina_get_model_original', hooks)
        self.assertNotIn('pause_stamina_hud_power_milli', hooks)
        self.assertNotIn('_ZN7UCanvas8DrawItemER11FCanvasItem', hooks)

    def test_native_stamina_draw_is_not_intercepted(self):
        hooks = (ROOT / "source/ue4_hooks.c").read_text()
        install = hooks.split('void install_ue4_hooks', 1)[1]
        self.assertNotIn('ModelStaminaGauge8GetModel', install)
        self.assertNotIn('Model2DData4Draw', install)
        self.assertNotIn('stamina_draw_plt', install)

    def test_native_stamina_slots_put_live_fill_after_dark_track(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
        install = hooks.split('void install_ue4_hooks', 1)[1]
        self.assertIn('stamina_color_code + 0xc0, 0x54000229, 0x54000228',
                      install)
        self.assertIn('stamina_exec_code + 0xe8, 0x540001a8, 0x540001a9',
                      install)
        self.assertIn('stamina_exec_code + 0xec, 0x8b354a94, 0x8b394a94',
                      install)
        self.assertNotIn('_ZN7UCanvas8DrawItemER11FCanvasItem', install)
        self.assertNotIn('PES_STAMINA_FILL_SCALE_Y', hooks)

    def test_custom_stamina_hud_is_removed(self):
        overlay = (ROOT / "source/overlay.c").read_text()
        self.assertNotIn('stamina_outline_first_quad', overlay)
        self.assertNotIn('stamina_track_first_quad', overlay)
        self.assertNotIn('stamina_fill_first_quad', overlay)
        self.assertNotIn('pes_controller_stamina_bars(', overlay)


    def test_buffer_matches_engine_request_even_with_720p_config(self):
        shim = (ROOT / "source/libc_shim.c").read_text()
        block = function(shim, "ANativeWindow_setBuffersGeometry_fake")
        code = r'''
#include <assert.h>
typedef void NWindow;
static int screen_width=1280, screen_height=720, buffer_w,buffer_h;
#define debugPrintf(...) ((void)0)
static void nwindowSetDimensions(NWindow *win,int w,int h) {
  buffer_w=w; buffer_h=h;
}
''' + block + r'''
int main(void) {
  ANativeWindow_setBuffersGeometry_fake(0,1024,576,0);
  assert(buffer_w==1024 && buffer_h==576);
  ANativeWindow_setBuffersGeometry_fake(0,1280,720,0);
  assert(buffer_w==1280 && buffer_h==720);
  ANativeWindow_setBuffersGeometry_fake(0,1024,540,0);
  assert(buffer_w==1024 && buffer_h==540);
  ANativeWindow_setBuffersGeometry_fake(0,0,0,0);
  assert(buffer_w==1280 && buffer_h==720);
}
'''
        build_and_run(self.cc, code)

    def test_projected_feet_use_native_display_units_at_each_resolution(self):
        hooks = (ROOT / "source/ue4_hooks.c").read_text()
        code = r'''
#include <assert.h>
#include <math.h>
static int screen_width=1280,screen_height=720;
''' + function(hooks, "match_gauge_project_to_overlay") + r'''
int main(void) {
  float x=472,y=280;
  assert(match_gauge_project_to_overlay(&x,&y,1024,576));
  assert(x==590 && y==350);
  x=512; y=270;
  assert(match_gauge_project_to_overlay(&x,&y,1024,540));
  assert(x==640 && y==360);
  x=640; y=360;
  assert(match_gauge_project_to_overlay(&x,&y,1280,720));
  assert(x==640 && y==360);
  screen_width=1024; screen_height=540; x=640; y=360;
  assert(match_gauge_project_to_overlay(&x,&y,1280,720));
  assert(x==512 && y==270);
  assert(!match_gauge_project_to_overlay(&x,&y,0,720));
  assert(!match_gauge_project_to_overlay(&x,&y,1280,NAN));
}
'''
        build_and_run(self.cc, code)
        producer = function(hooks, 'pes_match_cursor_name_get_position')
        self.assertIn('match_gauge_project_to_overlay(&screen_x, &screen_y', producer)
        self.assertIn('match_projection_display_width()', producer)

    def test_camera_heading_and_ls_curl_are_independent(self):
        route = (ROOT / "source/native_pad_lab.inc").read_text()
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
''' + f'#include "{(ROOT / "source/setplay_aim.h").as_posix()}"\n' + r'''
#define PES_SETPLAY_CORNER 2
#define PES_SETPLAY_GOAL_KICK 1
#define NATIVE_LAB_TRAJECTORY_MAX_ELEVATION_DEGREES 18.0f
static int32_t native_lab_camera_yaw_millirad[2];
static int32_t native_lab_debug_axis_x, native_lab_debug_axis_y;
static int32_t native_lab_debug_axis_x_p2, native_lab_debug_axis_y_p2;
static uint32_t native_lab_left_aim_latched_mask, native_lab_command_angle_valid_mask;
static uint32_t native_lab_command_vertical_bits[2], native_lab_command_angle_bits[2];
static uint32_t native_lab_command_curl_bits[2], native_lab_camera_heading_bits[2];
static uint32_t native_lab_camera_heading_mask;
static uint32_t native_lab_single_camera_mask;
static float (*native_lab_mobile_filter_angle_abi)(void*,const void*,float);
static float native_lab_stable_setplay_base_angle(uint32_t p,uint32_t n,float a,int *same) {
  (void)p;(void)n;(void)a;*same=1; return 90.0f;
}
''' + function(route, "native_lab_normalize_axis") + "\n" + function(route, "native_lab_apply_native_kick_angle") + r'''
static float field(unsigned char *p, unsigned off) { float v; memcpy(&v,p+off,4); return v; }
int main(void) {
  unsigned char unit[128]={0}, input[64]={0};
  float base=90; memcpy(unit+0x38,&base,4);
  for (unsigned pad=0;pad<2;pad++) {
    float heading=210; memcpy(&native_lab_camera_heading_bits[pad],&heading,4);
    native_lab_camera_heading_mask=1u<<pad;
    for(int sign=-1;sign<=1;sign++) {
      native_lab_command_curl_bits[pad]=0;
      native_lab_debug_axis_x=native_lab_debug_axis_x_p2=sign*32767;
      native_lab_debug_axis_y=native_lab_debug_axis_y_p2=0;
      native_lab_apply_native_kick_angle(unit,input,pad,PES_SETPLAY_CORNER);
      assert(fabsf(field(unit,0x38)-210)<.001f); // LS-X never rotates launch
      assert(fabsf(field(unit,0x48)-(sign?1:0))<.002f);
      assert(field(unit,0x44)==(sign<0?90:sign>0?270:0));
    }
    native_lab_debug_axis_x=native_lab_debug_axis_x_p2=32767;
    native_lab_debug_axis_y=native_lab_debug_axis_y_p2=-32767;
    native_lab_apply_native_kick_angle(unit,input,pad,PES_SETPLAY_CORNER);
    const uint32_t latched_curl=native_lab_command_curl_bits[pad];
    native_lab_debug_axis_x=native_lab_debug_axis_x_p2=0;
    native_lab_debug_axis_y=native_lab_debug_axis_y_p2=0;
    native_lab_apply_native_kick_angle(unit,input,pad,PES_SETPLAY_CORNER);
    assert(native_lab_command_curl_bits[pad]==latched_curl);
    assert(field(unit,0x44)==270 && field(unit,0x48)>.99f);
    heading=235; memcpy(&native_lab_camera_heading_bits[pad],&heading,4);
    native_lab_apply_native_kick_angle(unit,input,pad,PES_SETPLAY_CORNER);
    assert(fabsf(field(unit,0x38)-235)<.001f); // RS still moves aim after LS latch
    // Switching to single-stick camera mode preserves curl/height while the
    // routed LS is neutral, but still accepts the camera's changing heading.
    const uint32_t curl_before=native_lab_command_curl_bits[pad];
    const uint32_t height_before=native_lab_command_vertical_bits[pad];
    native_lab_single_camera_mask=1u<<pad;
    native_lab_debug_axis_x=native_lab_debug_axis_x_p2=0;
    native_lab_debug_axis_y=native_lab_debug_axis_y_p2=0;
    heading=240; memcpy(&native_lab_camera_heading_bits[pad],&heading,4);
    native_lab_apply_native_kick_angle(unit,input,pad,PES_SETPLAY_CORNER);
    assert(fabsf(field(unit,0x38)-240)<.001f);
    assert(native_lab_command_curl_bits[pad]==curl_before);
    assert(native_lab_command_vertical_bits[pad]==height_before);
    assert(field(unit,0x44)==270 && field(unit,0x48)>.99f);
    native_lab_single_camera_mask=0;
  }
  for(int s=-1;s<=1;s++) {
    const float yaw=s*.4f, old_x=-15, old_z=-20;
    const float cx=old_x*cosf(yaw)-old_z*sinf(yaw);
    const float cz=old_x*sinf(yaw)+old_z*cosf(yaw);
    const float a=pes_setplay_camera_heading(0,0,cx,cz)*.01745329252f;
    assert(fabsf(sinf(a)+cx/25)<.0001f && fabsf(cosf(a)+cz/25)<.0001f);
    float x=0,z=0; pes_setplay_bend_point(&x,&z,0,1,30,(float)s,0);
    assert(x==0 && z==0);
    x=0; z=30; pes_setplay_bend_point(&x,&z,0,1,30,(float)s,1);
    assert(fabsf(x+s*4.2f)<.001f && z==30); // lateral bend, not launch rotation
  }
}
'''
        build_and_run(self.cc, code)

class OnfieldAssetAndAbiTests(unittest.TestCase):
    def test_switch_sprites_are_bundled_byte_identical(self):
        from PIL import Image
        assets = dict(x='X_Button.png', y='Y_Button.png', l='L_Button.png',
                      zl='ZL_Button.png', zr='ZR_Button.png', sl='SL_Button.png',
                      sr='SR_Button.png', ls='LeftStick_Default_CORE.png',
                      rs='RightStick_Default_CORE.png',
                      right='Directional_Button_Right.png',
                      up='Directional_Button_Up.png',
                      down='Directional_Button_Down.png',
                      left='Directional_Button_Left.png')
        for key, source in assets.items():
            original = ROOT / 'art/SwitchButton' / source
            bundled = ROOT / 'data' / f'switch_button_{key}.bin'
            self.assertEqual(original.read_bytes(), bundled.read_bytes(), key)
            with Image.open(bundled) as png:
                self.assertEqual(png.size, (32, 32))
                self.assertIn('A', png.getbands())
        self.assertIn('!data/switch_button_*.bin', (ROOT / '.gitignore').read_text())

    def test_owned_binary_stamina_update_dispatch_is_nonvirtual(self):
        import struct
        library = ROOT / 'local-debug/apk-arm64/libUE4.so'
        if not library.exists(): self.skipTest('optional user-owned native binary unavailable')
        try:
            from elftools.elf.elffile import ELFFile
        except ImportError:
            self.skipTest('optional pyelftools unavailable')
        with library.open('rb') as stream:
            elf = ELFFile(stream)
            symbols = list(elf.get_section_by_name('.dynsym').iter_symbols())
            names = {s.name: s for s in symbols}
            name = '_ZN7match2D6Screen9ModelBase6UpdateEv'
            vt = names['_ZTVN7match2D6Screen17ModelStaminaGaugeE']
            start, end = vt['st_value'], vt['st_value'] + vt['st_size']
            slots = [symbols[r['r_info_sym']].name for r in
                     elf.get_section_by_name('.rela.dyn').iter_relocations()
                     if start <= r['r_offset'] < end]
            self.assertNotIn(name, slots)  # regression: absent vtable hook never ran
            plt = elf.get_section_by_name('.plt')
            targets = [plt['sh_addr'] + 32 + i*16 for i,r in enumerate(
                       elf.get_section_by_name('.rela.plt').iter_relocations())
                       if symbols[r['r_info_sym']].name == name]
            self.assertEqual(targets, [0x38b4b20])
            stream.seek(next(elf.address_offsets(targets[0])))
            words = struct.unpack('<4I', stream.read(16))
            self.assertEqual(words, (0x9002e330, 0xf943f611, 0x911fa210, 0xd61f0220))
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        self.assertNotIn('stamina_draw_plt', hooks)
        self.assertNotIn('pause_stamina_update_original', hooks)

if __name__ == "__main__": unittest.main()

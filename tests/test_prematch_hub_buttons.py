"""Exercise the real Hub geometry and draw ranges without a GPU/game emulator."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HubButtonTests(unittest.TestCase):
    def test_all_focus_positions_in_four_and_five_button_hubs(self):
        compiler = shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            self.skipTest("Host C compiler required")
        overlay = (ROOT / "source/overlay.c").read_text(encoding="utf-8")
        start = overlay.index("    const float frame_inset = 0.004f")
        geometry = overlay[start:overlay.index("    // Badge atlas quads", start)]
        start = overlay.index("    if (custom_hub_button_frame_quads) {")
        drawing = overlay[start:overlay.index("    use_rounded_rect(&custom_back_button_style)", start)]
        source = r'''
#include <assert.h>
#include <stdint.h>
#include <math.h>
enum { GL_TRIANGLES, FNX_BUTTON_FRAME, FNX_BUTTON_FILL, FNX_BUTTON_GLOSS };
typedef struct { float w, h, radius; } RoundedRectStyle;
static RoundedRectStyle custom_hub_button_frame_style, custom_action_button_style;
static float verts[128 * 24];
static int screen_width, screen_height, custom_hub_button_frame_quads;
static int custom_action_button_quads, custom_hub_button_gloss_quads, quads, custom_offset;
static int custom_2p_prematch_hub=1, cup_settings_popup;
static uint32_t focus, action_count, draw_count, layer, selected;
static float action_y, action_w, action_h, action_gap;
static uint32_t pes_controller_2p_prematch_hub_focus(void) { return focus; }
static uint32_t competition_frontend_cup_setting_focus(void) { return 0; }
static uint32_t competition_frontend_cup_setting_count(void) { return 5; }
static void use_rounded_rect(const RoundedRectStyle *style) { (void)style; }
static void fnx_button_color(uint32_t part, int active, int enabled) {
  assert(enabled); layer=part; selected=active;
}
static int emit_rect(float x, float y, float w, float h, float *v) {
  v[0]=x; v[1]=y; v[2]=w; v[3]=h; return 1;
}
static int emit_round_rect_quad(float x, float y, float w, float h, float *v) {
  return emit_rect(x,y,w,h,v);
}
static void glDrawArrays(int primitive, int first, int count) {
  assert(primitive==GL_TRIANGLES && count==6);
  const uint32_t button=draw_count%action_count, part=draw_count/action_count;
  assert(layer==FNX_BUTTON_FRAME+part);
  assert(selected==(button==focus));
  const float *v=verts+(first/6)*24;
  const float inset=0.004f*screen_height;
  const float x=0.035f*screen_width+(action_w+action_gap)*button+part*inset;
  assert(fabsf(v[0]-x)<0.01f);
  assert(fabsf(v[1]-(action_y+part*inset))<0.01f);
  assert(fabsf(v[2]-(action_w-2.0f*part*inset))<0.01f);
  if (part==2) assert(fabsf(v[3]-0.007f*screen_height)<0.01f);
  draw_count++;
}
static void geometry(void) {
'''+geometry+r'''
}
static void draw(void) {
'''+drawing+r'''
}
int main(void) {
  for (uint32_t resolution=0; resolution<2; ++resolution) {
    screen_width=resolution?1920:1280; screen_height=resolution?1080:720;
    for (action_count=4; action_count<=5; ++action_count) {
      action_y=0.855f*screen_height; action_h=0.064f*screen_height;
      action_gap=0.012f*screen_width;
      action_w=(0.93f*screen_width-(action_count-1)*action_gap)/action_count;
      quads=7; custom_hub_button_frame_quads=custom_action_button_quads=custom_hub_button_gloss_quads=0;
      geometry();
      assert(quads==7+(int)action_count*3);
      assert(custom_hub_button_frame_quads==(int)action_count);
      assert(custom_action_button_quads==(int)action_count);
      assert(custom_hub_button_gloss_quads==(int)action_count);
      for (focus=0; focus<action_count; ++focus) {
        custom_offset=7; draw_count=0; draw();
        assert(draw_count==action_count*3 && custom_offset==quads);
      }
    }
  }
  return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="pes-hub-buttons-") as folder:
            path = Path(folder) / "buttons.c"
            exe = Path(folder) / "buttons.exe"
            path.write_text(source)
            result = subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                                     str(path), "-lm", "-o", str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_button_label_not_repainted_as_legacy_red_focus_text(self):
        overlay = (ROOT / "source/overlay.c").read_text(encoding="utf-8")
        start = overlay.index("custom_hub_button_text_quads += line_quads;")
        focus_text = overlay[start:overlay.index("(void)page_side;", start)]
        self.assertNotIn("action_labels[hub_focus]", focus_text)


if __name__ == "__main__":
    unittest.main()

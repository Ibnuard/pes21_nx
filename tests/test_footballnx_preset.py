"""Fixed FootballNX UI plus live Day-only hub roof controls."""
from pathlib import Path
import shutil
import unittest
from test_result_flow import build_and_run, function

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'source/ue4_hooks.c').read_text()

class FootballNXTests(unittest.TestCase):
    def run_c(self, body):
        cc=shutil.which('gcc')
        if not cc: self.skipTest('gcc unavailable')
        build_and_run(cc, '#include <stdint.h>\n#include <assert.h>\n#include <stddef.h>\n'+body)

    def test_fixed_ui_and_stadium_custom_slider_isolation(self):
        self.run_c(r'''
#define PAUSE_SETTINGS_PAGE_CAMERA 2
static uint32_t pause_settings_page=2,pause_camera_dynamic_wide_custom=1;
static unsigned char settings[15];
static unsigned char *pause_settings_tmpdb_camera(uint8_t *type) {*type=settings[0];return settings;}
''' + function(SOURCE,'pes_controller_pause_settings_count') +
                   function(SOURCE,'pause_settings_camera_field') + r'''
int main(void) {
  settings[0]=5;settings[9]=4;settings[10]=7;settings[11]=9;
  assert(pes_controller_pause_settings_count()==1);
  for(unsigned i=1;i<=3;++i) assert(!pause_settings_camera_field(i,NULL));
  pause_camera_dynamic_wide_custom=0;settings[0]=13;
  assert(pes_controller_pause_settings_count()==4);
  assert(*pause_settings_camera_field(1,NULL)==7);
  assert(*pause_settings_camera_field(2,NULL)==4);
  assert(*pause_settings_camera_field(3,NULL)==9);
  pause_settings_page=1;assert(pes_controller_pause_settings_count()==7);
}
''')

    def test_hub_roof_toggle_day_night_and_preference_survives(self):
        body=function(SOURCE,'pes_controller_2p_prematch_hub_pad_event')
        body=body.split('  if (page == MAIN_MENU_2P_PREMATCH_PAGE_STADIUM) {',1)[1]
        body=body.split('\n  uint32_t focus = pes_controller_2p_prematch_hub_focus()',1)[0]
        self.run_c(r'''
static uint32_t main_menu_2p_prematch_hub_page_focus,main_menu_2p_prematch_stadium_index;
static uint32_t main_menu_2p_prematch_hub_page,exhibition_settings_time_zone;
static uint32_t stadium_roof_shadow_enabled;
static unsigned char main_menu_2p_prematch_hub_input_armed[2];
#define MAIN_MENU_2P_PREMATCH_PAGE_MAIN 0
static void *exhibition_get_tmpdb_match(void) {return (void*)1;}
static uint32_t written_time;
static void write_time(void *m,uint32_t t) {assert(m==(void*)1);written_time=t;}
static void (*exhibition_match_set_time_zone)(void*,uint32_t)=write_time;
''' + function(SOURCE,'pes_controller_stadium_is_day') +
              function(SOURCE,'pes_controller_roof_shadow_enabled') +
              'static void event(uint32_t pressed) {\n'+body+r'''
int main(void) {
  event(1u<<10); assert(main_menu_2p_prematch_hub_page_focus==2);
  event(1u<<1); assert(pes_controller_roof_shadow_enabled()==1);
  event(1u<<12); assert(pes_controller_roof_shadow_enabled()==0);
  event(1u<<13); assert(pes_controller_roof_shadow_enabled()==1);
  event(1u<<10); assert(main_menu_2p_prematch_hub_page_focus==1);
  event(1u<<1); assert(!pes_controller_stadium_is_day() && written_time==1);
  event(1u<<11); assert(main_menu_2p_prematch_hub_page_focus==0); // no Night roof row
  event(1u<<10); event(1u<<13);
  assert(pes_controller_stadium_is_day() && pes_controller_roof_shadow_enabled());
  event(1u<<11); event(1u<<1); assert(!pes_controller_roof_shadow_enabled());
}
''')
        setup=function(SOURCE,'pes_exhibition_match_setup_data_entry')
        self.assertNotIn('&stadium_roof_shadow_enabled,',setup)

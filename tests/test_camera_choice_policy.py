"""Five native choices plus FootballNX, default and session/rematch selection."""
from pathlib import Path
import re
import shutil
import unittest

from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')


class CameraChoiceTests(unittest.TestCase):
    def test_cycle_default_and_rematch_with_fixed_footballnx(self):
        compiler = shutil.which('gcc')
        if not compiler:
            self.skipTest('gcc unavailable')
        preset = re.search(r'typedef struct \{\s*uint8_t native_type;.*?'
                           r'\} PauseCameraPreset;', SOURCE, re.S)[0]
        table = re.search(r'static const PauseCameraPreset pause_camera_presets\[\]'
                          r' = \{.*?\n\};', SOURCE, re.S)[0]
        functions = '\n'.join(function(SOURCE, name) for name in (
            'pause_camera_preset_index', 'match_pause_camera_page',
            'pause_settings_resident_work', 'pause_settings_tmpdb_camera',
            'pause_settings_capture_camera', 'pause_settings_prepare_match_camera',
            'pause_settings_restore_camera', 'pause_settings_cycle_camera',
            'pes_controller_pause_settings_value'))
        build_and_run(compiler, r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define PAUSE_SETTINGS_PAGE_CAMERA 1
#define PES_PAUSE_INPUT_LEFT 5u
static uint32_t pause_settings_page=PAUSE_SETTINGS_PAGE_CAMERA;
static uint32_t pause_camera_dynamic_wide_custom, pause_camera_saved_valid;
static uint32_t pause_camera_saved_dynamic_wide_custom;
static unsigned char pause_camera_saved_settings[15];
static unsigned char manager[80], resident[0x18400];
static uint32_t pause_settings_radar, pause_settings_show_replay;
static uint32_t pause_settings_show_nameplate;
static uint32_t pause_settings_chant, pause_settings_commentary;
static uint32_t available=1, apply_calls;
static void *get_manager(void) { return available ? manager : NULL; }
static void *(*exhibition_tmpdb_manager_get_instance)(void)=get_manager;
static unsigned char *pause_settings_tmpdb_system(void) { return resident+0xb44; }
static unsigned char *pause_settings_camera_field(uint32_t i,uint8_t *t) { return NULL; }
static void pause_settings_apply_camera(void *window) { assert(window==(void*)9); ++apply_calls; }
static void debugPrintf(const char *format,...) {}
''' + preset + table + functions + r'''
static void assert_choice(unsigned index) {
  const unsigned types[]={5,12,0,1,2,5}, custom[]={0,0,0,0,0,1};
  const char *labels[]={"DYNAMIC WIDE","STADIUM","MEDIUM","LONG","WIDE","FOOTBALLNX CAM"};
  uint32_t count=0;
  unsigned char *settings=pause_settings_tmpdb_camera(NULL);
  assert(match_pause_camera_page(NULL,&count)==index && count==6);
  assert(settings[0]==types[index] && pause_camera_dynamic_wide_custom==custom[index]);
  assert(!strcmp(pes_controller_pause_settings_value(0),labels[index]));
}
int main(void) {
  void *p=resident; memcpy(manager+72,&p,sizeof(p));
  assert(sizeof(pause_camera_presets)/sizeof(pause_camera_presets[0])==6);
  // Old persisted types must not change the app-session default.
  for(unsigned mode=0;mode<=6;++mode) {
    memcpy(resident+0x18338,&mode,4);
    unsigned char *settings=resident+0xb78+mode*15;
    memset(settings,0x7a,15); settings[0]=mode==0?13:7;
    pause_camera_saved_valid=0; pause_camera_dynamic_wide_custom=1;
    pause_settings_prepare_match_camera(); assert_choice(0);
    for(unsigned j=1;j<15;++j) assert(settings[j]==0x7a);
    assert(pause_camera_saved_valid && pause_camera_saved_settings[0]==5);
  }
  // Production LEFT/RIGHT/DECIDE selection, including wraparound.
  apply_calls=0;
  for(unsigned i=1;i<=18;++i) {
    pause_settings_cycle_camera((void*)9,6); assert_choice(i%6);
  }
  for(unsigned i=1;i<=18;++i) {
    pause_settings_cycle_camera((void*)9,PES_PAUSE_INPUT_LEFT);
    assert_choice((6-i%6)%6);
  }
  assert(apply_calls==36);
  pause_settings_cycle_camera((void*)9,3); assert_choice(1);
  // Every choice survives native rematch bootstrap without importing its
  // type or copying stale per-match camera bytes into the new resident.
  for(unsigned choice=0;choice<6;++choice) {
    unsigned char *settings=pause_settings_tmpdb_camera(NULL);
    settings[0]=pause_camera_presets[choice].native_type;
    pause_camera_dynamic_wide_custom=pause_camera_presets[choice].dynamic_wide_custom;
    pause_settings_capture_camera();
    memset(settings,0x5b,15); settings[0]=13;
    pause_camera_dynamic_wide_custom=0;
    pause_settings_prepare_match_camera(); assert_choice(choice);
    for(unsigned j=1;j<15;++j) assert(settings[j]==0x5b);
    // Opening native camera/general page may reset tmpdb; restore our capture.
    memset(settings,0,15); pause_camera_dynamic_wide_custom=0;
    pause_settings_restore_camera((void*)9); assert_choice(choice);
    for(unsigned j=1;j<15;++j) assert(settings[j]==0x5b);
  }
  // Removed or unknown snapshot types are normalized at the match boundary.
  pause_camera_saved_settings[0]=5;
  pause_camera_saved_dynamic_wide_custom=1;
  pause_settings_prepare_match_camera(); assert_choice(5);
  const uint8_t removed[]={3,4,6,7,8,9,10,11,13,255};
  for(unsigned i=0;i<sizeof(removed);++i) {
    assert(pause_camera_preset_index(removed[i],1)==0);
    pause_camera_saved_settings[0]=removed[i];
    pause_camera_saved_dynamic_wide_custom=1;
    pause_settings_prepare_match_camera(); assert_choice(0);
  }
  // Invalid mode falls back to resident slot zero; missing manager is a no-op.
  uint32_t mode=99; memcpy(resident+0x18338,&mode,4);
  assert(pause_settings_tmpdb_camera(NULL)==resident+0xb78);
  pause_settings_prepare_match_camera(); assert_choice(0);
  available=0; unsigned before=apply_calls;
  pause_settings_prepare_match_camera();
  pause_settings_cycle_camera((void*)9,6);
  assert(apply_calls==before);
  uint32_t count=0; assert(match_pause_camera_page(NULL,&count)==0 && count==6);
}
''')


if __name__ == '__main__':
    unittest.main()

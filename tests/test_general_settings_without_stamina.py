"""Execute menu rows, values and input routing after removing stamina UI."""
from pathlib import Path
import re
import shutil
import unittest

from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')


class GeneralSettingsTests(unittest.TestCase):
    def test_owned_binary_exposes_required_stamina_visibility_slot(self):
        library = ROOT / 'dist/pes21_nx/libUE4.so'
        if not library.is_file():
            self.skipTest('requires ignored compatible libUE4.so fixture')
        try:
            from elftools.elf.elffile import ELFFile
        except ImportError:
            self.skipTest('requires pyelftools')
        with library.open('rb') as stream:
            elf = ELFFile(stream)
            symbols = list(elf.get_section_by_name('.dynsym').iter_symbols())
            names = {s.name: s for s in symbols}
            table = names['_ZTVN7match2D6Screen17ModelStaminaGaugeE']
            method = names['_ZN7match2D6Screen17ModelStaminaGauge7GetDispEj']
            start = table['st_value']
            self.assertGreaterEqual(table['st_size'], 25 * 8)
            matching_slots = []
            for relocation in elf.get_section_by_name('.rela.dyn').iter_relocations():
                offset = relocation['r_offset'] - start
                if 2 * 8 <= offset < 25 * 8:
                    symbol = relocation['r_info_sym']
                    target = ((symbols[symbol]['st_value'] if symbol else 0)
                              + relocation['r_addend'])
                    if target == method['st_value']:
                        matching_slots.append(offset // 8)
            self.assertEqual(len(matching_slots), 1)

    def test_seven_rows_dispatch_and_wrap_with_and_without_profiling(self):
        compiler = shutil.which('gcc')
        if not compiler:
            self.skipTest('gcc unavailable')
        header = (ROOT / 'source/ue4_hooks.h').read_text()
        constants = '\n'.join(re.findall(
            r'^#define PES_PAUSE_INPUT_\w+ .*$', header, re.M))
        pages = re.search(r'enum \{\s*PAUSE_SETTINGS_PAGE_GENERAL.*?\};',
                          SOURCE, re.S)[0]
        stubs = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static uint32_t pause_settings_page, pause_settings_focus;
static uint32_t pause_camera_dynamic_wide_custom, pause_settings_radar;
static uint32_t pause_settings_chant=1, pause_settings_commentary=1;
static uint32_t pause_settings_show_replay=1;
static uint32_t pause_settings_show_nameplate=1;
static unsigned char system_data[0x20], resident_data[0x50], camera_data[15];
static uint32_t speed_calls, speed_action, target_calls, replay_calls;
static uint32_t volume_calls, volume_kind, camera_calls, log_calls;
static float volume_value;
static char last_log[256];
static unsigned char *pause_settings_tmpdb_system(void) { return system_data; }
static unsigned char *pause_settings_resident_work(void) { return resident_data; }
static unsigned char *pause_settings_tmpdb_camera(uint8_t *type) {
  if(type) *type=camera_data[0]; return camera_data;
}
static unsigned char *pause_settings_camera_field(uint32_t index, void *type) {
  (void)type; return index>=1 && index<=3 ? &camera_data[index] : 0;
}
static void pause_settings_set_game_speed(uint32_t action) {
  ++speed_calls; speed_action=action; system_data[0x14]=3;
}
static void pause_settings_toggle_next_target(void) {
  ++target_calls; resident_data[0x47]=!resident_data[0x47];
}
static void pause_settings_toggle_replay(void) {
  ++replay_calls; pause_settings_show_replay=!pause_settings_show_replay;
}
static void set_volume(uint32_t kind,float value) {
  ++volume_calls; volume_kind=kind; volume_value=value;
}
static void (*pause_settings_volume)(uint32_t,float)=set_volume;
static uint64_t perf_trace_now_ns(void) { return 1234567; }
static void perf_trace_log_line(const char *line) {
  ++log_calls; snprintf(last_log,sizeof(last_log),"%s",line);
}
static void *match_pause_camera_window=(void*)9;
static uint32_t (*match_pause_camera_update_original)(void*,uint32_t);
static void *(*match_setplay_get_root)(void*);
static void (*match_node_set_alpha)(void*,float);
static uint64_t match_pause_camera_seen_tick, pause_editor_transition_tick;
static uint32_t match_pause_camera_action, live_gameplan_returning_to_pause;
static void (*match_pause_camera_footer)(void*,uint32_t);
static uint64_t armGetSystemTick(void) { return 100; }
static void pause_settings_restore_camera(void *window) { ++camera_calls; }
static void pause_settings_adjust_camera(void *w,uint32_t f,uint32_t a) { ++camera_calls; }
static uint32_t match_pause_camera_page(void *w,uint32_t *n) { *n=2; return 0; }
typedef struct { uint8_t native_type, dynamic_wide_custom; } PauseCameraPreset;
static const PauseCameraPreset pause_camera_presets[]={{5,0},{5,1}};
static void pause_settings_capture_camera(void) { ++camera_calls; }
static void pause_settings_apply_camera(void *w) { ++camera_calls; }
static void pause_settings_cycle_camera(void *w,uint32_t action) { ++camera_calls; }
static void debugPrintf(const char *format,...) {}
'''
        functions = '\n'.join(function(SOURCE, name) for name in (
            'pes_controller_pause_settings_count',
            'pes_controller_pause_settings_label',
            'pes_controller_pause_settings_value',
            'pause_settings_adjust_general',
            'pes_match_pause_camera_update'))
        body = r'''
static void input(uint32_t action) {
  match_pause_camera_action=action;
  pes_match_pause_camera_update((void*)9,0);
}
int main(void) {
  const char *labels[]={"RADAR","GAME SPEED","NEXT TARGET INDICATOR",
                        "SHOW NAME PLATE","SHOW REPLAY","CHANT SFX","COMMENTARY"};
  const char *before[]={"OFF","0","ON","ON","ON","ON","ON"};
  const char *after[]={"ON","+1","OFF","OFF","OFF","OFF","OFF"};
  const uint32_t actions[]={PES_PAUSE_INPUT_LEFT,PES_PAUSE_INPUT_RIGHT,
                            PES_PAUSE_INPUT_DECIDE};
  pause_settings_page=PAUSE_SETTINGS_PAGE_GENERAL;
  assert(pes_controller_pause_settings_count()==7);
  for(unsigned a=0;a<3;++a) for(unsigned row=0;row<7;++row) {
    pause_settings_radar=0;
    system_data[0x14]=2; resident_data[0x47]=0;
    pause_settings_show_nameplate=pause_settings_show_replay=1;
    pause_settings_chant=pause_settings_commentary=1;
    speed_calls=target_calls=replay_calls=volume_calls=log_calls=0;
    pause_settings_focus=row;
    for(unsigned i=0;i<7;++i) {
      assert(!strcmp(pes_controller_pause_settings_label(i),labels[i]));
      assert(!strcmp(pes_controller_pause_settings_value(i),before[i]));
    }
    input(actions[a]);
    for(unsigned i=0;i<7;++i)
      assert(!strcmp(pes_controller_pause_settings_value(i),i==row?after[i]:before[i]));
    assert(speed_calls==(row==1) && target_calls==(row==2) && replay_calls==(row==4));
    assert(volume_calls==(row>=5));
    if(row==1) assert(speed_action==actions[a]);
    if(row>=5) assert(volume_kind==(row==5?3:2) && volume_value==0.0f);
    assert(camera_calls==0);
#ifdef PERF_TRACE
    assert(log_calls==1 && strstr(last_log,"[SETTINGS] ns=1234567"));
    assert(strstr(last_log,labels[row]) && strstr(last_log,"nameplate="));
#else
    assert(log_calls==0);
#endif
    // All non-speed rows toggle back correctly on the next action.
    if(row!=1) {
      input(actions[a]);
      assert(!strcmp(pes_controller_pause_settings_value(row),before[row]));
      if(row>=5) assert(volume_value==1.0f);
    }
  }
  for(unsigned i=7;i<10;++i) {
    assert(!strcmp(pes_controller_pause_settings_label(i),""));
    assert(!strcmp(pes_controller_pause_settings_value(i),""));
  }
  unsigned previous_logs=log_calls, previous_volumes=volume_calls;
  pause_settings_adjust_general(7,PES_PAUSE_INPUT_DECIDE);
  assert(log_calls==previous_logs && volume_calls==previous_volumes);
  pause_settings_focus=0;
  input(PES_PAUSE_INPUT_UP); assert(pause_settings_focus==6);
  input(PES_PAUSE_INPUT_DOWN); assert(pause_settings_focus==0);
  for(unsigned i=1;i<=7;++i) {
    input(PES_PAUSE_INPUT_DOWN); assert(pause_settings_focus==i%7);
  }
  pause_settings_focus=7; input(0); assert(pause_settings_focus==0);
  assert(camera_calls==0);
  // Camera page and its fixed FootballNX preset remain independent.
  pause_settings_page=PAUSE_SETTINGS_PAGE_CAMERA;
  assert(pes_controller_pause_settings_count()==4);
  assert(!strcmp(pes_controller_pause_settings_label(0),"CAMERA TYPE"));
  pause_camera_dynamic_wide_custom=1; camera_data[0]=5;
  assert(pes_controller_pause_settings_count()==1);
  assert(!strcmp(pes_controller_pause_settings_value(0),"FOOTBALLNX CAM"));
}
'''
        for profiling in (False, True):
            with self.subTest(profiling=profiling):
                build_and_run(compiler, ('#define PERF_TRACE\n' if profiling else '')
                              + constants + '\n' + pages + stubs + functions + body)


if __name__ == '__main__':
    unittest.main()

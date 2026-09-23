"""Guards for native settings ownership and final-result completion routing."""
from pathlib import Path
import re
import shutil
import unittest
from test_gameplan_editor import function
from test_result_flow import build_and_run, harness

SOURCE = (Path(__file__).resolve().parents[1] / "source/ue4_hooks.c").read_text(encoding="utf-8")


class SettingsExitTests(unittest.TestCase):
    def test_camera_names_follow_tmpdb_type_and_include_custom(self):
        body = SOURCE.split("const char *pes_controller_pause_settings_value", 1)[1].split("static void match_pause_go_top_menu", 1)[0]
        self.assertIn("pause_settings_tmpdb_camera(&tmpdb_type)", body)
        self.assertIn("switch (type)", body)
        for enum, label in ((0, "MEDIUM"), (1, "LONG"), (2, "WIDE"), (12, "STADIUM")):
            self.assertIn(f'case {enum}: return "{label}";', body)
        self.assertIn('? "FOOTBALLNX CAM" : "DYNAMIC WIDE"', body)
        self.assertNotIn('"WIDE DYNAMIC CUSTOM"', body)
        self.assertNotIn('"LIVE BROADCAST"', body)
        self.assertNotIn('"STADIUM CUSTOM"', body)
        self.assertNotIn("PRESET", body)

    def test_native_stamina_is_hidden_without_publishing(self):
        compiler = shutil.which("gcc")
        if not compiler: self.skipTest("gcc unavailable")
        build_and_run(compiler, r'''
#include <stdint.h>
#include <assert.h>
static uint32_t published;
static void match_stamina_publish_from_model(void *model, uint32_t index) {
  (void)model;
  published |= 1u << index;
}
''' + function(SOURCE, "pause_stamina_disp") + r'''
int main(void) {
  for (uint32_t i = 0; i < 4; ++i) {
    assert(pause_stamina_disp((void *)123, i) == 0);
    assert(pause_stamina_disp(0, i) == 0);
  }
  assert(pause_stamina_disp(0, UINT32_MAX) == 0);
  assert(published == 0u);
}
''')
        self.assertNotIn('pause_settings_stamina', SOURCE)
        self.assertNotIn('pause_stamina_disp_original', SOURCE)

    def test_pause_settings_are_split_into_general_and_camera_pages(self):
        self.assertIn('return index < 7u ? general[index] : "";', SOURCE)
        self.assertIn('"RADAR", "GAME SPEED", "NEXT TARGET INDICATOR"', SOURCE)
        self.assertNotIn('SHOW STAMINA', SOURCE)
        self.assertIn('"SHOW NAME PLATE", "SHOW REPLAY", "CHANT SFX", "COMMENTARY"', SOURCE)
        self.assertIn('"CAMERA TYPE", "CAMERA HEIGHT", "CAMERA DISTANCE", "CAMERA ANGLE"', SOURCE)
        self.assertIn('focus == 2u ? PAUSE_SETTINGS_PAGE_CAMERA', SOURCE)
        self.assertIn('const uint32_t native_route = focus == 2u ? 1u : focus;', SOURCE)
        camera_field = function(SOURCE, 'pause_settings_camera_field')
        self.assertIn('type == 5u &&', camera_field)
        self.assertIn('pause_camera_dynamic_wide_custom', camera_field)
        self.assertIn('return NULL; // FOOTBALLNX CAM', camera_field)
        self.assertIn('type >= 7u && type <= 11u', camera_field)
        self.assertIn('type == 13u', camera_field)

    def test_radar_toggle_overrides_the_per_frame_info_byte(self):
        compiler = shutil.which("gcc")
        if not compiler: self.skipTest("gcc unavailable")
        build_and_run(compiler, r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
static uint32_t pause_settings_radar, calls;
static void *pause_radar_initialized_object;
static uint32_t native_update(void *radar) { assert(radar); ++calls; return 77; }
static uint32_t (*pause_radar_update_original)(void *) = native_update;
''' + function(SOURCE, "pause_radar_update") + r'''
int main(void) {
  unsigned char radar[0x40]={0}, info[2]={9,0}; void *p=info;
  memcpy(radar+0x38,&p,sizeof(p));
  pause_settings_radar=0;
  assert(pause_radar_update(radar)==77 && info[0]==0 && radar[0x22]==1 && calls==1);
  pause_settings_radar=1;
  assert(pause_radar_update(radar)==77 && info[0]==1 && radar[0x22]==1 && calls==2);
  unsigned char radar2[0x40]={0}; memcpy(radar2+0x38,&p,sizeof(p));
  assert(pause_radar_update(radar2)==77 && info[0]==1 && radar2[0x22]==0 && calls==3);
}
''')
        install = SOURCE.split('void install_ue4_hooks', 1)[1]
        self.assertIn('"_ZN7match2D6Screen5Radar6UpdateEv"', install)
        self.assertIn('*radar_update_slot = (uintptr_t)&pause_radar_update;', install)

        need_disp = function(SOURCE, 'pause_radar_need_disp')
        self.assertIn('pause_settings_radar', need_disp)
        self.assertNotIn('pause_radar_need_disp_original', need_disp)
        setup = function(SOURCE, 'pes_exhibition_match_setup_data_entry')
        self.assertIn('&pause_settings_radar, 0', setup)
        self.assertIn('static uint32_t pause_settings_radar = 0', SOURCE)

    def test_game_speed_commits_registry_but_leaves_native_timing_ownership(self):
        body = function(SOURCE, 'pause_settings_set_game_speed')
        self.assertIn('(unsigned char *)registry_system + 0x14', body)
        self.assertNotIn('pause_match_listener_change_game_speed', SOURCE)
        self.assertIn('pause_registry_game_speed_get_fps(registry_speed)', body)
        self.assertNotIn('pause_basic_status_set_pes_module_thread_fps', SOURCE)
        self.assertIn('pause_basic_status_get_pes_module_thread_fps()', body)
        self.assertIn('&pause_game_speed_debug_apply_count, 1', body)
        self.assertNotIn('pause_settings_enforce_game_speed', SOURCE)
        tick = function(SOURCE, 'ue4_tickrate_clamp')
        self.assertNotIn('game_speed', tick)
        root = Path(__file__).resolve().parents[1]
        overlay = (root / 'source/overlay.c').read_text(encoding='utf-8')
        self.assertNotIn('pes_controller_game_speed_debug(&game_speed_debug)', overlay)
        self.assertNotIn('GAME SPEED DBG', overlay)
        install = SOURCE.split('void install_ue4_hooks', 1)[1]
        self.assertIn('"_ZNK5match8registry17GameSpeedSettings10GetGameFPSEv"', install)
        self.assertNotIn('"_ZN5basic6Status21SetPesModuleThreadFPSEf"', install)
        self.assertIn('"_ZN5basic6Status21GetPesModuleThreadFPSEv"', install)

    def test_replay_off_overrides_the_runtime_replay_decision(self):
        compiler = shutil.which("gcc")
        if not compiler: self.skipTest("gcc unavailable")
        build_and_run(compiler, r'''
#include <assert.h>
#include <stdint.h>
static uint32_t pause_settings_show_replay, native_value, calls;
static uint32_t native_get(void *settings) { assert(settings==(void*)9); ++calls; return native_value; }
static uint32_t (*pause_registry_system_is_no_replay_original)(void *) = native_get;
''' + function(SOURCE, "pause_registry_system_is_no_replay") + r'''
int main(void) {
  pause_settings_show_replay=0; native_value=0;
  assert(pause_registry_system_is_no_replay((void*)9)==1 && calls==0);
  pause_settings_show_replay=1; native_value=0;
  assert(pause_registry_system_is_no_replay((void*)9)==0 && calls==1);
  native_value=1;
  assert(pause_registry_system_is_no_replay((void*)9)==1 && calls==2);
}
''')
        install = SOURCE.split('void install_ue4_hooks', 1)[1]
        self.assertIn('module->load_base + 0x380e790', install)
        self.assertIn('&pause_registry_system_is_no_replay', install)

    def test_camera_changes_sync_camera_registry_and_live_match_env(self):
        apply = function(SOURCE, 'pause_settings_apply_camera')
        self.assertIn('pause_match_listener_set_camera_from_tmpdb(listener, 1u)', apply)
        self.assertIn('match_pause_camera_update_registry(window, 1u)', apply)
        self.assertIn('static const PauseCameraPreset pause_camera_presets[]', SOURCE)
        self.assertIn('{5u, 0u}, {12u, 0u}, {0u, 0u}, {1u, 0u}, {2u, 0u},', SOURCE)
        update = function(SOURCE, 'pes_match_pause_camera_update')
        cycle = function(SOURCE, 'pause_settings_cycle_camera')
        self.assertIn('pause_settings_cycle_camera(window, action)', update)
        self.assertIn('settings[0] = preset.native_type', cycle)
        self.assertNotIn('settings[9] =', update)
        self.assertNotIn('settings[10] =', update)
        self.assertNotIn('settings[11] =', update)
        self.assertIn('pes_controller_pause_settings_count()', update)
        self.assertIn('const int opening = window && window != match_pause_camera_window;', update)
        self.assertIn('pause_settings_restore_camera(window)', update)
        self.assertIn('pause_settings_capture_camera()', cycle)
        self.assertIn('pause_settings_apply_camera(window)', cycle)
        capture = function(SOURCE, 'pause_settings_capture_camera')
        restore = function(SOURCE, 'pause_settings_restore_camera')
        self.assertIn('sizeof(pause_camera_saved_settings)', capture)
        self.assertIn('&pause_camera_saved_valid, 1', capture)
        self.assertIn('memcpy(settings, pause_camera_saved_settings', restore)
        self.assertIn('pause_settings_apply_camera(window)', restore)
        setup = function(SOURCE, 'pes_exhibition_match_setup_data_entry')
        self.assertIn('pause_settings_prepare_match_camera();', setup)
        self.assertNotIn('&pause_camera_saved_valid, 0', setup)

    def test_footballnx_keeps_native_type_and_uses_fixed_stadium_framing(self):
        compiler = shutil.which("gcc")
        if not compiler: self.skipTest("gcc unavailable")
        build_and_run(compiler, r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
static uint32_t pause_camera_dynamic_wide_custom;
static uint32_t match_broadcast_anticipation_enabled;
static uint32_t match_broadcast_ball_tracking_ready(const void *a,const float *b) {assert(!a && !b);return 0;}
static void native_convert(void *registry, const void *tmpdb, void *resident) {
  (void)tmpdb; (void)resident;
  unsigned char *camera=registry;
  memset(camera, 0, 32);
  camera[0]=11; camera[6]=11; camera[11]=11;
  camera[2]=camera[8]=camera[13]=2;
  camera[3]=camera[9]=camera[14]=2;
}
static void (*pause_set_tmpdb_camera_original)(void *, const void *, void *) = native_convert;
''' + function(SOURCE, 'pause_set_tmpdb_camera_settings') + r'''
int main(void) {
  unsigned char registry[32]={0}, tmpdb[15]={0}; tmpdb[0]=5;
  tmpdb[9]=4; tmpdb[10]=7; tmpdb[11]=9;
  pause_camera_dynamic_wide_custom=0;
  pause_set_tmpdb_camera_settings(registry,tmpdb,(void*)1);
  assert(registry[0]==11 && registry[2]==2 && registry[3]==2);
  pause_camera_dynamic_wide_custom=1;
  pause_set_tmpdb_camera_settings(registry,tmpdb,(void*)1);
  for (unsigned i=0;i<3;i++) {
    const unsigned base=(unsigned[]){0,6,11}[i];
    assert(registry[base]==11);
    assert(registry[base+2]==2 && registry[base+3]==3 && registry[base+4]==6);
  }
  assert(tmpdb[9]==4 && tmpdb[10]==7 && tmpdb[11]==9); // other custom preset untouched
  for (unsigned type=0; type<=13; ++type) {
    tmpdb[0]=type;
    pause_camera_dynamic_wide_custom=0;
    pause_set_tmpdb_camera_settings(registry,tmpdb,(void*)1);
    assert(match_broadcast_anticipation_enabled == (type==12));
    for (unsigned i=0;i<3;i++) {
      unsigned base=(unsigned[]){0,6,11}[i];
      assert(registry[base+3]==((type==12)?6:2));
    }
  }
}
''')
        install = SOURCE.split('void install_ue4_hooks', 1)[1]
        self.assertIn('module->load_base + 0x38bced0', install)
        self.assertIn('&pause_set_tmpdb_camera_settings', install)

    def test_footballnx_upper_tribune_compensates_near_far_zoom_continuously(self):
        compiler = shutil.which("gcc")
        if not compiler: self.skipTest("gcc unavailable")
        build_and_run(compiler, r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
''' + (Path(__file__).resolve().parents[1] / 'source/stadium_view_policy.h').read_text() + r'''
int main(void) {
  for (int x=-60; x<=60; ++x) for (int z=-40; z<=40; ++z) {
    float camera[16] = {x, 1, z, x+20, 35, z+40}; camera[14]=42;
    float last[16]={0};
    for (int repeat=0; repeat<3; ++repeat) {
      assert(footballnx_tribune_view(camera));
      assert(camera[0]==x && camera[1]==1 && camera[2]==z);
      assert(camera[3]==x && camera[4]>=19 && camera[4]<22 && camera[5]==55);
      const float dz=camera[5]-camera[2], dy=camera[4]-camera[1];
      assert(dy>=18 && dy<21); // close to Stadium's 17.68m, not V11's 35-50m
      const float span=hypotf(dz,dy)*tanf(camera[13]*.5f);
      assert(span>=9.499f && span<=11.001f); // Stadium scale, controlled near-side zoom
      assert(camera[14]==42);
      if(repeat) for(int j=0;j<16;j++) assert(camera[j]==last[j]);
      for(int j=0;j<16;j++) last[j]=camera[j];
    }
  }
  float previous[16]={0};
  for(int i=0;i<=6800;i++) {
    float p[16]={0,0,-34+i*.01f,0,0,0};
    assert(footballnx_tribune_view(p));
    if(i) {assert(fabsf(p[4]-previous[4])<.002f);assert(fabsf(p[13]-previous[13])<.001f);}
    for(int j=0;j<16;j++) previous[j]=p[j];
  }
  assert(!footballnx_tribune_view(0));
  float invalid[6]={NAN,0,0,1,2,3};
  assert(!footballnx_tribune_view(invalid) && invalid[3]==1);
  float outside[6]={100,0,0,1,2,3};
  assert(!footballnx_tribune_view(outside) && outside[3]==1);
}
''')
        wrapper = function(SOURCE, 'pes_inplay_camera_update')
        self.assertIn('match_inplay_camera_update_original(camera, parameter)', wrapper)
        self.assertIn('pause_camera_dynamic_wide_custom', wrapper)
        self.assertIn('camera_id != 5u', wrapper)
        self.assertIn('footballnx_tribune_view((float *)parameter)', wrapper)
        self.assertNotIn('pause_dynamic_wide_apply_angle', SOURCE)
        install = SOURCE.split('void install_ue4_hooks', 1)[1]
        self.assertIn('InplayCamera6UpdateERN4draw15CameraParameterE', install)
        self.assertIn('*inplay_camera_update_slot = (uintptr_t)&pes_inplay_camera_update;', install)

    def test_stadium_native_target_arms_after_ball_motion_and_resets_on_pause(self):
        compiler = shutil.which("gcc")
        if not compiler: self.skipTest("gcc unavailable")
        build_and_run(compiler, r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
''' + function(SOURCE, 'match_broadcast_ball_tracking_ready') + r'''
int main(void) {
  int first_ball = 1;
  int second_ball = 2;
  float still[3] = {10.0f, 20.0f, 0.0f};
  float moved[3] = {10.6f, 20.0f, 0.0f};
  float live[3] = {10.8f, 20.0f, 0.0f};
  assert(match_broadcast_ball_tracking_ready(&first_ball, still) == 0);
  assert(match_broadcast_ball_tracking_ready(&first_ball, still) == 0);
  assert(match_broadcast_ball_tracking_ready(&first_ball, moved) == 0);
  assert(match_broadcast_ball_tracking_ready(&first_ball, live) == 1);
  assert(match_broadcast_ball_tracking_ready(0, 0) == 0);
  assert(match_broadcast_ball_tracking_ready(&first_ball, still) == 0);
  assert(match_broadcast_ball_tracking_ready(&first_ball, still) == 0);
  assert(match_broadcast_ball_tracking_ready(&first_ball, moved) == 0);
  assert(match_broadcast_ball_tracking_ready(&first_ball, live) == 1);
  assert(match_broadcast_ball_tracking_ready(&second_ball, live) == 0);
  assert(match_broadcast_ball_tracking_ready(0, 0) == 0);
  float lifted[3] = {10.0f, 22.0f, 0.0f};
  float lateral[3] = {10.0f, 20.0f, 0.8f};
  assert(match_broadcast_ball_tracking_ready(&first_ball, still) == 0);
  assert(match_broadcast_ball_tracking_ready(&first_ball, lifted) == 0);
  assert(match_broadcast_ball_tracking_ready(&first_ball, lateral) == 0);
  assert(match_broadcast_ball_tracking_ready(&first_ball, lateral) == 1);
}
''')
        root = Path(__file__).resolve().parents[1]
        assembly = (root / 'source/cobra_pad_hook.s').read_text(encoding='utf-8')
        wrapper = function(SOURCE, 'pes_inplay_ball_position_broadcast')
        self.assertIn('match_ball_position_broadcast_original(', wrapper)
        self.assertIn('(const unsigned char *)camera + 0x198', wrapper)
        self.assertIn('match_broadcast_ball_tracking_ready(ball_info, ball_position)', wrapper)
        self.assertNotIn('match_broadcast_limit_anticipation', SOURCE)
        self.assertIn('match_broadcast_frame.camera == camera', wrapper)
        self.assertIn('match_broadcast_frame.sampled = 1u',
                      function(SOURCE, 'pes_stadium_ball_target_mode'))
        setup = function(SOURCE, 'pes_exhibition_match_setup_data_entry')
        self.assertIn('match_broadcast_ball_tracking_ready(NULL, NULL);', setup)
        self.assertIn('match_broadcast_ball_tracking_ready(NULL, NULL);',
                      function(SOURCE, 'pes_match_pause_update_entry'))
        self.assertNotIn('if (!active', wrapper)
        self.assertNotIn('armGetSystemTick', wrapper)
        install = SOURCE.split('void install_ue4_hooks', 1)[1]
        self.assertIn('GetBallPositionBroadcastERKfRK8HomeAway', install)
        self.assertIn('(uintptr_t)&pes_inplay_ball_position_broadcast', install)
        self.assertIn('pes_inplay_ball_position_broadcast_original:', assembly)
        self.assertIn('inplay_ball_position_broadcast_resume', assembly)

    def test_stamina_gate_replaces_draw_experiments(self):
        install = SOURCE.split('void install_ue4_hooks', 1)[1]
        self.assertIn('"_ZTVN7match2D6Screen17ModelStaminaGaugeE", stamina_disp_runtime, 25', install)
        self.assertIn('*stamina_disp_slot = (uintptr_t)&pause_stamina_disp;', install)
        self.assertIn('fatal_error("Unexpected ModelStaminaGauge::GetDisp vtable layout")', install)
        for name in ('stamina_disp_code', 'stamina_color_code', 'stamina_exec_code'):
            self.assertNotIn(name, SOURCE)

    def test_final_exit_uses_result_handshake_not_pause_event(self):
        compiler = shutil.which("gcc")
        if not compiler: self.skipTest("gcc unavailable")
        header = (Path(__file__).resolve().parents[1] / "source/ue4_hooks.h").read_text()
        constants = "\n".join(re.findall(
            r"^#define (?:PES_PAUSE_INPUT_\w+|PES_VIRTUAL_CURSOR_\w+) .*$", header, re.M))
        stubs = r'''
#include <stddef.h>
#include <string.h>
static uint32_t match_result_input_action, virtual_cursor_context;
static uint32_t match_result_surface, match_result_skin_ready;
static uint32_t match_postmatch_custom_active, match_result_exit_requested;
static uint32_t match_result_surface_focus, live_gameplan_returning_to_pause;
static uint32_t live_gameplan_open_requested, match_result_page;
static uint64_t pause_editor_transition_tick, match_result_action_tick;
static uint64_t match_result_handoff_tick, pause_top_menu_transition_tick;
static void *match_result_window;
static uint32_t footer_calls, stats_calls, pause_calls, wait_calls, event_calls;
static int match_result_handoff_active(void) { return match_result_handoff_tick != 0; }
static uint64_t armGetSystemTick(void) { return 100; }
static void debugPrintf(const char *fmt, ...) { (void)fmt; }
static void footer(void *w, uint32_t key) { assert(w==(void *)123 && key==0); ++footer_calls; }
static void stats(void *w, uint32_t key) { assert(w==(void *)123 && key==0); ++stats_calls; }
static void wait_control(void *w, uint32_t on) { assert(w==(void *)123 && on==1); ++wait_calls; }
static void match_pause_go_top_menu(void *w) { assert(w==(void *)123); ++pause_calls; }
/* Cup score capture is tested in its own frontend path; this isolated
 * result handshake harness exercises the non-Cup native footer route. */
static void match_result_record_cup_score(void) {}
static void match_result_dispatch_event(void *w, const char *event) {
  assert(w==(void *)123 && !strcmp(event,"plan")); ++event_calls;
}
static void (*match_result_footer_touch)(void *, uint32_t) = footer;
static void (*match_stats_footer_touch)(void *, uint32_t) = stats;
static void (*match_result_control_wait)(void *, uint32_t) = wait_control;
static void reset(void) {
  footer_calls=stats_calls=pause_calls=wait_calls=event_calls=0;
  match_result_exit_requested=0; match_result_handoff_tick=0;
  match_result_surface_focus=0; match_result_skin_ready=1;
  match_result_final_seen=0; pause_top_menu_transition_tick=0;
}
'''
        body = r'''
int main(void) {
  // A and the B shortcut must use the same native footer as a physical tap,
  // regardless of which match-ending settings led to the final result.
  for (uint32_t input=PES_PAUSE_INPUT_DECIDE; input<=PES_PAUSE_INPUT_BACK; ++input)
    for (uint32_t et=0; et<2; ++et)
      for (uint32_t pk=0; pk<2; ++pk) {
        reset(); exhibition_settings_extra_time=et; exhibition_settings_penalties=pk;
        match_result_final_seen=1; stub_phase=MATCH_PHASE_END;
        match_result_page=MATCH_RESULT_PAGE_FINAL;
        match_result_surface=MATCH_RESULT_SURFACE_FULL_MENU;
        virtual_cursor_context=PES_VIRTUAL_CURSOR_FULL_TIME;
        match_result_input_action=input;
        match_result_process_controller_input((void *)123);
        assert(footer_calls==1 && stats_calls==0 && pause_calls==0);
        assert(wait_calls==0 && event_calls==0); // footer owns its handshake
        assert(match_result_exit_requested && pause_top_menu_transition_tick);
        assert(virtual_cursor_context==PES_VIRTUAL_CURSOR_NONE);
        match_result_input_action=input;
        match_result_process_controller_input((void *)123);
        assert(footer_calls==1); // no double activation during handoff
      }
  reset(); stub_phase=MATCH_PHASE_HALFTIME;
  match_result_page=MATCH_RESULT_PAGE_INTERVAL;
  match_result_surface=MATCH_RESULT_SURFACE_HALF_MENU;
  match_result_input_action=PES_PAUSE_INPUT_BACK;
  match_result_process_controller_input((void *)123);
  assert(pause_calls==1 && wait_calls==1 && footer_calls==0);
  for (uint32_t full=0; full<2; ++full) {
    reset(); match_result_page=MATCH_RESULT_PAGE_STATS;
    match_result_surface=full?MATCH_RESULT_SURFACE_FULL_STATS:MATCH_RESULT_SURFACE_HALF_STATS;
    match_result_input_action=PES_PAUSE_INPUT_BACK;
    match_result_process_controller_input((void *)123);
    assert(stats_calls==0 && footer_calls==0 && pause_calls==0);
    match_result_input_action=PES_PAUSE_INPUT_DECIDE;
    match_result_process_controller_input((void *)123);
    assert(stats_calls==1 && footer_calls==0 && pause_calls==0 && wait_calls==0);
  }
  reset(); stub_phase=MATCH_PHASE_HALFTIME;
  match_result_page=MATCH_RESULT_PAGE_INTERVAL;
  match_result_surface=MATCH_RESULT_SURFACE_HALF_MENU;
  match_result_input_action=PES_PAUSE_INPUT_DECIDE;
  match_result_process_controller_input((void *)123);
  assert(event_calls==1 && wait_calls==1 && footer_calls==0 && pause_calls==0);
}
'''
        build_and_run(compiler, harness(SOURCE, "\n" + constants + stubs
                      + function(SOURCE, "match_result_process_controller_input") + body))

    def test_pause_settings_back_is_covered_until_pause_returns(self):
        update = SOURCE.split("static uint32_t pes_match_pause_camera_update", 1)[1].split(
            "const char *pes_controller_pause_settings_value", 1)[0]
        self.assertIn("&live_gameplan_returning_to_pause, 1", update)
        self.assertIn("&pause_editor_transition_tick, armGetSystemTick()", update)

    def test_pause_settings_uses_embedded_switch_button_art(self):
        root = Path(__file__).resolve().parents[1]
        overlay = (root / "source/overlay.c").read_text(encoding="utf-8")
        assets = (root / "source/main_menu_assets.h").read_text(encoding="utf-8")
        self.assertIn("main_menu_button_b_tex", overlay)
        self.assertIn('ADD_SWITCH_HELPER("A", action_key_x', overlay)
        self.assertIn('ADD_SWITCH_HELPER("B", back_key_x', overlay)
        self.assertIn("switch_helper_textures[i]", overlay)
        self.assertIn("custom_key_text_quads && !custom_popup", overlay)
        self.assertIn("main_menu_button_b_bin", assets)
        self.assertTrue((root / "data/main_menu_button_b.bin").is_file())


if __name__ == "__main__":
    unittest.main()

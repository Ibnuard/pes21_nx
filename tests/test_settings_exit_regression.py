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
        for enum, label in ((0, "MEDIUM"), (1, "LONG"), (2, "WIDE"), (5, "DYNAMIC WIDE"), (7, "LIVE BROADCAST"), (12, "STADIUM"), (13, "STADIUM CUSTOM")):
            self.assertIn(f'case {enum}: return "{label}";', body)
        self.assertNotIn("PRESET", body)

    def test_stamina_toggle_gates_native_active_player_visibility(self):
        compiler = shutil.which("gcc")
        if not compiler: self.skipTest("gcc unavailable")
        build_and_run(compiler, r'''
#include <stdint.h>
#include <assert.h>
static uint32_t pause_settings_stamina, valid, calls;
static uint32_t native_disp(void *model, uint32_t index) {
  assert(model == (void *)123 && index < 4); ++calls; return valid;
}
static uint32_t (*pause_stamina_disp_original)(void *, uint32_t) = native_disp;
''' + function(SOURCE, "pause_stamina_disp") + r'''
int main(void) {
  for (valid = 0; valid <= 1; ++valid)
    for (uint32_t i = 0; i < 4; ++i) {
      pause_settings_stamina = 0; calls = 0;
      assert(pause_stamina_disp((void *)123, i) == 0 && calls == 0);
      pause_settings_stamina = 1; calls = 0;
      assert(pause_stamina_disp((void *)123, i) == valid && calls == 1);
    }
}
''')

    def test_pause_settings_are_split_into_general_and_camera_pages(self):
        self.assertIn('return index < 7u ? general[index] : "";', SOURCE)
        self.assertIn('"RADAR", "SHOW STAMINA", "GAME SPEED", "NEXT TARGET INDICATOR"', SOURCE)
        self.assertIn('"SHOW REPLAY", "CHANT SFX", "COMMENTARY"', SOURCE)
        self.assertIn('"CAMERA TYPE", "CAMERA HEIGHT", "CAMERA DISTANCE", "CAMERA ANGLE"', SOURCE)
        self.assertIn('focus == 2u ? PAUSE_SETTINGS_PAGE_CAMERA', SOURCE)
        self.assertIn('const uint32_t native_route = focus == 2u ? 1u : focus;', SOURCE)
        camera_field = function(SOURCE, 'pause_settings_camera_field')
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
static uint32_t native_update(void *radar) { assert(radar); ++calls; return 77; }
static uint32_t (*pause_radar_update_original)(void *) = native_update;
''' + function(SOURCE, "pause_radar_update") + r'''
int main(void) {
  unsigned char radar[0x40]={0}, info[2]={9,0}; void *p=info;
  memcpy(radar+0x38,&p,sizeof(p));
  pause_settings_radar=0;
  assert(pause_radar_update(radar)==77 && info[0]==0 && calls==1);
  pause_settings_radar=1;
  assert(pause_radar_update(radar)==77 && info[0]==1 && calls==2);
}
''')
        install = SOURCE.split('void install_ue4_hooks', 1)[1]
        self.assertIn('"_ZN7match2D6Screen5Radar6UpdateEv"', install)
        self.assertIn('*radar_update_slot = (uintptr_t)&pause_radar_update;', install)

    def test_game_speed_targets_embedded_registry_settings_and_refreshes_match(self):
        body = function(SOURCE, 'pause_settings_set_game_speed')
        self.assertIn('(unsigned char *)registry_system + 0x14', body)
        self.assertIn('pause_match_listener_change_game_speed(listener)', body)
        self.assertIn('pause_registry_game_speed_get_fps(registry_speed)', body)
        self.assertIn('pause_basic_status_get_pes_module_thread_fps()', body)
        self.assertIn('&pause_game_speed_debug_apply_count, 1', body)
        root = Path(__file__).resolve().parents[1]
        overlay = (root / 'source/overlay.c').read_text(encoding='utf-8')
        self.assertIn('pes_controller_game_speed_debug(&game_speed_debug)', overlay)
        self.assertIn('GAME SPEED DBG UI:%+d TMP:%u REG:%u TARGET:%uFPS', overlay)
        install = SOURCE.split('void install_ue4_hooks', 1)[1]
        self.assertIn('"_ZNK5match8registry17GameSpeedSettings10GetGameFPSEv"', install)
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
        self.assertIn('static const uint8_t pause_camera_types[] = '
                      '{0u, 1u, 2u, 5u, 7u, 12u, 13u};', SOURCE)
        update = function(SOURCE, 'pes_match_pause_camera_update')
        self.assertIn('settings[0] = pause_camera_types[next]', update)
        self.assertIn('const int opening = window && window != match_pause_camera_window;', update)
        self.assertIn('pause_settings_restore_camera(window)', update)
        self.assertIn('pause_settings_capture_camera()', update)
        self.assertIn('pause_settings_apply_camera(window)', update)
        capture = function(SOURCE, 'pause_settings_capture_camera')
        restore = function(SOURCE, 'pause_settings_restore_camera')
        self.assertIn('sizeof(pause_camera_saved_settings)', capture)
        self.assertIn('&pause_camera_saved_valid, 1', capture)
        self.assertIn('memcpy(settings, pause_camera_saved_settings', restore)
        self.assertIn('pause_settings_apply_camera(window)', restore)
        setup = function(SOURCE, 'pes_exhibition_match_setup_data_entry')
        self.assertIn('&pause_camera_saved_valid, 0', setup)

    def test_broadcast_camera_tracking_is_fully_native_again(self):
        root = Path(__file__).resolve().parents[1]
        assembly = (root / 'source/cobra_pad_hook.s').read_text(encoding='utf-8')
        self.assertNotIn('pes_inplay_ball_position_broadcast', SOURCE)
        self.assertNotIn('GetBallPositionBroadcast', SOURCE)
        self.assertNotIn('inplay_ball_position_broadcast_resume', assembly)
        # BallInfo remains for set-piece charge prediction, which is unrelated
        # to Stadium/Live Broadcast target selection.
        self.assertIn('match_ball_info_get_trans', SOURCE)

    def test_stamina_mobile_branch_returns_validated_visibility(self):
        # Frozen native tail: the instruction AFTER the patched CBZ clears
        # w20. Execute that tail to catch NOP fall-through hiding every player.
        patch = re.search(r"stamina_disp_code \+ 0x12c, 0x34000128, (0x[0-9a-f]+)", SOURCE)
        self.assertIsNotNone(patch)
        for visible in (0, 1):
            words = {0x12c: int(patch[1], 16), 0x130: 0x2a1f03f4,
                     0x134: 0x2a1403e0}
            pc, w20, w0 = 0x12c, visible, None
            for _ in range(4):
                insn = words.get(pc)
                if insn is None: self.fail(f"visibility left validated return path at {pc:x}")
                if insn & 0xfc000000 == 0x14000000:
                    imm = insn & 0x03ffffff
                    if imm & 0x02000000: imm -= 0x04000000
                    pc += imm * 4
                    continue
                if insn == 0x2a1f03f4: w20 = 0
                elif insn == 0x2a1403e0:
                    w0 = w20
                    break
                elif insn != 0xd503201f: self.fail(f"unhandled ARM instruction {insn:x}")
                pc += 4
            self.assertEqual(w0, visible)

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

"""Scope guards for the isolated two-controller native-pad experiment."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NativeGamepadLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hooks = (ROOT/'source/ue4_hooks.c').read_text(encoding='utf-8')
        cls.shim = (ROOT/'source/android_shim.c').read_text(encoding='utf-8')

    def test_tile_requires_two_hid_slots_then_starts_fixed_2p_match(self):
        choice = re.search(r'if \(choice == 2\) \{(.*?)\n  \}',
                           self.hooks, re.S).group(1)
        self.assertIn('pes_controller_native_hid_connected_mask()', choice)
        self.assertIn('(connected & 3u) != 3u', choice)
        self.assertIn('MAIN_MENU_INFO_TWO_PLAYER', choice)
        self.assertIn('native_gamepad_lab_active', choice)
        self.assertIn('native_gamepad_lab_two_player', choice)
        self.assertIn('exhibition_home_team_id, 108', choice)
        self.assertIn('exhibition_away_team_id, 114', choice)
        self.assertIn('MyClub/TutorialMatch', choice)
        self.assertIn('exhibition_flow_direct_set', choice)

    def test_exhibition_and_lab_share_native_gameplay_path_after_play(self):
        self.assertIn('if (native_pad_lab_active && gameplay_active)',
                      self.shim)
        self.assertIn('emit_native_lab_pad_input(0, &left_stick, &right_stick,',
                      self.shim)
        self.assertIn('emit_native_lab_pad_input(1, &left_stick_p2, &right_stick_p2,',
                      self.shim)
        self.assertIn('pes_controller_native_pad_lab_debug_input(port, mapped, x, y,',
                      self.shim)
        self.assertIn('HidNpadIdType_No2', self.shim)
        self.assertIn('padConfigureInput(2, HidNpadStyleSet_NpadStandard)',
                      self.shim)
        enable = re.search(
            r'static void native_pad_lab_enable_exhibition\(void\) \{.*?\n\}',
            self.hooks, re.S).group(0)
        self.assertIn('native_gamepad_lab_two_player, 0', enable)
        strategy = re.search(
            r'static void pes_exhibition_strategy_footer\([^;]*\)\s*\{.*?\n\}',
            self.hooks, re.S).group(0)
        self.assertIn('if (!pes_controller_native_pad_lab_two_player())',
                      strategy)
        self.assertIn('native_pad_lab_enable_exhibition()', strategy)
        self.assertIn('preserving P1-vs-P2 gameplay bridge', strategy)
        self.assertIn('exhibition_strategy_action', strategy)
        self.assertNotIn('SetDataControl', self.hooks)

    def test_matchplan_uses_stock_pad_port_ownership_for_both_sides(self):
        self.assertIn('_ZN9matchPlan4Data10SetPadPortE8HomeAwayj', self.hooks)
        helper = re.search(
            r'static void native_lab_assign_matchplan_pads.*?\n\}',
            self.hooks, re.S).group(0)
        self.assertIn('exhibition_matchplan_set_pad_port(data, 0, 0)', helper)
        self.assertIn('exhibition_matchplan_set_pad_port(data, 1, 1)', helper)
        self.assertIn('pes_controller_native_pad_lab_two_player()', helper)
        self.assertNotIn('SetDataControl', helper)

    def test_tmpdb_cursor_post_hook_creates_local_away_owner_only_in_2p_lab(self):
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        asm = (ROOT/'source/cobra_pad_hook.s').read_text(encoding='utf-8')
        self.assertIn('SetCursorInfoFromTmpdb', route)
        self.assertIn('native_lab_bind_away_cursor', route)
        self.assertIn('pes_match_cursor_info_ready', route)
        self.assertIn('pes_controller_native_pad_lab_two_player()', route)
        self.assertIn('away[0] = 2', route)
        self.assertIn('pad_no = 1', route)
        self.assertIn('pes_match_cursor_info_from_tmpdb_hook:', asm)
        self.assertIn('bl pes_match_cursor_info_ready', asm)
        self.assertIn('sub sp, sp, #0x1e0', asm)

    def test_native_face_button_positions_match_existing_switch_layout(self):
        mapping = re.search(r'static void emit_native_lab_pad_input.*?\n\}',
                            self.shim, re.S).group(0)
        expected = {'B': 0, 'A': 1, 'Y': 2, 'X': 3,
                    'L': 4, 'ZL': 5, 'R': 7, 'ZR': 8}
        for button, bit in expected.items():
            with self.subTest(button=button):
                self.assertIn(f'HidNpadButton_{button}', mapping)
                self.assertIn(f'mapped |= 1u << {bit};', mapping)
        self.assertIn('HidNpadButton_AnySL', mapping)
        self.assertIn('HidNpadButton_AnySR', mapping)

    def test_setplays_keep_stock_consumers_and_bridge_native_kick_methods(self):
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        self.assertNotIn('native_setplay && kind == 95', route)
        self.assertNotIn('native_setplay && kind == 90', route)
        self.assertIn('native_lab_mobile_kick_main', route)
        self.assertIn('native_lab_exec_setplay_action', route)
        self.assertIn('native_lab_short_press_original(unit, input)', route)
        self.assertIn('native_lab_long_press_original(unit, input)', route)
        self.assertIn('native_lab_shoot_press_original(unit, input)', route)
        self.assertIn('_ZTVN5match3pad26ThinkUnitMobileSetplayKickE', route)
        self.assertIn('PES_NATIVE_LAB_ROUTE_GOALKICK_SUPPORT', route)
        self.assertIn('PES_NATIVE_LAB_ROUTE_CORNER_TACTICS', route)
        self.assertIn('PES_NATIVE_LAB_ROUTE_FREEKICK_TACTICS', route)
        self.assertIn('PES_NATIVE_LAB_ROUTE_CAMERA_STICK', route)
        self.assertIn('PES_NATIVE_LAB_ROUTE_SETPLAY_GUIDE', route)
        self.assertIn('native_lab_append(entries, &count, 26)', route)
        self.assertNotIn('native_lab_reset_setplay_action_power', route)
        self.assertNotIn('native_lab_kick_power_milli', route)
        self.assertIn('ThinkUnitThrowinBodyAngleRotation', route)
        self.assertNotIn('touch_state_append', route)
        self.assertNotIn('GetSwipeVec', route)

    def test_right_stick_enters_native_cobra_axis_slots(self):
        self.assertIn('cobra_pad_set_native_input_for_port(',
                      self.shim)
        apply_input = re.search(
            r'uintptr_t cobra_pad_apply_input.*?\n\}', self.hooks, re.S
        ).group(0)
        self.assertIn('memcpy(pad + 140 + 20 * 4, right_directions,',
                      apply_input)
        self.assertIn('cobra_pad_right_input', apply_input)

    def test_lab_routes_distinct_inputs_only_to_internal_pad_zero_and_one(self):
        apply_input = re.search(
            r'uintptr_t cobra_pad_apply_input.*?\n\}', self.hooks, re.S
        ).group(0)
        self.assertIn('use_p2 ? &cobra_pad_input_p2', apply_input)
        self.assertIn('pad_id > (two_player ? 1 : 0)', apply_input)
        self.assertIn('const uint64_t packed = reject_pad', apply_input)

    def test_thinkunit_accessor_is_scoped_to_each_canonical_pad_unit(self):
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        binding = re.search(
            r'static int native_lab_bind_input.*?\n\}', route, re.S
        ).group(0)
        self.assertIn('(const char *)input + 0x08', binding)
        self.assertIn('(const char *)input + 0x18', binding)
        self.assertIn('&native_lab_input_units[expected_pad]', binding)
        update = re.search(
            r'static void native_lab_list_update\(.*?\n\}', route, re.S
        ).group(0)
        self.assertLess(update.index('native_lab_bind_input'),
                        update.index('native_lab_list_update_original'))
        self.assertLess(update.index('native_lab_list_update_original'),
                        update.index('native_lab_restore_input'))

    def test_both_cobra_pads_are_primed_before_native_history_update(self):
        prime = re.search(
            r'int cobra_pad_prime_native_port\(.*?\n\}', self.hooks, re.S
        ).group(0)
        self.assertIn('pad[1] = connected ? 1 : 0', prime)
        self.assertIn('memcpy(pad + 16, &buttons', prime)
        self.assertIn('memcpy(pad + 20, &clicked', prime)
        self.assertIn('pad + 140 + 16 * 4', prime)
        self.assertIn('pad + 140 + 20 * 4', prime)
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        sample = re.search(
            r'static void native_lab_sample\(.*?\n\}', route, re.S
        ).group(0)
        self.assertLess(sample.index('cobra_pad_prime_native_port(pad_no)'),
                        sample.index('native_lab_sample_original'))

    def test_setplay_sticks_hook_each_stock_camera_plugin(self):
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        self.assertNotIn('append_native_setplay_camera_swipe(', self.shim)
        self.assertIn('native_lab_apply_camera_stick', route)
        self.assertIn('&native_lab_debug_right_axis_x_p2', route)
        for camera in ('CornerKickCamera', 'GoalKickCamera',
                       'FreeKickCamera'):
            with self.subTest(camera=camera):
                self.assertIn(camera, route)
        self.assertIn('state->yaw += axis_x * 0.025f', route)
        self.assertIn('state->yaw > 0.55f', route)
        self.assertIn('parameter->position_x = parameter->look_x', route)
        self.assertIn('parameter->position_z = parameter->look_z', route)
        camera = re.search(
            r'static void native_lab_apply_camera_stick.*?\n\}',
            route, re.S).group(0)
        self.assertNotIn('raw_y', camera)
        self.assertNotIn('raw_left_x', camera)
        self.assertNotIn('camera_lock', camera)
        self.assertIn('float axis_x = (float)raw_x / 32768.0f', camera)
        self.assertIn('const float absolute_x = fabsf(axis_x)', camera)

    def test_native_command_angle_inherits_rs_camera_and_direct_ls_aim(self):
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        aim = re.search(
            r'static void native_lab_apply_native_kick_angle.*?\n\}',
            route, re.S).group(0)
        self.assertIn('(const char *)unit + 0x38', aim)
        self.assertNotIn('(char *)unit + 0x24', aim)
        self.assertNotIn('native_lab_mobile_filter_angle', aim)
        self.assertIn('native_lab_camera_yaw_millirad[pad]', aim)
        self.assertIn('57.2957795131f', aim)
        self.assertIn('native_lab_debug_axis_x', aim)
        self.assertIn('native_lab_debug_axis_y', aim)
        self.assertIn('atan2f(-left_x, left_y)', aim)
        self.assertIn('desired -= left_x * 60.0f', aim)
        self.assertIn('native_lab_command_angle_bits[pad]', aim)
        self.assertIn('native_lab_left_aim_latched_mask', aim)
        self.assertIn('memcpy(&desired, &previous_bits', aim)
        self.assertNotIn('touch_state_append', aim)
        command = re.search(
            r'static void native_lab_adjust_kick.*?\n\}', route, re.S
        ).group(0)
        self.assertIn('memcpy(angle, &angle_bits', command)
        self.assertIn('native_lab_set_kick_no_player', route)
        self.assertIn('(uintptr_t)module->load_base + 0x391ed80', route)
        bridge = re.search(
            r'static uint32_t native_lab_mobile_kick_main.*?\n\}',
            route, re.S).group(0)
        self.assertNotIn('native_lab_guide_main_original(guide', bridge)
        guide = re.search(
            r'static uint32_t native_lab_guide_main.*?\n\}', route, re.S
        ).group(0)
        self.assertIn('return 0;', guide)
        self.assertLess(guide.index('return 0;'),
                        guide.index('native_lab_guide_main_original'))

    def test_native_setplay_uses_right_for_custom_kicker_and_keeps_l_stock(self):
        self.assertIn('queue_native_lab_setplay_action', self.shim)
        self.assertIn('pressed & HidNpadButton_Right', self.shim)
        self.assertIn('PES_SETPLAY_BUTTON_SET_PIECE_TAKER', self.shim)
        self.assertIn('HidNpadButton_Right | HidNpadButton_Minus', self.shim)
        overlay = (ROOT/'source/overlay.c').read_text(encoding='utf-8')
        self.assertIn('NATIVE 2P SETPLAY V8.15.1', overlay)
        self.assertIn('setplay_keys[0] = "L";', overlay)
        self.assertIn('setplay_keys[1] = ">";', overlay)
        self.assertNotIn('CAMERA LOCK', overlay)
        self.assertIn('"TRAJECTORY ON"', overlay)
        self.assertIn('setplay_keys[4] = "R";', overlay)
        throw_helper = re.search(
            r'else if \(native_setplay_debug &&\s*'
            r'setplay_context == PES_SETPLAY_THROW_IN\).*?'
            r'setplay_helper_count = 1;', overlay, re.S).group(0)
        self.assertIn('"SET THROWER"', throw_helper)
        self.assertNotIn('"LONG THROW"', throw_helper)
        self.assertNotIn('"NORMAL THROW"', throw_helper)
        self.assertIn('native_far_free_kick', overlay)
        far_helper = re.search(
            r'else if \(native_far_free_kick\).*?'
            r'setplay_helper_count = 1;', overlay, re.S).group(0)
        self.assertIn('setplay_keys[0] = ">";', far_helper)
        self.assertIn('"SET PIECE TAKER"', far_helper)
        self.assertNotIn('"ZR"', far_helper)
        self.assertIn('!native_setplay_debug && !native_lab', overlay)

    def test_defending_pad_cannot_clear_attacking_setplay_owner(self):
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        update = re.search(
            r'static void native_lab_list_update\(.*?\n\}', route, re.S
        ).group(0)
        self.assertIn('&native_lab_debug_setplay_pad', update)
        self.assertIn('setplay_pad == (uint32_t)route_pad', update)
        self.assertIn("defender clears the attacker's context", update)

    def test_custom_pad_owned_gauge_is_visual_only(self):
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        gauge = re.search(
            r'static void native_lab_track_action_power.*?\n\}',
            route, re.S).group(0)
        self.assertIn('(const char *)power_unit + 0x20', gauge)
        self.assertIn('(char *)screen_2d + 0x10b9', gauge)
        self.assertIn('native_lab_gauge_owner_pad', gauge)
        self.assertIn('native_lab_gauge_power_milli', gauge)
        self.assertNotIn('native_lab_draw_shoot_line', gauge)
        overlay = (ROOT/'source/overlay.c').read_text(encoding='utf-8')
        self.assertIn('power_gauge_background_first_quad', overlay)
        self.assertIn('power_gauge_segment_first_quad', overlay)
        self.assertIn('native_debug.gauge_active_mask & (1u << pad)', overlay)
        self.assertIn('native_debug.gauge_power_milli', overlay)
        self.assertIn('0.12f + 0.88f * t', overlay)
        self.assertIn('native_lab_gauge_linger_frames', route)
        self.assertIn('native_lab_gauge_active_mask', route)
        self.assertIn('native_lab_gauge_charging_mask', route)
        self.assertIn('native_lab_gauge_power_milli_p2', route)
        self.assertIn(': 180u', route)
        self.assertIn('native_debug.gauge_anchor_valid_mask', overlay)
        self.assertIn('native_debug.gauge_anchor_x_milli_p2', overlay)
        self.assertIn('if (!anchor_valid)\n        continue;', overlay)
        self.assertIn('const float bar_w = 0.075f', overlay)
        self.assertIn('const float bar_h = 0.0060f', overlay)
        self.assertIn('const float gap = 0.0f', overlay)
        hooks = (ROOT/'source/ue4_hooks.c').read_text(encoding='utf-8')
        self.assertIn('ModelCursorName11GetPosition', hooks)
        self.assertIn('ProjectPos3DToScreen', hooks)
        self.assertIn('pes_match_cursor_name_get_position', hooks)
        self.assertIn('match_global_registry_get_player_move', hooks)
        self.assertIn('(const char *)player_move + 0x55c', hooks)
        self.assertIn('(const char *)registry + 0x90', hooks)
        self.assertIn('native_lab_gauge_observe_released_ball', route)

    def test_regular_gameplay_gauge_lifecycle_is_not_cleared_by_none_context(self):
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        publish = re.search(
            r'void pes_controller_native_pad_lab_publish_setplay_context'
            r'.*?\n\}', route, re.S).group(0)
        self.assertNotIn('native_lab_gauge_clear_all();', publish)
        self.assertIn('native_lab_gauge_charging_mask', route)
        self.assertIn('? 900u', route)
        self.assertIn(': 180u', route)
        self.assertIn('native_lab_gauge_player_no_by_pad', route)
        self.assertIn('native_lab_gauge_release_ball_valid_mask', route)
        self.assertIn('native_lab_gauge_release_min_distance_bits', route)
        self.assertIn('native_lab_gauge_completion_frames', route)
        self.assertIn('player_distance_sq >= min_distance_sq + 0.49f', route)
        self.assertIn('(const char *)input + 0x24', route)
        self.assertNotIn('(const char *)cursor + 0x20', route)
        hooks = (ROOT/'source/ue4_hooks.c').read_text(encoding='utf-8')
        self.assertIn('(action_player_no >= 11u ? 1u : 0u) != index', hooks)

    def test_native_context_wins_over_one_frame_lagging_ui_snapshot(self):
        overlay = (ROOT/'source/overlay.c').read_text(encoding='utf-8')
        native_context = re.search(
            r'int native_setplay_debug.*?\n  \}', overlay, re.S).group(0)
        self.assertIn('setplay_context = native_debug.context', native_context)
        self.assertIn('setplay_options = 0', native_context)
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        detector = re.search(
            r'static uint32_t native_lab_setplay_context.*?\n\}',
            route, re.S).group(0)
        self.assertIn('pes_controller_setplay_context()', detector)
        self.assertIn('has_setplay_unit', detector)

    def test_real_setplay_trajectory_uses_ls_angle_and_stock_cross_renderer(self):
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        trajectory = re.search(
            r'static void native_lab_publish_setplay_trajectory\('
            r'const void \*input,\s*void \*screen_2d\) \{.*?\n\}',
            route, re.S).group(0)
        self.assertIn('native_lab_command_angle_bits[pad]', trajectory)
        self.assertIn('native_lab_draw_pass_line(0x50u', trajectory)
        self.assertIn('0xffu', trajectory)
        self.assertIn('(buttons & (1u << 7))', route)
        self.assertIn('PES_NATIVE_LAB_STOCK_MOBILE_KICK', route)
        self.assertIn('native_lab_publish_setplay_trajectory(input, screen_2d)',
                      route)
        policy = (ROOT/'source/match_visual_policy.h').read_text(
            encoding='utf-8')
        self.assertIn('pes_set_pitch_trajectory', policy)
        self.assertIn('index = 11; index <= 12', policy)
        self.assertIn('pes_set_pitch_trajectory(manager, 1', self.hooks)

    def test_penalty_roles_and_trajectory_are_pad_owned(self):
        hooks = (ROOT/'source/ue4_hooks.c').read_text(encoding='utf-8')
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        overlay = (ROOT/'source/overlay.c').read_text(encoding='utf-8')
        self.assertIn('match_penalty_role_by_pad[2]', hooks)
        self.assertIn('match_native_penalty_input_pad', hooks)
        self.assertIn('pes_controller_penalty_role_for_pad', hooks)
        self.assertIn('PenaltyGestureState states[2]', self.shim)
        self.assertIn('previous_hid_buttons_p2', self.shim)
        self.assertIn('pes_controller_native_penalty_ready(0, penalty_role_p1)',
                      self.shim)
        self.assertIn('penalty_active && native_pad_lab_active', self.shim)
        self.assertIn('emit_native_lab_pad_input(1, &left_stick_p2,',
                      self.shim)
        self.assertIn('queue_native_penalty_action', self.shim)
        self.assertIn('match_penalty_touch_owner_pad', hooks)
        self.assertIn('owner_pad != match_native_penalty_input_pad(input)',
                      hooks)
        self.assertIn('!native_ready', hooks)
        self.assertIn('native_lab_penalty_guide_units[2]', route)
        self.assertIn('native_lab_penalty_action_units[2]', route)
        self.assertIn('native_lab_penalty_trajectory_enabled_mask', route)
        self.assertIn('ThinkUnitPenaltykickGuideE', route)
        self.assertIn('ThinkUnitPenaltykickE', route)
        self.assertIn('ThinkUnitKeeperPenaltykickMoveE', route)
        self.assertIn('ThinkUnitKeeperPenaltykickActionE', route)
        self.assertIn('ThinkUnitKeeperPenaltykickLayerE', route)
        self.assertIn('NATIVE_LAB_KIND_PENALTY_KICK = 37', route)
        self.assertIn('NATIVE_LAB_KIND_KEEPER_PENALTY_MOVE = 43', route)
        self.assertIn('NATIVE_LAB_KIND_KEEPER_PENALTY_ACTION = 44', route)
        self.assertIn('NATIVE_LAB_KIND_KEEPER_PENALTY_LAYER = 66', route)
        self.assertIn('native_lab_optional_penalty_units', route)
        self.assertIn('native_lab_penalty_suite_matches', route)
        self.assertIn('pes_controller_native_penalty_ready', route)
        self.assertIn('native_lab_penalty_press', route)
        self.assertIn('native_lab_penalty_pull', route)
        self.assertIn('native_lab_draw_shoot_line(0x58u', route)
        self.assertIn('"P1 KICKER + LS AIM"', overlay)
        self.assertIn('"P2 KEEPER DIVE"', overlay)
        self.assertIn('"TRAJECTORY ON/OFF"', overlay)
        helper = re.search(
            r'const int penalty_helper_active =.*?;\n'
            r'  if \(!setplay_helper_count', overlay, re.S).group(0)
        self.assertIn('penalty_role_p1 != PES_PENALTY_NONE', helper)
        self.assertIn('penalty_role_p2 != PES_PENALTY_NONE', helper)

    def test_penalty_list_heartbeat_has_priority_over_touch_fallback(self):
        hooks = (ROOT/'source/ue4_hooks.c').read_text(encoding='utf-8')
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        overlay = (ROOT/'source/overlay.c').read_text(encoding='utf-8')
        self.assertIn('match_native_penalty_publish_for_pad', hooks)
        self.assertIn('native_penalty_goalkeeper', route)
        self.assertIn('ThinkUnitList is the only callback', route)
        self.assertIn('const int penalty_session_active', overlay)
        self.assertIn('native_setplay_debug = 0', overlay)
        self.assertIn('setplay_options = 0', overlay)
        self.assertIn('> 600000000ULL', hooks)

    def test_close_free_kick_vertical_bridge_is_release_scoped(self):
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        bridge = re.search(
            r'static void native_lab_adjust_kick.*?\n\}', route, re.S).group(0)
        self.assertIn('native_lab_pending_kick_command', bridge)
        self.assertIn('PES_SETPLAY_FREE_KICK', bridge)
        self.assertIn('native_lab_pending_kick_power_bits', bridge)
        self.assertIn('native_lab_pending_kick_action', bridge)
        self.assertIn('*kick_power = native_power', bridge)
        self.assertIn('native_lab_command_vertical_bits[pad]', bridge)
        release = re.search(
            r'static uint32_t native_lab_exec_setplay_action.*?\n\}',
            route, re.S).group(0)
        self.assertLess(release.index('(const char *)unit + 0x20'),
                        release.index('native_lab_short_pull_original'))

    def test_second_pad_can_drive_selector_replay_and_title_start(self):
        self.assertIn('previous_hid_buttons_p2', self.shim)
        self.assertIn('native_setplay_owner_pad == 1', self.shim)
        self.assertIn('(buttons_p2 & ~previous_hid_buttons_p2)', self.shim)
        self.assertIn('controller_connected || controller_connected_p2',
                      self.shim)
        self.assertIn('pes_controller_start_prompt(NULL, NULL)', self.shim)
        self.assertIn('HidNpadButton_AnySL | HidNpadButton_AnySR', self.shim)

    def test_goal_and_throw_helpers_preserve_native_actions(self):
        self.assertIn('PES_SETPLAY_BUTTON_SELECT_THROWER', self.shim)
        self.assertIn('ui->setplay_context == PES_SETPLAY_THROW_IN',
                      self.shim)
        self.assertIn('pes_controller_native_pad_lab_two_player()',
                      self.hooks)
        self.assertIn('pes_match_goal_button_update', self.hooks)
        self.assertIn('match_node_set_alpha(root, 0.0f)', self.hooks)
        self.assertIn('ButtonGoalPerformance25UpdatePreControlWindowSub',
                      self.hooks)


if __name__ == '__main__':
    unittest.main()

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

    def test_normal_exhibition_stays_touch_and_lab_is_native_only_in_play(self):
        self.assertIn('if (!(native_pad_lab_active && gameplay_active))',
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
                self.assertRegex(
                    mapping,
                    rf'HidNpadButton_{button}\) mapped \|= 1u << {bit};')

    def test_setplays_use_native_units_not_mobile_swipe(self):
        route = (ROOT/'source/native_pad_lab.inc').read_text(encoding='utf-8')
        self.assertIn('native_setplay && kind == 95', route)
        self.assertIn('native_setplay && kind == 90', route)
        for kind in (26, 0, 1, 3):
            self.assertIn(f'native_lab_append(entries, &count, {kind})', route)
        self.assertIn('PES_NATIVE_LAB_ROUTE_GOALKICK_SUPPORT', route)
        self.assertIn('PES_NATIVE_LAB_ROUTE_CORNER_TACTICS', route)
        self.assertIn('PES_NATIVE_LAB_ROUTE_FREEKICK_TACTICS', route)
        self.assertIn('PES_NATIVE_LAB_ROUTE_CAMERA_STICK', route)
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

    def test_secondary_cobra_pad_is_primed_before_native_history_update(self):
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
        self.assertLess(sample.index('cobra_pad_prime_native_port(1)'),
                        sample.index('native_lab_sample_original'))


if __name__ == '__main__':
    unittest.main()

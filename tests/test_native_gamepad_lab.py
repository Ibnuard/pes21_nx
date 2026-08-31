"""Scope guards for the intentionally single-player native-pad experiment."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NativeGamepadLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hooks = (ROOT/'source/ue4_hooks.c').read_text(encoding='utf-8')
        cls.shim = (ROOT/'source/android_shim.c').read_text(encoding='utf-8')

    def test_tile_is_fixed_single_player_lab_not_second_pad(self):
        choice = re.search(r'if \(choice == 2\) \{(.*?)\n  \}',
                           self.hooks, re.S).group(1)
        self.assertIn('native_gamepad_lab_active', choice)
        self.assertIn('exhibition_home_team_id, 108', choice)
        self.assertIn('exhibition_away_team_id, 114', choice)
        self.assertIn('MyClub/TutorialMatch', choice)
        self.assertIn('exhibition_flow_direct_set', choice)
        self.assertNotIn('MAIN_MENU_INFO_TWO_PLAYER', choice)
        self.assertNotIn('pad_port', choice.lower())
        self.assertNotIn('memcpy', choice)

    def test_normal_exhibition_stays_touch_and_lab_is_native_only_in_play(self):
        self.assertIn('if (!(native_pad_lab_active && gameplay_active))',
                      self.shim)
        self.assertIn('else if (native_pad_lab_active && gameplay_active)\n'
                      '    emit_native_lab_pad_input', self.shim)
        self.assertNotIn('HidNpadIdType_No2', self.shim)
        self.assertNotIn('SetDataControl', self.hooks)
        self.assertNotIn('native_lab_matchplan', self.hooks)

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

    def test_lab_input_is_injected_into_internal_pad_zero_only(self):
        apply_input = re.search(
            r'uintptr_t cobra_pad_apply_input.*?\n\}', self.hooks, re.S
        ).group(0)
        self.assertIn('pes_controller_native_pad_lab_active() && pad_id != 0',
                      apply_input)
        self.assertRegex(apply_input, r'pad_id != 0\) \{\s*buttons = 0;\s*'
                                          r'x = 0;\s*y = 0;')


if __name__ == '__main__':
    unittest.main()

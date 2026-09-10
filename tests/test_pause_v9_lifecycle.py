"""Regression checks for diagnostic lifecycle changes; not a hardware test."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class LifecycleTests(unittest.TestCase):
    def test_concrete_editor_hook_runs_native_before_custom_and_preserves_return(self):
        asm = (ROOT / 'source/cobra_pad_hook.s').read_text()
        hook = asm.split('pes_match_squad_edit_update_hook:', 1)[1].split('.size', 1)[0]
        self.assertLess(hook.index('bl .Lmatch_squad_original'),
                        hook.index('bl pes_match_squad_edit_update_entry'))
        self.assertIn('str x0, [sp, #32]', hook)
        self.assertIn('ldr x0, [sp, #32]', hook)
        self.assertIn('stp x19, x20, [sp, #16]', hook)
        self.assertIn('ldp x19, x20, [sp, #16]', hook)

    def test_pause_native_routes_can_request_custom_editor(self):
        src = (ROOT / 'source/ue4_hooks.c').read_text()
        self.assertIn('if (!live_gameplan_window) live_gameplan_open_requested = 1;', src)
        self.assertIn('window && !live_gameplan_window && pes_controller_native_pad_lab_active()', src)

    def test_prematch_observer_preserves_native_visibility_result(self):
        src = (ROOT / 'source/ue4_hooks.c').read_text()
        body = src.split('static uint32_t pes_prematch_card_need_disp(', 1)[1].split('\n}', 1)[0]
        self.assertIn('prematch_card_need_disp_original(screen)', body)
        self.assertIn('kickoff_loading_reveal();', body)
        self.assertIn('return visible;', body)
        self.assertIn('pause-v9: prematch card hook runtime=', src)

if __name__ == '__main__':
    unittest.main()

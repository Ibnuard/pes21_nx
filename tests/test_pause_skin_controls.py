"""Regression guards for the pause skin's separate presentation/input paths."""
from pathlib import Path
import unittest
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


class PauseSkinTests(unittest.TestCase):
    def test_fullscreen_pause_draws_background_before_header_and_controls(self):
        overlay = (ROOT / 'source/overlay.c').read_text()
        bg = overlay.index('glDrawArrays(GL_TRIANGLES, pause_background * 6')
        self.assertLess(bg, overlay.index('glDrawArrays(GL_TRIANGLES, pause_header * 6'))
        self.assertLess(bg, overlay.index('glDrawArrays(GL_TRIANGLES, pause_skin_cards'))
        self.assertIn('pes_controller_pause_score(side, &score)', overlay)
        self.assertIn('quads += emit_image_rect(0, 0, screen_width, screen_height', overlay)

    def test_legacy_popup_does_not_follow_pause_active_flag(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        self.assertNotIn('match_pause_custom_active', function(hooks, 'pes_controller_custom_info_popup_active'))

    def test_update_consumes_actions_instead_of_discarding_them(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        update = function(hooks, 'pes_match_pause_update_entry')
        self.assertIn('__atomic_exchange_n(&match_pause_custom_action', update)
        self.assertNotIn('__atomic_store_n(&match_pause_custom_action, 0', update)
        self.assertIn('match_pause_choice_touch(window, event)', update)
        self.assertIn('match_pause_pad_event_back(window)', update)

    def test_analog_repeat_and_pointerless_input_path_exist(self):
        shim = (ROOT / 'source/android_shim.c').read_text()
        self.assertIn('if (!custom_prematch_gameplan_active && (gameplan_cursor_active ||', shim)
        self.assertIn('pause_stick_repeat_ms', shim)
        overlay = (ROOT / 'source/overlay.c').read_text()
        self.assertIn('pes_controller_custom_info_popup_active() && !pause_skin', overlay)

    def test_live_editor_uses_native_reservations_and_not_bootstrap(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        child = function(hooks, 'pes_match_squad_edit_update_entry')
        self.assertNotIn('exhibition_gameplan_prepare_matchplan()', child)
        self.assertIn('live_gameplan_window = window', child)
        swap = function(hooks, 'prematch_gameplan_swap')
        self.assertIn('live_squad_can_reserve(state->squad_data, out, in)', swap)
        self.assertIn('live_squad_reserve(state->squad_data, out, in)', swap)
        root = function(hooks, 'prematch_gameplan_process_root')
        self.assertIn('exhibition_gameplan_sides[1u - side].waiting', root)
        self.assertIn('live_gameplan_footer(window, 1u)', root)
        self.assertIn('if (live_gameplan_window) return;', root)

    def test_stats_never_store_native_record_pointer(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        snapshot = function(hooks, 'pause_record_get_stats')
        self.assertIn('500000000ULL', snapshot)
        self.assertIn('pause_stats_data(team, kinds[row], 5)', snapshot)
        self.assertNotIn('static void *', snapshot.split('{', 1)[1])
        self.assertIn('&pause_stats_seen, 0', function(hooks, 'pes_exhibition_match_setup_data_entry'))

    def test_live_open_initializes_com_and_consumes_request(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        child = function(hooks, 'pes_match_squad_edit_update_entry')
        self.assertIn('live_gameplan_open_requested && !live_gameplan_window', child)
        self.assertIn('matchplan_squad_load()', child)
        self.assertIn('prematch_gameplan_refresh_side(0)', child)
        self.assertIn('prematch_gameplan_refresh_side(1)', child)
        self.assertIn('live_gameplan_open_requested = 0;', child)
        self.assertNotIn('field_count == 11', child)

    def test_pause_hides_native_surface_without_opaque_cover(self):
        overlay = (ROOT / 'source/overlay.c').read_text()
        self.assertNotIn('pause_content_cover', overlay)
        self.assertIn('0.10f, 0.76f', overlay)
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        self.assertIn('match_node_set_alpha(surface, 0.0f)', function(hooks, 'pes_match_pause_update_entry'))
        self.assertIn('hide ? 0.0f : 1.0f', function(hooks, 'pes_pause_guide_update'))


if __name__ == '__main__':
    unittest.main()

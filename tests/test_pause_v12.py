from pathlib import Path
import unittest
from test_pause_skin_controls import function
ROOT = Path(__file__).resolve().parents[1]

class PauseV12Tests(unittest.TestCase):
    def test_live_portraits_cannot_enter_sync_reader(self):
        src = (ROOT / 'source/ue4_hooks.c').read_text()
        body = function(src, 'prematch_gameplan_load_portrait')
        guard = body.index('if (live_gameplan_open_requested || live_gameplan_window) {')
        self.assertLess(guard, body.index('exhibition_sys_file_sync_read(file)'))
        self.assertIn('return 0;', body[guard:body.index('char path[96]')])

    def test_open_cover_starts_at_request_and_expires(self):
        src = (ROOT / 'source/ue4_hooks.c').read_text()
        self.assertIn('&pause_open_cover_tick, armGetSystemTick()', function(src, 'pes_controller_pause_request_for_pad'))
        self.assertIn('5000000000ULL', function(src, 'pes_controller_pause_skin_active'))
        self.assertIn('&pause_open_cover_tick, 0', function(src, 'pes_match_pause_destroyed'))

if __name__ == '__main__': unittest.main()

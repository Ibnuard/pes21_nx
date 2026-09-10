"""Execute the real root input handler with a mocked native footer."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


class LiveReadyTests(unittest.TestCase):
    def test_independent_ready_single_player_and_auto_lock(self):
        compiler = shutil.which('gcc')
        if not compiler:
            self.skipTest('gcc unavailable')
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        header = (ROOT / 'source/ue4_hooks.h').read_text()
        macros = '\n'.join(line for line in header.splitlines() if
                            re.match(r'#define (PES_PAUSE_INPUT_|PES_PREMATCH_GAMEPLAN_)', line))
        source = r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#define debugPrintf(...) ((void)0)
#define PREMATCH_GAMEPLAN_NO_SELECTION UINT32_MAX
typedef struct { uint32_t waiting, root_focus, page, substitute_area,
 selected_area, selected_index, formation_focus, position_focus,
 position_picker_open; } PrematchGameplanSide;
static PrematchGameplanSide exhibition_gameplan_sides[2];
static void *live_gameplan_window;
static uint32_t exhibition_gameplan_custom_active, main_menu_2p_prematch_hub_input_armed[2];
static uint32_t saved, footer_calls, single_player, auto_calls, published;
static uint64_t pause_editor_transition_tick;
static uint32_t live_gameplan_returning_to_pause;
static uint64_t armGetSystemTick(void) { return 12345; }
static void live_gameplan_cancel_portraits(void) {}
static void live_gameplan_lock_substitutions(uint32_t side, int commit) {}
static int pes_controller_exhibition_single_controller_mode(void) {return single_player;}
static void exhibition_save_matchplan_sides(uint32_t mask) {saved = mask;}
static void exhibition_publish_prepared_matchplan(void) {published++;}
static void prematch_gameplan_prepare_auto_preview(uint32_t side) {auto_calls++;}
static void footer(void *w, uint32_t key) {
 assert(w == (void *)1); assert(key == 1);
 assert(pause_editor_transition_tick == 12345);
 assert(live_gameplan_returning_to_pause);
 assert(!exhibition_gameplan_custom_active);
 footer_calls++;
}
static void (*live_gameplan_footer)(void *, uint32_t) = footer;
'''
        source += '\n' + macros + '\n' + function(hooks, 'prematch_gameplan_process_root')
        source += r'''
int main(void) {
 live_gameplan_window = (void *)1; exhibition_gameplan_custom_active = 1;
 prematch_gameplan_process_root(1, PES_PAUSE_INPUT_BACK);
 assert(exhibition_gameplan_sides[1].waiting && !footer_calls);
 prematch_gameplan_process_root(1, PES_PAUSE_INPUT_BACK);
 assert(!exhibition_gameplan_sides[1].waiting && !footer_calls);
 prematch_gameplan_process_root(0, PES_PAUSE_INPUT_BACK);
 assert(exhibition_gameplan_sides[0].waiting && !footer_calls);
 prematch_gameplan_process_root(1, PES_PAUSE_INPUT_BACK);
 assert(footer_calls == 1 && saved == 3 && !published && !live_gameplan_window);
 assert(!exhibition_gameplan_custom_active);
 memset(exhibition_gameplan_sides, 0, sizeof(exhibition_gameplan_sides));
 live_gameplan_window = (void *)1; single_player = 1;
 exhibition_gameplan_sides[0].root_focus = 2;
 prematch_gameplan_process_root(0, PES_PAUSE_INPUT_DECIDE);
 assert(!auto_calls && exhibition_gameplan_sides[0].page == 0);
 prematch_gameplan_process_root(0, PES_PAUSE_INPUT_BACK);
 assert(footer_calls == 2 && saved == 1 && !published);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='pes-live-ready-') as folder:
            cfile = Path(folder) / 'test.c'
            exe = Path(folder) / 'test.exe'
            cfile.write_text(source)
            subprocess.run([compiler, '-std=c11', str(cfile), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()

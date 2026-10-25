"""Run the real result APIs while a Cup ceremony owns a live result window."""
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


def source(hooks):
    def actual(name):
        start = re.search(r'(?m)^(?:static )?(?:uint32_t|int|void) ' + name + r'\([^;{]*\)\s*\{', hooks)
        assert start, name
        return function(hooks[start.start():], name)
    prelude = r'''
#include <stdint.h>
#include <assert.h>
#include <stddef.h>
#define debugPrintf(...) ((void)0)
enum { MATCH_RESULT_SURFACE_NONE, MATCH_RESULT_SURFACE_FULL_MENU=4,
       MATCH_RESULT_PAGE_FINAL, PES_VIRTUAL_CURSOR_FULL_TIME };
static int ceremony, native_updates, prepares, cursors, inputs, post_inputs;
static int live_gameplan_open_requested, live_gameplan_window;
static uint32_t exhibition_gameplan_custom_active, match_postmatch_custom_active;
static uint32_t match_result_skin_ready=1, match_result_surface=4;
static uint32_t match_result_exit_requested, match_result_page, match_result_input_action;
static uint64_t match_result_seen_tick=999, pause_top_menu_transition_tick;
static uint64_t match_result_action_tick, match_result_cover_tick=999;
static void *match_result_window, *match_postmatch_window;
static struct { uint32_t active, focus; } match_result_top_menu_confirm={1,0};
static int fixdemo_trophy_ui_active(void) { return ceremony; }
static uint64_t armGetSystemTick(void) { return 1000; }
static uint64_t armTicksToNs(uint64_t t) { return t*1000000; }
static int match_result_handoff_active(void) { return 0; }
static int pes_controller_custom_postmatch_active(void) { return match_postmatch_custom_active; }
static uint32_t match_result_current_phase(void) { return 10; }
static void native_update(void *p) { assert(p); ++native_updates; }
static void (*match_result_update_original)(void *)=native_update;
static void match_result_set_surface(uint32_t s) { match_result_surface=s; }
static void match_result_prepare_skin(void *p) { assert(p); ++prepares; }
static void match_result_ceremony_hold(void *p) { assert(p); match_result_input_action=0; }
static void pes_virtual_cursor_activate(int c, int x, int y) { (void)c; (void)x; (void)y; ++cursors; }
static void match_result_process_controller_input(void *p) { assert(p); ++inputs; }
static void match_postmatch_process_input(void *p) { assert(p); ++post_inputs; }
'''
    return prelude + '\n'.join(actual(n) for n in (
        'pes_controller_result_top_menu_confirm_active',
        'pes_controller_match_result_skin', 'pes_controller_match_result_transition',
        'pes_match_result_update')) + r'''
int main(void) {
  void *window=(void *)(uintptr_t)0x1234;
  /* A native result window and heartbeat already exist; loading and playback
   * must both suppress custom overview, spinner, modal, cursor and actions. */
  for (ceremony=1; ceremony<=2; ++ceremony) {
    match_result_input_action=3;
    assert(!pes_controller_match_result_skin());
    assert(!pes_controller_match_result_transition());
    assert(!pes_controller_result_top_menu_confirm_active());
    pes_match_result_update(window);
    assert(!prepares && !cursors && !inputs && !post_inputs);
    assert(!match_result_input_action);
  }
  assert(native_updates==2); /* Loading/native lifecycle continues. */
  ceremony=0; /* Native end OR bounded failure releases the ordinary overview. */
  assert(pes_controller_match_result_skin()==MATCH_RESULT_SURFACE_FULL_MENU);
  assert(pes_controller_match_result_transition());
  assert(pes_controller_result_top_menu_confirm_active());
  pes_match_result_update(window);
  assert(native_updates==3 && prepares==1 && cursors==1 && inputs==1);
  assert(match_result_window==window);
  return 0;
}
'''


def test_live_result_window_waits_for_ceremony(tmp_path):
    cc = shutil.which('gcc') or shutil.which('clang')
    if not cc:
        pytest.skip('host C compiler required')
    hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
    c = tmp_path / 'overview.c'
    c.write_text(source(hooks))
    exe = tmp_path / 'overview.exe'
    built = subprocess.run([cc, '-std=c11', str(c), '-o', str(exe)],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=10)

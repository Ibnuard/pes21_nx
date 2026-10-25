"""Exercise native result-node hiding while a Cup ceremony owns the frame."""
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


def harness(hooks):
    def actual(name):
        start = re.search(r'(?m)^(?:static )?(?:uint32_t|uintptr_t|int|void) '
                          + name + r'\([^;{]*\)\s*\{', hooks)
        assert start, name
        return function(hooks[start.start():], name)

    return r'''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <assert.h>
#define debugPrintf(...) ((void)0)
enum { PES_VIRTUAL_CURSOR_NONE, PES_VIRTUAL_CURSOR_HALF_TIME,
       PES_VIRTUAL_CURSOR_HALF_PREVIEW, PES_VIRTUAL_CURSOR_FULL_TIME,
       PES_VIRTUAL_CURSOR_GAMEPLAN };
enum { MATCH_RESULT_SURFACE_NONE, MATCH_RESULT_SURFACE_HALF_STATS,
       MATCH_RESULT_SURFACE_FULL_STATS, MATCH_RESULT_SURFACE_HALF_MENU,
       MATCH_RESULT_SURFACE_FULL_MENU };
enum { MATCH_RESULT_PAGE_STATS, MATCH_RESULT_PAGE_INTERVAL,
       MATCH_RESULT_PAGE_FINAL };
typedef struct { float alpha; } Node;
typedef struct { Node *surface, *root; int initialized; } Window;
static uint32_t ceremony, virtual_cursor_context, match_result_input_action;
static uint32_t match_result_skin_ready, match_result_exit_requested;
static uint32_t match_result_page, match_result_half_menu_seen;
static uint32_t match_result_final_seen, match_postmatch_custom_active;
static uint32_t live_gameplan_returning_to_pause, match_result_surface;
static uint64_t pause_editor_transition_tick, match_result_cover_tick;
static uint64_t match_result_action_tick, match_result_seen_tick;
static void *live_gameplan_window, *match_result_window, *match_postmatch_window;
static void **match_listener_instance;
static uintptr_t match_result_half_update_resume=0x777;
static uintptr_t match_result_full_resume=0x888, match_result_half_resume=0x999;
static unsigned native_calls, getter_calls, alpha_writes, cursor_calls;
static unsigned input_calls, post_input_calls;
static int fixdemo_trophy_ui_active(void) { return ceremony!=0; }
static uint64_t armGetSystemTick(void) { return 1000; }
static int match_result_handoff_active(void) { return 0; }
static void match_result_clear_handoff(void) {}
static int pes_controller_custom_postmatch_active(void) {
  return match_postmatch_custom_active;
}
static uint32_t match_result_interval_surface(uint32_t a,uint32_t b) {
  (void)a; return b;
}
static void match_result_set_surface(uint32_t s) { match_result_surface=s; }
static void native_update(void *p) { assert(p); ++native_calls; }
static void (*match_result_update_original)(void *)=native_update;
static void set_alpha(void *p,float alpha) {
  assert(p && alpha==0.0f); ((Node *)p)->alpha=alpha; ++alpha_writes;
}
static void (*match_node_set_alpha)(void *,float)=set_alpha;
static void *get_surface(void *p) {
  Window *w=p; assert(w && w->initialized); ++getter_calls; return w->surface;
}
static void *get_root(void *p) {
  Window *w=p; assert(w && w->initialized); ++getter_calls; return w->root;
}
static void *(*exhibition_window_get_window)(void *)=get_surface;
static void *(*match_setplay_get_root)(void *)=get_root;
static void pes_virtual_cursor_activate(uint32_t c,uint32_t x,uint32_t y) {
  (void)x; (void)y; virtual_cursor_context=c; ++cursor_calls;
}
static void match_result_process_controller_input(void *p) {
  assert(p); ++input_calls;
}
static void match_postmatch_process_input(void *p) {
  assert(p); ++post_input_calls;
}
''' + '\n'.join(actual(name) for name in (
        'match_result_hide_native', 'match_result_ceremony_hold',
        'match_result_prepare_skin', 'pes_match_team_stats_update_entry',
        'pes_match_result_update', 'pes_match_result_half_update_entry',
        'pes_match_result_full_entry', 'pes_match_result_half_entry')) + r'''
static void update(unsigned page,Window *window) {
  if (page==0) pes_match_team_stats_update_entry(window);
  else if (page==1) pes_match_result_update(window);
  else assert(pes_match_result_half_update_entry(window)==0x777);
}
int main(void) {
  Node a={1},b={1},c={1},d={1}; Window window={&a,&b,1};
  /* Every live page hides both the footer/window and separate stats root.
   * It must not publish a custom skin, cursor or pending result action. */
  for (ceremony=1;ceremony<=2;++ceremony) {
    for (unsigned page=0;page<3;++page) {
      window.surface->alpha=window.root->alpha=1.0f;
      match_result_skin_ready=0; match_result_cover_tick=17;
      match_result_action_tick=18; match_result_seen_tick=19;
      match_result_input_action=3; virtual_cursor_context=PES_VIRTUAL_CURSOR_FULL_TIME;
      update(page,&window);
      assert(window.surface->alpha==0.0f && window.root->alpha==0.0f);
      assert(!match_result_skin_ready && !match_result_input_action);
      assert(virtual_cursor_context==PES_VIRTUAL_CURSOR_NONE);
      assert(match_result_cover_tick==17 && match_result_action_tick==18);
      assert(match_result_seen_tick==19);
      assert(!cursor_calls && !input_calls && !post_input_calls);
      /* A rebuilt layout must resolve its new nodes, never cached pointers. */
      window.surface=page&1?&a:&c; window.root=page&1?&b:&d;
    }
  }
  assert(native_calls==2 && alpha_writes==12 && getter_calls==12);
  /* Constructors precede layout initialization: hold input without touching
   * their uninitialized native node accessors. Native execution still resumes. */
  ceremony=1; window.initialized=0; unsigned getters=getter_calls;
  virtual_cursor_context=PES_VIRTUAL_CURSOR_HALF_PREVIEW;
  assert(pes_match_result_full_entry(&window,"result",0)==0x888);
  assert(pes_match_result_half_entry(&window,"result",0)==0x999);
  assert(getter_calls==getters && !cursor_calls);
  assert(virtual_cursor_context==PES_VIRTUAL_CURSOR_NONE);
  virtual_cursor_context=PES_VIRTUAL_CURSOR_GAMEPLAN;
  match_result_ceremony_hold(NULL);
  assert(virtual_cursor_context==PES_VIRTUAL_CURSOR_GAMEPLAN);
  /* Optional bindings or a not-yet-published node are safe and never mark
   * the skin ready; the next live update can resolve the nodes again. */
  window.initialized=1; window.surface=window.root=NULL;
  match_result_skin_ready=0; match_result_ceremony_hold(&window);
  assert(!match_result_skin_ready);
  match_node_set_alpha=NULL; getters=getter_calls;
  match_result_ceremony_hold(&window); assert(getter_calls==getters);
  match_node_set_alpha=set_alpha; window.surface=&a; window.root=&b;
  /* Native end or bounded failure releases the existing result flow. */
  ceremony=0;
  for (unsigned page=0;page<3;++page) {
    match_result_skin_ready=0; update(page,&window);
    assert(match_result_skin_ready && match_result_window==&window);
  }
  assert(native_calls==3 && cursor_calls==3 && input_calls==3);
  assert(!post_input_calls);
  return 0;
}
'''


def test_native_result_nodes_and_input_wait_for_ceremony(tmp_path):
    cc = shutil.which('gcc') or shutil.which('clang')
    if not cc:
        pytest.skip('host C compiler required')
    hooks = (ROOT / 'source/ue4_hooks.c').read_text(encoding='utf-8')
    source = tmp_path / 'native-result.c'
    source.write_text(harness(hooks), encoding='utf-8')
    exe = tmp_path / 'native-result.exe'
    built = subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                            str(source), '-o', str(exe)],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr

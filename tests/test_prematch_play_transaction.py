"""Execute the production hub Play transaction and fresh-editor ownership."""
from pathlib import Path
import shutil

import pytest

from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]


def run(source):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler required")
    build_and_run(compiler, source)


def test_direct_hub_play_prepares_once_and_resumes_frozen_audio_transaction():
    hooks = (ROOT / "source/ue4_hooks.c").read_text()
    handler = function(hooks, "main_menu_2p_prematch_hub_process_pending")
    # Earlier branches select pages; this is the actual Kick Off branch.
    tail = handler[handler.index("  if (action != 3)"):]
    run(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
enum {MAIN_MENU_2P_TRANSITION_VS=2,EXHIBITION_STRATEGY_START=1,PES_VIRTUAL_CURSOR_NONE=0};
static uint32_t exhibition_match_settings_armed,exhibition_cpu_level_value;
static uint32_t kickoff_loading_armed,main_menu_2p_transition_active,main_menu_2p_transition_kind;
static uint32_t main_menu_2p_prematch_hub_active=1,exhibition_searching_active=1;
static uint32_t exhibition_team_select_active,exhibition_strategy_action,exhibition_strategy_pending;
static uint32_t native_gamepad_lab_autostart,main_menu_2p_prematch_return_pending,virtual_cursor_context;
static char listener_bytes[0x200];
static void *listener_value=listener_bytes,**exhibition_flow_listener_instance=&listener_value;
static unsigned prepared,snapshots,saved,gate_calls,dispatched,closed,notes;
static int prepare_ok=1,snapshot_ok=1,gate_ready,resuming;
static int ml_frontend_plan_editor(void){return 0;}
static int exhibition_gameplan_prepare_matchplan(void){prepared++;return prepare_ok;}
static int exhibition_capture_pre_strategy_squad_snapshot(void){assert(prepared);snapshots++;return snapshot_ok;}
static int exhibition_rebase_prepared_matchplan(void){assert(snapshots);saved++;return 1;}
static void main_menu_2p_native_uniform_close(void){closed++;}
static void exhibition_apply_cpu_level(uint32_t value,void *p){(void)value;assert(!p);}
static void exhibition_apply_match_settings(void *p){assert(!p);}
static void exhibition_apply_selected_uniforms(void *p){assert(!p);}
static int player_commentary_roster_resume_pending(void){return resuming;}
static int player_commentary_roster_play_gate(void){assert(saved);gate_calls++;return gate_ready;}
static void scene_runtime_note(const char *a,const char *b){assert(a && b);notes++;}
static void direct(void *p,const char *name){assert(p==listener_bytes+0x118);assert(!strcmp(name,"MyClub/Match/MenuMatchMenu"));dispatched++;}
static void (*exhibition_flow_direct_set)(void *,const char *)=direct;
#define debugPrintf(...) ((void)0)
static void play(void){const uint32_t action=3;const int game_plan=0;
''' + tail + r'''
int main(void){
  prepare_ok=0;play();assert(prepared==1 && !snapshots && !saved && !gate_calls && !dispatched);
  assert(main_menu_2p_prematch_hub_active && notes==1);
  prepare_ok=1;snapshot_ok=0;play();assert(prepared==2 && snapshots==1 && !saved && !gate_calls);
  assert(main_menu_2p_prematch_hub_active && !dispatched && notes==2);
  snapshot_ok=1;play();assert(prepared==3 && snapshots==2 && saved==1 && gate_calls==1);
  assert(main_menu_2p_prematch_hub_active && !dispatched);
  resuming=1;gate_ready=1;play();
  assert(prepared==3 && snapshots==2 && saved==1 && gate_calls==2 && dispatched==1);
  assert(!main_menu_2p_prematch_hub_active && exhibition_strategy_pending && native_gamepad_lab_autostart);
}
''')


def test_new_prematch_clears_only_prior_live_editor_state():
    hooks = (ROOT / "source/ue4_hooks.c").read_text()
    run('#include "' + str(ROOT / 'source/result_exit_confirm.h').replace('\\','/') + '"\n' + r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
enum {PES_VIRTUAL_CURSOR_NONE=0,MAIN_MENU_2P_PREMATCH_BOOT_HUB=1};
static uint32_t live_gameplan_open_requested=1,match_gameplan_pause_route=1;
static uint32_t live_gameplan_returning_to_pause=1,virtual_cursor_context=8;
static uint64_t match_pause_seen_tick=100,match_gameplan_seen_tick=200;
static unsigned char live_substitution_locked[2][40];
static uint32_t main_menu_2p_prematch_hub_active,main_menu_2p_prematch_bootstrap_mode;
static unsigned resets;
static ResultExitConfirm match_result_top_menu_confirm;
static void exhibition_gameplan_reset(void){resets++;}
''' + function(hooks, "exhibition_gameplan_begin_prematch")
        + function(hooks, "exhibition_prematch_editor_owned") + r'''
int main(void){
 memset(live_substitution_locked,1,sizeof(live_substitution_locked));
 /* An in-match reset retains consumed substitution locks. */
 exhibition_gameplan_reset();assert(live_substitution_locked[1][39]);
 exhibition_gameplan_begin_prematch();assert(resets==2);
 assert(!live_gameplan_open_requested && !match_gameplan_pause_route);
 assert(!match_pause_seen_tick && !match_gameplan_seen_tick && !live_gameplan_returning_to_pause);
 assert(virtual_cursor_context==PES_VIRTUAL_CURSOR_NONE);
 for(unsigned s=0;s<2;s++)for(unsigned i=0;i<40;i++)assert(!live_substitution_locked[s][i]);
 assert(!exhibition_prematch_editor_owned());
 main_menu_2p_prematch_hub_active=1;assert(exhibition_prematch_editor_owned());
 main_menu_2p_prematch_hub_active=0;main_menu_2p_prematch_bootstrap_mode=1;
 assert(exhibition_prematch_editor_owned());
 main_menu_2p_prematch_bootstrap_mode=0;assert(!exhibition_prematch_editor_owned());
}
''')


def test_closing_native_editor_cannot_retake_prematch_owner():
    hooks = (ROOT / "source/ue4_hooks.c").read_text()
    native = function(hooks, "pes_match_squad_edit_update_entry")
    # Execute the entry admission before native/live side effects.
    admission = native[:native.index("  // WindowMobile")]
    run(r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
static int owned;
static int exhibition_prematch_editor_owned(void){return owned;}
static unsigned admitted;
''' + admission + "  admitted++;\n}\n" + r'''
int main(void){
 owned=1;pes_match_squad_edit_update_entry((void *)123,0);assert(!admitted);
 owned=0;pes_match_squad_edit_update_entry(NULL,0);assert(!admitted);
 pes_match_squad_edit_update_entry((void *)123,0);assert(admitted==1);
}
''')

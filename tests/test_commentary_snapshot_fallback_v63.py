"""A rejected optional roster must not hold a valid Exhibition in its hub."""
from pathlib import Path
import pytest
from test_player_commentary_roster_runtime import compile_run
from test_gameplan_editor import function

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('fault',range(8))
def test_only_optional_policy_failure_can_use_baseline_without_new_names(tmp_path,fault):
    compile_run(tmp_path,r'''
int main(void){
 environment();install();uint32_t flags;
 switch(FAULT){
  case 0:flags=10u<<9;memcpy(teams[0]+0x3a6u,&flags,4);break;
  case 1:flags=41u<<9;memcpy(teams[1]+0x3a6u,&flags,4);break;
  case 2:bad_record=1;break;
  case 3:bad_team=1;break;
  case 4:missing_match=1;break;
  case 5:teams[1][0x110u]^=1;break;
  case 6:match_tmpdb_match_get_player=NULL;break;
  case 7:scope_bad=1;break;
 }
 PcSelection snapshot;assert(!player_commentary_capture_selection(&snapshot));
 const unsigned before=notes;
 if(FAULT!=7){
  assert(!player_commentary_roster_play_gate());
  assert(!player_commentary_snapshot_fallback && !native_requests);
  assert(!player_commentary_reload.prepared_live && main_menu_2p_prematch_hub_active);
  cleanup();return 0;
 }
 assert(player_commentary_roster_play_gate());
 assert(player_commentary_snapshot_fallback==1 && notes==before+1);
 assert(!native_requests && !player_commentary_reload.prepared_live);
 assert(!player_commentary_active_generation && player_commentary_active_mount==-1);
 assert(main_menu_2p_prematch_hub_active && !main_menu_2p_transition_active);
 const unsigned logged=notes;
 assert(player_commentary_roster_play_gate() && notes==logged); /* no log/request loop */
 uint32_t side=0;uint64_t carrier=((uint64_t)100000u<<32)|0xab0000u;
 assert(!pes_sound_player_name_label(NULL,&side,&carrier,0,0)); /* unmounted new owner */
 carrier=((uint64_t)100039u<<32)|0xab0027u;
 const int calls=typed_calls;
 const char *native=pes_sound_player_name_label(NULL,&side,&carrier,0,0);
 if(FAULT==7){assert(!native && typed_calls==calls);}
 else {assert(native && typed_calls==calls+1);}
 side=2;assert(!pes_sound_player_name_label(NULL,&side,&carrier,0,0));
 cleanup();return 0;
}
'''.replace('FAULT',str(fault)))


def test_fallback_waits_for_prior_native_request_to_drain_and_cancels_on_new_fixture(tmp_path):
    compile_run(tmp_path,r'''
int main(void){
 environment();install();assert(!player_commentary_roster_play_gate());
 assert(native_requests==1 && pc_reload_phase(&player_commentary_reload)==PC_RELOAD_WAITING);
 main_menu_2p_prematch_hub_active=1;scope_bad=1;
 assert(!player_commentary_roster_play_gate());
 assert(player_commentary_snapshot_fallback==2);
 assert(pc_reload_phase(&player_commentary_reload)==PC_RELOAD_DRAINING);
 player_commentary_roster_tick();
 assert(!main_menu_2p_prematch_hub_input_pending && !player_commentary_roster_play_gate());
 native_busy_value=0;now_ms++;player_commentary_roster_tick();
 assert(player_commentary_snapshot_fallback==1 && main_menu_2p_prematch_hub_input_pending==3);
 assert(player_commentary_roster_play_gate() && native_requests==1);
 assert(!player_commentary_reload.borrowers && !player_commentary_reload.prepared_live);
 player_commentary_roster_invalidate();scope_bad=0;main_menu_2p_prematch_hub_input_pending=0;
 assert(!player_commentary_snapshot_fallback && !player_commentary_snapshot_identity);
 assert(!player_commentary_roster_play_gate() && native_requests==2);
 cleanup();return 0;
}
''')


def test_snapshot_fallback_does_not_reopen_selector_after_cancel(tmp_path):
    compile_run(tmp_path,r'''
int main(void){
 environment();install();assert(!player_commentary_roster_play_gate());
 main_menu_2p_prematch_hub_active=1;scope_bad=1;
 assert(!player_commentary_roster_play_gate() && player_commentary_snapshot_fallback==2);
 main_menu_2p_prematch_hub_active=0;main_menu_2p_team_selector_active=1;
 player_commentary_roster_invalidate();native_busy_value=0;now_ms++;player_commentary_roster_tick();
 assert(!player_commentary_snapshot_fallback && !main_menu_2p_prematch_hub_input_pending);
 assert(!main_menu_2p_prematch_hub_active && main_menu_2p_team_selector_active);
 cleanup();return 0;
}
''')


def test_real_hub_play_continues_strategy_after_rejected_optional_snapshot(tmp_path):
    handler=function((ROOT/'source/ue4_hooks.c').read_text(),'main_menu_2p_prematch_hub_process_pending')
    tail=handler[handler.index('  if (action != 3)'):]
    compile_run(tmp_path,r'''
static uint32_t exhibition_match_settings_armed,exhibition_cpu_level_value;
static uint32_t kickoff_loading_armed,exhibition_searching_active=1,exhibition_team_select_active;
static uint32_t exhibition_strategy_action,exhibition_strategy_pending,native_gamepad_lab_autostart;
static uint32_t main_menu_2p_prematch_return_pending,virtual_cursor_context;
enum {EXHIBITION_STRATEGY_START=1,PES_VIRTUAL_CURSOR_NONE=0};
static unsigned prepared,snapshots,saved,dispatched;
static unsigned char listener[0x200];static void *listener_value=listener;
static void **exhibition_flow_listener_instance=&listener_value;
static int ml_frontend_plan_editor(void){return 0;}
static int exhibition_gameplan_prepare_matchplan(void){prepared++;return 1;}
static int exhibition_capture_pre_strategy_squad_snapshot(void){snapshots++;return 1;}
static int exhibition_rebase_prepared_matchplan(void){saved++;return 1;}
static void main_menu_2p_native_uniform_close(void){}
static void exhibition_apply_cpu_level(uint32_t v,void *p){(void)v;(void)p;}
static void exhibition_apply_match_settings(void *p){(void)p;}
static void exhibition_apply_selected_uniforms(void *p){(void)p;}
static void direct(void *p,const char *flow){assert(p==listener+0x118);assert(!strcmp(flow,"MyClub/Match/MenuMatchMenu"));dispatched++;}
static void (*exhibition_flow_direct_set)(void *,const char *)=direct;
static void play(void){const uint32_t action=3;const int game_plan=0;
''' + tail + r'''
int main(void){
 environment();install();scope_bad=1;play();
 assert(dispatched==1 && prepared==1 && snapshots==1 && saved==1);
 assert(exhibition_strategy_pending && native_gamepad_lab_autostart);
 assert(!main_menu_2p_prematch_hub_active && main_menu_2p_transition_kind==MAIN_MENU_2P_TRANSITION_VS);
 assert(!native_requests && player_commentary_snapshot_fallback==1);
 cleanup();return 0;
}
''')

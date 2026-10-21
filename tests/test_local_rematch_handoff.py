"""Exercise frontend ownership and reused native TutorialMatch across matches."""
from pathlib import Path
import shutil
import unittest
from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT/'source/ue4_hooks.c').read_text()


class LocalRematchHandoffTests(unittest.TestCase):
    def replay(self, text):
        compiler = shutil.which('gcc')
        if not compiler:
            self.skipTest('host C compiler required')
        build_and_run(compiler, '#include <assert.h>\n#include <stdint.h>\n#include <string.h>\n' + text)

    def test_actual_tutorial_entry_reinitializes_parked_object_only_when_requested(self):
        self.replay(r'''
#define debugPrintf(...) ((void)0)
#define scene_runtime_note(...) ((void)0)
enum { MAIN_MENU_2P_PREMATCH_BOOT_NONE,MAIN_MENU_2P_PREMATCH_BOOT_HUB };
enum { MAIN_MENU_2P_TRANSITION_NONE,MAIN_MENU_2P_PREMATCH_PAGE_MAIN=0 };
enum { EXHIBITION_STRATEGY_NONE,EXHIBITION_STRATEGY_START };
#define EXHIBITION_INITIAL_REFRESH_TICKS 8
static uint32_t exhibition_return_to_selector,main_menu_2p_prematch_return_pending;
static uint32_t exhibition_requested,exhibition_searching_active,exhibition_search_refresh_pending;
static uint32_t exhibition_search_initial_refresh_ticks,exhibition_team_select_active;
static uint32_t main_menu_2p_selector_postbootstrap_host,main_menu_2p_prematch_hub_active;
static uint32_t main_menu_2p_transition_active,main_menu_2p_transition_kind;
static uint32_t main_menu_2p_prematch_hub_page,main_menu_2p_prematch_hub_input_pending;
static uint32_t main_menu_2p_prematch_hub_input_armed[2],main_menu_2p_prematch_hub_focus;
static uint32_t main_menu_2p_prematch_hub_page_focus,main_menu_controller_active;
static uint32_t main_menu_2p_prematch_bootstrap_mode,exhibition_session_active=1;
static uint32_t exhibition_home_team_id=108,exhibition_away_team_id=100;
static uint32_t exhibition_select_side,exhibition_strategy_action,exhibition_plan_ready;
static uint32_t exhibition_strategy_pending;
static uintptr_t exhibition_tutorial_main_resume=0x123;
static unsigned char listener_storage[512];
static void *listener=listener_storage;
static void **exhibition_flow_listener_instance=&listener;
static unsigned native_lab=1,refreshed,dispatches;
static char dispatched[128];
static void direct(void *p,const char *flow) {
  assert(p==listener_storage+0x118);dispatches++;strcpy(dispatched,flow);
}
static void (*exhibition_flow_direct_set)(void *,const char *)=direct;
static int pes_controller_native_pad_lab_active(void) {return native_lab;}
static void exhibition_prepare_search_parameters(void) {}
static void main_menu_2p_prematch_hub_cache_lineups(void) {}
static void exhibition_gameplan_refresh_uniform_choices(void) {}
static void exhibition_refresh_selected_tmpdb(void) {refreshed++;}
static void *exhibition_status_get_instance;
static void (*exhibition_status_set_game_mode)(void *,unsigned);
''' .replace('static void *exhibition_status_get_instance;',
              'static void *(*exhibition_status_get_instance)(void);')
            + function(SOURCE,'pes_exhibition_tutorial_main_entry') + r'''
int main(void) {
  _Alignas(8) unsigned char flow[600]={0};
  uint32_t *state=(uint32_t *)(flow+540);
  /* Native startup/unrequested objects must not be rewritten. */
  for(unsigned i=0;i<12;i++) {
    *state=i;assert(pes_exhibition_tutorial_main_entry(flow)==0x123);
    assert(*state==i && !dispatches);
  }
  /* Native flow objects can be cached. Reuse the same parked instance through
   * three complete bootstrap lifecycles instead of allocating fresh zeroes. */
  *state=9;
  for(unsigned match=1;match<=3;match++) {
    exhibition_requested=1;main_menu_2p_prematch_bootstrap_mode=MAIN_MENU_2P_PREMATCH_BOOT_HUB;
    assert(pes_exhibition_tutorial_main_entry(flow)==0x123 && *state==3);
    *state=4;pes_exhibition_tutorial_main_entry(flow);assert(*state==4);
    *state=7;listener=0;pes_exhibition_tutorial_main_entry(flow);
    assert(*state==7 && exhibition_requested && dispatches==match-1);
    listener=listener_storage;pes_exhibition_tutorial_main_entry(flow);
    assert(*state==9 && !exhibition_requested && dispatches==match);
    assert(main_menu_2p_prematch_hub_active && !main_menu_2p_transition_active);
    assert(refreshed==match && exhibition_home_team_id==108 && exhibition_away_team_id==100);
    assert(!strcmp(dispatched,"MyClub/Match/Training/MenuMatchSearching"));
    pes_exhibition_tutorial_main_entry(flow);assert(dispatches==match);
  }
}
''')

    def test_ready_frontend_retires_old_page_and_dispatches_once(self):
        self.replay(r'''
#define scene_runtime_note(...) ((void)0)
enum {MATCH_RESULT_SURFACE_NONE=0,MATCH_RESULT_PAGE_NONE=0};
enum {LOCAL_REMATCH_PLAY=1,LOCAL_REMATCH_SELECT=2};
enum {COMPETITION_ACTION_EXHIBITION=10,COMPETITION_ACTION_TWO_PLAYER=20};
enum {MAIN_MENU_2P_PREMATCH_BOOT_NONE=0,MAIN_MENU_2P_PREMATCH_BOOT_HUB=1};
static uint32_t local_rematch_request,local_rematch_menu_ready,local_rematch_booting;
static uint32_t local_rematch_wait_noted;
static uint32_t local_rematch_handoff_cover;
static uint32_t local_rematch_transition_abi_ok=1;
static uint32_t local_rematch_valid=1,local_rematch_two_player,allowed=1;
static struct {unsigned team_id;} local_rematch_plan[2]={{108},{100}};
static uint32_t exhibition_requested,exhibition_searching_active,exhibition_team_select_active;
static uint32_t exhibition_search_refresh_pending,exhibition_return_to_selector,exhibition_strategy_pending;
static void *exhibition_search_window,*live_gameplan_window,*match_result_window;
static uint32_t live_gameplan_open_requested,live_gameplan_returning_to_pause;
static uint32_t match_result_surface,match_result_page,match_result_skin_ready,match_result_exit_requested;
static uint64_t match_result_handoff_tick,match_result_action_tick,match_result_cover_tick;
static uint64_t pause_top_menu_transition_tick,pause_editor_transition_tick;
static uint32_t kickoff_loading_armed,main_menu_controller_active;
static uint32_t exhibition_home_team_id,exhibition_away_team_id,exhibition_settings_hub_mode;
static uint32_t main_menu_2p_prematch_bootstrap_mode;
static unsigned char listener_storage[0x210];
static void *listener=listener_storage;
static void **exhibition_flow_listener_instance=&listener;
static void direct(void *p,const char *name) {(void)p;(void)name;}
static void (*exhibition_flow_direct_set)(void *,const char *)=direct;
static unsigned starts,selected,start_ok=1;
static int local_rematch_allowed(void) {return allowed && local_rematch_valid;}
static void main_menu_activate_match_mode(unsigned mode) {selected=mode;}
static int start(void) {
  assert(!match_result_surface && !match_result_skin_ready && !match_result_exit_requested);
  assert(!exhibition_requested && !exhibition_searching_active && !exhibition_search_window);
  starts++;return start_ok;
}
static int main_menu_start_two_player_match(void) {return start();}
static int main_menu_start_exhibition_match(void) {return start();}
''' + function(SOURCE,'local_rematch_finish_exit')
            + function(SOURCE,'local_rematch_flow_idle')
            + function(SOURCE,'local_rematch_process_pending') + r'''
int main(void) {
  local_rematch_request=LOCAL_REMATCH_PLAY;
  assert(!local_rematch_process_pending() && !starts && local_rematch_request);
  exhibition_requested=exhibition_searching_active=exhibition_strategy_pending=1;
  match_result_surface=match_result_skin_ready=match_result_exit_requested=1;
  exhibition_search_window=(void *)1;match_result_window=(void *)2;
  local_rematch_finish_exit();
  assert(local_rematch_menu_ready && !match_result_window && !exhibition_strategy_pending);
  /* Neither an old frame nor a second Pad may consume it before new frontend. */
  assert(!local_rematch_process_pending() && !starts && local_rematch_request);
  main_menu_controller_active=1;
  /* SetupWindow has returned but native fade completion still owns/clears the
   * queue. V57 would consume and append here; native completion discarded it.
   * Keep exactly one request through every non-idle phase without a timer. */
  uint32_t *step=(uint32_t *)(listener_storage+0x118+8);
  uintptr_t *begin=(uintptr_t *)(listener_storage+0x118+0x40);
  uintptr_t *end=(uintptr_t *)(listener_storage+0x118+0x48);
  *step=5;*begin=0x1000;*end=0x1088;
  for(unsigned i=0;i<10;i++) {
    assert(local_rematch_process_pending());
    assert(local_rematch_request && local_rematch_menu_ready && !starts);
  }
  assert(local_rematch_wait_noted);
  /* Native completion destroys its entire old vector. Our request remains
   * wrapper-owned rather than being a second element in that destroyed queue. */
  *end=*begin;
  for(unsigned phase=1;phase<=6;phase++) {
    *step=phase;
    assert(local_rematch_process_pending() && !starts && local_rematch_request);
  }
  *step=0;
  *end=*begin+0x88;
  assert(local_rematch_process_pending() && !starts && local_rematch_request);
  *end=*begin;
  listener=0;
  assert(local_rematch_process_pending() && !starts && local_rematch_request);
  listener=listener_storage;
  exhibition_flow_direct_set=0;
  assert(local_rematch_process_pending() && !starts && local_rematch_request);
  exhibition_flow_direct_set=direct;
  assert(local_rematch_process_pending() && starts==1 && local_rematch_booting);
  assert(!local_rematch_request && !local_rematch_menu_ready);
  assert(!local_rematch_wait_noted);
  assert(exhibition_home_team_id==108 && exhibition_away_team_id==100);
  assert(!local_rematch_process_pending() && starts==1);
  for(unsigned two=0;two<2;two++) {
    local_rematch_valid=1;local_rematch_two_player=two;
    local_rematch_request=LOCAL_REMATCH_SELECT;local_rematch_finish_exit();
    assert(local_rematch_process_pending());
    assert(selected==(two?COMPETITION_ACTION_TWO_PLAYER:COMPETITION_ACTION_EXHIBITION));
    assert(!local_rematch_valid && starts==1);
  }
  local_rematch_valid=1;local_rematch_request=LOCAL_REMATCH_PLAY;
  local_rematch_finish_exit();start_ok=0;
  assert(local_rematch_process_pending() && !local_rematch_booting);
  assert(main_menu_2p_prematch_bootstrap_mode==MAIN_MENU_2P_PREMATCH_BOOT_NONE);
  assert(main_menu_controller_active && !local_rematch_request);
}
''')

    def test_native_admission_uses_step_and_empty_queue_without_writing_either(self):
        self.replay(r'''
static _Alignas(8) unsigned char data[0x210];
static uint32_t local_rematch_transition_abi_ok=1;
static void *listener=data;
static void **exhibition_flow_listener_instance=&listener;
static void direct(void *p,const char *flow) {(void)p;(void)flow;}
static void (*exhibition_flow_direct_set)(void *,const char *)=direct;
''' + function(SOURCE,'local_rematch_flow_idle') + r'''
int main(void) {
  unsigned char before[sizeof(data)];
  uint32_t *step=(uint32_t *)(data+0x118+8);
  uintptr_t *begin=(uintptr_t *)(data+0x118+0x40);
  uintptr_t *end=(uintptr_t *)(data+0x118+0x48);
  /* Zeroed/unallocated and allocated-empty vectors are both valid idle. */
  for(unsigned allocated=0;allocated<2;allocated++) {
    *begin=*end=allocated?0x1000:0;
    for(unsigned phase=0;phase<8;phase++) {
      *step=phase;memcpy(before,data,sizeof(data));
      assert(local_rematch_flow_idle()==(phase==0));
      assert(!memcmp(before,data,sizeof(data)));
    }
  }
  *step=0;
  const uintptr_t queues[][2]={{0x1000,0x1088},{0x1088,0x1000},{0,0x88}};
  for(unsigned i=0;i<3;i++) {
    *begin=queues[i][0];*end=queues[i][1];
    memcpy(before,data,sizeof(data));
    assert(!local_rematch_flow_idle());assert(!memcmp(before,data,sizeof(data)));
  }
  listener=0;assert(!local_rematch_flow_idle());
  listener=data;exhibition_flow_listener_instance=0;
  assert(!local_rematch_flow_idle());
  exhibition_flow_listener_instance=&listener;
  local_rematch_transition_abi_ok=0;
  *step=0;*begin=*end=0;
  assert(!local_rematch_flow_idle());
}
''')

    def test_owned_native_completion_discards_a_queued_second_transition(self):
        """Replay actual completion instructions, not just our admission bool."""
        fixture=ROOT/'dist/pes21_nx/libUE4.so'
        if not fixture.is_file():
            self.skipTest('compatible ignored PES21 ELF required for native oracle')
        try:
            from elftools.elf.elffile import ELFFile
            from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
        except ImportError:
            self.skipTest('pyelftools and Capstone required for native oracle')
        with fixture.open('rb') as stream:
            elf=ELFFile(stream)
            segments=[part for part in elf.iter_segments()
                      if part['p_type']=='PT_LOAD']
            def read(address,size):
                for part in segments:
                    start=part['p_vaddr']
                    if start<=address and address+size<=start+part['p_filesz']:
                        stream.seek(part['p_offset']+address-start)
                        return stream.read(size)
                self.fail('native oracle address outside compatible ELF')
            decoder=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
            decoder.detail=True
            # Native MAIN_STEP_FLOW_FADEIN_START completion, including its
            # destructor loop and native end-pointer write before fade wait.
            instructions=list(decoder.disasm(read(0x7bb9a7c,60),0x7bb9a7c))
            self.assertEqual(instructions[0].mnemonic,'ldp')
            self.assertEqual(instructions[0].operands[2].mem.disp,0x40)
            self.assertEqual(instructions[4].mnemonic,'sub')
            stride=instructions[4].operands[2].imm
            self.assertEqual(stride,0x88)
            self.assertEqual(instructions[6].mnemonic,'bl')
            self.assertEqual(instructions[8].mnemonic,'b.ne')
            self.assertEqual(instructions[8].operands[0].imm,instructions[4].address)
            self.assertEqual(instructions[10].mnemonic,'str')
            self.assertEqual(instructions[10].operands[1].mem.disp,0x48)
            self.assertEqual(instructions[12].mnemonic,'mov')
            self.assertEqual(instructions[12].operands[1].imm,6)
            # Both old and newly appended entries are destroyed. Only keeping
            # the new request outside this native vector survives completion.
            queue_start=0x1000
            queue_end=queue_start+2*stride
            destroyed=[]
            cursor=queue_end
            while cursor!=queue_start:
                cursor-=stride
                destroyed.append(cursor)
            queue_end=queue_start
            self.assertEqual(destroyed,[queue_start+stride,queue_start])
            self.assertEqual(queue_end,queue_start)

    def test_unavailable_admission_disables_only_new_automatic_result_actions(self):
        body=function(SOURCE,'local_rematch_allowed')
        self.assertIn('local_rematch_transition_abi_ok',body)
        for name in ('main_menu_start_exhibition_match','main_menu_start_two_player_match'):
            self.assertNotIn('local_rematch_transition_abi_ok',function(SOURCE,name))
        self.assertIn('automatic result actions disabled: native transition ABI differs',SOURCE)

    def test_frontend_receipt_does_not_depend_on_optional_stock_root(self):
        body=function(SOURCE,'pes_main_menu_simplify')
        self.assertLess(body.index('local_rematch_finish_exit();'),
                        body.index('void *root = exhibition_window_get_window(window);'))


if __name__=='__main__':
    unittest.main()

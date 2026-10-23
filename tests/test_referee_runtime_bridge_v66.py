"""Exercise native replay callbacks through the real optional actor publisher."""
from pathlib import Path
import re

from test_gameplan_editor import function
from test_referee_kickoff_v62 import compile_run
import test_referee_native_contract as native_contract

ROOT = Path(__file__).resolve().parents[1]


def test_replay_lifecycle_hides_without_draw_and_preserves_goal_kickoff(tmp_path):
    hooks = (ROOT / "source/ue4_hooks.c").read_text()
    fixture = (ROOT / "tests/test_scene_canaries.c").read_text()
    fixture = fixture.replace("int main(void)", "int previous_canary_main(void)")
    fixture = fixture.replace(
        "static int referee_probe_scene_active(void) { return inplay; }",
        "static int referee_probe_scene_active(void) { return bridge_ready ? "
        "referee_probe_scene_bridge() : inplay; }")
    fixture = fixture.replace(
        "static void display(void *p,int visible) {assert(p);",
        "static void display(void *p,int visible) {assert(p);bridge_check_display(visible);")
    scene = function(hooks, "referee_probe_scene_active").replace(
        "referee_probe_scene_active", "referee_probe_scene_bridge")
    publish = function(hooks, "match_replay_publish")
    names = set(re.findall(r"(?:&|\b)(match_\w+)(?=\s*[,\)])", publish))
    names.discard("match_replay_publish")
    globals_ = "\n".join(f"static uint64_t {name};" for name in sorted(names))
    compile_run(tmp_path, r'''
static int bridge_ready;
static int referee_probe_scene_bridge(void);
static void bridge_check_display(int visible);
''' + fixture + r'''
static int expect_fresh_display,previous_publications,previous_updates,expect_negative_x;
static void bridge_check_display(int visible){
  if(!bridge_ready || !visible || !expect_fresh_display)return;
  assert(published>previous_publications && updates>previous_updates);
  if(expect_negative_x)assert(last_position.x<0);
  expect_fresh_display=0;
}
enum {MATCH_PHASE_HALFTIME=2,MATCH_PHASE_EX_TIME=4,MATCH_PHASE_EX_INTERVAL=6};
enum {PES_VIRTUAL_CURSOR_NONE=0,PES_VIRTUAL_CURSOR_SET_PIECE_TAKER=7};
enum {PES_GOAL_DEMO_ACTION_NONE=0,PES_REPLAY_FEEDBACK_NONE=0};
static uint32_t phase=1,pause,cursor,offside_available;
static uint32_t match_result_current_phase(void){return phase;}
static int referee_offside_presentation_active(void){return offside_available;}
static int pes_controller_pause_skin_active(void){return pause;}
static int pes_controller_pause_transition(void){return 0;}
static int pes_controller_match_result_skin(void){return 0;}
static int pes_controller_match_result_transition(void){return 0;}
static int pes_controller_virtual_cursor_context(void){return cursor;}
''' + globals_ + "\n" + function(hooks, "match_native_replay_active_at") + r'''
int pes_controller_replay_active(void){return match_native_replay_active_at(ticks);}
''' + scene + "\n" + publish + r'''
static uint64_t match_goal_demo_own_goal,match_goal_demo_own_goal_tick;
static uint32_t native_replay(void *replay,const void *context){
  assert(replay && context==(void*)7);
  /* The hide must precede native Init/Main, even if no live draw follows. */
  assert(!displayed && referee_recorded_replay_active());return 5;
}
static uint32_t native_replay_end(void *replay,const void *context){
  assert(replay && context==(void*)7);
  assert(!displayed && referee_recorded_replay_active());return 6;
}
static uint32_t (*match_replay_mode_init_original)(void*,const void*)=native_replay;
static uint32_t (*match_replay_mode_main_original)(void*,const void*)=native_replay;
static uint32_t (*match_replay_mode_end_original)(void*,const void*)=native_replay_end;
''' + "\n".join(function(hooks, n) for n in (
        "pes_match_replay_mode_init", "pes_match_replay_mode_main",
        "pes_match_replay_mode_end")) + r'''
static unsigned char kickoff_info[0x1710];
static void put32(void *p,uint32_t n){memcpy(p,&n,4);}
static void native_status(unsigned status,unsigned restart){
  void *p=kickoff_info;memcpy(registry_data+0x4f0,&p,sizeof(p));
  put32(kickoff_info+0x116c,status);put32(kickoff_info+0x1514,restart);
}
static void at_kickoff(void){
  assert(displayed && last_position.x==0 && last_position.z==9.15f);
  assert(referee_kickoff_ready && !referee_probe_reposition);
  assert(!referee_motion.velocity.x && !referee_motion.velocity.z);
}
int main(void){
  assert(!previous_canary_main());
  referee_probe_clear();referee_probe_enabled=1;
  referee_probe_teardown=0;referee_probe_scene_ready=1;
  load_groups_alive=native_loaded=ready=registry_available=1;
  uniform_busy=0;inplay=2;
  *(void**)(registry_data+0x4a10)=NULL;
  size_t size;unsigned char *data=referee_animation_fixture_count(&size,8);
  assert(referee_animation_bind(&referee_animation_bank,data,size));
  referee_animation_bank.whistle_begin=0;referee_animation_bank.whistle_end=.08f;
  referee_kickoff_layout_ok=1;warp_complete=1;
  preload();assert(referee_probe_model && referee_probe_loaded);
  bridge_ready=1;native_status(1,1);ball_data[0]=12;ball_data[2]=0;
  frame();assert(displayed);
  unsigned char players_before[sizeof(human)];memcpy(players_before,human,sizeof(human));
  const int allocated=creations,removed=deleted;
  uint32_t serial=10;
  for(unsigned side=0;side<2;++side)for(unsigned end=0;end<2;++end){
    native_status(1,1);frame();
    unsigned char record[0x60]={0},judge[0x30]={0};
    put32(record,0x24);put32(record+4,++serial);put32(record+0x10,1);
    put32(judge,1);put32(judge+4,side);put32(judge+0x20,3);
    referee_probe_out_of_play(record+0x14,registry_data,judge);
    referee_motion.position=(RefereePoint){end?40:-40,side?20:-20};
    ball_data[0]=end?52:-52;ball_data[2]=side?4:-4;
    frame();assert(displayed);
    void *replay=(void*)(uintptr_t)(0x100u+serial);
    const int poses=published;
    /* Offside guard unavailable is deliberately independent from Replay. */
    offside_available=0;assert(pes_match_replay_mode_init(replay,(void*)7)==5);
    assert(!displayed && published==poses);
    /* Native kickoff acknowledgement can arrive while Replay owns display. */
    put32(flow_object+0xcd4,3);
    assert(referee_probe_position_warp(flow_object,(void*)7));
    const uint32_t applied=referee_kickoff_applied;
    ticks+=3000000000ull;pause=1;cursor=3;
    assert(!pes_controller_replay_active());
    assert(referee_probe_scene_bridge()==4 && !displayed);
    /* No ObjectList::Draw occurred for three seconds. A later draw is still
     * suppressed by lifecycle ownership, rather than the 1s input timeout. */
    frame();assert(!displayed && published==poses && referee_kickoff_pending);
    assert(referee_kickoff_applied==applied);
    assert(pes_match_replay_mode_main(replay,(void*)7)==5);
    referee_probe_replay_end((void*)0x999);assert(referee_recorded_replay_active());
    assert(pes_match_replay_mode_end(replay,(void*)7)==6);
    assert(!referee_recorded_replay_active() && !displayed);
    pause=0;cursor=0;
    /* First read can still be old IN_PLAY as well as the old goal-end ball.
     * The subsequent true stopped kickoff must recover the placement. */
    frame();assert(displayed && !referee_kickoff_ready);
    native_status(3,1);frame();at_kickoff();
    const uint32_t held=referee_kickoff_applied;
    for(unsigned i=0;i<6;++i){frame();at_kickoff();}
    assert(referee_kickoff_applied==held && held==applied+2);
    /* A missing borrowed read retains the hold and does not produce an edge. */
    *(void**)(registry_data+0x4f0)=NULL;frame();at_kickoff();
    native_status(2,1);frame();at_kickoff();
    assert(referee_kickoff_applied==held);
    const uint8_t command=0x4f;const unsigned sounds=sound_calls;
    referee_probe_sound((void*)3,100+serial,&command,0x1d,(void*)4,22);
    native_status(1,1);ball_data[0]=end?-8:8;ball_data[2]=2;
    frame();at_kickoff();assert(sound_calls==sounds+1);
    frame();frame();frame();assert(!referee_kickoff_ready);
    assert(creations==allocated && deleted==removed);
    assert(!memcmp(players_before,human,sizeof(human)));
    /* Ordinary stopped restarts do not hide, rearm or reset placement. */
    for(unsigned restart=2;restart<=7;++restart){
      native_status(3,restart);const uint32_t before=referee_kickoff_applied;
      assert(referee_probe_scene_bridge()==2);frame();assert(displayed);
      assert(!referee_kickoff_ready && !referee_kickoff_pending);
      assert(referee_kickoff_applied==before);
    }
  }
  /* Replay return publishes a fresh transform when no kickoff is pending. */
  native_status(1,0);ball_data[0]=35;ball_data[2]=20;frame();
  pes_match_replay_mode_init((void*)0xabc,(void*)7);
  ball_data[0]=-35;ball_data[2]=-20;
  previous_publications=published;previous_updates=updates;
  expect_fresh_display=expect_negative_x=1;
  pes_match_replay_mode_end((void*)0xabc,(void*)7);
  assert(expect_fresh_display);
  registry_available=0;frame();assert(!displayed && referee_probe_reposition && expect_fresh_display);
  registry_available=1;frame();assert(displayed && last_position.x<0);
  assert(!referee_probe_reposition && !expect_fresh_display);
  pes_match_replay_mode_init((void*)0xdef,(void*)7);
  referee_probe_clear();assert(!referee_recorded_replay_active());
  free(data);return 0;
}
''')


def test_optional_compatible_elf_admits_actual_offside_guard(tmp_path):
    Native = native_contract.RefereeNativeContractTests
    Native.setUpClass()
    try:
        hooks = (ROOT / "source/ue4_hooks.c").read_text()
        install = function(hooks, "referee_presentation_install")
        names = re.findall(r'"(_ZN[^"]+)"', install)
        buffers = []
        for i, name in enumerate(names):
            address, size = Native.symbols[name]
            raw = Native.read(address, min(size, 0x400))
            buffers.append("memcpy(code+%du,(unsigned char[]){%s},%du);" % (
                i * 0x400, ",".join(str(b) for b in raw), len(raw)))
        # Execute the production guard with original ELF bytes in inaccessible-
        # RX/writable-backing form; never execute or retain proprietary code.
        compile_run(tmp_path, r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
typedef struct{uintptr_t load_base,load_virtbase;size_t load_size;}so_module;
static unsigned char code[0x1800];
static uint32_t referee_presentation_layout_ok;
static const char *names[]={''' + ",".join('"' + n + '"' for n in names) + r'''};
static uintptr_t so_try_find_addr_rx(so_module *m,const char *s){
  for(unsigned i=0;i<6;++i)if(!strcmp(s,names[i]))return m->load_virtbase+i*0x400u;
  return 0;
}
static void scene_runtime_note(const char *a,const char *b){assert(a && b);}
''' + function(hooks, "referee_presentation_code") + install + r'''
int main(void){
  so_module m={(uintptr_t)code,0x10000000u,sizeof(code)};
''' + "\n".join(buffers) + r'''
  referee_presentation_install(&m);assert(referee_presentation_layout_ok);
  return 0;
}
''')
    finally:
        Native.tearDownClass()


def test_optional_replay_lifecycle_installer_uses_native_relocations(tmp_path):
    Native = native_contract.RefereeNativeContractTests
    Native.setUpClass()
    try:
        from elftools.elf.elffile import ELFFile
        Native.stream.seek(0)
        elf = ELFFile(Native.stream)
        vtable, size = Native.symbols["_ZTVN5match6ReplayE"]
        symbols = elf.get_section_by_name(".dynsym")
        relocations = {r["r_offset"]: r["r_addend"] +
                       (symbols.get_symbol(r["r_info_sym"])["st_value"]
                        if r["r_info_sym"] else 0) for r in
                       elf.get_section_by_name(".rela.dyn").iter_relocations()
                       if vtable <= r["r_offset"] < vtable + size}
        targets = []
        for method in ("8ModeInit", "8ModeMain", "7ModeEnd"):
            symbol = f"_ZN5match6Replay{method}EPKN5cobra4game7ContextE"
            target = Native.symbols[symbol][0]
            slots = [offset for offset, value in relocations.items() if value == target]
            assert len(slots) == 1
            assert 2 <= (slots[0] - vtable) // 8 < 64
            targets.append(target)
        hooks = (ROOT / "source/ue4_hooks.c").read_text()
        start = hooks.index("  const char *replay_mode_init_symbol =")
        end = hooks.index("\n  // Foul/offside/out-of-play demos", start)
        initializers = "\n".join(
            f"table[{(offset-vtable)//8}]=0x10000000u+{value}u;"
            for offset, value in relocations.items())
        compile_run(tmp_path, r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
typedef struct{uintptr_t load_base;}so_module;
static uintptr_t table[64];
static uintptr_t so_find_addr(so_module *m,const char *s){
  (void)m;assert(!strcmp(s,"_ZTVN5match6ReplayE"));return (uintptr_t)table;
}
static uintptr_t so_find_addr_rx(so_module *m,const char *s){
  (void)m;
  if(strstr(s,"ModeInit"))return 0x10000000u+''' + str(targets[0]) + r'''u;
  if(strstr(s,"ModeMain"))return 0x10000000u+''' + str(targets[1]) + r'''u;
  assert(strstr(s,"ModeEnd"));return 0x10000000u+''' + str(targets[2]) + r'''u;
}
static void fatal_error(const char *s){(void)s;assert(0);}
static uint32_t (*match_replay_mode_init_original)(void*,const void*);
static uint32_t (*match_replay_mode_main_original)(void*,const void*);
static uint32_t (*match_replay_mode_end_original)(void*,const void*);
static uint32_t pes_match_replay_mode_init(void*a,const void*b){(void)a;(void)b;return 0;}
static uint32_t pes_match_replay_mode_main(void*a,const void*b){(void)a;(void)b;return 0;}
static uint32_t pes_match_replay_mode_end(void*a,const void*b){(void)a;(void)b;return 0;}
''' + function(hooks, "find_vtable_method_slot") + r'''
int main(void){so_module m={0},*module=&m;
''' + initializers + hooks[start:end] + r'''
  assert(*replay_mode_init_slot==(uintptr_t)&pes_match_replay_mode_init);
  assert(*replay_mode_main_slot==(uintptr_t)&pes_match_replay_mode_main);
  assert(*replay_mode_end_slot==(uintptr_t)&pes_match_replay_mode_end);
  assert((uintptr_t)match_replay_mode_init_original==replay_mode_init_runtime);
  assert((uintptr_t)match_replay_mode_main_original==replay_mode_main_runtime);
  assert((uintptr_t)match_replay_mode_end_original==replay_mode_end_runtime);
  return 0;
}
''')
    finally:
        Native.tearDownClass()

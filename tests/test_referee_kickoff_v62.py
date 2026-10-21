"""Run actual referee publication with native stopped-kickoff snapshots."""
from pathlib import Path
import re
import shutil
import struct
import subprocess

import pytest

from test_gameplan_editor import function
import test_referee_native_contract as native_contract

ROOT = Path(__file__).resolve().parents[1]


def compile_run(tmp_path, source):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler required")
    path = tmp_path / "kickoff.c"
    path.write_text(source)
    exe = tmp_path / "kickoff.exe"
    subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-I", str(ROOT / "source"), "-I", str(ROOT / "tests"),
                    str(path), "-pthread", "-lm", "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=30)


def test_actual_publisher_keeps_both_goal_sides_planted_until_native_inplay(tmp_path):
    compile_run(tmp_path, r'''
#define main previous_canary_main
#include "test_scene_canaries.c"
#undef main
static unsigned char kickoff_info[0x1710];
static void put32(void *p,uint32_t n){memcpy(p,&n,4);}
static void native_status(unsigned status,unsigned restart){
  void *p=kickoff_info;memcpy(registry_data+0x4f0,&p,sizeof(p));
  put32(kickoff_info+0x116c,status);put32(kickoff_info+0x1514,restart);
}
static void at_kickoff(void){
  assert(displayed && last_position.x==0 && last_position.z==9.15f);
  assert(referee_kickoff_ready==2 && !referee_probe_reposition);
  assert(!referee_motion.velocity.x && !referee_motion.velocity.z);
}
int main(void){
  /* Reuse the production include and bounded renderer/lifetime fixture. */
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
  native_status(3,1);ball_data[0]=51;ball_data[2]=4;
  /* Initial warp can complete before the optional model is enqueued. */
  put32(flow_object+0xcd4,2);
  assert(referee_probe_position_warp(flow_object,(void*)7) && referee_kickoff_pending);
  preload();assert(referee_probe_model && referee_probe_loaded);
  const int allocated=creations,removed=deleted;
  inplay=4;frame();assert(!displayed && referee_kickoff_pending);
  inplay=2;frame();at_kickoff();
  native_status(1,1);ball_data[0]=7;frame();assert(!referee_kickoff_ready);
  unsigned char players_before[sizeof(human)];memcpy(players_before,human,sizeof(human));
  uint32_t serial=0;
  for(unsigned side=0;side<2;++side)for(unsigned end=0;end<2;++end)
    for(unsigned status=2;status<=3;++status){
    unsigned char record[0x60]={0},judge[0x30]={0};
    put32(record,0x24);put32(record+4,++serial);put32(record+0x10,1);
    put32(judge,1);put32(judge+4,side);put32(judge+0x20,3); /* native GOAL */
    referee_probe_out_of_play(record+0x14,registry_data,judge);
    const uint32_t event=(uint32_t)(referee_probe_event>>32);assert(event);
    referee_motion.position=(RefereePoint){end?40:-40,end?20:-20};
    ball_data[0]=end?52:-52;ball_data[2]=side?5:-5;
    native_status(status,1);inplay=4;frame();assert(!displayed);
    put32(flow_object+0xcd4,3);
    assert(referee_probe_position_warp(flow_object,(void*)7));
    const uint32_t applied=referee_kickoff_applied;
    frame();assert(referee_kickoff_pending && referee_kickoff_applied==applied);
    /* A pause/interval owner also cannot consume the pending placement. */
    inplay=1;frame();assert(referee_kickoff_pending);
    inplay=0;frame();assert(!displayed && referee_kickoff_pending);
    inplay=2;frame();at_kickoff();
    assert(referee_kickoff_applied==applied+1 && !referee_kickoff_pending);
    assert(referee_gesture.serial==event && !referee_gesture.clip);
    for(unsigned i=0;i<6;++i){frame();at_kickoff();}
    /* A replay return after consumption retains the native kickoff hold. */
    inplay=4;frame();assert(!displayed);
    inplay=2;frame();at_kickoff();
    registry_available=0;frame();registry_available=1;frame();at_kickoff();
    /* Whistle remains planted even if native IN_PLAY and first pass arrive
     * before the first centre-ball sample. Native audio is forwarded once. */
    const uint8_t command=0x4f;const unsigned sounds=sound_calls;
    referee_probe_sound((void*)3,100+serial,&command,0x1d,(void*)4,22);
    native_status(1,1);ball_data[0]=end?-7:7;ball_data[2]=2;frame();at_kickoff();
    assert(sound_calls==sounds+1 && referee_gesture.clip==4);
    frame();frame();frame();assert(!referee_kickoff_ready);
    assert(creations==allocated && deleted==removed);
    assert(!memcmp(players_before,human,sizeof(human)));
  }
  /* Fast first pass without a whistle releases immediately on native IN_PLAY;
   * no centre sample or elapsed-time/teleport fallback is required. */
  put32(flow_object+0xcd4,3);native_status(1,1);ball_data[0]=9;ball_data[2]=1;
  assert(referee_probe_position_warp(flow_object,(void*)7));
  frame();assert(!referee_kickoff_ready && last_position.z==9.15f);
  /* Missing status/layout retains the established bounded ball fallback. */
  for(unsigned fallback=0;fallback<3;++fallback){
    native_status(fallback==2?99:3,1);referee_kickoff_layout_ok=fallback!=0;
    if(fallback==1)*(void**)(registry_data+0x4f0)=NULL;
    assert(referee_probe_native_kickoff(registry_data)==-1);
    assert(referee_probe_position_warp(flow_object,(void*)7));
    ball_data[0]=0;ball_data[2]=0;frame();at_kickoff();
    ball_data[0]=8;frame();assert(!referee_kickoff_ready);
  }
  referee_kickoff_layout_ok=1;
  native_status(3,4);assert(!referee_probe_native_kickoff(registry_data));
  native_status(1,1);assert(!referee_probe_native_kickoff(registry_data));
  native_status(3,99);assert(referee_probe_native_kickoff(registry_data)==-1);
  assert(referee_probe_native_kickoff(NULL)==-1);
  referee_probe_clear();assert(!referee_probe_model && !referee_kickoff_pending);
  free(data);return 0;
}
''')


def test_contract_guards_read_only_backing_and_reject_each_mismatch(tmp_path):
    source = (ROOT / "source/referee_probe.inc").read_text()
    contract = function(source, "referee_probe_kickoff_contract")
    checks = re.findall(r'\{"([^"]+)",(0x[0-9a-f]+|0),(0x[0-9a-f]+)\}', contract)
    assert len(checks) == 8
    initializers = ",\n".join(f'{{"{s}",{o},{w}}}' for s, o, w in checks)
    compile_run(tmp_path, r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef struct{void *load_base,*load_virtbase;size_t load_size;}so_module;
static unsigned char code[0x5000];
static const char *missing;
static uintptr_t so_find_addr(so_module *m,const char *s){
  size_t offset=strstr(s,"OpenRead")?0:strstr(s,"ExecWaitInPlay")?0x1000:
      strstr(s,"ToInPlay")?0x2000:0x3000;
  return (uintptr_t)m->load_base+offset;
}
static uintptr_t so_try_find_addr_rx(so_module *m,const char *s){
  return missing && !strcmp(s,missing)?0:so_find_addr(m,s);
}
''' + contract + r'''
int main(void){
  /* No executable address exists: installation must inspect backing only. */
  so_module m={code,NULL,sizeof(code)};
  const struct{const char *symbol;unsigned offset,word;}checks[]={
''' + initializers + r'''};
  for(unsigned i=0;i<sizeof(checks)/sizeof(checks[0]);++i)
    memcpy((void*)(so_find_addr(&m,checks[i].symbol)+checks[i].offset),&checks[i].word,4);
  assert(referee_probe_kickoff_contract(&m));
  for(unsigned i=0;i<sizeof(checks)/sizeof(checks[0]);++i){
    unsigned char *p=(void*)(so_find_addr(&m,checks[i].symbol)+checks[i].offset);
    *p^=1;assert(!referee_probe_kickoff_contract(&m));
    *p^=1;assert(referee_probe_kickoff_contract(&m));
    missing=checks[i].symbol;assert(!referee_probe_kickoff_contract(&m));missing=NULL;
  }
  m.load_size=0x3000;assert(!referee_probe_kickoff_contract(&m));
  m.load_base=NULL;assert(!referee_probe_kickoff_contract(&m));
  assert(!referee_probe_kickoff_contract(NULL));return 0;
}
''')


def test_optional_native_words_status_names_and_assistant_stubs():
    # Optional proprietary input remains ignored; no extracted bytes are saved.
    Native = native_contract.RefereeNativeContractTests
    Native.setUpClass()
    try:
        source = (ROOT / "source/referee_probe.inc").read_text()
        contract = function(source, "referee_probe_kickoff_contract")
        for symbol, offset, word in re.findall(
                r'\{"([^"]+)",(0x[0-9a-f]+|0),(0x[0-9a-f]+)\}', contract):
            assert Native.word(Native.symbols[symbol][0] + int(offset, 16)) == int(word, 16)
        pointers = struct.unpack("<4Q", Native.read(0x93af700, 32))
        assert [Native.read(p, 32).split(b"\0")[0].decode() for p in pointers] == [
            "MATCH_STATUS_NONE", "IN_PLAY", "OUT_OF_PLAY", "SET_PLAY"]
        for action in ("12LinesmanMove", "14LinesmanAction"):
            for method, args in (("7Execute", "EPNS_11AnimePlayerERNS1_3ArgE"),
                                 ("15UpdateAnimeInfo", "ERNS_8registry9AnimeInfoEPNS_11AnimePlayerE")):
                symbol = f"_ZN5match5anime6action{action}{method}{args}"
                address, size = Native.symbols[symbol]
                assert size == 4 and Native.word(address) == 0xd65f03c0
    finally:
        Native.tearDownClass()

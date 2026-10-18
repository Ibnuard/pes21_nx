"""Native entrance lifecycle releases only the armed VS cover, not other UI."""
from pathlib import Path
import re
import shutil

import pytest
from test_gameplan_editor import function
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]


def test_checked_install_and_native_first_lifecycle():
    cc = shutil.which('gcc')
    if not cc:
        pytest.skip('host C compiler required')
    source = (ROOT/'source/ue4_hooks.c').read_text()
    reveal = function(source, 'kickoff_loading_reveal')
    include = (ROOT/'source/native_prematch_reveal.inc').as_posix()
    build_and_run(cc, r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef struct {int unused;} so_module;
enum {MAIN_MENU_2P_TRANSITION_NONE, MAIN_MENU_2P_TRANSITION_VS, OTHER};
static uint32_t kickoff_loading_armed, main_menu_2p_transition_kind;
static uint32_t main_menu_2p_transition_active;
static unsigned calls, notes, rmw, failure;
#define debugPrintf(...) ((void)0)
#define __atomic_exchange_n(p,v,o) (++rmw,__atomic_exchange_n((p),(v),(o)))
static void native(void *p) { assert(p==(void *)42); ++calls; }
static uintptr_t slot;
static uint32_t words[8]={0xa9bf7bf3,0xaa0003f3,0x96ea4709,0x96e7768c,
                        0x36000060,0xa8c17bf3,0xd65f03c0,0x96ea4704};
static uintptr_t so_try_find_addr_rx(so_module *m,const char *name) {
  (void)m;
  if(strstr(name,"_ZTV"))return failure==1?0:1;
  return failure==2?0:(uintptr_t)&native;
}
static uintptr_t so_find_addr(so_module *m,const char *name) {
  (void)m;(void)name;return failure==3?0:(uintptr_t)words;
}
static uintptr_t *find_vtable_method_slot(so_module *m,const char *name,
                                        uintptr_t method,unsigned limit) {
  (void)m;(void)name;assert(method==(uintptr_t)&native && limit==32);
  return failure==5?NULL:&slot;
}
static void scene_runtime_note(const char *area,const char *message) {
  assert(calls>0); assert(!strcmp(area,"native prematch"));
  assert(strstr(message,"entrance started"));++notes;
}
''' + reveal + '\n#include "'+include+'"\n' + r'''
int main(void) {
  so_module module={0};
  for(failure=1;failure<=5;failure++) {
    slot=(uintptr_t)&native;
    if(failure==4)words[0]^=1;
    install_native_prematch_reveal(&module);
    assert(slot==(uintptr_t)&native && !native_prematch_reveal_installed);
    if(failure==4)words[0]^=1;
  }
  failure=0; install_native_prematch_reveal(&module);
  assert(slot==(uintptr_t)&native_prematch_entrance_start);
  install_native_prematch_reveal(&module);
  assert(native_entrance_start_original==&native);
  kickoff_loading_armed=1;main_menu_2p_transition_kind=MAIN_MENU_2P_TRANSITION_VS;
  main_menu_2p_transition_active=1;
  native_prematch_entrance_start((void *)42);
  assert(calls==1 && notes==1 && !kickoff_loading_armed);
  assert(!main_menu_2p_transition_active && main_menu_2p_transition_kind==0);
  const unsigned before=rmw;
  for(unsigned i=0;i<100000;i++)kickoff_loading_reveal();
  assert(rmw==before); /* Ordinary gameplay cannot write this cache line. */
  native_prematch_entrance_start((void *)42);
  assert(calls==2 && notes==1); /* No recursion; no repeated journal writes. */
  main_menu_2p_transition_kind=OTHER;main_menu_2p_transition_active=1;
  native_prematch_entrance_start((void *)42);
  assert(calls==3 && notes==1 && main_menu_2p_transition_active);
  assert(main_menu_2p_transition_kind==OTHER);
  /* No-entrance mode retains the existing card/live-gameplay fallback. */
  kickoff_loading_armed=1;main_menu_2p_transition_kind=MAIN_MENU_2P_TRANSITION_VS;
  kickoff_loading_reveal();assert(!main_menu_2p_transition_active);
}
''')


def test_native_fingerprint_matches_audited_start_without_experiment_activation():
    source=(ROOT/'source/native_prematch_reveal.inc').read_text()
    trace=(ROOT/'source/fixdemo_scene_trace.inc').read_text()
    words=lambda s: re.findall(r'0x[0-9a-f]+',s)
    start=source.split('expected_start[8] = {',1)[1].split('};',1)[0]
    old=trace.split('expected_words[][8] = {',1)[1].split('};',1)[0]
    assert words(start)==words(old)[8:16]
    hooks=(ROOT/'source/ue4_hooks.c').read_text()
    assert 'else\n    install_native_prematch_reveal(module);' in hooks
    assert 'EndDemoEvent' not in source and 'SetSceneId' not in source

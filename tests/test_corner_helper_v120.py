"""Execute the shared nameplate gate and corner lifetime without engine pointers."""
from pathlib import Path
import shutil
import subprocess

import pytest

from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def helper_binary(tmp_path_factory):
    cc = shutil.which('gcc') or shutil.which('clang')
    if not cc:
        pytest.skip('host C compiler required')
    hooks = (ROOT / 'source/ue4_hooks.c').read_text()
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "corner_tactics.h"
typedef struct { unsigned surface; } PesControllerSnapshot;
enum { PES_CONTROLLER_SURFACE_NONE=0, PES_MOBILE_CONTROL_UNKNOWN=0,
       PES_VIRTUAL_CURSOR_NONE=0 };
static uint64_t now=100000000,match_hud_inplay_tick=100000000;
static uint64_t match_scoreboard_visible_tick=100000000;
static unsigned match_scoreboard_visible=1,blockers;
static uint64_t armGetSystemTick(void) { return now; }
static uint64_t armTicksToNs(uint64_t ticks) { return ticks; }
static void pes_controller_surface_cached_snapshot(PesControllerSnapshot *s) { s->surface=blockers&1u; }
static int pes_mobile_control_active_mode(void) { return !(blockers&2u); }
static int pes_controller_replay_active(void) { return blockers&4u; }
static int pes_controller_goal_demo_active(void) { return blockers&8u; }
static int pes_controller_cinematic_skip_active(void) { return blockers&16u; }
static int pes_controller_fix_demo_skip_active(void) { return blockers&32u; }
static int pes_controller_pause_skin_active(void) { return blockers&64u; }
static int pes_controller_pause_transition(void) { return blockers&128u; }
static int pes_controller_match_result_skin(void) { return blockers&256u; }
static int pes_controller_match_result_transition(void) { return blockers&512u; }
static unsigned pes_controller_virtual_cursor_context(void) { return blockers&1024u; }
''' + function(hooks, 'pes_controller_match_hud_inplay') + '\n' + function(
        hooks, 'pes_controller_nameplate_ready') + r'''
static void publish(unsigned side) {
  fnx_corner_publish(side,42,side ? FNX_CORNER_DEFENCE : FNX_CORNER_ATTACK,
                     1,8,4,0,1000);
}
static unsigned input(unsigned side,unsigned keys) {
  return fnx_corner_input(side,1000,1,1,keys,!keys);
}
static void open_and_queue(unsigned side) {
  input(side,0);input(side,FNX_CORNER_LEFT);input(side,0);
  input(side,FNX_CORNER_UP);
}
int main(int argc,char **argv) {
  assert(argc==2);fnx_corner_reset();
  if(!strcmp(argv[1],"lifecycle")) {
    assert(pes_controller_nameplate_ready());
    for(unsigned bit=1;bit<=1024;bit<<=1) {
      blockers=bit;assert(!pes_controller_nameplate_ready());
    }
    blockers=0;assert(pes_controller_nameplate_ready());
    match_hud_inplay_tick=0;assert(!pes_controller_nameplate_ready());
    match_hud_inplay_tick=now;match_scoreboard_visible=0;
    assert(!pes_controller_nameplate_ready());
    match_scoreboard_visible=1;match_scoreboard_visible_tick=0;
    assert(!pes_controller_nameplate_ready());
    match_scoreboard_visible_tick=now+1;assert(!pes_controller_nameplate_ready());
    match_scoreboard_visible_tick=now-80000000;
    assert(pes_controller_nameplate_ready());
    match_scoreboard_visible_tick--;assert(!pes_controller_nameplate_ready());
    match_scoreboard_visible_tick=now;match_hud_inplay_tick=now-80000001;
    assert(!pes_controller_nameplate_ready());
  } else if(!strcmp(argv[1],"both-owners")) {
    publish(0);publish(1);open_and_queue(0);open_and_queue(1);
    /* Identical reads by either owner must not cancel an actual choice. */
    fnx_corner_set_nameplate_ready(0);fnx_corner_set_nameplate_ready(0);
    uint32_t command;uint8_t option;
    assert(fnx_corner_take(0,42,1000,&command,&option));
    assert(command==0x6e && option==1);
    open_and_queue(0);
    fnx_corner_set_nameplate_ready(pes_controller_nameplate_ready());
    for(unsigned pad=0;pad<2;pad++) {
      FnxCornerView v;fnx_corner_view(pad,1000,&v);
      assert(!v.available && !v.open);
      assert(!fnx_corner_take(pad,42,1000,&command,&option));
      assert(!input(pad,FNX_CORNER_LEFT|FNX_CORNER_BACK));
      publish(pad);fnx_corner_view(pad,1000,&v);assert(!v.available);
    }
    /* Names disappear for the next restart; old native publications cannot
     * revive. Both pads independently wait for their fresh corner context. */
    match_scoreboard_visible=0;
    fnx_corner_set_nameplate_ready(pes_controller_nameplate_ready());
    FnxCornerView v;fnx_corner_view(0,1000,&v);assert(!v.available);
    fnx_corner_view(1,1000,&v);assert(!v.available);
    publish(0);fnx_corner_view(0,1000,&v);assert(v.available && !v.open);
    fnx_corner_view(1,1000,&v);assert(!v.available);
    fnx_corner_set_nameplate_ready(0);fnx_corner_view(0,1000,&v);assert(v.available);
    publish(1);open_and_queue(1);
    fnx_corner_set_nameplate_ready(0);
    assert(fnx_corner_take(1,42,1000,&command,&option));
    assert(command==0x6f && option==2);
  } else return 2;
  return 0;
}
'''
    folder = tmp_path_factory.mktemp('corner-helper-v120')
    source = folder / 'helper.c'
    source.write_text(code)
    binary = folder / 'helper.exe'
    subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pthread',
                    '-I', str(ROOT / 'source'), str(source),
                    str(ROOT / 'source/corner_tactics.c'), '-o', str(binary)],
                   check=True, capture_output=True, text=True)
    return binary


@pytest.mark.parametrize('case', ['lifecycle', 'both-owners'])
def test_shared_nameplate_and_corner_gate(helper_binary, case):
    result = subprocess.run([str(helper_binary), case], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_visible_cards_and_hidden_preference_cannot_reenable_corner_tactics():
    hooks = (ROOT / 'source/ue4_hooks.c').read_text()
    ready = function(hooks, 'pes_controller_nameplate_ready')
    assert 'pause_settings_show_nameplate' not in ready
    bars = function(hooks, 'pes_controller_stamina_bars')
    assert bars.index('pes_controller_nameplate_ready()') < bars.index('pause_settings_show_nameplate')
    overlay = (ROOT / 'source/overlay.c').read_text()
    gate = 'fnx_corner_set_nameplate_ready(stamina_bar_count != 0 || pes_controller_nameplate_ready());'
    assert overlay.index(gate) < overlay.index('FnxCornerView corner_views[2]')

"""Run the production helper builder with stale corner views and real restarts."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_actual_overlay_uses_thrower_and_only_owned_goal_kick_helpers(tmp_path):
    compiler = shutil.which('gcc') or shutil.which('clang')
    if not compiler:
        pytest.skip('Host C compiler unavailable')
    overlay = (ROOT / 'source/overlay.c').read_text()
    start = overlay.index('  FnxCornerView corner_views[2]={{0}};')
    end = overlay.index('  const int penalty_helper_active =', start)
    source = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "corner_tactics.h"
#define PES_SETPLAY_NONE 0
#define PES_SETPLAY_GOAL_KICK 1
#define PES_SETPLAY_CORNER 2
#define PES_SETPLAY_FREE_KICK 3
#define PES_SETPLAY_THROW_IN 4
#define PES_SETPLAY_OPTION_KICKER 1
#define PES_CONTROLLER_PROFILE_FULL 0
#define PES_VIRTUAL_CURSOR_NONE 0
#define PES_CONTROLLER_SURFACE_REPLAY 10
#define PES_CONTROLLER_SURFACE_GOAL_DEMO 11
#define PES_CONTROLLER_SURFACE_CINEMATIC 12
#define PES_NATIVE_LAB_STOCK_FREEKICK_TACTICS 32
#define PES_NATIVE_LAB_STOCK_FREEKICK_POSITION 64
#define PES_NATIVE_LAB_STOCK_GOALKICK_SUPPORT 4
static uint64_t armGetSystemTick(void){return 1000000000;}
static uint64_t armTicksToNs(uint64_t value){return value;}
static int pes_controller_native_pad_lab_two_player(void){return 1;}
static int android_controller_profile(unsigned pad){(void)pad;return 0;}
static int pes_controller_free_kick_offside(void){return 0;}
static unsigned reads;
void fnx_corner_view(uint32_t pad,uint64_t now,FnxCornerView *view){
 (void)now;reads++;memset(view,0,sizeof(*view));
 view->available=1;view->mode=pad ? FNX_CORNER_DEFENCE : FNX_CORNER_ATTACK;
}
static void check(unsigned setplay_context,unsigned mask,unsigned expected,const char *label) {
 int native_lab=1,frontdoor_page=0,set_piece_selector=0,custom_gameplan=0;
 int custom_2p_transition=0,virtual_cursor_context=0,single_joy_setplay=0;
 int native_setplay_debug=1;unsigned setplay_options=0;
 const char *setplay_taker_key="RIGHT";
 struct {unsigned stock_mask;} native_debug={mask};
 struct {unsigned surface;} controller_snapshot={0};
 reads=0;
''' + overlay[start:end] + r'''
 assert(setplay_helper_count==expected);
 if(label)assert(!strcmp(setplay_labels[0],label));
 if(setplay_context!=PES_SETPLAY_CORNER) {
  assert(!reads);
  for(unsigned i=0;i<setplay_helper_count;i++)
   assert(!strstr(setplay_labels[i],"CORNER") && !strstr(setplay_labels[i],"TACTICS"));
 }
}
int main(void) {
 check(PES_SETPLAY_THROW_IN,0,1,"SELECT THROWER");
 check(PES_SETPLAY_GOAL_KICK,0,0,0);
 check(PES_SETPLAY_GOAL_KICK,PES_NATIVE_LAB_STOCK_GOALKICK_SUPPORT,1,"POSITION SHIFT");
 check(PES_SETPLAY_FREE_KICK,0,3,"SET PIECE TAKER");
 check(PES_SETPLAY_CORNER,0,3,"SET PIECE TAKER"); // Per-pad tactics entries render in their own corners.
}
'''
    path, executable = tmp_path / 'helpers.c', tmp_path / 'helpers.exe'
    path.write_text(source)
    built = subprocess.run([compiler, '-std=c11', '-I', str(ROOT / 'source'),
                            str(path), '-o', str(executable)], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    result = subprocess.run([str(executable)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

"""Exercise the actual preset state machine with controlled storage results."""
from pathlib import Path
import shutil
import subprocess
import pytest
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]

def test_empty_save_overwrite_load_success_cancel_and_failure(tmp_path):
    cc=shutil.which('gcc') or shutil.which('clang')
    if not cc: pytest.skip('host C compiler unavailable')
    hooks=(ROOT/'source/ue4_hooks.c').read_text()
    source=r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define GAMEPLAN_PRESET_SLOTS 3u
#define PES_PREMATCH_GAMEPLAN_PAGE_ROOT 0u
enum {PES_PAUSE_INPUT_LEFT=1,PES_PAUSE_INPUT_RIGHT,PES_PAUSE_INPUT_UP,PES_PAUSE_INPUT_DOWN,PES_PAUSE_INPUT_BACK,PES_PAUSE_INPUT_DECIDE};
typedef struct {uint32_t preset_step,preset_focus,preset_action,preset_target_slot,preset_exists[3],page;char preset_status[96];} PrematchGameplanSide;
static PrematchGameplanSide exhibition_gameplan_sides[2];
static void *live_gameplan_window;
static int saved[2][3],save_calls,load_calls,fail;
static int prematch_gameplan_save_preset(uint32_t side,uint32_t slot){save_calls++;if(fail)return 0;saved[side][slot]=1;return 1;}
static int prematch_gameplan_load_preset(uint32_t side,uint32_t slot){load_calls++;return saved[side][slot]&&!fail;}
static void prematch_gameplan_refresh_preset_slots(uint32_t side){for(int i=0;i<3;i++)exhibition_gameplan_sides[side].preset_exists[i]=saved[side][i];}
''' + function(hooks,'prematch_gameplan_finish_preset') + function(hooks,'prematch_gameplan_process_preset') + r'''
static void tap(uint32_t key){prematch_gameplan_process_preset(0,key);}
int main(void){
  PrematchGameplanSide *s=&exhibition_gameplan_sides[0];s->page=3;
  PrematchGameplanSide other=exhibition_gameplan_sides[1];
  tap(PES_PAUSE_INPUT_DECIDE);assert(s->preset_step==1 && !save_calls);
  tap(PES_PAUSE_INPUT_DECIDE);assert(s->preset_step==3 && save_calls==1 && strstr(s->preset_status,"SAVED"));
  tap(PES_PAUSE_INPUT_DOWN);assert(s->preset_step==3 && save_calls==1);
  tap(PES_PAUSE_INPUT_DECIDE);assert(!s->preset_step && s->page==3 && !s->preset_focus);
  tap(PES_PAUSE_INPUT_DECIDE);tap(PES_PAUSE_INPUT_DECIDE);assert(s->preset_step==2 && s->preset_focus==1);
  tap(PES_PAUSE_INPUT_DECIDE);assert(s->preset_step==1 && save_calls==1); // cancel
  tap(PES_PAUSE_INPUT_DECIDE);tap(PES_PAUSE_INPUT_LEFT);tap(PES_PAUSE_INPUT_DECIDE);
  assert(s->preset_step==3 && save_calls==2);tap(PES_PAUSE_INPUT_BACK);assert(!s->preset_step);
  tap(PES_PAUSE_INPUT_DOWN);tap(PES_PAUSE_INPUT_DECIDE);tap(PES_PAUSE_INPUT_DECIDE);
  assert(s->preset_step==2 && !load_calls);tap(PES_PAUSE_INPUT_BACK);assert(s->preset_step==1 && !load_calls);
  tap(PES_PAUSE_INPUT_DECIDE);tap(PES_PAUSE_INPUT_LEFT);tap(PES_PAUSE_INPUT_DECIDE);
  assert(s->preset_step==3 && load_calls==1 && strstr(s->preset_status,"LOADED"));
  tap(PES_PAUSE_INPUT_DECIDE);assert(!s->preset_step && s->preset_focus==1 && s->page==3);
  tap(PES_PAUSE_INPUT_DECIDE);tap(PES_PAUSE_INPUT_DOWN);tap(PES_PAUSE_INPUT_DECIDE);
  assert(s->preset_step==4 && load_calls==1 && strstr(s->preset_status,"EMPTY"));
  tap(PES_PAUSE_INPUT_DECIDE);assert(s->preset_step==1 && s->preset_focus==1);
  tap(PES_PAUSE_INPUT_UP);tap(PES_PAUSE_INPUT_DECIDE);tap(PES_PAUSE_INPUT_LEFT);fail=1;tap(PES_PAUSE_INPUT_DECIDE);
  assert(s->preset_step==4 && load_calls==2);tap(PES_PAUSE_INPUT_BACK);assert(s->preset_step==1);
  assert(!memcmp(&other,&exhibition_gameplan_sides[1],sizeof(other)));
}
'''
    path=tmp_path/'flow.c';path.write_text(source);exe=tmp_path/'flow.exe'
    subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror',str(path),'-o',str(exe)],check=True,capture_output=True,text=True)
    subprocess.run([str(exe)],check=True,capture_output=True,text=True)

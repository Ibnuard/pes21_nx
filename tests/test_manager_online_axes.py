"""Exercise the real HID normalization and atomic menu-axis publisher."""
from pathlib import Path
import shutil
import subprocess

import pytest
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


def test_exhibition_and_online_share_screen_space_stick_axes(tmp_path):
    compiler = shutil.which("gcc")
    if not compiler:
        pytest.skip("Host C compiler unavailable")
    shim = (ROOT / "source/android_shim.c").read_text()
    hooks = (ROOT / "source/ue4_hooks.c").read_text()
    source = r'''
#include <stdint.h>
#include <math.h>
#include <assert.h>
#define JOYSTICK_MAX 32767
typedef struct {int32_t x,y;} HidAnalogStickState;
static uint32_t main_menu_screen_axes;
'''
    source += function(shim, "normalize_stick") + "\n"
    source += function(hooks, "pes_main_menu_pad_axes") + "\n"
    source += r'''
int main(void){
  const HidAnalogStickState inputs[]={{0,32767},{0,-32767},{32767,0},{-32767,0},{0,0},{1000,-1000}};
  for(unsigned i=0;i<6;i++){
    float x,y;normalize_stick(&inputs[i],1,&x,&y);pes_main_menu_pad_axes(x,y);
    uint32_t packed=__atomic_load_n(&main_menu_screen_axes,__ATOMIC_ACQUIRE);
    int16_t sx=(int16_t)packed,sy=(int16_t)(packed>>16);
    if(i==0)assert(sy<0&&sx==0); /* Physical UP is screen UP. */
    if(i==1)assert(sy>0&&sx==0);
    if(i==2)assert(sx>0&&sy==0);
    if(i==3)assert(sx<0&&sy==0);
    if(i>=4)assert(sx==0&&sy==0); /* Deadzone never drags. */
  }
  float x,y;normalize_stick(&inputs[0],0,&x,&y);pes_main_menu_pad_axes(x,y);
  assert(main_menu_screen_axes==0);
}
'''
    path = tmp_path / "axes.c"
    path.write_text(source)
    exe = tmp_path / "axes.exe"
    subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", str(path), "-lm", "-o", str(exe)], check=True, capture_output=True)
    subprocess.run([str(exe)], check=True, capture_output=True)

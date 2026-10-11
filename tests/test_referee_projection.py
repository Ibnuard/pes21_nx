"""Production projection hand-off: stale cameras cannot hide the referee."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_native_camera_margin_and_invalid_observations(tmp_path):
    compiler = shutil.which('gcc') or shutil.which('clang')
    if not compiler:
        pytest.skip('host C compiler unavailable')
    text = (ROOT/'source/ue4_hooks.c').read_text()
    start = text.index('static void referee_probe_project(')
    end = text.index('\n}\n', start)+3
    harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <math.h>
typedef struct { float x,y,z; } Match2DVector3;
static uint32_t referee_probe_enabled;
static uint64_t referee_world_tick,referee_world_point,referee_screen_sample;
static uint64_t now=500000000;
static int live=1,calls;
static float sx=640,sy=360,w=1280,h=720;
static uint64_t armGetSystemTick(void){return now;}
static uint64_t referee_elapsed_ns(uint64_t a,uint64_t b){return b-a;}
static int pes_controller_match_hud_inplay(void){return live;}
static void project(void *model,Match2DVector3 p,float *x,float *y){
  assert(model==(void*)1);assert(fabsf(p.x+12.5f)<.001f && p.y==1.1f && fabsf(p.z-7.25f)<.001f);
  calls++;*x=sx;*y=sy;
}
static float width(void){return w;}
static float height(void){return h;}
static void (*match_model_project_pos_3d_to_screen)(void*,Match2DVector3,float*,float*)=project;
static float (*match_projection_display_width)(void)=width;
static float (*match_projection_display_height)(void)=height;
''' + text[start:end] + r'''
int main(void){
  referee_probe_project((void*)1);assert(!calls && !referee_screen_sample);
  referee_probe_enabled=1;
  referee_probe_project((void*)1);assert(!calls && !referee_screen_sample);
  referee_world_point=(uint32_t)-12500|((uint64_t)7250<<32);referee_world_tick=now;
  referee_probe_project((void*)1);assert(calls==1 && referee_screen_sample==(now<<1));
  sx=-255;referee_probe_project((void*)1);assert(!(referee_screen_sample&1));
  sx=-257;referee_probe_project((void*)1);assert(referee_screen_sample&1);
  sx=1535;referee_probe_project((void*)1);assert(!(referee_screen_sample&1));
  sx=1537;referee_probe_project((void*)1);assert(referee_screen_sample&1);
  sx=640;sy=-143;referee_probe_project((void*)1);assert(!(referee_screen_sample&1));
  sy=-145;referee_probe_project((void*)1);assert(referee_screen_sample&1);
  sy=865;referee_probe_project((void*)1);assert(referee_screen_sample&1);
  sy=NAN;referee_probe_project((void*)1);assert(!referee_screen_sample);
  sy=900;w=0;referee_probe_project((void*)1);assert(!referee_screen_sample);w=1280;
  live=0;referee_probe_project((void*)1);assert(!referee_screen_sample);live=1;
  referee_world_tick=now-100000001;referee_probe_project((void*)1);assert(!referee_screen_sample);
  referee_world_tick=now+1;referee_probe_project((void*)1);assert(!referee_screen_sample);
  referee_world_tick=now;referee_probe_project(NULL);assert(!referee_screen_sample);
  match_model_project_pos_3d_to_screen=NULL;referee_probe_project((void*)1);assert(!referee_screen_sample);
}
'''
    src = tmp_path/'projection.c'
    src.write_text(harness)
    exe = tmp_path/'projection.exe'
    result = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', str(src), '-lm', '-o', str(exe)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout+result.stderr
    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout+result.stderr

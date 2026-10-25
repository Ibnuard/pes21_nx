"""Exercise the production HID helper: loading, stick bits and input rearming."""
from pathlib import Path
import shutil
import subprocess
import pytest
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


def test_cup_skip_requires_started_released_intentional_input(tmp_path):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler required")
    android = (ROOT / "source/android_shim.c").read_text(encoding="utf-8")
    code = r'''
#include <stdint.h>
#include <assert.h>
typedef uint64_t u64;
typedef struct { int unused; } FakeTouchState;
enum { HidNpadButton_A=1, HidNpadButton_B=2, HidNpadButton_X=4,
       HidNpadButton_Y=8, HidNpadButton_Plus=16 };
enum { PES_CEREMONY_INPUT_NONE, PES_CEREMONY_INPUT_LOADING,
       PES_CEREMONY_INPUT_PLAYING };
enum { PES_REPLAY_FEEDBACK_A_SKIP=1, PES_REPLAY_FEEDBACK_SKIP=2 };
static uint32_t synthetic_input_generation=1, phase, requests, feedback;
static int replay_touch_requested;
uint32_t pes_controller_ceremony_input_state(void) { return phase; }
static void pes_controller_demo_skip_request(void) { ++requests; }
static void pes_controller_replay_feedback_set(int value) { feedback=value; }
''' + function(android[android.index("static uint32_t append_cinematic_skip_controller"):],
                  "append_cinematic_skip_controller")
    code += r'''
static void sample(int connected, u64 buttons, u64 previous) {
  replay_touch_requested=1;
  assert(!append_cinematic_skip_controller(0,connected,buttons,previous,100));
  assert(!replay_touch_requested);
}
int main(void) {
  const u64 noise=UINT64_C(0xfff00000); /* HID stick directions/status, not keys */
  phase=PES_CEREMONY_INPUT_LOADING;
  for (int i=0;i<100;++i) {
    sample(1,noise,0); sample(1,HidNpadButton_A,0);
  }
  assert(!requests && !feedback);
  phase=PES_CEREMONY_INPUT_PLAYING;
  /* A held gameplay key must be released after the loading/play transition. */
  sample(1,HidNpadButton_A,0); sample(1,HidNpadButton_A,0);
  assert(!requests);
  sample(1,noise,0); sample(1,noise,0); assert(!requests);
  sample(1,HidNpadButton_A,0); assert(requests==1 && feedback==1);
  sample(1,HidNpadButton_A,HidNpadButton_A); assert(requests==1);
  sample(1,0,HidNpadButton_A);
  sample(1,HidNpadButton_B,0); assert(requests==2 && feedback==2);
  /* Profile/context reset and disconnect require another neutral sample. */
  ++synthetic_input_generation;
  sample(1,HidNpadButton_X,0); assert(requests==2);
  sample(1,0,0); sample(1,HidNpadButton_X,0); assert(requests==3);
  sample(0,0,0); sample(1,HidNpadButton_Y,0); assert(requests==3);
  sample(1,0,0); sample(1,HidNpadButton_Y,0); assert(requests==4);
  sample(1,noise,0); sample(1,HidNpadButton_Plus,0); assert(requests==5);
  /* A new ceremony re-arms independently; ordinary native demos retain input. */
  phase=PES_CEREMONY_INPUT_LOADING; sample(1,0,0);
  phase=PES_CEREMONY_INPUT_PLAYING; sample(1,HidNpadButton_B,0);
  assert(requests==5); sample(1,0,0); sample(1,HidNpadButton_B,0);
  assert(requests==6);
  phase=PES_CEREMONY_INPUT_NONE; sample(1,noise,0); assert(requests==7);
  return 0;
}
'''
    source = tmp_path / "trophy-hid.c"
    source.write_text(code, encoding="utf-8")
    exe = tmp_path / "trophy-hid.exe"
    build = subprocess.run([compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                            source.as_posix(), "-o", exe.as_posix()], capture_output=True,
                           text=True, timeout=60)
    assert build.returncode == 0, build.stdout + build.stderr
    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
    assert ran.returncode == 0, ran.stdout + ran.stderr

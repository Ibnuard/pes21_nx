"""Exercise the actual native-callback and world-tick glue for optional sparks."""
from pathlib import Path
import shutil
import subprocess

import pytest
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


def run_c(tmp_path, body):
    cc = shutil.which('gcc') or shutil.which('clang')
    if not cc:
        pytest.skip('host C compiler required')
    src, exe = tmp_path / 'glue.c', tmp_path / 'glue.exe'
    src.write_text(body)
    built = subprocess.run([cc, '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
        '-Wno-unused-function', '-Wno-unused-variable', '-I', (ROOT / 'source').as_posix(),
        '-I', (ROOT / 'tests').as_posix(),
        src.as_posix(), '-o', exe.as_posix(), '-lm'], capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
    assert ran.returncode == 0, ran.stdout + ran.stderr


def test_live_bound_podium_callback_captures_only_admitted_generation(tmp_path):
    # Reuse the existing native callback fixture with optional FX enabled.
    run_c(tmp_path, r'''
#include <stdint.h>
#define PESNX_TROPHY_SPARKS_RUNTIME 1
static uint64_t fixdemo_trophy_sparks_active_epoch(void);
static void fixdemo_trophy_sparks_observe(uint64_t,uint64_t,void*,void*,uint64_t);
#define main original_props_main
#include "test_fixdemo_trophy_props_runtime.c"
#undef main
static unsigned captures;
static uint64_t captured_generation;
static uint64_t fixdemo_trophy_sparks_active_epoch(void) { return 7; }
static void fixdemo_trophy_sparks_observe(uint64_t epoch,uint64_t generation,
    void *actor,void *component,uint64_t active) {
  assert(epoch==7 && active==7 && generation && callbacks);
  assert(actor==rigs[1].actor.data && component==rigs[1].component.data);
  captured_generation=generation;++captures;
}
int main(void) {
  setup();assert(fixdemo_trophy_props_begin(7));create(0);create(1);
  update(0);assert(!captures); /* Cup is never a podium emitter. */
  update(1);assert(captures==1);
  assert(fixdemo_spark_owner_generation(&fixdemo_trophy_prop_lifecycle,7)==captured_generation);
  fixdemo_trophy_prop_destroy(rigs[1].owner.data);
  assert(!fixdemo_spark_owner_generation(&fixdemo_trophy_prop_lifecycle,7));
  /* Cached UE/component bytes remain valid; retired PES ownership forbids capture. */
  fixdemo_trophy_prop_ue_callback(rigs[1].ue.data,(void*)(uintptr_t)77);
  assert(captures==1);fixdemo_trophy_props_cancel(7);
  return 0;
}
''')


def test_world_bridge_uses_atomic_playing_and_current_podium_metadata(tmp_path):
    hooks = (ROOT / 'source/ue4_hooks.c').read_text()
    active = function(hooks, 'fixdemo_trophy_sparks_active_epoch')
    update = function(hooks, 'fixdemo_trophy_sparks_update_world')
    run_c(tmp_path, r'''
#include <stdint.h>
#include <assert.h>
#include "fixdemo_spark_owner.h"
static FixDemoPropLifecycle fixdemo_trophy_prop_lifecycle;
static uint64_t fixdemo_trophy_ui_token,fixdemo_trophy_ui_playing_token,fixdemo_trophy_ui_skip;
static struct { uint64_t epoch; } trophy_sparks;
static unsigned calls;
static uint64_t got_active,got_playing,got_generation;
static int got_skip;
static void fixdemo_trophy_sparks_tick(void *w,float seconds,uint64_t active,
    uint64_t playing,uint64_t generation,int skip) {
  assert(w==(void*)(uintptr_t)77 && seconds==.02f);++calls;
  got_active=active;got_playing=playing;got_generation=generation;got_skip=skip;
}
''' + active + update + r'''
int main(void) {
  void *world=(void*)(uintptr_t)77;
  fixdemo_trophy_sparks_update_world(world,.02f);assert(!calls); /* Ordinary idle tick. */
  trophy_sparks.epoch=7;fixdemo_trophy_ui_token=7;
  FixDemoPropLifecycle *s=&fixdemo_trophy_prop_lifecycle;
  s->epoch=7;s->ready_mask=2;
  s->slots[1]=(FixDemoPropTicket){.epoch=7,.generation=42,.owner=1,.demo=2,
      .model=3,.ue=4,.key=1,.kind=2,.ready=1};
  fixdemo_trophy_sparks_update_world(world,.02f);
  assert(calls==1 && got_active==7 && !got_playing && got_generation==42 && !got_skip);
  fixdemo_trophy_ui_playing_token=7;
  fixdemo_trophy_sparks_update_world(world,.02f);assert(got_playing==7);
  fixdemo_trophy_ui_playing_token=8;
  fixdemo_trophy_sparks_update_world(world,.02f);assert(!got_playing);
  fixdemo_trophy_ui_skip=7;
  fixdemo_trophy_sparks_update_world(world,.02f);assert(got_skip);
  s->slots[1].owner=0;
  fixdemo_trophy_sparks_update_world(world,.02f);assert(!got_generation);
  fixdemo_trophy_ui_token=0;
  fixdemo_trophy_sparks_update_world(world,.02f);assert(!got_active && !got_playing && !got_skip);
  return 0;
}
''')


def test_world_tick_services_ceremony_even_when_weather_returns_early(tmp_path):
    fixture = (ROOT / 'tests/test_weather_scene.c').read_text()
    fixture = fixture.replace('int main(void){', 'static int original_weather_main(void){', 1)
    # The C entry point's implicit success return needs to be explicit when
    # reusing its body as an ordinary helper function.
    fixture = fixture.rsplit('}', 1)[0] + 'return 0;\n}\n'
    run_c(tmp_path, r'''
#include <stdint.h>
#define PESNX_TROPHY_SPARKS_RUNTIME 1
static void fixdemo_trophy_sparks_reset(void);
static void fixdemo_trophy_sparks_update_world(void*,float);
''' + fixture + r'''
static unsigned spark_ticks,spark_resets;
static void fixdemo_trophy_sparks_reset(void) { ++spark_resets; }
static void fixdemo_trophy_sparks_update_world(void *w,float seconds) {
  (void)w;(void)seconds;
  assert(tick_count==(int)++spark_ticks); /* Native tick has already returned. */
}
int main(void) {
  assert(!original_weather_main());
  unsigned before=spark_ticks;weather_scene_active=0;
  weather_scene_tick(world_obj,0,.02f);
  assert(spark_ticks==before+1 && spark_resets>0);
  return 0;
}
''')

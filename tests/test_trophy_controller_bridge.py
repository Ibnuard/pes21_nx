"""Run the actual input/surface bridge without a native scene or controller."""
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from test_gameplan_editor import function, struct


ROOT = Path(__file__).resolve().parents[1]


def test_ceremony_skip_is_isolated_and_restores_native_input(tmp_path):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler required")
    hooks = (ROOT / "source/ue4_hooks.c").read_text(encoding="utf-8")
    header = (ROOT / "source/ue4_hooks.h").read_text(encoding="utf-8")
    defines = "\n".join(line for line in header.splitlines()
                        if re.match(r"#define PES_(SETPLAY_|CONTROLLER_SURFACE_)", line))
    code = r'''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <assert.h>
static int trophy, accepted_skip, native_demo, native_replay;
static unsigned skip_calls, native_owner_queries;
static uint64_t now = 1000000;
static uint64_t match_demo_skip_request_tick, match_controller_surface_word;
static uintptr_t match_demo_skip_request_owner;
static uint64_t match_goal_demo_seen_tick, match_goal_demo_pad_seen_tick;
static uint64_t match_goal_button_visible_tick, match_button_setplay_seen_tick;
static uint64_t match_native_free_kick_seen_tick, match_replay_feedback_tick;
static uintptr_t match_button_setplay_owner;
static uint32_t match_goal_demo_owner_known, match_goal_demo_player_goal;
static uint32_t match_goal_button_visible, match_goal_demo_helper_consumed;
static uint32_t match_button_setplay_visible, match_button_setplay_mask;
static uint32_t match_native_setplay_context, match_replay_feedback_value;
static uint64_t armGetSystemTick(void) { return now; }
static uint64_t armTicksToNs(uint64_t value) { return value; }
static int fixdemo_trophy_ui_active(void) { return trophy; }
static int fixdemo_trophy_request_skip(void) { ++skip_calls; return accepted_skip; }
static int match_native_demo_active_at(uint64_t tick, uintptr_t *owner) {
  assert(tick == now);
  if (owner) { ++native_owner_queries; *owner = native_demo ? 42 : 0; }
  return native_demo;
}
static int match_native_replay_active_at(uint64_t tick) {
  assert(tick == now); return native_replay;
}
static uint32_t match_button_setplay_context_from_mask(uint32_t mask) {
  (void)mask; return 0;
}
static uint32_t match_button_setplay_options_from_mask(uint32_t mask) {
  (void)mask; return 0;
}
''' + defines + "\n" + struct(header, "PesControllerSnapshot") + "\n"
    code += "\n".join(function(hooks[re.search(
        r"^(?:void|int) " + name + r"\(", hooks, re.M).start():], name) for name in (
        "pes_controller_demo_skip_request", "pes_controller_cinematic_skip_active",
        "pes_controller_surface_snapshot", "pes_controller_surface_cached_snapshot"))
    code += r'''
int main(void) {
  PesControllerSnapshot snapshot, cached;
  pes_controller_surface_snapshot(NULL);
  pes_controller_surface_snapshot(&snapshot);
  assert(snapshot.surface == PES_CONTROLLER_SURFACE_NONE);
  assert(!pes_controller_cinematic_skip_active());
  pes_controller_demo_skip_request();
  assert(skip_calls == 1 && native_owner_queries == 1);
  assert(!match_demo_skip_request_owner && !match_demo_skip_request_tick);

  native_demo = 1;
  assert(pes_controller_cinematic_skip_active());
  pes_controller_demo_skip_request();
  assert(match_demo_skip_request_owner == 42 && match_demo_skip_request_tick == now);
  match_demo_skip_request_owner = match_demo_skip_request_tick = 0;

  /* The canary owns the frame even while earlier replay/goal heartbeats live. */
  trophy = accepted_skip = native_replay = 1;
  match_goal_demo_seen_tick = match_goal_demo_pad_seen_tick = now;
  match_goal_demo_owner_known = match_goal_demo_player_goal = 1;
  match_goal_button_visible_tick = now; match_goal_button_visible = 1;
  unsigned before = native_owner_queries;
  pes_controller_surface_snapshot(&snapshot);
  assert(snapshot.surface == PES_CONTROLLER_SURFACE_CINEMATIC);
  assert(!snapshot.goal_player && !snapshot.goal_helper_visible);
  pes_controller_surface_cached_snapshot(&cached);
  assert(cached.surface == snapshot.surface && cached.generation == snapshot.generation);
  pes_controller_demo_skip_request();
  assert(native_owner_queries == before);
  assert(!match_demo_skip_request_owner && !match_demo_skip_request_tick);

  /* Releasing the gate restores the existing exact native surface priorities. */
  trophy = accepted_skip = 0;
  uint32_t generation = snapshot.generation;
  pes_controller_surface_snapshot(&snapshot);
  assert(snapshot.surface == PES_CONTROLLER_SURFACE_GOAL_DEMO);
  assert(snapshot.goal_player && snapshot.goal_helper_visible);
  assert(snapshot.generation == generation + 1);
  match_goal_demo_seen_tick = match_goal_demo_pad_seen_tick = 0;
  pes_controller_surface_snapshot(&snapshot);
  assert(snapshot.surface == PES_CONTROLLER_SURFACE_REPLAY);
  native_replay = 0;
  pes_controller_surface_snapshot(&snapshot);
  assert(snapshot.surface == PES_CONTROLLER_SURFACE_CINEMATIC);
  pes_controller_demo_skip_request();
  assert(native_owner_queries == before + 1 && match_demo_skip_request_owner == 42);
  native_demo = 0;
  pes_controller_surface_snapshot(&snapshot);
  assert(snapshot.surface == PES_CONTROLLER_SURFACE_NONE);
  assert(!pes_controller_cinematic_skip_active());
  return 0;
}
'''
    source = tmp_path / "trophy-input.c"
    source.write_text(code, encoding="utf-8")
    executable = tmp_path / "trophy-input.exe"
    built = subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            str(source), "-o", str(executable)],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
    assert ran.returncode == 0, ran.stdout + ran.stderr

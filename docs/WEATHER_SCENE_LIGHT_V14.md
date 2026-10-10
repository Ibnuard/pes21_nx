# Weather scene lighting v14 — 11 October 2026

The user accepted v13 pitch remnants but reported the camera shade disappearing
at ball-out and other events, disliked the cartoon lens beads, and explicitly
requested keeping the white snow remnants on the pitch.

## Device evidence from v13

The supplied scene log records Konami Stadium, the optional referee enabled,
Rainy Summer followed by Rainy Winter, and a 1024x576 viewport. It contains no
Fine baseline. Buffered presentation interval samples give:

| Selection | Samples / intervals | Weighted mean | Approx. presentations/s | Worst | Above 20 ms |
|---|---:|---:|---:|---:|---:|
| Rainy Summer | 2 / 4,529 | 18.301 ms | 54.64 | 70.490 ms | 642 |
| Rainy Winter | 6 / 13,976 | 19.284 ms | 51.86 | 70.340 ms | 3,803 |

These are elapsed intervals between live overlay callbacks, not GPU timings or
native simulation FPS. They substantiate uneven presentation but do not isolate
the cause or establish a causal performance difference between seasons. Different
matches/cameras and the referee are uncontrolled variables. Paused time is
excluded. Raw logs stay local.

The v13 camera draw required live HUD, replay or goal-demo status, with additional
frontend exclusions. A ball-out scene could leave all these gates. This explains
a code path for the reported disappearing shade; it is not proof that every
reported blink had that cause.

## Implementation

- Remove the camera mask include, texture storage/upload, fullscreen quad and
  draw from the active overlay. Rain and snow particles remain uninstalled.
- Use the existing cached match climate uniform in audited scene material
  lighting. No camera coordinates, frame counter, HUD state or event state
  controls the new lighting coefficients.
- Rainy Summer scales direct and ambient light by 0.84 relative to the existing
  Cloudy daylight coefficients. Rainy Winter reduces cloud attenuation and keeps
  the cool seasonal tint, bringing unshadowed light near Fine brightness.
- Night Rain uses bounded dark/cool scaling, including the separately audited
  night pitch output. Fine and Cloudy night baselines remain unchanged.
- Keep world-space patch coordinates and snow coverage. Winter's underlying wet
  darkening is reduced so its grass does not stay as dark as Summer rain. Painted
  lines receive no patch mask. Native wet ball-surface setup remains active.
- Keep buffered frame-interval logging, now marked v14; no per-frame log writes.

This is material lighting, not a UV-coordinate change or a new global UE light
actor. Coverage is limited to the existing audited pitch, character and perimeter
shaders. Unknown/custom materials and sky are not newly rewritten. There is no
new draw, texture, particle, world actor, framebuffer observer or depth/alpha
change. Light multipliers add uniform-dependent shader arithmetic; zero cost or
stable 60 FPS is not claimed. Referee code is unchanged.

`tools/pitch_weather_preview.py` uses the shipped functions with a synthetic
65% direct / 35% ambient mixture. It illustrates colour/patch differences, not
the actual game's lighting balance or a Switch capture.

## Verification and device acceptance

Host checks cover light ordering, cool Winter tint, repeated Rain-to-Fine resets,
accepted day/night baselines, world-space snow coverage, paint preservation,
cached uniforms, and exact reversal of native shader edits. GLSL compilation
checks both clip-space configurations against the available owned fixtures.
Build/package verification results are stored with the local release.

The production build and icon verification passed; all 2,824 shader compilations
(706 variants, native/candidate in two clip spaces) passed. The focused suite
initially had 16 passes plus a host test-adapter compilation failure; adding
vector addition to that adapter resolved it, with both lighting tests passing
on recheck. Supplemental tests reported 15 passes / 91 subtests, but the optional
old-v12 Unicorn trampoline test emitted a Windows access-violation diagnostic
despite pytest returning success. That emulator result is not treated as clean
verification. The public-tree audit passed. No hardware validation is implied.

Replace only `pes21_nx.nro`; retain the installed assets and Anfield PAK. No
reforward is needed. Check Fine, Cloudy, Rainy Summer and Rainy Winter through
ball-out, corner, goal, replay and the next match. Collect matched Fine/Rainy
20–30 second fast-pass runs followed by Pause, with the same camera/stadium and
referee state. New on-device colour, persistence and frame-time acceptance is
still required.

# Stadium V2: held framing and smooth zoom

## Current candidate: screen margin hold, v41

The user rejected continuous ball-centred tracking on the device: fast passes
made the camera feel jerky even apart from measured frame-time variation.
The new policy holds the current composition while the native-framed ball
target stays comfortably visible. Horizontal/vertical motion starts at 60%/52%
of the viewport half span, then settles at 38%/32%. Hysteresis prevents tiny
passes from repeatedly starting and stopping a pan. These are initial tuning
values, not a claim of hardware acceptance.

Margins are projected through the previous final native pose and vertical FOV
at the Switch's 16:9 aspect. They therefore scale with distance and zoom.
Native eye placement, pitch bounds, target-height shaping and optical demand
still supply the shot. Panning uses a convex 340 ms response, smoothly reaching
120 ms near an edge. It never predicts the receiver or carries velocity after
a reversal. Lens expansion takes 300 ms and contraction 950 ms, with a small
deadband and at most 18% extra FOV for a fast crossing. The lens input comes
from the native calculation before interpolation to avoid feeding the composed
output back into its own demand. Native transition state still updates once.

The same guarded target/trace/interpolation boundaries and lifecycle exclusions
remain in use. No per-frame registry lookup, allocation, file write or GPU wait
is added. Other camera choices remain separately available. Bootstrap, invalid
views, pause/time discontinuities, session and preset changes are handled by
the existing bounded scope and reset rules.

Host simulations cover short passes that leave the pose completely stationary,
40 m/s crossings at 30/60/120 Hz, off-centre settling, smooth bounded lens
changes, native geometry, ABI/register preservation and unrelated-camera
isolation. Those are policy/ABI checks, not a Switch camera recording.

Build and device comparison details are in
[Match pacing baseline v41](MATCH_PACING_BASELINE_V41.md). The artifact folder
is `local-debug/stadium-v2-frame-hold-v41/`. Compare the ordinary NRO first;
use its separately built diagnostic variant for performance measurements.

## Previous implementation (superseded motion and optical policy)

`STADIUM-V2` is an opt-in camera beside the unchanged native `STADIUM`,
`PITCH SIDE` and `FOOTBALLNX CAM` choices. The previous revision followed the
user's latest direction: **use native Stadium framing, replace its tracking
motion**. It supersedes both rejected authored fixed-tripod experiments.

## What remains native

The original `InplayCamera::Update` runs once. Its Stadium preset converter,
`ShotBroadcast` tables and `ShotBroadcastBallActive` still own:

- D2/H3/P6 settings, target-height shaping and native projection adjustments;
- eye height, rail distance, X-panning ratio and resulting vertical angle;
- dynamic field of view, optical zoom limits, zoom velocity and shot state;
- pitch-edge framing constraints and `ShotTVChange` table selection;
- entry-transition counters and interpolated optical lens.

There is no wrapper-authored FOV, tripod position, look-ray length or tilt
offset. In particular the eye is **not pinned at X=0**: native Stadium moves
eye X with its target. At the native D2/H3 centre pose, eye Y/Z are 21/70 and
target Y is 0.5; off centre the native X-pan ratio is 0.39. These are observations
of native execution, not new wrapper tuning constants.

Native optical behavior remains native, including the cap supplied by its
target-acquisition helper and contextual shot transitions. The change removes
prediction from **look/eye tracking**; it does not claim to remove every
contextual or anticipatory native zoom decision.

## Changed motion boundaries

1. A checked mid-function hook at `ShotBroadcastBallActive + 0x6d0` replaces
   the acquired/predicted target with the current `BallInfo::GetTrans` vector
   the game has already sampled. This is after player/target overrides, before
   native height, zoom and projection calculations. Only three floats are
   copied; there is no extra registry query or retained ball pointer.
2. At the native broadcast trace boundary, the native-framed target is clamped
   with the native limits and followed with an 80 ms exponential response.
   This convex step has no velocity extrapolation, future-pass vector or
   overshoot. Stationary balls cannot start a predicted pan; reversals do not
   carry old momentum. Smooth following necessarily has a small bounded delay.
3. The old-look input is seeded with that same clamped result. This neutralizes
   the subsequent native `54/GetFSec` positional stage, which can extrapolate
   rather than damp at the owned ELF's default `GetFSec=27`.
4. The original `UpdateInterpolate` still runs. Only its positional blend is
   bypassed after a successful V2 trace; its native FOV output and transition
   counters are retained. `ShotTVChange` is not patched.

The target trampoline preserves volatile integer registers, all 32 SIMD
registers, NZCV and FPSR, then replays the displaced native loads with relocated
addresses. All three patch sites have exact instruction guards. Original
native trace/interpolation functions are called for non-V2 or invalid scopes.

## Scope and lifecycle

The bounded thread-local scope exists only during the wrapped native Update,
with explicit V2 selection, tmpdb type 12, live camera ID 6 and the existing
live HUD gate. Player-follow parameters, pause, replay, demos, results, loading
and stale in-play state leave native behavior intact. The scope is always
cleared on return. Owner, match session and preset revision changes reset the
filter. Invalid samples fall back to native tracing; time reversals and gaps
over 250 ms restart without integrating pause time.

No per-frame allocation, disk I/O, gameplay/ball mutation or PAK modification
is introduced. Native Stadium/Pitch Side and FootballNX remain independently
selectable. V2 keeps the native fixed preset values; unavailable native sliders
are not invented. Selection remains remembered within the app session.

## Evidence and verification

Owned compatible Mobile ELF SHA-256:
`a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`.

REA native pseudocode was unavailable on this host. Focused local Capstone
inspection and Unicorn execution were used instead; they are **not REA
decompilation or observed Switch gameplay**. Tests contain only project-authored
code and locators; proprietary inputs remain optional and ignored.

- C motion tests: stationary positions, moving and reversing targets, no lead
  or overshoot, bounded lag, 30/60/120 Hz, duplicate timestamps, pause/reset,
  invalid samples and changing native bounds.
- Actual C adapter tests: native-choice isolation, actual-ball injection,
  complete trace argument forwarding, native lens/other-field preservation,
  scope cleanup and session/preset changes.
- Actual AArch64 trampoline test: hostile helper clobbers all volatile registers
  and SIMD state; exact argument/SP, flag restoration and displaced replay
  are verified, including optional comparison with the owned native bytes.
- Optional native oracle: actual settings normalization, Stadium parameter
  calculation, target height, neutral optical lens and 15 off-centre eye writes.
  Native preset conversion and Pitch Side routing have separate oracle tests.

```powershell
python -m pytest tests/test_stadium_v2_camera.py tests/test_stadium_v2_native.py tests/test_stadium_v2_hook.py tests/test_camera_choice_policy.py tests/test_stadium_camera_anticipation.py tests/test_stadium_diagnostics.py tests/test_settings_exit_regression.py tests/test_general_settings_without_stamina.py tests/test_footballnx_preset.py tests/test_pause_v20.py tests/test_result_flow.py tests/test_single_joy_camera.py tests/test_weather_camera.py tests/test_near_camera_trace.py -q
python -m unittest discover -s tests -p test_fl26_native_cameras.py -v
```

Candidate output: `local-debug/stadium-v2-native-motion/build/pes21_nx.nro`.
It uses runtime pair `e861c583ec78e9ae` and the 53,248-byte dummy OBB requirement.
Only the NRO changes on that compatible runtime; do not replace PAK/CPK/OBB or
the parallel real-face assets.

Verification for this revision: **58 focused tests and 2 subtests pass**, plus
both separate native-preset oracle tests. The production devkitA64 build passes
with diagnostics/performance tracing disabled; existing unrelated unused-code
warnings remain. NRO/ELF executable segments, all eight compiled camera choices,
the three new motion-boundary symbols, runtime identity and launcher icon are
verified. Public-tree audit passes (996 files at verification).

NRO size: 83,841,951 bytes. SHA-256:
`5e01d5d401bd0eb1015c25115a77172711ddd6503ca79206f4f69db9910c6a14`.

## Superseded framing experiments

The first fixed-tripod implementation incorrectly interpreted UI distance 2 as
0.2 instead of the native `1-D/10 = 0.8`, and used an excessively wide authored
lens. The second corrected the centre anchor and calibrated a 19-degree lens
against screenshots, but still reconstructed framing. The user rejected both.
Those authored lens/anchor/tilt policies have now been removed, not retuned.

## Device acceptance remains required

Compare native `STADIUM` and `STADIUM-V2` in the same stadium/phase, including
midfield, each touchline, both goal ends, a held keeper ball, fast diagonal
passes, receiving/reversing play and aerial balls. Then verify pause/resume,
goal/replay, goal kick, free kick, rematch and switching back to native cameras.
Also check low-FPS/hitch recovery: the existing 80 ms HUD freshness gate can
temporarily fall back to native behavior and reset the filter on a long stall.

Native code ownership and host regression results do not establish on-device
visual equivalence or subjective smoothness. The complete live engine pipeline,
occlusion and gameplay-gate transitions still need Switch validation. This
camera candidate does not diagnose or claim to fix unrelated FPS degradation.

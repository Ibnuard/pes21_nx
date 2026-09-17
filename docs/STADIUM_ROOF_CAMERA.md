# Stadium inventory, roof option and camera candidate

Based on checkpoint `checkpoint-high-shadow-pitch-v19`.

## Hardware checkpoint: Roof ON/OFF accepted (2026-09-18)

User explicitly confirmed both states work with the V6 NRO below. Local Git
tag: `checkpoint-roof-shadow-toggle-v6`. This snapshots the integrated V6
source, tests and profiling, but acceptance is **only for the roof toggle**.
FootballNX framing is not accepted and Day performance remains unresolved.
The accepted pitch PAK is unchanged. No additional runtime tuning or push is
part of this checkpoint. The 54 focused tests and 7 subtests passed again.

### Supplied V6 performance capture

Input fingerprint (log remains local): SHA-256
`a597c86d5f51ede95226297ec39c7e2f3f5d0cbd2b4cb7e7fb0f7c449513fcbe`.
All 100 STADIUMPERF records are Day; there are no Night samples. Match 1 has
Roof OFF; match 2 has Roof ON. The following aggregation selects complete
five-second windows with match > 0, paused=0 and camera_recent=1. FPS is total
frames / total recorded time, not an arithmetic mean of window FPS. The
camera heartbeat is a live-camera proxy, not an authoritative gameplay-phase
label. Different matches/ball positions are not a controlled roof-only A/B.

| Match / camera | Roof | Windows | FPS | Frame ms | Draws/frame | Depth draws/frame | Roof candidates blocked/seen |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 / Stadium | OFF | 11 | 32.59 | 30.68 | 300.2 | 135.0 | 5388/5388 |
| 1 / FootballNX | OFF | 6 | 38.47 | 26.00 | 280.9 | 136.1 | 3468/3468 |
| 2 / Stadium | ON | 18 | 32.13 | 31.13 | 293.9 | 140.0 | 0/8691 |
| 2 / ordinary Dynamic Wide | ON | 11 | 32.09 | 31.17 | 287.4 | 146.0 | 0/5310 |

All groups retain a maximum observed depth-only viewport of 2040x2040.
Roof OFF removes the tracked roof casters, not the whole daytime shadow/depth
pipeline. Depth submissions remain about 45-51% of intercepted draw counts;
this is **not** their percentage of GPU time. Driver draw-call CPU wall time
is 3.09-3.41 ms/frame and measured swap scope 0.25-0.27 ms/frame. Neither is a
GPU timer, and the remaining frame time cannot be attributed to GPU solely
by subtraction. Summed generic waits include concurrent threads and likewise
cannot be added up as a main-thread critical path.

The log's quality=1 and fps_mode=0 come from cached menu fields (nominally
Standard/60). They default to those values and refresh when video settings
are opened/applied, not directly from the renderer. This capture alone does
not prove the native graphics quality or active frame cap. For another
capture open Video Settings first, verify the selection, and record Day OFF,
Day ON and Night with the same camera, teams, quality and FPS selection in
one run. Copy perf.log before restarting. The match-2 type-5 samples have
footballnx=0, so they must not be compared as another FootballNX sample.

Day-only shadow/depth work is a concrete next investigation target, not a
confirmed complete explanation of the Day/Night difference. Isolate shadow
generation/resolution and sampling separately before selecting an optimization;
do not remove player shadows or change the accepted pitch implicitly.

### FootballNX POV review

The supplied screenshots are different field positions, not matched camera
poses, but code confirms the underlying mismatch: V6 gives ShotHorizontal
the Stadium 2/3/6 parameter values, then applies a fixed X/Z yaw around the
native look target. It preserves Dynamic Wide's vertical eye offset and
planar radius; equal slider values do not yield the Broadcast/Stadium lens
and eye/look geometry. The yaw-only helper cannot create a lower tribune POV.

A follow-up can retain Dynamic Wide's target tracking while mapping the
eye-to-target elevation, setback and lens to a fixed Stadium-like composition.
Measure the native Stadium pose first; adjust elevation and setback together
to retain field coverage, avoid accumulated transforms, and test both
touchlines, kickoff, pause/resume and camera switches. Do not translate the
entire eye/look pair toward the ball (the rejected V4 clipping behavior), or
reintroduce Stadium's prediction into the Wide tracking path. No POV code
change or new build has been made in this acceptance/analysis checkpoint.

## V6: FootballNX preset, restored native motion and profiling

User confirmed V5 removes the roof shadow. Its camera behavior was rejected:
the supplied 36-second SysDVR capture shows abrupt horizontal stops around
15 and 31 seconds, followed by a camera held toward the attacking half as the
ball travels left. Native consumer inspection explains an actual V5 error:
GetFutureMoveVec is also a camera-speed cap selected by BallTouchKind and field
region. Zeroing it can stop horizontal movement; it is not merely removing
look-ahead. V6 removes that hook completely, retaining native acceleration,
deceleration and shared tracing. The X-only soft target-position limit stays;
no final Stadium eye/look translation or shared quantization patch is added.

### FootballNX and roof controls

- The old Dynamic Wide Custom option is now **FOOTBALLNX CAM**. It retains
  native Dynamic Wide tmpdb type 5, with fixed original Stadium Distance 2,
  Height 3 and Angle 6 in all three registry copies. These are the original
  preset values, not the wrapper's Height 6 override for Stadium/Broadcast.
- Only Camera Type is offered for FootballNX. No editable custom sliders;
  existing Stadium Custom values are not read or overwritten. The fixed
  angle uses the existing Dynamic-Wide-only rotation about its native target.
  Its effective projection still follows Dynamic Wide: this is not a promise
  of pixel-identical Stadium framing at every ball position.
- Hub > Stadium > Day exposes **Enable Roof Shadow** again. Default OFF;
  preference lasts for the process, survives new matches and Day/Night
  switches, but is not saved across app restarts. Night hides the row and
  keeps native casting. Both exact native roof-caster filtering and the
  material uniform read the same preference. No in-match roof setting.
- Accepted High compatibility and v19 pitch PAK remain untouched.

### Focused performance build

Candidate: `local-debug/footballnx-camera-perf-v6/pes21_nx.nro`.
Built with `-PerfTrace`, **without** `-Diagnostics`: release-style rendering
with opt-in counters, no DEBUG_LOG overlay, shader dumps or diagnostic pixel
readbacks. Profiling is not overhead-free and does not constitute a fix for
Day FPS.

Build completed: 51,876,045 bytes; SHA-256
`8e1f3f0aa77e85f947d333312dab617204a47d7806ff7943d938c17044c30c44`.
Focused verification: 54 tests and 7 subtests passed, including the native
camera ABI audit, fixed preset, roof filtering, performance-window isolation
and settings regressions. The public-tree audit passed (427 files checked),
as did `git diff --check`. Binary inspection confirms the new preset and
profiling strings and removal of the future-vector wrapper. This is not a
full-suite or on-device acceptance. Replace the NRO only; retain the accepted
pitch PAK. No commit/push requested for V6.

Collect **`switch/pes21_nx/perf.log`**, not a stale debug.log. It is overwritten
on the next launch and flushed every five seconds. `[STADIUMPERF]` records
per-state windows, match number, Day/Roof, native camera type plus FootballNX
flag, quality, FPS-mode setting, pause and camera heartbeat, swap cadence,
mean/max frame time, histogram p95 upper bound, draw-call CPU wall time,
submission counts, depth-only draws/viewport and roof-suppression counts.
`p95_upper_ms=0` means above 200 ms (not zero latency).

Depth-only target classification reuses existing compositor attachment
queries; it includes depth passes other than roof shadows. Draw timing is
CPU-side driver-call duration, not GPU execution time. Swap duration can
include presentation waits, GPU backlog and the existing overlay/compositor;
do not label it pure GPU time. `[PESPERF]` additionally lists wait/sleep sites.
No extra GL synchronization or scene readback is introduced by profiling.
Transition frames are discarded, and windows split on setting/state changes.
Counts cover intercepted engine draws, not direct wrapper composition draws.

Hardware procedure (same build, quality, FPS setting, teams and camera):

1. Play Day / Roof OFF for 45-60 seconds, then Day / Roof ON, then Night in
   the same application run. Avoid judging the initial shader/loading frames.
2. Test native Stadium and FootballNX separately: midfield receive/stop,
   forward pass near goal, defensive return, both flanks and near touchline.
3. Pause > General Settings > Back > resume; switch camera away and back.
   FootballNX remains fixed; Stadium Custom sliders retain their values.
4. Copy perf.log before relaunch. ON restoration, camera smoothness and Day
   performance still require hardware acceptance. V5 roof OFF alone has been
   accepted; do not conflate that with V6 being fully tested on device.

## V5: forced roof OFF and native camera anti-anticipation

V4 feedback rejected the rigid ball lock and a near-touchline camera entering
stadium geometry. The supplied log confirms final-eye Z increasing from its
native 70 to about 80 during that movement. V4's final-pose translation is
removed, not merely weakened.

The same log registers all three roof proxies (main roof plus two glass
instances), and the native shadow-gather hook runs. However, the session is
`day=1 roof=1`, every filter sample has `disabled=0`, and the final counter is
`suppressed=0`. There is no OFF sample in that capture. This does not prove
that an active OFF filter failed; it proves no roof subjects were excluded
in the supplied run. At the user's request, V5 forces the policy OFF from
startup. The hub toggle is temporarily removed instead of offering an ON
choice that the renderer ignores. Night still uses the native caster path.

### Camera changes

- Preserve the complete native final look/eye transform. No final-pose
  tracking, camera-eye translation, or extra temporal smoother.
- Keep the native GetBallPositionBroadcast calculation, then softly bound
  excessive **X-only** group-target bias before native tracing: six units
  untouched, residual gradually limited to ten. This is a composition band,
  not a 100% ball lock. Y and Z, including near/far-touchline composition,
  remain native, as does its zoom output.
- Native ShotBroadcastBallActive passes GetFutureMoveVec to
  gcViewTraceBroadcast. V5 zeros only that vector's X/Z prediction at that
  exact call site, after the movement readiness gate. Vertical prediction
  remains native. The shared PLT wrapper checks the native return address,
  same-update sample, readiness, and fixed-preset selection. All other
  physics/AI/camera callers receive the original result. No BallInfo or
  TeamAI registry is modified.
- Scope remains fixed Stadium/Live Broadcast (tmpdb 12/7); custom presets,
  Dynamic Wide Custom angle, native zoom/height/angle/clamps/spring and
  kickoff/pause rearming remain. The previously requested fixed height 6
  adjustment remains as well.

### Roof/performance scope

The exact-asset native caster filter is now unconditionally enabled for Day.
Roof geometry stays visible; no global CSM sampler disable is used, so player
and goal shadows are not deliberately removed. The existing OFF material
mask route also stays active. The accepted v19 pitch PAK is untouched.
The remaining CSM/player and day-lighting costs still exist: night-equivalent
FPS is **not** guaranteed, and the visual absence of every roof contribution
still requires hardware confirmation.

Candidate: `local-debug/roof-camera-prod-v5/pes21_nx.nro`.
Production: Diagnostics OFF and PerfTrace OFF, two build jobs. Replace NRO
only; do not copy the stale `dist/` NRO or replace the accepted PAK.
Build completed: 51,871,949 bytes; SHA-256
`aae868bde2a603ec0b547670fb5034e595320c0516759c3af5dba42ee3cb0117`.
All 38 focused tests passed, including native ELF call-site/ABI checks,
same-update gating, unchanged final camera pose, horizontal bias limits,
forced roof policy and settings-exit regressions. Production AArch64 output
was checked for preserving the native caller address and vector-return ABI.
`git diff --check` and the public-tree audit passed (422 tracked files).
This is not a full-suite or on-device visual/performance acceptance.

Hardware checklist: High + Day + fixed Stadium, near touchline with the ball
low on screen, neutral possession on either flank, counterattack, repeated
back/forward passes, then pause > General Settings > Back > resume. Confirm
roof silhouette absent and player shadows retained, with native zoom and
smooth camera motion. Compare Night using the **same production build**;
diagnostic-v4 vs production-v5 is not a controlled roof-only performance test.
Hardware acceptance pending. No commit/push requested for V5.

## V4 caster filtering and final camera correction

V3 hardware run: Day > Roof OFF > lateral passes > pause > General Settings
> Back > resume. Its pitch program reported `day=1 enabled=0 desired=1
actual=1` before and after resume. The roof option reached the shader; the
material `ps1` override was not the directional depth-shadow caster path.
The shadow sampler was bound to the depth-only shadow-map attachment.
No new shader compile/link failures were reported in that capture.

V3 also showed the early broadcast target correction being overwritten by
native reprojection/tracing. One resume sample had ball X/Z about
`21.77/-12.75`, while final look-at was `22.18/2.07` despite the early target
already being within four units. V4 fixes the final output, not that
intermediate native target.

Changes:

- Register exact `st029_c` and `st029_c_glass` static-mesh proxy identities
  when their components create proxies. Audited mesh bounds locate them
  above the field (about 33-46 m and 42-45 m respectively). `frame` is near
  field level, and `st029_c_backface` spans below/above the stands: neither
  is assumed to be a roof-only mesh. No substring or height-based runtime
  heuristics are used.
- Day + Roof OFF skips those proxies at
  `FGatherShadowPrimitivesPacket::FilterPrimitiveForShadows`, before they
  enter directional shadow subject arrays. Hooking `IsShadowCast` alone
  would not suffice: this path inlines its primitive-flag checks. Both audited
  AnyThreadTask call sites dispatch through this filter. ON/Night
  delegates unchanged, even for already loaded proxies. This does not hide
  roof geometry or disable the global shadow sampler/player shadows.
- A bounded atomic registry, both virtual destructor hooks and non-roof
  address-reuse cleanup avoid retaining/dereferencing UObjects on render
  workers. Full registry/unknown assets fail open. Native FString storage
  is released with native FMemory::Free. Hook prologues and lifecycle vtable
  slots are verified against the compatible local ELF.
- Broadcast target hook now only captures a live ball sample. The final
  InplayCamera Update translates look-at and eye equally in X/Z, limiting
  residual to four units while preserving native eye/look direction, Y
  height, distance and lens. No extrapolated ball velocity is used. Only a
  ready sample produced within that same Update may apply; missing samples
  cannot reuse the last frame. Registry scope remains fixed tmpdb 7/12;
  custom cameras are excluded. Kickoff/pause movement rearming remains.
- Preserve v19 pitch PAK, High compatibility, accepted grading/pattern/grain,
  existing material uniform and height-6 fixed-preset adjustment.

Candidate: `local-debug/roof-camera-diag-v4/pes21_nx.nro` (51,957,965 bytes).
SHA-256: `52a410dddf375bd9066cfc3971c4cb027e5b2f06e746a4e85365e971f8ad0e3b`.
Diagnostics ON, PerfTrace OFF, 2 build jobs. Replace **NRO only**, keep v19
PAK and current runtime data; the NRO under `dist/` is not this candidate.
Do not use diagnostic builds as production performance benchmarks.

New log markers: `roof-caster-v4` creation/filter counts and
`camera-final-v4` same-frame ball/native/final/eye. Legacy v3 probe markers
remain for comparison. 31 focused tests passed, including lifecycle/address
reuse, ON/OFF/Night, optional native ELF ABI checks, and a final-camera
regression replaying captured resume coordinates. Build and public-tree
audit passed. **Hardware acceptance pending**, including whether any
additional/baked roof contribution remains; do not label OFF visually fixed
until the next capture confirms it.

Retest the same Day/OFF/passes/pause/General/Back/resume sequence. Then start
a Day/ON match in the same application run to verify restoration, and Night
to check the accepted pitch. Check player/contact shadows, rapid forward,
backward and lateral passes, fixed Broadcast/Stadium and custom presets.
Copy the new debug.log before relaunch. No commit/push for this candidate.

## V3 diagnostic after V2 hardware feedback

Hardware feedback: Roof OFF removes a white glow, but the roof silhouette
remains. The `ps1` override must no longer be described as a verified roof
mask bypass. Its exact contribution needs the captured shader/draw evidence.

Diagnostic candidate: `local-debug/roof-camera-diag-v3/pes21_nx.nro`.
Build completed: 51,957,965 bytes; SHA-256
`27abe6da67e9495aacda2634471fc21881964db9829f78c1e518843c24941509`.
Same camera tuning, pitch shader rewrite and v19 PAK as V2; new probes observe
state only. Diagnostics enabled, PerfTrace disabled, build uses 2 jobs.

- `roof-camera-diag-v3`: match-start Day/Roof state.
- `roof-diag`: linked fragment body fingerprints/features and bounded source
  samples (24 unique bodies / 1 MiB per render thread); source is captured at
  link before native detach and falls back to first draw. Draw samples show
  requested vs actual roof uniform, actual program/FBO, blending/depth and
  `ps0..ps7` sampler-to-texture mapping. Sample interval is 2 seconds per
  program, with immediate samples on state/context changes.
- `camera-diag`: live ball XYZ, original and corrected target XYZ, readiness,
  correction/result flags, zoom, planar error, camera ID, and final native
  look/eye vectors. Samples are 0.5 seconds apart, or on owner/state changes.
  Pause readiness resets and fixed-preset registry height/distance are logged.

All GL probes are diagnostic-only. No GPU texture readback, shader/uniform
write, or framebuffer mutation is added by these probes; active texture is
restored after sampler inspection. Existing generic Diagnostics overhead still
applies, so this build is not suitable for judging production performance.
Local logs include native shader text: do not commit or publish them.

Test with High + Day + Stadium: first Roof ON, play 30-60 seconds with lateral
and forward/back passes, pause > General Settings > resume, then return to the
hub and start another Day match with Roof OFF in the same application run.
Capture each visual result and copy `switch/pes21_nx/debug.log` before relaunch
(the log is overwritten each launch). Replace NRO only; keep the accepted PAK.
23 focused tests pass, including probe rate limits and render-state restoration.
Hardware capture is still pending; this is instrumentation, not a roof fix.

## V2 corrections after hardware rejection of V1

V1 roof OFF had no visible effect and its camera framing was rejected.
The target guard incorrectly treated native match Vector3 as Z-up. Native
ShotBroadcastBallActive bounds field coordinates at +0/+8; camera parameter
rotation likewise operates in X/Z. V2 corrects target and readiness movement
to X/Z while preserving target Y exactly. Tests cover lateral movement,
forward/back passes and vertical-only motion during the readiness gate.

V1 delivered roof uniforms only through the imported glUseProgram wrapper.
Dynamic EGL lookup of glUseProgram returned the driver function directly.
V2 also routes dynamic use/link/delete through the same wrappers, including
uniform cache invalidation. Tests exercise ON/OFF and Day/Night on an already
bound program, missing uniforms and reused program IDs. The route omission
is confirmed in code; its contribution to hardware roof visibility still
requires the new build to be tested.

Production candidate: `local-debug/roof-camera-prod-v2/pes21_nx.nro`.
Build succeeded without Diagnostics or PerfTrace (2 jobs), 51,867,853 bytes.
SHA-256: `fb2c566e031cc5b8d5242ff06143331cfb414398b807ec78e6236de9ef5e2972`.
20 focused tests and the public-tree audit passed.
Use v19 PAK; no asset changes in this correction.
No commit/push or new hardware acceptance yet.

## Runtime stadium inventory

Listing the supplied main PAK finds one complete gameplay stadium asset set,
`bg_lighting_AM1` / `st029` (Konami Stadium). It has day High/Low/no-stand and
night High/Low sublevels. The only other stadium-like ID, `st069`, occurs in
two demo `bg_360cap` maps and is not evidence of another playable venue.
The wrapper's Auto/Home/Away index currently changes only selection state;
it is not connected to a native stadium setter. Do not present those choices
as three available stadium models. Football Life PC conversion is unaudited.

## Hub roof option

Hub > Stadium has Stadium, Match Time, and (Day only) Enable Roof Shadow.
Default ON. The preference remains for the session when switching Day/Night;
it is not saved across application restarts. It is not an in-match setting.
The time label now reads the actual time-zone field, independent of COM-level
row remapping in General Settings.

The audited High day pitch shader gains a runtime uniform that makes its
`ps1` sample fully lit when OFF. ON uses the original sample. V2 feedback shows
this changes glow but does not remove the roof silhouette. The
dynamic shadow comparison remains intact to retain player/contact shadows.
Night shaders are not rewritten. The uniform is updated on program binding,
so cached programs work across matches and ON/OFF changes. The custom PAK
from v19 stays installed. Coverage of lower-quality materials, peripheral
pitch-side meshes and actual hardware visual behavior remains unverified.

## Camera

Broadcast-family live ball target uses a 2-unit deadzone and smooth 4-unit
maximum residual, replacing 14/18. The movement readiness and pause reset
guards remain. Native type 7 (Live Broadcast) and 12 (Stadium) get height 6
in all three registry copies; custom type 13 and Dynamic Wide Custom retain
their settings. Native zoom/interpolation and target height remain intact.

## Build and hardware acceptance

Original rejected candidate: `local-debug/roof-camera-prod-v1/pes21_nx.nro`.
Use the V2 candidate above, not V1. Replace NRO only; keep v19 PAK.
Test Day ON then OFF, including a second match in the same process, Night
with hidden roof option, kickoff and pause/resume, fast passes in both
directions, and fixed versus custom camera heights. Visual acceptance pending.

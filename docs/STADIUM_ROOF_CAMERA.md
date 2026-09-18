# Stadium inventory, roof option and camera candidate

Based on checkpoint `checkpoint-high-shadow-pitch-v19`.

## Day flat lighting and non-CSM coverage — 2026-09-18

Extends Day pitch shader modification to all 18 unique fingerprint variants (8 CSM
and 10 non-CSM). With Day CSM cascades capped at 0, non-CSM shaders write to 0
without directional shadow terms; their missing fingerprints previously allowed
raw roof shadowmap texture sampling and unpatched grazing highlights. Both CSM
and non-CSM Day bodies now zero the additive grazing highlight, route roof
disable to uniform 1.0 (eliminating the two-tone pitch split), and apply the 4%
grass luminance grade. Night shader bodies remain strictly rejected and unchanged.

## Post-checkpoint Day grass candidate — 2026-09-18

The hardware review of `checkpoint-nameplate-day-pitch-v2` confirms that the
previous 20% reduction did not remove the broad bright/dark patches or restore
visible grain. Inspection of the owned native Day shader shows that the roof
mask sample controls an *additive, view-dependent grazing highlight* (`v55`),
which is added after the diffuse, indirect, direct and skylight terms. With
roof OFF the sample is forced to white, making this component full strength.
This candidate replaces only that Day highlight color with zero in the same
eight fingerprint-allowlisted shaders. It retains the accepted 4% grass-only
luminance reduction, all base diffuse/grain/stripe inputs, native lighting,
player shadows and Night shader bodies. This is meant to expose the existing
pitch grain more like the supplied reference, without touching the expensive
shadow/cascade policy. Actual tone and FPS still require Switch review.

## Day pitch flattening candidate — 2026-09-18

Permanent roof OFF revealed the native Day grazing-highlight term as broad
bright/dark patches. The change remains restricted to the existing allowlist
of eight owned Day pitch fragment shaders: the highlight keeps its accepted
green hue at 80% amplitude and the grass-only luminance grade is reduced by
4%. Neutral/non-grass pixels, Night shaders, pitch textures, mowing pattern,
grain, player contact shadows and stadium geometry are untouched. The intent
is a more even, slightly darker Day pitch without restoring roof/CSM cost;
final appearance must be validated on Switch hardware.

## V12 candidate: native ball-target route, Stadium-scale view, simple Day shadows

2026-09-18. User **confirms stable 60 FPS in Day with V11**, but rejects its
eagle-eye FootballNX framing and odd player shadow appearance. Keep the accepted
zero Day cascades, permanent roof OFF/no toggle and custom pitch PAK. V12's
camera/shadow appearance and continued performance still need hardware testing.

### Native Stadium anticipation, not a final-pose correction

`GetBallPositionBroadcast` reads actual `BallInfo::GetTrans`, then its normal
composition path consults `TeamAIInfo`, possession/keeper/player records,
predicted receive coordinates and `BallInfoBase::GetFuture`. It also blends
separate target banks when possession changes. That is evidence of native
group/prediction-based framing, not proof of a mobile-exclusive feature named
"counter attack" or identification of every reported jerk from a screenshot.

The same calculator already has a **live-ball branch** at +0x244: copy the
unmodified GetTrans sample and return its native ball-only zoom factor 1.6.
V12 adds an instruction-checked branch selector at +0x150, before the normal
group/possession calculations. It chooses this existing branch only for selected
Stadium (tmpdb 12), live CAMERA_ID 6, within the same InplayCamera Update and
after the existing ball-motion readiness gate. Other camera/initial/set-piece
paths retain the original flag/phase decisions. No camera flag, world BallInfo
or TeamAI registry is overwritten. The hook preserves NZCV, live GPRs and SIMD
registers; both native continuations are validated against the compatible ELF.

The old 6-to-10-unit post-target soft clamp is **removed**, eliminating its
competing pull-back. Final eye/look remain native. Downstream native zoom,
field-bound composition, interpolation and acceleration/deceleration still
execute; the former group-driven zoom input is replaced by the native
ball-only branch's factor, so identical zoom behavior is not promised.
`GetFutureMoveVec` remains untouched: the tracer also uses it as a speed cap.
No shared trace/grid patch or additional temporal smoother is introduced.
Changing camera/pause/rematch resets scope/readiness as before.

### FootballNX and inexpensive shadows

FootballNX keeps Wide's interpolated target but moves back to the audited
Stadium Z=55 rail. Eye elevation is `18 + 0.025 * (55 - lookZ)` (about 18-21m,
close to native Stadium D2/H6's 17.68m), replacing V11's roughly 35-50m.
The continuous lens compensation uses 9.5-11m target-plane half-span instead
of 22-25m. This tightens framing and player scale without restoring the old
near-touchline zoom spike. It is a Stadium-scale approximation, not a promise
of screenshot-identical framing at unmatched ball positions.

V11 forced Night's board asset into Day. V12 removes that class override:
native Day uses **AShadowBoardActorDay**, Night still uses its own board.
Only `UEPlayerModel::Tick`'s local shadow-quality selector (+0x1e4) is set to
the simple board route. Actual RenderManager time, quality, player LOD,
lighting and Day/Night board creation remain native. Board transform, lifetime,
visibility and planar-shadow suppression remain native. No extra shadow map,
cascade, asset edit or global quality downgrade is introduced. Day should now
use its own simple shadow shape, not the Night lighting pattern; visual quality
must still be checked on Switch. Optional Day grading is not added speculatively.

Artifact: `local-debug/native-stadium-v12/pes21_nx.nro`, 51,884,237 bytes.
SHA-256 `b6b9cba0e7d44957b602e9f086958e4b95573b41908622c63570b0f0b2d51492`.
Built `-PerfTrace -Jobs 2`, no diagnostic overlay. Replace NRO only. The prepared
`dist/` NRO, V11 rollback NRO and accepted pitch PAK are untouched.
Verification: 136 focused tests plus two native-route tests pass (one optional
historical HUD fixture unavailable). The compiled ARM64 trampoline was emulated
for normal/live/nonzero-native-flag routes with an ABI-conforming register-
clobbering selector, checking continuation, stack, NZCV, GPRs and all SIMD
registers. Native opcode guards, camera scope/reset, geometry continuity,
shadow budget, helper/settings regressions, NRO markers, whitespace and public-
tree checks pass. The temporary local disassembly helper was removed; no raw
disassembly or proprietary game payload is added to the public tree.

Next device test: Day High; FootballNX near/far touchlines; Stadium goalkeeper
throw, aerial forward pass after a turnover, defensive return pass, midfield
receive/stop; switch Stadium -> Dynamic Wide and back; then Night. A short video
and this build's `stadium-perf v12` log are useful if any behavior remains wrong.
Do not infer full on-device acceptance from host tests or compilation.
No commit/push requested or performed.

## V11 candidate: permanent roof OFF, player contact shadows, upper tribune

2026-09-18; **hardware validation pending**. The user reports acceptable Day
FPS with V10, but missing player shadows and unacceptable coarse roof edges.
The latest request supersedes the old toggle policy: roof shadows must always
be OFF, with no Hub toggle. Day/Night selection remains available; there is no
Night-default fallback in this revision. The accepted pitch PAK is untouched.

- Hub Stadium contains only Stadium and Match Time. The roof policy accessor
  returns zero, with no mutable option. The accepted exact native roof-caster
  filter remains active. Day `r.Shadow.CSM.MaxCascades` is now **0**, removing
  directional cascade submissions rather than merely hiding their output;
  the two resolution ceilings remain 512. Checked native CVar writes retain
  ownership/priority guards and restore the original values for Night or
  Top Menu. The allowlisted Day pitch shader uses a uniform conditional for
  its disabled roof-mask sample instead of sampling then mixing it away.
  Actual driver execution and depth-draw counts still require a new capture.
- Thin player shadows use the existing **Night ShadowBoard** path, independent
  of Day CSM. Two instruction-checked selectors in `UEPlayerModel::LoadImpl`
  (+0x70) and `Tick` (+0x1dc) select Night for board class and visibility only.
  Both replace `mov w21,w0` with `mov w21,#1`; quality, real match time, Day
  lighting, player LOD and pitch materials are not changed. The native Tick
  continues to own board transforms, player visibility and lifetime. Night's
  own selector already returns 1, so that path is unchanged. No speculative
  Day color grading is added before the native board is tested on hardware.
- **FOOTBALLNX CAM** returns as the sixth fixed camera, alongside Dynamic Wide
  (default), Stadium, Medium, Long and Wide. It retains Dynamic Wide's native
  interpolated target, raises the side rail to Z=65 and uses elevation
  `32 + 0.16 * (65 - lookZ)`. A continuous vertical FOV mapping limits target-
  plane half-span to 22-25 units, reducing near-touchline magnification while
  maintaining an elevated far-side view. This is not a pixel-identical Stadium
  pose. No sliders, target predictor or new frame-history state are added.
  The compatible native FOV field is CameraParameter+0x34, in radians.
- The Stadium correction is now gated by both tmpdb type **12** and the live
  InplayCamera **CAMERA_ID 6**. These are distinct enum spaces (Dynamic Wide's
  live ID is 5, Live Broadcast's is 3). Selecting another type resets readiness;
  its target hook returns the original native result unchanged. Native Stadium
  zoom, angle, height, future-vector and shared trace routines remain intact.
- Pause and pause-loading surfaces clear all gameplay helper families,
  including set pieces, goal actions and penalties. A fresh native free-kick
  heartbeat takes precedence over an ambiguous PositionShift bit; long free
  kicks keep only Set Piece Taker. Unknown-context fallback cannot invent a
  Position Shift helper. Goal-kick/corner controls remain contextual.

Artifact: `local-debug/upper-tribune-shadow-v11/pes21_nx.nro`, 51,884,237 bytes.
SHA-256 `8fa9908d098da009b7abfc0f8cd6c86e8ec86aa2df5402a6be7f35827cd87141`.
Built with `-PerfTrace -Jobs 2`, without diagnostic overlay. Replace **NRO only**;
the prepared `dist/` NRO and accepted pitch PAK were not overwritten.
Verification: 136 focused tests and 21 subtests passed; one optional native HUD
fixture test was unavailable. Coverage includes upper-tribune continuity and
idempotence, camera ownership, all three CVar caps/restoration, roof UI removal,
helper modal combinations, and compatible ELF player-shadow/camera ABI.
NRO markers, whitespace and public-tree audit pass. The disposable audit helper
was removed after recording its findings here and in the ABI tests.

Hardware checklist: Day High with roof absent and thin player shadows; Night
High in the same session; FootballNX near/far touchlines; Stadium -> each other
camera; long free kick and goal kick -> Pause -> each submenu/loading -> Resume.
Use this build's `stadium-perf v11` log to assess actual performance. Compile,
host policy tests and compatible-library ABI checks do not establish Switch
visual quality, frame pacing or FPS. No commit/push performed.

The following sections are historical candidates, not the current roof policy.

## V10 candidate: final Day High budget attempt, five cameras

2026-09-18; **hardware acceptance pending**. The user allows one more Day High
performance attempt before choosing a Night-default fallback. Do not treat a
successful build as a performance result, or force Night before that test.

Supplied log SHA-256:
`2bf3c13ca7996c0ef1a2e2edbf3584d8fc11b4f294d580745ce92a850913d755`.
Its header is V7 (not V9). Selected complete active-camera, unpaused windows:

| Match / setting | Windows | Aggregate FPS | Mean depth draws/frame |
| --- | ---: | ---: | ---: |
| 1 / Night High, Stadium | 25 | 59.71 | 0 |
| 2 / Night Standard, Dynamic Wide | 30 | 59.91 | 0 |
| 3 / Day Standard, Dynamic Wide, roof ON | 3 | 59.99 | 0 |
| 4 / Day High, Dynamic Wide, roof ON | 14 | 43.41 | 145.0 |

Day High reports 276.4 mean draws/frame and 1016x1016 depth viewports. Native
readback confirms the V7 2048 -> 1024 resolution caps took effect. Resolution
was not ignored, but the workload remained large. Quality/time/camera are
different scenes, so this is evidence to target the extra shadow work, not
a measured GPU-cost breakdown or a controlled shadow-only A/B.

V10 caps Day `r.Shadow.MaxCSMResolution` and `r.Shadow.MaxResolution` at **512**,
and adds `r.Shadow.CSM.MaxCascades` capped at **1**. All use the checked native
integer-CVar setter on the UE game thread, with existing priority and ownership
guards. Lower/zero native values are not raised. Owned originals are restored
for Night/Top Menu, respecting detectable external changes. No ShadowQuality=0,
global High-to-Standard downgrade, scene-resolution change, frame skipping,
GPU readback, arbitrary GL viewport override or pitch asset edit is introduced.
The accepted roof filter still independently controls the roof casters.

Native audit: FViewInfo::Init bounds its cascade count and stores it at
FSceneView+0x278; directional-light shadow gathering reads that field and
GetNumShadowMappedCascades clamps the light's requested count to it. The runtime
contains the CSM MaxCascades setting. This supports a native count reduction;
the next CVar readback/depth-draw capture must establish its effective result.
`[SHADOWBUDGET] observe` records already-low values once per match as well as
setter readbacks, so an absent write is no longer ambiguous. Missing/different
CVar types retain native behavior and are logged, never blindly cast.

Tradeoff: reduced shadow detail / potentially coarser edges or cascade coverage.
Player and stadium shadows remain enabled by policy; no guarantee of 60 FPS.
Test Day High, same camera/roof/team settings as match 4, then Night High in the
same app session to verify restoration. Check roof ON/OFF and player shadows.
If the resulting Day experience is still unacceptable, stop tuning and follow
the user's requested Night-default fallback in the next change.

Camera choices now contain only Dynamic Wide (default), Stadium, Medium, Long
and Wide. Wide Dynamic Custom is removed; any legacy custom snapshot falls
back to ordinary Dynamic Wide with the custom flag cleared. Previous stamina
OFF and V7 native-speed/rematch changes remain included.

Artifact: `local-debug/day-high-final-v10/pes21_nx.nro`, 51,884,237 bytes.
SHA-256 `96025b2655b1749db183a2f3a6f21962c8360c69e7168e4cbf7eacdea0c19a6e`.
Built with `-PerfTrace -Jobs 2`, without `-Diagnostics`. Replace **NRO only**;
keep the accepted pitch PAK. The prepared `dist/` NRO was not overwritten.
69 focused tests and 2 subtests passed; 1 optional historical HUD fixture was
unavailable. Tests cover five-choice wrap/legacy-custom removal, all three
shadow caps, refused writes/restores, throttling, lower native values, wrong
CVar type, quality ownership, Night/Top Menu restoration and compatible ELF
view/cascade ABI. NRO marker checks, whitespace and public-tree audits pass.
Disposable native audit dumps were removed; findings remain here and in tests.
No commit/push performed. None of these checks establishes on-device FPS.

## V9 candidate: six-choice camera selector

2026-09-18; hardware validation pending. The only selectable types, in order,
are **Dynamic Wide (default), Stadium, Medium, Long, Wide, Wide Dynamic Custom**.
Live Broadcast and Stadium Custom are removed from the picker. Wide Dynamic
Custom is the renamed FootballNX fixed tribune preset from V8; it does not
restore editable sliders or change tracking, lens or framing in this revision.
Its native type remains 5 and the existing internal/perf `footballnx` flag
still distinguishes it from ordinary Dynamic Wide.

The first match of an app session seeds native tmpdb with Dynamic Wide before
MatchSetup consumes it, regardless of old saved camera types. Subsequent
matches retain the player's in-session selection, including the custom flag.
Only the chosen type is carried into the new match; its other camera bytes
come from the new resident rather than an old match snapshot. Removed/unknown
snapshot types fall back to Dynamic Wide. Pause-page restore and the native
registry/MatchEnv update path are retained; no per-frame camera forcing added.

V8 stamina OFF, the accepted pitch/roof toggle and the V7 candidate fixes stay
unchanged. The light profiling build now identifies itself as V9, without a
diagnostic overlay. Hardware check: cycle all six choices in both directions,
verify the default before first kickoff, then Top Menu -> new teams -> new
match and confirm the selected camera remains active.

Artifact: `local-debug/footballnx-camera-perf-v9/pes21_nx.nro`, 51,884,237 bytes,
SHA-256 `71529095280bc1a7f98b4f57a8aff61e5f1c6df345db5b4b76de6607b3855374`.
Built with `-PerfTrace -Jobs 2`, without `-Diagnostics`. Replace NRO only; the
prepared runtime and pitch PAK remain untouched. 67 focused tests and 2 subtests
passed; 1 optional historical HUD fixture was unavailable. Executable coverage
includes both-direction six-choice wrap, Decide, all seven resident modes,
old-type/default normalization, missing manager, per-session rematch choice,
and pause restore without stale camera bytes. NRO inspection confirms the six
labels and excludes LIVE BROADCAST, STADIUM CUSTOM, FOOTBALLNX CAM and SHOW
STAMINA. Public-tree and whitespace audits pass; no commit/push performed.

## V8 candidate: stamina display disabled, settings action trace

2026-09-18; **not yet accepted on hardware**. Supersedes the V7 candidate for
the next test and retains its native speed ownership, rematch rules, FootballNX
view and Day shadow budget. The accepted roof toggle and pitch PAK are unchanged.

New input: `Videos/perf.log`, SHA-256
`89b18bb7c683c404d193e9a567d575e3985cf4eb82d71abe1691b67a22fda1b3`.
The header is **stadium-perf v6**, not V7. It contains no `[GAMESPEED]`,
`[MATCHRULES]` or `[SHADOWBUDGET]` events, so it cannot validate those changes.
Complete unpaused active-camera windows (loading/menus/transitions excluded):

| Match | Windows | Frames | Aggregate FPS | Window FPS range |
| --- | ---: | ---: | ---: | ---: |
| 1 | 17 | 3512 | 41.24 | 36.24–44.76 |
| 2 | 13 | 2671 | 40.98 | 38.38–45.30 |

Aggregate FPS uses total frames / sum(frames / reported FPS), with rounding
from the log. Both matches report Night, native camera 5, FootballNX off,
and zero depth-only draws. Draw-submission CPU time averages about 3.23/3.45ms
per frame and swap time 0.37/0.35ms. These are **not GPU timings** and do not
explain the whole 24ms frame. The first complete active window before the first
recorded pause is already 36.24 FPS. V6 has neither stamina state nor action
timestamps, so no causal stamina-toggle or Game-Speed-change conclusion can
be drawn. Its cached quality/fps-mode labels also cannot establish identical
native quality to the earlier smooth Night capture.

At the user's request, V8 removes SHOW STAMINA and always hides native stamina
gauge slots. It removes the old visibility/fill-order experiments; gameplay
stamina is untouched. General Settings now has six rows: Radar, Game Speed,
Next Target Indicator, Show Replay, Chant SFX, Commentary. Labels, values,
input dispatch and focus wrap use the new order. Camera settings are unchanged.

The light `-PerfTrace` build logs one `[SETTINGS]` record per General action,
with monotonic timestamp, row, action, label and resulting value. No per-draw
logging or diagnostic HUD is added. This identifies UI state, not proof that
a renderer/simulation has consumed it. The file header identifies **v8**;
`[STADIUMPERF] v=6` continues to identify the unchanged record schema.

Next hardware test: use the same Night/camera/quality setup, play first without
opening settings, then change Radar/Replay/audio one at a time, resume between
changes, and finally exercise Game Speed. Confirm no stamina bars/toggle and
retain the log. Also repeat the V7 before-kickoff and Night/Legend rematch tests
below. This build does not claim to have restored 60 FPS before measurement.

Artifact: `local-debug/footballnx-camera-perf-v8/pes21_nx.nro`, 51,884,237 bytes,
SHA-256 `216f21e2ddb93eb452c82bf9c40030cc4c7f9877e81a9fadd721b0bc9afaabe4`.
Built with `-PerfTrace -Jobs 2`, without `-Diagnostics`. Replace **NRO only**;
the prepared `dist/` NRO and pitch PAK were not overwritten. Local validation:
66 distinct focused tests and 2 subtests passed across the focused run plus
the additional native stamina-slot audit; one older optional HUD fixture test
was unavailable. Menu tests execute all six labels/values/actions, focus wrap,
and both profiling/release paths. NRO contains the V8/event markers and no
SHOW STAMINA label, old fill-order patch label or removed Status setter symbol.
Public-tree and whitespace audits pass. No new commit/push.

## V7 candidate: native speed ownership, rematch rules and Day budget

Built 2026-09-18; **not yet accepted on hardware**. Roof-toggle acceptance
remains at `38f0d46` / `checkpoint-roof-shadow-toggle-v6`. V7 does not alter
the roof caster filter, roof preference, pitch assets or High shader fixes.

### Game Speed, not all General Settings

The user isolated frame glitching to changing **Game Speed**, including
before the first kickoff. The previous wrapper changed the native Status
FPS immediately and then re-enforced that target from every UE tick for the
rest of the match. This fights legitimate loading, pause, replay and FixDemo
rates. Native `MatchMain` already calls its speed updater (at +0x1ec and
+0x3a0); it reads `SystemSettings::GameSpeedSettings`. The async renderer's
`BeginWriteBuffer` also reads Status FPS to compute buffer timestamps.

V7 commits only tmpdb + the embedded registry speed settings at +0x14.
It removes the direct Status setter, the UI-triggered high-speed updater,
and the unconditional UE-tick enforcement. Native gameplay now owns when
the requested speed takes effect; menus/cinematics retain their own timing.
The conflicting writers are demonstrated by native call-site inspection;
their removal is a **candidate fix**, not visual proof of the glitch's cause.
The old claim that every General Settings change caused this is superseded.

`[GAMESPEED]` records setting, native target (21/24/27/30/33 simulation Hz),
and sampled live rate. These are **not** the 30/60 render-FPS option. Live may
legitimately differ while paused/loading. No rate is forced to make the log
match the requested target.

### Night/COM after Top Menu and new teams

Hub preferences remain authoritative instead of importing bootstrap defaults.
Rules are armed before Hub -> Strategy and reapplied at active Exhibition
MatchSetup even when a native footer was bypassed. Opening COM Level no
longer replaces its choice with the stock debug selector's reset value.

There are two different Day/Night copies in the compatible runtime:

- `tmpdb::Match` rule at +0x13c (`Get/SetTimeZone`).
- Its 0xa8-byte `common::InitParam` renderer snapshot at +0x170, timezone +4.

Updating the rule alone did not update the prebuilt stadium snapshot. V7
round-trips the native getter/setter and changes only that word; stadium ID,
weather, team and all other snapshot fields are preserved. Its AArch64 return
ABI uses x8. `[MATCHRULES]` logs desired zone/level and both tmpdb readbacks,
including `stadium_zone`. This is handoff evidence, not a rendered-scene probe.
Preferences still last for the current app session, not across app restarts.

### FootballNX tribune view

Native Stadium D2/H3 audit yields eye height 16.5 and side rail Z=55. V7 replaces
the old yaw-only rotation with that fixed rail/height, taking eye X from Wide's
already-interpolated look X. Wide owns tracking, look target and lens; the
mapping is absolute/idempotent, never an accumulating rotation or a translation
of the whole eye/look pair toward the near stand. Only native camera ID 5 with
the FootballNX flag is affected. This is Stadium-like fixed tribune framing,
not Stadium's dynamic lens/yaw or a promise of pixel-identical composition.
Native Stadium retains V6's X-only soft bias and native future-vector motion;
shared tracing and native final Stadium eye/look remain untouched.

### Night comparison and targeted Day experiment

Night-only input SHA-256:
`a4741c426fe33616a7481e8cd04483f0d9ef29d7eb63de1840c532096082930b`.
Nine complete active-camera windows: 59.14 FPS overall; the eight after the
initial slow window are 59.99-60.02 FPS. Approximately 153.6 draws/frame,
**zero depth-only draws**, compared with the Day capture's 135-146 depth draws
and 2040x2040 maximum depth viewport. These are submission counts, not GPU
timings; positions/cameras differ, so this is not a controlled GPU-cost A/B.

V7 caps `r.Shadow.MaxCSMResolution` and `r.Shadow.MaxResolution` at 1024 in Day,
without raising lower quality values or disabling player/cascade shadows.
The native console setter propagates changes on the UE game thread; exact
integer-CVar vtable identity is checked first. It restores only a value it
owns on Night/Top Menu, respecting detectable external quality/value/priority
changes. A same-value, same-priority external write cannot be distinguished.
Missing/different CVar types fail open. `[SHADOWBUDGET]` reports the actual
readback; the next depth viewport samples establish whether the renderer
consumed it. Expected tradeoff: lower shadow detail for reduced depth workload;
no 60-FPS guarantee. Roof ON/OFF remains independent.

### Artifact and verification

- `local-debug/footballnx-camera-perf-v7/pes21_nx.nro`, 51,884,237 bytes.
- SHA-256 `fa5d42292b84adbc101d69d0fe16bcdd7322e9680f8ea9db8dc0bfb5f21ed9cf`.
- Built with `-PerfTrace`, `-Jobs 2`, without `-Diagnostics`; no debug HUD.
- 53 focused tests passed. Host tests cover all speed values without forcing live timing,
  rematch bootstrap/default replacement and both Day/Night copies, snapshot
  byte preservation, view idempotence, shadow ownership/restore/type guards,
  plus existing camera/roof/result tests. Optional local ELF ABI tests passed.
- NRO markers include all three new log categories and exclude the removed
  Status setter symbol. Public-tree audit and whitespace checks pass.
- Replace **NRO only**; keep the accepted pitch PAK. The prepared `dist/`
  NRO was not overwritten. No new commit/push performed.

Hardware verification: before kickoff cycle every Game Speed (-2..+2),
resume, repeat during play and check replay/goal transitions; change a non-speed
General setting as a control. Play Night/Legend -> Top Menu -> new teams ->
kickoff without changing either choice, then repeat Day. Compare Day roof
ON/OFF and Night with the same camera/quality and check the FootballNX near/far
touchlines. Copy `perf.log` before the next app launch overwrites it.

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

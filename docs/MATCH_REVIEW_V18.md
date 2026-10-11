# Referee rendering and kickoff candidate v18

The user-requested v17 checkpoint is commit `f7abf99`, pushed on `cupleague`
with annotated tag `checkpoint-review-v17-2026-10-11`. The following changes
are included in the subsequent `checkpoint-roof-shadow-v20-2026-10-11` build.
That acceptance concerns improved roof-shadow performance; the referee-specific
device checks below still define its separate acceptance criteria.

## Evidence from the supplied v17 log

The match log records one owned model load and no subsequent release/reload.
Its four presentation summaries average 18.6-19.8 ms, with 20 ms overruns.
Follower CPU averages 11-12 microseconds, pose evaluation 8 microseconds and
publication 2 microseconds. Most worst samples are below 0.15 ms; one reaches
1.49 ms. These CPU measurements exclude native asynchronous rendering and GPU
work. They do not establish repeated spawning as the cause of the frame issue.
No completed kickoff relocation appears in the log.

## Native renderer policy

The old `draw::Human::SetLod` call only stores its level. The native
`UEPlayerModel::LoadImpl` selects the actor class using the graphics quality,
and `render::PlayerModel::Update` separately selects its body mesh. Setting the
wrapper Human's level does not by itself request the lower-cost actor.
The renderer's virtual UEBridge quality query delegates to the same Env
quality PLT used by the asynchronous loader; both call paths were verified in
the local compatible library.

The probe now resolves its own renderer through the locked native
`VisionModelManager::GetPlayerModel` API during loading. Live updates use a
single atomic identity comparison; they do not scan or lock that manager.
The owned renderer's native mesh selection and queued actor load temporarily
observe native Low quality when the global setting is High. Native Low/Lowest
settings remain unchanged. The global quality option is never written.

The override is thread-local and restored after each callback. The queued UE
model identity is published before the original native queue exposes it to the
load thread. Unrelated and nested player callbacks retain their native quality.
Owned identities are cleared before deletion; old callbacks then pass through.
The referee can therefore use the game's Low actor/body path without lowering
the 22 players or reducing visible pose cadence. Its appearance may have less
detail, and Low kit/face appearance still needs checking on the device.

New bindings and PLTs are checked before any probe patch is installed. Missing
symbols or unexpected instructions leave the optional probe uninstalled.
The deferred break summary adds native PlayerModel update timing, `low_loads`,
`creates` and `kickoff` counts. That update timing also excludes UE actor ticks,
VisionModel interpolation, draw submission and GPU time. It is not a total
renderer cost or an FPS claim. No new live-frame filesystem writes are added.

## Goal to kickoff

The previous broad ResetFlow hook and live fade-flag polling are removed.
`Flow::ExecPositionWarp` supplies a request only when native player placement
reports completion in HalfStart or KickOff. This task occurs before fade-in,
and its scalar request survives the period in which draw callbacks stop.

The first resumed publication puts the existing referee at X=0, Z=10.75 m,
outside the 9.15 m centre circle, facing the centre. Motion/gesture clocks reset,
and the ready stance holds until the ball leaves the centre area. Native warp
already establishes the centre placement: a pass before the first resumed
draw releases readiness immediately, instead of leaving it stuck indefinitely.
No Human, UE actor, animation bank or bone buffer is spawned for this reset.
Demo placement cannot overwrite the ready stance.

## Verification and delivery

Host coverage includes native completion versus pending warp, no draw during
black, half-start, fifty successive goals reusing one model, fast kickoff,
22 unchanged players, native Low/Lowest preservation, nested callbacks,
another OS thread, teardown and full-rate visible/off-screen pose handling.
Bootstrap tests also reject each new layout/PLT mismatch before executable
mapping. The existing weather/stadium hook chain remains covered.

The local update contains only the new NRO for the existing v17 runtime pair
(`e861c583ec78e9ae`, 53,248-byte patch OBB). It does not require another stadium
cook, face pack, weather pack or OBB copy. Close the game before replacing the
NRO, keep the existing probe token, and retain the v17 NRO for rollback.

Device acceptance must check fast passes with the probe, a goal followed by
kickoff, referee Low appearance in Summer/Winter and a subsequent match.
`low_loads=1`, stable `creates=1` during a match and an increasing `kickoff`
count make the new paths observable. Compare presentation intervals in the
same scene with and without the probe; host tests cannot guarantee 60 FPS.
If `low_loads` remains zero on native High, retain the log: the queued actor may
have loaded before renderer ownership was captured. This candidate does not
destroy or respawn an already-created actor to change its class.

The final focused run passes 9 tests and 180 subtests. It includes an optional
local-library contract check for all probe bindings, the five new PLT sites,
the native Low actor branch, queued load dispatch, UEBridge quality delegation
and the actual Flow task's call through the warp PLT. This also caught and
corrected a renderer layout guard before delivery; the final NRO was rebuilt.
The broader run before that guard-only correction passed 686 tests and 55,375
subtests, skipped 51 optional cases, and retained 13 known baseline failures in
menu/catalog, gamepad, pause harness and master-data checks. No new broad-suite
failure was introduced. The final focused checks cover the corrected guard.

The isolated production build uses the accepted private catalog pair, with
diagnostics/performance trace disabled. NRO executable segments are matched to
the produced AArch64 ELF, the compiled migration ID is checked against the
runtime manifest, and the project icon is checked byte-for-byte. The delivery
archive is read back and hash-verified. Binary inputs and outputs remain local.

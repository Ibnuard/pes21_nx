# Stadium / High diagnostic candidate — 2026-09-17

Checkpoint: user confirmed High renders 3D without the prior crash and accepted
the reconstructed pitch pattern/grain (2026-09-17). This is not confirmation
of complete High postprocessing fidelity or all camera scenarios.

## Accepted checkpoint and next visual review

- NRO SHA-256: `e514b94d01d63e3b40e5d44a65ec9b60caed4e49ef43aecefd1e930566a54d33`
- PAK SHA-256: `f25e26d1b5e6bb08156485663ba43f33efb6779521d29d4c08a538e2505ee946`
- Pitch backup: `local-inputs/custom-pitch-v17/PesMobile-Android_ETC1_P.pak`
  (ignored, never publish the cooked game payload).
- High renders successfully in the supplied hardware screenshots. Night pitch
  pattern and grain accepted; user requests only a very slight darkening next.
- Day stadium shadow appears olive/yellow with jagged edges. Screenshot alone
  does not isolate shadow-map filtering, lighting/material tint, or the fallback
  color transform. Inspect those independently before changing shader behavior.
- Next candidate should preserve stripe separation and grain, reduce pitch
  luminance by roughly 2–3% as a starting experiment, and isolate day shadow
  changes from the accepted night look. No such tuning is in this checkpoint.
- 40 tests and 30 subtests passed; full 27-member PAK roundtrip verified.

## Follow-up v4: source identified; complete pitch reconstruction

The v3 hardware trace shows FBO 8 / texture 85 at 1024x576 with nonzero RGB
(sample 768/115/22372), while FBO 10 / texture 297 at 256x144 is black.
The final three-index draw (program 19) binds texture 297 on unit 0 and texture
85 on unit 1. This is direct evidence that the old unit-0-only compositor
does not recognize High's scene source. Numeric IDs are diagnostic evidence,
not constants used by the fix.

V4 records completed color+depth targets within the current frame. On a
three-vertex presentation draw, a unit-1 source must match a recorded target
and the full destination viewport dimensions. It then uses the existing
fullscreen fallback with that source and sampler, restoring unit 0 and the
active texture afterwards. Targets expire at swap and after consumption.
This bypasses the native final bloom composition; it does not claim complete
High postprocessing fidelity. Other shader stages and High quality selection
remain enabled. User has confirmed scene rendering; broader hardware coverage
and postprocessing parity remain unverified.

The previous 11-member pitch candidate was rejected by the user: it removed
the custom overrides. Do not deploy that PAK again. With no backup available,
`tools/recreate_custom_pitch.py` rebuilds all 27 members from the owned native
PAK. Shader hashes and same-length name-table changes are verified using the
existing Low_R pipeline. White-line blocks at every mip are retained; six
diffuse textures, neutral specular masks and a soft detail texture are present.
Grain is explicitly seeded procedural, not falsely described as recovered EF10
grain. Palette/phase validation verifies 18 bands, opposite Low_R phase, and
unchanged native marking blocks. This is a reconstruction, not backup recovery.

Artifacts: `local-debug/high-compositor-v4/pes21_nx.nro` and
`local-debug/pitch-recreate/install/PesMobile-Android_ETC1_P.pak`.

## Follow-up v3: High reaches gameplay but scene is black

User confirms v2 no longer crashes. The next hardware log records successful
vertex-only completion, no shader compile/link failures, and about 920,700
offscreen indices per sampled gameplay frame. This proves draw submission,
not correctly shaded geometry. Its offscreen samples repeatedly inspect only
FBO 10, texture 232, viewport 256x144, with zero RGB. The scene-sized 1024x576
allocation exists but is not sampled at its intermediate transition.

`local-debug/high-compositor-v3/pes21_nx.nro` is a diagnostic-only follow-up,
not a claimed black-screen fix. It samples transitions between non-default
FBOs as well as the final transition to screen, throttled per target rather
than globally (avoids sampling cadence aliasing a fixed multipass sequence).
It records default-target draw textures even when the preceding sample is
black. No guessed scene texture, shader replacement, or High-to-Standard
downgrade is added. V2's guarded link compatibility remains.

Copy NRO only; leave the pitch PAK unchanged. Reproduce High kickoff, allow
about 10 seconds of gameplay, then collect debug.log before another launch.
Inspect intermediate RGB samples and final sampler identities to choose the
next compositor change. Debug readbacks can reduce performance.

## Follow-up v2

The supplied hardware log ends with `program lacks a fragment shader` for
program 72, then `AndroidThunkJava_ForceQuit`. The preceding 4096x2048 depth
allocation returns. This identifies a link failure, not an established OOM.
The shadow/depth-pass attribution is still an inference.

The compatibility candidate retries only that exact driver error with exactly
one attached, compiled vertex shader and a recognized GLES source version.
It adds a matching-version fragment stage with no color outputs. Existing
fragment shaders, including masked geometry shaders, are never replaced.
Failed retries preserve failure rather than faking link success. Host tests
cover refusal cases, cleanup, successful retry, and unsuccessful retry.

`local-debug/stadium-high-review-v2/` contains the diagnostic NRO and
`PesMobile-Android_ETC1_P.pak`. Back up the installed NRO and patch PAK first.
Test the NRO alone first to isolate High, then copy the PAK to
`PesMobile/Content/Paks/`. No OBB/CPK/saves changes.

At the user's request the pitch candidate uses the surviving local custom
11-member patch, not an asserted byte-identical copy of their installed PAK.
`tools/soften_pitch_patch.py` rebuilds its three ETC1 diffuse payloads with
the v17 palette and deterministic positive grain. All eight material files
and all detected white-paint ETC blocks remain byte-identical to that local
baseline. Package unpack/repack is independently byte-checked. This is not
a claim of coverage for the unavailable six-texture/27-member baseline.
Pitch lighting and High gameplay still require hardware review.

- Stadium target retains the 14-unit deadzone but smoothly bounds planar
  ball-to-target separation to 18 units instead of retaining 65% of arbitrary
  native prediction error. No velocity prediction or shared trace patch.
- Pause updates reset movement readiness, including the settings-child route.
  Resume must observe fresh ball movement and one native warm-up frame.
- Diagnostic build logs texture storage and renderbuffer allocations before
  and after driver entry. Existing diagnostics and per-line flushing are on;
  profiling is off. These logs help narrow a crash, not prove its cause.
- Pitch recipe `clean-v17` retains v16's RGB midpoint and stripe geometry,
  reduces green stripe separation from 24 to 8, and uses weaker positive-only
  diffuse grain. Runtime generation is pending the actual installed baseline:
  local dist contains an older 11-member patch, not the documented 27-member
  pitch baseline. Do not replace the user's pitch with this old patch.

Candidate NRO: `local-debug/stadium-high-review/pes21_nx.nro`.
Copy only that NRO over the current full-loose-CPK installation for diagnostics.
Keep existing OBB, LooseCpk, PAK and saves. Previous NRO remains in
`local-debug/full-mobile-kit-migration-v1/` for rollback.

Test Standard first: Stadium selected before kickoff; forward/backward passes;
pause > General Settings > resume; repeat camera changes and second match.
Then select High and reproduce entering the field. Copy `debug.log` immediately
after failure, before another launch (the next boot truncates it). Include the
system crash report if available. Diagnostic frame rate is not representative
of release performance. Ultra and 90 FPS are out of scope.

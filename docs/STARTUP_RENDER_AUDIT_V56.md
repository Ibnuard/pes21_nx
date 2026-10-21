# First launch after an NRO update: bounded render observation

The 21 October device report shows missing whole players, disconnected shoes,
and a black kit during walkout. The user reports that a second application
launch with the same installation renders normally. Earlier clarification
limits the trigger to replacing the NRO/package; a reboot alone was not the
reported trigger. This is broader than a hair alpha or triangle-budget defect.

The supplied journal identifies the v54 build
`79cf4f629bf5992fc6e878d96f15f7ff29a32c19`. Its SHA-256 is
`a6e3caedc081abfa125c6a2d2bf2d510a07800f6ac263dad4113821258eea968`.
It contains one application boot and two match/stadium sessions, rather than a
matched first/second application-launch pair. There are no recorded compile or
link failures. That does not establish the absence of other GL/upload errors.
The v51 program-binary uniform invalidation is already present. Neither the
log nor the screenshots establish a cache failure, an out-of-memory condition,
or a particular synchronization defect.

## Narrow diagnostic candidate

`build-wsl.ps1 -StartupRenderAudit` enables a separate compile-time observation
path. It cannot be combined with Diagnostics, PerfTrace, or NearCameraTrace in
that entry point. Default builds compile out this path.

The probe counts existing compile/link outcomes, core/OES program-binary
attempts, existing native link-status and GL-error queries, core/EXT/OES buffer
map/unmap outcomes, wrapped buffer/texture allocations, existing periodic flushes,
and real make-current outcomes. Binary attempts are **not cache hits**. Upload
counts cover intercepted routes, not every possible GL upload API. Counters are
cumulative across native GL threads. Sixteen bounded failure records identify
the route and wrapper context slot without publishing pointers/game payloads.
The engine receives the native return values and arguments unchanged.

There are no additional GL queries, readbacks, GPU waits, forced flushes, cache
purges, artificial loading delays, draw hooks, or asset/quality changes. RAM
counts are reported on leaving the wrapper's live-play state, with at most eight
snapshots in the existing bounded scene journal. This optional observation build
is for visibility diagnosis, not a replacement performance benchmark or a
confirmed fix. A zero error count with zero native checks remains unknown.

Failure kind numbers: 7 native link rejection, 9 map failure, 11 unmap failure,
13 native GL error, 18 make-current failure. Map routes: 1 core, 2 EXT, 3 OES.
Shader `compile`/`link` and `make_current` pairs mean success/failure; binary
pairs mean core/OES attempts. Resource and error counters include all observed
threads, not just the presenting context. Snapshots are not an atomic GPU frame.

## Device sequence

Use the separate ready-copy folder containing only `switch/pes21_nx/pes21_nx.nro`.
Keep the same installed PAKs, lineup, graphics, camera, weather, and stadium.
Keep the delivered v54 NRO as rollback. No new face processing is required.

1. Copy the diagnostic NRO, fully launch, and play Barca versus MU. Inspect the
   walkout and kickoff, play briefly, then Pause and leave the menu open for a
   few seconds so the snapshot can be written. Record whether bodies, kits,
   heads, ball, or stadium disappear. Preserve `scene-runtime.log` if convenient.
2. Fully exit and launch that **same NRO** again without replacing files or
   clearing caches. Repeat the same match and Pause.
3. Before a third launch, preserve both `scene-runtime.previous.log` and
   `scene-runtime.log`. The first is the immediately preceding application boot.
   The journal must contain `startup render audit: v56 observe-only` and the
   `startup shaders` / `startup resources` snapshots after Pause.

If neither launch reproduces the issue, record that outcome; it is not evidence
that an observation-only build repaired it. Do not delete a working cache just
to manufacture a failure. A subsequent correction must follow the observed
resource/status evidence and preserve the stable frame-pacing baseline.

## Local verification

The initial focused suite passed 19 tests: actual-source observation wrappers,
program-binary invalidation, mixed GL lookup routes, roof uniforms, upload-budget
regressions, and vertex-only completion. The observation harness checks exact
arguments/results, unsupported lookups, native error preservation, map aliases,
bounded records, and no journal output while its live flag is set. Build and
package receipts remain ignored under `local-debug/startup-render-v56`.
No Switch first-launch fix or device FPS acceptance is claimed.

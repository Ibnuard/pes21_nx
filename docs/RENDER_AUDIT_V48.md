# Konami visibility and compositor audit v48

## Accepted checkpoint and first-launch follow-up

On 18 October 2026 the user reports smooth, stable 60 FPS with v48. Blinking
occurs only on the first launch after replacing the NRO/package; the second
launch with the same NRO is normal. The user clarifies that a full Switch
restart with the same installation is not the reported trigger. Preserve the
accepted v48 binary and current face/stadium quality as this checkpoint.
This is user device acceptance for the tested setup, not a new timing capture
or a claim covering every team, camera, stadium and graphics setting.

The locally available scene-runtime.log still has the v47 header and the
previously recorded SHA-256 below. No v48 first/second-launch pair was supplied
with this feedback. Do not relabel the old log as evidence for v48 acceptance.

The pattern points to initialization after an update, but does not establish
the failed resource or synchronization boundary. In particular:

- The wrapper's GL state/uniform caches live in process-local TLS and are reset
  on context changes; they do not persist from one application launch to the
  next. Native upload contexts retain separate submission budgets.
- main.c requests a persistent Mesa shader cache with MESA_GLSL_CACHE_DIR and
  MESA_GLSL_CACHE_DISABLE. Configuration is not proof that this driver uses it.
  The installed libEGL.a has an empty disk_cache.c.o symbol inventory and no
  MESA_GLSL_CACHE option strings; the linked v48 ELF lacks disk_cache_* entry
  points. Its state-tracker shader-cache helpers still exist. These observations
  prevent attributing the fix on a second launch to Mesa disk caching alone.
- The compatible Mobile ELF contains native OpenGL program-binary file-cache
  read/write and pipeline-precompile methods. Their presence does not prove
  that the corresponding runtime option was enabled, a cache hit occurred, or
  a shader caused the missing geometry in this run.
- v47/v48 have different GNU build IDs, generated from build inputs/options.
  This verifies a build change, not that a particular cache was invalidated.

Cold compilation can change load timing, but it does not by itself explain
missing pixels. Native cached-data initialization or a resource-publication
race exposed by that timing remain hypotheses. No new GPU waits, artificial
loading delay, forced cache purge, geometry reduction or renderer change is
added to the accepted NRO on this evidence.

The log analyser now retains exact session headers, compile/link failures and
actual model-quality policy notes, including load-only logs. Missing shader
cache-hit measurements remain unknown and visibility is never inferred from
zero error records. When the next natural update reproduces the issue, retain
scene-runtime.previous.log and scene-runtime.log after the second launch, then
compare them with analyze_match_pacing.py --allow-partial and separate
--case first=... / --case second=... arguments. Preserve the same installation
and play sequence; do not purge a working cache merely to collect a trace.

Focused checkpoint tests, including these new analyser cases, passed 29 tests.
The broader checkpoint suite passed 377 tests and 86 subtests, with 2 optional
fixture tests skipped. The public-tree audit passed for 1,111 files.
The Windows Unicorn replay diagnostic noted below remains a host limitation.
REA deep providers are unavailable on this host; the additional observations
use local ELF/archive inspection and source, not REA decompilation or a new
Switch runtime observation. The candidate ZIP and its manifest remain immutable;
their original pre-test acceptance flags describe packaging time.

## Original v47 evidence and v48 preparation

The user reports that blinking disappears on a second launch, while native
Konami loses surfaces behind a goal and native STADIUM stutters toward the
far touchline/crowd. The user confirms the Konami holes also occur with the
extra face PAK removed. This is not evidence for further head reduction.

The supplied v47 journal confirms native Konami, DAY/FINE, 1024x576 and the
installed mixed-quality policy. Across 17,497 presentation intervals it records
17.675 ms mean (56.58 presentations/s), 10.076% over 20 ms and a 159.410 ms
maximum. Camera, actual saved quality, exact mounts, first-launch behavior
and draw/visibility outcomes are not recorded. The long first-window outlier
does not identify shader compilation or explain every later slow frame.
Preserved input SHA-256:
7050b482928704e668862ffd75fc1736f2774febf36f1e61cdc748f596f2aa57.

## Prior stadium budget scope

The 24,560 native core triangles are an offline asset reference. The reduction
manifest contains only Etihad, Signal Iduna, Stamford Bridge, Old Trafford and
Camp Nou. Runtime code does not truncate native draws to this budget.

An executable replay of stadium_loaded_canary calls the original loader and
then compares every supplied native actor, component and mesh byte before and
after. Both the full shell carrier and alternate low shell case remain intact;
asset-load and all mutation callbacks remain NULL in this replay. Native
Konami has no imported mesh in this scenario and exits before mesh replacement,
LOD clearing, material clearing or actor hiding.

The repeatable audit_stadium_package_scope.py utility lists PAK membership
without extracting or changing assets. The five locally packaged v34
release-fixed stadiums contain only their FootballNX/Stadiums namespaces,
with no native asset overrides or overlapping entries. This result describes
those exact local packages, not an inventory of the user's currently mounted
SD card. Neither scope check proves runtime visibility.

v48 journals a bounded component inventory during LoadedCall: requested
stadium, static actor count, native/imported shell counts and carrier presence.
These are component counts, not triangle counts, draw calls or visible objects.

## Reproduced wrapper defect and narrow fix

gl_diag_prepare_compose_experiment set log_result for the first four matched
compositions and four out of every 120, even when DEBUG_LOG was absent.
gl_diag_finish_compose_experiment then ran its pixel probe and glGetError
calls. Suppressing debugPrintf output did not suppress these side effects.

The ordinary NRO and quiet pacing NRO could therefore perform synchronous
pixel reads and consume GL errors before the engine queried them. A normal
compositor replay fails on the first matched frame with the old code. The
same replay now preserves a pending engine error and performs no pixel reads,
error queries or diagnostic state queries over 240 compositions. It checks
texture/sampler/active-unit restoration and the accepted flipped-blit fallback
when shader composition is unavailable, including distinct read/draw FBOs.

Only the diagnostic sampling is compiled out of ordinary and NEAR_CAMERA_TRACE
builds. Existing scene composition, native draws, shaders, lights, camera,
stadium assets, face PAK and resolution remain unchanged. Detailed DEBUG_LOG
builds retain their opt-in probes. Existing menu-only kit preview capture is
outside this compositor fix. No CPU/GPU speedup or visibility repair has yet
been measured on Switch; the probe defect is not asserted to explain the
specific goal-side holes.

## Preserve cold/warm evidence

At startup, the bounded prior scene-runtime.log is retained as
scene-runtime.previous.log. Exactly one prior session is kept, with an upper
bound of 64 KiB; a second launch no longer destroys the first launch's evidence.
The new journal still identifies the current version. File operations happen
at startup, not per draw. A real-filesystem test covers first boot, two further
boots and oversized input without growing an archive.

## Device acceptance and boundaries

The v47 quality policy remains Low=Low/Low, Standard=Standard/Standard and
High=Standard/High for players/stadium. The balanced-5000 pilot is unchanged;
there is no 2k recook. STADIUM-V2 and the FL26 entrance canary remain suspended.

Use the same lineup/settings and check native Konami behind both goals, the
far touchline and near-camera region, from kickoff and through a corner.
Pause before closing; repeat after a full second launch and retain both
journals before another restart. If the holes persist, a diagnostic run is
needed to distinguish native draw/driver behavior from the now-audited addon
selection and wrapper probe paths. Existing per-region CPU and asynchronous
GPU stream measurements remain available; compare like builds/settings and
do not equate GPU stream span with pure GPU busy time.

The diagnostic package also includes a narrow comparison for the v47 mixed
player-class change. First measure with diagnostic/render-control.txt, then
replace only the installed control file with
controls/native-player-class/render-control.txt and fully restart. The exact
PESNX_NATIVE_PLAYER_CLASS_V1 token skips installation of the High-player
branch patch; the log must identify native player classes. Saved quality,
stadium, face assets and state caching are unchanged. At High, this control
uses native High players with High stadium. Restore the default control and
restart to restore the requested Standard/High mapping. Ordinary builds ignore
the control. A hole persisting in both runs rules out that branch change as a
sufficient explanation; a changed outcome needs follow-up before attribution.
This comparison is for visibility, not a performance recommendation.

The control is read once by update_imports before install_ue4_hooks installs
the quality policy. Host tests cover ordinary and diagnostic installers,
unknown/malformed tokens, and independence from the separate cache bypass.

The source-level scope audit and removal of an unnecessary probe are complete.
The exact Konami disappearance cause, first-launch blinking and stable 60 FPS
remain device acceptance items, not confirmed fixes.

## Candidate verification

Both serial WSL builds succeeded with runtime pair e861c583ec78e9ae and the
53,248-byte dummy-OBB expectation. The launcher icon check passed. Packaging
compares all three NRO load segments with their respective ELF. The active
dist runtime was not promoted or replaced.

Compiled-code inspection confirms the v47 compositor finish function has
calls to glGetError and gl_diag_sample_rgb. Neither v48 variant contains the
pixel-probe helper, and their prepare/finish functions have no pixel-probe or
error-query calls. The native-player-class control token and activation
message occur only in the diagnostic NRO. This is not a claim that the entire
application has no glReadPixels use: the engine API and menu preview remain.

The final focused run completed with 19 passed and exit code zero. An adjacent
render/stadium run completed with 40 passed and 6 subtests passed. The Windows
Unicorn native-chooser replay emitted an access-violation diagnostic during
memory mapping despite completing all assertions; retain that host-emulator
limitation when interpreting its result. The standalone C compositor,
installer, stadium and journal replays passed. No Switch test was performed.
The public-tree audit passed for 1,111 files; scoped git diff --check passed.

Local artifact: local-debug/render-audit-v48/FootballNX-Render-Audit-v48-TEST.zip
(89,261,182 bytes). ZIP CRC and all manifest file hashes were independently
checked. Its six members are two NROs, two control text files, INSTALL.txt and
VERIFICATION.json; there are no game payloads. ZIP SHA-256:
706d3f97591a7b27d45016b5cad46e124af09be183991f878d2e5bda7f62fde2.

Build/audit reports are disposable under local-debug/render-audit-v48/.

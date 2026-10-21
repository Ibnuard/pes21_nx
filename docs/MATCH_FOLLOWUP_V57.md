# Match follow-up v57

The user did not reproduce blinking after installing the v56 observation NRO.
That is a non-reproduction, not evidence that observation repaired the original
first-launch issue. Yamal and Raphinha commentary were confirmed correct on
Switch. The new feedback concerns referee presentation, native Stadium target
selection, local result actions, wider commentary, assistant referees and
competition scoreboard layout/animation.

## Local result actions

Ordinary Exhibition/two-player startup and Top to Menu remain accepted by the
user. The two new Exhibition result actions, Rematch and Select Team, reportedly
stay under loading. V57 retains the accepted native final footer exit and
per-side, identity-checked Game Plan snapshots; it does not skip native teardown.

Two reproducible wrapper gaps are corrected:

- The custom frontend readiness receipt and old result cleanup were below a
  return for an absent stock root. The custom frontend does not require those
  legacy nodes. Once native `MyClubMain::SetupWindow` has completed, the queued
  local request retires old result/cursor/editor/search state before that optional
  node lookup. It becomes consumable by the next P1 update only while the new
  frontend controller gate is active.
- The wrapper parks TutorialMatch at state 9 to suppress its native proceed
  event. A fresh explicitly requested bootstrap on a reused parked object had
  no branch back to initialization, leaving the native 0..8 dispatcher idle.
  States 0 and the wrapper's own parked 9 now enter state 3 when a fresh request
  exists. Unrequested startup and native in-progress states remain unchanged.

The request is dispatched once; unsuccessful bootstrap admission leaves the
menu available and clears its bootstrap mode. Release journal notes distinguish
request, native frontend receipt, selection dispatch, bootstrap dispatch, and
initialization. These are ownership/progress events, not timer-based loading
completion or hardware proof of successful re-entry.

Actual-source host replays reuse the same native-flow buffer for three matches,
wait for an initially absent flow listener, initialize fresh squads, preserve
team IDs, and verify no duplicate dispatch. A second harness checks frontend
gating, cleanup, both controller modes and unavailable bootstrap. Existing
native result/footer, transactional Game Plan and handoff tests remain.

## Referee and Stadium

[Referee presentation](REFEREE_PRESENTATION_V57.md) places the optional actor at
the requested near centre-circle intersection, holds its native whistle pose,
consumes stale signal serials, hides it during replay/demo, and publishes a fresh
valid pose before revealing it again. Native entrance officials remain native.

[Stadium target selection](STADIUM_CAMERA_TARGET_V57.md) corrects only the live
normal-STADIUM acquired target to the actual ball already sampled by native
code. Pan, zoom, bounds, smoothing and final camera construction stay native.
V2 stays suspended; other cameras and presentation owners retain native paths.
This is not complete removal of every native future-vector branch or an exact
FL26 camera executable transplant.

## Remaining port scope

[The scoreboard contract audit](SCOREBOARD_FL26_CONTRACT_V57.md) documents
incompatible PC/Mobile instance paths, events and atlas ownership/size. No raw
PC scoreboard is installed and no recolor is described as a port of animation.
An atlas/layout/keyframe adaptation retaining Mobile scripts is a separate step.
Assistant models/props exist, but validated live assistant movement, flag
attachment/animation and lifetime integration are still missing. Two extra
actors and a full PC referee controller are not included.

[The per-team commentary workflow](PLAYER_COMMENTARY_BATCH_V57.md) has an active
thread heartbeat, `commentary-pemain-per-tim`. It audits the active catalog,
validates player identity and stages exact source calls serially with resume
receipts. Staged/desktop-decoded recordings are separate from runtime integration
and Switch playback. The accepted two-player bank is retained; a wider port
must respect cue-index, graph, memory, mount/unmount and fallback contracts.

## Delivery and device check

The isolated v57 production build uses the accepted v54 private input pair
`e861c583ec78e9ae` and 53,248-byte dummy OBB expectation. StartupRenderAudit,
Diagnostics, NearCameraTrace and PerfTrace are disabled. No face budget/PAK,
accepted referee bank, commentary audio, active runtime or source CPK changes
are required. The package preserves v54's three non-NRO payloads byte-for-byte.

Copy the ready package's `switch` folder into the SD root. First test kickoff,
a goal then kickoff, replay/demo hiding and return. Test normal STADIUM keeper
catches/backpasses at both ends and possession changes in one/two-player modes.
Finish an Exhibition, select Rematch, then finish again and select Select Team;
also check Top to Menu. Preserve `scene-runtime.log` after a failure; its v57
header and bounded `local rematch` notes identify the last completed boundary.
Keep the previous NRO as rollback. Local tests do not establish device playback,
subjective camera acceptance, or a locked 60 FPS result.

The 21 October production build completed successfully. The local ready-copy
folder is `local-debug/match-followup-v57/FootballNX-v57-MATCH-FOLLOWUP-SIAP-COPY`
with a sibling ZIP. `CANDIDATE-SUMMARY.json` pins the delivered NRO and ZIP;
the package's `VERIFICATION.json` records source/input identities and protected
payload hashes. All three ELF load segments match the NRO, and ZIP CRC, member
inventory and every unpacked payload hash pass. The focused host suites passed
112 tests and 92 subtests, with two unavailable optional fixture tests skipped.
Hardware validation of this candidate remains pending.

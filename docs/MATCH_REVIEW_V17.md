# Preset, Anfield camera and referee candidate v17

Follow-up to the device feedback on [v16](MATCH_REVIEW_V16.md). This is a
candidate build, not confirmation of 60 FPS or every native camera on Switch.

## Preset flow and identity

- Save -> slot -> overwrite confirmation only for an occupied slot -> success
  popup -> OK/Back returns to the Save/Load root.
- Load -> slot -> confirmation -> success popup -> OK/Back returns to that
  same root. Cancellation returns to the selected slot without changing data.
- An empty/unreadable slot or a failed write uses an error popup; dismissing
  it returns to the slot list. No failure is reported as success.
- Popups dim only the owning player's panel, retain the slot list behind them,
  and use the existing sprite art. Left/Right selects confirmation or Cancel;
  each controller retains its own state.

Exhibition/2P presets previously persisted the runtime's encrypted, session-bound
16-byte player IDs. The V2 file envelope stores canonical native IDs instead,
scoped to the compiled migration build ID. Loading maps every saved identity to
the current team's fresh native ID before any lineup changes. This prevents
cross-session crypt keys from making a newly saved slot unreadable, and rejects
unrelated roster builds instead of reusing numeric IDs across migrations.
Master League retains its existing career-scoped canonical representation.
In-memory Rematch snapshots retain their session-local format.

V1 files remain readable only when their original IDs still match exactly.
They are not decoded with a new session key or guessed from a reused slot.
Older unreadable presets need saving once again. Physical slot presence still
requires overwrite confirmation even if a file is old, corrupt or belongs to
another roster build. Alternating copies, checksums and read-back verification
remain in place; a corrupt newer copy can fall back to the last valid copy.

## Anfield camera clearance

The fixed six-metre, low-camera sphere did not cover walls farther from the
lens. Materials now also test whether a fragment lies before the pitch/player
apron along its camera ray. The protected volume is +/-58 m by +/-40 m,
from -0.5 to 2.6 m vertically. Imported shell fragments blocking that volume
are masked; shell beyond it remains visible. A surrounding lens clearance
also grows with the camera's horizontal distance outside the regulation pitch
plus six metres. This clears the foreground wall around the composition,
instead of opening only a player-sized hole. Camera height does not inflate
that radius, so an aerial view does not erase the stadium bowl.
This applies to all 44 imported shell materials and both mobile shader levels.
No native pitch, player, goal, camera path or world transform is modified.

`tools/audit_stadium_camera.py` casts through every shell layer, not just the
first/back-facing polygon. The local converted mesh audit covered 30,240 rays:
both goal ends, all corner/side quadrants, 3-40 m camera radii, 1.6-32 m camera
heights, and feet/torso/head targets. There were 6,101 obstructed rays without
cutaway, 5,362 still obstructed under v16, and zero uncleared fragments under
v17. Unit checks also retain far stands and rays looking away from the pitch.

The native sixteen-frame crowd sheet remains unchanged. The cooked material
shaders passed 3,696 GLES2/GLES3.1 compilation checks and all 221 PAK entries
round-tripped byte-for-byte. This establishes geometry/shader coverage, not
device acceptance of every celebration composition, cutaway edge or GPU cost.

## Referee performance

The supplied Fine-weather log contains roughly 17-20 ms average presentation
intervals, but no v15/v16 follower CPU summary: normal out-of-play transitions
did not invoke its suspension flush. The log alone cannot distinguish native
rendering cost, GPU time and wrapper CPU work.

The existing name renderer now projects the optional referee's scalar position
using its current native camera. A 20% viewport margin and observation younger
than 50 ms allow the follower to skip pose evaluation/publication while fully
off-screen. Position/ball tracking continues; a complete fresh pose and transform
are published before showing the model again. Visible poses keep native frame
cadence. Missing/invalid/stale projections, kickoff readiness, native referee
demo placement and goal celebrations fail open to normal rendering. Only
atomic scalar values cross threads; no HUD/native model pointer is retained.

Repeated SD writes for native whistles, out-of-play records and already-active
model-manager notifications are removed. CPU timing snapshots are published
in memory once per 60 updates and at suspension. The overlay writes the latest
snapshot beside its existing presentation summary at a break, including the
off-screen count. This excludes native asynchronous drawing and GPU work.
No new native hook, model reload, guessed LOD patch or shared player buffer is
introduced. The probe still requires the user's existing enable token.

Host scenarios verify unchanged full-rate visible publication, no uploads for
120 off-screen updates, current movement, fresh-pose re-entry, stale-camera
fallback, demo/kickoff exclusions, duplicate callbacks and scene teardown.
Projection tests cover signed world coordinates, viewport margins, unavailable
HUD, missing callbacks, nonfinite dimensions and time regression.

## Delivery and remaining device checks

The local v17 package updates only the NRO and Anfield PAK on the tested v16
runtime (`e861c583ec78e9ae`, 53,248-byte patch OBB). Existing face/skin, Weather,
StadiumPerimeter, FootballNX.assets and LooseCpk data stay with that runtime.

Test Save/Load across a full game restart, cancel/overwrite with both controllers,
celebrations at each corner and behind both goals, and fast passes in Fine with
the probe enabled. Verify referee re-entry during fast pans and compare frame
pacing with the same scene without the probe. No 60 FPS guarantee follows from
host tests. The package includes hashes and installation/rollback instructions.

## Verification record

The release NRO built successfully with the paired local roster/catalog inputs
and Windows devkitPro toolchain. ELF segment, migration build-ID and launcher
icon verification passed. UI previews exercise the production renderer and
include confirmation, success and error states for both sides.

The project-wide run reported 684 passed, 14 failed, 51 skipped and 55,358
subtests passed. One failure was the older preset test harness, which lacked
the new completion helper/slot-presence field and expected the previous return
to the slot list. That harness was updated to test the requested success-popup
flow. The other thirteen failure names match the pre-existing v16 baseline
(catalog/identity expectations, old menu assertions and pause harnesses).
Windows Unicorn again printed its baseline access-violation diagnostics while
the overall test process continued. Focused checks passed after the harness
repair. The final surrounding-wall clearance adjustment also passed its
focused camera tests and the mesh/shader audits. The whole suite was not
rerun after those final changes.

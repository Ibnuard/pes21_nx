# Match review candidate v16

Checkpoint `5201160` was pushed before this work. This candidate addresses the
subsequent stadium, referee, Game Plan, realface and local match-result review.
It is not a Switch performance or visual acceptance result.

## Game Plan and set-piece selection

Formation, shape selection, presets, position assignments and the in-match
taker/thrower picker use the same white, navy, blue and cyan presentation as
the custom front end. The renderer is in `source/gameplan_panels.inc`.

Rows use role-colored plates, actual native portrait IDs and a dedicated
[generated sprite atlas](../art/gameplan/README.md). Both boots remain visible;
the nondominant foot uses 20% opacity. Missing portraits use a bust sprite
while the existing asynchronous portrait queue resolves the asset. No native
object pointer crosses into the overlay, and no synchronous portrait file
read is added to the drawing loop.

The centered set-piece panel is 60% of the screen width. Its height follows
the visible row count, up to seven rows, with the controller footer directly
underneath the list. One-player and loading states also shrink. In the
two-column Game Plan, panel heights remain aligned with the opposite team.
Full controllers and single Joy-Con input hints follow the active controller.

`tools/preview_gameplan.py` runs the production drawing code against synthetic
menu state at 720p and 1080p. Local portrait samples can be supplied with
`--player-samples`; their presence does not make these previews device captures.
Geometry canaries check buffer limits, finite coordinates, state isolation and
the opacity of both foot sprites.

## Exhibition and two-player results

Only the final result page of a locally started Exhibition or two-player match
offers Rematch and Select Team alongside Back. Cup, League, Master League,
half-time and extra-time decisions retain their own routes.

At match setup the wrapper copies both starting squads, two tactics, formation
coordinates, settings and position assignments by value. Rematch exits through
the normal native result flow, waits for a fresh main menu, starts the matching
local mode and restores both snapshots before kickoff. A backup of the fresh
Game Plan makes restoration transactional: failure on either side restores
both sides and leaves the prematch hub available. A missing backup prevents
any snapshot application. Identity and bounds are checked before roster writes.
Select Team returns to the selector for the same local mode.

`tests/test_gameplan_rematch.py` exercises the actual extracted snapshot,
restore and rollback functions with a host fixture. Native scene teardown and
re-entry still require a full-time match on Switch.

## Referee transitions

The optional referee probe retains its independent render resources, full-rate
pose updates and 15 Hz neighborhood evaluation from v15. It is not enabled by
installing this candidate; the existing probe token controls it.

Two guarded native observations provide transition context. A fresh native
center-referee position from a demo scene is accepted only when the demo's
actor table contains that referee. Player/assistant entries, absent actors,
out-of-range values and expired samples are ignored. Scalar snapshots cross
threads through a bounded atomic sequence check; no native scene pointer is
retained. Protest scenes can therefore place the visual referee at the native
scene position while the wrapper continues its own animation handling.

Kickoff reset arms a pending relocation. The wrapper applies it only after
the native fade-out reports completion, placing the referee beside the center
circle. It holds the ready pose until the ball has been observed at the center
and then leaves it. The model and animation bank are not reloaded. Host tests
cover visible versus hidden relocation, demo expiry, teardown, and the existing
update cadence. This is not a complete port of EF10 referee AI.

## Anfield close-camera visibility and crowd

The converted shell keeps its existing geometry. Its 44 materials now mask
fragments within six meters of a camera below twelve meters, so nearby stand
geometry can clear the low celebration camera. The rule is in
`tools/stadium_material_policy.py`; it does not change the normal high camera.
The offline ray audit supports this approach but does not reproduce every
native celebration camera. Masked-material cost and edge visibility need a
device comparison.

Crowd strips sample the owned native 1024-pixel atlas: sixteen vertical frames
at eight frames per second. Frame selection happens in the material, with
inset frame coordinates to avoid bleeding. The previous synthetic motion is
removed. The atlas keeps its native animation frames rather than a single
static crowd row. No new crowd geometry or per-frame CPU update is introduced.

The Android ETC1 cook contains both GLES2 and GLES3.1 material maps. All 44
materials passed 3,696 extracted shader compilation checks. The local PAK is
limited to the converted Anfield namespace; native engine assets remain out
of the package.

## Realface/body palette matching

`data/barcelona_skin_profiles_v1.json` records an explicit policy for the
twenty combined-face identities. The local staging pass changes fourteen
appearance bytes, leaving the accepted Yamal and Raphinha choices in place.
The master player registry, BaseId mapping and all other CPK members remain
unchanged.

`tools/audit_skin_palette.py` measures a neck region and the native body palette
in Lab color space to suggest the closest available palette. It does not edit
face textures. `tools/patch_player_skin.py --profiles` applies reviewed choices
only when BaseId, native ID, fingerprint and accepted appearance-row hash
match. Reapplying a profile is idempotent. Three old face-inventory height
fingerprints were reconciled explicitly against the canonical identities and
recorded in the policy; a reused native ID alone never authorizes a patch.

Six native body palettes cannot eliminate every texture seam. Day/night kit
lighting and close-up neck/arm transitions still need visual acceptance. The
policy is an explicit regeneration step, not an implicit donor-slot heuristic.

## Local delivery and validation

The partial update is staged under ignored
`local-debug/review-v16/release/FootballNX-Review-v16/`. It contains the NRO,
Anfield PAK and the paired LooseCpk archive/manifest. It does not contain an
OBB or another copy of the Barcelona face PAK. Installation details and hashes
are provided in the local package.

The native release build completed and its launcher icon matched byte-for-byte.
Focused tests cover the UI, result flow, rematch transaction, referee lifecycle,
skin policy and stadium material rules. The NRO also matches the accompanying
ELF segments and compiled roster build ID. All 221 stadium PAK entries match
the cooked sources byte-for-byte; 2,840 CPK members were compared, with only
the appearance member changed. ZIP contents and checksums were verified.

The project suite (`python -m pytest tests -q`) initially reported 678 passed,
16 failed and 51 skipped. Two new failures were extraction harnesses missing
the newly shared snapshot/restore helpers; these were repaired without changing
the runtime. The previously failing result-exit harness was updated to the
competition callback and now checks both new actions through the native footer.
The follow-up run of the five affected modules passed all 38 tests. The thirteen
remaining failures match the previous baseline (catalog/registry expectations,
older menu assertions and pause harness dependencies). The whole suite was not
rerun after the harness-only corrections. Windows Unicorn also emitted the
same access-violation diagnostics seen in the baseline, although the process
continued; that host result is not hardware evidence. The public-tree audit
passed for 771 files, and `git diff --check` passed.

Switch checks remain necessary for
celebration occlusion, animated crowd, protest and goal transitions, rematch in
both controller modes, neck/body color and frame pacing with the optional probe.

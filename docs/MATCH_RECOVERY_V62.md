# Match recovery and presentation v62

Device follow-up: [v63 commentary snapshot fallback](EXHIBITION_COMMENTARY_FALLBACK_V63.md)
addresses a confirmed optional-commentary rejection after this hub admission.

The v61 device report still had unusable Rematch substitutions, an empty hub
lineup labelled Open Game Plan, and a Main Menu frame between result and hub.
It also showed the extra referee running to the centre-circle position after
an opponent goal. This follow-up changes the actual admission boundaries.

## Fresh hub and native squad conversion

V61 prepared squads on Play, after publishing the hub from TutorialMatch.
That publication only queued the native MatchSearching host; it did not prove
that its team records and initialization had finished. The new admission point
is the existing SearchWindow post-update callback after both matching records
are available and the native refresh has run. Preparation happens once there,
before releasing the cover or exposing the starting XI.

The compatible native LoadSquadDataFromMatchPlanData returns a boolean. It
returns false before conversion when UtilityCommon::GetMatchMySide returns
NONE (2). That utility compares the current ParameterCommon user ID against
the Match HOME and AWAY user IDs. The old wrapper declared the loader void,
so this early refusal could leave an earlier SquadEdit available to callers.

Fresh preparation now binds HOME to the current local Parameter user ID
immediately before native conversion and requires its successful return. It
does not hook or force GetMatchMySide, overwrite the native transition queue,
or recycle a live match's SquadData. Both sides must contain eleven starters.
The current prepared squad order supplies hub names; the old registry's order
table is not used for that prepared view. The existing identity hydration,
deep-copy rollback and selected-roster commentary barrier remain in force.

Rematch plan restoration runs after admission. A successful restoration can
continue automatically; failure retains the new hub for editing. A refused
native conversion is logged and releases the loading cover to a usable setup
instead of manufacturing readiness or retaining an indefinite spinner.
Select Team reaches the same fresh-host preparation on its next fixture.

An explicit cover spans the entire result -> native frontend -> new hub or
selector transaction. The internal Main Menu remains available to the native
lifecycle but cannot become the visible custom frame during that handoff.
The cover releases after the target has published its state and lineup.

Tests execute the actual post-update, preparation and admission functions over
three sessions with reused native objects and changing local user IDs. They
cover unavailable matching records, an owner changed by native setup,
once-only load, a rejected conversion and current XI order after a substitute.
The native byte investigation used the already identified compatible local
ELF and format-aware symbol/Capstone inspection. It did not execute the game.

## Result exit confirmation

The result's B shortcut and its Top Menu card open the same modal. Cancel is
selected initially. B cancels; A on Cancel stays on the result. Only an explicit
navigation to Confirm followed by A dispatches the native exit/footer route.
Rematch and Select Team remain their own actions. New result surfaces and new
pre-match sessions clear obsolete confirmation state. The legacy postmatch
root uses the same policy and the existing production modal renderer.

## Selection grouping

The selector presents the union of Other Asia and North American/MLS club
groups as `Other Asia & American Clubs`. Canonical categories, team records,
league membership, IDs, fingerprints, save data and commentary are unchanged.
The projection removes duplicate IDs inside the union and preserves every
selectable team. It applies to the team-selection UI only.

## Referee, pitch and scoreboard

[Kickoff publication](REFEREE_KICKOFF_V62.md) now distinguishes a completed
warp from an actual live kickoff snapshot. It retains the placement through
replay and stale goal-end ball samples. The approved motion bank is unchanged.
Live assistant referees remain an integration gap: appearance assets exist,
but the inspected Mobile live movement/animation exports are stubs. A live
controller, flag attachment/animation, actor lifetime and device cost are not
established by the entrance models or PC class names.

[Pitch mowing](STADIUM_PITCH_MOWING_V62.md) differentiates six imported stadiums
in the existing audited shaders. The latest human directions set Camp Nou to
concentric circles and Old Trafford to alternating straight bands. Konami
retains its accepted pattern. No new texture samples or draw passes are added;
the shader change still needs appearance and frame-pacing acceptance on Switch.

[Spain scoreboard work](SCOREBOARD_SPAIN_CANARY_V62.md) is an authored Mobile
adaptation included in the test candidate's consolidated FootballNX.assets.
The latest text reference supplies a rectangular three-column, two-row layout:
white mark on red above the clock, native team initials in the centre, and
stacked scores on white. It retains native scripts and bindings; reveal/fade
motion is authored for Mobile, not imported PC executable animation. Other
league packets are unchanged. Complete league-wide FL26 layouts and device
event/motion acceptance are not claimed.

## Candidate boundary

The isolated candidate retains the pinned roster, commentary metadata and
full-loose runtime pair. Commentary/audio and the approved referee motion are
byte-identical to v61. Optional assets stay in FootballNX.assets. Active dist,
OBB, CPK, face PAKs, saves, proprietary inputs and unrelated dirty work are not
modified. A successful host run/build is not a successful Switch Rematch.

Device checks: direct hub Kick Off; finish -> Rematch -> live Game Plan reserve
selection; finish -> Select Team -> another pair -> hub XI -> Game Plan swap;
result B and Top Menu card cancellation/confirmation; both teams scoring then
kickoff; and the requested pitches in Day/Night, followed by Konami. Keep the
new scene journal if a step fails: it identifies native load refusal versus
host admission and records XI/bench counts before the cover releases.
For the Spain candidate, check both team initials, clock/added time, score
updates, goal/replay transitions, and restoration on a following non-Spanish
fixture. Copy both NRO and FootballNX.assets from the ready-copy package.

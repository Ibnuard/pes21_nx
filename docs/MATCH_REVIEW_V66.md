# Match review v66

The v65 source checkpoint was committed and pushed as
`6b4a863b384bf2cb7cc9ce175b3befbd101d1778` before these review changes.
V66 is a separate device-test candidate. Its source preserves the v65
match-local HOME/AWAY identity and two-sided structural publication gates.

## Reused Game Plan

The custom hub omitted the stock native pre-match initialization of reused
editor and plan owners. V66 calls the native common-data initializer,
complete additional-data constructor and pre-match editor mode utility once
per new fixture. The constructor initializes six change records and forty
player-info records; calling its Init method alone would leave those arrays
stale. Reopening a prepared plan does not reset edits, and live Pause
substitution limits remain native. See
[the lifecycle evidence and regression boundary](PREMATCH_FIXTURE_LIFECYCLE_V66.md).

This corrects a source-confirmed missing lifecycle consistent with the bench
failure after Rematch/Select Team. It does not establish which retained field
caused the reported device failure or prove that the complete device flow
now succeeds.

## Referee replay and goal restart

Recorded Replay Init/Main now hide the optional actor synchronously, before
the original callback, rather than depending on another live object-list
draw. A distinct lifecycle owner lasts until its matching Replay End or model
teardown. Input heartbeat timeouts remain unchanged. Returning to live play
keeps the actor hidden until a complete pose and transform have been published.
Ordinary out-of-play/foul demos do not enter this recorded replay policy.

The optional offside layout check compared the native registry/fixed-info
instruction pair at the wrong offset. The compatible owned ELF contains that
pair at `+0x0c`, not `+0x10`. The corrected guard admits only the verified
layout; replay hiding remains independent of this optional admission.

A goal warp can precede both the ball and MatchInfo read snapshots. A native
stopped KICK_OFF edge now recovers the requested `(0,0,9.15)` placement after
a stale IN_PLAY sample, without rearming every stopped frame. A missing
borrowed snapshot retains the last known stopped hold; an unsupported layout
without such an observation keeps the established ball fallback. Native
whistle contact remains planted. Both scoring sides and goal ends are tested.

The actual replay wrapper/publisher tests cover sparse draws, a paused replay
past the input timeout, mismatched Replay End owners, missing registry reads,
fresh-pose publication before redisplay, ordinary restart kinds, and teardown.
Optional owned-ELF checks verify the admission instructions and actual replay
vtable relocation installation. These are bounded host/static checks, not
complete native game execution. The animation bank and token are unchanged.

## Compact league scoreboards

The subsequent England device feedback and asset-only correction are recorded
in [the v68 review](SCOREBOARD_ENGLAND_REVIEW_V68.md). It supersedes the England
name compression and lower added-time placement described below.

`tools/build_fl26_scoreboard_profiles.py` builds four source-backed Mobile
adaptations from the pinned owned UI inputs:

| Theme key | League | Main plate at 1280 x 720 |
| --- | --- | --- |
| 9 | England | 306 x 64, horizontal green score cells and central lion |
| 10 | Italy | 320 x 60, blue horizontal bar and diagonal score centre |
| 11 | Spain | 164 x 88, stacked text reference, reduced from 246 x 132 |
| 12 | France | 164 x 110, full-height league mark and lower clock tab |

Each keeps the measured physical anchor `(38,32)`. Auxiliary score fields
sit below the plate, with the whole native card, goal and substitution content
timelines translated below that band. Labels, scripts, frame endpoints,
bindings, flags and movie identities stay unchanged. Native team initials
and digit selection remain dynamic. No fixed club names are baked in.

The compact score fields use authored reveal/stagger placement adjustments.
Event enter/reveal/member-swap/exit motion remains the Mobile event lifecycle;
this is not a claim to import the complete FL26 PC animations. The four
designs differ in geometry and artwork, rather than only changing colour.

The builder verifies all edited fields remain inside separate cells, including
one-, two- and three-digit minute layouts, bounds sparse source crops, and
rejects unexpected input hashes, unrelated movie changes or packet overflow.
Actual host sample PNGs for all four themes were inspected. Their text is a
sample composition; native fonts, playback, penalties, aggregate, event timing
and next-match restoration still require Switch checks.

## Packaging and device checks

The candidate merges only four approved scoreboard packets into
`FootballNX.assets`. Every other member, including accepted Yamal/Raphinha
audio, roster audio, referee motions and the token, remains byte-identical to
v65. Actual C packet admission rejects truncated/corrupt/wrong-source inputs;
the C archive reader reads every member and checks caller bounds. Production
build source and private inputs are frozen and checked again after the build.
The active `dist` runtime and proprietary source archives are not modified.

Copy both the NRO and consolidated assets in the ready-copy `switch` folder.
If an old loose `Scoreboards` folder exists, rename it to `Scoreboards.backup`
so its overrides do not take precedence over the new archive packets.

Check a fresh match, then Rematch and Select Team, swapping a starter with a
reserve from each new pre-match hub. Confirm edits survive reopening Game
Plan and that live Pause substitutions retain native limits. Score from both
sides; check the circle-edge kickoff stance and planted whistle. Check replay
and offside hiding while ordinary stoppages keep the referee visible. Check
each scoreboard's timer, score, substitution, goal, added time and return to
another fixture. Device acceptance and FPS are not established by host tests.

# Manager League device review v95

The user authorized the Switch build after reviewing the final previews. The
isolated production build has completed; its package receipt is recorded under
`local-debug/manager-review-v95/FINAL-VERIFICATION.json` after sealing. Switch
device acceptance remains pending. The v94 delivery and its frozen production
inputs remain untouched.

- The introductory messages have one informational Continue action. Back does
  not dismiss an unread message; ordinary destructive confirmations retain
  their two actions. The footer shows only the current introduction action.
- Manager Game Plan renders and accepts input for one centered club. The
  second native bootstrap squad remains an implementation detail; it is never
  presented as a known opponent. Formation, roles and presets use the existing
  editor panels at the same centered origin. Exhibition and two-player layouts
  keep their existing behavior.
- The sealed-pack page exposes no player rows, names or portraits. Opening
  uses an entrance overshoot, anticipation squeeze/shake, foil sweep, release
  flash, particles and a fan of card backs. A separate reveal phase folds only
  the card backs; portraits and names appear at their normal aspect ratio.
  The selection page becomes interactive after every card has settled, at
  3.4 seconds. Selection still requires an explicit Confirm;
  cancelling opening or selection charges nothing. Confirmed cards are centered.
- News projects actual saved pack receipts, completed fixture results for all
  clubs and registered squads. Scheduled results cannot leak into the feed.
  Stories open a replay or the relevant club. Other managers' purchase records
  must eventually come from the authoritative API journal; the offline view
  does not invent those transactions or silently mutate opponent squads.
- Match Centre has six cards in two columns, with both crests, score/status,
  date, time and round. D-pad navigation follows the grid. It includes upcoming,
  live and completed broadcasts; it is not just match history.
- Manager footer sprites and visible capital glyphs share the exact center of
  the footer bar. Other established front-door footers keep their prior origin.
- The dot tape has a legal initial kickoff shape and a visible backward pass,
  carrier movement, delivery to named actors, pass/shot endpoints and dead-ball
  holds. Goals return continuously to a new kickoff. Saves reach the keeper;
  substitutes leave via the touchline. The half-time change of ends is animated
  rather than a coordinate reflection. Sampling is deterministic and independent
  of the time a viewer opens the broadcast. This remains a scripted offline
  fixture, not a new tactical or physics simulation.

## Native audio evidence and candidate

The supplied v94 scene journal identifies build
`256b88922fd8c53453f66815012368094e5641a9`. It records the private bank mounting
successfully and all requested crowd, contact and speech cues returning zero
with handles. The user hears none of them. Queue admission therefore did not
establish voice playback or audible output.

REA opened the pinned native ELF, SHA-256
`a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`.
Native function analysis was unavailable: the Windows server had no compatible
configured provider for this ARM64 ELF. Existing source-bound host probes and
ordinary local ELF inspection were used instead; these are not REA decompiler
or device evidence.

The candidate stages `Audio/manager-league-v95.acb` (1,816,192 bytes, SHA-256
`0fdc132e090d61a2f23daca8cff76dfe0fc1927a8a148ef564b7babe359a73d3`).
It replaces the unverified direct-MasterOut send with the native trophy music
bank's explicit MasterOut=0 and BUS8=1 route. Recordings, waveform metadata,
cue-local gains, event graph and ACF binding stay byte-exact. No global category,
playlist, pool or device is changed. This is a routing candidate, not a confirmed
root cause or a claim that sound now works on Switch.

The native owner now records bounded status and playback position observations
in `manager-audio-runtime.log`, retaining one prior log. Six complete native
binding bodies, including GetPlayPosition, are guarded before executable aliases
are called. Kickoff speech is admitted once for a current Live kickoff; late
joins, seeking and Replay cannot replay historic speech. Replay retains only
supporter and ball audio. Device audibility remains a required acceptance test.

## Pitch follow-up

Konami supplies the light-left/dark-right midfield reference, not one shared
stripe count. Anfield has 20 bands, Stamford 22, Old Trafford 14 and Signal Iduna
12. The user's later review takes priority for Old Trafford and Signal Iduna:
their strips are uniform at 7.5 m and 8.75 m respectively, with no narrow/wide
groups near the boxes. Their goal and halfway boundaries align; penalty fronts
can cross a uniform strip. Anfield/Stamford use small piecewise spacing changes
to align halfway, penalty fronts, six-yard fronts and goal lines. Etihad retains
  a checker pattern with three base green levels, formed by additive horizontal
  and vertical mowing contributions; Camp Nou retains rings.

The shared Stamford green and fixed worn patches apply to all seven supported
pitches, including Konami. Paint, native texture/detail operations, alpha,
lighting and weather remain preserved. Mathematical top views omit actual
native lighting and fine grass detail.

## Verification

Focused host checks cover ownership after a two-player session, onboarding and
purchase rollback, hidden contents before opening, manual selection, grid
navigation, other-club stories, new-process archive persistence, deterministic
continuous motion, kickoff legality, dead balls, goal restarts, native ABI and
bank integrity, Replay speech suppression, pitch spacing/anchors and paint
preservation. Native C renderer previews exercise the draw/vertex budgets.
They do not establish Switch rendering performance or audio audibility.

The v95 production build completed with build ID
`b4618019bfba064e0c0d81a972a73e614033c069`. The reviewed host checks passed
26 tests and 104 renderer subtests. ELF/NRO load segments, launcher artwork,
the paired 24 CPKs and every ZIP member hash were verified. The ready-copy
ZIP is 397,025,727 bytes, SHA-256
`13611fc798f507a950e8b33551caf3785d1d7cb1fce361e9827865bc8011dab1`.
The binary package remains local; hardware acceptance is still pending.

# Replay-only referee visibility and local result admission v58

The user reports that v57 hides the extra referee during ordinary ball-out and
foul actions, and that Rematch still remains under loading. The supplied v57
journal completes native frontend teardown and records a dispatched bootstrap,
but no second bootstrap initialization. The log is preserved with its hash in
`local-debug/match-followup-v58/evidence/INDEX.json`.

V57's referee visibility classification was too broad: generic demo/skip
ownership also covers throw-ins, fouls and set pieces. V58 hides the extra
actor only for the native ReplayMode lifecycle. Ordinary stoppages keep the
actor; pause may retain its current pose. Match intervals and actual stadium
teardown still follow their established lifetime. Replay return retains the
fresh-pose-before-display rule, and the accepted kickoff stance is unchanged.
The actual-source regression exercises replay separately from each generic
demo flag, including pause/cursor overlap and set-piece controls.

[Native transition admission](LOCAL_REMATCH_FLOW_V58.md) retains a Rematch or
Select Team request until the previous transition is idle and its native queue
is empty. SetupWindow completion alone did not establish that boundary. Only
then does the wrapper dispatch once. It never forces a native queue/step,
waits an arbitrary duration or repeats an admitted request. Compatibility
guards disable only these new actions if the audited contract differs.

This remains an automatic native teardown and new-match route. The user does
not manually enter Home. It is not an unproved in-place restart of the running
match. The native queue hazard is established by local binary inspection and
a focused instruction oracle; the submitted journal does not uniquely prove
the internal stalled state. Successful hardware rematch remains to be tested.

The isolated production candidate retains v57's input pair, Stadium camera,
renderer, face packages, referee animation/token and accepted Yamal/Raphinha
bank. Wider commentary staging is complete and has a separate active
automation. No wider commentary payload is included in this gameplay fix.

Device checks: ball out, throw-in, goal kick and a minor foul should retain the
referee; an actual replay should hide it and return it with a fresh pose.
Finish Exhibition, choose Rematch, finish again, choose Select Team and start
another match. Repeat with two controllers and check ordinary Top to Menu.
Preserve the v58 scene journal if it stops: request, frontend receipt, native
idle wait, dispatch and initialization are distinct bounded notes.

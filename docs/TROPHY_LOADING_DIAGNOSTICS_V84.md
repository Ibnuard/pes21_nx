# Cup-final trophy loading diagnosis, v84

The latest supplied journal is from build
`787a93698540d331314842fa893fb60cba450628`, matching the verified v83
NRO and ELF. The enclosing delivery directory's v81 name does not identify the
executing build. The final snapshot passes, the overview is held and a trophy
candidate is created. After 3,108 ms it is released as `candidate-finished`.
No first-cut Start or bound-prop readiness event appears. The user reports
leaving the controller untouched after full time.

This establishes that v83's team-key admission correction is active. It does
not establish why the native manager terminates. The old journal conflates
native terminal state 4 with successful playback, including termination before
Start. Native Exec has a separate environment-suppression path and Skip paths
that can terminate without starting. Those paths are possibilities, not a
device-observed cause.

The adapter now distinguishes terminal-before-start, explicit/native Skip,
failure and native completion. A terminal-before-start outcome still follows
the native destructor, ordinary background and overview route and never counts
as ceremony success. Current-owner observations record changes to native
manager/cut states, start permission, native Skip, queued Skip, cut existence,
load bits and the suppression byte. Unchanged frames write nothing; each
candidate allows at most twenty state observations. No cut/renderer pointer is
followed. No native load/state/readiness or suppression field is modified.
The environment getter is added to the pinned ABI checks.

The supplied journal's abbreviated lifetime is reproduced in a host fixture:
terminal state before Start releases the overview with an unconsumed success
latch and an explicit failed-before-start reason. Repeated-state, bounded-log
and borrowed-byte preservation checks supplement the existing actual-C
adapter lifecycle tests. These checks do not reproduce the engine's cause or
prove trophy playback. Native inspection used bounded local Capstone probes;
the REA native decompiler remains unavailable on this host.

v84 is a diagnostic candidate, not a claimed visual fix. It changes only the
NRO from the verified v83 delivery. All thirteen other runtime files, including
the enlarged added-time scoreboard assets, all 1,638 heads, 436 body corrections,
cinematic CPK/manifest/marker and trophy props remain exact. No recook or active
runtime installation is required.

Next device evidence: win a standalone Cup championship final, leave controls
untouched through the transition, then retain `trophy-runtime.log` and
`scene-runtime.log` before relaunching. The bounded `candidate-state` and
`candidate-terminal` events determine the next correction. Do not disable
readiness gates, invent successful playback, or force a native MatchTop state
to make the journal appear successful.

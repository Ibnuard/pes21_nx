# Exhibition commentary snapshot fallback v63

Superseded by [v64 selected-team publication](EXHIBITION_SELECTED_MATCH_V64.md).
The later device log identified a structural HOME member-count failure at
stage 4. Allowing that failure through this fallback produced an invalid match;
v64 repairs the selected Match publication and blocks structural failures.

The v62 device journal admits a fresh ordinary Exhibition with XI 11/11 and
bench counts 17/23. Every subsequent Kick Off is followed by `roster snapshot
rejected; retained setup`. This establishes that the optional selected-roster
commentary snapshot is blocking Play after successful squad preparation. It
does not identify which snapshot field failed: v62 collapsed all capture errors
to that one line. No carrier, owner or fingerprint check is weakened to guess
that missing detail.

V63 retains the strict capture and generation admission. A rejected snapshot
invalidates only the optional roster intent and uses the accepted baseline
name path for that fixture. Under the existing short policy lock, its typed
lookup permits only complete, pinned native or accepted canary owners; new,
held, unknown, missing-side or mismatched-runtime owners return NULL. The
native fallback route omits their name. No unproved selected bank is accepted,
no generated cue is returned, and no replacement audio is fabricated.

Ordinary Play can then dispatch the existing Strategy transition after its
normal squad commit. If a previous optional native request is still draining,
Play waits for that real drain and resumes once from the game-thread tick.
It does not issue a duplicate request or release native mount buffers early.
Starting a new fixture or returning to the selector clears the scoped fallback;
stale completions cannot reopen the previous hub. Successful roster snapshots
keep the existing selected-bank reload and mount proof.

The new journal records the capture stage, side and index once for a fallback.
Stages are 1 missing getters, 2 missing Match, 3 missing team, 4 invalid count,
5 player-record layout, 6 full carrier mismatch, and 7 canonical selection.
An absent side/index is UINT32_MAX. This will distinguish the remaining
device data discrepancy without logging raw pointers or player payloads.
The fallback stays scoped to this fixture, avoiding a repeated error every
time the same button is pressed.

This is a gameplay recovery for the observed rejection, not proof that the
additional batch names now play in that rejected fixture. Yamal/Raphinha and
verified native voices retain their accepted label path. All audio, metadata,
referee and scoreboard payloads in FootballNX.assets remain byte-identical to
v62. Pitch, hub admission, result confirmation and referee source are unchanged.

Host tests execute strict rejection, the actual runtime gate/typed accessor,
the actual hub Play tail, once-only Strategy dispatch, optional-request drain,
selector cancellation and a following valid fixture. Synthetic records are
deliberately malformed; they are not represented as a reproduction of the
unknown device field. Local read-only ELF inspection corroborated the existing
Match team/player getter layout and copying of the complete Player carrier,
but did not execute the application or establish the rejected device value.

Device check: ordinary Exhibition -> hub -> Kick Off directly. If fallback is
used, expect the new `v63 snapshot rejected stage=...` note followed by normal
match loading. Then test Game Plan swaps, Rematch, Select Team and both canary
names. Preserve scene-runtime.log to resolve the remaining capture discrepancy.

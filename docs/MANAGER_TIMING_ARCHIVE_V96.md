# Manager League timing and archive v96

New fixtures last 600,000 real milliseconds: five minutes per half, with the
half-time event at 300,000 ms. The displayed football clock maps this interval
to 00:00–90:00. The archive contains 99 six-second actions, including passing
moves, attempts, saves, fouls, corners, cards and substitutions. Its outcome
contains zero to five goals, chosen deterministically from the fixture seed
with a preference for low scoring games. Goal opportunities avoid half-time
and substitution slots and retain the complete shot/goal/restart motion.
The fixture seed stream includes the week number so subsequent weeks cannot
repeat every outcome, while the account's identity seed remains unchanged.
These remain deterministic offline fixtures; this change is not a tactical
engine or the native 3D match simulation.

The three preparation days retain their nine-minute local-preview intervals.
Each Match Day has a thirty-minute interval so its three ten-minute round slots
cannot overlap for a club. The seven-team round robin still contains 21 games
across seven rounds. Results remain hidden until their scheduled broadcast
ends. Live position always derives from scheduled kickoff and wall clock;
opening the viewer cannot reset a live game. Replay uses its own elapsed time.

## Existing saves

The original `SaveData/manager-league-dummy-v1.dat` and backup remain untouched.
The importer validates their exact 15,216-byte ABI and checksum, then converts
to `manager-league-dummy-v2.dat`. Each imported fixture explicitly retains its
180,000-ms duration, 29 events, kickoff, participants, seed and full original
event tape. Its completed scores and three-minute replays therefore remain
unchanged. The original account/profile file is retained, including purchased
players, wallet, receipts and presets. A damaged v2 file does not silently fall
back to an older v1 season. Invalid records stay preserved.

New fixtures carry explicit duration and event count. Validation checks those
bounds, exactly one correctly timed half-time event, legal active player and
substitute identities, unique round-robin pairs, and all time intervals for
clubs that participate in multiple rounds.

## Moving to another week

At Result, the explicit Next Week action archives the completed season in
`manager-league-week-NNNN.dat`. The bundle includes its full player profile,
club assignments, club name and match roster. Replay names and events cannot
change when the next week's registered squad changes. Match Centre can select
the current or previous archived weeks with L/R; viewing an archive never
replaces the active account or season.

A successor week keeps the account, wallet, owned players and purchase receipts.
Its lineup is copied from the current registered squad and unlocked during
preparation. The current local offers remain single-purchase receipts; moving
weeks does not reset or charge a pack again.

The rollover prepares and validates both complete successor records in
`manager-league-transition-v2.dat` before promoting them. The previous archive
must already be durable. The journal remains until the active season and player
records have been reread and verified. On restart, an interrupted promotion
finishes that same prepared week and cannot generate another set of fixtures.
A malformed or incomplete recovery record blocks editing and preserves files.

## Host verification

`tests/test_manager_timing_v96.py` compiles the production C implementation and
checks real-minute boundaries, 45:00 at half-time, late joins, full-time audio
markers, all club intervals, enriched tapes, and continuous motion around the
new tape's action boundaries. New-process tests import legacy data byte-for-byte,
replay a snapshotted roster after a later squad change, retain purchase receipts
and wallet, and recover promotion failures at both season and profile writes.
These tests do not establish Switch audio audibility or rendering performance.

# Manager League offline dummy v91

The main menu now has five custom rows: Match, Modes, Online League,
Settings, Credits. Four original native tile IDs and their native pointer
arrays remain unchanged. Virtual tile 4 opens the separate Manager League
frontend; it never indexes a fifth native tile or portrait. The shared mapping
preserves Settings and Credits actions, five-row touch bounds, navigation,
260 ms menu reflow, and the 2.17 active/resting height ratio.

Online League opens an explicitly labelled offline dummy. Its flow is local
registration, club identity, team name through the Switch keyboard, strategy,
join confirmation, and dashboard. Every existing selectable club is available
through the current club categories. A chosen badge never supplies its original
roster. The sample players are visibly fictional and have no PESDB IDs,
portraits, native assets or ownership mapping. The 5,000 starter points fund three synthetic Shop offers. Purchases debit
that isolated wallet once, reject duplicates or insufficient funds, and add
player profiles. A failed save rolls the purchase back. The window opens
before joining and after the final match; frozen fixtures never reroll. There
is no production account, real player market or backend in this version.

The dashboard reuses the FootballNX font, rounded cards, authored white
background, navy/blue/red patterns, header icons and production button sprites.
It includes rotating club news, current standings, the opening round schedule,
team information, strategy, the full match centre, and player profile pages.
The hub calls the same `ml_ui_chrome`, `ml_ui_hub` and
`ml_ui_navigation_slide` implementation as production Master League, with
the same tabs styled for Home, Squad and Competition, two upper
features, three lower panels, shoulder sprites, three carousel indicators and
180 ms slide. D-pad focus follows the same shared `fnx_hub_navigate` rules,
including paging across a row edge and clamped shoulder paging.
The shared renderer accepts a tab count; production Master League retains
its existing four tabs and indicators. Shop remains under Squad. Registration,
club choice, team name, strategy and join confirmation are separate pages
without a shared wizard tab bar. Shop, news, league guide and overall ranking
are separate destinations. Weekly standings use current league points;
overall ranking displays clearly labelled sample historical reputation plus
a projected weekly RP award after all fixtures finish, separate from wallet
points. No settlement reward is minted. Pairings use `Vs`.
There are seven sample clubs and 21 fixtures, each pair meeting once, with one
bye per club. The dummy calendar is deliberately accelerated: kickoff at the
next device-clock minute and one round every four minutes. This is a test of
presentation and scheduling, not the production 3+3+1 weekly scheduler.

## Scheduled broadcast and full replay

Each match stores an immutable kickoff and 29 authored match events for a
180-second presentation. The fixture seed, events and kickoff are created once
at joining and stored in the dedicated dummy save. Goals, scores, shots, fouls, corners, yellow cards and substitutions are
projected from those same events. Substitutions change the on-pitch shirt
numbers and subsequent events reference the active squad. Goal celebration,
foul stoppage, card, half-time and substitution panels derive their animation
phase from the event timestamp, so seeking and late joining reconstruct the
same presentation. The last three events remain visible in the match feed. The dot paths are a deterministic
scripted illustration; they do not yet model player strength or tactical AI.
Changing formation/approach demonstrates the UI and does not reroll a match.

Live position is `clamp(device_now - kickoff, 0, 180000)` milliseconds. It is
not elapsed time since opening the screen. For a 19:00 kickoff, joining at
19:01 opens at presentation 60 seconds / football minute 30; 19:01:30 opens
at minute 45; 19:03 is full time. A late join receives the score/statistics
at that exact point and does not display future goals. The full record is
already present locally. This offline dummy cannot conceal it from a user
who reads or modifies local data or changes the device clock.

Live broadcasts cannot be paused or fast-forwarded. Leaving, returning or
reopening the app catches up to the scheduled time. After full time every
fixture, including matches between other clubs, opens as a full replay from
kickoff. Replay has its own play/pause cursor, left/right 15-second seek, and
X restart; it never moves the live clock or changes the archive. The whole
21-match dummy season is retained, rather than only the managed club's games.
Future seasons/history rotation and production retention remain separate work.

Dashboard X is an explicit test-clock control. It cycles the first broadcast
to pre-match, +60 seconds, +90 seconds, full time and season end, without changing the OS
clock or stored kickoff/events. This is intentionally confined to dummy mode.
Offline results can move backward when that test clock is moved backward;
this is not an online anti-cheat implementation.

## Isolation and persistence

Only `SaveData/manager-league-dummy-v1.dat` and its `.tmp`/`.bak` companions are
written. Existing Cup, League, Master League and native saves are untouched.
The record binds a format version, exact byte length and checksum; it rejects
truncated/trailing data, invalid IDs/events and duplicate fixtures. Writes
complete a temporary file before rotating the previous valid record. A valid
backup can recover an interrupted write. If both records are invalid, their
bytes are preserved and the UI refuses to overwrite them or reroll onboarding.
Save failure leaves the session open with an explicit retry status.

A mutex protects the new frontend between input and rendering. Rendering only
projects value snapshots: it does not save, simulate, publish results or advance
the archive. The mode never hands control to a native match, mutates source
CPKs/PAKs, updates the real-face roster, or changes existing music/skin policies.

## Host verification and previews

`tests/test_manager_league_dummy.py` compiles the actual C implementation and
checks onboarding, menu mapping, scheduled late joins, future event exclusion,
live controls, replay controls, event/goal bindings, substitutions, strategy
return, all starter profile rows, Shop window/duplicates/funds/save rollback, preserved
fixtures, a separate-process reload, and refusal to overwrite invalid data.
The existing Cup/recovery/controller tests remain applicable to entry routing.

`tools/preview_manager_league_dummy.py` drives the real C frontend through the
same pages and captures the exact renderer's draw records, fonts and public
textures. Each capture asserts its expected page, finite on-screen geometry,
the 384 draw-record / 4,096 quad budgets and an unchanged VBO canary. Defaults
write under ignored `local-debug/manager-league-dummy-v91/previews`.

These are host layout previews and synthetic data checks, not Switch screenshots
or acceptance of playback, keyboard interaction, audio, performance or FPS.
The existing v90 payload remains the packaging baseline; only the new NRO is
required for this dummy, with every other runtime file preserved exactly.

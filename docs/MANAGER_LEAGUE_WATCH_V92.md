# Manager League match presentation v92

The match viewer uses the existing FootballNX and Master League artwork,
fonts, official badge atlas and controller helper sprites. The native C
renderer now builds a broadcast header with blue home and red away panels,
a central score and match clock, a framed tactical arena, comparative
statistics, a touchline feed and a match-event timeline. Home, Squad and
Competition hub navigation continues to use the shared Master League hub.

The pitch includes striped turf, a quiet tactical grid, penalty and goal
areas, goal nets, numbered team markers and a highlighted ball. Its short
ball trail samples the same deterministic path at earlier presentation
timestamps. Trails break across episode relocations. Pre-match players keep
their formation on their own half.

Goals, fouls, cards, saves, corners, substitutions and half time have an
animated lower third. Team colours and badges bind to the fixture's home
and away teams. Substitutions show the actual outgoing and incoming shirt
numbers from the saved tape. Event entry is reconstructed from event age,
so live late joins and replay seeks show the same state. Pausing a replay
also freezes the ball pulse and event animation.

Comparative bars use the actual shot, on-target, foul, corner, yellow-card
and substitution counters. Zero totals remain neutral. Timeline markers
only contain goals, cards, substitutions and the break already reached by
the current presentation cursor. This projection never publishes future
events or writes a fixture. The existing dummy save schema is unchanged.

`tools/preview_manager_league_dummy.py` captures the actual C renderer and
defaults to ignored `local-debug/manager-league-watch-v92/previews`. Frames
include live, goal entry/settled, foul, yellow card, substitution, pre-match,
half time, full time and paused replay. Geometry checks cover finite
on-screen vertices, the 384 draw-record limit, the 4,096 quad limit and a
VBO canary. Core tests also compare a historical ball sample with the live
path, hide future timeline markers and compare live/replay timeline state.

This revision is built for Switch and packaged as the v92 Manager League
candidate. It includes the fifth Online League main-menu entry, separate
onboarding pages, the three-tab Master League hub, Shop and the new viewer.
The serial production build retains O3 and LTO. The NRO's three load segments
match the ELF, and its embedded launcher artwork and FootballNX27 branding
are checked. The other 17 runtime payloads match v91 byte-for-byte, retaining
all 1,638 heads and the 436 existing skin corrections. All 24 CPKs pass the
overlay and actual native C validator; ZIP CRC and member hashes also pass.

The ready-copy folder and ZIP are under
`D:/PESNX-Cache/Deliveries/FootballNX27-v92-MANAGER-LEAGUE-SIAP-COPY`.
Merge its `switch` folder into the existing SD installation and preserve
SaveData. Local receipts and the runtime override are under ignored
`local-debug/manager-league-watch-v92/`. The active development runtime was
not installed or replaced.

Focused Manager League tests pass (4 tests and 31 subtests); the compatibility
run passes 31 tests and 370 subtests with one previously documented League
save-slot label assertion: the old harness expects `MATCHDAY 1/1` while the
existing UI uses `MATCHDAY 1 OF 1`. That unrelated assertion remains visible
in `BASELINE-TEST-LIMITATIONS.json`. Public-tree audit passes for 1,416 files.
There is no v92 device acceptance or performance measurement. The match
remains an offline authored dummy, with no new inference about tactical
strength, possession or expected goals.

## Requested audio policy (not implemented)

Commentary belongs only to the live broadcast. Replay disables commentary
at every playback speed, including 1x, and keeps supporter ambience and
ball sounds. Entering replay or leaving the viewer must stop the owned
commentary handle and clear pending lines. Returning to live starts from
the current fixture time without replaying missed calls. A late join also
starts at the current cursor. The three-minute live tape needs bounded
priorities and cooldowns rather than an accumulating commentary queue.
Replay pause, speed changes and seeks must not burst missed ball sounds or
speed up supporter audio.

The existing selected-roster commentary hooks require an actual native
match selection and identity-bound players; they are not a direct driver
for synthetic dot matches. The trophy adapter demonstrates guarded native
bank mount/play/stop/status plumbing, but its music route is not proof of
generic commentary cue availability or playback outside a native match.
A dedicated adapter still needs an audit of owned generic commentary,
crowd and ball cues, their mount lifetime and mixer routes. Synthetic player
names use generic calls unless independently supported by an own recording.
No commentary, crowd or ball audio is newly connected by this presentation
revision, and no device playback is claimed.

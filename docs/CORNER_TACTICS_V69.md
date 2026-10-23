# Corner presets v69

The user authorized the corner selector and a combined ready-copy candidate,
including the v67 bench boundary fix and v68-r2 English scoreboard assets.
Switch testing is unavailable. This is a native-command activation candidate,
not a claim of FL26 behavioural parity or device acceptance.

## Controls and presentation

During a ready corner, D-pad Left opens a compact FootballNX panel. Release
the opening press, then select with a direction. D-pad Right outside the panel
retains Set Piece Taker. B closes without passing. All buttons and both sticks
for the owning pad are isolated until the closing press/sticks are released;
the other controller continues independently. X switches attack/short-corner
pages when the native restart permits short tactics. On a horizontal Joy-Con,
stick click opens and stick direction selects; SL+SR remains Set Piece Taker.

| Direction | Attack | Short | Defence |
| --- | --- | --- | --- |
| Up | Dash | Touchline | Mixed |
| Right | Far Post | Diagonal Run | Zonal |
| Down | 6-yard Box | Run From Deep | No action |
| Left | Train | Two Options | Man-to-Man |

Highlight comes from current native team-AI state, not an optimistic UI update.
Native attack/short selection can toggle a repeated choice back to default.
The normal L short-corner action, aiming, kicking and camera controls remain
outside the modal selector. Synthetic previews use the actual C geometry,
shared optical font alignment, public font atlas and draw recorder. They are
not game screenshots. `tools/preview_corner_tactics.py` regenerates them.

The reviewed presentation uses generic role headings without controller IDs
or slash separators. Its top corners match the panel radius; a square lower
header joins the continuous cyan accent without pale corner notches. Footer
actions use dark B/X sprites from scoped colour derivatives of the existing
credited SVG set. Existing white button payloads remain unchanged. The former
technical preset explanation is omitted from the product HUD.
Each directional choice is a single horizontal sprite-and-label row, using
the existing D-pad artwork rather than a separate direction word above it.

## Native boundary and lifetime

`corner_tactics.c` owns two small mutex-protected scalar state machines.
The native adapter publishes match/session/restart/kicker/controller epochs,
role, availability and actual presets; engine pointers stay on its callback
thread. Context and queued requests expire after 250 ms without a heartbeat.
Pause/replay/cinematic/loading/disconnect, restart changes and new fixture
generation cancel stale requests. Opening, page switching and closing all
require release before another selection. Diagonal choices are ignored.

The adapter admits seven bounded compatible-ELF function fingerprints, resolves
the original methods and checks exact dormant ThinkUnit vptrs in the existing
object table. Unsupported optional ABI retains stock controls. A valid corner
unit is placed first in the local list, with duplicate corner units removed.
It returns zero when idle. It still calls native Main for Init/lifecycle while
clearing the hidden native menu flags around that call.

A selected request writes only the native ThinkUnit option byte and returns
the existing attack/short/defence command (`0x6e`, `0x71`, `0x6f`). Native Team
update consumes it. The wrapper does not patch team-AI tactics memory. Both
MatchInfo SET_PLAY/restart bounds and kicker set-play animation readiness are
required, including when the defending side has no Mobile ButtonSetplay HUD.

The bounded owned-ELF tests interpret actual integer leaf instructions and
their actual option/jump tables. The broader AI routines and player movement
are not executed by that oracle. REA provider limitations from the feasibility
pass remain; no REA native execution is claimed. See
[the native feasibility audit](CORNER_TACTICS_FEASIBILITY.md).

## Candidate and verification

The delivered v69 failed at Switch startup, with the journal ending after
referee presentation admission. Its new installer hashed `load_virtbase`
before `so_finalize` mapped that alias. Host gameplay tests had not exercised
successful installation with distinct, inaccessible runtime addresses.
The v70 followup reads bounded opcode/vtable spans from `load_base`, storing
runtime aliases only as future call/vptr values. A new actual-C installer
fixture reserves a no-access RX range and uses the owned seven opcode bodies
in a separate RW buffer. Original v69 fails that test; v70 passes installation
and missing/corrupt/out-of-range cases without partially patching a vtable.
See [the startup fix](CORNER_STARTUP_V70.md). Hardware retesting remains pending.

Build in an isolated output directory with the pinned v67 private catalog,
roster and commentary inputs; keep `-Jobs 1 -LtoJobs 1`, O3 and LTO. Do not
install into `dist`. The final update contains only `pes21_nx.nro` and the
byte-identical v68-r2 `FootballNX.assets` (SHA-256
`ef74bc2437d0e037f6b1036f2f32c9e48b3a7771860900399dc1b7493d3ae722`).
Accepted commentary/referee payloads and other scoreboard members are retained.
Existing face PAK, LooseCpk, OBB and saves are not duplicated.

Focused checks cover actual C input, native-adapter command/owner/lifetime,
bounded native leaf conversions, native-pad routing, bench confirmation,
referee/scoreboard/audio/flow regressions, journal rotation and build limits.
Seven old UI string assertions also fail against committed HEAD; they are
recorded separately and excluded from the focused integration acceptance.
Do not describe them as fixed or claim a completely green repository suite.
Receipts, frozen source/input hashes, previews and package verification live
under optional ignored `local-debug/corner-tactics-v69/`.

When a Switch is available, test both sides taking/defending corners, both
camera directions, short corners, each preset and default toggle. Observe
actual player movement, not just the highlight. Check Right taker, B cancel,
opening/closing holds, replay/skip/pause, successive corners and Rematch/Select
Team. Re-test bench A-confirm after both result routes, referee replay/VAR
visibility and kickoff placement, and EPL name/score alignment and +N timing.
No new hardware playback, substitution success or 60 FPS proof is supplied.

# Master League implementation

## Risky-action safeguards (2026-10-08)

Occupied-slot overwrite and player release retain their confirmation dialogs.
Leaving the career hub now asks **Save & Leave** before updating the active
slot or exiting. Simulation and next-season rollover also start on Cancel;
Play Match remains a non-destructive, default-Play confirmation. B always
cancels before processing simultaneous accept/navigation input, and modal
input cannot reach background shortcuts. Save failures keep the career open.
Normal progression autosaves and the intentional Quick Save shortcut are
unchanged. Save format and content identity policy are unchanged. The host
frontend tests cover cancellation, slot focus, no-exit-on-cancel and unchanged
day/season when rejecting rollover. See `FRONTDOOR_UI.md` for matching
Cup/League, preset and Pause safeguards.

## Header square-canvas follow-up (2026-10-07)

The per-symbol optical offsets in the initial v8 candidate overcorrected the
header icons. All 16 reusable icon sampling regions now use equal **288 x 288**
transparent square canvases, centred around the complete artwork (within half
a source pixel). This is an atlas-coordinate/layout change: the generated PNG
and its embedded bytes are preserved, with no regenerated or stretched art.
`header-icons-v8.json` records both square canvases and original artwork bounds.

The renderer samples the whole square and gives every panel icon the same
**40 x 40px** destination inside the **54px** header at 720p. The square has
**7px above and below**, scaled with the interface. There are no per-icon Y
offsets or white-pixel-centroid corrections. Feed-body ornaments reuse the
same square sampling contract at their own size. Tests check square regions,
centred artwork, transparent gutters, aspect ratio and equal header margins.

Verification: **21 focused tests passed**, with **48,916 geometry subtests**;
public-tree audit passed (**616 files**). Production-renderer synthetic previews
and the isolated diagnostic build are in `local-debug/master-league-v8-square/`.
The NRO SHA256 is
`8a56b52684bf0a33298a556a711fb661f8c75e947c1ae3fd10998c636bdeb667`
(69,591,967 bytes; link build ID `ba9e44ed98ea59b3ed13422562f430f5bdd61255`).
Staged source hashes, embedded assets and ELF/NRO sections verify. This revision
changes only header rendering/catalog metadata; the runtime pair and save
format are unchanged. Hardware visual confirmation is still pending.

## Review revision v8 diagnostic (2026-10-07)

Pre-review checkpoint: commit `8f5a389`, annotated local tag
`checkpoint/master-league-v7`. No push was requested for this checkpoint.
The unrelated stadium/camera documentation edit was excluded.

- The international office remembers its entry page and selected destination.
  Back from empty offers or the active national office returns to Cup
  Competitions when entered there, or Manager when entered there. Nested
  federation offers return to the national office without replacing this parent.
- Home's clickable Club Feed cycles through four real story summaries every
  five seconds, with a short opacity transition, progress line and page dots.
  Opening it keeps the currently displayed story. Rotation runs on the input
  thread, pauses off Home/during a modal/native match, and ignores suspend gaps.
  A newly completed match is the first story shown after calendar playback or
  reloading a save; projecting the view never writes state or advances RNG.
- Match Centre derives its three newest managed-team results by calendar date
  from the existing league, domestic cup, continental, friendly, qualifier,
  regional and World Cup fixtures. It excludes byes, incomplete/future fixtures
  and matches involving neither managed team. Full score cards retain home/away
  order; one-opponent history rows use manager-versus-opponent score order.
  Competition, day and WIN/LOSS/DRAW are displayed, including WIN/LOSS ON PENS
  for tied knockout scores. No invented shootout score or duplicate result
  journal is stored. History remains limited to the current season's fixtures.
- Modal height is measured from the same wrapping routine used to render its
  body/error text, identity block and zero-to-three actions. Renewal/propose
  terms and overwrite/play/simulate/release confirmations share compact padding.
  Terminal offers show a small final-status cue without disabled action rows.
- Built-in imagegen produced 16 reusable vector-style raster icons in one
  transparent atlas: `art/master-league/header-icons-v8.png`. The identical PNG
  is embedded as `data/master_league_headers_v8.bin`; source prompt and measured
  bounds are in `v8-prompts.json` and `header-icons-v8.json` beside the artwork.
  Calendar, ranking, save and other blue headers use semantic icon IDs. Sampling
  uses individual padded artwork bounds, not nominal cell centres. Per-symbol
  optical offsets align visible white ink with the bitmap-font capitals
  (calendar -6px, ranking -9px, save -3px at 720p, scaled with the interface).
  Official club/national identities continue using the existing paired atlas.

Save format remains **v5**, with the same v1-v4 migration support. This review
does not alter economics, fixtures, roster identity or the active runtime.
Host tests cover empty/active/nested international return paths, real simulated
continental results, a complete club/national result stream, away-score and
shootout labels, save reload, input-only carousel timing and read-only views.
Production C-renderer previews check compact modal bounds, wrapped text,
optical header alignment against visible title ink, icon aspect/sampling,
layering, text overlap and the 384-draw/4096-quad limits. These synthetic previews
are not Switch captures. Native play/halftime validation still needs hardware.

Verification: **79 passed, 1 skipped**, with **48,900** geometry subtests; the
skip requires the user's local hardware log. Public-tree audit: **616 files**.
The isolated `build-wsl.ps1` diagnostic build and verification report are under
`local-debug/master-league-v8/`; the NRO-only delivery directory is
`local-debug/FootballNX-MasterLeague-v8-DIAGNOSTIC-COPY-TO-pes21_nx/`.
The candidate is **69,591,967 bytes**, SHA256
`717bc8e1e9d1e44b1742237564879a4102ef0e9e27057caf3d9ea5fb865c1905`,
link build ID `7f317cb19c7bd192f8e49463cb2c4eaee0b69f43`.
Captured WSL-stage source hashes, embedded art/badges, ELF-to-NRO initialized
sections, launcher icon and active diagnostic logger all verify. Runtime pair
remains `e861c583ec78e9ae`; active `dist/pes21_nx` and SaveData were not changed.

## Review revision v7 diagnostic (2026-10-07)

The pre-review v6 checkpoint is commit `25faeeb`, pushed to `origin/cupleague`.
This revision keeps that runtime pair and the post-result-only calendar flow.
The user confirmed that a club move preserves the season date/results while
adopting the new club's squad, money and targets, and that international dates
may use a fictional game calendar rather than official UEFA/FIFA schedules.

### UI and transfer balancing

- Closed-window transfer attempts use the timed foreground toast. Short data
  lists, including Club Offers and selector results, now start below the header;
  centred one/two-destination action groups remain unchanged. Club Feed history
  and statistic cards sit directly below their heading/summary.
- Offer rows include the counterparty club's atlas crest beside the player
  portrait. Fees are right-aligned at a fixed right edge and vertically centred;
  unread dots sit in the upper-right corner, never shifting the monetary text.
- Normal/Hard negotiations now include elite-player fee/wage premiums, starting
  XI importance, remaining contract, club-strength step-down and willingness.
  A stable identity/buyer/season/window roll prevents re-rolling willingness by
  sending another offer. Rejected players cannot immediately be approached again
  in that window. Easy retains the prior forgiving terms behavior. Prices and
  probabilities are fictional game balance, not real-world valuations.
- Built-in imagegen created the transparent 2x2 decorative atlas in
  `art/master-league/career-emblems-v7.png`, embedded unchanged as
  `data/master_league_emblems_v7.bin`; prompts are in `v7-prompts.json` alongside
  the source artwork. Trophy, globe, manager and laurel emblems decorate career
  destinations and stories. Insets isolate cells and preserve square geometry.
  Official club/national identities still use the existing paired badge atlas.

### Club and international calendar

- Cup Competitions links domestic, continental and international views. New
  careers without a named domestic cup use their verified league pool for a
  generic domestic knockout cup. Existing cup-less saves are not retroactively
  given a new domestic competition.
- European supported top-division pools feed a compact **UEFA Champions League**
  knockout (up to 32 teams); South American and Asian pools use corresponding
  generic Champions Cups. Seeded strength chooses up to four qualifiers per
  league in season one; the managed club's previous final rank must be top four
  in later seasons. This is not an official multi-stage UEFA competition format.
- Federation offers arrive as **2-4 distinct countries simultaneously**, selected
  from the paired national pool independently of manager nationality. Each has
  its flag, expiry, read receipt and persisted decision. Its modal offers Accept
  and Decline; declining leaves other offers open. Accepting keeps one club plus
  one national appointment and withdraws other pending federation offers. The
  Federation Offers destination retains terminal statuses without disabled
  actions. Appointments continue across seasons; switching between multiple
  national posts mid-season is not implemented.
- National management has two friendlies, a four-team home/away qualifying group
  (six rounds, top two advance), a regional knockout and an eight-team World Cup
  finals bracket. Dates share the club calendar and avoid domestic/continental
  fixture dates. These are annual compact career competitions, not official
  international cycles. Header captions show the active club/country name,
  season and date. Home Hub/Next Match switch to national identity for an
  upcoming national match; club office/squad pages keep club identity. National
  contexts show the country flag without club budgets, not a generic dual-job label.
- Native matches use existing paired national rosters. No canonical club player
  is duplicated or transferred to a national club; no national wages, transfer
  market, club cash prizes or permanent national squad/preset editor is added.
  Club weekly wages still accrue with elapsed calendar time. National results
  are isolated from the domestic standings and club board-loss counter.
- National fixtures, continental rounds and office events all use the canonical
  next-event path. Actual shootout winners are required for played knockout draws;
  duplicate result callbacks cannot advance twice. Results save before return
  calendar playback. National managed-side identity delegates to the existing
  paired native roster validation rather than the career club roster override.
- Club job checks occur on three seed-varied mid-season dates, subject to
  results and availability. Offers remain inside the current league/domestic-cup
  pool, expire after 14 days, and reset current/named tactics and financial/board
  summaries on acceptance. Existing fixtures/results and a national appointment
  remain intact; no cross-league season migration is claimed.

### Save compatibility and acceptance

The append-only world extension writes **save version 5**. Frozen v1-v4 layouts
remain readable, checksum-validated and zero-extended in memory. Enabling world
features on an old save never invents past continental results: saves at day 78
or later defer that competition to next season; after day 76 national offers
also wait until next season. Back up **SaveData before testing**. A rollback
needs both the older NRO and its pre-v5 saves; old builds cannot read v5 saves.

Host coverage includes a complete parallel season, all 13 paired league pools,
national/club job isolation, multiple unrelated federation offers, independent
declines, read receipts, expiry, duplicate/invalid replies, world save roundtrip,
v4 migration, shootout/result retries, elite transfer behavior over 100 seeds,
and actual C renderer geometry (crest presence, stable fee positions, sprite
gutters, top-aligned histories, text overlap and draw/vertex limits).

Final focused regression: **76 passed, 1 skipped**, with **38,951** geometry
subtests. The skipped identity check requires the user's ignored Switch log.
The public-tree audit checks 611 files successfully; `git diff --check` passes.

The clean diagnostic candidate and synthetic host previews are under
`local-debug/master-league-v7/`; the delivery folder contains only the NRO, never
game payloads. Runtime pair remains `e861c583ec78e9ae`, catalog content
`97e84d7f8c21ba930bb0e13793ac46c91a60836a33902d40100d36aa5801a59f`, with 304 clubs
and 9,075 canonical players. Diagnostics remain enabled and performance trace
disabled. No active runtime or existing user save is modified by this build.

Verified NRO: **68,645,791 bytes**, SHA-256
`d87c9532e0259ce552b77ba0f5d8feff54a413f7ae0c6e80705591f29e2725d7`.
Staged source hashes, all initialized ELF/NRO sections, paired badge/artwork
bytes, launcher icon and enabled diagnostic logger were checked. Copy candidate:
`local-debug/FootballNX-MasterLeague-v7-DIAGNOSTIC-COPY-TO-pes21_nx/pes21_nx.nro`.
The verification report is `local-debug/master-league-v7/build-verification.json`.

**Switch acceptance remains required**, especially national match/kit/roster
handoff, pre-match/live substitutions, actual shootout return and season rollover.
The reported whistle -> loading -> halftime crash is not declared fixed without
a hardware rerun/log; the v6 diagnostic breadcrumbs remain enabled. Host passes
and a successful native build are not a substitute for those checks. The broader
legacy-suite/optional-fixture caveats below still apply.

## Review revision v6 diagnostic (2026-10-07)

This revision supersedes v5's **pre-kickoff** calendar playback and confirmation
pages. It preserves the accepted catalog, generated artwork, palette and native
live-match substitution rules. The frontend-design pass guided shared panel
proportions and the richer crest-led Club Feed; no new raster assets were needed.

- The office-only substitution path validates the entire SquadData against the
  career roster: exact canonical native identities, all reserves, unique 18-player
  registration/order maps, and the managed side only. It retains native deep-copy
  rollback. It no longer requires or publishes executable Match/AdditionalData
  records while editing from My Squad. Changes are persisted through the existing
  canonical career-plan adapter. Pre-match/live paths retain their existing guards.
- Two-destination groups (Squad, Next Match, My Teams, Manager) are centred
  vertically; the three save slots fill their panel. Four Market tiles remain
  evenly fitted. Short data/selector lists have bounded, centred rows, while
  paginated lists keep stable row height on partially filled last pages.
- Overwrite, Play, Simulate and Release use a centred two-button modal over the
  original page. Destructive actions start on Cancel; left/right chooses the
  button. The modal draws after global helper sprites. Projection never performs
  an action. Drawer modals suppress transient toasts and show errors inline.
- Play opens confirmation, then native pre-match/Game Plan without advancing
  the date or charging wages. A committed, saved result triggers calendar playback
  only when native result flow returns, then lands on the Hub. Cancel, failed
  handoff, aborted matches and duplicate callbacks cannot advance again.
  Simulated and office events still commit/save once before their playback.
- My Teams now has Club Offers and My Players. `OFFER EXPIRED` explicitly means
  the buyer's offer, not the player's contract. An expired incoming offer for a
  still-owned player can open paid contract renewal; it cannot revive the bid.
  Rejected/completed/cancelled details show status and no disabled action trio.
  Waiting offers expose Cancel only. My Players provides renewal/release even
  without an incoming bid. Renewal has an adjustable duration and readonly
  signing-fee/wage quote in its existing payment modal.
- Release creates a free agent and stops that player's wage. This candidate uses
  a **proposed balancing default of 25% of player value** as compensation, matching
  the request for release income; the percentage was not separately confirmed.
  The payout is once per player identity, preventing release/re-sign cash loops.
  Validation retains at least 18 players, the last keeper and suitable starter
  cover, respects dismissal/balance limits, cancels live offers and invalidates
  the current lineup. Checks precede mutation. Identity/face keys stay unchanged.
- Top Scorer rows render the team crest beside the portrait. Four Club Feed
  stories use existing artwork, club/nationality badges, actual latest league
  results with scores/opponent crests, season statistics and recent transfer
  statuses. They do not fabricate historical results or news.

Save version remains **4** with unchanged struct layout. Bit 0 of the previously
reserved `MlPlayer.reserved` byte stores the release-compensation receipt; unknown
bits are rejected. v1/v2/v3 migration and v4 roundtrip remain tested. The receipt
survives free-agent re-signing and save/reload. Back up SaveData for rollback;
older builds lack the new release action and its balancing rules.

### Verification and candidate

Core/frontend tests cover expired-offer renewal, fee deduction, release/re-sign
anti-exploit, goalkeeper/squad limits, identity preservation, cancellation and
save roundtrip. Native host probes cover office bench/reserve substitution
without a MatchPlan, unchanged Match buffers, and rollback on foreign/duplicate
identities. Layout probes cover proportional groups, modal foreground order,
badge presence, text overlap and the native draw/vertex budget.

Focused regression: **73 passed, 1 skipped**, with 32,662 layout subtests.
The skipped test needs the user's ignored hardware log. `git diff --check`
and the public-tree audit (605 files) passed. The broader legacy-suite caveats
below still apply; these checks do not constitute Switch acceptance.

The v6 candidate was built cleanly with `build-wsl.ps1`, `DIAGNOSTICS=1`,
`PERF_TRACE=0`, and the same full-loose pair `e861c583ec78e9ae` / catalog content
`97e84d7f8c21ba930bb0e13793ac46c91a60836a33902d40100d36aa5801a59f`.
Source hashes were compared against the live build stage; launcher icon,
embedded UI/badge assets, diagnostic logging and initialized ELF/NRO sections
were verified. The NRO is 66,823,071 bytes, SHA-256
`2540187285a83a3812f81eb32cdc5a9cdfa5d6ea28f2f6aae91817eb60d006c6`.
The copy folder is `local-debug/FootballNX-MasterLeague-v6-DIAGNOSTIC-COPY-TO-pes21_nx/`;
verification and synthetic host previews stay under `local-debug/master-league-v6/`.
No active runtime, game payload or existing save was changed.

Hardware acceptance is still required: office substitution -> leave editor ->
reopen -> save/relaunch -> verify the actual starting player at kickoff; played
and simulated result return/calendar timing; first-half whistle -> loading ->
halftime. The v5 diagnostic breadcrumbs/readiness guard remain. No new Switch
log was supplied, so this is **not a claim that the halftime crash is fixed**.
After reproducing, copy `pes21_nx/debug.log` before relaunching, plus any Atmosphere
crash report. This log is replaced at each boot.

## Review revision v5 diagnostic (2026-10-07)

This pass retains the accepted palette, art, badge/font assets and gameplay
catalog. The frontend-design pass informed the balanced card groups, equal
team-name lanes and the notification hierarchy; no new raster art was needed.

- Empty-state sampling excludes the neighbouring handshake tip and preserves
  the icon's aspect ratio at 58% opacity. The host preview now honours texture
  alpha, matching the native shader.
- Profile cards are centred as a group within the card body. Four Market
  tiles fill the available height and their title/description blocks are
  vertically centred. Next Match names share equal-width centred badge lanes.
- Toasts draw after the global Switch-helper sprite pass, with an opaque
  background; the shoulder R can no longer overpaint them. Renewal success
  uses the same timed toast as transfer updates.
- Renewal quotes a signing fee of four weeks of the new wage per chosen
  contract year. Confirmation validates both cash and the wage budget before
  changing anything, deducts the displayed fee once, and refuses durations
  that do not extend the current end season. Contract duration remains relative
  to the current season, not an extra number of years added to the old contract.
- Advance commits and saves once, then displays a full calendar for 1.1–2.45s,
  stepping the highlighted date with a per-day sweep and overall progress bar.
  Input is locked during playback. Office/simulation events return to the Hub;
  choosing Play continues to the native match hub after the date transition.
  Render projection does not advance dates or process transactions. Failed
  saves stay on the Hub with an explicit retry-save error, without replaying
  the already-committed event.
- Calendar tile height adapts to the actual 4/5/6 week rows, filling a constant
  grid area above the date-detail line. Five-week months use approximately
  66px tiles at 720p; six-week months remain fully visible.
- Red unread dots appear on My Teams/Transfer Response, individual offer rows,
  the Hub's Club Office tab and its Transfer Market destinations. Merely
  displaying a list does not mark an update read: opening its detail does.
  New incoming bids, replies, counters, rejections and expirations are unread;
  waiting bids and user-initiated completion/cancellation are not. Read receipts
  follow offer compaction and distinguish subsequent negotiation rounds.

Save **version 4** appends 32 read receipts after the frozen v3 layout. Exact
v1/v2/v3 prefixes remain checksum-validated and migrated in memory without
rewriting on read. Unknown/invalid files and A/B recovery retain the existing
guards. Back up SaveData before this test: older builds cannot read v4 saves.

### Halftime and substitution diagnostic boundary

The reported failure is **first-half whistle -> loading -> crash**. No hardware
log was available. This candidate is built with `DIAGNOSTICS=1`, `PERF_TRACE=0`;
it is not a claim that the crash or reported failed substitution is reproduced
or resolved. Native lineup validation and rollback are intentionally retained.

`ml-v5-diag:` breadcrumbs bracket native ending/demo/result creation, stats
InitMobile, stats snapshots, halftime-menu entry and substitution commit checks.
They report registration/count/identity failure branches without dumping game
payloads. Existing debug logging flushes each message to `debug.log`. The
halftime initializer also defers skin/root access until native InitMobile says
the layout is ready, keeping the cover during retries. Host tests execute this
readiness guard in both release and diagnostic builds.

On Switch, reproduce substitution once, then play through the first whistle.
After a crash **copy `pes21_nx/debug.log` before relaunching** (each boot replaces
it). Include the latest Atmosphère crash report if available, and say whether
the failed substitution was in the career office editor, pre-match hub or
pause/halftime. A successful host test or NRO build is not hardware acceptance.

### Verification and candidate

The focused regression run passed 69 tests and 29,877 layout subtests; one
hardware-log test was skipped because its ignored Switch log was unavailable.
`git diff --check` and the public-tree check (605 files) passed. This does not
claim a clean full legacy suite or Switch acceptance.

The diagnostic NRO is 66,782,111 bytes, SHA-256
`9e3841e1568c040a3b87547e294c5a26d7bb0a4418600724156a20eaf2579ca2`.
Verification compared staged sources, embedded assets, ELF/NRO sections,
diagnostic logging and launcher icon bytes. Runtime pair `e861c583ec78e9ae`,
content `97e84d7f8c21ba930bb0e13793ac46c91a60836a33902d40100d36aa5801a59f`
and the 304-club/9,075-player catalog remain unchanged. Install only the NRO;
do not replace game payloads. To roll back after saving with v5, restore both
the previous NRO and the pre-v5 SaveData backup.

## Standings review (2026-10-08)

Master League and standalone League now show six teams per standings page,
with larger crests and consistent row spacing. L/R steps by six clubs. The
shared rank indicator uses a blue up triangle, red down triangle or gray dash,
comparing against the start of the latest matchday with recorded results.
Its baseline comes from the existing saved fixtures, including partial rounds;
rendering does not mutate the competition or add fields to career saves.
The same projection supplies national qualifying standings.

## Review revision v4 (2026-10-07)

This revision supersedes the v3 selector, condition-setting and fixed-price
transfer behavior below. The accepted team/kit/logo catalog is unchanged.

- Reusable white cards have opaque bodies, 54px blue headers, 25px title
  geometry, rounded top corners and square header bottoms. Main and selector
  panels have identical heights. Existing light artwork and shared font atlas
  are retained; no native data is drawn into a generated screenshot.
- League standings are a full-width table: eight clubs per page, larger
  crests/text, and aligned P/W/D/L/GF/GA/GD/PTS columns. L/R pages through all
  clubs. The domestic cup uses a connected three-round bracket viewport;
  round navigation and fixture groups expose the entire actual bracket.
- Player lists use colored position tags and large right-aligned ratings,
  moving from blue/green toward red at higher values, without STARTER labels.
  Empty panels show one centered message and the generated empty-state icon.
- Settings retain drawers only for League/Club. The other five values change
  inline with generated left/right chevrons. Player Condition is removed and
  always Random, including old career loads. Nationalities remain alphabetical.
- Office Game Plan holds the opaque native loading transition until the
  custom editor is ready, including the intermediate native Hub publication.
  Permanent career plans and temporary pre-match changes remain separate.
- Quick Save uses a top-right 180ms-in/250ms-out toast, automatically dismissed
  after three seconds without navigation. Errors remain separate and visible.
- Transfer Market has My Teams, Transfer Response, Weak Position and Browse
  Team. Browsing is category/league -> team -> players, with Free Agents also
  available. Recommendations use the weakest registered starting role, not
  invented season-performance statistics.
- Propose Terms is a centered modal over a dimmed, unshrunk page. Contract,
  weekly wage and fee have centered values and smaller generated arrows.
  Fees use one-decimal M and 0.1 M steps (2.3 M -> 2.4 M); weekly wages use K
  and 1 K steps. Steps follow the chosen display currency. Only the new draft
  quote is rounded to its visible precision; saved balances/contracts are not
  rewritten by changing currency. A advances fields; Send Offer is explicit.
- Offers persist identity, ownership, terms, status and a rolled response date
  one to three days ahead. Counteroffers/acceptance still require explicit
  Accept Terms; duplicate/replayed transactions cannot move the player twice.
  Negotiations, roster/keeper limits, budgets and ownership are revalidated
  before committing. Incoming bids support Accept/Reject/Negotiate.
- The calendar marks opening, middle, updates and deadline with the generated
  handshake. July 1/16/31 and January 1/16/31 are in-game milestones, not a
  real-world feed. Skip First Window affects only the first July. Next Event
  stops for responses and deadlines before later matches; deadline responses
  are processed before the deadline milestone. Unresolved offers expire after
  the window; new bids cannot start on deadline day.
- Manager offers and President Messages live in Club Office. The agreed rules
  warn at three mid-season consecutive losses and terminate at six; negative
  transfer cash warns first and terminates after 14 days. Dismissed careers
  remain viewable/saveable but cannot play, advance or transact. A qualifying
  mid-season job offer lasts 14 days and is restricted to the same league and
  compatible cup field; accepting preserves fixtures/results and club budgets.

Save version 3 appends the office state after the frozen v2 prefix. Exact-size
v1/v2 files are checksum-validated, zero-extended and migrated in memory; reads
never overwrite them. A/B recovery and content pairing remain mandatory.
Back up career SaveData before testing: older NROs cannot read v3 saves.

The built-in imagegen tool created `art/master-league/office-icons-v4.png`,
embedded byte-for-byte as `data/master_league_icons_v4.bin`. Its exact prompt
and mode are recorded in `art/master-league/v4-prompts.json`. The generated
atlas supplies both chevrons, handshake and empty-state art; none are hand-drawn
stand-ins. The frontend-design pass guided spacing, hierarchy and modal layout.

Host tests cover delayed replies/counters/rejection, incoming terms, transaction
atomicity, deadline stops, stored reply dates, v1/v2 save ABI migration, dismissal
warnings and thresholds, same-league job changes, and non-mutating projections.
Layout tests exercise actual C-emitted geometry, eight-row table sizing,
centered modal/arrows, auto-dismiss without page navigation, text overlap and
native draw/vertex budgets. Software previews use synthetic players and are
not Switch captures. Hardware acceptance is still required for native editor
entry/return, real player identity, transfers and save/relaunch.

V4 verification: **49 focused tests passed, 1 optional hardware-log test
skipped, 23,547 geometry subtests passed**. This includes all 13 paired curated
leagues, Cup/League core/frontend/save checks and Game Plan regression probes.
The public-tree audit passes (604 files); the older broad-suite caveats below
still apply. There is no claim of an on-device or all-project-suite pass.

The production candidate is 66,675,615 bytes, SHA-256
`ea674aa1bdaabe1b1d11ebf8b03d8b05f1fd860df87666f99c1c50a6781f8a51`.
It preserves full-loose pair `e861c583ec78e9ae`, dummy OBB size 53248 and content
`97e84d7f8c21ba930bb0e13793ac46c91a60836a33902d40100d36aa5801a59f`.
The native devkitPro build uses the existing private paired staging headers,
diagnostics/perf trace off and authoritative OVR off. Verification checks source
equality, initialized ELF/NRO sections, exact old/new artwork and badge bytes,
launcher icon and the disabled logging stub. Candidate copy folder:
`local-debug/FootballNX-MasterLeague-v4-COPY-TO-pes21_nx/` (NRO only).
Instructions, reports and synthetic previews are under
`local-debug/master-league-v4/`. No active runtime, CPK, OBB or save was changed.

## Review revision v3 (2026-10-07)

The white/blue/red artwork and native font/badge pipeline are retained. The
frontend-design pass changes hierarchy and interaction, not the artwork or
base rosters:

- Landing and ordinary pages have one centered primary panel. NEW/CONTINUE
  use 40px title geometry and regular-weight descriptions. A secondary panel
  appears only when selecting something, with a 200ms in/out transition.
- Settings, league/club selection, alphabetical nationalities, squad browsing,
  transfers and contract terms share the right drawer. A confirms, B closes
  without committing a selection, up/down scrolls and L/R moves five entries.
  Closing an entire settings page without Apply leaves the career unchanged.
- Eight settings: League, Club, Difficulty, Match Time, Transfer Difficulty,
  Currency, Skip First Transfer Window, and Player Condition. Existing careers
  show LOCKED on League/Club and start focus on Difficulty. All values open a
  selector; there is no hidden left/right cycling on a settings tile.
- Flat navy/cyan action buttons have centered labels. The full-width helper
  strip has square corners, 32px sprite geometry, 22px text and measured gaps;
  helpers are grouped left and vertically centered, not distributed evenly.
- Hub navigation has two top and three bottom targets. The middle ranking is
  now actionable. Fixed-gap rounded indicators replace the page counter text.
  Header budgets show annual wage allocation (weekly wage budget x 52) and
  the club's transfer cash, as agreed by the user.
- The calendar is a full-width Monday-first month grid. Day zero maps to
  1 July 2026 for season one; subsequent seasons use the next calendar year.
  This is the game's calendar, not a real-world fixture feed. Cells use the
  exact core league/cup dates, venue and recorded results; selecting a day
  reveals the opponent in the detail line. Undrawn future cup pairings are
  not invented. Browsing dates does not advance time or charge wages.
- Squad opens My Squad List / Game Plan. The office Game Plan reuses the
  native squad bootstrap and existing custom editor, not a second editor.
  B at its root saves the canonical career default and returns to Squad.
  It cannot kick off, accept a match result or advance the date/fixture.
  Opening failures return to the career; a failed save keeps the editor open
  for retry. Pre-match/pause changes no longer overwrite this permanent plan.
  Explicitly saved named presets remain independent of the default plan.

Options are an aligned append-only extension to the v1 career payload. Save
version 2 reads both v1 (default options) and v2 after checking the exact
version/size/checksum; reading never rewrites the file. A/B recovery and pinned
content identity are unchanged. Back up career SaveData before testing: the
older NRO does not understand newly written v2 saves.

Transfer Difficulty has an actual game-economy effect: Normal is the old fee;
Easy purchases cost 90% and sales return 110%; Hard purchases cost 125% and
sales return 85%. The displayed quote and the transaction use the same core
function. Free agents still have no transfer fee. Skip First Transfer Window
closes only the season-one opening window, not January or later seasons.
Currency is presentation only: EUR is the canonical unit; GBP uses a fixed
0.85 multiplier and USD 1.10, not live exchange rates. Underlying cash/wages
are never converted or rounded back into storage.

The sections below describe the original v1/v2 checkpoint; this revision
supersedes their old four-target/read-only-middle layout, calendar list and
pre-match-only permanent tactics behavior.

V3 verification: 46 focused tests passed, with one user-hardware-log fixture
unavailable; 9,937 geometry subtests passed. This includes host save-v1 ABI/
checksum migration, all setting selectors, cancellation, locked focus, country
order, calendar navigation, permanent/temporary plan isolation, and native
editor save-failure/return handling. Public-tree audit: 598 files. The optional
paired-catalog test still imports all 13 leagues. The wider legacy suite's v2
caveats below remain; this is not a new all-suite or on-device pass claim.

The paired production NRO is 66,028,447 bytes, SHA-256
`70dba33e4a3a181eafaa7c02f91517713dbd9c6d652ef13d5d9bc76c50315682`.
Diagnostics/perf trace are off; ELF/NRO initialized sections, exact embedded
art/accepted badge atlas, launcher icon, source-stage equality, curated catalogs,
and pair/content identities were checked. The copy folder contains only the
NRO: `local-debug/FootballNX-MasterLeague-v3-COPY-TO-pes21_nx/`. No active
runtime or CPK/OBB/save was modified. Local instructions and verification live
under `local-debug/master-league-v3/`. The 23 layout previews there are host
software renders, not Switch screenshots. Re-check actual on-field identity
and formation after an office edit, a temporary match override, an away
fixture, and a save/relaunch on hardware.

## Agreed scope (2026-10-05)

Existing-club career, one human manager, eligible curated league plus a domestic
cup where supported, Play/Simulate, transfers and basic contracts/finances,
three independent career save slots, and season rollover. Reuse the Cup/League
match handoff, Game Plan, fonts, badge atlas, button theme and Switch helpers.
Do not revive removed leagues or change Exhibition/Cup/League rosters.

Flow: New/Continue -> Career Settings -> Manager Profile -> Career Hub.
Manager Profile has exactly two inputs: Manager Name and Manager Nationality.
Both must be explicitly provided before starting a new career.

Implementation gates:

1. Snapshot roster identities, ownership, registration and tactics per career;
   test transfers, roster limits, goalkeeper availability and mode isolation.
2. Career setup/profile, dashboard, season calendar, Play/Simulate, three-slot
   checksummed A/B saves and rollover.
3. Windowed buy/sell/free-agent transactions, contracts, wage accounting and
   board target. Financial values are game balancing, not real-world salaries.
4. Native roster/preset adapter and result idempotency; verify actual on-field
   players, not just HUD/UI names. Keep production roster baseline untouched.
5. Focused regression tests, paired full-loose build, and Switch acceptance.

No live web updates within an ongoing career. Content identity is pinned;
incompatible saves must fail closed without overwriting either backup. Player
identity uses verified BaseId/native mappings, never guessed numeric identity.
Unmapped local-only players keep their provenance identity and native ID.
Cup and League saves are not converted or overwritten.

Deferred: create-a-club, youth, full scouting/staff, complex loans, continental
competitions, promotion/relegation, and unverified native attribute growth.

## Multi-page console hub

The hub has four sections, with four large destination cards per section:

| Section | Cards |
| --- | --- |
| Home | Next Event, Club Feed, Season Calendar, Save Career |
| Squad | Squad, Contracts, Transfer Market, Club Feed |
| Club Office | Transfer Market, Contracts, Finances, Career Settings |
| Competitions | League Table, Top Scorer, Domestic Cup, Season Calendar |

Four destinations retain two navigation rows. The v2 presentation uses two
wide artwork cards above two action panels, with a read-only context panel
between the lower actions. Right/left moves between destinations; crossing a
horizontal edge enters the next/previous section, preserving the selected row.
The central snapshot is not a hidden focus target. L/R provides a direct section
shortcut. Tabs, page dots/count and a short slide make the section explicit.
The ends do not wrap unexpectedly.

Club Feed is a four-story image-card carousel. Its manager, result, season
target and transaction stories come from the current save, not invented social
posts. Lists show at most five clubs/players per page; Top Scorer shows four.
Confirmation/action buttons keep the shared FNX Cup/League renderer. Following
the user's light eFootball-style reference, v2 navigation cards use cyan/lime
focus rims over blue/crimson/teal generated artwork, white information panels,
and dark blue type on a pearl football-pattern backdrop. Actual Switch button
textures and the shared stencil/bold font atlas remain in use, without
downscaling a whole UI render target. This redesign is scoped to Master League.

Home projects the next event, up to three club fixtures, three ranked clubs and
the current save's balance/season. Other sections show squad or club snapshots.
These are bounded read-only projections of the current career; reading the UI
does not simulate a fixture, change the roster or touch a save. Long match-card
club names sit below the crests, separately from VS, to avoid collisions.

## Career state and native boundary

- Immutable player identity and native asset keys; career-only mutable club
  membership, order, shirts, contracts, budgets and presets. National teams and
  Exhibition/Cup/League's base rosters are not rewritten.
- Three career slots, each with alternating checksummed A/B copies. Reads must
  pass structural validation and match the complete catalog content hash.
  Failed reads do not replace the running career. Explicit confirmation is
  required before overwriting an occupied/incompatible slot.
- The local generator verifies native Player record fingerprints against the
  persistent identity state, plus the selector/roster/manifest pairing. Public
  source contains an empty safe catalog, never extracted player records.
- Native match handoff imports career rosters before actor creation. Formation
  and lineup edits store canonical native IDs in the career. The adapter maps
  these back to each new match's temporary, encrypted IDs; global presets are
  not repurposed as career saves.
- A played domestic-cup draw requires the actual shootout winner. The audited
  native `StatsTeamInfo::GetScore` uses HalfKind 4 for penalties and HalfKind 5
  for regulation plus extra time. Missing deciding scores leave the fixture
  pending instead of selecting a random winner. No proprietary disassembly is
  stored in this document or the public tree.
- Played/simulated events complete one calendar event at a time. Results are
  idempotent, wages accrue only for newly advanced weeks, and league scorers
  are credited only to registered identities within the reported team score.

MVP limits: domestic cups use a single leg and the existing supported cup pools;
there is no domestic cup for leagues without a supported pool. The calendar
list currently shows league fixtures; domestic-cup progress has its own card.
Transfers are explicit fixed-fee buy/sell operations, not an AI bidding system.
Strength values marked STR are simulation balancing, not claimed native OVR.
Changing the squad registration invalidates the implicit current tactics plan;
named presets with an incompatible roster are refused, not partially loaded.
Native Game Plan is available in the pre-match hub, not directly in the office.

## Generated artwork

The original v1 built-in imagegen (not API/CLI fallback) project-bound asset:
`art/master-league/manager-office-v1.png`. The same PNG bytes are embedded as
`data/master_league_background.bin`. The v1 artwork is retained as a source
reference, but its texture is no longer uploaded by the v2 UI.

Prompt: Original 16:9 football manager menu background; premium cinematic club
manager's office overlooking a floodlit stadium at night, no people, dark navy
and electric blue with restrained warm gold accents. Quiet uncluttered central
85% for UI, dark bottom 12% for controller helpers, architectural detail toward
the edges. Realistic game-environment lighting, crisp, without excessive grain
or bloom. No text, logos, watermarks, trophies, or baked-in buttons/panels.

V2 generated assets, also made with the built-in tool:

- `art/master-league/pearl-football-v2.png` ->
  `data/master_league_pearl_v2.bin`: light pearl/ice-blue embossed football art.
- `art/master-league/card-sprites-v2.png` ->
  `data/master_league_cards_v2.bin`: one 2x2 decorative atlas (blue satin,
  crimson fabric, teal tactics and a manager's office).

The exact prompt set and output paths are in
`art/master-league/v2-prompts.json`. The generated pixels contain no team names,
scores, buttons or official club crests. All actual identities and numbers are
rendered separately. Artwork sampling uses an inset gutter and aspect-preserving
cover crop; rounded-image masking is opt-in and resets to the original solid
renderer for every other custom page. Textures are uploaded once, not per frame.
The frontend-design skill informed the visual hierarchy and spacing; imagegen
supplied only decorative raster assets, not an uneditable UI screenshot.

## Verification status

Host checks cover identity uniqueness, transfer restrictions, goalkeeper safety,
calendar byes, result retries, actual shootout winners, five synthetic seasons,
save corruption/backup recovery, profile fields, multi-page navigation, feed
carousel, native preset rekeying, mode isolation and save/continue.

Focused regression run: **43 passed, 1 skipped** (optional native fixture),
including Cup/League frontend, catalog, result, save and tournament probes;
Game Plan editor/preset, pre-match lineup, live identity, hub buttons and
high-resolution compositor checks. The broader run stopped at 15 failures
with 322 passed/46 skipped; its one missing-link failure introduced by the
new frontend dependency was fixed and the FL26 Cup catalog tests rerun green.
The remaining legacy failures are not a passing-suite claim or hardware proof.

The optional paired-data test imported 304 clubs and 9,075 players, then simulated
and rolled over all 13 eligible curated leagues. The generator normalized 197
invalid/duplicate shirts in the career snapshot only; native base data is intact.

Software previews in `local-debug/master-league-v2/previews/` execute the actual
C layout/font emission, then rasterize its commands at 1280x720. They are not
Switch screenshots. They use a synthetic career, the public badge catalog and
actual Switch helper sprites. The candidate still uses the accepted private
catalog/atlas; synthetic preview names and roster values are not its game data.
Host layout checks cover eight screens, the native vertex/draw budget, atlas
gutters/aspect ratios, text line overlap, and career-projection non-mutation.
V2 focused regression: 46 passed, 1 optional-fixture skip, including three new
layout tests and 3,097 geometry subtests. Public-tree audit passes. This does not
supersede the broader legacy-suite caveats below or constitute GPU/hardware QA.

Production candidate uses the accepted full-loose pair `e861c583ec78e9ae`, dummy
OBB size 53248, diagnostics/performance trace off, authoritative OVR override
off, and the accepted selector, scorer pool, badge atlas and curated league/cup
headers. Its catalog content hash is
`97e84d7f8c21ba930bb0e13793ac46c91a60836a33902d40100d36aa5801a59f`.
Build verification compares initialized ELF/NRO sections, exact atlas and
background bytes, launcher icon, embedded pair ID, and the no-op logging stub.
No CPK, OBB, active runtime or existing save was modified for this candidate.

The broad legacy suite is not all green: it includes unavailable ignored
fixtures and older source-shape expectations unrelated to the focused runtime
probes. Running pytest from the repository root also discovers third-party
Blender tests under ignored local-debug; use `python -m pytest tests` to scope
discovery to project tests. Do not report the broad suite as passing.

Before release, verify on Switch:

1. New/Continue, software keyboard cancel/accept, nationality, page edges and
   shoulders, feed stories, long club/player names and five-row image quality.
2. Buy a player, register him in Game Plan, kick off and verify the actual
   on-field identity/model, not just the HUD; repeat for an away fixture.
3. Change starter/formation/preset, finish a fixture and start another; verify
   persistence, uniform/random conditions and save/load after relaunch.
4. Complete a domestic-cup draw through penalties, return exactly once, and
   verify the correct advancing club. Retry/quit must not advance a fixture.
5. Season rollover, expired-contract safeguards and return to Exhibition/Cup/
   League with unchanged base rosters and existing saves.

A successful production build and host tests are not Switch acceptance.

# Master League implementation

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

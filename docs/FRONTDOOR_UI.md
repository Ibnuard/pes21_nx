# Flat Matchday frontdoor

## Scope and direction

The presentation layer in `source/frontdoor_overlay.inc` covers the title,
main menu, Match/Mode choice, Exhibition and local-two-player team selector,
prematch hub, kit choice, stadium options, prematch match settings, Video
Settings, Credits, loading/versus transitions, Pause and its settings/confirm
screens, plus Half Time/Full Time overview and result menus. Game Plan keeps
its native layout with the same bright palette,
white-pattern backdrop, rounded buttons and larger bottom helpers.

White gradient/pattern artwork, blue/red side identity, large Switch helpers
and shared Master League rounded primitives define the direction. The main
menu is a compact left rail with four icon/title rows and no descriptions;
an existing unframed player portrait occupies the right. Title and menu share
the existing wordmark silhouette. No realistic stadium backdrop or ML fabric
cards are used in these pages. See `art/frontdoor/README.md` and its prompt set.

The selector keeps both featured cards coloured, including an inactive away
side. Only active/confirmed sides get a focus ring. Bottom explanatory labels
and numeric pagination counters are absent. Adjustable values use paired ML
arrow icons. Buttons align their complete icon/label group, with font cap-ink
metrics used for vertical alignment instead of the padded atlas cell.

The focused main-menu tile is 2.17x the resting height (131px versus 60px at
720p). A 260ms cubic ease-out expands it while shrinking the previous tile;
icons and titles scale subtly with it. The four weights sum to one, keeping
the rail's outside bounds and gaps fixed. Quick input retargets from the current
pose, without a jump or input lock. The UI-only motion resets outside the menu.

The active tile's blue artwork also drifts diagonally/up-down in a six-second
elliptical loop. A zoomed UV crop stays inside the focus strip's pixel gutters;
both the vertex UVs and rounded-mask UVs move together. Border, icon and title
geometry remain stationary, and inactive cards do not animate. This reuses the
existing texture and draw call, rather than decoding video or adding surfaces.

The v3 base removes the baked red/blue corner bands. Four flat vector bands
now move independently, morphing with the portrait transition and drifting
at rest. Portraits translate horizontally on alternating entrances/exits with
clipped UVs, rather than only cross-fading. No frame-by-frame asset decoding
is involved. General Settings and Stadium both display six adjustable rows;
the former scrolls when needed.

## Boundaries

The 2026-10-09 loading review anchors the LOADING label's measured right edge
to the animated indicator, with a height-scaled 10 px gap at 720p. Loading and
versus pages share this placement. Font cap alignment, animation timing,
transition ownership and input are unchanged. The production-renderer preview
verifies the compact grouping; the previous fixed label-left position left a
large empty gap after this short proportional-font word.

`frontdoor_snapshot` reads existing native/controller getters into a bounded
value structure. `frontdoor_emit` consumes that structure without mutation.
The rendering snapshot does not change native identity, roster, ready-state,
kit transactions, lineup, kickoff or saves. A separate tested kit-navigation
helper implements Left/Right container selection, A to edit, Left/Right kit
changes, B to leave editing, and a second B to return to the hub. Up/Down does
not change sides. Main-menu indices keep the existing
Match, Modes, Settings, Credits order; the native input already supports both
directional axes. Single-slot competition pickers and four-button competition
hubs use the same presentation with their existing state.

The result route uses the same team strips, score and eight-row statistics
panel as Pause. Its one, two or three centered actions come from the native
result resolver, including overtime, penalties and competition-specific return
destinations. B is shown only when a return action exists. Pause and transition
covers retain priority, and the old result geometry is bypassed.
Cup, League and Master League
pages keep their mode-specific renderers. Game Plan retains its existing
geometry and interaction path with scoped palette/helper changes. The GL dispatch selects
only one full-screen presentation path, then uses the common state restoration.

The v3 background and v2 panel-strip PNGs use the existing build pipeline. Shared draw
kind 3 samples luminance for rating stars; kind 4 tints RGB while retaining image
alpha for the navy wordmark. Existing image kind 2 is unchanged. No new shader
program, render target or per-frame image loading is introduced.

## Synthetic review and verification

```powershell
python tools/preview_frontdoor.py
python tools/preview_frontdoor.py --animate
python -m pytest tests/test_frontdoor_visuals.py tests/test_league_visuals.py tests/test_master_league_visuals.py tests/test_prematch_hub_buttons.py -q
python -m pytest tests/test_frontdoor_controls.py tests/test_league_tournament.py tests/test_cup_frontend_flow.py tests/test_league_frontend_flow.py -q
```

The preview defaults to `local-debug/frontdoor-v3-preview/index.html`.
It compiles the production C renderer and records its GL geometry, then uses
the shared CPU rasterizer to make review PNGs. Its 46 states include every
main-menu focus, selector phases/ready transitions/long names, four- and
five-button hubs, outer/inner kit focus, settings scrolling, bright loading,
Pause/confirm/Camera/Video/Credits and 1080p layout geometry.
Ratings and lineups are synthetic. The kit preview deliberately displays its
fallback without proprietary runtime textures. The gallery is not an input
emulator or a Switch screenshot.

The host driver checks an immutable input snapshot, VBO canary, finite on-screen
vertices and draw/vertex budgets. Maximum observed: 509 / 4096 quads and
112 / 384 draw records. Public asset byte equality and decoder size limits are
also tested. Native GPU/performance, controller transitions and populated kit
textures still require a device smoke test.

`--animate` adds `menu-focus-motion.gif` from 33 production-rendered poses.
Its input sequence is synthetic and the portrait is held still to isolate the
tile motion. Additional host assertions cover fast reversals, inactive/reentry
reset and identical poses at different update frequencies. Motion geometry
is stored separately under `motion/` and is always tested.
`menu-pattern-loop.gif` isolates the six-second background drift (10fps preview;
runtime updates every game frame). Sixty sampled poses plus the exact cycle end
check stable content geometry, strip isolation and a seamless loop boundary.

Windows preview galleries explicitly use UTF-8; this includes the shared Cup
writer and League reader/writer to avoid default-codepage failures.

Local canary builds must keep the existing migration catalog/roster/loose
manifest pair. The current build is isolated under
`local-debug/review-v6-production/`; it does not replace `dist/pes21_nx/`.
The previous v5 candidate remains available for comparison/rollback.

### v6 overview/results and Night coverage (2026-10-09)

The user confirmed v5 at Night/High still gives players a green cast that
varies between sides/directions; the pitch markings/textures are accepted.
The next candidate extends decoded-light coverage as described in
`STADIUM_HIGH_REVIEW.md`, retaining the accepted PAK.

Half Time and Full Time now use Flat Matchday throughout both overview and
action-menu phases. The native phase resolver, scores, statistics, controller
actions and competition result persistence are unchanged. The renderer shares
Pause's bright stats panel and blue/red team cards. A single action stays
centered at the same width as the multi-action cards; long return labels fit.

`local-debug/review-v6-frontdoor-preview/` contains 62 synthetic production-C
states, including 16 new overview/result cases: every menu focus, all four
return destinations, overtime, penalties, unavailable statistics and 1080p.
Geometry tests cover button bounds, helper availability, transition/Pause
priority, shared team-strip geometry and native VBO/draw limits. New result
states peak at 226 quads and 69 draw records. These previews do not certify
native controller transitions or match lighting on hardware.

Production NRO: 82,781,087 bytes, SHA-256
`47a1dad98e2032e49dba180889c48d50b45a30a8e11114d210b7579f43e68144`.
Diagnostics and PerfTrace are off. Build, link and embedded-icon verification
passed with the same full-loose pair `e861c583ec78e9ae` and v5 catalogs/rosters.
Focused validation passed 66 distinct tests and 756 subtests across UI,
result resolution, competition flow, Pause and lighting. A stale Pause test
required its existing guard assertion to accept line breaks; the guard itself
is unchanged. Offline GLSL validation passed all 1,000 before/after/clip-space
compiles. Public-tree audit passed (657 files); `git diff --check` passed.
The full legacy suite was not rerun; this does not supersede its known issues.

### v5 participant clarification and Night lighting candidate (2026-10-09)

League Participants always uses two columns by four rows, including a final
partial page. Card width/height, badge size and spacing are identical to a full
eight-team page. Unused cells stay empty; the old right-hand stadium picture
is removed. The user explicitly confirmed this geometry. Preview states 58
and 59 under `local-debug/review-v5-league-preview/` show the full/final pages.
All 59 preview states rendered; the six League visual tests and 186 subtests
passed, including identical geometry and absence of a filler image.

The production NRO is 82,776,991 bytes, SHA-256
`216e4870d32b5bfccbd143ac7f254407030c4c32560449bd0d60d45e19eb9385`.
Diagnostics and PerfTrace are off, with the same full-loose migration pair
`e861c583ec78e9ae`, catalog and roster flags as v4. It includes v4's GPU-pool,
HUD ownership and LEFT/RIGHT helper changes. The new scoped Night/High
indirect-light compensation is detailed in `STADIUM_HIGH_REVIEW.md`; its
appearance and effect on the green cast are not yet verified on Switch.
No new PAK is needed for this candidate. Keep the existing PAK, OBB, LooseCpk
and saves; replace only the NRO after backing up the installed one.

The focused regression run passed 105 tests and 54,429 subtests; one optional
native-binary HUD test was unavailable. An additional numeric-helper test
passed for disabled identity and colour bounds (the final six-test Night
policy rerun passed with 250 subtests). Native compilation/linking, offline
GLSL compilation and the 657-file public-tree audit succeeded. Hardware smoke tests remain necessary;
neither post-match lag nor random crashes are certified resolved.

### v4 partial-page, HUD and GPU-pool review (2026-10-09)

- Kit container navigation now says LEFT / RIGHT, not P1 / P2. Editing still
  says PREV KIT / NEXT KIT; the two-stage controls are unchanged.
- League Participants keeps the same four-row geometry on every page,
  including a 19-team season's final three entries. Badge and card dimensions
  no longer grow to fill the remaining vertical space.
- User confirms the persistent slowdown also occurs on Low, survives returning
  to the main menu and clears only after restarting. This separates the report
  from the High-only green cast, but does not identify its cause by itself.
- The replacement Nouveau buffer pool previously handed an entire coalesced
  free range to a smaller request and retained every empty slab indefinitely.
  Free ranges now split to the aligned request size; one empty 2 MiB slab is
  retained per native cache and additional empty slabs release the pool's BO
  reference. Vacant descriptors are reused without moving live handles. The
  native 24-byte handle ABI, deferred frees and external BO references remain.
  Oversized requests that would overflow alignment fail without allocating.
  No forced per-frame GPU synchronization or blanket texture purge is added.
- The HUD, like League scorers, now sends only portrait IDs from the render
  thread. Two bounded mailboxes transfer requests to the game-thread file/LRU
  owner, which publishes independent PNG copies. The render snapshot no longer
  polls native portrait files or reads that LRU. GPU-resident IDs skip duplicate
  decode/upload/mipmap work, while evicted IDs can be requested again. Native
  player-identity reads are not claimed to be removed by this change.

`tests/test_gpu_buffer_pool.py` compiles the production allocator with fake,
reference-counted BOs. It exercises range splitting, 250 repeated 24 MiB load/
release cycles, allocation failures, overflow, external-reference lifetime,
cache separation and four concurrent allocation/free workers. Before the fix,
all five cases failed; after it, retained empty memory returns to at most one
2 MiB slab per cache. This is host allocator evidence, not Switch frame-time
or native driver validation. On a Linux host, optional sanitizer coverage is:

```sh
PESNX_POOL_SANITIZERS=address,undefined python3 tests/test_gpu_buffer_pool.py -v
```

Additional executable tests verify HUD request coalescing, PNG copy ownership,
and no extra upload for 1,000 repeated resident-portrait deliveries, including
eviction/reload and GL state restoration. The v4 synthetic galleries are
`local-debug/review-v4-frontdoor-preview/` (46 states) and
`local-debug/review-v4-league-preview/` (59 states). These use production C
geometry and synthetic teams; kit textures are deliberately unavailable there.

Production NRO: `local-debug/review-v4-production/pes21_nx.nro`,
82,768,799 bytes; SHA-256
`4ef40c29718e5f1a92e60e2234f92db183396ab417703f72dd5757ee3c45ad65`.
Diagnostics and PerfTrace are off. It retains the v3 full-loose build pair
`e861c583ec78e9ae` and the same migration/catalog flags. Install the NRO alone
first, retaining existing PAK, OBB, LooseCpk and saves. Repeated full matches,
replays, menu returns and Low/High behavior require hardware verification;
neither the reported lag nor random crash is declared resolved by host tests.
The separately supplied PAK control is diagnostic only; see
`STADIUM_HIGH_REVIEW.md` before testing it.

Final focused validation: 100 tests and 54,179 subtests passed; one optional
native-binary HUD test was skipped because its user-owned fixture is absent.
All five allocator cases also passed with Linux AddressSanitizer/UBSan.
Native Switch compilation/linking succeeded. These results do not supersede
the earlier unrelated legacy-suite failures recorded below.

### v3 control/stability changes and production candidate

Risky-action confirmations use the shared Master League white/navy modal:

- Pause > Top Menu keeps its existing default-Cancel gate, now explicitly
  warning that unfinished match progress is lost.
- Explicit Cup/League saves check both A/B file copies before writing. Any
  occupied, unreadable or incompatible slot requires Overwrite confirmation.
  Unreadable data is not labelled as an empty slot. A cancelled prompt leaves
  both copies byte-identical; an overwrite failure does not exit the slots page.
- B from the Cup/League home hub (and a completed Cup's Top Menu action)
  warns that progress since the last save will be discarded. Cancelling keeps
  the page, focus and competition; the news carousel is paused behind a modal.
- Master League retains occupied-slot/release confirmations, adds Save & Leave
  and next-season confirmation, and defaults irreversible simulation to Cancel.
  Failed saves keep the career open. Normal progression autosaves and explicit
  Quick Save to the active career slot remain unchanged.
- Game Plan's explicit preset Save and Load both prompt before replacing stored
  tactics or the current unsaved lineup. Each controller has independent modal
  state; the target slot is frozen, Cancel restores slot focus, and live-match
  preset restrictions still apply. No preset/save format changes are introduced.

These dialogs start on Cancel. A selects the highlighted action; B cancels.
Competition/ML modal input blocks background shortcuts and prioritizes B over
simultaneous accept input. Navigation cannot also accept on the same input tick.
Tests cover held A, mixed buttons, repeated prompts, target retention, corrupt
B-only saves and byte-preserving cancellation in temporary test directories.
Cup/League preview tools include overwrite/cancel and leave-unsaved states.

- Match Hub Back queues native teardown onto Cobra's game-thread input tick.
  A missing flow listener defers teardown; the loading cover stays until the
  native Main Menu reconstruction restores the competition hub. Frontend
  regression tests assert that an aborted fixture is still pending and can
  reopen with the same teams. Device verification of the reported loop remains
  required; a host stub does not certify native flow completion.
- The League renderer no longer polls native files or dereferences the
  game-thread portrait LRU. Five atomic ID mailboxes coalesce requests, and the
  game thread publishes independently allocated PNG copies. This removes a
  concrete cross-thread eviction/read risk, but does not prove that the user's
  random menu/after-match crash was an out-of-memory failure. No crash report
  has been supplied.
- Optional Switch button textures are attempted once per GL context even if
  one image fails. A partial failure no longer reloads all helpers each frame.
- No-human-opening-bye rules and their capacity limits are documented in
  `FL26_CUP_IMPORT.md` and `FOOTBALLNX_LEAGUE_DESIGN.md`. Host coverage checks
  2–32 teams, 1–8 owners, rejected swaps and unchanged brackets on rejection.
- Production NRO: 82,776,991 bytes; SHA-256
  `d7ece4ccddd59de290f16053eaeaaf0b42b93950c34e5bdd73cd5af24d525524`.
  Diagnostics and PerfTrace are off. The full-loose migration uses pair ID
  `e861c583ec78e9ae`, dummy patch OBB size 53,248, the existing October 5
  migration selector/rosters, curated FL26 catalog and ML v1 catalog. The
  existing active NRO, saves and user PAK were not replaced.
- Focused v3 renderer/control/tournament/save/material checks passed (73 tests
  and 54,164 subtests, including confirmation cancellation and save protection).
  Native compilation/linking and public-tree audit passed. Actual GPU motion,
  populated kits, repeated match returns and Night/High lighting need hardware
  smoke tests. The PAK tint A/B is diagnostic-only; see `STADIUM_HIGH_REVIEW.md`.

### Earlier v2 verification (2026-10-08)

- Final Switch canary build succeeded (82,842,527-byte NRO). Only existing
  unused-helper warnings remain; the live runtime is untouched.
- 39 focused tests passed across the new layout/motion (12), League layout (5),
  Master League layout (18), prematch button contract (2), and Cup/League
  frontend flow (2). The ML harness passed when rerun separately after its
  60-second timeout during a concurrent build.
- Cup production geometry also completed all 38 synthetic states (pixel
  rasterization skipped for that smoke check). Public-tree audit and
  `git diff --check` passed.
- Broader legacy checks: 19 passed, one skipped, five existing failures. The
  failures are the stale match-settings count assertion, the removed
  `league_emit_text` test-slicing marker, and three catalog/legacy-roster
  assertions. The marker failure was reproduced against `HEAD:source/overlay.c`;
  the other failing tests and their native/catalog dependencies are unchanged
  from HEAD. They are not reported as passing UI regressions.

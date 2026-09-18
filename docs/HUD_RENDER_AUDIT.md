# HUD render candidate — 2026-09-16

## Native visibility ownership — 2026-09-19

The fixed bottom nameplates now follow the exact native
`match2D::Screen::Time::NeedDisp` result. A fresh native scoreboard heartbeat
is required, so the cards disappear with the scoreboard under the large
kickoff/match banner instead of relying on a guessed ball-motion delay.

Goal actions similarly require the exact native
`ButtonGoalPerformance::NeedDisp` result. The broader GoalDemo heartbeat is
retained only for lifecycle isolation; hidden black hand-offs cannot render or
accept A/B. The own-goal latch is no longer cleared by a reusable GoalDemo
page rearm when `IsOwnGoalDemo` has just classified the same goal.

## Set-play power gauge and authentic shirt numbers — 2026-09-19

- **Shirt number resolution**: 	mpdb::util::GetUniformNo defaults to 10 (#0xa)
  when a player's ID is not present in the static tmpdb database (such as updated
  transfers or migrated squads). Shirt numbers are now resolved directly from
  authoritative master rosters (xhibition_find_roster) using the player's 32-bit
  unique identity, falling back to GetUniformNo only when uncatalogued.
- **Set-play power gauges**: Custom action power bars now render for the four
  dead-ball situations (corner, close free kick, far free kick, goal kick)
  even though IsInplayTime() reports false. A bottom-centered fallback anchor is
  used when 3D cursor foot projection is absent. Gauges are strictly dismissed on
  replay transition, goal demo, pause, cinematic, or when button hold duration
  exceeds 120 frames (2 seconds) to avoid lingering on lost balls.

## Post-checkpoint away-card mirror — 2026-09-18

Checkpoint `53874bf` (`checkpoint-nameplate-day-pitch-v2`) preserves the
accepted HUD/settings/goal-helper build. The right-side card now anchors its
name-number line at the right edge of the text cell, immediately before the
portrait, and fills its stamina strip from right to left. Cell order remains
name, shirt number, portrait, crest; the left-side card is unchanged. Switch
visual confirmation is pending.

## Nameplate checkpoint follow-up — 2026-09-18

The accepted custom portrait/crest/name/number/stamina card is checkpointed at
`1714d84` (`checkpoint-nameplate-hud-v1`). General Match Settings now exposes
`SHOW NAME PLATE`, default ON. It gates only the custom card; native stamina
gauges remain hidden and simulation remains untouched.

Goal helpers use one right-side group in both one- and two-player matches.
Full controllers share one sprite. When horizontal Joy-Con profiles require
different buttons, both sprites are separated by `/` before one common label.
The helper also requires a current interactive-button heartbeat (120 ms) and
is suppressed as soon as native Replay owns the transition, preventing it
from surviving the two black goal/replay hand-offs. Hardware validation of
the transition timing is still required.

## HUD diagnostic capture — 2026-09-18

Hardware capture: 22 live samples, 18 with zero cards despite valid fresh
stamina and no lifecycle blocker. One live row reports identity_fail=1219,
identity_ok=821, snapshot age=4 ms and power=960/990. Both fixtures had already
captured 18 stable MemberId identities. The resolver incorrectly required a
temporary tmpdb player before consulting that map. Use the team-validated
captured identity first, with jersey captured before kickoff and portrait ID
derived from its authentic common PlayerId. Retain live order-to-member
resolution for substitutions. Do not cache a previous player's card on a new
selection. The HUD image pass also unbinds/restores native samplers, matching
Game Plan, because HUD textures do not necessarily have native-scene mipmaps.
These corrections remain pending hardware confirmation.

The next capture shows all 15 live samples returning two cards except the
first and one transient sample, but identity failures still accumulate and
reveal alpha repeatedly returns to zero. Keep the last validated identity for
the same team and PlayerNo for up to 500 ms; this bridges transient OrderInfo
rebuilds without carrying a previous player across a normal control switch.
The first successful lookup and substitutions refresh the cache. Current-player
portraits are requested through the existing asynchronous FileThread path,
copied into the overlay upload queue when ready, and never synchronously read
from the gameplay/render path.

The first complete hardware render confirmed the card, crest and identity but
exposed presentation-only issues. The layout now uses distinct padded crest,
portrait and text cells. The stamina track is inset inside the text cell and
starts on the same x coordinate as the shirt number instead of spanning the
whole card. Entrance state is keyed to a MatchSetup session serial: it runs
once when each side first appears, while cursor changes, replay, pause and
loading simply hide or replace content without replaying the animation.

Hardware layout validation then exposed two lifecycle details. IsInplayTime is
already true while the initial kickoff ball is stationary, so the card now
latches on only after native GlobalRegistry BallInfo has moved 0.5 world units
from its MatchSetup anchor. Cursor hand-off can also publish a new PlayerNo one
frame before tmpdb identity is available. The overlay-facing snapshot retains
the previous complete card during that gap and atomically replaces it once the
new portrait/name/number/stamina tuple resolves; the plate no longer vanishes
for an intermediate frame. The inset stamina palette is raised slightly to
retain contrast against the dark card.

The direct-PlayerInfo candidate still fails on hardware. Build with
`-Diagnostics` plus the full loose CPK arguments below to record
`[HUD-DIAG-v1]` in debug.log once per second. No visibility policy is changed
by this diagnostic. Publisher counters separate bad model, non-inplay,
invalid side/player and missing registry data; identity counters show card
resolution failures. Each row includes every lifecycle gate, snapshot ages,
overlay blocker bits, returned card count, reveal alpha and cumulative draw
submissions (submission does not prove visible pixels).

Overlay bits: 0 popup, 1 modal frontend, 2 tutorial, 3 startup transition,
4 start prompt, 5 main menu, 6 controller surface. Counters are cumulative.
Capture kickoff followed by 30 seconds passing, pause/resume and a replay,
then preserve debug.log before relaunching, which overwrites it.

## Helper transitions — 2026-09-18, V11 candidate

Pause and pause-loading ownership now clears set-piece, goal-action and penalty
helpers before overlay drawing. In particular, stale goal-kick L/context flags
must not appear above a pause submenu transition. The native free-kick
heartbeat also overrides the ambiguous PositionShift bit, retaining only Set
Piece Taker for a long free kick. Unknown-context fallback no longer constructs
Position Shift from raw bits. Host tests cover modal flag combinations and
fresh/stale free-kick precedence; Switch transition timing remains unverified.

## Current policy — 2026-09-18, custom stamina candidate

All four native `ModelStaminaGauge::GetDisp` slots remain hidden and General
Settings still has no SHOW STAMINA toggle. CursorName slots now publish only the
authoritative player identity and stamina percentage already maintained by
`Manager::UpdateNamePlateInfo`; no native canvas draw, fill-order patch, or
stamina simulation hook has returned. A lightweight rounded overlay line is
attached to a fixed bottom-corner player card and eases in over 220 ms.
The card includes a translucent dark-green plate, cached native portrait,
team crest, shirt number and player name. The in-match order-to-member mapping
resolves identity across substitutions. The old floating stamina line is
replaced. Portraits reuse the prematch texture cache without synchronous
asset reads in gameplay; missing assets leave the portrait space empty.
For the COM opponent, use the NPC nameplate record that native CursorName
slots 2/3 consume (+0x488 visibility, +0x48c side, +0x490 PlayerNo, stride 0x20)
and read its percentage from PlayerInfo. A missing controller cursor must not
silence that opponent card.

After the refresh correction, hardware still reported occasional flashes.
Fixed cards now ignore the above-head presentation fields +0x1a0, +0x195 and
NPC +0x488 when selecting a valid side/PlayerNo. Both sides obtain stamina
directly from GlobalRegistry::GetPlayerInfo / GetStaminaPercentage, rather than
the gauge's cached percentage. Native stamina simulation was never disabled:
GetDisp remains zero for all four slots, so no native gauge is re-enabled.
Host regression covers hidden native presentation, invalid cursor, stale cached
percentage, invalid identity and non-inplay rejection. Switch confirmation is
still required; the individual runtime gate causing flashes was not logged.

The publisher requires native `Utility::Info::IsInplayTime`, a fresh mobile
control heartbeat, a normal controller surface, and no replay, goal demo,
cinematic, pause, result, or virtual-cursor owner. Losing any gate removes the
overlay immediately (there is intentionally no fade-out), so prematch intro,
set-play waiting, replay, and menu transitions cannot retain stale stamina.
This candidate is host-verified but still requires visual/lifecycle validation
on Switch hardware.

The custom kick-power gauge shares the same live-play gate, including native
in-play state, replay/fixed-demo ownership, pause/loading ownership and an
80 ms freshness limit. Both card and gauge remain hidden outside live play.
Do not gate the replacement HUD on native Info +0x1a30. Its interpretation as
a scene-cover flag was not established, and the candidate that copied this
native gauge suppression gate showed no cards on hardware. The replacement
now uses IsInplayTime and explicit replay/pause/loading ownership instead.
This correction still requires hardware confirmation; the screenshot alone
does not establish which individual gate was false.

The follow-up hardware report still shows missing cards with brief flashes.
The publisher is therefore moved out of the disabled stamina GetDisp path to
the existing CursorName GetPosition hook, including NPC slots 2/3. Both models
reference the same Utility::Info at +0x18. Explicit lifecycle gates and the
80 ms limit remain unchanged; this does not keep cards alive through transitions.
The snapshot clock is sampled after its producer timestamp, avoiding unsigned
age underflow if the producer updates between reads. Hardware validation of
this refresh correction remains pending.

Build this candidate for the deployed full loose CPK runtime with:

```powershell
.\build-wsl.ps1 -PlayerMigrationCanary -LooseCpkFull -ExpectedPatchObbSize 53248 `
  -BadgeAtlas local-debug/full-mobile-kit-migration-v1/league-branding/badge_atlas.bin `
  -MigrationTeamInclude local-debug/full-mobile-kit-migration-v1/league-branding/exhibition_teams_migration_generated.inc `
  -Jobs 8
```

The plain build command selects the legacy large-OBB profile and is incompatible
with this installation. The first custom-stamina NRO was built with that wrong
profile and rejected the 53,248-byte placeholder at boot. Replace only the NRO;
the installed dummy OBB, LooseCpk assets, pitch and saves do not need replacing.

The following sections document historical experiments, not current behavior.
No FPS improvement is claimed from hiding the gauges without a hardware A/B.

Status: **failed hardware experiment, removed from current source**. This file
records why it must not be repeated. No OBB/CPK or roster changes were involved.

## Stamina

The current source no longer contains the old height/scale experiments. Native
`ModelStaminaGauge` supplies active fills in slots 0/1, plus full-power dark
tracks in slots 2/3 (`GetColor`: RGB 17/17/17). Native `Primitive::DrawBuff`
also submits each stamina model as two separate triangle items: a textured
plate and a vertex-colored fill using `GWhiteTexture`.

This establishes multiple overlapping draws; it does **not** prove from static
analysis whether the hardware symptom is batch ordering, sampling, or clipping.
The failed candidate attempted to remove those ambiguities locally:

- It suppressed the duplicate dark-track slots after its hook installed.
- It deferred the plate submission and replaced the stamina fill with one
  white-texture triangle item containing a dark track followed by the fill.
- It obtained bounds, remaining-power width and fill color from the native
  items in that same call. No saved world positions or delayed overlay snapshot.
- It preserved the outer rectangle and targeted an 80%-height fill.
  a 10% inset at each edge; no fixed 720p coordinates or height multiplier.
- It used centered white-texture UVs and an ordinary canvas batch.
  custom texture sampler/stencil parameters. Other UI batches are untouched.
- It used stack-only scratch geometry without readback or heap allocation.
  per-frame logging, synchronization, or new heap allocation in the wrapper.
  On hardware, however, stamina disappeared completely. The ABI guards were
  insufficient evidence that the reconstructed item state was valid.

Frozen libUE4 ABI:

- `FCanvasUVTri`: 0x60 bytes, three XY/UV/RGBA float vertices.
- `FCanvasTriangleItem`: texture at +0x38, parameters at +0x48, triangle array
  at +0x50. Its native Draw method copies vertices into `FBatchedElements`.
- `Primitive::DrawBuff` (0x03f0d064) +0x2c0c: defer plate `DrawItem`.
- +0x30d8: guarded four-instruction trampoline, resume +0x30e8. The first
  item's copied vertex array remains alive at this point.
- Shared `UCanvas::DrawItem` entry and PLT are **not** hooked.
- Unknown instruction layout leaves the original stamina renderer enabled.

## Camera

The checked-in camera correction is an 80% planar ball-target bias, not the
older ten-unit threshold. Further along, `gcViewTraceBroadcast` quantizes X/Z
through `FCVTZS`/`SCVTF` pairs at +0x84/+0x88 and +0xa4/+0xa8. Its grid cell
depends on the native trace parameters and current scale. Crossing a cell can
therefore make a continuous target jump before interpolation.

The failed candidate bypassed both snaps. Hardware testing made frame glitching
worse and visible across every camera mode. Therefore this shared trace routine
cannot be treated as broadcast-exclusive despite its symbol name. The patch was
removed; it must not be revived without a verified runtime camera-owner gate.

## Small eFootball text

Switching the existing 48px atlas to trilinear mipmaps produced no visible
improvement on hardware and was reverted. The next attempt must change the
source rasterization/atlas strategy, not only the texture filter.

## Hardware result

1. Stamina: not drawn at all.
2. Camera/HUD: worse frame glitching across all camera modes.
3. Small eFootball text: still visibly rough.

## Follow-up candidate

The next candidate avoids all three failed mechanisms:

- Stamina keeps the native four models and native canvas path. Three guarded
  instruction changes swap slot semantics so full dark tracks draw first in
  slots 0/1 and live colored power draws afterward in slots 2/3. There is no
  draw hook, reconstructed canvas item, scale or height override.
- Camera correction remains inside the single-caller Broadcast ball-position
  calculator. A ten-unit deadzone blocks physics micro-motion, with a smooth
  eight-unit ramp to a capped 35% correction. The shared trace routine is not
  modified.
- Small eFootball text uses dedicated 20x24 hinted glyphs stored in separate
  atlas rows, selected at 21 screen pixels and below. Large glyph rows and
  texture filtering remain unchanged.

## Lesson from local verification

- Failed build: `local-debug/hud-render-v1/install/pes21_nx.nro`.
- SHA-256: `2fee72bd5487ebf71b4d0162a3d7a804438a9a3c01271be59a98e2a6348a44b6`.
- All 13 guarded instruction words matched the supplied ARM64 `libUE4.so`.
- Linked trampoline disassembly checked against the native stack offsets,
  replayed instructions and resume address.
- 83 source/host regressions passed, yet hardware behavior failed in all three
  target areas. These tests were structural and cannot be treated as visual or
  frame-pacing validation.

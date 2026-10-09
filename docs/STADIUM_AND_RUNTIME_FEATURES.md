# Stadium and runtime feature audit — 2026-10-09

This audit follows accepted Stadium Lite v5 (`7f6bdff`). The new implemented
change is the v6 **High Day pitch grade**; the features below are proposals,
not functionality included in that NRO. Night, roof receiving on players,
accepted faces and Indonesia commentary remain the baseline.

## Stadium settings

`exhibition_apply_match_settings` in `source/ue4_hooks.c` writes season,
weather, turf length and pitch condition into both the native stadium init
snapshot and the available match setters. Thus these controls are not merely
labels. That write does not establish a visible effect or a physics effect.

The owned cooked stadium inventory contains one complete match stadium,
`bg_lighting_AM1` / `st029`, with Day High/Low/no-stand and Night High/Low
sublevels. `AStadiumLoader::GetFName` selects its level using stadium name,
time of day and quality. This audit found no separate cloudy/rainy seasonal
sublevels for that stadium. The wrapper has no tested visual implementation
for the current Fine/Cloudy, Summer/Winter, turf length or pitch condition
controls. Do not describe those options as working weather or ball physics.

AUTO/HOME/AWAY is currently selector state, not three stadium models. It is
also not applied to a native stadium-ID setter by the match-settings handoff.
The `st069` demo maps are not an additional complete playable stadium.

A future implementation should expose an actual stadium catalog and resolve
HOME/AWAY from a team-to-stadium map, with an explicit installed default.
Weather presets need their own renderer wiring: neutral directional/ambient
light for Cloudy, and bounded particles/material changes if Rain is added.
Turf length and wetness need a controlled gameplay test before being presented
as ball-speed changes. Unsupported combinations should be clearly unavailable.

## Football Life stadium conversion

The local FL26 install includes Anfield, Etihad and other stadiums. Its stadium
assets include Fox `.fpk`/`.fpkd`, `.fmdl`, `.ftex` and PC material definitions.
This runtime consumes UE4.22 Android cooked meshes/materials/maps. Copying a
FL folder or Sider module into the Switch installation will not load a stadium.

A conversion experiment is plausible, but no complete stadium conversion has
been validated. Start with one stadium and convert the static shell, textures,
UVs, scale and orientation; simplify geometry and texture sizes before cooking.
Then bind pitch, crowds, adboards, cameras and collision, and supply compatible
Day/Night materials. Roof dimensions and the analytic shadow proxy must be
authored per stadium; applying the current Konami proxy unchanged would produce
incorrect shadows. Measure memory and frame time on device before adding more.

Pitch patterns can be a separate stadium/profile attribute. Multiple striping
textures do not require importing multiple complete stadium shells. Keep line
placement, pitch dimensions and ball/player coordinates unchanged.

SmokePatch documents its PC stadium server and team mapping in
[Sider stadiums](https://www.pessmokepatch.com/2024/11/siderstadiums.html).
Its compatibility statements concern PES PC/Football Life, not this UE runtime.

## One runtime asset archive

This is a practical wrapper feature. `source/overlay.c` loads CupLogos and
LeagueLogos using project-owned PNG readers. `source/team_commentary_policy.h`
reads the Indonesia `.nxcp` delta through a project-owned loader as well.

Proposed format: one versioned `FootballNX.assets` containing an indexed table
of normalized paths, offsets, lengths and checksums, followed by file payloads.
Read only the selected entry into existing bounded buffers. PNG and compressed
audio already have compression, so the initial benefit is fewer SD files and
simpler updates, not a promised large reduction in bytes or RAM.

Use one shared reader, preserve exact payload bytes, validate offset/length
bounds and checksums, and support loose-file overrides plus a legacy fallback.
Migrate the three named folders first. Preserve the accepted commentary delta
and its native source-bank verification. Keep saves writable and separate;
existing engine PAK/CPK data is outside this first archive migration.
Embedding all assets in the NRO would unnecessarily tie content updates to a
rebuild. No archive or loader migration is included in v6.

## 3D referee and other FL assets

The owned Mobile PAK still contains referee face/hair packages. The library
also contains `CreateHumanReferee`, referee appearance/uniform loading and
referee animation paths. These are useful leads, not proof that a live-match
referee actor is currently created, rendered or fully usable.

First investigate the native spawn/load/visibility gates, including the
distinction between cutscene referees and a live-match referee. A working
on-pitch actor needs movement, animation, placement and collision behaviour,
with a measured draw/skin cost. The installed FL referee add-on contains kit
textures; those do not implement a referee's AI or match integration.

Other suitable asset-conversion candidates include balls, boots, kits, adboards
and more faces. Each still needs an explicit identity/material/import policy.
PC Sider gameplay modules, executable patches and AI features cannot simply be
copied into the Android library. See SmokePatch's
[Sider functions](https://www.pessmokepatch.com/p/sider-functions.html) for what
its PC add-ons actually supply. Keep converted proprietary payloads local.

## Kick feint, cancel and goalkeeper rush

These are different behaviours and should be tested separately:

| Requested action | Native evidence | Proposed Switch default |
| --- | --- | --- |
| Shoot, then Pass before contact | `ThinkUnitKickFeint::ExecClick` returns a kick-feint command; `ActionKickFeint` and fake-shot animation logic exist | Y, then B during the accepted pre-kick window |
| Cancel a queued kick/movement | Native `ThinkUnitSuperCancel` is implemented; the mobile variant's update is a stub | Verify the native chord and cancellation state before assigning/documenting buttons |
| Rush the goalkeeper | `ThinkUnitKeeperPress::Main` reads held button state and returns its action while held | Hold X while defending, equivalent to the requested Triangle/through-pass action |

Current play uses the native pad adapter, not only synthesized mobile touch.
`source/native_pad_lab.inc` replaces MobileShoot/Pass/SuperCancel with native
units, but does not explicitly add KickFeint or KeeperPress to its replacement
list. Unrelated native entries are retained, so static inspection alone cannot
prove those actions never appear in an original list. Merely finding a symbol
does not prove a current controller gesture works.

The next experiment should verify native object kinds/vtables and button IDs,
then schedule the existing units in the correct attacking/defending contexts.
Keep per-pad ownership for P1/P2 and avoid changing CPU control. Test short and
long passes, charged/released shots, cancellation before/after ball contact,
keeper hold/release, both teams, rematch and set plays. A post-contact button
press must not retroactively cancel the kick. No new control mapping ships
in v6; these behaviours can be explored in the mobile engine without a FL port.

## Suggested implementation order

1. Device-check the Day-only v6 colour change against accepted v5 Night.
2. Prototype native kick feint and goalkeeper rush independently of lighting.
3. Add the shared asset archive, retaining compatibility with loose files.
4. Wire real stadium/weather profiles; trial one converted FL stadium.
5. Investigate the live 3D referee using the available native assets first.

Raw extracted assets, library disassembly and local build artifacts remain
ignored. This document records findings and proposed work, not a claim of
hardware performance or completion of the future features.

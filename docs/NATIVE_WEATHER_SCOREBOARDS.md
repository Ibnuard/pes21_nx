# Native weather and competition scoreboards

## Camera weather v13 (10 October 2026)

Device feedback accepts v12 pitch patches but reports poor motion/frame pacing
in **Fine as well as Rainy**, first noticed around the earlier precipitation
updates. This is temporal correlation, not a measured GPU diagnosis. Still
screenshots cannot distinguish low presentation FPS from low-resolution edge
aliasing. No device FPS recovery or locked 60 FPS is claimed for this candidate.

v13 removes all per-material haze and lens calculations from native character,
stadium and pitch outputs. Pitch weather remains world-anchored, reduced from
three noise octaves to two; the fine snow breakup reuses existing detail. The
roof toggle uniform is submitted only on a value change, program invalidation
or first use, rather than every draw bind, including during Fine weather.

Camera effects now use **one fullscreen alpha-mask draw** inside the existing
overlay state-save/restore region, before wrapper player cards. Two 256x144
luminance masks are generated once on first use and retained across matches:
about 72 KiB base texture storage total, plus mipmaps and one 36 KiB scratch
buffer. There are no scene copies, blur passes, per-frame texture uploads or
falling particles. Rain has a neutral white veil and soft condensation rings;
Rainy + Winter has a cooler, stronger veil with sparse fixed frost beads on the
lens. Both keep the central action area free of beads and soften coverage over
native score/name bars. Fine/Cloudy perform no weather overlay draw. Live play,
replay and goal scenes may show the lens; menus, pause and loading suppress it.
The camera veil is not physically simulated fog, blur or droplet refraction.

`frame_pacing_sample.h` accumulates presentation intervals in memory during
live gameplay for every weather. On leaving live play, after at least 120
samples, the release journal records average/worst interval, counts above
20/30 ms, weather/season and the observed viewport. There is **no log I/O during
live play**, no GPU readback/query, and pause gaps are excluded. These timings
are not GPU execution times or native simulation FPS. Play Fine and Rainy for
20 seconds each, then pause before collecting `scene-runtime.log`; also note
whether referee-probe.txt was enabled. This permits a device comparison without
changing the user's resolution or silently forcing graphics/FPS preferences.

Implementation update, 2026-10-10. This follows
[the source/runtime audit](SCOREBOARD_WEATHER_AUDIT.md).

## v11: ordinary mesh precipitation and referee loading isolation

The latest v10 device journal was recorded **after removing the referee
probe**, as confirmed by the user. Rain reaches 638/637 simulated particles,
one registered emitter and a scene proxy, but remains invisible. There are no
referee events in that session. This establishes a weather visibility problem
independent of the probe; it does not diagnose the separate on-probe report
of whole-player blinking. Snow invisibility is user reported, not present in
that particular journal. Particle counts/proxy presence are not draw evidence.

v11 replaces Cascade with an authored static-mesh field through the regular UE
primitive renderer, the same renderer used by the stadium. Rain has 768 drops /
3,072 triangles; Snow has 640 flakes / 2,560 triangles. Each drop is two crossed
quads. A masked, unlit, two-sided material animates vertex height from an encoded
UV phase and one bounded scalar clock. There are no image textures, per-drop
actors, collision traces, dynamic lights or CPU vertex-buffer updates. The
field follows camera focus in 50 cm increments, clips to the pitch rectangle,
tests scene depth and does not cast shadows. It is not a Switch screen overlay.

The game-thread clock wraps at 24 seconds (a whole number of fall/sway cycles)
and freezes during menus/pause. A single deferred `StaticMeshActor` is configured
before registration, owns its mesh/material, and is retired before stadium
unload/destruction. All retained UObject references are weak. Fine allocates
nothing. The first-live-frame gate remains: no optional field is loaded during
the stadium intro. Native weather/ball-surface handoff is unchanged. The new
PAK and NRO must be installed together under the existing filenames.

Source tools: `weather_field_mesh.py` creates deterministic centimetre OBJ
geometry; `ue_create_weather_field.py` imports it and authors the materials;
`pack_weather_assets.py` admits only these meshes and their ES2/ES3.1 materials.
`ue_create_weather.py` remains the historical Cascade authoring tool; it is
not the v11 packaging input. The native ABI retains the Android 40-byte
FTransform and 8-byte FName, not the Win64 editor layouts.

Two referee issues are corrected without changing its model/animation bank:

- Native player loads and shared uniform jobs drain **before** the optional
  Human is enqueued. Readiness is checked again after enqueue. An optional
  uniform preflight timeout lets a native-ready match continue without the
  referee, rather than waiting indefinitely.
- Native `VisionModelFramePool::SetDisp` allocates timestamped queue entries;
  visibility persists after consumption. The wrapper now sends visibility only
  when it changes, instead of allocating another command every write frame.
  This also avoids queue churn during held pause/replay poses.

These corrections are candidates for the reported blinking; neither its
device root cause nor its elimination is established. No global GL routing,
player buffers, player visibility or renderer-creation hooks are changed here.
The EF10 animation bank is retained; full EF10 AI is still not ported.

Local v11 validation includes 60 match lifecycles, paused clocks, long-session
clock wrapping, partial-spawn rollback, unavailable assets, invalid weak
references, native preload/uniform barriers, bounded visibility queues, mesh
budget/phase/bounds checks and the compatible library's bindings/layouts.
Desktop captures compare Fine, Rain and Snow at two times against a green
floor and depth occluder. These establish local visibility/movement, not Switch
rendering, FPS or freedom from blinking. The focused run passed 46 tests and
147 subtests. At 720p, Rain differs from Fine in 5,969 pixels and Snow in 1,959
(RGB delta >24); changing the clock moves 11,661 / 3,866 pixels respectively.
Removing the test occluder reveals 144 rain / 42 snow pixels inside its bounds,
confirming depth occlusion in that desktop capture. Android cook completed
without errors/warnings and all eight PAK members roundtrip with both ES2 and
ES3.1 shaders. Build, cook, tests and hashes are recorded in the ignored v11
release verification report. Device comparison
must preserve separate probe-off and probe-on logs before reopening the game.

## v10: recover the Rain/Snow stadium-entry regression

The v9 device log supplied on 2026-10-10 stops immediately after `Rain spawned`
on **Konami Stadium**, before the two-second particle report or the referee's
prematch loading barrier. The user reports the same crash with Snow/Winter;
Fine has not been tested. The log confirms FX creation and component spawn
returned, but contains no stack trace and cannot identify the crashing call.
v9 should not be treated as a stable weather release.

v10 restores the v8 translucent material path and dynamic GL entry routes,
and removes the optional renderer-creation observer. This withdraws changes
introduced alongside the regression; it does not prove which change caused
it. The high texture-unit bookkeeping correction remains. Rain/Snow retain
their larger v9 footprint, full central opacity, bounded counts and world-space
depth testing. Both the NRO and Weather PAK must be updated together.

Stadium LoadedCall can complete before Fox finishes players and uniforms. FX
creation, asset loading and emitter spawn now wait for the existing live-HUD
heartbeat, which rejects loading, menus and cinematics. Elapsed time alone can
never open this gate. After the first spawn, losing the heartbeat in a replay
or set piece does not destroy/recreate the effect. A fresh match must pass the
gate again. Native weather and ball-surface setup continue at their original
initialization point. Precipitation consequently starts at live gameplay, not
during the opening stadium cinematic.

Read-only proxy/particle reports remain. A bounded pair of journal entries
records entry/return of the first native world tick after spawn, without a new
renderer hook. Release builds retain bounded Android error/fatal messages and
native termination notices in the same journal. Error and fatal budgets are
separate, and routine INFO output remains disabled. Host tests cover a
30-second unfinished load, paused readiness,
single spawn, replay-like heartbeat loss and readiness reset on the next match,
as well as the existing 60-match retirement checks. Device crash recovery and
precipitation visibility still require hardware confirmation; desktop rendering
cannot establish Switch compatibility.

The v10 local capture retains 645 Rain / 845 Snow particles. At the same 720p
camera, Rain has 1,105 pixels above RGB 32 and Snow 1,122 (v8: 0 and 11).
Android cooking reports zero errors/warnings; all eight packed assets roundtrip
and contain ES2/ES3.1 shaders. The final focused suite passed 44 tests and 133
subtests; the Switch NRO/icon and public-tree audit passed. This verifies the
fallback assets locally, not their visibility or frame time on the console.

## v9: visible precipitation and shared render state

The v8 hardware journal now confirms simulation: Rain reports 638/637 active
particles, and Snow 352/843, with a registered component, one emitter and world
FX. Both selections reach native wet surface profile 3. The user still sees no
precipitation and reports intermittent missing jerseys in Rain/Snow; Fine has
not yet been compared. These observations do not establish a referee-only or
weather-only cause, nor a measured change in ball travel.

A local 1280x720 UE capture at a broadcast-like camera distance reproduced very
weak v8 sprites. Rain had no pixels above RGB 32 and Snow only 11 against black.
v9 uses 7x65 cm rain sprites and 14 cm snow, with the same rates, lifetimes and
720/900 draw caps. The materials use depth-tested masked unlit rendering instead
of the optional translucent/HDR path. No framebuffer overlay is introduced.
The new capture has 1,370 rain / 1,184 snow pixels above RGB 32, at 645/845 live
particles. This is a desktop render comparison, not proof of Switch visibility
or mobile pass compatibility. Larger sprites increase covered pixels but do not
increase particle count.

Two wrapper bookkeeping gaps are corrected: selecting texture unit 8 or above
no longer leaves the prior tracked unit active, and resolved framebuffer,
viewport and draw calls use the same compositor routes as imported calls in
release builds. A high-unit binding previously replaced the saved texture for
the prior low unit. Host regression tests exercise that sequence and mixed GL
entry routes. Whether this caused the reported jersey blinking is unconfirmed.

The journal now samples the component's scene-proxy presence, match view-family
count and Particles show flag at two/eight seconds. The guarded native renderer
observer only reads current-family fields and records atomic counters; it never
changes show flags or submits a second scene. Native instruction checks cover
the Android family/proxy layouts and renderer PLT. Lifecycle tests ensure other
scenes and retired worlds cannot pollute these readings.

Install both the v9 NRO and Weather PAK. The accepted v8 referee adaptation,
Anfield PAK and FootballNX.assets remain the baseline. Device acceptance still
requires a Fine/Rain/Snow comparison with the referee enabled, then successive
matches, replay and pause. Preserve the new session log if precipitation remains
invisible or jerseys still blink. The patch does not claim a full EF10 AI port.

## v8: zero-particle follow-up

The v7 device log reports Rain in both Summer and Winter, with zero active
particles at two and eight seconds. It does not contain a Snow selection.
Successful component creation alone therefore does not prove simulation.

The owned Mobile `UParticleSystemComponent::InitializeSystem` requires both
registration and an FX system. `weather_scene.inc` now checks the current
world's scene/FX fields and calls the native `UWorld::CreateFXSystem` only when
FX is absent. The world owns teardown; an existing FX system is never replaced.
Failure leaves native match physics running. New diagnostics distinguish
registration, FX availability, emitter instance count and live particle count.

A local UE4.22 commandlet simulation of the same assets produced zero emitter
instances without world FX, then 645 rain / 284 snow particles after native
FX initialization and a two-second diagnostic warmup. This demonstrates the
asset and initialization requirement, **not** the cause on Switch: commandlets
normally omit FX, whereas the device world may already have it. The device
journal must confirm the actual branch and continued simulation.

The authored weather templates also opt out of batched particle-manager
ticking, using one ordinary UE component per match. The pause/resume binding
uses the particle component's override, not the base actor-component method.
No global FX quality, particle permission or spawn-rate CVars are overridden.
Rain/Snow caps and materials remain unchanged; replace the weather PAK along
with the NRO when updating from v7. No warmup is enabled in shipped assets.

A second local simulation exercised ordinary component ticks for 300 frames
at 30 Hz with rendering enabled and no warmup. Rain progressed 15 -> 450 ->
645 particles; Snow progressed 4 -> 140 -> 280 -> 845. Both remained below
their draw caps at ten seconds. An earlier diagnostic run with `-nullrhi`
could not activate particles (`CanEverRender=false`); it was corrected and
rerun. Final sequential authoring/cook verification avoids shared-editor cache
locks. These diagnostics do not substitute for the outstanding Switch test.

## Device feedback and precipitation transform correction

The first device journal confirms Rain/Summer and Snow/Winter reach native
weather setup: both use rain=1/change=2 and live/predicted ball surface=3,
compared with Fine's surface=1. The emitters report successful creation, but
the user sees no precipitation. These values prove settings delivery, not the
magnitude of changed ball movement or particle visibility.

Inspection of the owned Android SpawnEmitterAtLocation implementation found a
specific ABI error: its FTransform occupies 40 bytes and scale begins at 0x1c.
The previous desktop SIMD layout put scale at 0x20, making the actual callee
read (0,1,1). v7 uses the verified packed layout with aligned storage and adds
compile-time size/offset assertions, a raw-offset host test, and a local native
instruction check independent of the C definition.

The weather component now journals active particle counts and world focus at
two and eight seconds, making an inactive emitter distinguishable from a
visibility/material problem. Pause and retirement reset/preserve these counters
as appropriate. The existing 128,686-byte weather PAK is byte-identical; the
transform correction is in the NRO. Visual Rain/Snow placement and residual
referee/Anfield texture symptoms still require another device run.

The loaded callback chain includes the new referee stadium barrier, ensuring
weather, referee and optional Anfield replacement each run once in order.
Combined installer tests cover all optional-feature combinations.

## Match settings and ball surface

`source/match_environment.h` defines the UI-to-Mobile mapping. The stadium
snapshot now writes weather at `0x08` and season at `0x0c`, correcting the
previously reversed fields. Turf and condition retain their native fields.

Mobile's own ordered weather label table was checked through its ELF relocations:
Fine=0, Rain=1, Snow=2. These values are not borrowed from the PC configuration.

| Selection | Native weather | Playing surface |
| --- | --- | --- |
| Fine | Fine | Selected Dry/Normal/Wet and Short/Normal/Long |
| Cloudy | Fine, overcast lighting preset | Selected surface |
| Rain | Rain | Wet, native precipitation state |
| Snow | Snow, Winter season | Wet, native precipitation state |

Snow selects Winter. Changing its season to Summer changes weather to Rain.
Winter alone remains a season selection; it does not invent an ice-friction
coefficient. The stock engine shares the precipitation surface state between
rain and snow. Some turf/condition combinations also share a native profile,
as documented in the audit.

`source/native_weather.inc` applies the settings after the native initializer
resets its rain/change flags, within its existing match setup context. Native
`Ball::UpdateBallPitchState` continues to own both current and predicted movement
state. No second physics ball or per-frame velocity multiplier was introduced.
The release journal records the effective environment and native ball profile.
The actual difference in bounce and stopping distance requires matched kicks
on hardware. Random mid-match weather transitions are not part of this preset.

## Unreal precipitation

`tools/ue_create_weather.py` authors CPU Cascade particles and unlit translucent
materials in UE4.22.3. The editor-only reflection bridge in
`tools/ue_editor_properties.py` uses exported construction/property APIs for
Cascade classes unavailable through this editor's Python bindings. Materials
are saved before constructing unreferenced emitter subobjects, and particle
modules have the ParticleSystem as their outer, matching engine ownership.

Only `/Game/FootballNX/Weather` is packaged. Both ES2 and ES3.1 material shaders
are embedded and validated. The initial eight-file PAK was 128,686 bytes;
v8 recooks the two systems with component ticking enabled independently.

Rain uses 450 particles/second with a 1.4-second lifetime (draw cap 720); snow
uses 140/second with a six-second lifetime (draw cap 900). There is no warmup,
per-particle collision, or global quality increase. The volume follows the
camera's pitch-plane focus in world coordinates. Depth testing and a bounded
open-pitch mask exclude the stands and ground; roof-edge clipping needs device
review. These effects render through Unreal's particle components.

`source/weather_scene.inc` chains stadium/referee load and teardown callbacks.
Native weak object pointers track the world and component, with no rooted actor
or retained raw UObject across matches. The component pauses with the pause UI,
appears in match cameras/replays, and retires before stadium teardown. Missing
assets fail back to native gameplay. Particle spawning is independent of the
optional referee probe. Splash/wet-player stubs remain stubs; this package does
not claim restored splashes or wet clothing.

## Competition scoreboards

The selector follows the active Cup, League or Master League event. An active
cup takes precedence over club membership. Master League domestic cups,
continental events, national qualifiers, regional finals and world finals have
separate presentation contexts. Region category indexes are resolved through
their labels, not interpreted as competition IDs. Continental competitions
currently use a generic international theme.

Exhibition uses a league theme only when both clubs belong to the same curated
league. Mixed exhibitions and international friendlies retain the native theme.
Unknown or missing skins also retain the native UI.

`tools/build_competition_scoreboards.py` builds 22 local Mobile-compatible
palettes/emblems from the accepted square scoreboard. These are authored skins
using the FL-style competition-selection approach, not a binary port of PC
FL26 scoreboards. All AP2 movies, bytecode, bindings and geometry remain
byte-identical. Native score, timer, added time, penalties, goal animations and
replay continue to use their existing scripts.

`source/scoreboard_runtime.inc` supplies the replacement at AfpBin's synchronous
expansion boundary, where the native package copies input into its own owned
allocation. The wrapper restores the borrowed input pointer/size and frees its
temporary buffer after expansion. It never retains a themed archive between
matches. Each NXSB entry validates original TXP2 size/fingerprint and replacement
size/checksum. This intentionally rejects a different Mobile UI baseline.

Theme files live inside `FootballNX.assets`. All 34 earlier commentary, emblem
and animation entries were retained byte-for-byte, alongside 22 new themes.

## Initial v1 verification and installation

The Switch NRO builds successfully with the accepted local roster/catalog
overrides and release flags; its launcher icon matches the repository artwork.
UE cook completed with zero errors and zero warnings. The weather PAK was
unpacked and compared member-for-member. All 22 skins passed atlas roundtrips
and AP2 equality checks. The public-tree audit passed.

Host tests cover 72 settings combinations, snapshot boundaries, native reset
ordering, 60 successive simulated world lifecycles, pause, unavailable assets,
invalid weak components, 100 alternating scoreboard expansions, corrupt skin
rejection, Cup/League/Exhibition precedence and Master League event routing.
Optional local ABI checks verify 28 native symbol bindings and seven hook sites
against the compatible Mobile library. UI preview/menu tests include cycling
all four weather options and Snow/Summer consistency.

The final focused run passed 41 tests and 384 subtests. The broad project run
reported 638 passed, 17 failed and 51 skipped. Two failures were isolated C test
harnesses missing the new environment header; both were repaired and passed in
the focused run. The remaining 15 concern existing catalog/master-data identity,
menu, gamepad, substitution and pause/result expectations outside this change.
The entire broad suite was not repeated after those two harness-only repairs.

These tests cannot establish Switch frame time, visual particle placement,
real match UI resource lifetime, or ball-trajectory magnitudes. Broad legacy
suite status is recorded with the local release verification report; unrelated
catalog expectations and unavailable ignored fixtures are not silently treated
as passing. Use `python -m pytest tests ...`, since root discovery also picks up
unrelated bundled Python/Blender tests in ignored local folders.

The local update contains `pes21_nx.nro`, `FootballNX.assets`, and
`PesMobile/Content/Paks/PesMobile-Weather-Android_ETC1_P.pak`. Merge it into the
existing runtime. It is an update to the accepted installation and does not
contain the original game data or a replacement Anfield PAK.

Device acceptance should check Fine/Rain/Snow across successive matches in both
stadiums, pause/replay/half-time, matched kicks with surface variations, and
league-to-cup-to-exhibition scoreboard changes including added time and penalties.
`scene-runtime.log` reports `native weather`, `weather particles`, and
`scoreboard` events to distinguish input selection, native state and asset load.
# Weather surface v12 (10 October 2026)

The device test confirmed that v11 precipitation rendered, but its bright bars
and flakes overwhelmed gameplay. At the user's request v12 removes **all falling
rain/snow**: `weather_scene.inc` is no longer included or installed. The previous
weather PAK is unused; this update requires only the NRO. Native Rain/Wet ball
surface settings remain active. No new claim is made about referee stability.

Weather choices are Fine / Cloudy / Rainy; Summer / Winter remain independent.
Rainy + Winter uses native Rain with Winter season, not the old native Snow
choice. Invalid legacy weather selections fall back to Fine. Changing back to
Fine removes every new surface/atmosphere effect on reused programs.

Audited pitch fragment shaders add world-anchored procedural wet patches and,
only during Rainy + Winter, sparse broken snow remnants. This is spatial surface
colour variation, not a uniform tint, bitmap replacement or simulated puddle
reflection. Existing stripe/detail sampling and line colours remain intact.
Night pitch has a separate fingerprint scope that bypasses Day light changes.
The climate key retains a Rainy bit, keeping Cloudy and manually Wet/Fine free of
snow, haze and lens mist.

Rainy adds bounded distance haze (at most 6.5%) and soft peripheral lens mist
(at most 4.5%) to audited native opaque surface outputs. The centre of the lens
stays clear. This is a colour veil, not scene blur/refraction; it does not affect
HUD, unknown/translucent materials or sky shaders. Depth/alpha and all native
texture reads/bindings remain unchanged. There is no new draw, actor, texture
allocation or global render-state observer. Native Rain physics is independent
of the presentation. These are implementation bounds, not measured Switch FPS.

Host verification covers three-choice menu wrap, both seasons, native surface
snapshots/reset, cached climate updates, patch coverage/bounds, dry baselines,
paint preservation and reversible shader edits. `tools/pitch_weather_preview.py`
plots the shipped math on synthetic turf; it is not a Switch screenshot.
Device checks still needed: Day/Night on both stadiums, Rainy Summer/Winter,
then Fine in the next match, replay/camera changes and repeated matches with the
optional referee enabled. The new colour effects require device visual approval.

# Stadium and runtime expansion — 2026-10-10

Accepted Day pitch checkpoint: `288ab12` (Stadium Lite v6), pushed to
`cupleague`. This expansion is a test build on top of that checkpoint.
Compilation and host tests do not establish Switch appearance, timing or FPS.

## v7 referee event lifetime and EF10 gestures

The supplied Weather/Score v1 device journal confirms that v6 still deletes and
recreates the follower on individual player retirement and idempotent manager
creation. It also queues the first referee while Anfield is still replacing its
shell (the replacement takes 6.7–8.0 seconds in this log). These are concrete
resource churn and ordering defects; the log does not establish a GPU root
cause for every missing texture or the reported Anfield corner.

The follower now survives player substitutions/demo model replacement and
idempotent manager creation. Its lifetime follows the stadium's LoadedCall,
UnLoad/DestroyLoader and actual global load-group release. Loading waits for
the completed shell replacement and the native uniform pending queue; the
optional timeout still allows a match to continue. Draw cannot enqueue a load.
The publisher initializes all 20 native bone-buffer entries, including the
unused final slot, and still publishes once per native write timestamp.

Visible out/foul/throw-in demos no longer hide or reposition the referee based
on demo-skip UI availability. Pause/replay/menu and temporary registry handovers
hold its last pose and position; resume starts with zero elapsed time. This is
not historical referee replay simulation. Actual world/model teardown still
retires it before native resources disappear.

The owned EF Mobile 10.3.1 input supplies four additional retargeted motions:
whistle, raised arm, directional signal and lowering the arm. Animation bank
v3 has eight clips (216,128 bytes); the four accepted locomotion pose payloads
remain byte-identical. Gesture clips preserve source order, clamp instead of
looping, and blend with locomotion. The reader also accepts the old v2 bank,
which cannot supply these gestures, and continues to reject malformed/v1 data.

A guarded native RecordOutOfPlay hook copies finalized restart/reason metadata.
The native event's start frame and phase deduplicate repeated notifications.
Line-out and foul restarts trigger the imported whistle, followed by a
directional signal or the free-kick raised-arm sequence. Other fresh events
cancel a pending gesture. A bounded journal records the first 16 events.
This is an event adapter using PES21 decisions with EF motion data, **not a
binary port of EF10 decision AI**. Cards, advantage and specialized officiating
signals have not been mapped; the generic free-kick gesture does not establish
the exact rules meaning of every restart.

Host checks exercise preserved model identity across native player recreation,
shell/loading interleaving, uniform readiness, teardown, duplicate callbacks,
duplicate events, gesture completion, pause/resume and eight-clip corruption.
All four combinations of weather with/without Anfield and referee installers
are checked before executable mapping exists. Local runtime ABI verification
checks the event call site's record layout as well as its PLT hook.

The final focused/regression run passes 39 tests and 123 subtests. The real C
archive reader verifies all 56 entries and samples 3,600 frames from the shipped
eight-clip bank. The release NRO builds and its launcher icon verifies; the
public-tree audit passes. The broader legacy suite was not repeated for v7.

The update replaces the NRO and FootballNX.assets, retains all 55 non-animation
entries, and includes the same weather PAK and referee enable token. No Anfield
geometry package was changed. **Residual texture corruption and corner holes
remain device acceptance items**; compilation and mocked lifecycle tests do
not prove that they are resolved.

## v6 referee isolation and match-aware positioning

Device feedback on v5 isolates the random missing player parts to the referee
probe: removing `referee-probe.txt` makes the same game stable. Referee skinning
and motion are improved. The earlier shared-GL change did **not** resolve this
device report; the probe's load/publication path is the focus of v6.

Native inspection identifies a concrete scheduling hazard: adding a `draw::Human`
calls `HumanList::CreateSomething`, which updates uniform information and marks
the shared `UniformManager` dirty. v5 could enqueue that extra load from inside
`Player::Draw`. v6 changes the transaction boundaries:

- `match::Human::CreateModel` only arms the optional load. The native
  `Manager::IsAllLoaded` barrier queues/initializes it together with the other
  humans, before Match::Main releases the loading stage. Native readiness is
  preserved. A 20-second optional-load timeout retires the referee and allows
  the match to proceed. The model uses the same LOD policy as native match humans.
- Pose publication runs after the **entire** `match_system::ObjectList::Draw`,
  called by `ExecDrawListener`. The individual `Human::DrawModel` PLT is no
  longer hooked. Duplicate list callbacks publish at most one pose per native
  write timestamp. This path cannot create/load a model, nor alter player data.
- Native human retirement, manager release and stadium exit still retire the
  optional model before its dependencies. A new model needs another loading
  barrier; late draw callbacks cannot recreate it. Invalid pose contracts hide
  the model until teardown rather than unloading assets during a draw.

This removes a verified late-load hazard; the exact device corruption has not
been reproduced locally, so **the disappearance/blinking fix remains a device
test candidate**, not a confirmed diagnosis of every missing-part symptom.

The owned EF10 binary's referee update path checks restart setup, initialization
levels and replay/scene state and calls newer registry/action objects. No
standalone referee AI script was found in the inspected dt200/dt230 inventories.
Its stripped gameplay functions cannot safely receive PES21 object pointers.
v6 therefore adapts the restart/live-play distinction using PES21 inputs and
authored movement logic: filtered ball velocity and a short prediction horizon,
a stable diagonal viewing lane, separate start/stop distances, bounded turns
before acceleration, and player separation. Restarts hold a destination until
the ball moves meaningfully; pause/replay clears stale velocity prediction.
These are **positioning behaviors, not an EF10 decision-AI binary port**. Foul,
advantage and card decisions remain native. The model is still PES21 with the
retargeted EF motion bank v2 accepted in v5, byte-identical for this update.

Host scenarios cover settled/noisy balls, restarts, counterattacks, teleports,
frame-rate consistency, repeat callbacks, preload failures and match teardown.
All native bind/PLT guards must match before installing any referee hook.
The v6 partial update replaces the NRO, retains the v5 assets/Anfield PAK and
includes the original referee enable token for the device comparison. No
forwarder change, save migration or Day/Night lighting change is required.

## v5 skinned referee, shared GL resources and crowd motion

Device feedback on v4 confirms **repeated matches no longer crash** and the
referee's animation no longer alternates/blinks. Its mesh is folded, however;
player body/head parts can still disappear randomly, especially in Day.
The v4 lifetime hooks are retained. Missing parts have not been reproduced
locally, and their connection to the following GL hazard remains a hypothesis.

- Referee rotations now include the native **render** skeleton's conversion
  quaternions. `body_anim_skel.ask` supplies positions/lengths, while
  `body_render_skel.ask` supplies the bone bases expected by the skinned mesh.
  The native forward conversion is `world_rotation * render_conversion`;
  positions remain in model space. v4 wrote animation-space rotations directly.
  All 109 frames / 19 renderer slots were compared against the owned native
  conversion function: maximum error **1.20e-7**, with positions byte-identical.
  Bank format v2 rejects v4's unconverted bank, so update NRO and assets together.
  This is still the native PES21 referee model with retargeted EF motions.
- Texture/program rebind calls are always delivered to GL. Numeric name equality
  cannot establish resource identity after deletion/reuse or acquire changes
  made in a shared upload context. This follows the shared-object rules in the
  [OpenGL ES specification, Appendix C](https://www.khronos.org/files/opengles_spec_2_0.pdf).
  Context-local blend/depth/cull caches stay enabled. Link/delete events invalidate
  uniform-location caches across threads; upload drain counters are thread-local.
  Release builds record bounded shader compile/link failures as well as lifecycle
  events in `scene-runtime.log`. This is a candidate visibility fix, not a
  hardware-confirmed resolution of the random missing-part report.
- Anfield's existing seated atlas now sways/bobs per group through its UVs.
  Feet stay pinned; colour and alpha use the same animated coordinates.
  This is lightweight authored motion, not the native crowd's full repertoire.
  Geometry, texture count and draw-section count are unchanged: **102,524
  triangles / 44 materials**, including 3,962 crowd triangles.
- The shell returns to Static mobility before registration. Repeated callbacks
  with the same mesh skip resource release, GPU drain and registration. Actual
  mesh swaps retain the resource-release/flush/LOD-clear safety sequence.
  The journal records native-load, actor enumeration, asset-load and application
  milliseconds. First-load latency and intro FPS still require device measurement.

Local validation: **25 tests / 45 subtests passed**, 1,716 cooked shader
compilations passed for GLES2/3.1, both clip-space paths and three HDR modes.
The production C reader verified all 34 archive entries and 1,800 animation
samples. All 33 pre-animation assets (including Indonesian commentary) remain
byte-identical. The Day/Night lighting policy and accepted player faces are unchanged.

The v5 update contains `pes21_nx.nro`, `FootballNX.assets`, and the Anfield PAK
in `PesMobile/Content/Paks/`. Keep `referee-probe.txt` and the same forwarder.
Validate the skinned referee, Day/Night missing parts, spectator motion, intro
and three consecutive matches on Switch. Preserve the journal before relaunch
if anything fails. Host/native-oracle checks do not confirm those visual outcomes.

## v4 EF motion conversion and per-match model retirement

The supplied v3 journal reaches the second stadium load without any recorded
unload or global animation/load-manager release. Device feedback still reports
a crash during match two in either stadium and alternating idle/running poses.
No crash backtrace or comparison with the referee disabled is available, so a
full cache or referee-only crash cause remains unproven.

Native inspection identifies two additional lifetime boundaries: Mobile's
`AStadiumLoader::DestroyLoader` bypasses `UnLoad`, and individual
`draw::util::Human` models retire through `draw::Human`'s base destructor while
the global load manager survives. The follower now releases before those
boundaries. An idempotent prematch `Manager::Create` also retires an existing
follower. Remaining callbacks from a retired frame cannot recreate it. Early
global teardown hooks remain as fallbacks. The journal records release entry
and return, permitting a device failure to be narrowed to a specific stage.

v4 replaces player-pose sampling with four converted EF Mobile 10.3.1 loops:
`referee_stand_0`, `walk_1_1`, `run_2_2`, and `run_3_3`. Idle is referee-specific;
the other three are EF's general locomotion. The original PES21 referee model
remains: EF's 22-bone source is retargeted to PES21's 20-bone skeleton and the
19 slots used by its native body renderer. Extra spine/neck rotations are
preserved through mapped world orientations; positions use PES21 rest lengths.
The wrapper supplies horizontal movement, preserving the clips' vertical motion.
This imports motion data, **not EF's decision AI or executable functions**.

`tools/convert_ef_referee.py` selects motions by full native name hash from the
locally supplied XAPK. `tools/native_animation_bake.py` evaluates their compatible
GANI/FRIG tracks, including limb IK, using the owned PES21 decoder in a bounded
offline ARM64 emulator. It implements memory allocation/copy only; Android, UE
startup, file and network imports are unavailable. Optional converter dependencies
are `pyelftools` and `unicorn`. ASK/GANI/FRIG inputs and decoded output stay ignored.
The public [FoxEngineTemplates format notes](https://github.com/kapuragu/FoxEngineTemplates)
were used as an initial format reference; evaluation uses the local native decoder.

```powershell
python tools/convert_ef_referee.py --xapk local-inputs/EF.xapk --native-lib dist/pes21_nx/libUE4.so --pes21-skeleton <local-PES21-body_anim_skel.ask> --pes21-render-skeleton <local-PES21-body_render_skel.ask> --output <local-asset-root>/Animations/referee.nxra
python tools/pack_runtime_assets.py --root <local-asset-root> --output <local-output>/FootballNX.assets
```

The asset root must contain all accepted loose logo/commentary entries as well
as the new animation; packing only Animations would omit existing assets.
The baked bank is **66,432 bytes** with 30/36/22/21 frames at 30 Hz. A repeated
conversion produced identical bytes. Offline pose inspection found intact
limbs, native bone lengths and continuous loop boundaries. This is a skeleton
preview, not validation of the skinned Switch model.

`source/referee_animation.h` validates the bank, blends normalized quaternion
poses, and maintains independent idle/gait phases. Walking, jogging and running
phases are aligned at conversion; speed changes blend without resetting the
cycle. Runtime work is one 19-bone upload per native frame, with no allocation
or file read per frame. Pause/replay gates preserve phase and discard elapsed
wall-clock time. The only persistent clip allocation is the single 66 KB bank.

Update an existing v3 installation with **NRO and FootballNX.assets together**.
The v3 Anfield PAK and referee enable token remain compatible. A missing or
invalid bank disables the optional referee before any of its hooks are installed.
Retest three consecutive matches, both stadiums, Day/Night, idle/run transitions,
pause and replay. Preserve `scene-runtime.log` before reopening after a crash.
The original v4 release had no hardware confirmation; subsequent user testing
confirmed repeated-match stability and animation continuity (see v5 above).

## v3 stability, render state and seated crowd

Device feedback confirms that v2 renders the complete Anfield shell and moves
the referee. Remaining reports: missing home-side bodies in Night **on the
first match**, return to HOME while loading the second match, referee blinking,
and some performance loss. A full cache is a hypothesis, not a measured cause.

Two concrete runtime hazards are addressed:

- The core GL setters returned by `eglGetProcAddress` bypassed the state cache
  used by ELF imports. A material changing depth, blend, cull, texture or colour
  state through one route could leave the next renderer's restore suppressed.
  Both routes now use the same wrappers, including texture deletion. Host tests
  reproduce mixed-route depth/enable restoration. This is a candidate fix for
  invisible bodies; the reported Night match still needs a Switch retest.
- The old referee hook cleaned up at `HumanLoadManager::Release`. Native
  `draw::load::Manager::Destroy` destroys animation and load groups earlier,
  while `draw::Human`'s destructor still needs `Manager::Unload`. Cleanup now
  starts at animation release, before those dependencies disappear. A teardown
  gate prevents late draw callbacks from creating a new model; a successful
  native manager creation opens the next session. This repairs unsafe ordering,
  but does not by itself prove the cause of the second-match crash.

Referee visibility uses native match phases and explicit pause/replay/cutscene
owners instead of the HUD's 80 ms freshness timeout. Held poses are republished
to native timestamped interpolation buffers. Display submissions are bounded
to one per frame, plus a possible first-pose transition, instead of 22 setters.
The follower is still visual; game decisions and player registries are unchanged.

The v3 PAK reduces the shell from **140,804 to 98,562 triangles**. It adds
**1,981 static seated crowd strips / 3,962 triangles**, for **102,524 total**,
27.2% below the old shell alone. There are 44 material slots (previously 43).
The existing native seated atlas supplies alpha-masked people. FL seating-area
quads preserve section gaps; rows are fitted against the imported seat surfaces
and excluded from the playable pitch. This is a static 2D crowd, not animated
individual spectators. Offline visual inspection checks seating and geometry;
device memory/frame time remain unmeasured.

Reproduction additions:

- Pass `--with-audience-areas` to `convert_fl26_stadium.py` to validate/extract
  the owned `audiarea.bin` into ignored output.
- Pass `--triangle-ratio 0.7 --crowd-area <audiarea.bin> --crowd-atlas <native-png>`
  to the Blender stage. `tools/stadium_crowd.py` strictly validates version,
  section boundaries, finite geometry and row budget.
- On an existing editor project, set `PESNX_STADIUM_RESUME=1` and
  `PESNX_STADIUM_REIMPORT=1`. Resume alone updates materials but does not replace
  the mesh. The seated atlas permits 1024 px; other textures retain the 512 cap.

`scene-runtime.log` is a bounded release-build journal for stadium load stages,
referee teardown and shader link failures. It adds no per-draw file logging.
The new update requires **both NRO and Anfield PAK**; `FootballNX.assets`, the
referee enable token, accepted pitch lighting, realfaces and commentary remain
compatible. Retest Night Newcastle–Leeds first, followed by at least three
consecutive matches, switching Day/Night and returning to Konami stadium.

## Supplied EF Mobile 10.3.1 audit

The newly supplied local `EF.xapk` contains arm64 native code, CPK data and newer
PAK/IoStore asset containers. Its binary names referee/linesman animation clips,
equipment and `IsEnabledDisplayingLinesmanAndRefereeOnMobile`; that setting name
is absent from the supported PES21 binary. Referee appearance and colour tables
also exist. These references establish available source material, not a callable
AI API for PES21; gameplay symbols are stripped from this EF native library.

Selective extraction compared the actual body skeletons: PES21's ASK has version
1 / 20 entries; EF's decompressed ASK has version 2 / 22 entries, with different
entry counts and animation-table headers. Copying EF skeletons or animation banks
over PES21 would therefore bypass required conversion. No EF library/bank is
installed by v3. v4 implements the explicit motion conversion described above.
XAPK, decoded samples,
raw inspection and comparison hashes remain ignored under local inputs/debug.

## v1.1 startup correction

The first device attempt reported a crash before the logo with both the Anfield
PAK and referee flag installed. Both optional installers inspected instruction
bytes through `so_try_find_addr_rx()` before `so_finalize()` mapped that address.
Either opt-in independently reached an inaccessible address during startup.
They now inspect the loaded backing via `so_find_addr()` after checking symbol
availability; eventual native calls still retain their executable addresses.

The bootstrap regression executes the actual installers with an inaccessible
executable mapping. The old code faults for each enabled experiment; the fix
passes enabled, absent, missing-symbol and incompatible-instruction cases.
Earlier scene tests exercised model/mesh callbacks but excluded installation,
so they did not cover this startup failure. Archive-only logo/commentary tests
also pass. The subsequent device test reached a match, loaded the Anfield shell
and spawned the referee. It exposed missing stadium surfaces and a referee
walking at a fixed location, addressed experimentally below.

Replace only the NRO from the v1.1 update when v1 is already installed. The
asset archive, Anfield PAK and referee flag are unchanged. Regenerating the
forwarder is unnecessary when it still targets
`sdmc:/switch/pes21_nx/pes21_nx.nro`.

## v2 shell replacement and moving referee experiment

The source/Blender shell contains continuous stand terraces that are absent in
the device screenshots. A component-replacement hazard was found in the owned
runtime and the locally installed UE4.22 engine source: `SetStaticMesh` does
not clear component `LODData`. The scene proxy can reuse the original stadium's
pre-culled triangle ranges, vertex colours and baked-light references against
the imported mesh. Clearing override materials alone does not discard them.

The replacement now uses native `FComponentReregisterContext`, releases old
instance GPU resources, waits for rendering commands, and clears instance LOD
data before re-registering. This avoids freeing a live pre-culled index buffer.
Rejected replacement restores registration; a missing asset is not touched.
The next device test confirmed the complete shell rendering. The v2
Anfield PAK/texture payload was unchanged.

The referee now has bounded ball-following motion and chooses a suitable
native idle/moving pose, instead of always copying player 4 at a fixed spot.
This is authored visual positioning, not imported FL26 referee AI. Some
Mobile referee/linesman action functions are stubs; the sound referee-position
getter returns the origin. A working live visual controller was not established
from those symbols. The local FL26 Sider `common/referee.lua` assigns kits;
it does not supply movement AI. Its game executable is a Windows x64 binary,
so it is not a callable movement module for the Mobile arm64 runtime. EF10 was
not available during v2; the supplied v3 input is audited above.

The v2 update needs only its new NRO on an existing v1.1 installation. Keep the
existing Anfield PAK, asset archive and `PESNX_REFEREE_PROBE_V1` flag. Check
terraces/materials in Day and Night, follow play into both halves, pause/resume,
replay, rematch and return to Konami stadium. Status files identify v2 and record
the referee's first three metres of travel. Device visuals, pacing and FPS are
not established by the host tests or successful compilation.

## Stadium settings

The existing native match-setting handoff remains. The renderer now also
receives a cached `nxStadiumClimate` uniform when settings change.
These appearance presets apply to **Day + High**:

| Setting | Implemented appearance |
| --- | --- |
| Fine / Cloudy | Cloudy reduces direct light, increases ambient fill and weakens/softens roof contrast on pitch and players |
| Summer / Winter | Winter uses a lower analytic sun angle and slightly cooler light |
| Short / Normal / Long grass | Changes existing grass detail strength, without extra grass geometry |
| Dry / Normal / Wet pitch | Changes grass brightness and bounded specular sheen |

Fine / Summer / Normal / Normal preserves accepted v6 Day math. Night retains
its accepted lighting and ignores these appearance presets. The menu states
the Day + High requirement. This does not add rain particles, turf physics or
ball friction; native setters alone are not evidence of those effects.

`source/stadium_environment.h` validates settings. The shared roof receiver
still affects pitch, bodies and faces; no dynamic player-shadow pass is
re-enabled. `source/imports.c` updates cached uniforms without shader recompiles,
and invalidates them on relink, deletion and context changes.

## Stadium catalog and Anfield experiment

AUTO / HOME / AWAY was three labels for one model. The selector now lists
KONAMI STADIUM and, when its optional local package and ABI checks are available,
ANFIELD (TEST). This first catalog does not assign home stadiums to teams.

The local Football Life 26 Anfield conversion is reproducible through:

1. `tools/convert_fl26_stadium.py`: locally supplied FPK/FMDL/FTEX to eight
   glTF shell parts and base textures.
2. `tools/stadium_shell_fbx.py`: Blender material consolidation and FBX export.
   Fox X/Z horizontal and Y-up becomes UE X/Y horizontal and Z-up, in cm.
3. `tools/ue_import_stadium_shell.py`: UE4.22 import, simple native materials,
   texture cap of 512 px with needed transparency; cook Android_ETC1 with both
   `bBuildForES2=True` and `bBuildForES31=True`. Set
   `bShareMaterialShaderCode=False` to keep both shader maps inside each material.
4. `tools/pack_stadium_shell.py`: package only
   `PesMobile/Content/FootballNX/Stadiums/Anfield`, V8A/Zlib, into
   `PesMobile-Anfield-Android_ETC1_P.pak`. No Engine defaults/native paths.

The packer requires both GLSL 100 and GLSL 310 ES shader maps. ETC1 alone only
specifies texture encoding; a default ES2-only cook is insufficient for the
runtime's ES3.1 route even when UE reports a successful cook.

The first shell had **140,804 triangles, 43 materials, 213 cooked files** and a
10.7 MB PAK. One unavailable common banner texture uses concrete fallback.
PC pitch, weather, outer-city parts and crowd animation are excluded; the new
shell initially had empty seats. v3 adds static crowd strips and the geometry
reduction described above. This is not a complete FL stadium port.

`source/stadium_canary.inc` runs after native stadium loading, validates
component classes, replaces the `st029_b` shell carrier and hides audited native
bowl/perimeter/crowd meshes. It preserves pitch, goals, flags, adboards, cameras
and match coordinates. It retains no UObject pointer across callbacks and
leaves the native shell visible if the imported asset/carrier is unavailable.
Selecting Konami restores a reused carrier. First test with **High quality**.
`stadium-canary.status` records installation and replacement outcomes.

Anfield gets an authored rectangular roof approximation without Konami
skylights, not an exact reconstruction of its beams. Shell materials use cheap
static hemisphere shading, not FL Day/Night shell illumination. Native pitch
striping is retained; stadium-specific pitch patterns remain future work.
Verify scale, goal clearance, memory and frame time on Switch.

## Consolidated assets

`FootballNX.assets`, beside the NRO, now supplies CupLogos, LeagueLogos and the
Indonesia commentary delta. v4 adds `Animations/referee.nxra`; the prepared
archive has **34 entries / 1,019,622 bytes**. The original 33 entries are preserved
byte-for-byte. Accepted Indonesia delta SHA-256 remains
`762524358c15ccab63282aa6abf1031ad4dc5746bfb0badf69e5cc64006deed8`.

`source/runtime_assets.h` binary-searches a versioned index, validates bounds
and checksums, and loads only the bounded selected entry. Loose files remain
explicit overrides; an invalid override does not silently use archived data.
Commentary bank identity/delta verification is unchanged.

With Python 3.11+ and the game closed:

```powershell
python tools/pack_runtime_assets.py --root <runtime> --output <runtime>/FootballNX.assets
python tools/install_runtime_assets.py --root <runtime> --archive <archive> --backup-dir <outside-runtime>
```

The installer checks every loose asset against the archive, creates and verifies
a ZIP backup outside the runtime, atomically installs the archive, then removes
only identical files and empty folders. Different/custom or unsupported files
stop migration before replacement; repack those inputs first. `--check` is a
read-only preflight. Existing archives are backed up too. Restore by extracting
that backup into the same runtime with the game closed.

Only these four folders are consolidated. Saves, LooseCpk manifests and engine
PAK/CPK/OBB data retain their existing formats and locations.

## Referee visual follower

The native live-match factory creates 22 players. `source/referee_probe.inc`
uses Mobile's existing referee loader for an optional **visual follower**,
not an FL referee import or new match decision logic.

Enable by placing `referee-probe.txt` beside the NRO with token
`PESNX_REFEREE_PROBE_V1`. Remove it and restart to disable. The normal update
omits this flag; a separate probe package supplies it. `referee-probe.status`
records transitions, without per-frame file writes.

The probe checks entry points, creates one independent native Referee-kind
model and waits for its own model/bone storage. `source/referee_motion.h`
positions it near the action using read-only ball/player positions, bounded
acceleration, a 5.8 m/s speed cap, pitch limits and proximity avoidance. This
is approximate steering, not physical collision or a complete referee AI.

The native model-upload frame timestamp bounds movement/pose work independently
of player draw order. v4 uses the independent converted EF clip player described
above. It reads no player animation object and uploads at most one pose per
frame into its own bone buffer. Player visibility and idle/running transitions
cannot select a different donor pose.

Pause, replay and cinematic gates hide the follower and reset elapsed time.
It never inserts a 23rd player into gameplay registries or changes decisions.
Per-model, stadium and early animation-release hooks destroy it before native
dependencies. A bounded load failure disables it until the next match. Device
movement was confirmed in v2; v4 animation continuity and repeated-match
stability are confirmed by user testing. The v5 skinned pose still needs a retest.

## Additional native controls

| Switch input | Native action scheduled |
| --- | --- |
| Y then B before shot contact | Kick feint / fake shot |
| A then B before lofted-pass contact | Lofted-pass feint |
| R + ZR | Native super-cancel chord |
| Hold X while defending | Keeper rush; X is the requested Triangle equivalent |

Optional units must match vtable and native pad-key identity. Feint is scheduled
only in live attack after a shot/lofted-pass unit, preserving ordinary B passes.
Keeper rush runs only in pure defense; super cancel uses native chord detection.
P1/P2 ownership is retained. CPU, penalty and set-play contexts are excluded;
missing optional objects retain existing controls. No synthetic touches or
keypress sequences are injected.

Host tests verify scheduling and fallback, not animation timing. Device tests
must cover before/after contact, normal passes, keeper hold/release, both sides
and rematch. Completed kicks cannot be cancelled retroactively. Pressing Shoot
to cancel a short pass is not introduced here.

## Validation and local artifacts

- Release NRO compiles with accepted migrated roster/asset overrides; diagnostics
  and performance tracing disabled.
- 648 extracted native shader variants and their patches compile on both
  clip-space routes: **2,592 checks, zero errors**.
- Host tests execute shader math, uniform cache updates, input scheduling,
  scene lifetime/fallback, archive reading, audio reconstruction and migration.
- v2 focused tests: **21 passed, 36 subtests passed**. Actual scene callbacks
  exercise resource-release/flush/destruction ordering, rejected swaps, 22
  callbacks per frame in both orders, culling independence, donor invalidation,
  pause/replay gating, missing live data and unload. Motion simulations compare
  30/60 Hz, speed/field limits, overlap avoidance and stalled-frame recovery.
- v3 focused tests: **27 passed, 40 subtests passed**. New cases cover mixed GL
  entry-point routes, bounded crowd geometry, continuous held-pose publication,
  early destruction before dependency teardown and no respawn during unload.
- v4 focused tests: **15 passed, 41 subtests passed**. They cover skeleton
  layouts/retargeting, Python-to-C clip compatibility, independent gait timing,
  malformed clips, model retirement without global teardown, idempotent manager
  creation, installer gates and consolidated assets. The release separately
  verifies 42 native bindings, three ABI guards and eight PLT stubs. The C
  reader compares all 34 shipped payloads and samples the converted bank for
  1,800 frames. The accepted v3 PAK and all other staged runtime sources remain
  byte-identical apart from referee playback/lifetime and journal versioning.
- The original Anfield cook reported zero errors/warnings. The v3 cook completed
  with zero errors and one warning about editor smoke-test duration. Its import
  also warned about missing smoothing groups/degenerate tangents; these unlit
  materials use imported vertex normals and no tangent-space normal maps.
  Menu previews use production drawing code with synthetic state, not a Switch
  capture. Both long-side crowd arrangements were inspected in offline renders.
- All 43 original Anfield materials contain vertex and fragment maps for GLES2 and
  GLES3.1, with texture lookups and the authored shading present. An additional
  **1,632 shader compilations** cover both clip-space and all three HDR modes.
- v3 has **44 materials, 1,716 successful shader compilations** across the same
  modes; all six crowd fragment variants retain alpha discard. The scoped PAK
  contains **218 files / 9,525,532 bytes**. The release verifies 44 native
  bindings, three ABI guards, six PLT stubs and unchanged accepted build assets.
- The native C archive reader compared all 33 prepared payloads byte-for-byte
  with their loose originals in an archive-only installation. A repeated
  stadium conversion preserved all 45 decoded textures and transparency data.
- Full repository suite: **623 passed, 51 skipped, 55,229 subtests passed;
  15 failed**. All 15 failure IDs reproduce against checkpoint `288ab12`.
  They concern existing catalog/registry snapshots, obsolete menu expectations
  and host harness stubs, not new failing expansion tests. Missing optional
  local fixtures remain skipped. The local runner caches the same native ELF
  bytes in memory to avoid excessive Windows file seeks; parser/assertions are
  unchanged. Reports: `full-tests.log` and `baseline-comparison.json`.

Local updates and reports: ignored `local-debug/runtime-expansion-v1/`.
Converted payloads and raw inspection outputs remain local. Accepted Yamal,
Raphinha, Indonesia commentary, custom pitch and perimeter assets are preserved.

## v8 referee behavior and Anfield corner follow-up

The user confirmed v7 no longer corrupts player textures and stadium loading
is lighter. Keep its stadium-owned model, loading/uniform barrier, independent
pose buffer and early retirement order. The v8 changes do not reload the
referee during an out, foul, goal or player-model switch.

Further inspection of the owned EF10 library found a referee update path with
separate initialization, restart-setup and replay/context gates. Its downstream
controller accesses EF-only registries, virtual interfaces and behavior state.
It is not a standalone AI asset that can be attached to PES21. No EF binary
routine is executed with PES21 objects. The full EF10 decision/positioning graph
has **not** been ported. Current positioning remains an authored adaptation,
using PES21 ball/player positions, restart categories and native match events.

v8 adds distinct viewing targets for throw-in, goal kick, corner, free kick and
penalty. During a goal celebration it returns towards halfway instead of
freezing. Visible set-piece-taker UI no longer pauses the follower; actual menus
and replays retain the held pose. Replay history playback is still not provided.

The imported EF10 gestures now layer only above the pelvis, aligned to the
current pelvis pose. The seven pelvis/leg slots retain the locomotion pose,
so a pointing clip's walking feet cannot run on a stationary actor and an
active signal no longer forces its world movement to stop. Native PitchSound
referee-position commands trigger a whistle gesture, including restart sounds
without a new OutOfPlay record. All audio calls are forwarded once; sound is
neither substituted nor replayed. Duplicate handles and paused/replay cues are
discarded. The existing EF stand-whistle clip holds the hand near the face at
about 0.7–1.2 seconds; sound-triggered gestures enter that part of the clip.
Cards, advantage decisions and full EF10 behavior are not claimed.

The blue Anfield corner was a missing concourse floor. A narrow centre-part
import restores 122 shallow concrete triangles wholly outside the protected
53.5 m by 35 m half-extents. It reuses the existing concrete material and keeps
44 material slots; the shell totals 102,646 triangles. The optimized stadium,
crowd and shading remain in place. Before/after offline geometry renders show
the previously open space filled below the stair and gate. These are diagnostic
renders, not Switch captures. FBX import retained smoothing/degenerate-tangent
warnings; the Android cook completed with zero errors/warnings, and all 218
packaged members roundtrip byte-for-byte against the cooked namespace.

Local v8 artifacts live under `local-debug/referee-weather-v8/`. Device testing
must still confirm gesture timing, corner appearance, Rain/Snow visibility and
repeated-match stability. Host motion, event, audio-forwarding, lifetime and
native ABI tests cannot establish visual acceptance or FPS on the console.

### v11 referee follow-up

Later device feedback reports severe player blinking with the probe enabled.
The supplied v10 weather log was taken after the probe was removed, so it
cannot show the faulty referee session. v11 drains native player/uniform jobs
before enqueueing the extra Human, keeps the second readiness check, and bounds
the optional uniform preflight wait. Visibility is now edge-triggered across
frames, matching the native timestamped queue's persistent state. Tests verify
that 300 live frames produce only the initial hide/show commands, hidden frames
produce one transition, and an unfinished native player load creates no extra
Human. The previous EF10 gesture bank and authored positioning remain intact.
These are candidate corrections, not a hardware-confirmed blinking fix or a
full EF10 AI port. See `NATIVE_WEATHER_SCOREBOARDS.md` for the matching weather
field update and the probe-off/probe-on validation boundary.

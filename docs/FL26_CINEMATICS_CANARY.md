# FL26 cinematics: entrance canary and trophy boundary

Status (2026-10-15): one reduced entrance is packaged for **experimental Switch
testing**, not production approval. Trophy lifting is **not enabled**. Original
archives, the active runtime and saves are not modified by preparation. All
game payloads and detailed local audit reports remain ignored.

Follow-up (2026-10-18): the user reports the current entrance/intro works. That
report does not identify the separately staged FL26 walkout package, and is
not trophy acceptance. The reproducible asset recheck, remaining integration
gates and shortest device test sequence are maintained in
[Trophy ceremony test plan](TROPHY_CEREMONY_TEST_PLAN.md).

## Implemented

- `tools/fixdemo_scene_table.py`: strict parser/writer for native scene, cut and
  control streams. Four owned Mobile/FL26 entrance/ending tables round-trip
  byte-identically. Non-entrance scene isolation preserves semantic ID indices.
- `tools/entrance_scene_canary.py`: bounded FDC parsing, dependency resolution,
  actor-layout inspection, skeleton comparison and isolated native motion
  decoder probes. Embedded four-byte placeholders are not mistaken for assets.
  PC `#Win` model candidates are reported, never accepted as Mobile models.
- `tools/stage_entrance_walkout.py`: build one entrance candidate from a
  validated, complete LooseCpk V2 baseline and owned FL26 data. Only `dt220`, its
  paired manifest and a trace marker are emitted. Every unrelated CPK payload,
  existing member ID and TOC row order is checked; appended rows use `Sorted=0`.
- `source/fixdemo_scene_trace.inc`: optional native entrance selection/start/end
  observations. An exact `cinematic-trace.txt` marker, three native instruction
  fingerprints and all vtable slots must pass before any patch. Originals are
  always called, including native FPS restoration. No match-state, Skip or
  scene-selection override is installed. Logging is lifecycle-only and bounded
  to 128 events / 16 KiB.

The entrance uses the first three files of `ENT_012_CMN`: two camera tracks and
the player track. It requests the native 22 field players and three referees.
Extra PC mobs/audience are deliberately excluded. The scene is remapped to
Mobile's entrance ID `0x10001`, retaining Mobile's generic selection condition
and terminal row. Native team/captain assignments are retained from the donor
walkout descriptor. This is a reduced port, not the entire PC ceremony.

The dependency closure adds 3 FDC files and 46 GANI motions (about 1.37 MB).
Two other referenced motions already exist in Mobile and match the donor
byte-for-byte. Six body/eye skeleton or rig files also match byte-for-byte.
All 48 motions passed the Mobile ARM64 decoder at their first, middle and last
frame: 144 sampled poses with finite positions and normalized quaternions.
These tests do **not** establish camera framing, actor creation, full scene
execution, Skip completion or Switch performance.

## Corrected native findings

The earlier inference that a stubbed `fixdemo::DB::Init()` prevents all scene
loading was incomplete. `DataManager::Setup()` / `LoadDBData()` load the typed
`table_ent.bin`, `table_end.bin` and related banks. The table parser populates
the DB; the empty `Init()` alone is not a blocker.

Scene IDs are not interchangeable. FL26's first entrance is `ENT_LOADING`, while
Mobile's selector always chooses `ENT_MOBILE_CMN` at the same numeric ID.
Ending IDs `0x70001` and `0x70002` have special native actor setup. Copying the
entire PC table or renumbering a trophy scene to either ID is unsafe.

The native entrance's Start/End callbacks temporarily select and restore the
PES thread FPS. The trace preserves these callbacks, and the existing native
Skip path remains responsible for teardown and kickoff. Removing the marker
disables **tracing only**, not the candidate entrance assets.

## Why trophy activation remains disabled

The native result factory runs at both halftime and full-time, usually with
the same result scene and neutral side. Base virtual execution/destruction is
compatible with a narrowly substituted `FixDemoMatch`, but a future activation
must require actual match phase END, the pending championship final (not a
third-place match), a freshly verified winner and a complete scene asset set.
Do not force MatchTop state 18 or globally change Cup predicates.

`END_CUP_CMN` / `END_TROPHY_01_CUP` has a native captain assignment that resolves
the winning team's real captain marker. Hard-coding starter index zero is
incorrect. Native ending callbacks and the derived destructor restore FPS;
future integration must retain virtual ownership and deletion.

The original donor has four PC-only model dependencies: the cup, two suit-mob
models and the winners' platform. The reduced candidate now removes the four
proved trailing suit-mob records and their three trailing resources while
retaining ten teammates, the captain and platform. Matching animation skeletons
still do not prove model/renderer compatibility. The captain track is in the
cup FDC; deleting that file removes captain choreography too. Player anchors
are 0.30–0.60 above ground, so deleting the platform also leaves floating players.
The two remaining models require conversion and a verified renderer bridge
before an automatic post-final ceremony can be enabled.

`stage_trophy_ceremony.py` stages this detached asset-only candidate using
**variant 1**, whose `cup_int_hi` matches the converter, not variant 13's
different `cup_intclub_hi`. It adds the explicit `END_CUP_CMN` / `END_TROPHY_01_CUP`
slots without renumbering native groups or changing controls. The optional
isolated Mobile decoder passed first/middle/last samples of 22 body/eye tracks
and one separately sampled rigid-cup motion: **69 poses**, not full playback.
The package retains the native entrance and 2,471 unrelated CPK members. It has
no NRO, activation marker or playable scene integration. Its CPK/manifest pair
must not be independently overlaid with the entrance candidate, which replaces
the same two files; a combined package needs explicit merging and revalidation.

The renderer audit identified an additional hard boundary:
`FixDemoObject::CreateObject()` skips the skeleton-bearing branch and only
creates models for the existing boots/backboard path families. The downstream
`ObjectModel` route uses UEBridge, `AObjectBaseActor` and a cooked Unreal
`UStaticMesh` under `/Game/Assets/`; it does not render the PC FPK/FMDL directly.
An allocated actor alone can report loaded without a real mesh. Therefore a
future adapter needs exact cup/platform path allowlists, verified cooked
assets, a real mesh-loaded check, and verified ownership/teardown.

A reduced conversion is plausible: the cup has one rigid `sk_prop` bone and
the podium is unskinned. The cup's skeleton/rig match Mobile; its GANI also
passed five native-decoder samples. Preserve the native captain-parent and
root-animation transform and pass its final matrix to a cooked static mesh;
do not discard that transform just because the render geometry is static.

## Prop conversion and final-result safety

The local rigid conversion is now implemented in `prepare_cinematic_props.py`
and `cinematic_props_fbx.py`. The former retains the original source/material
provenance and rejects non-rigid cup weights. The latter reverses the measured
Fox clockwise winding while retaining split normals, then checks oriented
triangle/corner correspondence through a fresh FBX export and reimport.

Measured results: the cup retains 19,664 triangles and both UV channels; the
platform retains 331 triangles and its one source UV channel. Maximum FBX
position drift is below 0.00000042 metres, with zero UV drift. Both remain
unskinned meshes. FBX axes, centimetre units and the serialized model transform
are checked separately from the actual Unreal/cooked-buffer verification.
An exact rounded hash is not used to reject harmless floating-point drift.

`cook_cinematic_props.py` and `ue_import_cinematic_props.py` prepare a **new,
isolated** UE4.22 project, under `/Game/Assets/FootballNX/FixDemo/`. They recheck
the preparation/FBX hashes, import only the two audited props, measure actual
Unreal bounds, require ES2 and ES3.1 shaders, and validate a narrowly scoped
asset-only PAK. They do not install it or enable a ceremony. The material is an
explicit base-colour/scalar PBR approximation, not a port of the packed Fox
normal/specular shader. Its appearance still needs hardware review.

The isolated UE4.22 cook completed. `validate_cinematic_props_cooked.py` then
independently exported the cooked meshes and matched all oriented source
triangles/corner UVs with fixed axes, without fitting a rotation or reflection.
Maximum position error was 0.000000060 m for the cup and 0.000000477 m for the
platform; maximum UV error was 0.000030518, and packed-normal error stayed below
0.456 degrees. No front-face normals were opposed or degenerate. Single-section
material identities and ETC1 texture formats matched. UModel cannot decode the
material's `Metallic` property, so this audit does not independently establish
the scalar material values or shader appearance.

The asset-only PAK contains 14 files (1,379,421 bytes), embedded ES2/ES3.1 material
shaders, and no unrelated engine/plugin packages. UnrealPak confirmed all 14
entries healthy; an independent unpack/hash comparison matched every cooked
payload. This is still **not a playable trophy update** and has not been
installed. Preparation never changes the user's active PAK or CPKs.

Reproduction notes: this host required `-nothreading` for the isolated import
commandlet to avoid a startup stall. UE4.22 does not expose `StaticMaterials`
through Python editor properties; the importer uses reflected section/material
methods instead. The package check matches UE4.22's named-archive verdict and
exact file count. A packaging-only retry may reuse the same verified import
profile/cooked tree, but refuses an existing output PAK.

The wrapper now exposes a read-only live Cup-final context in
`competition_frontend_cup_live_final_context()`. It preserves the already
established native HOME/AWAY swap, excludes third place, simulations, recorded
results and failed handoffs, and never changes tournament/save state.
`fixdemo_ceremony_policy.h` separately checks the actual END phase, exact
result-call boundary, fresh current-match teams/scores and a monotonic match
token. It uses shootout-only scores only after a tied match and consumes its
one-shot latch only after an explicit backend success. It produces a plan;
**no result factory is redirected by this helper**.

`fixdemo_prop_bridge.inc` is similarly an inactive preflight, not a renderer
hook. The owned Mobile ELF hash and nine symbol/instruction windows bind its
memory-layout assumptions. Package markers are not approval by themselves.
Its mesh-readiness check requires a real mesh bound to the expected component,
not merely a non-null actor, and requires a serialized lifecycle boundary.
Unknown or incomplete evidence cannot activate the bridge.

`fixdemo_prop_backend.h` is a **probe-only** adapter candidate, not included by
the wrapper. Twelve whole-function ABI fingerprints and eight bounded ARM64
probes establish native cleanup order, the 24-byte DemoObject layout, hidden
display and deletion. It forwards the original CreateObject once, stages the
native Cobra-string/load ID, and moves ownership only after a non-null model
and valid load key. It rejects the native Init function's misleading success
when its key is 192. Failed staging restores ownership without touching the
native animation/parent transforms. These probes do not run UE loading, the
renderer scheduler, full native teardown or hardware scene playback.

### Native prop route: offline proof and remaining canary gate

The owned Mobile ELF provides a native route without new direct UObject
access. `FixDemoCutFile::LoadObject` (`0x7b62f60`) queues `LoadObjectTask` in
`DataManager+0x5f8`. `DataManager::Exec` (`0x7b57ec4`) visits that queue only in
its game-thread mode; background mode visits the separate `+0x5a8` queue.
The task calls `ObjectData::CreateObject`, then polls `FixDemoObject::IsReady`.
This establishes the native scheduling route, not the Switch thread identity
or a new hook's synchronization. Native `ObjectData::DeleteObject` hides and
virtually deletes its owner; the owner deletes its DemoObject and animation
controller. The adapter must retain these ownership boundaries.

`FixDemoMain::DrawWork` sets the native parent before `DrawModel`. The latter
combines extracted root motion, the parent pose, and the **last animation
bone's** pose before `DemoObject::Update`. For the rigid one-bone cup, this is
bone zero; the unanimated platform uses the world pose directly. Five bounded
read-only ARM64 probes passed for platform placement, one-bone animation with
and without a parent, hidden display, and inactive owners. Matrix/animation
callbacks were simulated with identity rotations: these are routing checks,
not full animation, coordinate-system or renderer acceptance.

Readiness remains the concrete blocker. `DemoObjectList::CreateSomething`
(`0x7b3b4e8`) marks its entry loaded after `ObjectModel::Load` only stores a
filename and pending flag; it even marks a null-model entry loaded.
`DemoObject::IsReady` reads that entry flag. Later `UEObject::IsLoaded`
(`0x3f015ec`) checks only actor existence. Six additional bounded probes
confirmed these false-positive readiness cases and the game/background queue
split. Actual mesh loading/binding occurs inside `AObjectBaseActor::LoadMesh`;
a missing asset returns without binding a mesh. Its return is after a load
attempt, **not** a success signal, and no audited DemoObject notification
exposes the result. Returning from `ObjectModel::Update`'s initial load step
therefore must not be used as a verified mesh-completion boundary.

Before an explicit local canary, a separately verified serialized completion
observer must check the exact expected bound mesh, owner, load key and scene
token. It must have a finite frame/time budget, never wait indefinitely, and
keep failure hidden. On mismatch, expiry or scene teardown, release only the
still-owned candidate through native deletion, without touching a replacement
owner, native animation, parent assignment or result selection; retain the
ordinary native scene fallback. Neither this observer nor its asynchronous
failure/teardown behavior is implemented or proved by the probe-only adapter.
The production gate remains disabled. At the 2026-10-15 audit the staged
entrance port had not been installed on hardware; the later report of a working
current intro does not identify that package. None of the offline trophy
results is Switch playback evidence.

## Reproduce and test locally

```powershell
python -m pytest tests/test_fixdemo_scene_table.py tests/test_entrance_scene_canary.py tests/test_stage_entrance_walkout.py tests/test_fixdemo_scene_trace.py -q
python tools/stage_entrance_walkout.py --fl26-root '<owned-FL26-directory>' --mobile-root '<validated-runtime-baseline>' --output local-debug/entrance-walkout-test
```

The staging tool refuses an existing output directory, unsupported native
table shape, missing/ambiguous dependencies and pre-existing donor assets.
Build the matching NRO against the same runtime pair; retain all 23 unchanged
CPKs, the dummy OBB, PAK and selector/catalog assets. A candidate is not a full
runtime or an update for an arbitrary baseline. Read its generated `INSTALL.txt`
and `walkout-report.json` before copying anything to the Switch.

Hardware acceptance: start in Konami stadium; test natural completion and Skip,
both teams/kit combinations, High and Low, then two consecutive matches.
Confirm correct player/referee placement, cameras, ball and HUD recovery,
kickoff, normal FPS and no retained scene actors. Check `cinematic-trace.log`
for the end callback returning. If it stalls or actors/cameras are wrong,
restore **both** the original `dt220_mobile_all.cpk` and its matching manifest.
Do not promote the candidate based solely on the offline tests.

## Remaining result-boundary integration evidence

Read-only inspection of the owned Mobile ELF (SHA-256
`a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`)
confirms a candidate seam: `match::FixDemo::CreateFixDemo` calls
`FixDemoResult::Create` at RVA `0x620c1a0`, returning at `0x620c1a4` into the
native owner. The distinct halftime call at `0x7bf333c` must be rejected.
The current diagnostic PLT wrapper checks the factory signature, not this
caller identity; scene `0x80001` and side `2` alone are insufficient.

The existing phase reader obtains actual MatchPhase through GlobalRegistry's
MatchInfo pointer (`+0x4f0`, then `+0x1168`); only END `10` is eligible.
Existing score APIs provide match goals with HalfKind `5` and shootout-only
goals with HalfKind `4`, through `RecordInfo::GetMatchStats` and
`StatsMatchInfo::GetTeamInfo`. Native TimeUpDemo reads RecordInfo from its
borrowed Registry at `+0x1d0`. This does **not** make the throttled, token-free
pause-score cache valid evidence for a new ceremony.

The factory hook has no Registry argument. Its owning function receives one
on entry, but overwrites its saved `x22` before the factory call. Integration
therefore still needs an ABI-checked, invocation-scoped entry capture and proof
of the native read-lock/serialized lifetime. No engine pointer may escape that
scope. Fresh phase, both teams and scores must belong to the same match token;
phase timing at the candidate call after ordinary and shootout endings remains
unverified on hardware. Unknown ownership or freshness must use the original
result path.

The frontend getter and policy use **logical catalog team IDs in native
HOME/AWAY order**, not encoded physical IDs. Recheck actual native teams using
the established logical-to-physical mapping (`physical_team_id << 14`) before
publishing the logical IDs. MatchSetup is the existing lifetime boundary, but
its 32-bit HUD serial is not a ceremony latch: a dedicated nonzero monotonic
64-bit token, failure/teardown invalidation and serialized one-shot ownership
remain integration work.

Before returning any replacement, prove asset readiness and backend success,
not merely allocation. A failed candidate must release its own resources and
restore native FPS before calling the original result factory once. A committed
candidate must retain native virtual execution, derived destruction and Skip
ownership; never leave two owners or consume the latch on failure. No new
factory hook, global Cup predicate or MatchTop-state override is installed by
this audit. Shell/static evidence and offline tests are not scene playback or
hardware validation.

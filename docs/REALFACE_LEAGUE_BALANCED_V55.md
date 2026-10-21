# English/Spanish balanced real faces v55

21 October 2026. Offline TEST work; no final candidate has been delivered.

## Current checkpoint and continuation

Read `local-debug/realface-leagues-balanced-v55/RUN-STATUS.json` and the live
log for current counts. The selected source cohort is **907** (original 897
plus ten documented aliases). **All 907 passed preparation and independent
cooked validation**, including all ten source additions.
All 907 fronts and all 405 main critical heads in four views have now been
actually inspected and recorded: **2,122 unique current images**, with zero
superseded proofs. The completed main render produced 2,527 image instances
(907 front plus 405 four-view sets); repeated fronts do not increase the
unique inspection count. These are partial inspections, with unresolved
material/card concerns and additional flagged heads outside the main plan.
The subsequent flagged review has also finished: **419 heads in four views**
(405 main plus 14 additional heads), **2,164 unique current images** including
all 907 fronts. All 93 original flagged heads and all 87 queued source/prepared
comparisons were actually viewed. Ten observations were manually resolved after
four-view, identity, geometry/cook and mip checks: seven short/swept-hair or
eye-only observations and three exact user-pinned accepted heads. **83 visual
detail / 77 source-comparison flags remain open**. This is not final acceptance.
The actual inspection count is recorded separately in
`VISUAL-REVIEW-PROGRESS.json`; it must not be inferred from generated previews.
Remaining material decisions/repairs and PAK/ZIP packaging remain pending. Preparation, cooked validation,
generated previews and visual inspection are separate counts. Do not claim
full roster coverage, visual acceptance or 60 FPS.

The main preview runner and both serial follow-up queues have finished. Their
historical receipts are `PREVIEW-RESUME-LATEST.json`,
`RENDER-FOLLOWUP-LATEST.json` and `MATERIAL-FOLLOWUP-LATEST.json`. All required
main/source/detail output was inspected and recorded. Do not treat the PIDs
inside completed receipts as live owners or repeat 907 preparation/cook/preview
jobs. Read `REVIEW-HANDOFF.json` and the latest material diagnostic receipt for
current work; verify actual process ID, creation time, command and children
before resuming any worker. No owned renderer or canary remains active at the
08:20 Jakarta material checkpoint. The hourly continuation remains active.

The preview shutdown regression was fixed before completion: waiting without
draining piped stdout could block Blender teardown. The client now uses
`communicate` with bounded graceful/terminate/kill stages, retains ownership
until the old process is reaped, and refuses duplicate workers. Image recipes
and the renderer remained unchanged. Current diagnostics reuse completed
geometry/cook evidence where payloads are exact; a changed candidate must get
its own bound validation and actual image inspection.

Use one serial runner and one Blender/editor/validator at a time. Stages share
a Windows process-held lock. Inspect stderr and the specific import, cook,
validation or render log. Resume unchanged successes; never repeat
deterministic failures without a changed input/recipe. Source-atlas and mip
checks are diagnostic gates, not automatic acceptance. Keep caches, temporary
files, logs and outputs on D. Do not duplicate OBBs, edit source payloads,
replace the installed runtime or touch other work.

Existing hourly heartbeat `real-face-inggris-spanyol-5k` remains active. Do
not duplicate it; disable it only after verified final delivery. It stays
quiet without actionable changes. Local runs need the computer/app available:
[scheduled-task documentation](https://learn.chatgpt.com/docs/automations?surface=app).

## Scope and immutable foundation

The supplied catalog contains **19 English and 20 Spanish teams**, 1,122
unique active roster identities; Sunderland is absent. BaseId, native storage
ID and fingerprint must all match. Club/national assignments do not duplicate
heads. A reused numeric slot is not identity evidence.

The accepted [v46 Barca/MU cohort](STADIUM_FACE_SWEETSPOT_V46.md) contains 50
heads, including four retained originals at 5,962–6,932 triangles. Every
accepted asset must remain byte-identical to its pinned package. Rejected
v38/v40 reduced heads and generic flattened/dome hair are not reused.

The full [v54 foundation](REFEREE_NATIVE_V54.md), build
`79cf4f629bf5992fc6e878d96f15f7ff29a32c19`, is pinned in local config. Its NRO,
`Animations/referee.nxra`, `referee-probe.txt` and
`Commentary/players-v53.nxcp` must remain byte-identical; all four were rehashed
successfully. No NRO rebuild is part of this batch. Trophy lifting and complete
PC referee AI remain separate unresolved work.

A setup path-variable bug once overwrote the local v54 commentary copy with
JSON. Exact bytes were restored from its hash-verified original ZIP; installed
runtime was untouched. The regression test now checks immutable initialization.

## Source coverage

`realface_league_source_extension.py` rechecks the ten
[documented aliases](../data/realface-source-aliases-v1.json), current owners,
archive metadata and all original dense-conversion cache hashes. New ignored
manifests under `source-extension/` extend 897 to 907 without editing historical
manifests or existing successful results. Source-only `source_ready_verified`
is not new cooked/visual acceptance. Original dense sources are reused, never
rejected 2k conversions. See [historical recovery](REALFACE_RECOVERY_V40.md#source-recovery).

Added preparation counts: Cuéllar 4,979; Bellegarde 4,629; Tsitaishvili 4,978;
Protesoni 3,867; Kalimuendo 4,977; Urko 4,975; Pablo 6,979; Osula 4,979;
Jair 4,979; Youssef 4,951. Pablo has an explicit bounded exception.

`audit_realface_unresolved.py --config <local-config>` writes read-only
`UNRESOLVED-SOURCE-AUDIT.json`. Of the remaining **215**, two have direct source
parts but unresolved identity, 81 have verified direct identity but missing
required parts, and 132 lack both verified direct identity and complete direct
parts. Do not call all 215 confirmed absent. The two explicit conflicts are
Benoît Aimée/Nicolas Jackson (140870) and Bahoya (157602, conflicting foot
metadata). No speculative donor or global identity-gate relaxation. Historical
v40 also checked base Data CPKs without finding extra numeric face sources.
Report unavailable, identity, geometry and visual holds separately.

## Geometry, repairs and cook gates

Normal complete-head target **4,500–5,000 triangles**; documented exceptions
must be **strictly below 7,000**. Smaller valid heads are not padded. Keep the
accepted native-rig/source-eye/seam/neck/smooth-normal path, one opaque face
atlas plus one masked hair section, 256px face and 128px hair. Shape, UV,
skinning, anatomy, normal and 13-view projection gates remain.

Try 5k with 3,000 skin triangles, bounded 2,800/2,600 redistribution, then a
recorded 7k exception. Anatomy/UV failures do not authorize less face detail.
At least 20 source triangles touching the forward lower face requires protected
facial-hair cards. Numeric silhouette success cannot approve bad appearance.

All original 897 now have independent cooked validation. Final 17 source
repairs preserved final gates and immutable originals:

- Bounded hair error/UV searches recovered Tomiyasu 6,804, Mitoma 6,971 and
  Pedro Lima 6,902; skin/eye settings and facial locks remained unchanged.
- Invisible-slot policy requires conservative filtered/wrapped UV alpha proof
  or rigid microscopic bone-frame bounds. Empty raster alone never proves
  invisible hair. Original FMDL/extraction hashes bind same-player empty-part
  proof: authored points, transparent triangles, or microscopic meshes deeply
  inside their own skin with clearance/ray checks. Isi Palazón's converted
  ghost markers use the explicitly proven empty original PC reference.
- Proven empty slots keep one zero-alpha native-head-bound triangle alongside
  ordinary opaque face geometry. No visible hairstyle is removed.
- Anselmino 4,979 needed converted sentinel cleanup near 930 m. Only two
  bit-identical corners with identical normalized weights prove zero area in
  every pose. Approximate thin cards, different bindings, nonfinite vertices
  and broad distance clipping fail.

Blender named some generated empty materials `.001` (UE `_001`). The shared
`realface_material_slots.py` accepts exactly those aliases with adjacent valid
invisible-slot proof, one hair material, no hair-skin and merged eyes. Unknown
slots fail; prepared caches are immutable. The helper is tested against UE's
actual Python **2.7.14**, as well as host Python.

Cook/import chunks are at most 12 heads. Keys bind inputs, recipe/compiler/
helper versions. Each new cooked head independently checks mesh, rig, UVs,
normals and triangles before publishing a cache. Failed cook rows remain
retryable with changed recipes; previews cannot proceed with missing cooked
validation. Accepted 50 and already verified heads are not recooked.

## Preview evidence and outstanding inspection

`VISUAL-REVIEW-PROGRESS.json` records actual inspection, image hashes and
pending detail IDs; it is not final approval. Check every front and four views
(front/left/right/above) for exceptions/protected facial hair. Previews show
prepared FBX with decoded cooked textures, not device captures or complete
PC/mobile shader simulation.

Use `realface_review_progress.py --config <local-config> status` for compact
counts and pending sheets. After actually viewing named sheets, use `record
--sheet <path> --finding <finding>` (repeat `--sheet` as needed). This checks
current prepared/cooked/renderer keys, image and completed-batch hashes. It
records partial evidence only; changed cook keys cannot inherit old inspection.
Hashing older inspected images can be slow on this machine. A running `record`
writer must finish before another process writes the progress file. Check
`INSPECTED-PENDING-RECORD.json` for any actually viewed sheet waiting to be
recorded; verify its image hash and avoid concurrent ledger writers. This
backlog is not final acceptance and does not replace current provenance checks.
Add new concerns with `--pending-detail <BaseId>`. When the main runner and its
children have finished, `render-details` uses the same exclusive lock and
persistent worker to fill flagged front/left/right/above views, reusing exact
matching previews. Inspect those results before recording them. Initial flags
101585, 118111 and 120430 were outside the main 405-head
exception/facial-hair detail plan; later flags must also be checked. Do not start
this beside the active runner.

An old pending request 57533 had no owner in the cooked cohort or inspected
image evidence. It is archived in `visual-metadata-repairs/retired-57533/`,
and removed only from the review queue. This is not an identity alias or a
finding that a player is unavailable. Dani Carvajal is independently verified
as 57353, with his own inspected four-view concern. Recording now checks both
existing and newly requested IDs before hashing images; status exposes invalid
pending IDs. No identity, geometry, texture, cooked asset or image was changed.
Read BaseId/name from the matching `PROVENANCE.json` when writing findings;
small contact-sheet labels are not identity evidence.

Use `record --source-comparison <BaseId>` to queue a questionable appearance
without approving it. Once the main runner and children finish,
`render-source-comparisons` renders original and reduced fronts in serial
12-head chunks using the same lock and persistent worker. Its index also binds
the exact current cooked front for comparison. Inspect all three stages before
resolving a concern. This diagnostic cannot grant cooked acceptance, clear a
pending flag or modify the source. Read the current IDs from the progress file.
A cap-like shape alone does not prove lost hair:
compare the player's own source before changing geometry or UVs.

Source/prepared reference images now also have a conservative regrouping cache.
`realface_reference_preview_cache.py` requires a completed reference receipt,
exact stage, native ID/fingerprint, source/prepared key, config, renderer,
preview adapter and PNG/sidecar hashes. It never reuses cooked evidence as a
source reference, changes a render recipe, or records visual acceptance.
Unsealed old diagnostics are not silently trusted. This avoids repeating valid
reference renders when additional flagged heads change the twelve-head groups.
The focused reference/review/preview/worker suite passed 40 tests in 6.51 seconds;
receipt: `D:/PESNX-Cache/Logs/realface-v55-reference-regroup-cache-tests.log`.
Live reference-cache integration now verifies the first completed twelve-owner
source and prepared batches against current config, native ID/fingerprint,
source/prepared key, renderer/adapter and PNG/sidecar hashes. Lookup finds all
twelve exact owners in each separate stage. The local receipt is
`texture-diagnostic/REFERENCE-CACHE-LIVE-INTEGRATION.json`; it is diagnostic
cache evidence, not cooked acceptance or proof of a subsequent regrouped copy.
The later regroup integration verified 22 moved PNG/sidecar pairs byte for
byte; the two late owners needed only four new reference render requests.
Of 174 reference images, 170 were reused. The receipt is
`texture-diagnostic/REFERENCE-CACHE-REGROUP-INTEGRATION.json`.
The public-tree audit after this cache addition passed 1,189 files:
`D:/PESNX-Cache/Logs/realface-v55-reference-cache-public-tree.log`.

The follow-up source/prepared comparisons for Ampadu, Semenyo and Mujaid Sadick have
now been inspected in full-size fronts (six diagnostic images). Ampadu's
angular clusters and Semenyo's broad under-chin cards already exist in the
unreduced converted source; source/prepared textures retain finer beard fibers
than cooked textures. Sadick's wide eye shape/gray iris also match the source
profile, with eyes present and aligned. No full PC shader is simulated and no
flags are automatically cleared. Increasing triangles alone is not an evidenced
fix for these source/material concerns. The progress receipt keeps historical
hashes separate when a diagnostic path is rerendered after a material repair.

The preview worker reuses one Blender process for eight serial requests of
at most 48 views, then recycles it. Renderer, scene reset, materials, resolution
and samples stay unchanged. Matching receipts and renderer hashes are required
before sidecars are written. Failure/wrong tokens cannot bless older images.
Check the first live worker receipt; unit tests alone are not integration proof.
The first two live requests succeeded in the same persistent Blender worker:
all six source/prepared comparison images were inspected. Their receipts and
hashes are recorded in `texture-diagnostic/PERSISTENT-WORKER-CHECK.json`.

Preview cache reuse requires exact current prepared/cooked/renderer keys and
PNG hashes, even after chunk regrouping. `PREVIEW-COMPLETE.json` stamps batches;
`PREVIEW-INDEX.json` lists required images after completion. Rendering ends
`awaiting_review`, without automatic approval.

Outstanding details include coarse beard/hair cards. Cullen 108525's skin-toned
hair plates were repaired by the scoped, promoted canary described below.
A 1024x256 atlas can become 128x32 after cook; full-size comparisons
for 44104/47524/60709 are under `texture-diagnostic/prepared-full-hair/`. They
also show this renderer's card/shading limits: larger textures alone are not
proven to fix it. Raw Valverde 113911 hair is already gray/white; color alone is
not a conversion defect. Before further full-cohort previews the finalizer
renders `texture-diagnostic/source/` and `prepared/` for 108525/113677/113911.
The diagnostic set also includes Ampadu, Semenyo and Mujaid Sadick
(118657/124266/124855) for source-versus-reduced comparison.
Source-stage images check original input hashes and have no cooked key, so they
cannot satisfy cooked acceptance. Inspect comparisons before clearing flags.
No global texture-size or geometry change was selected from these diagnostics.

A read-only material audit for 14 flagged identities (29 raw FMDL files) is in
`texture-diagnostic/FLAGGED-SOURCE-MATERIALS.json`, with a compact summary beside
it. All 14 dense profiles use the recorded common native-eye texture; most raw
faces also have PC eye-occlusion materials. Source-stage previews use that dense
conversion and do not reproduce the full PC eye shader. Matching wide eyes in
two converted previews alone cannot verify original PC appearance or clear a
flag. Multiple hair UV sets likewise do not authorize Cullen's UV switch for
another player. No source, geometry, texture or budget policy changed in this audit.

The later cached raw-material grouping covers the first 74 flagged owners
(152 FMDLs): 47 have hair with distinct UV sets and 72 have PC eye-occlusion
helpers. Its immutable report is
`texture-diagnostic/material-groups/125143f40a7ed911/AUDIT.json`; subsequent
expanded metadata scopes are pointed to by `MATERIAL-GROUPS-LATEST.json`.
The current expanded scope covers **93 owners / 191 raw FMDLs**: 60 owners
have hair with distinct UV sets and 90 have PC eye-occlusion helpers. Every
selected owner has its own direct raw folder; none was replaced with a donor.
All source identities and file hashes are checked. This is metadata evidence,
not a PC shader reconstruction, a UV repair selection, or visual acceptance.

An additional read-only eight-owner UV/color sample audit is pointed to by
`texture-diagnostic/SELECTED-HAIR-UVS-LATEST.json`. Several primary UV0 hair
samples are nearly constant gray, while the same owner's secondary map and UV1
contain different colors. This suggests a material approximation worth testing;
it does not determine the PC blend equation or authorize a global UV/color fix.
Huijsen 159586 has a separate, unapproved mesh-0 UV1 canary plan in
`texture-diagnostic/huijsen-uv-canary/06ac906c9075045d/`: geometry, normals,
weights, topology, skeleton bind and atlas pixels match his dense source;
only the selected mesh UV mapping differs. The shared-lock check refused an
export while the reference renderer was active. Export, preparation, independent
cook and four-view inspection must succeed before considering promotion.
The experiment uses a short local output root to avoid the previously observed
UModel path-length failure. No league assets, accepted Barca-MU result or v54
payload was changed by planning it.

`MATERIAL-FOLLOWUP-LATEST.json` pins a second hidden continuation to the exact
first queue process and its creation time. It waits for successful
`awaiting_inspection` and no surviving related worker, checks pinned inputs,
then fills the two late source comparisons through the sealed reference cache
and runs the isolated Huijsen experiment serially under the shared lock.
It cannot promote the experiment or grant visual acceptance. Inspect both
queue receipts before starting manual render/canary work; a failed dependency
or changed hash stops this continuation instead of silently retrying it.

Both queued continuations subsequently completed. The UV1-only Huijsen trial
passed independent cooking at 4,978 triangles but was rejected after four-view
inspection because crown patchwork and gaps became worse. A separate
own-secondary-diffuse/UV1 trial (4,979 triangles) improves the gray crown color,
but prominent plates remain; it is held and has not been promoted. These are
different keyed recipes, not retries of the rejected UV1-only input.

Rioja's fractional-alpha reference visibly softens beard plates. A separate
native-masked 256px cook retains some finer fibers but leaves the large plates;
hair mip storage rises from 21,852 to 87,388 bytes, so this resolution-only
repair was rejected. A fixed-size alpha-1.5 experiment preserves RGB,
dimensions, mesh/rig/material payloads and the current mip gate, and looks
smoother in four views. It remains experimental: an additional hair-only render
comparison loses 35.5-49.4% of hair-layer pixels. That measure is not the existing
3D geometric projection gate; it does require a reasoned coverage reference
before accepting a smoother underlying painted scalp as preserved hair.
Stronger alpha exponents 2/3 already fail the unchanged mip gate.

The full 907-head cooked-hair mip audit is pointed to by
`texture-diagnostic/HAIR-MIP-AUDIT-LATEST.json`: 765 are visible/intentionally
empty, 112 need the existing permitted tiny-mip protection, and **30 are held**
for visibility outside that policy. None of those 30 belongs to the accepted
50. These are separate packaging gates, not unavailable-player or identity
findings, and do not establish observed device behavior. A two-owner native UE
alpha-coverage-threshold cook for Cairns/Rioja keeps RGB and dimensions exact
but fails the existing mip gate on both; that recipe is rejected. No mip guard,
source asset, shared importer/renderer, accepted payload or active runtime was
changed to turn a failed trial into a pass.

An own-authored-normal audit for Rioja, Reece James and Huijsen is in
`texture-diagnostic/AUTHORED-HAIR-NORMAL-AUDIT.json`. Some source transfer
materials have normals departing substantially from the geometric card plane.
The initial FBX conversion currently rebuilds custom normals; the later hair
normal transfer can only project those already-converted directions. This is
a separate shading hypothesis, not a demonstrated repair. The first isolated
Reece James trial retains the original glTF hair-normal attribute and passes
cooking at 4,820 triangles, but actual inspection finds dark facets and broken
beard lighting; that naive preservation recipe is rejected.

The source exporter compensates bind positions and includes reflections. A
second isolated recipe transforms authored corner normals by the inverse
transpose of that same per-vertex position map, checks reconstruction, and
retains polygon/vertex association when reversing winding. It keeps the same
geometry/UV/rig/texture inputs and uses the existing bounded preparation, cook
and validation path. It passed at 4,820 triangles and all four actual views
were inspected. Hair cooked vertices increased from 3,384 to 3,386, with the
same face. Broad gray hair/beard plates remain; this trial is held without
promotion or a performance claim. The public exporter/renderer is unchanged. Do not disable normal
repair, face winding, bind compensation or any quality gate globally.

A subsequent isolated Reece diagnostic bakes his explicitly referenced
secondary albedo from UV1 into the primary UV0 atlas, averaging overlapping
RGB samples in linear light. Every existing alpha mip, geometry, UV, normal,
material, texture dimension and payload size remains exact. Independent payload
roundtrip and the unchanged mip gate pass. All four actual views were inspected:
gray plates become dark source-colored hair, but the broad beard cards remain
an open concern. This is a scoped approximation, not a PC shader reconstruction
or final acceptance. Its all-atlas mapping fraction also includes unused source
texels and must not be called surface-coverage proof. Further trials may only
use each owner's documented material/UV/texture correspondence and immutable
alpha; no arbitrary tint, donor, global UV change or extra runtime sampler.

The source-atlas match must also cover the prepared input recipe. The read-only
`tools/realface_hair_atlas_correspondence.py` checks BaseId/native ID/fingerprint
across the source, prepared job and source profile, then hashes both source FBX
and atlas and requires the existing card UV domain. The live 83-owner audit
finds 82 matching recipes; Cullen's promoted UV1 input intentionally differs
from the raw UV0 catalog. His generic RGB diagnostic must not be promoted or
used to undo the earlier repair. `RGB-PREPARED-CORRESPONDENCE.json` records this
extra gate; a matching result still provides no geometry or visual acceptance.
Eleven synthetic regressions pass, including copied identical inputs, reused
IDs/fingerprint mismatches, an existing own UV repair and missing local fixtures.

The remaining 80-owner RGB diagnostic batch has completed: 47 rendered trials,
32 inapplicable source-material layouts and one correspondence hold (146944).
All 47 four-view sheets were actually inspected; with the initial three trials,
this is 50 heads and 200 diagnostic view instances, separate from the 2,164 main
unique images. Source color often improves, but broad beard/crown cards remain.
None was promoted. The immutable receipt, matching script and inspection index
are in `texture-diagnostic/own-secondary-rgb-batches/remaining-eighty/`.
Inapplicable material layouts are not unavailable players or visual acceptance.

The own-face-supported Reece beard experiment has finished and is rejected.
Its final 4,704-triangle version passed the existing dense 13-view gates and
additional bidirectional 0.45 cm beard-contour bounds. Independent cooked
validation was recovered without recooking after a missing legacy `recipe.eye`
metadata field; the parent face FBX and opaque atlas were byte-identical, and
the canonical parent eye metadata was retained. Actual four-view inspection
still found jagged dark beard slabs. Hair cooked vertices increased from 3,384
to 4,630. Numeric triangle reduction therefore did not produce a useful visual
or performance candidate. Do not promote or repeat this recipe.
`texture-diagnostic/BEARD-VERIFICATION-RECOVERY-LATEST.json` points to its
completed validation and explicit visual rejection.

A subsequent source-geometry trial retained all hair positions, weights and
triangles and blended beard RGB/normals toward the same player's own face only
within 0.6 cm. Crown pixels, face FBX and opaque atlas stayed exact; a separate
beard tile increased the hair atlas from 128x64 to 128x128. This version passed
independent cook, rig, UV, normal and unchanged mip gates at 4,820 triangles;
hair cooked vertices were 3,386 versus 3,384. Its four actual views and full-size
left view were inspected. Pale roots improve, but coarse projecting cards remain;
it is held without promotion. `texture-diagnostic/BEARD-TRANSFER-LATEST.json`
binds the result and inspection to immutable authoring snapshots. It is an
offline approximation, not a complete PC shader or hardware-performance proof.

The read-only `texture-diagnostic/MIP-HOLD-ALPHA-EXTENTS.json` checks all 30
separate mip holds. Most source atlases have nonzero alpha extending across
nearly their complete bounds; simple transparent-border cropping would not
solve them. Several lose all alpha-tested texels at 4-pixel mips; three already
fail at 8 or 16 pixels. Keep the existing mip guard. Increasing texture size,
forcing medium-mip alpha above the cutoff, or accepting a nonempty mip without
checking the hairstyle is not a demonstrated repair.

`tools/realface_mip_reference.py` adds a read-only orthographic mask diagnostic.
It measures destination alpha coverage, handles quantization/ties without
forcing a nonempty pixel, and compares periodic bilinear/trilinear sampling
against a supersampled base-mip mask on the same head geometry and skin depth.
No texture or runtime is patched. Tests include empty/unrepresentable masks,
UV addressing, projected footprint, skin occlusion and equal atlas coverage
with different visible head coverage. The combined helper/unchanged mip-guard
suite passes 14 tests. This is a sampling proxy, not a mobile GPU or shading
simulation; neither a lower average error nor a passing mip guard is acceptance.

The three actual diagnostic sheets for Robertson 101028, Cairns 101585 and
Mbappe 110718 were inspected. Destination coverage matching makes the existing
mip guard pass for all three. Mean projected error improves for the first two,
but some 8-pixel directions worsen, and Mbappe's aggregate error worsens.
`texture-diagnostic/MIP-REFERENCE-LATEST.json` binds the inputs, code snapshots,
per-view metrics and actual inspection. No alpha change was promoted. These
diagnostic sheets do not increase the 2,164 main image count.

The five-owner `texture-diagnostic/EYE-SOURCE-POLICY-AUDIT.json` distinguishes
the explicit shared neutral FL26 iris from a player's own native iris. Mujaid
Sadick, Boyomo, Nico Williams, Saliba and Lavia currently use that neutral
template. The same gray iris in a dense converted preview therefore does not
independently establish its PC color. Do not silently tint it or call it a
donor-player iris. Source eye geometry/guide alignment is a separate question.

Their own raw `pes3DFW_EyeOcclusion` helpers reference black RGB/alpha textures;
`EYE-OCCLUSION-METADATA.json` records the per-owner material, texture and identity
hashes. An isolated Mujaid trial projects that source helper onto the existing
eye surface within 0.5 cm and bakes a static eyelid shadow into the same 256px
opaque atlas. The negative-X eye gets a separate unused 56px atlas tile, with
an integer UV shift, so opposite lids need not share one baked shadow. This
adds no material, sampler, surface, triangle or texture size. Skin UVs and
encoded top-level skin pixels outside the two eye tiles remain exact, including
after cook; every face mip stays opaque. Coarse-mip RGB averages can change
because the previously unused tile now contains an eye.

The 3,751-triangle trial passed independent cook, rig/UV/normal checks and the
unchanged hair mip gate. Face cooked vertices remain 1,724 and hair vertices
337. All four full-size cooked-texture views were inspected: bright globe rims
are reduced and both irises remain present/aligned. Only the scoped static eye
material fix is accepted; the short crown cards remain an open head-review
concern. This is not animated gaze, a complete PC shader or factual iris color.
`texture-diagnostic/EYE-OCCLUSION-CANARY-LATEST.json` and the promotion receipt
under `material-repairs/124855/` record the current publication/ledger state.
Check the actual writer before any family trial; do not rebake a promoted head
or rerun all 907 models. Four further audited neutral-eye owners are queued for
serial prepared-only inspection before any cook is permitted.

The six inspected comparisons confirm Cullen's pink/skin-colored hair plates
already exist in the dense converted source, before reduction. Do not clear
that defect merely because source and reduced results agree. His material
audit finds `pes3DDF_Hair2_NrmUV`, two diffuse maps and two UV sets; the legacy
atlas policy picks UV0, while glTF export retains only UV0. The local UV audit
found far fewer skin-toned samples in UV1. That observation was tested with a
separately keyed, own-source canary and promoted only after the checks below;
it is not a simulation of the complete PC shader. Every further material repair
must preserve geometry/skin/identity and pass alpha/rig/budget/cook/visual gates.
Never switch all players, paint arbitrary
hair colors or remove visible cards to increase coverage. If no bounded repair
passes, retain an explicit visual hold/native fallback in the package report.
The audit files are `texture-diagnostic/108525-source-material-audit.json` and
`108525-uv-channel-audit.json`. Original source files remain immutable.

An isolated Cullen canary plan is now built under
`texture-diagnostic/uv-canary/50c497858f6d5f2c/`. It switches only the selected
mesh's diffuse UV0 to its own UV1. Exported positions, normals, topology,
skinning attributes, skeleton and bind matrices compare byte-for-byte with the
original dense glTF; the atlas pixels also remain byte-identical. This is a
host-side plan followed by a completed isolated export, 5k preparation,
cook, independent validation and four-view inspection. The source/export,
validation recovery and explicit local promotion entry points remain under
`texture-diagnostic/`. They acquire the shared runner lock and now refuse to
repeat after promotion. Do not rerun the canary; resume the main finalizer.
Its live lock check already refused a second Blender while the main preview
was running. A local planner rerun initially hit a same-file texture-copy error;
the changed recipe now validates/reuses an existing plan instead of exporting
over its own nested texture lookup. UModel initially found no cooked packages
because their full paths reached about 300 characters. The exact cooked files
were copied with SHA-256 checks into the short ignored fixture
`local-debug/rfv55/145140a15882b82a/Content`; UModel then exported normally and
independent validation passed, without recooking or changing payload bytes.
`material-repairs/108525/a3de1c9764b25b52/PROMOTED.json` binds the previous and
new keys, source/validation evidence, unchanged accepted-50 records and all four
unchanged v54 hashes. Pink crown cards are gone; dark angular cards remain a
visual-review concern. Cooked hair is still 128x64, PF_B8G8R8A8, and the complete
head decreased from 4,979 to 4,718 triangles. No global UV policy, final visual
approval, runtime install or device-performance claim follows from this repair.
The earlier Cullen front was superseded rather than counted twice.

Additional full-size cooked-texture front checks are recorded for Mujaid Sadick,
Ampadu and Semenyo (124855/118657/124266). Sadick's eyes are present and pupils
appear aligned in the neutral view; the inspected dense source also has wide
eyes and gray irises.
Ampadu has conspicuous angular clusters; Semenyo's beard has broad folded dark
plates. Their dense source comparison is recorded; material/alpha and side-view
concerns remain open. Numeric budget success does not clear them.



The diagnostic at BaseId 124855 is **Mujaid Sadick** (fingerprint
`8ad5456527e1e0b99962`). Earlier prose called him Sadiq. Umar Sadiq
is a separate owner, BaseId 108270, fingerprint `4e7dded28edf55229d84`.
All source/cache/image proof IDs were correct; this corrects the label only.
Never reuse one player's eye or face comparison for the other.

The full-size left view for Luis Rioja 103041 confirms projecting dark beard
plates. Its read-only `texture-diagnostic/103041-alpha-material-audit.json`
finds source vertex alpha is always 1, while atlas coverage above alpha 85 is
27.6821% before cook and 28.0518% after (1024x256 to 128x32). The alpha channel
has not globally vanished or become opaque. This narrows the investigation;
it does not establish the exact PC opacity/blend formula or prove a texture-size
or cutoff change is safe. Keep the source shader/UV and masked-detail comparison
open. No global alpha, texture, geometry or triangle-budget policy changed.
The read-only `103041-uv-sampling-audit.json` finds a distinct second UV set
only on the transfer material, with its own secondary face texture. The main
hair and head-shell meshes have no alternate UVs. Vertex/triangle-center alpha
samples differ between maps, but do not identify the correct PC blend formula
or justify reusing Cullen's UV repair on Rioja.

`texture-diagnostic/compare-rioja-alpha.py` is a bounded, reference-only plan:
it compares current masked output, fractional alpha, and the prepared-size hair
texture for 103041, in front and left views. It reuses two verified baselines
and needs six new renders. `RIOJA-ALPHA-LATEST.json` pins the plan, input hashes
and dimensions. Planning and the live shared-lock exclusion check passed;
the actual reference images have been inspected. The diagnostic
does not recreate the full PC shader, authorize a new runtime blend policy,
provide cooked acceptance or prove device performance. Inspect the actual
comparison before selecting any separately keyed material canary.

## Final package and handoff

After real inspection write `VISUAL-REVIEW.json` with:

- `decision=offline_candidate_reviewed`, current prepare/verify report hashes
  and every successfully cooked `reviewed_base_id`;
- any `held_base_ids` with nonempty reasons;
- inspected individual PNG `{base_id,path,sha256}` entries and concise findings.

Sidecars must match current prepared/cooked keys, PNG hash and view. Front is
mandatory for every cooked head; exceptions/protected facial hair also need
left/right/above. Source-only/prepared-only/old previews cannot approve current
cooked assets. Never manufacture visual acceptance.

```powershell
python -B tools/package_realface_league_balanced.py `
  --config local-debug/realface-leagues-balanced-v55/config.local.json
```

The packager checks complete pinned scope, quality/cache/identity proofs,
accepted Barca/MU bytes, two sections, opaque face mips, surviving visible hair
mips, exact asset allowlist, UnrealPak integrity and independent unpack hashes.
It creates `FootballNX-v54-LEAGUE-FACES-v55-SIAP-COPY` plus ZIP under
`release-builds/`, reads back every ZIP payload and all four v54 hashes, then
writes `latest-candidate.json`. Coverage/triangle CSVs and installation notes
accompany it. Nothing is installed automatically.

User closes the game, moves old additional face PAKs outside `Paks`, then copies
complete `switch` to SD root. Keep main game/stadium/weather/intro/CPK/OBB/saves.
Deliver folder/ZIP links, truthful coverage/holds and hardware-test limits.
Disable the heartbeat after delivery.

The earlier combined focused suite passed **126 tests**; its receipt is
`D:/PESNX-Cache/Logs/realface-v55-checkpoint-126.log`. After adding the flagged
source-comparison queue and fixing worker shutdown, the focused
review/preview/protocol suite passed **25 tests** in 5.64 seconds, including
source identity binding, mandatory current cooked references, bounded serial
batches, active-runner exclusion, stdout draining and bounded shutdown
escalation without duplicate workers. Its latest receipt is
`D:/PESNX-Cache/Logs/realface-v55-preview-shutdown-tests.log`; the earlier
21-test receipt is `D:/PESNX-Cache/Logs/realface-v55-review-comparison-tests.log`.
The pending-ID preflight regression suite then passed **27 tests** in 17.38
seconds; receipt: `D:/PESNX-Cache/Logs/realface-v55-review-pending-preflight-tests.log`.
The complete authoring checkpoint selection then passed **122 tests** in
74.09 seconds (`D:/PESNX-Cache/Logs/realface-v55-authoring-checkpoint-tests.log`),
covering inventory, identity, preparation/recovery, slots, import/cache,
previews, worker shutdown, inspection bookkeeping and packaging gates.
Source-comparison rendering and regroup-cache integration subsequently finished;
actual inspection is recorded separately from these unit-test results.
An old 124-byte mock-worker log in the repository root was moved to D: logs;
the shutdown regression now uses its pytest temporary directory even on failure
and checks that no render log is created while closing. Its eight tests passed
in 1.56 seconds (`D:/PESNX-Cache/Logs/realface-v55-preview-temp-isolation-tests.log`).
The authoring public-tree audit passed **1,187 files**; receipt:
`D:/PESNX-Cache/Logs/realface-v55-public-tree-checkpoint.log`.
No final PAK/ZIP has been produced. Earlier session
history is retained in ignored `SESSION-NOTES-before-runbook.md`; normal
continuation needs this runbook and current status/logs.

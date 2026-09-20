# PES21 PC face transfer audit

Audit date: 2026-09-19. This is a format/feasibility audit against the local,
legally supplied Football Life 2026 installation and the supported PES 2021
Mobile v5.3.0 runtime. No PC or mobile game asset is stored in this repository.

## Result

Direct face copying from PES21 PC/Football Life into PES21 Mobile is **not
compatible**. A conversion pipeline is technically possible, but it is a new
mesh/material/cooking project rather than the CPK member replacement used for
kits and crests.

The audited Football Life face archive uses the Fox Engine asset family. Its
26,996-row CPK contains per-player `face.fpk`/`face.fpkd` packages and PC FTEX
maps. One inspected package has the `foxfpk` signature and embeds
`face_high.fmdl`, `hair_high.fmdl`, face/hair material names, and DDS/TGA source
references. The release mobile PAK instead exposes 2,888 player-ID-keyed UE4
packages under `Content/Assets/character/RealFace/<id>_face.uasset`, with
associated cooked exports/bulk data. These are different model containers,
material contracts, package namespaces, and runtime loaders.

Consequently, renaming `face.fpk`, copying an FMDL, or converting only its FTEX
textures cannot produce a loadable mobile face. The existing uniform converter
does not solve this: uniforms flatten a known texture atlas, while a face also
needs the skinned mesh, mobile skeleton/bone mapping, face animation or morph
contract, hair geometry/transparency, materials, LODs, and Android-cooked UE4
package metadata.

## Feasible conversion route

A one-player canary would require all of the following:

1. Resolve identity by eFootball `BaseId` plus fingerprint; never trust the
   numeric PC player ID alone.
2. Extract FPK/FPKD locally, decode `face_high.fmdl`, `hair_high.fmdl`, and the
   complete FTEX material set.
3. Retarget the mesh and weights to the exact mobile face skeleton and recreate
   its face/hair material parameters, LODs, and animation/morph expectations.
4. Cook new UE4 assets for the target Android ETC1 runtime using the compatible
   engine serialization version and the exact internal package names expected
   by `RealFace/<NativePES21Id>_*`.
5. Package the cooked `.uasset`/`.uexp`/`.ubulk` set into a detached local PAK,
   then validate boot, gameplay, replay, close-ups, lighting, hair alpha, and a
   generic-face fallback. Only after that can the process be automated.

The repository now has an experimental FMDL-to-mobile-rig intermediate
converter and a locally cooked UE4.22.3 canary accepted on Switch with known
minor clipping (V18; see checkpoint below). Therefore the status is
**one-player conversion accepted with defects; batch conversion not validated**. The safe
production policy remains to pin the 2,888 native mobile real-face owners by
`NativePES21Id`; a mobile/UE4 face source is materially closer than a PES21 PC
Fox Engine face.

## Lamine Yamal conversion canary

The BaseId `162114` canary now proves the model-conversion half of the route.
The local Football Life face package supplies `face_high.fmdl`,
`hair_high.fmdl`, `oral.fmdl`, and the complete player texture set. The new
project-authored `tools/export_pes_fmdl_gltf.py` exports those models without
vendoring the parser or game data. It preserves vertices, triangles, normals,
tangents, UVs, materials, and weights, and can read the exact 29-bone UE4.22
`test_body_Skeleton` reference pose from a local UAssetGUI JSON export.

The mobile-retarget mode performs these verified transformations:

- converts Fox metres to mobile centimetres;
- converts the Fox coordinate basis through UE4 Z-up into standard glTF Y-up;
- keeps shared chest/neck/head weights, maps Fox clavicles onto mobile
  shoulders, maps the Fox neck helper bones onto `sk_neck`, and collapses the
  unavailable Fox facial bones onto `sk_head`;
- uses the mobile reference skeleton's exact hierarchy, rotations,
  translations, and scale for inverse bind matrices; and
- merges duplicate joint influences and retains at most four weights per
  vertex, matching the audited mobile LOD contract.

The three outputs pass Khronos glTF validation with no errors or warnings:

| Part | Source bones | Target bones | Vertices | Triangles |
|---|---:|---:|---:|---:|
| Face | 38 | 29 | 2,198 | 3,998 |
| Hair | 33 | 29 | 19,046 | 24,362 |
| Oral | 6 | 29 | 1,870 | 3,066 |

`tools/blender_export_ue_fbx.py` then converts each ignored glTF into a local
FBX using centimetre scene units, drops the Blender import helper mesh, and
performs an FBX export/import round-trip. The canary retained all 29 target
bones and exact vertex/triangle counts for face, hair, and oral meshes. The
face occupies approximately 139--178 cm in the target bind pose and the hair
approximately 154--184 cm, consistent with the audited mobile head joint.

Example local export:

```powershell
python tools/export_pes_fmdl_gltf.py `
  --source local-debug/lamine-yamal-face-canary/pc-source/.../face_high.fmdl `
  --output local-debug/lamine-yamal-face-canary/intermediate-mobile-rig/face_high.gltf `
  --pes-fmdl-root local-debug/lamine-yamal-face-canary/third-party/pes-fmdl-blender/pes-fmdl `
  --texture-root local-debug/lamine-yamal-face-canary/pc-source/.../sourceimages/#windx11 `
  --target-skeleton-json local-debug/lamine-yamal-face-canary/mobile-donor-audit/test_body_Skeleton.json
```

The active Lamine physical appearance is already exact: the 56-byte payload in
the generated `PlayerAppearance.bin` is byte-identical to BaseId/card `162114`
in the locked eFootball appearance table. Current eFootball also reports
height `180` and weight `72`; those two `Player.bin` fields remain report-only
until their packed PES21 offsets are proven.

The runtime-cooking half has now reached a **local hardware-test canary**. The
installed UE4.22.3 editor imports the face, hair, and oral FBXs with the exact
29-bone mobile hierarchy and cooks unversioned Android ETC1 packages without
errors. The Blender exporter names its synthetic armature `Armature`, allowing
UE4.22 to strip that helper instead of serializing an incompatible thirtieth
root bone. It can also join the oral glTF to the face rig, so the runtime only
needs the native `162114_face` and `162114_hair` loader identities.

The first hardware run proved that the converted skeletal meshes load and
animate, but also rejected the locally recreated Fox-material approximation:
the face rendered green, masked hair/shell sections broke up, and auxiliary
oral/transfer geometry became visible outside the head. The second canary
therefore strips the Fox eyelash, eye-occlusion, oral, scalp-shell, and hair-
transfer sections. It keeps only the two principal skin meshes and principal
hair mesh, clones a native six-digit real-face material instance for
`face_162114`, and makes the hair mesh reference the original base-PAK
`hair_parts_tablet_ss` material. The placeholder base material used during
cooking is deliberately omitted from the detached PAK so the runtime must
resolve Konami's native shader.

The revised detached canary PAK contains 13 files, uses Zlib, PAK version 8
(matching both supplied runtime PAKs), and has mount point `../../../`.
UnrealPak's full integrity test passes. The base and existing pitch PAKs remain
untouched. The active local runtime now has the canary as:

```text
dist/pes21_nx/PesMobile/Content/Paks/
  PesMobile-LamineYamal-Android_ETC1_P.pak
```

The third hardware candidate narrows the face import further after the second
run proved the native hair path is correct. It exports only the principal
`mesh_1` skin surface (1,788 vertices / 3,479 triangles); the smaller
`mesh_0` surface, then suspected of producing the visible collar ring, is omitted.
The later V8 audit establishes that this section contains necessary neck and
lower-eyelid/socket geometry, not merely a disposable shell.
The UE project also recreates the face material instance from a native-path
`M_RealFaceBase` placeholder and assigns a single `face_162114` skeletal slot.
The placeholder is excluded from the detached PAK; the shipped material
instance remains the locally renamed native donor instance.

The fourth candidate replaces the renamed donor with an explicitly cooked
`face_162114` instance matching the mesh reference. The earlier explanation
that the donor export was named simply `face` was incorrect: UE serializes
an FName's numeric suffix separately, and the parsed donor export is actually
`face_133157`. Replacing ASCII package paths alone does not update that suffix.
V4's material loads on hardware, but the earlier green appearance should not
be attributed to the raw name-map string alone. Its parent remains the base-PAK
`/Game/Assets/character/BaseAssets/M_RealFaceBase`, which is not duplicated in
the detached PAK.

Hardware then confirmed that V4 resolves and samples the face texture, but the
visible surface was incomplete. V5 reverses polygon winding on the
principal face mesh only. This targets the Fox-to-glTF-to-FBX handedness
change so the native one-sided face shader renders the outward surface rather
than culling it. Hair geometry and its proven native material path are kept
byte-for-byte from V4.

V5 made the outward face surface visible and proved the remaining issue was
the Fox head set's forward axis plus omitted closure geometry. V6 restores the
small `mesh_0` skin section now that the native face material resolves, and
rotates both principal face sections and the proven hair section by 90 degrees
around the mobile `sk_head` bind-pose pivot. Rotating around the bone pivot,
rather than the model origin, preserves the head's attachment to the mobile
skeleton while aligning its forward direction.

The V6 hardware image established the sign of that correction: `+90` moved
the previously side-facing head to the player's rear. V7 therefore keeps the
same closure geometry, outward winding, materials, and head-bone pivot while
changing the face/hair rotation to `-90` degrees.

### V8 closure, eye geometry, and shading-normal audit

The V7 hardware test confirms forward alignment but shows hollow eyes,
transparent rear scalp, and green face/neck shading. The 2026-09-20 local
audit separates three issues:

- The rear scalp is the `fox_skin_mat` section in **hair_high**, not in
  face_high. Omitting all hair sections except `fox_hair_mat` removed this
  necessary skin surface (341 vertices / 572 triangles).
- Flipping polygon winding did not clear imported custom shading normals.
  In the V7 FBX, 369/369 neck-section triangles and 3,476/3,479 main-face
  triangles still had average shading normals opposed to their geometric
  normal. `--recompute-normals` now rebuilds the mesh from final winding,
  preserving UV loops, material slots, vertex groups and weights. A synthetic
  Blender regression checks those invariants and rejects shape-key loss.
- The source's eyelid/socket surfaces are not eyeballs. Rendering with both
  the cooked 128px face atlas and original 1024px diffuse still gives black
  sockets. The PC `common_package.fpk` supplies a separate `eye.fmdl` (386
  vertices / 736 triangles). V8 adds those generic PC eyes, rigidly bound to
  the existing mobile head bone, with their own opaque texture/material slot.
  These are shared eye assets, not an inherited donor-player face. The canary
  uses the default eye base atlas; PC iris-layer blending, gaze and facial
  animation are not reproduced yet.

V8 keeps the hardware-proven `-90` degree pivot correction and V7 hair packages
unchanged. Face/neck/scalp/eyes total 2,751 vertices and 5,156 triangles on the
same 29-bone rig. Its FBX round-trip has only one opposed-normal triangle
(a locally folded detail), instead of almost the entire skin surface.
The neutral-light local preview shows closed rear scalp and visible eyes.
The remaining welded skin boundaries are the mouth and lower torso attachment,
not rear-head holes. These previews are **not Switch rendering validation**.

Green shading is not baked into the decoded face diffuse. Rebuilt normals
address a proven defect, but the native face shader also references a shared
mobile normal atlas that does not necessarily match PC UVs. Hardware must
confirm the remaining tint before changing that shader. Do not override the
global shared normal texture to fix one player.

The V8 detached patch adds `162114_eye_tablet` (uasset/uexp/ubulk) and
`eye_162114` (uasset/uexp), for 18 entries including its correctly versioned
marker. Both skin and eye instances resolve the original base-PAK
`M_RealFaceBase`; no generated skeleton or placeholder base shader is shipped.
The PAK integrity test and local regression tests do not establish hardware
compatibility or visual completion.

The active detached V8 PAK is 542,812 bytes, SHA-256
`b23d9c629f23e6af4edfb89c1cae47006668e6f96e513ebc9bf84772b4243cb2`.
Cook completes with zero errors/warnings; the import step reports FBX bind-pose
recreation and missing smoothing-group warnings, retaining 29 bones and
explicitly imported rebuilt normals. The clean import uses three material
slots (two skin, one eye), avoiding reimport's stale material-slot accumulation.
Five focused tests pass, including the optional generated-geometry Blender
test. V7 remains available locally for rollback; no NRO rebuild is needed.

The reproducible ignored project and source PAK are under
`local-debug/lamine-yamal-face-canary/ue-project/` and
`local-debug/lamine-yamal-face-canary/pak-canary/`. They must never be
committed or redistributed.

## UE4.22.3 canary checkpoint

The Lamine canary resumed on 2026-09-19 with Unreal Engine 4.22.3 installed at
`D:/UE_4.22`. Do not repeat the FMDL extraction or skeleton audit. The
validated ignored inputs are under
`local-debug/lamine-yamal-face-canary/`, including these UE-oriented FBXs:

- `ue-import/lamine_yamal_face.fbx`;
- `ue-import/lamine_yamal_hair.fbx`; and
- `ue-import/lamine_yamal_oral.fbx`.

`D:/UE_4.22/Engine/Build/Build.version` reports `4.22.3`. Asset-only Android
ETC1 cooking works with the installed editor target platform; it does not need
to compile a native APK. Full Android application packaging would still need
the historical 4.21--4.24 NDK r14b toolchain.

The audited mobile texture contract is now exact:

| Asset | Cooked format | Size | Mips |
|---|---|---:|---:|
| `162114_face_tablet` | `PF_ETC1` | 128 x 128 | 8 |
| `162114_hair_parts_color_tablet` | `PF_B8G8R8A8` | 128 x 128 | 8 |

The disposable ignored UE project is named `PesMobile` and preserves the
original package namespace. It imports against a 29-bone skeleton package at
`/Game/Assets/character/BaseAssets/test_body_Skeleton` and places the player
assets under `/Game/Assets/character/RealFace/`. A locally recreated skeleton
may be used to establish the import binding, but its cooked package must not be
shipped in the canary: the runtime must resolve the original base-PAK skeleton.
The canary correctly omits the recreated skeleton. Skeleton GUID/retarget
compatibility and the approximate material contract remain hardware-test
risks.

Cook for Android ETC1 with unversioned packages and produce the exact native
identity set:

```text
PesMobile/Content/Assets/character/RealFace/162114_face.uasset
PesMobile/Content/Assets/character/RealFace/162114_face.uexp
PesMobile/Content/Assets/character/RealFace/162114_hair.uasset
PesMobile/Content/Assets/character/RealFace/162114_hair.uexp
PesMobile/Content/Assets/character/RealFace/162114_face_tablet.uasset
PesMobile/Content/Assets/character/RealFace/162114_face_tablet.uexp
PesMobile/Content/Assets/character/RealFace/162114_face_tablet.ubulk
PesMobile/Content/Assets/character/RealFace/162114_hair_parts_color_tablet.uasset
PesMobile/Content/Assets/character/RealFace/162114_hair_parts_color_tablet.uexp
PesMobile/Content/Assets/character/RealFace/162114_hair_parts_color_tablet.ubulk
PesMobile/Content/Assets/character/RealFace/face_162114.uasset
PesMobile/Content/Assets/character/RealFace/face_162114.uexp
```

Do not replace the base PAK. Validate the detached canary through boot,
gameplay, replay, close-up framing, animation, lighting, hair alpha, mouth
placement, and generic-face fallback before changing the registry's
`face_owner_id` or promoting the candidate.

## Scope guard

### V10 eye fit and neck attachment canary (2026-09-20)

Hardware feedback on V8 showed protruding eyes and a neck/collar mismatch.
The V9 single-eye candidate was not promoted; V10 supersedes that experiment.
Both generic eye islands are scaled to 0.94 around their individual centres,
recessed 0.45 cm and raised 0.25 cm in the established export frame. Local
front and oblique previews show the lower-lid leak closed. These previews
use neutral lighting, not the native skin shader; iris colour and the green
lighting tint are not claimed fixed.

An audit of serialized mesh reference poses found different bone bases in
the native donor and converted cooked mesh despite matching bone names.
The rigid -90-degree geometry rotation approximately compensates head-only
vertices, but not vertices influenced by neck/chest/shoulder bones.
The exporter now supports an explicit audited `--runtime-bind-reference`
pair. It solves the inverse of the weighted native/cooked skin transform
per vertex, preserving the desired native rest position. `--runtime-mirror-x`
preserves V8's established runtime left/right convention so the unchanged
hair remains aligned. This is a rest-pose compensation, not a proven full
animation retarget: collar fit during turning, running and celebrations
still requires hardware verification.

Validation: seven focused tests pass, FBX topology/UV/skin weights are
unchanged, reconstructed non-eye rest positions agree within 0.001 cm,
and all 29 cooked reference-bone transforms match the audited V8 contract
exactly. UE import recreates its bind pose with warnings; the subsequent
Android ETC1 cook completes with zero errors/warnings. The detached PAK
passes all 18 integrity checks. Only the two face mesh asset files change;
hair, textures, material instances and shared skeleton packages do not.

Local V10 PAK: 543267 bytes, SHA-256
`438d7725ffa20f5be2c2f8d32221d1b9613b10a6b293eddfee5c0f11e8b0d598`.
It remains experimental until the user verifies eyes, collar and animation
on Switch. No NRO or base PAK replacement is needed.

### V11 collar and eye material canary (2026-09-20)

V10 hardware images show olive-coloured chest skin outside the shirt collar
and unnatural eyes. A source-mesh audit places that chest flare in the
236-vertex lower-neck mesh, sharing its section with the eye sockets. V11
insets only vertices below 161 cm; the effect ramps to a 0.52 horizontal
scale at 154 cm and below, around the neck axis. The eyelid and main face
mesh positions, UVs and weights remain as before.

The V10 eye material instance inherited the native face base material, which
also uses face-specific normal shading. V11 instead cooks a local opaque,
skeletal-mesh eye material whose base colour samples the already included eye
texture directly. Hair, face texture, eye texture and shared base packages
remain byte-identical. This material change targets the eye tint/shading; it
does not recreate native iris-layer blending or gaze animation.

The detached V11 patch is 739747 bytes, SHA-256
`bc9b26556770a613d21c07462f63890747ca90a6cb5f20c408bf7b59bbc339ba`.
The UE Android ETC1 cook completed without errors/warnings and the 18-entry
PAK passed integrity checking. Only the face mesh pair and eye material pair
differ from V10. Shirt overlap, eye appearance and facial motion still need
Switch validation.

### V13 untucked neck and local skin material canary (2026-09-20)

Switch photos reject V11's lower-neck inset: it leaves a visible opening below
the head. An earlier V12 FBX already contained the untucked V10 neck, but its
UE import script failed because it tried to set an instance-only `parent`
property on V11's concrete eye material. The corrected import recreates only
the face mesh from that FBX, retains the V11 eye material, and does not edit
hair or the common skeleton. The V10 chest overlap may reappear; the collar
is **not** declared visually fixed before another Switch test.

The same photos show Yamal's face markedly greener than the nearby native
players even at Night. The Day pitch shader/roof patch cannot directly explain
that: its fingerprint allowlist excludes Night and non-pitch materials. The
known PC-face/mobile-normal-atlas mismatch is a more local explanation, so
V13 assigns the two skin slots a cooked diffuse-only material referencing the
existing face texture. It does not change global lighting, shared face-normal
assets, grass, the accepted pitch PAK, or the V11 eye material. This is an
isolating hardware experiment, not proof of the colour cause; the eyes still
need inspection under actual animation and lighting.

V13 Android ETC1 cook completed with zero errors/warnings. The detached PAK
passed UnrealPak's 20-file integrity test; only the face mesh pair and the new
local skin-material pair differ from V11. Candidate SHA-256:
`d361bfa1b9d6d259e400d21bfbea1e0873c06992fc2a73490c7e9720d918b287`
(938021 bytes). V11 remains the local rollback; this V13 candidate is not
Switch-validated.

Any future canary must use ignored `local-inputs/` and `local-debug/` paths.
FPK, FPKD, FMDL, FTEX, cooked face packages, extracted trees, and generated
PAKs are proprietary local inputs/artifacts and must never be committed.

### V14 native texture route and vertical chest adjustment (2026-09-20)

Hardware feedback on V13 reports improved attachment but flat dark/green skin
and a small exposed chest patch. V13's custom skin shader is rejected. V14
restores the original `face_162114` material reference and the exact V11 skin
texture/material bytes. This restores the previously working texture route;
it does not establish that the remaining green tint is solved.

`--lower-chest-cm 1.2` lowers the 236-vertex mesh's chest attachment with a
smooth height falloff: 159 vertices below 161 cm are affected, reaching the
full 1.2 cm at 154 cm and below. It preserves horizontal coordinates, UVs,
weights, upper neck, main face, scalp and eye positions. This is a candidate
collar adjustment, not a demonstrated correction to the player's posture.
It replaces V11's rejected circumference reduction.

Eight focused exporter tests pass with Blender enabled, including a generated
mesh check for unchanged circumference, upper neck, UVs and skin weights.
UE import retains the known bind-pose recreation/smoothing warnings; ETC1
cook finishes with zero errors/warnings. All 18 PAK entries pass integrity
checking. Only the face mesh pair differs from V11, and no V13 custom skin
material or shared skeleton is packaged. Candidate: 739740 bytes, SHA-256
`31bb99dc98951c48d9fb4534fcecf2ba7dbf143c920b4fad7993ce04c50800ea`.
Switch checks remain texture appearance and collar overlap during animation.
No NRO rebuild is necessary for this asset-only change.

### V15 coherent forward tilt after V14 seam regression (2026-09-20)

Hardware feedback rejects V14: the isolated lower-chest displacement opens
visible throat/rear-neck seams while chest clipping remains. The user prefers
V13 geometry with a slight forward head angle. V15 starts from the untucked
V12 FBX (the geometry used by V13), discards the V14 chest displacement, and
applies a four-degree forward nod about the native neck pivot to every face,
eye, scalp, neck and hair vertex. Each vertex is transformed into native rest
space using its weighted bind transform, rotated, then transformed back. This
keeps the rotation coherent across independently skinned sections. Existing
custom normals receive the corresponding inverse-transpose transform; UVs
and skin weights are preserved. It changes the asset rest shape, not the
native animation or body posture.

The local rig/geometry audit checks native-space transform error below
0.001 cm and unchanged UV/weight values. Cooked face and hair retain 29 bones;
reference transform components differ by at most 0.000538 after FBX roundtrip.
ETC1 cook reports zero errors/warnings; all 18 PAK entries pass integrity
checking. Only face/hair mesh pairs change from V11. Native skin, eye and hair
material references and every texture are retained, so V13's custom skin
shader is absent. The pre-existing green tint is not claimed fixed.

Candidate: 740371 bytes, SHA-256
`9bc31bccf59573e4367c85c1ae8ca6da23f881362e01cf97b07807938df8e4db`.
Switch validation is still required for seams and collar clipping through
running, head turns and celebration. Replace the detached face PAK only.

### V16 original-mesh comparison and native eye shader (2026-09-20)

The V15 hardware photo still shows lateral collar penetration and white eyes.
Comparison now uses the original `133157_face` position buffer (688 vertices),
not only its reference skeleton. Both meshes are compared in native rest
coordinates. The native lateral neck band at z=156..159 cm spans about
12.1 cm in X; the converted attachment spans about 14.4 cm in that band.
This motivates a local collar fit, not a whole-face rescale or identity swap.

V16 fits vertices below z=158 cm toward three nearby original lower-neck
surface samples. Displacement is capped at 1 cm and smoothly fades to zero
between z=155 and 158. The same spatial mapping is used across skin sections,
preserving UVs/weights; 133 attachment vertices and 48 lower-face vertices
are affected. The V15 nod, upper face, eyes, scalp and hair positions remain.
This sample-based fit is experimental; it is not a reconstructed native-body
surface or proof of clipping-free animated attachment.

The native original uses its face material for the whole mesh, including eyes.
The PC eye diffuse contains pupils, with mapped pupil vertices near UV (0.5,
0.5). V15 instead used V11's independently cooked eye shader. V16 replaces
that route with `eye_native_162114`, an instance of the runtime's native
`M_RealFaceBase`, explicitly binding `162114_eye_tablet` as `Base Texture`.
Serialized parent, texture parameter and mesh material class are verified.
Whether this fixes the white-eye hardware appearance remains to be tested.

ETC1 cook succeeds without errors/warnings; 20 PAK entries pass integrity.
UVs and weights survive the fit, and the 29-bone contract is checked with
quaternion sign equivalence (maximum remaining component difference 0.001099
after FBX roundtrips). All V15 textures, hair and other materials are unchanged.
Candidate: 741804 bytes, SHA-256
`b3b50b0f08bbf4ca4951aab74bd7346cfc50058b7a89d26b7cba8419aa5cc2b4`.
Replace the detached face PAK only; NRO does not change.

### V17 small shoulder fit and player-local body skin (2026-09-20)

Hardware feedback accepts V16's upper head but shows slight lateral collar
penetration and a lighter body than the converted face. V17 starts from that
accepted FBX. It adjusts only the lateral lower collar, smoothly bounded to
151..159 cm and outside the central 4 cm half-width. The original `133157`
surface remains the reference; horizontal inward displacement is capped at
0.45 cm. There is no vertical displacement or whole-neck circumference
reduction. The spatial rule is shared across mesh sections. Upper custom
normals are retained instead of being globally recomputed by the collar fit.

The FBX round-trip audit preserves topology, UVs and weights exactly, with
upper position drift below 0.000016 cm and upper corner-normal vector error
below 0.000704. Eyes have no deliberate geometry change. Hair, eye/face
textures and all material packages are byte-identical to V16. The 29-bone
contract remains within 0.001553 in transform components after round-tripping.

The native body loader selects the separate `Uniform16/D/skin1..skin6` texture
set. The native appearance/configuration path and local schema audit locate
its three-bit selector at byte 37, bits 0..2, in the 60-byte appearance row.
Yamal's current migrated row selects 1. V17 experimentally selects 4, a darker
native body texture, without replacing shared textures, changing lighting,
copying another player's identity, or altering physique/face fields. Exact
visual colour matching remains a hardware check, not a measured guarantee.

`tools/patch_player_skin.py` requires BaseId, the persistent registry identity
fingerprint, and the expected existing row SHA-256. It changes only those
three bits and refuses ambiguous owners, missing/duplicate rows, invalid skin
indices and existing output files. Both raw and WESYS-wrapped tables are
supported. This is an explicit experimental post-build override; rebuilding
the canonical migration alone does not automatically reapply it.

The local V17 dt200 is based on `full-mobile-kit-migration-v1`. All 2,795 CPK
members are compared: only `PlayerAppearance.bin` differs, and its decoded
12,653-row table differs at exactly one byte in native ID/BaseId 162114's row.
The full loose package is hash-verified before generating a partial update
manifest. Its build ID stays `1852ec648d2ebd75`: roster identity, dependent
tables and compiled migration mapping do not change. The existing latest
full-loose NRO is retained, not rebuilt with the older/default build mode.

ETC1 cook completes without errors/warnings, the PAK passes all 20 integrity
checks, and 28 focused skin-override/migration/loose-CPK tests pass. Local
candidate hashes:

- Face PAK, 741745 bytes:
  `993a6e807369727ac53459be8b543fd114293fb607957963b5004f3712b081b2`
- dt200, 10493952 bytes:
  `effd153dcadf2e187432444531f5c5edc18334530b4eb729918c7c71d52ccaa4`

Install the three files under the ignored `pak-canary-v17/update/` directory:
the detached face PAK, `LooseCpk/dt200_mobile_all.cpk`, then
`LooseCpk/manifest.txt` last. Close the game first and retain rollback copies.
If present, discard only the generated `LooseCpk/verified-v2.txt` cache;
do not delete SaveData. Keep the current NRO, every other CPK and the 53248-byte
dummy OBB. Do not copy the legacy large OBB from `dist`. V16's PAK and the
unmodified full-mobile-kit dt200/manifest remain the local rollback. This
candidate still requires Switch verification during running and celebrations.

### V18 tiny anterior chest inset (2026-09-20)

V17 hardware feedback reports improved attachment with only tiny upper-chest
skin specks showing through the shirt near the collar. V18 retains V17 and
adds a smoothly masked anterior/lateral inset: at most 0.30 cm rearward and
0.15 cm inward (0.33542 cm combined). The mask is limited to z=150..159 cm,
outside the central 3.5 cm half-width and in front of y=4 cm in native rest
space. It moves 44 attachment vertices and five lower face-edge vertices.
There is no vertical movement, new head tilt, central throat narrowing or
rear-neck displacement. The latter boundaries are explicitly audited.

FBX round-trip retains topology, UVs and weights, with upper position drift
below 0.000016 cm and upper normal-vector error below 0.000153. The cooked
29-bone hierarchy and reference transforms pass (maximum component drift
0.001400). Every V17 staged asset except the face mesh pair is byte-identical,
including the hair, textures and native eye material. V17's skin4 database
override is retained; dt200, manifest, NRO and lighting are not modified.

Eight focused exporter tests pass with Blender enabled. UE import completes
with the known FBX warnings; Android ETC1 cook completes with zero errors or
warnings. All 20 PAK entries pass integrity verification. Candidate size is
741748 bytes, SHA-256
`480c1f5e3bccb252947ff61b6f671710837875e1cf9e414e6b5b248e66623c07`.
The ignored `pak-canary-v18/update/` contains only the detached face PAK.
Replace that one PAK with the game closed; keep V17's dt200 and manifest.
V17's PAK remains the rollback. Animated clipping still needs hardware testing.

### Accepted checkpoint: Yamal V18 + V17 skin4 (2026-09-20)

The user accepts V18 as the working checkpoint. This supersedes the pending
acceptance status above, but does not mean defect-free: slight upper-chest
clipping remains and is explicitly tolerated. Preserve the current upper
head, eyes, hair and body-colour result as the baseline for further work.
This is acceptance of the demonstrated hardware result, not exhaustive testing
of every kit, animation, camera or lighting configuration.

The local, ignored `local-checkpoints/face-yamal-v18/` is an asset-only
checkpoint, not another complete runtime. It preserves the V18 PAK, V17 skin4
dt200/manifest, final face/hair FBXs, local recipe scripts and validation
reports with SHA-256 hashes. No APK, OBB, library, save or full runtime is
duplicated. The required full-loose build ID remains `1852ec648d2ebd75`.
Public commits contain project-authored code/tests and this audit only;
proprietary models, textures and binary packages remain ignored and local.
The experimental `--lower-chest-cm` option is retained for audit/reproduction
of the rejected V14 experiment; it is **not** the accepted V18 recipe.

#### Batch automation feasibility (proposal, not implemented)

The demonstrated extraction, retarget, FBX import, ETC1 cook, PAK creation and
integrity checks can be orchestrated as a resumable batch pipeline. However,
Yamal-specific mesh counts, collar coordinates, eye adjustments and skin4
must not become unconditional defaults for every player.

Before scaling, resolve each source face to canonical BaseId plus fingerprint
and the persistent NativePES21Id; distinguish missing assets from mismatches.
Keep native faces by default, convert only explicitly selected valid sources,
and leave missing/failed cases unchanged or use the explicit generic fallback.
Use one identity across club and national appearances, not duplicate models.

Generalization requires semantic mesh/material classification, native-reference
collar fitting, per-player eye placement and body-tone policy, topology/rig/UV
checks, and a review queue for outliers. Hair alpha, missing components,
facial animation and LOD/performance differences remain unresolved batch risks.
No claim is made that the static face route recreates native facial animation.
Build/cache by source hash, converter version and per-player profile; support
resume and publish only validated batches, with no global material overrides.

A useful next validation is 5--10 deliberately varied players (different head
proportions, hair and skin tones), then a team, then larger batches. Measure
Switch loading, memory, frame time and package size before a full roster.
Automation can cover all *eligible available source faces*, not fabricate
missing licensed assets or guarantee zero clipping without visual checks.

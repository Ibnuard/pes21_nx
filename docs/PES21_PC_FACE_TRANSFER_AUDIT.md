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
converter, but no verified compatible UE4 face cooker. Therefore the status is
**model conversion proven, runtime cooking not production-ready**. The safe
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

Any future canary must use ignored `local-inputs/` and `local-debug/` paths.
FPK, FPKD, FMDL, FTEX, cooked face packages, extracted trees, and generated
PAKs are proprietary local inputs/artifacts and must never be committed.

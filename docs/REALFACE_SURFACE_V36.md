# Realface v36: isolate the converted face's normal map

The user reports that the v35 Barcelona/Manchester United candidate runs at
60 FPS but shows wrinkles from the left cheek into the neck across players.
They explicitly chose to retain the **2,000-triangle maximum per complete
head**, keeping the face smooth and simplifying the hair. This fix preserves
v35's geometry rather than rerunning reduction or increasing that budget.

## Evidence and diagnosis

The v35 head combines skin and eyes in a 128x128 diffuse atlas. Skin UV0 is
mapped into pixels `(2,2)..(94,126)`, with the eye tile in a separate region.
Its `face_<NativeId>` material instance overrides `Base Texture` but inherits
`M_RealFaceBase`'s fixed `common_face_normal_tablet` texture.

Format-aware parsing of the locally supplied native UE4.22 material shows a
fixed normal TextureSample and a separate diffuse TextureSampleParameter2D.
Twelve of 96 distinct extracted GLES pixel shader variants directly sample
both textures using the same UV0. This count identifies a specific source
layout, not every variant that can use a normal map. The 256x256 ETC1 common
normal texture contains anatomical eye, nose, cheek, mouth and ear features.
Those features no longer align after the new UV packing.

A diagnostic Raphinha render with the decoded native normal atlas reproduces
strong wrinkles at the cheek and lower jaw. Using neutral normals removes
them with identical geometry, view and lighting. This is an offline Blender
reproduction of the UV/normal interaction, not a complete emulation of the
game renderer or a new Switch capture. It strongly supports the normal-atlas
diagnosis; final appearance and frame pacing still need device validation.
Earlier v35 previews did not sample the runtime normal atlas, which explains
why the problem was absent from those previews.

The native shader export is pinned by SHA-256:
`c5e676782db7180949e6f80485bbb0d135ea5601176cf5756fd3315cfbb8ecbe`.
Raw extracted shaders, material JSON, textures, and payloads remain ignored.
REA's format catalog did not advertise UE packages; the audit reused the
existing local UAssetAPI and cooked-texture parsers. No native runtime trace
or GPU measurement is claimed.

## Material change and performance scope

`tools/realface_surface_patch.py` clones the audited cooked native parent as
`M_NXFaceSmooth`. Only approved equal-length package/name entries and their
valid FName hashes change. The entire parent export, including compiled
shader bytecode, is copied verbatim. UAssetGUI is used once to obtain validated
name-entry bytes; those entries are reused for all instances without
reserializing their exports.

The private parent references `pesnx0_face_normal_tablet`, a clone of the
native texture layout filled with a constant normal in every mip. It remains
256x256 ETC1 with nine mips and unchanged bulk sizes, flags, metadata and
trailers. The encoder's decoded RG is `(127,127)`, a uniform 0.318-degree
tilt from an exact neutral tangent-space normal. This is below the one-degree
gate and cannot create spatial wrinkles. The original normal texture and
original shared material are never overridden.

The source mesh/UV/weights, skin and hair color textures, hair material and
number of sections are unchanged. Lighting and roof/player shadows still use
the existing shader and smooth mesh normals. Fine anatomical normal-map
detail is deliberately omitted on the converted face; diffuse detail and
geometry remain. No new shader work, per-frame conversion or extra draw
section is introduced. The patch adds one private parent resource and one
shared normal texture; it does not claim measured equality of GPU time.

## Reproduce without a new cook

The post-process requires a verified `realface_mobile.py` release, its
identity verification rows and the current BaseId/NativeId/fingerprint state.
Set these fields in an ignored local configuration:

```json
{
  "work_dir": "<repo>/local-debug/realface-surface-v36/patch",
  "source_pak": "<verified-release>/update/PesMobile/Content/Paks/<source>.pak",
  "source_verification": "<verified-release>/VERIFICATION.json",
  "source_identity_report": "<mobile-work>/verify-report.json",
  "identity_state": "<local-identity-state.json>",
  "main_pak": "<legally-obtained-base-runtime.pak>",
  "main_pak_sha256": "<pinned-runtime-sha256>",
  "unrealpak": "<UE4.22>/Engine/Binaries/Win64/UnrealPak.exe",
  "repak": "<local-tools>/repak.exe",
  "uassetgui": "<local-tools>/UAssetGUI.exe",
  "etc1tool": "<Android-SDK>/platform-tools/etc1tool.exe",
  "release_label": "v36",
  "package_scope": "Barca-MU"
}
```

```powershell
python tools/realface_surface_patch.py --config <local-config.json>
python -m pytest tests/test_realface_surface_patch.py -q
```

This is the required surface post-process for the merged skin/eye atlas
recipe. Future roster batches can use their own verified source release and
package scope. It performs no paid API/model requests, Blender reduction or
UE cooking. Pinned inputs/tool revisions determine the cache key; an unchanged
complete release is hash-checked and reused. Interrupted attempts are retained
for diagnosis and retried in a fresh directory. `latest.json` points to the
checked release. The active runtime and SD are never modified.

The build rejects changed source bytes, stale identity fingerprints, duplicate
slot owners, heads above 2,000 triangles, extra sections, unexpected shared
assets, wrong native material revisions, or normals that vary spatially. Every
per-player export, mesh and diffuse/hair texture is compared with the verified
source. UnrealPak integrity, independent repak extraction/hash equality and
ZIP CRC/embedded-PAK hash checks are required before a completion stamp is
written. CSV/JSON lists all included players and source identities still
outside the candidate.

## Host result — 14 October 2026

All 51 source heads were packaged successfully. Their complete-head triangle
range remains 1,929 / 1,984 median / 1,995 maximum, totaling 100,948. Each head
still has two sections. Of the original 612 per-player files, 561 are
byte-identical: 204 mesh files, 306 color-texture files and 51 material-instance
exports. The other 51 files are instance headers with the approved parent
name/path changes. Five private parent/normal files bring the package to 617
files. No global native face asset is overridden.

UnrealPak reports all 617 files healthy. Independent repak extraction matches
every staged asset hash, and the release ZIP passed CRC and embedded-PAK
hash checks. The normal texture is spatially constant across all nine mips.
Offline renders of Raphinha and Bruno using this decoded packaged texture
remove the native-atlas wrinkles while preserving the original head meshes.
Fourteen surface tests and 28 existing material/atlas/cook/mobile regressions
passed, including the available native shader fixture and Blender tests.

- PAK: `PesMobile-Barca-MU-Faces-Mobile-v36-Android_ETC1_P.pak`, 4,850,560 bytes.
- PAK SHA-256: `0be6ca3ee8fc909385b0e7b31aadade4873705d5d67837e067d0ba6b19c9e376`.
- ZIP: `FootballNX-Mobile-v36-Barca-MU.zip`, 4,849,583 bytes.
- ZIP SHA-256: `e64d14a46244bb2c88490c710ad5c4f6dcfa3a5da7173c7c11dc8849ce8bdaaa`.

The accompanying status files list 51 included players and the same eight
roster identities without verified face sources. This remains a Barcelona/MU
candidate, not an updated release for all 897 previously covered identities.
No NRO, CPK or active installation changed.

## Device comparison

Replace the v35 PAK with v36; keep older realface PAKs outside mounted Paks
directories. Preserve the existing NRO, roster/physique/skin CPK and stadium
assets. Compare Barcelona versus Manchester United with the same starting XI,
quality, stadium and camera, in DAY and NIGHT. Check play near the lower
touchline, plus left cheek, eye, jaw and neck during replay/celebration.
Restoring the source PAK is the rollback. v35's reported 60 FPS must not be
presented as measured v36 performance.

The subsequent user test reports partial improvement, with severe mouth
distortion still visible on Anthony Gordon. The [v37 refinement](REALFACE_REFINEMENT_V37.md)
keeps this material correction and addresses that separate geometry/UV issue
and the requested compact hairstyles.

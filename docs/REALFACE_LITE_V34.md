# Realface Lite and stadium surface repair — v34

This candidate follows the device A/B result: removing the realface patch
removed the near-camera slowdown, including in Konami Stadium and at night.
It reduces the assets offline; it adds no per-frame face, referee, or camera
work. Switch frame pacing and close-up appearance still require a device test.

Device follow-up: the user tested only Lite v34 with Barcelona versus
Manchester United and still observed stutter; removing the face package was
smooth. v34 has not met the performance target. See
[the focused render-cost audit](REALFACE_RENDER_FOLLOWUP_V35.md).

## Identity and coverage

The input is the verified v24 combined PAK: 897 EPL/La Liga player identities,
including the 20 previously covered Barcelona players. This is optimization
of the existing coverage. It does not add faces for the other 225 target
players whose source identity/asset was not verified.

The factory checks BaseId, pinned native storage ID, and fingerprint against
the roster and accepted release. Each source FBX, rig, texture dependency and
compiler recipe is hashed. Unrelated donor faces cannot enter through a
reused numeric ID. Proprietary inputs, intermediate exports and PAK/CPK
outputs remain in ignored local directories.

## Offline reduction

`tools/realface_lite.py` uses a locally installed meshoptimizer 1.1.1 package
and Blender. There is no paid API or model call per player. A prepared/cooked
cache and explicit held statuses make the pipeline resumable. Changing an
input, simplifier, budget or validator invalidates the relevant cache.

Most heads target 2,500 triangles. Adaptive allocations permit 4,500, 6,500,
or at most 10,000 where the smaller candidate cannot retain the face/hair
surface. One alternative allocation gives complex skin more of that same
total budget. These are asset budgets, not measured hardware limits.

Reduction runs in the native rest pose, not the distorted fitted FBX bind
space. Surviving vertices retain their original UVs and bone weights. It
preserves the 29-bone rig, eye material, fitted lower neck, and same-atlas
material roles. Duplicate triangles are removed before FBX export so UE and
Blender cannot disagree about the index count. It does not substitute a
different player's low-detail face.

Quality gates compare source and reduced surfaces, including face-centre
samples, reverse distance, neck attachment and bounds. Point-size source
markers are excluded from visible-surface measurements only when each edge
is below 0.3 mm and area is at most 0.0001 cm²; long thin hair cards remain
measured. Separate hair islands below 2.5 mm in extent are locked to prevent
collapses from turning markers into a false surface. No skin, neck, or visible
hair error limit is relaxed to admit a failed player.

UE imports are bounded to 32 Lite players per editor lifetime. Texture cook
can run serially to avoid the known legacy Qonvert initialization race. An
independent UAssetGUI/UE Viewer/Blender pass checks the actual cooked meshes,
rig, UVs, weights, sections and triangle counts. Packaging requires all 897
accepted identities to pass; a held or incomplete batch cannot be packaged.

All 897 cooked player meshes pass the independent geometry checks. Against
the original accepted PAK inventory:

| Complete head (face + hair) | Original PAK | Lite |
| --- | ---: | ---: |
| Minimum triangles | 4,936 | 1,481 |
| Median triangles | 9,778 | 2,444 |
| Maximum triangles | 84,166 | 9,584 |
| Total triangles, 897 players | 10,323,241 | 2,472,341 |

The aggregate triangle reduction is **76.05%**. These are independently
checked asset counts, not measured FPS or frame-time gains. The 68 focused
face, identity, import-cache, skin, stadium, atlas and apron tests pass.

The final PAK replaces only four mesh files per player. All accepted texture
and material bytes remain unchanged, and new mesh dependencies must be a
subset of the accepted dependencies. UnrealPak integrity and an independent
repak unpack/hash roundtrip check the package. This first Lite version still
has one LOD, including replay close-ups; setting the game to Standard alone
would not reduce the original single-LOD heads.

The verified Lite PAK is 145,456,376 bytes (original: 292,274,960 bytes).
It replaces 3,588 mesh files and preserves the other 11,641 accepted assets
byte-for-byte. All 15,229 output members match an independent unpack. Its
SHA-256 is `8de00f55ad7a6b9f8e99281e4505feacf2f71cd7b4b9e8c3595a696d7021a665`.

## Stadium stairs

Global decimation could delete textured stair treads/risers while their
textures still existed. The repair rebuilds from the original owned glTFs,
not the damaged reduced FBXs. It assigns stair/concrete surfaces a separate
budget before reducing facade/rail/roof detail. Fixed open borders are
preferred; dense disconnected stair boxes use bounded spatial clustering
when fixed borders cannot fit. Clustering uses original vertex/UV samples
but does not promise exact open-border preservation. Preview and cooked
geometry checks are therefore required.

Old Trafford additionally needs continuous backing beneath disconnected
steps. The v34 manifest explicitly names the two reviewed stair materials.
An offline union of their original upward footprints, preserving holes,
creates a coarse backing 35 cm beneath the sampled source heights. It uses
the same material/texture and is included in the existing triangle budget.
This avoids retaining tens of thousands of individual step boxes solely to
close the visible sky gaps. It is a visual LOD approximation, not collision
geometry or an exact reconstruction of each individual step.

The five additions retain a maximum of 24,560 total core triangles, the
measured Konami inventory, with the fitted animated audience unchanged.
Native-floor clipping, reviewed overlay clearance, atlas IDs, camera
cutaway and roof lighting remain part of the prepared profile. The accepted
Anfield asset and retired stadium selection are unchanged. Equal triangle
counts are not a guarantee of equal rendering cost.

The floor audit also caught shallow ramps whose far vertices lay above the
old whole-triangle height filter. Clipping now applies only to the portion
inside the native floor's height band; the elevated ramp remains. Reviewed
Camp Nou floor overlays and Old Trafford's 1.057 m platform overlay receive
3 cm of separation from their concrete base. A strict cooked-geometry audit
checks sampled native-floor and self-overlap after these changes.

## Cunha skin correction

The reviewed policy in `data/realface_skin_profiles_v34.json` changes only
Matheus Cunha's skin selector, from unsupported value 7 to native palette 3.
The face texture's sampled neck colour is closer to this palette. The six
available native body palettes cannot guarantee a perfect pixel match.

`tools/stage_skin_profile_update.py` checks identity, roster build and the
paired CPK manifest. The candidate changes one byte's skin-selector bits in
PlayerAppearance.bin; every other member of the 2,840-member CPK is compared.
Height, weight, physique and all other identity fields remain unchanged. The
candidate CPK and its matching manifest must be installed together.

## Reproducing locally

The config files contain private local paths and are intentionally ignored.
The Lite config extends the existing batch factory config with
`source_profiles`, `source_verification`, `source_pak`, `identity_state`,
`node`, `meshoptimizer`, `import_chunk_size: 32`, and
`serial_texture_cook: true`. Pin source profiles before a new run.
To compare actual old/new cooked geometry, also supply the matching
`source_audit`, `source_metrics_csv` and its `source_metrics_sha256`; source
FBX counts are recorded separately from the accepted PAK counts.

```powershell
python tools/realface_lite.py run --config <local-lite-config.json> --workers 2
python tools/repair_stadium_surfaces.py --config <local-stadium-config.json> `
  --work local-debug/<fresh-surface-candidate> `
  --keys EtihadStadium SignalIdunaPark StamfordBridge OldTrafford CampNou
python tools/cook_stadium_batch.py --config <local-stadium-config.json> `
  --work local-debug/<surface-candidate> `
  --keys EtihadStadium SignalIdunaPark StamfordBridge OldTrafford CampNou
python tools/audit_stadium_optimization.py --config <local-stadium-config.json> `
  --work local-debug/<surface-candidate> --output local-debug/<fresh-cooked-audit>
```

Do not reuse old atlas materials after changing the source surfaces. Local
release reports include `PLAYER-STATUS.csv`/JSON, per-player quality budgets,
package hashes, and independent cooked verification. Source and output
identities are kept separate from hardware acceptance.

Packaging verifies independent assets with four bounded I/O workers, checks
each copied mesh against its cooked hash, and hashes unchanged textures and
materials once before packing. It still checks every output against an
independent unpack; parallel I/O does not replace any integrity or identity
gate. Native storage IDs must also be unique to prevent overlapping writes.

For the Switch A/B test use the same NRO, teams, stadium, camera and quality.
Move previous combined/Barcelona/individual face PAKs outside the Paks folder
when installing the combined Lite replacement, so a later-mounted heavy
patch cannot override it. Test lower midfield and the near touchline in DAY
and NIGHT, then inspect eyes/hair/neck in close-ups and Cunha's face/body seam.
The existing v33 NRO already contains the preceding upload/camera fixes;
geometry and appearance data changes alone do not require a new NRO.

## Final cooked stadium verification

The final cooked shells, including the unchanged animated crowd, pass these
counts against Konami's 24,560-triangle core inventory:

| Stadium | Shell + crowd triangles | Crowd triangles | Material sections |
| --- | ---: | ---: | ---: |
| Camp Nou | 24,328 | 9,250 | 5 |
| Etihad Stadium | 24,268 | 8,036 | 7 |
| Old Trafford | 24,522 | 6,496 | 4 |
| Signal Iduna Park | 24,551 | 9,848 | 7 |
| Stamford Bridge | 24,454 | 8,090 | 6 |

All five packages pass independent unpack/byte comparison and UnrealPak
integrity checks. Cooked atlas IDs, crowd geometry, ETC1 texture encoding,
cutout masks and baked lighting pass the asset audit. The shader audit checks
29 materials and 48 compilations with no errors against the existing v33
runtime policy.

Each stadium passes 30,240 camera rays with no uncleared blocking fragment,
and eleven near/far views with no visible fragment incorrectly removed.
The apron audit samples 8,753 positions per stadium and finds no close
parallel overlap against the native floor or another custom floor. Some
angled surface contacts remain; this sampling is not proof that every
possible view is free of flicker. Hardware visual and frame-time acceptance
remains pending.

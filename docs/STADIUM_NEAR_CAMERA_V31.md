# Stadium near-camera performance candidate v31 — 2026-10-13

The device-tested v30 Camp Nou still loses frame rate when play moves toward
the lower middle of the broadcast view, in both DAY and NIGHT. Other retained
stadiums need the same audit. The user requested Konami's actual triangle
inventory as the geometry reference and a Camp Nou roof band entering roughly
35% of the pitch from the roof side.

This candidate reduces all five additions below the measured native core
budget, defers shell RGB sampling until after coverage rejection, and widens
Camp Nou's roof band. **Switch frame pacing remains unverified for v31.** The
available earlier device journal is v26 and cannot establish v30/v31 GPU cost.

## Native geometry reference and final cooked assets

The owned Konami LOD0 exports contain 13,015 triangles across eight stand
meshes, 3,579 across three roof meshes, and 7,966 across eight audience meshes:
**16,594 structural + 7,966 audience = 24,560 core triangles**. The project
stores counts and mesh identifiers in
[the native budget reference](../data/stadiums/konami_budget_reference.json),
without storing the proprietary geometry.

This is an asset inventory, not live submitted triangles. Alternate `Low`
meshes are not added to their full-resolution counterparts. Native pitch,
perimeter grass, and night-only decorative overlays are outside this core
comparison; the runtime retains its native pitch/perimeter. Native mesh
actors/sections can be culled independently, so equal totals do not establish
equal pixel cost or FPS. Counting only `st029_b` (1,568 triangles) would count
one stand segment, not the whole stadium.

The final UE-cooked mesh exports have these counts. The earlier totals use
the installed v28 additions and v30 Camp Nou, including their crowd.

| Stadium | Earlier total | v31 structure | Preserved audience | v31 total | Material sections |
| --- | ---: | ---: | ---: | ---: | ---: |
| Etihad Stadium | 43,026 | 16,513 | 8,036 | 24,549 | 7 |
| Signal Iduna Park | 44,829 | 14,698 | 9,848 | 24,546 | 10 |
| Stamford Bridge | 42,848 | 16,260 | 8,090 | 24,350 | 7 |
| Old Trafford | 41,424 | 18,044 | 6,496 | 24,540 | 4 |
| Camp Nou | 38,403 | 14,812 | 9,250 | 24,062 | 7 |

All five are below 24,560; crowd rows and their native 16-frame, 8 fps sprite
sheet remain intact. Camp Nou retains 4,625 fitted rows. These are real final
cooked counts, rather than pre-decimation targets.

The accepted Anfield v17 PAK was also exported for comparison: **102,437
triangles, 44 sections**. Its device-accepted PAK is retained. This much larger
but accepted mesh is further evidence that a triangle total alone cannot
explain the near-camera slowdown. San Siro and Santiago Bernabeu remain
retired from the selectable menu.

## Performance changes beyond mesh reduction

Inspection of the actual authored compiled materials found that the RGB
texture fetch preceded the existing camera/alpha discard. In the full native
crowd mask, 61.85% of source pixels are below the 0.4 alpha threshold. This
source-sheet fraction is not a screen-coverage or GPU-time measurement, but
it identifies potentially avoidable texture work on transparent crowd pixels.

[The scoped source transform](../source/stadium_shell_clip.h) moves only the
RGB fetch behind the existing discard. It computes the original gradients
before any discard, including explicit gradients for the previously implicit
crowd sample. Coverage, atlas wrapping, mask lookup, lighting and output math
are unchanged. The policy accepts six normalized FNV64 main-body fingerprints
from owned, project-authored ES 3.1 material shaders, covering v30 and v31.
Unknown/native bodies, ES2, vertex shaders and depth-only shaders pass through.
The hash registry is project compiler metadata, not game shader source.

This transform runs at shader-source submission. It adds no draw-time actor,
texture binding, light or draw call. A cheap camera-mask AABB rejection also
skips the slab divisions when a fragment cannot lie between the camera and the
protected field box. Near-zero ray directions retain the old safe-ray path;
50,000 randomized/reference comparisons include those edge cases.

An additional cone-based vertex cull was evaluated and rejected because the
sampled views did not show extra rejection over the existing conservative
cluster cull. The existing cluster policy is retained. The expanded overdraw
audit samples nine lower near-camera positions as well as the existing near
and far views. It checks geometric visibility, not transparent texels or GPU
time. No sampled visible geometry was removed.

## Roof coverage and goal-side floor repairs

Camp Nou's measured source roof still enables only its roof-side panel. At
uniform upload, its effective projection height is 26 m and the opening shifts
22 m toward the field. Winter adds 6.5 m of compensation to keep the requested
band similar across seasons. The Fine pitch-grid preview reports **35.60%
Summer and 35.34% Winter**, with 28,907 sample points each. It is a shader-math
preview, not an in-game capture.

Pitch and player lighting continue using the same seasonal light ray and roof
profile. The opening compensation is cached on profile/season changes; it adds
no new per-fragment roof branch or per-draw uniform upload. Host tests exercise
repeated draws and seasonal transitions. The native lighting GLSL remains
byte-identical to v28/v29/v30.

All additions retain native-floor decal omission and a -0.25 m imported floor
minimum. Exact reviewed opaque overlays in Camp Nou
(`M_st002_redc200_kt_bsm_solid_one`) and Etihad
(`M_cm074_conc001_bsm_solid_two`) receive 3 cm of physical separation from their
base. UVs, normals and non-floor walls remain intact. The final cooked apron
audit samples 8,753 positions per venue and reports zero near-parallel native
or imported floor overlaps within 1 cm. Sampling does not prove the absence
of every possible depth conflict between those positions.

Signal Iduna Park still lacks the locally unavailable `st051_sgbd009_bsm`
small sign texture documented in v27; its neutral fallback is preserved and
reported in package metadata. Originally untextured plain surfaces retain
their existing neutral atlas tiles. All other atlas source images and all
final material texture files must exist at packaging.

The batch optimizer now honors each manifest's triangle budget. Decimation
and floor clipping can remove extreme or unused vertices; output bounds are
recomputed from exported/referenced geometry. UE import still rejects an
actual bounds mismatch. Its validation tolerance was not relaxed.

## Verification and installation

- Focused host tests: 51 passed, 42 subtests passed.
- Final five cooked meshes: exact structure/audience/section counts, constant
  per-triangle atlas IDs, preserved cluster bounds where enabled, and ETC1
  textures. Crowd compression differs at the clip threshold on about 0.55% of
  source pixels, within the existing audit tolerance; this is unchanged.
- Camera clearance: 30,240 rays per venue, zero uncleared fragments/failures.
  Eleven geometric overdraw views per venue remove no sampled visible surface.
- Authored material baseline: 35 materials, 490 shader records, 192 unique
  ES2/ES3 vertex/fragment compilations across clip/HDR variants, no errors.
  Actual final scoped source transforms: 35 ES3 RGB records, three live body
  fingerprints, 48 original/transformed compilations, no errors.
- Native production NRO and embedded icon verified; versioned journal is
  `FootballNX scene v31 session`. Runtime identity remains `e861c583ec78e9ae`,
  with the accepted 53,248-byte patch OBB.
- Five PAK member roundtrips and independent UnrealPak integrity tests passed.
  Source public-tree validation is required before packaging/committing.
- Offline bowl/near previews inspect textures and decimation. Their authored
  reference plane excludes the retained native apron; an exposed strip in a
  preview is not evidence of a missing in-game native floor.

The local review ZIP contains the NRO **and all five newly cooked stadium
PAKs**. Copy the contents of its `update` folder into `SD:/switch/pes21_nx/`,
replacing the NRO and those five PAKs. Keep the accepted Anfield PAK and the
existing realface/physique installation. This update contains no OBB/CPK/save.

Compare the same teams in DAY and NIGHT while moving the ball between the
lower middle, near touchline, far side and both goals; also review corner
celebrations. Pause to flush the frame summary and confirm the v31 journal
header. Device timing and visual acceptance are the remaining checks; the
package's `VERIFICATION.json` records `hardware_tested: false`.

## Reproduction inputs and tools

The reviewed budget/profile manifest is
[fl26_selected_v31.json](../data/stadiums/fl26_selected_v31.json).
Owned FL26 meshes, texture sheets, UE 4.22, Blender, UModel, repak and the
accepted local runtime catalogs are optional ignored inputs. No input OBB is
duplicated. Preparation/cooking reuse the local conversion project.

- [Atlas preparation](../tools/stadium_atlas.py),
  [batch optimizer](../tools/optimize_stadium_batch.py),
  [shell optimizer](../tools/optimize_stadium_shell.py),
  [floor repair](../tools/repair_stadium_apron.py).
- [Cooked asset audit](../tools/audit_stadium_optimization.py),
  [apron audit](../tools/audit_stadium_apron.py),
  [camera audit](../tools/audit_stadium_camera.py),
  [expanded overdraw audit](../tools/audit_stadium_overdraw.py).
- [Compiled authored-shader transform audit](../tools/audit_stadium_shell_clip.py)
  exercises the actual C transformer, allowlist and original/transformed GLSL
  with clip/HDR variants. Its optional `--register` writes only normalized
  hashes to the authored-shader registry; always rebuild/retest the NRO after
  a registry change.

# Strict mobile real faces across the English and Spanish leagues

## Status: visual regression held (2026-10-15)

**v38 is an unreleased draft.** The user rejected the flattened hair volume and
loss of facial detail in the Areola comparison. Numerical geometry/cook passes
do not clear that rejection. `QUALITY-HOLD.json` in the local work directory
blocks assembly; the accepted v37 assets and active runtime remain unchanged.

The current preparation inventory contains **883 complete heads from 897
verified sources**: 832 new seam-safe candidates and 51 inherited accepted
heads. All are within the 2,000-triangle ceiling. Another 14 verified sources
remain held by geometry/appearance checks. The configured catalog contains
39 teams (19 English and 20 Spanish) and 1,122 unique roster identities;
Sunderland's native team-record addition remains pending in the existing
catalog. The other 225 identities still
lack a resolved, verified source. Preparation and cook counts are distinct.
All 883 matching current heads have now passed independent cooked-buffer
validation, without cook holds. Use the generated progress report rather
than an earlier draft's successful count. These are **not 883 visually
accepted or released heads**.

The initial 67-input recovery completed with 34 successes and 33 holds. The
subsequent seam batch covered 811 selected inputs; 810 passed immediately.
Lucas Bergvall passed a bounded allocation retry at 1,976 triangles, and three
late recovery successes were prepared separately before merging. A targeted
retry then recovered six more identities: Joelinton (1,990), Adrià Pedrosa
(2,000), Tommy Doyle (1,995), Álex Baena (1,987), Evan Ferguson (1,999), and
Ewen Jaouen (1,988). It retries the most promising measured allocations and
original eye globes where appropriate, retaining every existing quality gate.

The latest seam investigation found an additional reproducible facial defect:
Jon Guridi's reduced cheek and neck contained narrow slits even with a flat
grey material. Some seam copies differ by native bind-roundoff, so the index
simplifier treated them as separate boundaries. A deterministic neighbouring-
cell search now aliases equal-weight seam copies within **0.0002 cm** for the
simplifier only. Export still uses the original vertex positions, UVs and
weights. Simple decimal rounding was rejected because copies can straddle its
cell boundaries and produce a new slit near the nose. On the inspected sample,
101 vertices differed by at most 0.0000164 cm; the corrected complete head has
1,989 triangles. The ten-head preparation canary passed both the unchanged
geometry gates and cooked-buffer validation. The expanded batch applies this
policy to all 820 new prepared candidates; it does not approve the hair
appearance or publish a PAK.

Four further failures were caused by thousands of microscopic marker triangles
inside the skin. They consumed the simplifier's protected-vertex budget while
the visible face and neck still lost detail. The opt-in marker cleanup removes
only isolated clusters no wider than 0.06 cm, with identical nonempty weights,
whose triangles already satisfy the unchanged surface auditor's microscopic
exclusion. Before reduction, 13 views must have identical skin coverage and
depth within 0.00001 cm. Original positions, UVs, corner normals and exact bone
weights are retained. This recovered Andoni Gorosabel (1,987 triangles), Sergio
Camello (1,987), Aimar Oroz (1,999) and Kevin Schade (1,985), all cooked and
validated. Schade's hair still needs visual improvement; the recovery is a
technical result, not an appearance approval.

A geometry-only preselection found another 23 potential marker cases among
prepared heads. Only four actually met the full weight/cluster guard: Álvaro
García, José Sá, Vitaliy Mykolenko and Luíz Júnior. The other 19 retained their
source triangles. Across these eight heads, 13,900 source marker triangles were
removed before the ordinary reduction. All 27 freshly prepared keys passed
cooking and their hair audits were refreshed. An experimental approach that
added more protected vertices instead was rejected: it increased the topology
floor without recovering the required face/neck error limits.

A bounded source-alpha volume retry then recovered eight of the remaining
22 sources: Noni Madueke (1,994 triangles), Jeremie Frimpong (1,993), Dani
Cárdenas (1,994), Félix Correia (1,994), Enzo Boyomo (1,993), Federico Redondo
(1,994), Buba Sangaré (1,994), and Chrisantus Uche (1,993). Eberechi Eze's
existing candidate was also replaced at 1,993 triangles: its large rectangular
forehead gaps were reduced and the original-eye face policy improved the
inspected preview. These nine current keys passed independent cooked-buffer
validation and entered the held canonical queue; they are not visual approvals.

This optional worker samples actual source alpha into a bounded 0.22 cm grid,
joins nearby locks, smooths them, and reduces the result to the budget left
after the actual face/eye count. It bakes source colour to the existing
128-pixel hair atlas, projects smooth normals, and keeps two native sections.
The face atlas is 256 pixels under the existing source-detail policy. Hair
uses the same rigid native-head binding as the joined scalp policy; inputs
with bindings outside the head/neck/chest chain are held. No per-frame work
or new runtime shader is introduced.

The four bounded face allocations are 1,400, 1,500, 1,600 and 1,700 skin
triangles; hair is an upper bound, not an allocation added blindly to the
head. The local 1,300-skin Eze study looked promising but failed the unchanged
UV guard, so it was not merged. A 256-pixel hair-atlas experiment was rejected
by the native import policy; the actual cooked candidates use 128. Separate
Areola and Foden volume trials passed preparation but still flatten the hair
and thicken facial-hair details. They remain isolated and were not merged.
Fourteen verified sources still fail surface, silhouette, binding or budget
checks. Those checks were not relaxed to increase the count.
The nine refreshed eight-view audits report 0–1.1% geometric interior scalp
exposure; this remains a diagnostic, not a guarantee about visible baldness.
Current preparation/cook keys, the 1,426–2,000 triangle range and all 51
unchanged inherited records were checked together. The accepted v37 PAK hash
still matches its recorded release. The focused automation/geometry suite
passed 64 tests; the public-tree check passed with 972 files.

The regression investigation has established:

- The original Areola source contains 4,364 exterior skin triangles, 80 eye
  triangles and 7,672 hair triangles. Its reference render is not proof that
  the same geometry satisfies the 2,000-triangle limit.
- Retaining the original eyes, protecting a wider eyelid rim, giving source
  normals more influence, and using a 256-pixel opaque face atlas improved the
  facial canary. Its face has 1,448 skin + 80 eye triangles; with the 450-triangle
  hair trials the complete head is 1,978 triangles and two sections. This is
  a canary, not an accepted hair recipe or a new device-tested release.
- Joining all hair layers into a radial or voxel volume can pass silhouette
  checks while erasing the hairstyle's relief. Such a numerical pass is
  insufficient. The direct-collapse, joined-volume, projected-colour and
  normal-bake trials remain experimental; no winning league-wide replacement
  has been selected.
- Square-atlas UV packing must disable the rectangular source image's aspect
  correction. The tested 256-square atlas used only 12,233 interior texels
  before correction versus 31,608 afterwards. More efficient packing helps
  resolution but did not by itself recover the rejected hairstyle.
- Preview materials must classify explicitly as skin, eye or hair. A duplicate
  `lite_hair.001` material previously fell through to the skin texture. Unknown
  or ambiguous assignments now fail instead of displaying a misleading mesh.
  Fractional-alpha source references and the native-style masked preview must
  also be labelled separately. Neither is a complete emulation of game lighting.
- The player's own mobile hair was checked as a reference and has a different
  hairstyle. It has not replaced the converted source. A matching numeric slot
  alone never authorizes using a donor's hair.

The optional source-quality/rebake helpers are investigation tools, not the
factory's approved production policy. Keep the release hold until the final
prepared **and cooked** hair/face combination passes visual review, identity,
surface, triangle, section, UV, normal and native-rig checks. Reusing a prepared
or cooked cache must not implicitly approve the rejected appearance.

The eight-direction hair audit completed for all 832 new candidates. It
compares source and reduced hair against separate skin depth buffers and
distinguishes interior exposure from lost silhouette tips. Its exposure score
is **diagnostic only**: short hairstyles may already have dark hair painted
on the underlying skin texture, so geometric exposure is not automatically
a visible bald patch. The report cannot grant visual approval. Incremental
audits retain only previous results with matching mesh and audit keys; they
do not claim to have rehashed the unchanged rows during that incremental run.

Recent multi-angle samples still show inadequate hair shapes on some inputs,
especially layered hair. Direct source collapse recovered more relief for
Areola and Foden but produced conspicuous card edges, so those successful
preparations were not promoted. Joining alpha-sampled hair into a manifold
volume produced a 1,993-triangle Areola canary without restoring enough hair
relief. It likewise remains an isolated experiment, not a league-wide policy.

Five verified scalp partitions have source hair stored in the opaque skin,
with no visible masked-hair section. Their dedicated allocation spends that
unused hair budget on facial detail. Original whole-eye LOD, without aperture
cap construction or visibility cropping, allowed four to retain 1,700 skin
triangles. All five passed cooking before the seam revision, at 1,880–1,988
complete-head triangles. This is separate from ordinary hairstyles: an empty
hair placeholder is permitted only after the original scalp was transferred
and checked. It is never a fallback for a failed visible hairstyle.

## Export and reporting corrections

Duplicate triangles now leave the indexed skin input before accumulating
smooth normals. Disconnected vertices left by that filtering cannot become
collapse targets. Only point-size markers with identical nonempty skin weights
are removed; normal facial features retain the existing distance and UV guards.
Hair receives the remainder after the **actual** retained face/eye triangle
count, so an eye surface retained above its requested allocation cannot make
the complete head exceed 2,000 triangles.

The five persistent cook failures were traced to zero vectors written into
the FBX eye normal pool. Blender and Unreal reconstructed different directions
at those corners. The optional export repair replaces only undefined corners
with their supporting face direction and checks the resulting custom normals.
Positions, UVs, triangle topology and weights are preserved by this repair.
An actual Blender-to-FBX regression test checks the raw serialized normal pool;
the cooked validator's angular tolerance was not relaxed. Cody Gakpo, Natan,
Hannibal Mejbri, Valentín Barco and Sergio Mestre passed after this correction.

`realface_league_progress.py` produces per-player and per-team CSVs plus a JSON
snapshot. Historical cook passes are separate from current matching recipe
passes and from visual acceptance. A stale recovery report cannot overwrite a
current preparation/cook pair. This is a metadata summary, not a replacement
for asset hashing or the release checks.
Separate CSV lists identify current technical passes, geometry holds and
unresolved sources. Their error summaries are concise; `coverage.json` keeps
the complete underlying diagnostics. Technical pass lists still expose the
pending visual-review state of new heads.
Optional `--trial` directories contribute only current matching cook passes.
Their rejected attempts remain in `trial_outcomes`, but cannot erase an earlier
valid candidate. Neither kind of technical pass becomes visual approval.

Preview caching now records the rendered image hash only after Blender exits
successfully. An interrupted render cannot relabel an old image with a new
recipe key. Front, left, right and elevated views are available. The cooked
preview uses prepared FBX geometry with decoded cooked textures; the native
mesh is checked separately by the cooked-buffer validator. These previews are
not game captures or performance measurements.

Source-eye retention, measured-aperture eyes and denser offline hair bakes
remain optional trials. The latest source-detail preview still exposes flat
hair and facial-hair artifacts for some inputs. Do not promote these merely
because preparation succeeds. Convex clumps and short-beard texture baking are
also local visual experiments, not a replacement league policy.

## Draft scope

The v38 factory expands the v37 smooth-face / compact-hair policy to every
identity-verified source in the existing league manifest. The source batch
contains 897 real faces out of 1,122 roster identities. The other 225 require
source matching, disambiguation or available assets; they must remain explicit
in the outside-candidate list, never receive a donor head silently.

Every complete head is limited to **2,000 triangles and two sections**. The
existing 51-head Barca/MU v37 release is retained byte for byte, including its
private neutral face normal material. Newly converted heads use that same
material without overriding the global native material or its shaders.

## Offline factory

`realface_league_mobile.py` validates BaseId, native slot and fingerprint,
then prepares immutable, hashed attempts. Persistent Blender workers reduce
startup costs. Mouth features and the true neck attachment boundary are
protected, source smooth normals are retained, and face UV projection is
checked at the actual mobile atlas resolution. Existing face, eye and neck
surface-distance limits continue to apply.

Hair tries a joined scalp/beard surface first, with bounded gap closing when
full filling changes the silhouette. Short opaque and structured hairstyles
have explicit alternative allocations. A strand-card alternative is accepted
only if it passes the stricter gap screen; it cannot silently retain the bald
patches that motivated this change. Every alternative uses the same total
head ceiling and projected hair-workload checks.

`realface_league_recovery.py` provides bounded retries with different allocations
and UV weights. An optional wider eye-cap recipe samples UVs from the same
player's source eye and still checks the original pupil, lid spill and visible
coverage. Skin-only source hair slots are merged into the opaque face while
checking that native skin vertex positions do not move. Only after that
transfer may the empty hair slot use a transparent engine placeholder.

The optional `realface_raster.c` helper accelerates **offline checks only**.
It has no game/runtime dependency. The implementation is compared with the
original NumPy raster for alpha wrapping, occlusion, degenerate triangles,
coverage counters and depth. The source, Python adapter and compiled helper
are fingerprinted into preparation. No per-frame processing is added.

`realface_league_cook_queue.py` consumes completed heads in bounded chunks,
while preparation continues. UE imports/cooks are followed by the independent
cooked-buffer validator for topology, UVs, normals, native rig and weights.
Only matching current prepared/cooked keys can enter the final report. Failures
remain visible and block the full release.

## Local commands

Extend the existing local v37 configuration with a dedicated v38 work directory,
the full source manifest, and the accepted v37 PAK/verification plus its v35
identity and v37 refinement reports. Source payloads and all generated PAK/FBX
data stay in ignored local directories.

```powershell
python tools/build_realface_raster.py --output local-inputs/realface-raster-v1
python tools/realface_league_mobile.py prepare --config <local-config> --workers 4
python tools/realface_league_cook_queue.py --config <local-config>
python tools/realface_league_recovery.py --config <local-config> --partition
python tools/realface_league_recovery.py --config <local-config> --workers 2
python tools/realface_league_preview.py --config <local-config> --stage cooked
python tools/realface_league_preview.py --config <local-config> --stage cooked --views front left right
python tools/realface_league_normal_recovery.py --config <local-config>
python tools/realface_league_scalp_detail.py --config <partitioned-config> --whole-eye-lod
python tools/realface_league_seam_recovery.py --config <partitioned-config> --overlay <preferred-work-dir> --all-prepared --workers 2
python tools/realface_league_seam_recovery.py --config <seam-config> --player <base-id> --marker-cleanup --work-dir <isolated-retry-dir> --workers 2
python tools/realface_league_seam_recovery.py --config <seam-config> --all-prepared --marker-cleanup --work-dir <isolated-retry-dir> --workers 2
python tools/realface_league_targeted_recovery.py --config <seam-config> --held-report <recovery-prepare-report> --workers 2
python tools/realface_league_hair_volume.py --config <seam-config> --held-report <recovery-prepare-report> --work-dir <isolated-volume-retry-dir> --workers 2
python tools/realface_league_hair_volume.py --config <seam-config> --player <base-id> --work-dir <isolated-volume-review-dir>
python tools/realface_league_merge_prepared.py --config <seam-config> --overlay <successful-retry-work-dir>
python tools/realface_league_hair_coverage.py --config <seam-config> --workers 2
python tools/realface_league_hair_coverage.py --config <seam-config> --player <newly-recovered-base-id>
python tools/realface_league_progress.py --config <local-config> --overlay <recovery-work-dir> --output <ignored-report-dir>
python tools/realface_league_mobile.py package --config <local-config>
```

`--follow` on the cook queue allows overlap with preparation. Its explicit
`prepare-complete.json` marker must match the active preparation run ID before
it ends following after the available queue drains;
it does not turn a failed preparation into a successful one. Recovery work is
isolated until its current, passing rows are merged into the main preparation
report. Re-run cooking and validation for those changed keys.
The seam batch preserves each selected player's prior allocation and the hard
complete-head cap; successful geometry receives a new fingerprint and must be
cooked and verified again. Its selection excludes inherited accepted v37 heads.
The merge helper checks source identity, current recipe, immutable preparation
hashes and the complete-head limit before an atomic report update. It never
replaces an inherited accepted head or carries a cooked result to a new key.
Place the canonical merged seam directory last in progress-report overlays
so an older successful recipe does not supersede its replacement.
The marker cleanup with `--all-prepared` scans only immutable index inputs,
skips heads already processed under that policy, and starts Blender only for
likely microscopic clusters. This scan does not claim their skin weights are
identical: the worker still requires that exact check and unchanged visibility.
An empty scan is explicitly a no-op. It cannot trigger the factory's default
full-batch behaviour or replace accepted inherited heads.
The joined-volume retry likewise requires explicit player IDs or a held report,
validates their source identities, and cannot replace an inherited accepted
head. An empty selection is a no-op. Failed attempts are cached and remain
separate from existing successes. Review prepared and cooked previews before
merging a useful candidate; this method is not a universal replacement for
every hairstyle.

The final assembler independently checks the PAK using UnrealPak and repak,
then checks ZIP CRC and the embedded PAK hash. `PLAYER-STATUS.csv` lists the
converted identities and cooked counts, `TEAM-STATUS.csv` lists coverage per
team, and `OUTSIDE-CANDIDATE.csv` preserves all uncovered roster identities.
Only one real-face PAK should be active during device testing.

On the current workstation, temporary files and Python, Blender, shader and
Unreal caches are directed to `D:\PESNX-Cache`; child processes inherit the
environment loaded by its local `use-cache.ps1`. This is optional workstation
configuration, not a repository input. Existing caches on C were not deleted
as part of that redirect.

Offline geometry/render validation is not a measured Switch frame rate.
The user's earlier 60 FPS report concerns the v35 Barca/MU test; the expanded
candidate needs the same near-camera passing and celebration checks on device.

The subsequent [native hair construction audit](REALFACE_NATIVE_HAIR_V39.md)
investigates the original opaque scalp plus masked-card composition. Its
isolated, identity-pinned trials remain outside canonical coverage and cannot
replace the inherited accepted heads or approve this held league release.

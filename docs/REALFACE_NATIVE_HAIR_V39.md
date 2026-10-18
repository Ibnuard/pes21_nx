# Native PES21 hair construction and bounded league conversion

This is an **unreleased conversion**, not an approved replacement league PAK. The
complete-head ceiling remains **2,000 triangles**, including skin, eyes,
opaque hair bulk and masked detail. Accepted v37 heads are excluded from
replacement. All native payloads, exports and review images stay ignored.

## Observed native construction

The local main PAK is pinned to SHA-256
`26a3969be6de9495e2b5f38866c4ae4698d304fae042e305cbba53fe61915036`.
`tools/audit_realface_native_hair.py` directly exports five bounded examples
and records topology, texture dimensions, bindings and original asset hashes.
Native IDs here select construction examples, never cross-update identities.

| Native example | Opaque face triangles | Hair triangles | Complete head | Largest connected hair component |
| --- | ---: | ---: | ---: | ---: |
| 42825 | 1,170 | 162 | 1,332 | 2 |
| 114808 | 1,164 | 279 | 1,443 | 21 |
| 114906 | 1,166 | 296 | 1,462 | 9 |
| 7511 | 1,158 | 448 | 1,606 | 32 |
| 126440 | 1,148 | 776 | 1,924 | 78 |

All five have a 128x128 opaque face texture with visible scalp/hairline colour,
plus a separate 128x128 RGBA hair texture. Hair includes small disconnected
panels and longer connected strips; a universal closed dome is not the native
topology. In example 42825, the largest indexed hair component is just a
two-triangle panel and every hair vertex is bound to `sk_head`.

The material fixture was compared byte-for-byte with a fresh extraction from
the pinned PAK. `hair_parts_tablet_ss` is `BLEND_Masked`, two-sided, with one
`HairBaseColor` texture parameter. Of 95 distinct decompressed compiled shader
variants, all 80 variants containing pixel discard use an alpha cutoff of
0.3333. The audited material has no sampled imported hair normal/specular map;
serialized specular metadata alone does not prove an actual shader cost.

Material hashes:

- `.uasset`: `f3bc1e584ebf2fc75cf104c9b12a3588936381c6719682bc5c44473e67d8fc1d`
- `.uexp`: `249c2aa59b833e101a289f53e295669f52c53db39583b8204ec3d07646d03f47`

REA's available format catalog did not support UE packages. This audit used
the existing format-aware UAssetAPI, UModel, glTF and cooked-texture tooling.
No runtime trace, Switch timing or native authoring-tool workflow is claimed.

## Applied conversion approach

The existing converter already uses the native masked hair shader. The new
opt-in factory adapts the **opaque foundation plus sparse detail** composition:

1. Pin BaseId, NativePES21Id, fingerprint, source hashes and a verified prepared
   face. Reject inherited accepted heads and unclassified skin in the hair part.
2. Project only the same player's visible source hair onto the existing skin
   atlas. Scalp projection is bounded at 3 cm; short facial hair at 0.67 cm.
   Unprojected skin/eye texels remain unchanged. This is not a generic dark fill.
3. Build a bounded source-derived opaque scalp mass in a free part of the
   existing face atlas, and append it to the same opaque face section. Original
   facial positions, triangle connectivity and UVs are checked before export.
4. Keep a budgeted subset of original source detail cards. Their original
   vertices, UVs, weights and shading normals are retained. Connected-shape
   classification preserves long locks below the neck rather than cutting all
   hair at a fixed height. Detached beard/brow detail is handled in face colour.
5. Bake source clump shading/self-shadow into colour offline. Diagnostic normal
   images are not runtime resources. This is our adaptation of the observed
   native layout, not evidence of how Konami authored its textures.
6. Reimport actual FBX output and check the rig, section/material count and
   complete-head budget. Compare opaque bulk plus masked cards together across
   13 views; a hair-only mask cannot measure an opaque scalp contribution.

The opaque bulk has an explicit maximum and reserves at least 64 triangles of
the available remainder for detail. Generated slivers or duplicate triangles
can be removed only when all 13 masks and depth samples remain unchanged.
This cleanup does not operate on imported facial anatomy. Two generated
duplicate bulk triangles explained the initial Eze/Madueke export discrepancy;
the source face/eye triangle counts were unchanged. Unexplained exported
triangle loss remains held; it is not waived as a cosmetic issue.

The isolated FBX exporter normalizes both the armature object and data names
to `Armature`, as the standard exporter does. Otherwise a second imported rig
can add a thirtieth root bone in UE4.22. The current three cooked heads have
the expected 29 bones. Optional bounded closing steps affect only the isolated
native-style worker; the shared v38 volume recipe is unchanged.

The three explored variants have different limits: sparse cards alone leave
outline gaps, collapsing all source sheets can expose overlapping shards, and
closing/remeshing all hair can flatten clump relief. Neither a good silhouette
score nor a 2,000-triangle count grants visual approval. Detailed shapes and
hairlines still require the four-angle review and cooked-buffer validation.

## Reproduce locally

Inputs below are optional local fixtures from the prior v38 preparation. A
checkout without them must regenerate its own source inventory and validated
face preparation; do not restore proprietary inputs into the public tree.

```powershell
. D:\PESNX-Cache\use-cache.ps1
python tools/audit_realface_native_hair.py --config <local-config> --player 42825 --player 114808 --player 114906 --player 7511 --player 126440 --work-dir local-debug/realface-native-hair-v39/reference-audit
python tools/realface_native_hair_trial.py --config <local-config> --face-report <verified-prepare-report> --player <BaseId> --opaque-base-triangles 420 --base-mode alpha_volume --colour-mode cycles_relief --work-dir <separate-ignored-trial-dir>
python tools/realface_native_hair_preview.py --config <local-config> --work-dir <separate-ignored-trial-dir>
python tools/realface_native_hair_validate.py --config <local-config> --trial <separate-ignored-trial-dir> --work-dir <separate-ignored-validation-dir> --workers 2
```

Each attempt and conversion failure is keyed by source/profile, identity,
prepared face, tool hashes, code and budget. Reruns reuse matching results;
failed players do not abort the rest of the queue. `trial-report.json`
distinguishes conversion holds, composite geometry holds and candidates still
awaiting visual review. Preview PNGs have separate candidate/renderer hashes.
The validation command stages only current, identity-matched, geometry-passing
candidates, rejects accepted inherited heads, and reuses the existing independent
cook/buffer validator. It retains an explicit visual hold. No command in this
trial/validation workflow packages or installs a PAK; the separate TEST factory
described below packages candidates without approving or installing them.
Repeating two unchanged prepared samples
took 0.199 seconds without restarting Blender; repeating validation of all three
reused their verified cooked caches with zero new cooks.

## Initial three-head verification (historical)

Three candidates passed independent cooked geometry/UV/weight/normal and
native-buffer checks. These remain visual holds, not an approved league update:

| Player | Opaque part, including eyes/bulk | Masked detail | Complete head | Cooked vertices |
| --- | ---: | ---: | ---: | ---: |
| Alphonse Aréola | 1,892 | 108 | 2,000 | 1,459 |
| Phil Foden | 1,892 | 108 | 2,000 | 1,379 |
| Noni Madueke | 1,928 | 72 | 2,000 | 1,395 |

Each has two render sections. Prepared four-angle and cooked-texture previews
are available locally. Madueke's existing eye appearance still needs separate
visual review; this hair investigation preserves the source facial anatomy.

Eberechi Eze remains outside the accepted native-style trial set because hair
shape fails the unchanged silhouette gate. Reallocating to 1,200 face triangles
failed the 0.45 cm anatomy limit (0.519 cm maximum); 1,300 failed the existing
visible face UV gate. Neither limit was weakened to spend more on hair.

The focused suite passed **81 tests**, and the public-tree audit passed
**983 files**. The inherited v37 PAK still matches SHA-256
`cd7263c1736badeaa13a9ae4b4bdc4bd6eda8dffa4a1ae9c5c4cf0d23994c497`.
At that checkpoint, canonical v38 preparation remained 883 heads, including 51 inherited accepted
heads. Apart from the four isolated trials, 828 canonical new heads had not
been converted by this new native-style method. Existing unresolved-source and
held-player coverage is unchanged. Local `PLAYER-STATUS.csv` and
`CURRENT-STATUS.json` distinguish these states.

The current local work is under `local-debug/realface-native-hair-v39/` with all
temporary/cache output on D. The canonical v38 league coverage and its quality
hold are not changed by these trials. Device FPS remains unmeasured.

## Full league factory

The user subsequently authorized applying the method across both leagues.
`realface_native_hair_leagues.py` queues all 832 non-inherited prepared heads,
retains the 51 accepted heads, and reports all 1,122 unique roster identities.
The source inventory has 897 verified identities; 14 still require a valid
face preparation and 225 have unresolved sources. The local catalog contains
39 teams, not a claimed modern 40-team roster.

The factory defaults to two Blender conversion processes and permits an explicit
third worker when local CPU/memory measurements leave capacity. Each player and
closing variant owns a separate directory/report, while one coordinator
atomically publishes the league JSON. Unchanged successful candidates and
keyed failures are reused on reruns. Explicit alternative face choices must
pass identity and immutable-cache checks and cannot replace accepted heads.

Bulk execution exposed 128 px face atlases in addition to the initial 256 px
samples. The free bulk tile now scales to the actual atlas dimensions; skin
and eye tiles and facial UVs remain unchanged. A bounded 0..0.45 cm radial
inset can compensate voxel dilation on generated scalp bulk only. It selects
among four measured values using the same composite gate; it never changes
facial vertices or relaxes silhouette thresholds. Sparse source styles can
use original cards without manufacturing a dense cap, subject to the same
coverage checks. The earlier three cooked trial keys predate these changes;
their historical validation is not a current bulk validation claim.

```powershell
. D:\PESNX-Cache\use-cache.ps1
python tools/realface_native_hair_leagues.py --config <canonical-config> --coverage <canonical-coverage.json> --work-dir <ignored-league-work> --workers 2
python tools/realface_native_hair_queue.py --config <canonical-config> --work-dir <ignored-league-work> --follow --chunk 32 --workers 1
```

The cook queue consumes geometry passes in bounded chunks and validates actual
cooked buffers. `PLAYER-STATUS.csv` and `coverage.json` distinguish pending,
source/geometry/conversion holds, accepted inherited heads and cooked candidates.
An exact-key `VISUAL-REJECT.json` can exclude known visible regressions even
when their silhouette/count tests pass. The first batch review found angular
detached scalp cards on Stuani; that exact candidate is excluded from packaging.

After the full queue has finished, `realface_native_hair_candidate.py` can
assemble an explicitly labelled **TEST** bundle. It requires a cook result for
every current geometry pass, rejects stale keys, omits held/visually rejected
heads and keeps the inherited material/heads byte-identical. PAK test, separate
unpack hashes and ZIP CRC/hash checks are mandatory. This separate test command
does not remove the canonical release hold, approve appearance, install files
or modify the active runtime. Its status list includes everyone, including
identities omitted from the PAK. Repeat runs need local tools and cached inputs,
not an online service or another model-driven conversion pass.

The TEST archive includes `PLAYER-STATUS.csv` with readable team/league names,
`TEAM-COVERAGE.csv` with actual included/excluded counts per team, and a short
`COVERAGE.txt`. Counts distinguish unique roster identities from team memberships
and distinguish prepared/cooked candidates from assets included in the PAK.

`realface_native_hair_screen.py` renders a fixed candidate snapshot in resumable
36-head front-view sheets. Each image pins its candidate key, renderer hash and
image hash. It consumes the prepared FBX without changing geometry or textures;
it is a screen for obvious hair/beard defects, not cooked-mesh, side/back-view,
animation or Switch performance approval. Run it again on newly recovered keys
that were absent from the first snapshot. Observed defects must be entered in
the exact-key `VISUAL-REJECT.json` before the final TEST package is selected.

```powershell
python tools/realface_native_hair_screen.py --config <canonical-config> --report <candidate-snapshot.json> --work-dir <ignored-screen-directory>
```

After looking at a sheet, `realface_native_hair_screen_review.py` records the
observed defects and hashes. It refuses changed snapshots/images, wrong-page
identities and stale rejection keys. Repeating a review cannot silently clear
an existing defect. Its `REVIEW.json` explicitly keeps full visual approval
false; front-only screening cannot approve the other views or animations.

```powershell
python tools/realface_native_hair_screen_review.py --report <candidate-snapshot.json> --screen-dir <ignored-screen-directory> --reject-file <ignored-league-work>/VISUAL-REJECT.json --page 1 --reject "<BaseId>=<observed defect>"
```

The league packaging configuration supplies `screen_reviews`, a list of
`{"report": "<candidate-snapshot.json>", "screen_dir": "<review-directory>"}`
entries. `realface_native_hair_screen_gate.py` requires a current front review
for every selected new head and rejects changed images, sheets, snapshots,
candidate keys or any remaining observed defect. The proof and gate-tool hash
participate in the package cache key; `FRONT-SCREEN-VERIFICATION.json` travels
with the TEST bundle. Front screening does not grant full appearance or device
approval. A cached package still refreshes `latest-test.json` after its stored
release hashes pass verification.

```powershell
python tools/realface_native_hair_candidate.py --config <screened-local-config> --work-dir <combined-ignored-league-work>
```

`realface_native_hair_finish.py` can supervise the already-running local
conversion/cook process IDs, resume an early conversion exit at most twice,
and run final technical verification plus TEST packaging after the full queue.
It writes `PIPELINE-STATUS.json`, including explicit failure state, and never
approves or installs the result. It is a local process, not a scheduled task.

Cook batches use short, key-isolated paths under ignored `local-debug/nh39c/`.
The initial nested queue path made shared material/skeleton paths 261/263
characters long. UModel could export the shorter mesh paths but could not open
those dependencies and reported `dummy_material_0`. Files were present; the
material check correctly held all 32 heads. Shortening the cook path addresses
the dependency load without allowing dummy materials or changing geometry.

## Transparent source-binding recovery

The full batch exposed source hair files containing shoulder/root bindings in
masked head-shell polygons. A bounded audit found that 12 of the first 17
affected sources had only transparent polygons on those bindings. Other
sources contained possibly visible surfaces and remain held; bone names are
not silently renamed or rebound.

`realface_native_hair_recover.py` derives a separate source copy for these
failures. `realface_hair_alpha_cleanup.py` checks every texel within each
offending triangle's periodic UV bounding rectangle, including bilinear
neighbours, against a conservative 0.333 cutoff. Both the original texture
and the actual 128 px runtime resize must pass. The Blender worker removes
only fully invisible triangles, preserves all retained position/UV/weight
connectivity and checks the exported FBX again. It does not edit facial
geometry, the original source, or an accepted v37 head.

Cleaned source bytes, original identity/source hashes, cleanup code and proof
are included in the derived source provenance. Only failed binding candidates
are retried with the unchanged native-style converter and 2,000-triangle cap.
The first Juanmi trial removed 98 transparent polygons and preserved all 6,860
retained triangles through export; its native conversion then passed at 2,000
triangles. This is not an appearance or device approval.

The finisher starts recovery once the original geometry queue is complete,
overlapping the last original cooks. It joins the original cook queue before
merging its final verification snapshot, carrying only matching candidate keys.
It independently cooks successful recoveries, then packages the combined TEST candidate. Its
live report remains on D. The four-angle review also explicitly excludes
known angular scalp/beard regressions on Stuani, Foulquier, Del Castillo,
Willock, Mings, Bruno Guimaraes, Haaland, Isco, Wan-Bissaka, Palmer and Nico
Williams; passing a silhouette gate does
not override an observed defect. The exact candidate keys and reasons live
in the ignored run's `VISUAL-REJECT.json`.

The recovery pass also tries a bounded set of previously untried hair-only
variants for composite geometry holds: closing level 2, a 150-triangle opaque
base when it changes the actual allocation, and a 500-triangle base only when
the unchanged face leaves enough room. It keeps the original face and the
same 13-view thresholds. Source cleanup runs before a fixed source manifest
is published; two independent conversion workers then process recoveries.
Neither a new allocation nor a cached geometry pass clears a visual reject.

`realface_native_hair_precompute.py` can warm those same recovery caches with
one worker while the primary queue runs. It only considers completed holds,
does not change the primary results, and stops accepting work when the main
queue reaches its target. The finisher waits for its active job to end before
merging recovery results. Cached results still undergo the normal identity,
input hash, geometry and cooked-buffer checks in the final pass.

The updated recovery/package/screen checks passed 47 focused tests. These include
immutable screen-review evidence, rejection retention, complete current review
coverage and readable held-player reasons without discarding specific errors.
A private factory
integration check combined one current cooked native candidate with all 51
accepted heads: PAK testing, independent unpack hashes, inherited byte identity
and ZIP CRC/hash checks all passed. That 52-head fixture is an internal factory
check, not the full league deliverable. Interrupted ZIP creation uses a temporary
file and excludes prior ZIP/metadata files, so reruns cannot archive themselves.

## Full league selection, 15 October 2026

All **832** new prepared heads were attempted. The primary pass yielded 574
geometry candidates. The bounded recovery completed all 215 eligible holds
and recovered another 68, for **642 independently cooked candidates**, with
no remaining cook failure. Their complete heads range from 1,692 to 2,000
triangles, use two sections and retain the 29-bone layout.

The run screened 627 current candidates across 19 front sheets; another 15
were already rejected by earlier multi-view review. Seventy exact-key visual
rejects remain excluded even though their geometry and cook checks passed.
The resulting TEST selection has **572 new heads plus 51 unchanged v37 heads**.
Every selected new head has matching front-screen evidence. This is not full
multi-view, animated or Switch approval; a bounded silhouette test and a front
screen cannot establish those properties.

| Catalog status | Unique players |
| --- | ---: |
| Selected new TEST heads | 572 |
| Accepted v37 heads retained | 51 |
| Observed visual defect; excluded | 70 |
| Composite hair geometry hold | 132 |
| Conversion hold | 58 |
| Source face preparation hold | 14 |
| No verified source available | 225 |
| Total catalog | 1,122 |

Thus the selection covers 623 identities; **499 are not included**. Coverage
is explicitly incomplete. The input catalog has 19 English and 20 Spanish
teams. The package's player/team CSVs distinguish unique identities from team
memberships and explain every exclusion. No runtime code, NRO, CPK or active
installation is changed by this asset-only TEST factory. All payloads, caches,
review images and reports remain local on D.

The full 623-head TEST bundle completed successfully: UnrealPak checked all
7,481 entries, independent extraction matched every staged asset hash, the
51 inherited heads and shared neutral material remained byte-identical, and
the ZIP passed CRC plus embedded-PAK hash verification. The PAK is 59,285,999
bytes; the ZIP is 58,824,342 bytes. Per-player CSV membership was reconciled
against the actual package list, including all 70 visual exclusions and no
empty reason fields. The final focused suite passed 47 tests. These checks
establish package integrity and the stated scope, not Switch FPS or complete
visual acceptance.

## Unapplied hidden-scalp diagnostic

A separate read-only six-head diagnostic found 83..210 rigid-head skin
triangles completely inside watertight opaque hair bulk on five samples
(Tonali, Saka, Bellingham, Palmer and Nico Williams). It requires a closed
bulk surface, no triangle/BVH overlap, rigid head weights, points above
174 cm and inside/outside ray checks. Isco's bulk has six nonmanifold edges
and is rejected by this diagnostic. No skin triangle has been removed and
these counts are not extra runtime budget. Any future reallocation would
need containment checked again against its newly generated hair plus
independent export, appearance and cooked validation.

# Realface league factory

12 October 2026. Local asset candidate; Switch appearance, animation and FPS
remain unverified. This extends the [Barcelona workflow](REALFACE_BATCH_AUTOMATION.md).

## Validated v24 candidate

The incremental release recovers **all 128 earlier conversion/cook holds**:
118 conversion holds and ten cooked-geometry holds. Coverage is now
**897/1122 players (79.9%)**, retaining the 749 v23 league
faces and all 20 Barcelona faces. Emiliano Martinez, Borja Iglesias, Christos
Tzolis and Orri Oskarsson are included; their eye/collar repairs pass preparation,
cook validation and local preview review. Posterior collar previews use the
native body reference, and synthetic pose reports cover the seam repair.

English coverage: 466/541.
Spanish coverage: 431/581.
The remaining 225 players need source identity matching (135), disambiguation
(2), or available source assets (88); there are no remaining conversion/import/
cook holds in this selected source batch. The complete per-team status list and
128-player recovery list are included as searchable HTML, text and JSON.

The release is `local-debug/league-realfaces-v24/release/55297f11812ec370`.
Its ZIP is 284704260 bytes and the PAK contains 15229
entries. UnrealPak integrity, independent unpack/hash comparison, ZIP CRC and
embedded PAK checks pass. All 13053 v23 payloads remain byte-identical.
`local-debug/league-realfaces-v24/package-report.json` is the local entry point.

PAK SHA-256: `6d62a14137904a1bcd3560d4ae36b1bce32bbb731bb2b7bbe22677d87f028315`.
ZIP SHA-256: `51aec25c63834936bd211e83372657f8d70bc8384026d4ffe33013123d9e1108`.

These are locally validated assets, not Switch acceptance. Native gameplay,
physique/database data, shared body palettes and NRO are unchanged. Hair uses
the documented mobile material approximation and eyes use a neutral template
where the player's own native atlas is unavailable. Cullen's hair colour and
Keane's small hair-card edges remain visual review points for device testing.

## Validated v23 baseline

The v23 baseline covers **769 of 1122 players (68.5%)**, up from
499 (44.5%) in v22. It adds **270** independently validated conversions while
retaining all 479 earlier league conversions and 20 Barcelona faces.
The selected English teams have 398/541 players covered; the selected Spanish
teams have 371/581 covered. These are conversion/cook results, not hardware
acceptance claims.

The additions recover 185 earlier conversion holds, 57 unmatched identities,
18 ambiguous identities, seven previously missing sources, two import failures
and one cooked-geometry hold. Remaining failures are recorded individually;
they are not counted as successful faces.

| Status | Unique players |
| --- | ---: |
| Additional v23 conversions passing cook validation | 270 |
| Earlier v22 league conversions reused | 479 |
| Existing Barcelona faces preserved | 20 |
| Source identity not matched | 135 |
| Ambiguous source identity | 2 |
| Source assets unavailable/incomplete | 88 |
| Held during conversion/fitting | 118 |
| Held during UE import | 0 |
| Held during cooked geometry validation | 10 |
| Total audited | 1122 |

The 353 pending players retain their existing runtime face/fallback. Of those,
225 need an unambiguous identity or available source payload; 128 remain held
by conversion or cooked-geometry checks. The ten cooked holds have unexplained
triangle-count changes and are excluded from the PAK. Their complete per-player
reasons, and the origin of every successful face, are exported in
`PLAYER-STATUS.html` and `PLAYER-STATUS.txt`.

The Buendia/Mourino empty-hair repair was recooked and independently checked;
each now has the complete 17-file native asset set, including a 65536-byte
transparent hair texture bulk. Senne Lammens passes the audited exact-collapse
exception. Source eyeball fitting and paired registration also recover players
such as Nick Pope, Kylian Mbappe and Yaser Asprilla. Eight local head previews
were inspected, including those eye-fit paths and both empty-hair repairs.

The completed local release is
`local-debug/league-realfaces-v23/release/7829356832a8b0f3/`;
`local-debug/league-realfaces-v23/package-report.json` is its entry point.
`FootballNX-League-Realfaces-v23.zip` is 238689596 bytes. Its PAK contains
13053 entries, passing UnrealPak integrity and independent unpack/hash
comparison. ZIP CRC and embedded-PAK comparison pass. All 8463 payloads from
the completed v22 PAK remain byte-identical. The searchable status export has
1122 unique players, 769 covered and 353 pending.

PAK SHA-256: `8d0ff33da02051cfb16bd8b8ec963a031993ff60915dc6a8bd94e97d8758cc8b`.
ZIP SHA-256: `e7369063e9b86a05265698ff2cb24acbd71ceeb8f210dad30291093efcce9289`.

## Incremental automation (v23)

The incremental run preserves successful v22 assets and retries failed/new
identities. `reuse_verified_batch` points to the earlier local batch directory;
`release_version` selects an explicit `vNN` package name. Runtime, canonical
identity, catalog, selector and source archive checks must still agree. Original
cache keys and cook proofs are retained, rather than relabeling older assets as
outputs of the new converter. Reports distinguish reused assets from new
conversions. An unsafe reuse error cancels queued jobs immediately.

The source resolver now also checks the canonical BaseId against the source
player's name, age, height, dominant foot and goalkeeper/outfield class. This
resolves namesakes and explicit initials/shortened names. A nationality
difference requires a full-name match plus the biography checks. The source
row hash and canonical fingerprint accompany each added match. Numeric IDs,
fuzzy surnames and fictional-name substitutions alone remain insufficient.

Hair shading now retains valid smooth corners and replaces undefined/opposing
corners at folds with their own polygon normal. This changes neither mesh
positions nor UVs, winding or weights. The FBX round-trip normal guard remains
active on triangles of area at least `1e-10` square centimetres, consistently
with the repair stage. Near-zero triangles still enter the independent cook
geometry checks. Runtime surfaces are selected before exporting helper geometry, so an
unused PC helper bone/texture cannot reject an otherwise supported head.
Explicit head and sternocleidomastoid aliases map to the existing head/neck
joints; unknown weighted bones still hold the candidate.

Availability no longer requires a specifically named hair atlas: bald scalps
can use their own skin texture, and custom hair textures are checked against
actual material dependencies. If an occlusion guide is absent or unusable,
the converter can fit the neutral/native eye template to that player's own
source eyeball geometry. Sphere fit, anatomical bounds, scale, visible-aperture
gaze alignment and protected-face round-trip checks remain mandatory.

The paired eye registration separates a shared head-frame offset from local
socket movement. Both guides must agree anatomically; shared translation is
bounded to 3.5 cm, with individual residuals still capped at 1.5 cm. Invalid
guides retain the previous fitting/fallback route instead of authorizing a
guessed placement. A public synthetic fixture covers both valid offsets and
invalid/asymmetric guides.

Fully collapsed filler meshes with identical weights can be excluded only
when another surface remains in that part. A wholly collapsed hair slot is
represented by a tiny authored triangle inside the head and a transparent
128x128 texture on the existing native hair material. A 4x4 texture is stored
inline by UE and omits the bulk-data file required by the native asset
contract; the standard mobile size preserves that contract. Its source extent must be no
more than `1e-6` cm on every axis. Visible scalp/hair surfaces are never replaced
by this exception; the resulting native mesh still passes cook validation.

UE can extract embedded FBX images into adjacent `.fbm` folders during import.
Old prepared proofs remain immutable. Additional images are accepted only
beside a verified FBX and when both filename and SHA-256 match a texture in the
original proof. Changed/missing original files and unrelated extras are rejected.
Cooked asset hashes are always rechecked. For previously validated cooked
assets, preparation and cook also verify the original locked identity profile;
they do not reread unused multi-megabyte Blender intermediates. Newly prepared
assets retain the complete intermediate-file audit. Reports are replaced
atomically so an interrupted write cannot truncate the previous report.

An exact repeated pair of triangle corners is also a zero-area collapse, even
when the third corner is distant. That narrow case now qualifies for the
existing audited triangle-count exception. Near-coincident extended cards
remain rejected. The local Senne Lammens source contains one such repeated
pair; Georginio Rutter's near-coincident cards do not meet that exception.

## Completed v22 baseline

| Status | Unique players |
| --- | ---: |
| New faces passing independent cook validation | 479 |
| Existing Barcelona faces preserved | 20 |
| Source identity not matched | 213 |
| Ambiguous source identity | 24 |
| Source assets unavailable/incomplete | 84 |
| Held during conversion/fitting | 298 |
| Held during UE import | 2 |
| Held during cooked geometry validation | 2 |
| Total audited | 1122 |

The four holds after preparation are Emiliano Buendía and Santiago Mouriño
(hair import failed), Georginio Rutter (two hair triangles lost) and Senne
Lammens (one hair triangle lost). Those two geometry losses are not explained
by the fully coincident-corner exception. The other 619 pending players have
individual source/identity/conversion reasons in the generated status lists.
"Pending" means not updated by this batch; it does not mean the runtime has
no existing realface or fallback for that player.

The local package/report entry point is
`local-debug/league-realfaces-v22/package-report.json`. It identifies the
immutable release folder and ZIP checksum. That folder contains the searchable
`PLAYER-STATUS.html`, the per-team `PLAYER-STATUS.txt`, machine-readable
`VERIFICATION.json`, and installation instructions. All payloads remain local.

The first completed release is `release/6e33ac5bf9fedced` within that work
directory: 8463 PAK entries, all passing UnrealPak integrity and independent
unpack/hash comparison; the ZIP passes CRC and embedded-PAK byte comparison.
PAK SHA-256: `8e4199f3c8924af8156bcb6a6c87864ff5abb10ef87437c08a9fc1767c544ce3`.
ZIP SHA-256: `de31c4f40a8976b2607349b55c265ce4b24d496976f89e1e3b506815bf239b7d`.

The inventory uses every team in the active `english_league` and
`spanish_league` selector categories: 19 English and 20 Spanish teams,
1122 unique playable identities. Those are the repository's actual categories,
not a claim that a current external league contains only 19 clubs. Squad order,
physical team slots, dt200 checksum and compiled selector build must agree.
The v21 physique database and pinned asset identities are preserved.

## Repeating the pipeline

```powershell
python tools/realface_batch.py run --config <local-config.json> --workers 3
```

`plan`, `prepare`, `cook`, `verify`, and `package` can also run separately.
`--player <BaseId>` limits prepare/cook diagnostics; partial preparation retains
the rest of its report. Full packaging requires a result for every available
source and every prepared face. It never treats an incomplete batch as full
coverage. `run` creates the inventory only when absent; a changed database or
identity state requires an explicitly regenerated inventory.

After updating the converter, retry only held/new sources with:

```powershell
python tools/realface_batch.py prepare --config <local-config.json> --retry-held --workers 3
```

Explicit `--player <BaseId>` arguments can additionally retry a prepared face
that failed import/cook. Then run full `cook`, `verify`, and `package` stages;
verified per-player caches avoid repeating successful work. Status exports
separate newly added conversions from reused earlier assets and include an
origin filter alongside player/team/reason search.

For a subsequent incremental batch, point `reuse_verified_batch` at the
completed v23 work directory. This preserves all 749 validated league faces
under their original keys, in addition to the separately preserved Barcelona
assets, while new recipes handle only held/new players.

The local config supplies `runtime_base`, `identity_state`, `catalog`, `selector`,
`categories`/`team_ids`, ordered low-to-high-priority source `cpks`, and dedicated
ignored `work_dir` and `cache_dir`. It also supplies local paths for Blender,
the FMDL and FTEX parsers, UE4.22 editor/UnrealPak, UAssetGUI, UE Viewer, repak,
the audited skeleton/rig contracts, neutral eye template and texture, native
neck/body references, main mobile PAK/checksum and an isolated UE project
template. `fit` contains explicit neck movement/reference-distance limits.

Earlier faces can be included with `preserved_verification`, `preserved_pak`,
`preserved_inventory` and `physique_report`. An old fingerprint mismatch needs
the exact old-to-new physical-row checksum chain and unchanged BaseId/native
ownership. A reused native number alone never authorizes an inherited face.

No paid API, generative image call, online download or manual per-player Blender
session is used. Each local CPK is indexed once; only verified face members are
read. Preparation uses one Blender process per player for export, automatic eye
placement, fitting and round-trip/pose checks. UE imports and cooks a batch in
one isolated project. Worker counts are bounded to avoid memory spikes.
Cook validation keeps one Blender process per worker and resets the scene for
each mesh. It reuses exact weighted bind matrices without rounding weights.
Three canary players produced identical audit metrics to the original process;
after startup, the two subsequent checks took 0.72 and 1.80 seconds locally.
Per-player reports also record the exact validation-source hashes.

Use `local-inputs/realface-cache-v1/` for reusable source/prepared/cooked caches.
Keys include source payload hashes, BaseId/fingerprint/native slot, reference
buffers, fit settings, tool code and the relevant tool binaries. Repeating an
unchanged preparation checks outputs and skips conversion. Cached conversion
failures are retained until an input/recipe changes; they are not retried on
every invocation. Cooked caches are finalized only after independent validation.
Modified/missing required outputs invalidate a cache; the only extra-file
exception is the documented identical FBX image extraction. Validated cooked
reuse checks its actual assets and locked identity profile, without depending
on unused preparation intermediates. Logs are diagnostic.

Blender can extract embedded FBX images beside its input. Preview and cooked
validation therefore read private copies outside immutable prepared caches.
UE4.22's script commandlet misinterprets spaces in its script path; the factory
uses a generated entry point in a space-free temporary directory while keeping
reports and profiles in the project workspace.

UE can return exit code 1 for caught per-player FBX failures. The factory permits
that specific exit only after a final batch-completion marker and all player
reports have been checked. A crash, missing report, wrong player or incomplete
mesh pair still stops the job. Failed players never enter the package.

## Identity, materials and eyes

The source resolver first checks BaseId, name and biography as described
above, then retains the unique normalized full-name/country fallback against
the local source Player.bin. Missing/ambiguous identities and incomplete
payloads are listed, not guessed. Canonical BaseId is kept independently of
the native storage ID. Club membership never duplicates a canonical face.

Skin/hair/effect classification comes from shader and texture roles, including
heads whose main skin is in `hair_high.fmdl`. Wet overlays, eyelid guides and
unsupported auxiliary geometry are excluded from runtime mesh exports.
Multi-atlas hair has an explicit **native primary diffuse/alpha** approximation:
the player's own primary texture, HairColor and integer UV repetition are baked
into a deterministic atlas. UV wrap seams remain continuous. The secondary
PC texture/shader blend, normal/specular/translucency effects are omitted and
recorded. This is not a complete port of the PC shader.
If the primary Hair2 diffuse is absent, an explicit secondary diffuse from the
same source material may be flattened using its second UV channel. Exactly two
UV channels and the actual secondary image are required. This policy is recorded
as `own_secondary_diffuse_uv1`; it does not recreate the absent PC blend layer.
Other missing images, ambiguous UV layouts and nonfinite coordinates stay held.

Geometry cleanup precedes texture resolution, so a disabled filler cannot demand
a texture used by no visible mesh. Fully coincident fillers remain degenerate
under any pose when their mapped influences span at most two mobile bones:
every transformed corner lies on the segment between the same two points.
Three-bone cases are retained. An entire all-XYZ-NaN mesh may be discarded only
when the same part contains another finite, noncollapsed mesh. Mixed corruption,
infinities or removal of the whole part are rejected; no replacement shape is
invented. Both exceptions retain explicit source audit records.

Both eyes are fitted to each source head's eyelid guide or verified source
eyeball geometry, with optional bounded pair registration. Own native eye
geometry/atlas is available only when the identity registry proves ownership;
migrated donor IDs use a declared neutral template instead. Excessive scale,
translation, occlusion or unstable eyelid guides hold the player for review.
Template iris colors are not factual player data. Lower-neck fitting restores
valid chest/neck groups removed as unused by FBX, retaining the audited skeleton
and movement budget. Existing upper-face geometry, UVs and weights are protected.

The v24 recovery recipe adds a measured skin-surface fallback when source eye
helpers are absent or malformed. Frontal ray depths identify one enclosed
orbital recess per side, including heads with a closed inner socket wall.
Upper/lower lid samples provide the fitting reference; no skin geometry is
replaced. Ambiguous recesses, unstable depths, excessive scaling and occluded
pupils still stop conversion. Both the selected reference and failed fitting
paths are recorded. The same bounded fitting and visible-pupil checks apply.
Unlike an abstract source helper, the measured skin rim must enclose the eye.
The fallback uses the 15th percentile of measured globe depths, bounded to
0.45 cm behind the median fit, to prevent lower-lid protrusion. The original
depth-stability and translation limits still apply before visible-pupil
alignment. Reports retain the median fit residual, final residual and clearance.
Secondary measurements can detect a shallower enclosed recess or omit at most
0.18 cm of nonspherical tear-duct corners from each end of the depth fit. Optical
validation still scans the full, untrimmed aperture. Each side records the
selected measurement. Fit stability, movement and pupil checks remain active.
A complete pair of nearly spherical source eyeballs (RMS below 0.03 cm, radii
0.95–1.8 cm, radius ratio below 1.12, bounded centre asymmetry) can size a small
neutral template directly, up to 1.5x. A single globe or eyelid guide cannot use
that exception. Iris colour remains the declared neutral template.

Lower chest/shoulder vertices below 155 cm may use the native body surface when
the face reference is too far away. This requires at least half their weight
on chest/shoulder bones and a body reference within the existing 3 cm limit.
The 1.15 cm movement budget plus 0.06 cm cloth clearance remain unchanged;
head/jaw vertices cannot use this fallback. Motion samples record whether the
reference was face or body. Synthetic poses remain diagnostics, not hardware
acceptance.
The second recovery pass excludes purely head-bound jaw/chin vertices from the
numeric lower-neck band and preserves them exactly. A posterior neck below
151 cm with over 10% torso influence may also use the nearby body reference;
the same 3 cm reference and movement limits apply. Distant torso-bound skin can
remain unchanged only if it stays inside the body surface, with clearance, in
all six synthetic poses and sixteen horizontal ray directions per pose. The
round-trip audit checks the preserved positions, weights, UVs and shading.
An open shirt region or a posed escape fails this exception.

Undefined shading on a triangle with effectively zero area does not describe a
visible surface. The eye round-trip checker ignores normal differences only
when the corner belongs to a degenerate triangle both before and after export.
Position, UV, topology and weight checks remain active on those corners. The
Blender regression fixture rejects visible-normal changes and attempts to use
this exception for moved geometry or newly nondegenerate triangles.
The neck round-trip uses the same before-and-after area requirement.

Cook validation checks the embedded rig, material components, triangle counts,
position/UV/weight tuples on the same vertices and reverse source coverage.
Only fully coincident source triangle corners within 0.00001 cm, or a pair of
exactly identical corners, qualify as source collapses during UE welding.
Near-coincident extended cards cannot use that exception. UE's removal
of a collapsed triangle is optional: unchanged triangle counts are accepted
with the same position/UV/weight and reverse-coverage checks. Eight local
candidates retained their collapsed triangles and needed this checker fix.
When UE removes only some collapsed faces, a separate audit must prove a
one-to-one match of every noncollapsed triangle, including its corner UVs and
skin weights. Duplicate cooked triangles cannot stand in for missing surfaces.
Rounded signatures accelerate lookup only; a full spatial fallback resolves
bin boundaries before a bijective match is accepted. Unexplained geometry
removal remains rejected. UE's removal
of influences at/below one percent and 8-bit weight quantization are accounted
for. Rest rigs are immutable; cached weighted bind matrices preserve the original
arithmetic without rounding weights.

Vertex checks index UV seams and deduplicate identical complete tuples. A
matching position, UV and weight must still belong to the same source tuple;
the tolerances remain 0.03 cm (0.005 cm for eyes), 0.001 UV and 0.025 weight L1.
This avoids repeatedly scanning thousands of coincident filler vertices.

## Release and status data

The packager accepts only per-player RealFace mesh/material/texture assets.
Shared skeleton, body and material cook dependencies never enter the PAK.
The 20 existing Barcelona faces are copied byte-for-byte from their verified
combined PAK. The resulting single League-Faces PAK replaces the separate
Barcelona/Yamal/Raphinha face PAKs; installation and rollback instructions are
inside the ZIP. NRO, gameplay hooks, database and SaveData are untouched.

UnrealPak integrity and a repak unpack/hash comparison are required before ZIP
creation. ZIP CRC and its embedded PAK bytes are then checked. Release outputs
include `VERIFICATION.json`, `CHECKSUMS.json`, `PLAYER-STATUS.txt` grouped by team,
and a searchable offline `PLAYER-STATUS.html`. The lists distinguish new
candidates, preserved faces, missing source/identity, conversion holds and cook
validation holds. Counts refer to unique players; a club's list may show a
player with multiple legitimate team assignments.

Incremental releases also export `RECOVERY-STATUS.txt` and JSON. They compare
the earlier failed conversions/imports/cook validations by BaseId plus native
slot and fingerprint, and separate recovered players from remaining holds.
Missing identities/assets are not counted as conversion recoveries. The
comparison is included in the release key and ZIP alongside the complete list.

Large imports use separate UE commandlets of at most eight players, with GC
between profiles and `-nullrhi`. This bounds native FBX allocation accumulation;
a missing completion marker still stops the job. Source code is checked before
and after preparation so an edit during a long batch cannot stamp a candidate
with an obsolete recipe key. Incremental repair can cook only selected player
IDs and merge their validated reports with unchanged verified assets; the final
package still checks all payload hashes and the locked player identities.

Import checkpoints can also preserve individually completed editor assets.
Their receipt locks the prepared recipe, identity profile, importer/compiler,
shared dependencies and every allowlisted asset hash. Changed recipes are
imported again; partial/crashed imports are excluded. This avoids repeating
successful imports after a later player fails. The compiler contract is saved
before import; an old project without matching provenance cannot be stamped
as a current checkpoint. Dense coincident filler islands
inside visible meshes are removed before FBX export only if their triangles
have zero area in every supported pose (identical weighted corners, or all
coincident corners using at most two mapped bones). A rest-only collapse that
can open under three-bone animation is retained. This prevents quadratic UE
overlap allocations without removing thin visible hair cards.

The final four preparation holds exposed two additional cases. Actual skin
sockets now take priority over PC helper planes, which can lie in front of the
visible eyelid. At most 15% isolated tear-duct depth outliers may be excluded
from the depth fit, only at the outer 20% of the aperture. The globe radius and
full optical scan bounds remain unchanged; depth, scale and gaze checks still
apply. A higher measured eye-pair frame is accepted up to 3.5 cm only when both
skin sockets agree within 0.35 cm. This recovered Tzolis and Oskarsson.

Posterior chest-bound collar tips first seek the outward body surface rather
than the inside of the collar. An isolated patch of at most four physical
points may follow at least four already fitted local neighbours when their
displacements agree within 0.5 cm. The 1.21 cm movement budget, triangle
orientation/area, identical UV-seam moves, unchanged weights and round-trip
checks remain enforced; repairs cannot use other unresolved points as support.
This recovered Martinez and Borja Iglesias. Synthetic poses are recorded for
the supported points as well as the ordinary fitted neck vertices.

Local structural checks do not prove actual kit collars, face/body shade,
expressions, animated hair, load time or match performance. The additional
faces do not change body skin palettes. Installation remains a device-test
candidate, and the status report must never label it hardware accepted.

112 focused tests pass with synthetic identity/material/cache/fitting fixtures. The
Blender bind-cache regression checks 3600 matrix comparisons against the
original arithmetic, including reuse with new rig references. The public-tree
audit passes. The enclosure fixture rejects exterior skin, missing clearance,
an open shell and skin that escapes during a synthetic pose. These checks do not turn the wider repository suite or the Switch
validation into a claimed pass.

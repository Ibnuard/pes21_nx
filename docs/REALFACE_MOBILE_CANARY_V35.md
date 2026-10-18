# Realface Mobile v35 — Barcelona / Manchester United candidate

This is the smaller asset test that follows the user's rejection of Lite
v34 for frame pacing. It targets the 51 verified realface identities in the
two affected rosters, including substitutes. Eight roster identities had no
verified realface source in v34 and remain outside this conversion. This is
not a new 897-player release.

## Subsequent device feedback

The user reports smooth 60 FPS with Barcelona versus Manchester United using
v35, but rejects the wrinkles on the left cheek through the neck. This is
user-reported performance, not a captured frame-time measurement. The user
explicitly retained the 2,000-triangle ceiling. The
[v36 surface correction](REALFACE_SURFACE_V36.md) preserves every cooked
mesh byte and isolates the mismatched native normal atlas.

## Host validation — 14 October 2026

All 51 prepared heads completed the Android ETC1 cook and independent
cooked-buffer validation. The cook finished with zero errors and warnings.

| Check | Result |
| --- | --- |
| Complete-head triangles, minimum / median / maximum | 1,929 / 1,984 / 1,995 |
| Total triangles across the same 51 identities | 100,948 |
| Material sections per complete head | 2 |
| Skin/eye normal samples checked after cook | 48,527 |
| Maximum cooked normal deviation | 0.383 degrees; limit 2 degrees |
| Eye apertures | 98 adjusted, 4 already enclosed, 0 unresolved |
| Hair recipes | 27 visible-card, 22 split scalp/beard, 1 closed surface, 1 braid-core |

The same-identity Lite v34 audit totals 143,157 triangles, so this candidate
reduces that count by 29.48%. Its thirteen-view hair-card fragment proxy is
5,818,152 versus 14,133,346 for the original fitted FL26 inputs. That fragment
baseline is **not v34**, and neither count is a frame-time measurement.

Offline front and three-quarter previews confirm that Bruno Fernandes's
beard follows the cheek and chin without the previous lateral fins. Dani
Olmo's eye/face preview and the compact braid fallback were also reviewed.
These are renders of the prepared meshes, not captures from Switch. Hair
detail remains deliberately reduced, especially braided styles. These early
previews omitted the native material's common normal atlas; they did not
predict the surface defect subsequently reported on device.

The local release contains 612 allowlisted per-player files in
`PesMobile-Barca-MU-Faces-Mobile-v35-Android_ETC1_P.pak` (4,139,437 bytes).
UnrealPak's integrity check passed, independent repak extraction matched
every asset hash, and the ZIP's CRC/embedded-PAK checks passed.

- PAK SHA-256: `b6193bbd3bb76dbcdea3a915e87533cdbca349eb91a20ceba82b0529634de88a`
- ZIP: `FootballNX-Mobile-v35-Barca-MU.zip`, 4,140,959 bytes.
- ZIP SHA-256: `6be5e94f18fdd75b056027beba53661c9aacbf7b0c6ccfe3dc2148fdb7f3a190`

Payloads and their detailed per-player proofs stay local and ignored. This
release was not installed into the active runtime or SD card; no NRO changed.

## Recipe

`tools/realface_mobile.py` uses the existing pinned sources and BaseId/native
ID/fingerprint registry. It runs locally with Blender, meshoptimizer and
UE4.22; no API or model call is needed per player. Prepared and independently
validated cooked outputs are cached. Failed geometry remains held.

Every complete head must stay at or below 2,000 triangles after conversion
and again after cook. Allocation retries move the budget between skin and
hair; they cannot raise the complete-head ceiling. Skin, eye shape and neck
attachment retain the v34 surface-error limits.

The user's visual review rejected uniformly reduced faces with angular lids,
nose and mouth. Skin now keeps its source corner normals, and directional
error attributes prioritize the visible facial surface. The initial skin
budget is 1,500 triangles, versus 380 for hair. Before reduction, rigid skin
triangles wholly occluded at four interior samples from 38 directions are
removed; neck and nonrigid skin remain protected. Surface error is measured
on that retained exterior. This finite visibility audit is not a guarantee
for every possible camera. Source normal directions are checked again from
the independently exported cooked buffer, within two degrees of tolerance.
If the directional attribute budget fails the unchanged surface limit, a
position-priority retry can allocate up to 1,800 skin triangles while reducing
hair further. Source shading normals remain preserved in either mode.

For protruding eyes, the cleanup measures each player's own eyelid aperture.
A compact anterior eye patch retains the pupil depth and source UVs while
tucking its outer edge under the skin. It overlaps the hidden edge to avoid
an inset crack. Moving an entire globe backwards was rejected in visual QA
because it made the eye look sunken. Ambiguous apertures preserve their input
and carry an explicit unresolved status instead of guessed geometry. Preview
renders retain the same imported normals; they do not hide defects with
subdivision or a separate smoothing pass.

The anterior patch keeps the iris within 0.03 cm of its source depth and
retains a broad inner ring before folding under the lid. Its winding faces
native +Y; an inward-facing X/Z fan would incorrectly darken the eye. A
synthetic Blender regression checks both direction and pupil depth.
The generated surfaces also reverse winding when moving through the native
rig's reflected coordinate transform. The regression checks the transformed
normal and UV ownership, not only the unconverted triangle fan. Original eye
triangles are normalized before that conversion so already-enclosed eyes
retain their original orientation.

Eye and skin geometry share one opaque material. An explicit 128x128 atlas
reserves a padded skin region and a cropped eye region. The crop follows the
actual eye UV extent, including native repeating overscan, instead of
assuming every source uses a standalone iris image. UV remapping records a
round-trip proof before the two objects are joined. Masked hair remains in
its own section. Native materials and skeletons resolve from the base game;
the test PAK contains only per-player meshes, textures and a face instance.

Hair first tries alpha-aware removal of hidden triangles and constrained
simplification. More layered styles use an offline radial surface bake from
that player's own visible hair. This produces a compact scalp mesh, a
128x128 albedo/alpha texture and one head-bone influence. There is no runtime
ray tracing or per-frame conversion. Disconnected facial-hair cards below
the eyes and in front of the jaw are classified separately from scalp hair.
Each region has its own source-derived radial center and cropped latitude
range within the same atlas. This prevents a scalp-origin bake from stretching
the beard into fins beside the jaw. Facial hair keeps its sampled alpha;
only scalp strand gaps are closed. No additional runtime material is added.

The final reduced scalp fits the exterior envelope with a bounded 0–1 cm
radial correction and records the chosen offset. Facial hair is not inflated.
Short opaque styles can retry a volume-aware collapse of their original
surface instead of a radial bake. It runs before the armature modifier and
inverts the native bind transform afterwards, retaining the native rig.
Neither fallback raises the 2,000-triangle head ceiling.

Layered braids have a separate offline fallback. Paired dense cores and
translucent fuzz are detected using alpha and matching source bounds. Their
own longitudinal UV rings define a small set of curved strands, using the
outer layer for the envelope and the dense core for color. Smooth strand
normals cross UV seams consistently, and broad roots partially follow the
source surface. Accessories use the remaining hair budget. The recipe still
passes the same thirteen-view envelope gate and 2,000-triangle head limit;
it does not silently retain a high-poly hairstyle. This optional converter
has its own source fingerprint, so editing it does not invalidate unrelated
successful heads.
The unchanged source projections and radial bakes are cached across retries.
The radial alpha atlas closes gaps up to two texels between isolated strands
to form compact clumps. Large openings remain transparent. The source's
neighboring colors fill those texels; no new color/identity is generated.
Each attempt hashes its own budget and material policy. Adding a fallback
does not invalidate otherwise unchanged successful attempts.
On a new recipe revision, the previous successful allocation is tried first
for the same verified identity. Its output is still rebuilt and checked;
only the allocation search order is remembered, not the earlier acceptance.

Following the user's preference to preserve facial shape and simplify hair,
the hair gate accepts a mean sampled envelope IoU of at least 85%, a worst
view of at least 80%, and at most 15% missing coverage. This explicitly
permits fewer isolated strands; the earlier 86% minimum rejected the compact
Fermín shell despite a recognizable host preview. It is a hair-only fidelity
tradeoff. Face, pupil, neck and cooked-normal checks are not relaxed.

Thirteen fixed views compare the original and candidate at the same bounds
and sample grid. The proof reports raw alpha agreement, the hairstyle
envelope (one pixel of strand-gap closing), missing coverage, and projected
card/alpha fragment counts. These are geometry workload proxies, **not GPU
timings**. They complement source/cooked rig, UV, weight and topology checks.
Host previews must be identified as offline renders, not Switch captures.

## Reproduce

Use a local configuration extending the v34 one with an explicit
`mobile_base_ids` allowlist and fresh ignored `work_dir`/`cache_dir` paths.
The existing full source manifest is still identity-validated before the
selected players are processed.

```powershell
python tools/realface_mobile.py prepare --config <local-config.json> --workers 2
python tools/realface_mobile.py status --config <local-config.json>
python tools/realface_mobile.py cook --config <local-config.json>
python tools/realface_mobile.py verify --config <local-config.json> --workers 2
python tools/realface_mobile.py package --config <local-config.json>
```

Packaging refuses a held, missing or duplicated identity; a head over the
ceiling; unexpected material sections; changed cached bytes; or assets
outside the per-player allowlist. A report from an older automation revision
cannot be mixed into a newly prepared batch. UnrealPak integrity and a separate repak
unpack/hash comparison are required. The active runtime is never modified.
The package command also creates a checked ZIP, installation instructions,
and per-player CSV/JSON coverage. `PLAYER-STATUS` lists the 51 cooked heads;
`OUTSIDE-CANDIDATE` lists the eight selected-roster identities without a
verified source, retaining their explicit source-availability statuses.
`status` reports held or still-pending
identities without treating results from old geometry code as finished.

## Device comparison

Use the existing NRO and roster/physique/skin CPKs. Move all previous
realface PAKs outside both mounted Paks folders for this test, including Lite
v34; install only the Barcelona/MU candidate. Other clubs then use their
unpatched head assets. Keep the same teams, starting XI, formation, stadium,
camera and graphics settings when comparing candidate versus no face PAK.
Test play near the bottom touchline in DAY and NIGHT and inspect a replay
close-up. Moving the test PAK out and restoring v34 is the rollback.

A successful host cook alone does not prove smooth frame pacing. The later
user test reports 60 FPS, while visual acceptance remains rejected until the
v36 surface correction is tested on device.

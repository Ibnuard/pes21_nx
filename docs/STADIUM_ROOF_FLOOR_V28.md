# San Siro / Bernabeu overhead roof and apron repair, v28

## Device feedback and scope

The user reports v27 is smooth at the other selected stadiums, but San Siro
and Santiago Bernabeu still stutter under the large roof shadow. They request
an overhead sun so the roof falls vertically onto the perimeter, and report
flickering floor surfaces near the left goal in several stadiums.

The roof policy changes only stable IDs 6 and 7. Other roof profiles, weather
colours, camera cutaways, crowd animation, resolution and frame timing retain
v27 behaviour. The apron repair applies to all six selected imported PAKs;
Anfield and Konami use their existing assets.

## Roof projection

Pitch, body and face shader variants share a world-XY projection for these
two profiles. Their uniform branch skips the sun/season/height-dependent
offset calculation. The derivatives still execute before spatial branches,
preserving the existing soft edge and weather attenuation. The player's feet
and head use the same vertical light ray.

The runtime opening is shifted toward +X/+Y (right/up in the plan preview),
as requested after the initial centred preview. San Siro's centre is (3.5, 3.5)
metres, leaving approximately 1.5 metres of shade at the left goal line and
1 metre along the lower touchline. Bernabeu's opening is widened from 28.5 to
32.5 metres half-width and centred at (3.5, 2.5) metres. Its shade enters about
4 metres from the lower touchline, slightly farther at the rounded lower-left
corner. Both upper touchlines and midfield remain lit.

This is an explicit visual policy requested by the user; the measured source
roof and imported geometry are retained separately. Source fitting manifests
are not rewritten as if the roof had changed physically.

A host run of the actual emitted shader math, using the representative Fine /
Summer sun from the accepted preview, samples 28,907 pitch points per venue:

| Stadium | v27 shaded samples | v28 shaded samples |
| --- | ---: | ---: |
| San Siro | 57.67% | 4.06% |
| Santiago Bernabeu | 69.44% | 6.59% |

The roof remains visible on the surrounding apron and the thin left/lower
pitch-edge bands. This measures coverage, not GPU time or FPS. The mathematical
preview is saved locally as `local-debug/stadium-roof-v28/roof-comparison.png`.

## Coplanar floor repair

The retained native `st029_pitch_2` includes the playable grass and an outer
apron. The v27 imported shells contain nearly coplanar floor at the same
height. A sampled audit found 1,949–4,181 native/imported near-coplanar pairs
per stadium. Competing depth values are a concrete candidate for the supplied
flicker; a still image cannot prove all temporal artifacts have that cause.

`tools/repair_stadium_apron.py` removes only nearly horizontal imported floor
within 6 cm of native pitch height where it overlaps the actual native floor
footprint. Bernabeu and Stamford Bridge use a lower bound of -25 cm to include
slightly sloped, mostly buried apron faces that still intersect the native
plane; their upper bound remains +6 cm. It preserves props, walls, railings,
stands, roof, crowd and the floor outside that footprint. Native grass, goals
and collision are untouched. The goal-side apron consequently uses the
existing native/perimeter texture.

The owned native mesh is an optional local input, never committed. Its union
is computed by `tools/stadium_apron_geometry.py` using Shapely 2.1 in a host
Python process. Internal native triangle edges are removed before clipping;
an initial triangle-by-triangle approach was rejected because it unnecessarily
increased geometry. The union preserves uncovered corners and holes that a
rectangle or convex hull would incorrectly fill. Boundary precision is 0.01 mm,
with a 0.02 mm topology-preserving simplification of redundant edges.

New vertices interpolate source UVs and normals. Triangle winding, atlas tile
IDs, conservative cull bounds and native crowd counts survive the export.
Vertex lighting is rebaked from the preserved corner normals. Unused material
slots are dropped. No per-frame work or additional shader sample is added.

For this geometry-only repair, `cook_stadium_batch.py --reuse-materials` can
retain materials in an existing verified UE project. Missing materials or a
profile without an apron-repair report fail instead of silently substituting
materials. The final cooked shader/mesh audit must still pass.

## Host verification

The final cooked meshes pass the texture, UV, vertex colour, camera and
overdraw audits. At 8,753 sampled apron positions per stadium, all six have
zero native/imported near-coplanar pairs and zero imported self-coplanar pairs
within the audit's 1 cm tolerance. This is a sampled geometric check, not an
on-device flicker test. Shell geometry totals 209,589 triangles, below v27's
210,000; the 47,380 native crowd triangles are unchanged.

The focused suite passes 36 tests and 41 subtests, including all weather/season
combinations, matching pitch/head lighting, the clear midfield and the shifted
edge bands. The native shader check passes 2,824 compilations across 706
variants. The cooked-material audit checks 40 materials, 560 shader records
and 4,480 clip/HDR variants (192 unique compilations), with no errors. The
production NRO builds with its expected runtime identity and verified icon.

Local reports, hashes, the mathematical preview and installation instructions
are bundled with the v28 release. Proprietary PAKs and native input meshes
remain ignored under `local-debug/`.

## Acceptance

Install the paired v28 NRO and all six replacement stadium PAKs. Existing
Anfield, realfaces, physique data and the accepted runtime identity remain in
use. The log header is `FootballNX scene v28 session`.

On Switch, compare San Siro and Bernabeu near midfield and the near touchline,
then move the camera slowly around both goals in DAY and NIGHT. Inspect the
perimeter and celebration corners for gaps or remaining flicker. The user's
v27 acceptance of the other stadiums is not a hardware test of this candidate;
v28 frame pacing and visual acceptance remain pending.

## v29 follow-up: visible left/lower bands

The user judged v28's 4–7% coverage too close to the boundary lines and asked
for 10–20% of the pitch to receive shadow from the left/lower sides. Only the
runtime opening centres change: San Siro to (8, 9) metres and Bernabeu to
(18.5, 5) metres. The different centres account for their different measured
opening widths. Bernabeu retains the v28 32.5 metre half-width.

Both straight bands now extend approximately 6 metres inside the left goal
line and 6.5 metres inside the lower touchline, with each roof's existing
rounded corner. Sampling the same 28,907 Fine/Summer pitch positions yields
15.77% coverage for San Siro and 16.54% for Bernabeu. Midfield, the right goal
and the centre of the upper touchline remain lit. The exact shader preview is
`local-debug/stadium-roof-v29/roof-comparison.png`.

This adjusts constants only. Shader code, vertical player/pitch projection,
weather attenuation, soft edges and uniform caching are unchanged from v28;
it adds no draw calls, texture lookups or per-frame fitting. Wider coverage
can still change GPU work, so hardware frame pacing must be checked again.
The roof tests enforce the 10–20% coverage range, dark samples several metres
inside both edges, a clear central region and matching ground/head lighting
for all weather/season combinations.

All 12 focused tests in `test_stadium_lite_math.py`, `test_roof_fast_paths.py`
and `test_roof_uniform.py` pass for v29. The package verifies that the shader
source is byte-identical to v28 and checks the NRO against its AArch64 ELF.

The v29 update contains only the rebuilt NRO (log header `FootballNX scene
v29 session`). Use the six floor-corrected PAKs already delivered with v28.
No stadium recook, player-data migration or save update is required.

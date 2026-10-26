# Old Trafford paint alignment v96

The v95 14-strip grid used equal 7.5 m widths. It aligned nominal halfway and
goal positions but crossed the native goal-area front. v96 changes only Old
Trafford to 20 nearly equal strips, anchored to retained native white paint.
All other stadium patterns, the shared green/wear, lighting and assets remain
unchanged.

The important discrepancy is in the artwork, not the football rulebook.
Read-only barycentric mapping of the retained `st029_pitch_2` mesh's two pitch
sections to the accepted L/R diffuse paint found these visible line centers:

| Native painted front | Left magnitude | Right magnitude | Authored mowing edge |
| --- | ---: | ---: | ---: |
| Penalty area | 36.203 m | 36.237 m | 36.220 m |
| Goal area | 47.282 m | 47.231 m | 47.257 m |
| Goal line | 52.547 m | 52.558 m | 52.552 m |

The symmetric authored edge lies within the retained white strip on **both**
halves. A whole-mesh affine UV fit was not used to choose these values: the
native mapping has local distortion, so the audit interpolates the actual UV
triangle covering the painted sample. Paint detection and interpolation at
three positions along each front independently check the edge remains inside
the white strip.

Each half contains seven 5.174 m central strips, two 5.519 m box strips and one
5.295 m goal-side strip. The maximum width ratio is below 1.067. There is no
isolated thin end strip, and the cadence continues beyond the goal line. The
two halves retain opposite shades at midfield. Exact equal-width strips cannot
also meet every nonuniform native box front at a useful strip count; this small
spacing adjustment gives priority to the user's visible marking alignment.
Old Trafford and Anfield now share a 20-strip count but use different anchors.

Only the uniform-selected Old Trafford branch calls `nxMowingOldTrafford()` in
`source/stadium_lite_glsl.h`. There are no new samples, textures, draw passes,
uniform uploads or frame-time dependencies. The mesh, white paint, alpha and
native fine detail are not rewritten.

The ignored proof is
`local-debug/manager-review-v96/pitch/native-uv-audit.json`; it records native
mesh/blob hashes, retained white columns and the barycentric world positions.
No native mesh, texture or raw decompiler output is added to the public tree.
The optional owned-fixture regression reports clearly when these inputs are
unavailable. It does not restore missing proprietary files.

Ten focused pitch tests pass, including actual profile rendering, near-uniform
strip widths, both halves' retained native paint bounds, all accepted paint
pixels, 58 accepted shader rewrites, weather independence and minification.
The supporting lighting/math/uniform policy suite passes another 17 tests and
878 subtests. A separate 3,266-point-per-profile comparison against checkpoint
v95 keeps all six other stadium profiles byte-identical in host math output.
The diagnostic preview uses emitted shader math and these observed box/goal
fronts. It omits native lighting and fine detail and is not a Switch screenshot.
Device acceptance still needs both goal areas in Day/Night and relevant quality
levels; this audit does not establish Switch performance.

Recreate the public-data-only view with:

```powershell
python tools/preview_pitch_mowing.py --stadium 12 --output local-debug/manager-review-v96/pitch/old-trafford.png
```

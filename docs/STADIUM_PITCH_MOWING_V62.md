# Stadium pitch mowing v62

Current follow-up: [Manager review v95](MANAGER_REVIEW_V95.md#pitch-follow-up)
supersedes the historical counts, color policy and Stamford-only wear below.
Old Trafford and Signal Iduna now have uniform widths at 14 and 12 strips;
the other striped stadiums keep their separate cadence and marking anchors.

## Stamford Bridge follow-up v94

Stamford Bridge now uses narrow vertical bands in the diagnostic top view,
following the user's direction correction: a 10.5 m repeat produces 5.25 m
alternating strips along the 105 m pitch length (twenty internal edges,
with half strips at the goal lines). Contrast increases from 8.5% to 15%.
An existing smooth value-noise helper adds numerous fixed worn-grass patches
at roughly 1.5-2 m scale, subtracting at most 12% of the diffuse midpoint.
The hue remains native. Band edges and patches fade under minification;
all derivatives run before paint/spatial rejection.

This is confined to loaded shell ID 9. Other stadium patterns, weather and
downstream native detail remain unchanged. The Stamford branch adds four
arithmetic hash evaluations per pitch fragment, without extra texture reads,
assets, uniforms or draws. Host tests preserve every accepted native paint
colour and all native shader texture/alpha operations. This does not establish
Switch performance or final lighting quality. Generate an isolated diagnostic
top view with `python tools/preview_pitch_mowing.py --stadium 9 --output <png>`.
This is a preview of the emitted math, not a device screenshot.

The seven selectable stadiums now have distinct mowing arrangements. Konami
keeps its accepted bands; six imported shells receive authored alternatives:

| Stadium | Arrangement |
| --- | --- |
| Konami Stadium | Accepted original bands |
| Anfield Stadium | Narrow transverse bands |
| Etihad Stadium | Rectangular checker |
| Signal Iduna Park | Broad transverse bands |
| Stamford Bridge | Narrow vertical bands with worn patches (v94) |
| Old Trafford | Straight alternating transverse bands |
| Camp Nou | Concentric circular rings |

These are project-authored designs, not a claim to reproduce each real venue's
current groundskeeping. The selection follows the successfully loaded shell's
stable ID in the existing cached `nxStadiumProfile` uniform. If an imported
shell fails to load, the restored native stadium keeps its original pattern.
Switching matches requires no shader recompilation or new asset allocation.

## Verified material route

The existing project shader decoder inspected the legally supplied cooked
`M_Pitch_Default`, `M_Pitch_Default_night` and
`M_Pitch_Default_night_Low` fixtures. This is local package-parser evidence,
not a REA decompilation or an observed Switch render. Their SHA-256 hashes are
recorded in ignored `local-debug/match-fixes-v62/pitch-patterns/shader-audit.json`.
No proprietary shader text or texture data is added to the public tree.

The standard Day and Night maps sample diffuse RGB from `ps0` before mixing a
separate tiled detail texture. The Low Night map samples its diffuse from
`ps2`, then reads detail separately from `ps1`. Existing normalized full-body
fingerprints authorize these routes; sampler names alone do not authorize an
edit. All 20 Day, 20 standard Night and 18 audited Low Night variants receive
the diffuse change. The other two Low Night variants remain outside the existing
shader policy and pass through unchanged.

`source/stadium_lighting_policy.h` wraps the existing standard diffuse sample,
or inserts one RGB assignment after the audited Low diffuse sample. Original
samplers, UVs, texture operations, detail mixing, alpha/depth and field geometry
remain intact. Mowing is applied before native lighting, material shading and
the existing Rainy/Snow-remnant surface treatment. Player/kit materials and
unrecognized shader bodies are outside the edit.

`source/stadium_lite_glsl.h` replaces the old diffuse's broad green bands at a
0.09 linear green midpoint, close to the accepted v17 turf's measured 0.09076
mean. It preserves the sampled hue ratios and separately mixed fine detail.
Other stadium arrangements have at most 8.5% variation either side of that
midpoint before existing lighting/shading; Stamford's v94 settings are above.
Neutral painted pixels and ground outside
the bounded pitch region are returned unchanged. `fwidth` filters band edges
and fades an undersampled pattern to its midpoint. Derivatives execute before
the spatial/paint gate; stadium branches depend only on a uniform.

The added work is scalar arithmetic within the existing pitch draw, using the
existing uniform cache. Camp Nou's uniform-selected branch uses one distance
operation for equal-width circular rings; other stadiums do not run it. There
is no extra geometry, draw pass, texture sample,
texture allocation, per-frame file access, readback, or GPU query. This bounds
the implementation work; it does not establish unchanged Switch FPS.

## Verification and device boundary

The new tests execute the emitted GLSL math through the existing host adapter,
compare whole-field samples between every pair of active imported stadiums,
exercise Day/Night/weather independence, check midpoint/variation bounds,
check minified patterns, and alternate imported/Konami matches. Optional local
texture tests pass all native paint colours from the three accepted L/R/inverse
diffuses through the actual helper and require exact equality. Optional shader
tests preserve every native texture operation and alpha assignment and reject
unknown/repeated rewrites. The existing production-hook test reverses every
allowed edit back to the complete original shader body, including segmented
source passthrough.

The first pattern revision compiled the 58 changed and 58 original native
variants with both clip-space settings and four HDR macro settings:
**928 successful compilations, zero errors**. The user then requested Camp Nou
rings and Old Trafford straight bands. The updated helper passes **24 candidate
compilations, zero errors** across one representative Day, standard Night and
Low Night variant, both clip-space settings and all four HDR settings. The
follow-up also passes seven focused tests, including circle rotation/reflection
invariance, straight-band direction, all 58 audited source rewrites, native
paint preservation and complete source reversibility. The compile results are
recorded in `shape-followup-shader-audit.json`. The original compiler identity
and fixture hashes remain in `shader-audit.json`. Existing roof, climate,
weather-surface, lighting-uniform
and character/perimeter shader tests remain passing, including 628 native
shader subtests. This is host/static verification, not driver execution.

Generate a public-data-only diagnostic comparison with:

```powershell
python tools/preview_pitch_mowing.py --output local-debug/match-fixes-v62/pitch-patterns/mowing-preview.png
```

The preview executes the shipped pattern math. It draws synthetic field lines
and omits native lighting, weather and fine-detail shading; it is not a game
screenshot. Device acceptance still needs all seven stadiums in Day/Night at
the accepted High stadium/Standard player settings, both pitch halves and
distant/replay cameras, Rainy Summer/Winter, then Konami in the next match.
Compare frame pacing against the same v61 setup. No active runtime, proprietary
source assets or consolidated `FootballNX.assets` members are modified.

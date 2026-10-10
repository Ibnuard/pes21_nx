# Pitch grass feasibility audit

Date: 2026-10-11. Scope: read-only runtime/asset investigation and this report.
No runtime source, pitch asset, NRO, PAK or prepared installation was changed
for this audit. The latest candidate remains Weather Camera v13.

## Conclusion

Grass can appear less flat at low incremental cost. Actual standing blades
require geometry and cannot be promised at zero performance cost. Start with
a same-size detail-texture experiment, then consider sparse near-camera blades
only if measured frame-time headroom permits. Do not add full-field geometry
while the reported Fine-weather frame pacing regression remains unresolved.

## Evidence in this checkout

- `source/stadium_lite_glsl.h`: `nxPitchGrain` changes colour, contrast and
  existing sampled detail strength. `nxPitchWeather` adds world-anchored colour
  patches. Neither displaces vertices nor creates blades.
- `source/stadium_lighting_policy.h`: pitch edits are scoped by audited shader
  fingerprints. Existing samplers and draws remain native. There is already a
  safe place for pitch-only experiments, but new normal/parallax instructions
  would need separate validation, including Night/Low permutations.
- `tools/build_efootball10_visual_patch.py`: the authored `clean-v17` recipe
  uses seeded noise rather than blade-shaped detail; it retains the native
  detail alpha channel. `tools/recreate_custom_pitch.py` reuses native material
  layouts rather than constructing grass geometry.
- Read 60 locally owned cooked fragment permutations: 20 each from
  `M_Pitch_Default`, `M_Pitch_Default_night`, and
  `M_Pitch_Default_night_Low` in the optional `local-debug/pitch-recreate/native`
  fixture. Static texture-call sites span 4–15 for Day and 3–14 for both Night
  materials; these include lighting/shadow branches, not per-pixel executed
  sample counts or GPU timings.
- In the representative Day permutation, tangent-space normal starts at
  `(0,0,1)` and transforms through the mesh basis. The tiled detail sample
  contributes RGB and angle-dependent alpha shading; another map contributes
  view-dependent directional response. This is **not** evidence of real blade
  geometry or a ready-made parallax height channel. In particular, do not
  overwrite existing alpha as if it were unused.
- Texture metadata in that native fixture: `pitch2_bsm_alp_copied` is
  512×512 `PF_B8G8R8A8`, 10 mips; `pitch_l_bsm_alp` is 1024×1024 `PF_ETC1`,
  one stored mip; `pitch_specular_mask_l` is 512×512 `PF_B8G8R8A8`, one stored
  mip. These describe the fixture, **not a verified dump of the currently
  installed Switch textures**. A new recipe must inspect its exact baseline.
- The inspected stadium mesh directory has pitch and pitch-side meshes and
  no asset named grass/turf. This name inventory is not proof that every game
  package lacks grass. No claim about hidden native grass activation is made.
- Local UE4.22 `MobileBasePassVertexShader.usf` applies material world-position
  offset to existing vertices. That can bend already-authored grass blades;
  moving a flat pitch mesh alone cannot create individual blades. Generic
  engine feature support also does not establish a working wrapper ABI path.

## Options and tradeoffs

| Approach | Visible result | Incremental work | Audit recommendation |
| --- | --- | --- | --- |
| Same-size replacement of existing detail RGB | Blade-like fibres and small baked highlights; silhouette remains flat | No new sampler, draw, geometry or shader instruction if format/mips/material stay identical | First experiment |
| Small normal/height shading enhancement | Lighting responds to microstructure; still no true silhouette | Extra arithmetic and possibly texture reads; high-frequency shimmer risk | Second, gated by camera distance and pixel footprint |
| Sparse standing blades near a close camera | Real raised tips and silhouette around boots/ball | Added vertices, masked coverage, draw/setup/lifetime cost | Optional close-up/replay experiment |
| Multiple shell layers over the entire pitch | Apparent volume from stacked layers | Repeated shading/overdraw over a large screen area | Avoid as the first Switch experiment |
| Full-field dense grass or iterative parallax | Potentially strong close-up depth | Unbounded density or multiple dependent reads without careful limits | Not justified by current evidence |

Texture-only is the closest to a neutral rendering budget, not a guarantee of
identical FPS: cache behaviour, visible aliasing and mip generation still need
checking. Normal mapping is not automatically cheaper than all geometry.
Masking instanced blades reduces object/draw overhead but does not remove
fragment overdraw, alpha-test or shadow cost.

For scale only, with an assumed 50° vertical FOV at 720 pixels, a 3 cm feature
perpendicular to the view projects to approximately 0.77 pixels at 30 m,
0.39 pixels at 60 m, and 0.23 pixels at 100 m. At 576 pixels these become
0.62 / 0.31 / 0.19 pixels. These are illustrative projection calculations, not
measurements of the game's actual camera; foreshortening can reduce them
further. Distant blades should disappear into filtered texture detail rather
than remain exaggerated, flickering high-contrast lines.

## Proposed experiment, not implemented

1. Keep the currently accepted pitch colours, stripes, paint and texture alpha.
   Bake restrained, directional short fibres into the existing detail RGB at
   the same dimensions/format. Retain the complete mip chain and reduce
   contrast in distant levels. Do not simply sharpen noise or enlarge textures.
2. Compare the exact same camera path, teams, weather, graphics settings,
   referee state and dock/handheld mode against v13, with a cold launch for
   each build. Establish whether v13 already fixes the reported pacing issue
   before combining it with another feature.
3. Check Day/Night, Fine/Rainy, Winter remnants, distant broadcast cameras and
   close replay. Verify markings, mip seams, shimmer during fast pans, loading
   time and repeated-match memory behaviour. Use v13 presentation-interval
   logs as an initial A/B signal; they cannot identify GPU cost by themselves.
4. Only if there is headroom, prototype a single pooled patch of sparse blade
   clusters around the **camera's visible ground area**, not around the ball.
   Try an initial 2,000–4,000-triangle ceiling and fade out as blades become
   subpixel. This is a proposed test budget, not a measured safe limit.
   Disable collision, dynamic shadows and per-blade actors/ticks. Keep normal
   broadcast gameplay on texture detail alone at first; fade rather than pop
   and do not rebuild/upload the mesh every frame.
5. Do not promise 60 FPS from a triangle count. A 60 Hz frame allows about
   16.67 ms for the whole frame; if the baseline already exceeds that, any
   additional geometry requires a demonstrated saving elsewhere. Reject the
   experiment if frame intervals, shimmering or memory/lifecycle stability
   regress. No grass movement, player interaction or collision is in scope.

## Primary reference

[Epic UE4 mobile performance guidelines](https://dev.epicgames.com/documentation/en-us/unreal-engine/performance-guidelines-for-mobile-devices?application_version=4.27)
explain the cost of masked/translucent overdraw, texture instructions and
material complexity. This is general UE4.27 guidance, not measured performance
for the UE4.22 Mobile binary running through this Switch wrapper. The local
shader/asset findings above are the compatibility evidence for this project.

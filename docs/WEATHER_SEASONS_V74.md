# Seasonal precipitation and slow cloud shade v74

The user accepted v73 rain/mist on Switch and requested snow in Rainy + Winter
and slowly moving cloud shadows on a Cloudy pitch. Winter uses small falling
flakes as the main effect, with much thinner cold distance haze. This is not a
device frame-time measurement or a claim of zero rendering cost.

Summer retains the exact v73 RainField payload. A separate optional snow PAK
adds a 256-flake field: two crossed quads per flake, 1,024 triangles total,
6 cm wide/high, falling at 1.5 m/s with gentle shader sway. Only one seasonal
mesh is spawned. There are no per-flake actors, image textures, collisions,
shadow casting or CPU vertex uploads. The existing deferred live-match gate,
pause clock, repeated-match cleanup and weak-object retirement remain.
The material clock loops seamlessly at 24 seconds. Winter retains the accepted
patchy ground remnants. Native wetness/rain physics and weather enums remain
unchanged; presentation alone selects the snow mesh.

Winter haze uses 35% of Summer's optical density, with bounded Day/Night
blends of 18%/12% and a cool neutral colour. Summer mist coefficients are
unchanged. Fine and Cloudy retain their exact mist-free colour path.

Cloud shadows modulate only audited pitch diffuse receivers, including white
lines. Two broad soft analytic shapes move about 20 cm/s along the field and
15 cm/s across it, with at most 10% darkening. The field is periodic without a
phase-wrap jump. There are no noise octaves, trigonometric fragment operations,
new texture reads, fullscreen passes, render targets or shadow maps. Fine,
Rainy, Night, players, audience and non-pitch geometry receive no cloud shade.
The shared native match clock pauses and resets with its world; the render
thread reads an atomic quarter-second step. Each active pitch program updates
its cached motion uniform at most four times per second, rather than per draw.
Unknown/depth-only shaders and native alpha/depth remain untouched.

Build/cook serialize with the face factory through exact owned-process
receipts. No active runtime or face source/recipe is changed. The candidate
retains every v73 payload except its NRO and adds the snow PAK. The composed
loose-CPK manifest, cinematic marker, commentary, real faces, referee,
scoreboards and v73 rain PAK remain exact. Host lifecycle/math/cook/shader and
package checks remain separate from Switch appearance and frame-time testing.

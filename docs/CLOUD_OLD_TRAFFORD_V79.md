# Cloudy final-colour receiver and Old Trafford surfaces

Device feedback includes a v77 log from Cloudy, Day, Summer at Camp Nou, Old
Trafford and Stamford Bridge. Its native world clock advances past eight
seconds in each match. That evidence rules out the stopped/missing clock
explanation for these runs; it does not prove which GL program displayed the
cloud function. No shader-cache purge or cache-hit cause is inferred.

The old implementation shaded the pitch diffuse texture inside mowing,
before native detail mixing, indirect/direct lighting and additive sheen.
Those later terms can fill in the diffuse-only shade. V79 moves the single
analytic cloud evaluation to the completed pitch colour in the allowlisted
native pitch shaders. Mowing no longer calls the cloud function. Existing
motion, two soft shapes, 20% linear-radiance darkening limit, world-space
coordinates and four-updates-per-second uniform cache remain. Fine, Rainy,
Night and non-pitch geometry keep the disabled path. Native texture reads,
alpha, depth and particle fields are unchanged; no render pass, image sample,
mesh or shadow map is added. This is a receiver correction, not a measured
zero-cost claim.

Two bounded `cloud receiver` messages per boot identify an actual program
with a live cloud uniform and its uploaded phase. They run only when the
cached uniform changes. The existing world-clock messages are separate;
neither message is a GPU timing or pixel-readback probe.

The Old Trafford screenshot shows gaps beneath steps and crowd platforms.
The existing source-bound v34 surface conversion addresses this geometry
loss from the v31 global reduction: two named original stair materials retain
dedicated simplification budgets and a continuous underlay from their source
footprint. This candidate reuses that independently checked PAK rather than
recooking unrelated stadiums. Its 24,522 cooked triangles include all 6,496
crowd triangles and four material sections, below the 24,560 native reference.
Camera cutaway, atlas policies and native-apron protection remain active.

The canonical `PesMobile-OldTrafford-Android_ETC1_P.pak` replaces the existing
Old Trafford namespace. Its 28 members are independently unpacked, decoded,
namespace checked and tested with UnrealPak. Actual cooked geometry, texture
encoding, atlas IDs, crowd counts and apron checks are separate from the
prepared-mesh comparison previews. The near/goal views are offline diagnostic
renders, not Switch acceptance.

The complete update inherits the v78 final skin candidate: all 1,638 head
payloads and its 436 existing-row corrections remain byte-identical, as do
the current cinematic-compatible manifest/marker pair, Serie A assets, Camp
Nou, adboards, commentary, referee and rain/snow packages. Only the NRO changes
and the corrected Old Trafford PAK is added to the ready-copy set. Device
visibility, coverage across all cameras and frame time still require testing.

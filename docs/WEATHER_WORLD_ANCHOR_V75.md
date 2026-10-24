# Fixed world-space precipitation v75

The user sees falling snow shift/jitter when the camera moves, and explicitly
requests the same correction for Rainy rain. V74 projected the camera onto the
pitch every world tick and translated the whole particle component whenever
that focus moved over 50 cm. This changes the world positions of every airborne
particle at once. V75 removes the camera getters, projection and component
relocation binding entirely.

One field is spawned at world origin with unit scale and stays there until its
match world retires. New RainField/SnowField meshes distribute the same 256
particles over the entire playable pitch, instead of concentrating them in a
camera-centred 56 by 42 m area. This lowers local particle density while keeping
coverage on both halves and the same active cost: one component, one primitive,
2,048 vertices and 1,024 triangles for the selected seasonal field. There are no
per-particle actors, camera-history buffers, CPU geometry uploads, new texture
reads or additional active draws. Each drop/flake keeps its authored world
trajectory; only the existing fall/wind material clock changes its position.

The v74 rain/snow sizes, speed, wind, masks, pause/lifecycle behaviour, thin
Winter haze and slow Cloudy shadows remain. A separate WeatherWorld PAK carries
both seasonal meshes/materials; the NRO selects one field. The older WeatherLight
and WeatherSnow payloads remain exact in the update set, and are not instantiated
alongside it. Missing the new PAK leaves native wetness/physics intact. Never
install a half-updated CPK manifest/cinematic pair.

Host tests use both kinds through camera pans, zooms and cuts with no camera API
bound, enforce fixed spawn transforms and continuing fall clocks, and exercise
repeated matches, pause, missing assets and weak retirement. Independently export
both cooked meshes and validate embedded shaders, PAK allowlist/roundtrip/Test,
NRO/ELF/pinned payload hashes and ZIP CRC/member hashes. These checks do not prove
device appearance or FPS. Build/cook serializes with the existing face factory;
resume its exact owned processes on success or failure. No face recipe/source,
active runtime, proprietary input or unrelated dirty work is changed.

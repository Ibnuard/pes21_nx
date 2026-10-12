# Camp Nou trial and retirement of two stadiums, v30

Following the user's Switch tests, San Siro and Santiago Bernabeu are no
longer selectable. Historical IDs 6 and 7 remain reserved for safe shell
recognition and logs. Old PAKs cannot re-enable them. Camp Nou is appended at
ID 13, so no existing stadium changes identity.

The available menu, when all retained PAKs are installed, is Konami Stadium,
Anfield Stadium, Etihad Stadium, Signal Iduna Park, Stamford Bridge, Old
Trafford and Camp Nou. The current conversion manifest is
`data/stadiums/fl26_selected_v30.json`; earlier manifests remain historical.

## Owned source and conversion

The local FL26 team map identifies Barcelona's stadium as `st002`. The model
is in the owned `Data/dt30_g4.cpk`, with a matching audience and complete
textures. `extract_fl26_stadium.py` extracts only its nested shell, audience
and texture members, without copying the outer CPK. All game payloads stay
ignored under `local-debug/stadium-campnou-v30/`.

Camp Nou's seating file has header `(4,0)`. Its 12 absolute section pointers,
group layout and 96-byte quad records match the existing bounded parser. The
reader now accepts that exact header, retaining all pointer, count, finite
coordinate and bounds checks. Synthetic tests cover multiple groups, empty
tiers, invalid pointers and unknown `(4,1)`; no game fixture is committed.

The reviewed tier/detail list excludes probes, rain alternatives and the
temporary cover mesh. It reduces 83,994 trimmed source shell triangles to a
30,000 budget, then clips coplanar apron surfaces against the exact retained
native floor. The resulting shell has 29,153 triangles and 9,250 crowd
triangles. All 4,625 fitted audience rows keep the native 16-frame sheet at
8 fps. Sixty-seven material slots become seven atlas/crowd materials.

The static shell uses the v27 vertex lighting, source one/two-sided and
cutout flags, conservative vertex camera culling and pixel cutaways. The v28
floor repair includes nearly horizontal faces from -25 cm to +6 cm at the
pitch plane, including slightly buried source apron slopes. The original
native pitch, goals, gameplay lights and collision remain the carrier.

Camp Nou also needs `repair_stadium_apron.py --floor-min-height -0.25
--omit-native-floor-decals --raise-floor-material
M_st002_redc200_kt_bsm_solid_one`. The decal option removes only flat,
near-ground, masked source paint/debris atlas entries. It removes 764 source
triangles; 205 retained opaque carpet triangles are raised 3 cm above their
concrete base. This adds no triangles, material passes or runtime work.
The final cooked mesh has zero near-coplanar overlaps with the native floor
and zero near-coplanar parallel self-overlaps across 8,753 sampled apron
points. Forty-nine close-height intersections remain at angled step joints
(7.15-64.98 degrees), not parallel overlapping floor layers. The sampling
audit is not a claim that every possible raster artifact is excluded.

## Single-sided roof

Only the +Y stand has a roof. Fitting `front3/st002_roof001` to the existing
rounded panel proxy gives 88.95% plan-mask overlap. The other three roof
panels stay disabled. The measured median height is 40.8171 metres; the
runtime uses a 26 metre projection height as a deliberate higher-sun visual
policy to keep the shadow close to that touchline.

No shader code, draw calls, lights or shadow maps are added. This uses the
existing cached uniform and partial-panel path. Pitch and player height
remain aligned along the same light ray, with soft edges and weather
attenuation. Exact emitted shader math at 28,907 pitch points measures
3.48% shaded coverage in Fine/Summer and 12.71% in Fine/Winter with the
representative existing sun. These are coverage measurements, not FPS.

## Verification and installation

The focused suite passes 38 tests and 42 subtests. It covers the updated
manifest, retired PAKs remaining installed, a Camp-Nou-only installation,
sparse menu indices, roof upload/cache behaviour, both seasons and matching
player/pitch light. The offline camera audit clears all 30,240 tested rays;
the conservative-culling audit removes no visible samples in its near/far
views. The cooked result preserves all 9,250 crowd triangles, five UV
channels, seven materials and a minimum 23.65 cm camera-bound margin.
All 160 unique cooked material shader variants compile. Repacking round-trip
and UnrealPak's independent check validate all 49 payload files; the PAK is
5,037,512 bytes. The native lighting shader is byte-identical to v28/v29.
The NRO builds with the existing runtime identity `e861c583ec78e9ae` and the
53,248-byte patch OBB. Its scene header is `FootballNX scene v30 session`.

The update consists of the v30 NRO and Camp Nou PAK. Retain the accepted
Anfield package and the v28 Etihad, Signal Iduna, Stamford Bridge and Old
Trafford PAKs. The San Siro and Santiago Bernabeu PAKs can be removed from the
SD card to reclaim space; leaving them installed does not restore their menu
entries. Realfaces, physique data and saves do not require an update.

This is a Camp Nou trial, not hardware acceptance. On Switch, compare DAY
and NIGHT near both touchlines, midfield and goals, cross the roof boundary,
and inspect replays/celebrations in all corners. The offline renders use a
reference pitch and omit the native apron; the game uses its retained native
floor there. Frame pacing and loading time still require the device test.

# Cloudy contrast, horizontal corner controls and Old Trafford backing

Device feedback confirms the v79 Cloudy receiver is visible. V80 changes its
linear darkening limit from 20% to 42%. The same two soft shapes, world-space
coordinates, drift and cached 4 Hz phase remain. The receiver still runs once
after the native pitch colour, with no new image fetch, render pass, shadow map
or mesh. Fine, Rainy, Night and non-pitch gates remain. Switch frame time and
the final perceived contrast require device testing.

Horizontal single Joy-Cons now use logical L1 (SL or the existing L alias) as
a held corner modifier. The left grip's directional buttons and the right
grip's YXAB buttons select by their position in the horizontal grip. The
existing profile rotation supplies logical X/up, A/right, B/down and Y/left;
the right panel displays the physical Y/up, X/right, A/down and B/left icons.
R1 (SR or R) changes the attacking/short-corner page while L1 stays held.
Releasing L1 closes the panel. Native input and the taker chord are isolated
for that owner while the modifier is active, including remaining buttons on
release. Page changes and choices use button edges; a held key does not repeat.
Full controllers keep Left to open, B to close and X for the short page.
Restart ownership, the corner-only native guard and independent pad epochs
remain. Pause, disconnect, profile changes and restart changes cancel the
modal state and require release before another corner action.

The v34 Old Trafford stair repair in v79 did not include the original outer
backing, transparent roof sheets or enough of its lower facade. The final
local recipe restores 781 triangles from owned st007: 250 upright cover walls,
208 roof/end faces, 315 opaque structural faces and the eight-triangle original
underground annulus. Exact source indices, bounds and FPK/glTF/buffer hashes
bind each selection; material primitives with repeated names require an
explicit ordinal. The floor remains outside the protected playing surface.
The original PC glass diffuse has uniform alpha 13/255 and depends on a
reflection technique absent from this port. The added end panel therefore
uses the existing opaque roof atlas as structural backing, explicitly rather
than pretending to reproduce that translucent material. The owned glass
texture is untouched. No donor stadium or invented extension of the roof
silhouette is used. Open sky above the lower roof follows the original source;
it is distinct from missing roof sheets and gaps below the bowl.

All 24,522 base triangles, including 6,496 crowd triangles, keep their
positions, UVs, colours, material slots and camera policy. The resulting
25,303 triangles exceed the 24,560 reference by 743 (3.03%). An explicit,
Old Trafford-only completion ceiling of 25,320 preserves the accepted base
instead of removing stairs or crowd to accommodate missing structure. Other
recipes retain the default reference ceiling. Each added face reuses an
existing opaque one-sided tile; no material section, image fetch or render
pass is added. Shipped texture and shader payloads remain exact. Source and
cooked coverage, material integrity and offline previews are host evidence;
they do not prove every stadium camera is visually accepted or unchanged FPS.

The isolated UE4.22 cook uses explicit package names with single-package mode.
That engine ignores CookDir in this mode; the ordinary cook instead takes a
filesystem CookDir. The final mesh is independently unpacked and exported,
and its 26 non-mesh PAK members must remain byte-identical to v79.

The combined candidate must inherit all current v79 runtime payloads, replacing
only its NRO and canonical Old Trafford PAK. In particular all 1,638 face
payloads, 436 v78 skin corrections, current Serie A assets, adboards, Camp Nou,
commentary, referee, precipitation packages and the cinematic-compatible
24-CPK manifest/marker pair remain exact. Local recipes, previews and binary
verification belong in ignored `local-debug/cloud-corner-stadium-v80/`.

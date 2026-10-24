# Camp Nou portal backing v77

The white rectangles in the supplied image are behind the crowd at the top
of that camera frame, rather than pitch or apron holes. Actual pixel rays
from the matched far-view diagnostic miss the imported bowl entirely. The
historical shell selection omitted the source backing underneath and around
the stands, so these entrances expose the bright background.

The existing v34 surface candidate restores stair boundaries lost by the
older v31 global reduction. It still shows the repeated white entrances in
the matched far-view diagnostic. This candidate uses that scoped Camp Nou
surface repair and restores the relevant backing from the owned source
`cover` member. Its 84 upright faces run from -5.007 to 25.785 metres. The
matched downward rays pass below their lower edge before reaching the wall,
so the source's 42-triangle underground floor is also needed. Its exact
outline is preserved, with the protected 58-by-40-metre half-extent rectangle
subtracted as a real hole. The resulting floor has 46 triangles and no area
overlap with that exclusion. The roof, distant outer floor and probe glass
are excluded. Higher glass and wall-only trials did not change the matched
diagnostic and are not represented as working fixes.

`stadium_backing.py` binds both the intermediate and buffer hashes, exact
material, height band and face count. Host floor clipping seals a source-bound
receipt. Blender rechecks its hash, source plane and triangle selection,
field exclusion and containment in the original source floor. Nonfinite
coordinates, unreviewed transforms and changed source selection are rejected.
`restore_stadium_backing.py` preserves the reviewed base geometry,
crowd, UV channels, colours and material slots, then adds the original
backing positions with inward-facing winding. It never edits the owned FPK.

The added faces use the existing plain-concrete atlas tile and its source
material policy. No atlas image, texture, shader graph, material section or
camera cutaway is added or replaced. This is a lightweight conversion of
source backing into the port's established unlit concrete material, rather
than a port of the PC temporary-view lighting technique.

The candidate contains 24,458 total triangles, including all 9,250 crowd
triangles and the same five material sections, below the 24,560 reference
budget. It does not assume that v34 was installed on the user's Switch.
Other stadium PAKs are outside this change.

Local recipes, source-frame/cooked coverage reports, diagnostic previews and
payloads remain ignored under `local-debug/stadium-camp-gaps-v77/portal-final/`.
Geometric coverage and offline rendering are not Switch appearance or FPS
acceptance. The canonical replacement PAK retains the existing Camp Nou
filename and namespace so it replaces the old shell rather than stacking
another override.

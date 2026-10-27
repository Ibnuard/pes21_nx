# Signal Iduna central stair access v99

The new screenshot isolates two sky-coloured strips at the central lower-tier
stair access. In the matching host camera, rays through those strips miss the
v98 structural mesh. The original Fox glTF contains the corresponding narrow
treads and risers. This is separate from the large concrete/walkway surfaces
and bench foundations repaired in v98.

The independently exported v98 cooked mesh retains none of the 170 exact stair
triangles selected around the two central accesses. Its adjacent concrete and
side panels also need protection: only 12 of the full 234 selected access
triangles survive unchanged in v98. The materials were protected from the main
detail decimator, but their disconnected small faces still entered the
spatial-clustering fallback. That fallback can erase narrow treads, risers and
portal borders together.

`data/stadiums/signal_surfaces_v99.json` extends the v98 recipe with one bounded
selection for those 234 original source faces across six materials. The
selection uses both side accesses, their height and their measured central
width; a changed source count fails conversion. Existing source positions and
per-corner UVs are retained.
No replacement slab is drawn across an access, and the v98 recipe remains
unchanged for reproducing the previous package. Other stadium recipes retain
their prior behaviour.

The final asset preparation reuses the verified v98 atlas layout after checking
all active source texture fingerprints. It retains one unused source tile
rather than shifting the other tile numbers. This keeps the material and
texture payloads stable while redistributing the existing structural triangle
budget toward the missing access surfaces.

`tools/audit_stadium_preserved_faces.py` independently checks the source against
the cooked mesh exported by UModel. It binds every corner position to its UV,
requires the original atlas material/tile, and rejects missing or duplicate
triangles. Synthetic checks exercise damaged positions, UVs and duplicate
geometry as well as successful changes in triangle corner order.

All 234 selected triangles match the final cooked export, with a maximum
position difference of 0.000004471 metres from the FBX/UE float round trip.
The local UModel export represents 48 tiny UV components with a half-subnormal
mapping; its maximum raw UV difference is 1/32768, less than 0.008 atlas texel.
The audit recognizes only that measured subnormal mapping and keeps its strict
tolerance for other UV values. This is an export precision limit, not evidence
that the material or texture payload changed.

The verified package has 24,553 triangles, including the unchanged 9,848 crowd
triangles, seven sections and five UV channels. Crowd positions, normals,
vertex colours and primary UVs are byte-equivalent in the independent exports.
All 44 non-mesh package members are exact matches to v98. Independent unpack,
UnrealPak, namespace, apron, camera, overdraw and shader checks pass. Four
authored-material previews cover both sidelines and both goal ends. The
reported central portal region has 488 sky-coloured pixels in the v98 preview
and zero in the matching final preview; that classifier is a host diagnostic.

The detached replacement is `PesMobile-SignalIdunaPark-Android_ETC1_P.pak`,
3,680,693 bytes, SHA-256
`023c1188157b2e9bff0fdd3197e0f3b61de70f452100dba057ce3a0f301c137f`.
It retains the existing namespace and filename. Its verified payload and
receipts are under the local investigation's `final/` directory; earlier
`complete/` files are an intermediate treads-only diagnostic.

Twenty-five focused host tests pass with the local meshoptimizer and Shapely
fixtures available:

```powershell
python -m pytest tests/test_stadium_surface_reduction.py tests/test_stadium_backing.py tests/test_stadium_preserved_faces.py -q
```

All native input geometry, generated mesh/package files and visual evidence
remain ignored under `local-debug/stadium-signal-stairs-v99/`. Host structural
and material previews do not establish Switch appearance or performance.

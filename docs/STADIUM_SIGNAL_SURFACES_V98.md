# Signal Iduna lower-tier surfaces v98

The reported pale strips below the crowd and behind the goals are reproduced
by the reduced shell, including an offline view with the native apron kept.
They are gaps in the structural coverage: the original converted concrete
and walkway faces cover those areas. The known unavailable small sign texture
does not account for these long strips. The screenshot alone does not identify
which historical Signal Iduna package is installed.

The older v28 shell and the v31/v34 reduced candidates were compared in the
same four geometry views. In the front view, low source-covered pixels exposed
to sky number 662 in v28, 14,083 in v31 and 9,500 in v34 at the diagnostic
800-by-450 resolution. These counts exclude crowd, treat geometry as opaque
and do not model material alpha or the camera cutaway. They are a structural
regression diagnostic, not a device-rendering or frame-time measurement.
The independent authored-material previews also show the continuous gap in
v34 and mostly intact v28 lower-tier coverage.

The reducer already protects whole stairs but its historical material-name
selection misses Signal Iduna's concrete (`cncr`) and walkway (`flor`) names.
The scoped recipe in `data/stadiums/signal_surfaces_v98.json` supplies eleven
exact concrete, walkway and perimeter-panel materials to the border-aware
stair reducer. It also retains 948 original wide/upper stair faces before
clustering. Their reviewed dimensional/height rules have exact source-count
checks. Other stadium recipes and the default material selection keep their
previous behavior. Missing, duplicate or changed selections fail conversion;
the source fingerprints, recipe and policy form the input contract.

This rebuild starts from the owned source intermediates, preserving original
UVs, surface flags and native crowd placement. It does not try to reconstruct
faces from the already damaged reduced mesh. Protected surfaces fit 12,387
triangles at the existing maximum clustering tolerance of 0.008. The remaining
14,712 structural target covers other detail. There is no runtime material,
culling, camera or pitch shader change.

Two small bench-edge gaps have a separate cause: the source's low wall lies
inside the existing celebration camera cutaway, while the retained native
apron does not cover the view behind it. `signal_foundation_v98.json` defines
two **project-authored underground foundation quads**, not unchanged source
faces. Their four upward triangles lie at -0.6 m, below the -0.5 m cutaway
bottom and outside the protected 58-by-40-metre half-extent rectangle. They
reuse the existing concrete tile and section. Original positions, faces,
material indices, UVs and baked-light colours remain exact. Blender normal
re-encoding differs by at most 0.033 degrees; the unlit baked colours are
unchanged. No native pitch or adboard asset is replaced.

The independently unpacked final mesh has 14,705 structural and 9,848 crowd
triangles: **24,553 total**, below the 24,560 reference, with seven sections
and five UV channels. Nineteen focused tests pass. The 46-member PAK passes
namespace/round-trip and UnrealPak checks, 48 shader compiles, 30,240 camera
rays and 57,024 conservative-cull samples. The 8,753-position apron audit
finds no close native/self floor overlaps. All 44 non-mesh members are exact
matches to the verified pre-foundation candidate, including every material
and texture payload. Four authored-material previews show the repaired
strips; these are host checks, not Switch appearance or FPS acceptance.

The canonical replacement is `PesMobile-SignalIdunaPark-Android_ETC1_P.pak`,
3,682,221 bytes, SHA-256
`bbdc747a9405463600a070f30d9d6fd2c27c3bdb33a36bb6472c7dfae592724b`.
It retains the existing namespace/filename and must replace the older Signal
package. The active runtime has not been modified.

Local inputs, geometry, previews and any candidate packages remain ignored in
`local-debug/stadium-signal-gaps-v98/`. Preparation and asset validation are
recorded separately from installing a package or testing it on Switch. The
validated payload and terminal receipts are in its `complete/` subdirectory.

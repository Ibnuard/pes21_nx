# Stadium performance v26

The user reports slow loading in all ten v25 addon stadiums and poor frame
pacing under roof shade. This candidate reduces the imported asset costs and
the curved-roof receiver's arithmetic. It has not been measured on Switch;
asset sizes and host operation counts are not frame-time measurements.

## Model and material budget

The ten shells now target 35,000 triangles each, down from 51,858–100,000.
Crowd geometry is separated before reduction and rejoined afterwards: every
previously fitted row, its position, UVs and native 16-frame/8-fps animation
remain. Roof openings and the native pitch are preserved. Reducing the mesh
does simplify small props and distant stadium detail.

Static textures are grouped into 1,024-pixel atlas pages, with sixteen
240-pixel tiles and wrapped eight-pixel gutters. UV0 retains the source's
repeating coordinates; UV1.x stores a constant tile ID per triangle. Material
sections fall from 26–107 per venue to 4–8, including the crowd. This reduces
the material/shader objects loaded and draw sections submitted for each shell.
Small texture detail is softer than v25's up-to-512-pixel individual textures.

RGB and cutout coverage are compressed as separate ETC1 textures. This avoids
the BGRA8 expansion previously required for alpha textures in Android_ETC1.
Crowd RGB and coverage retain the full original 1,024-pixel sheet before
compression. Mask edges can differ slightly due to ETC1 quantization; the
decoded cutout coverage is audited, with a maximum allowed mismatch of 2%.
Static cutout coverage is resolved at the existing 0.4 threshold before
compression, avoiding broad glass/roof panes flipping visibility when source
alpha is close to the threshold. Native crowd coverage remains unquantized
until texture compression.

The ES3.1 atlas samples use derivatives of the continuous source UV, before
wrapping, to avoid selecting a coarse mip at every texture repeat seam.
UE4.22's legacy ES2 path receives an ordinary sampled fallback via a compile-time
feature-level switch; its gradient sampling is unsupported. The fallback can
show coarser filtering at repeated seams. Packaging requires both ES2 and ES3.1
shader maps and rejects a failed material cook rather than shipping defaults.

The v17 camera cutaway remains on the shell and crowd. The offline audit
still finds zero uncleared fragments in 30,240 sampled camera/player rays
per stadium. The projected roof footprint overlap against v25 is 96.4–100%
on the measured one-metre grid. Those audits do not cover every native camera.

## Roof lighting

The imported ring classifier tests squared distances first. Square roots and
soft-edge smoothing are only needed near a curved light/shade boundary;
fully shaded and fully open regions take shorter paths. The full-ring panel
flag is calculated when uploading a stadium profile, avoiding four panel
selection branches for the current fully roofed profiles.

Roof height, contour, seasonal direction, cloudy/rain attenuation, edge
softness and player-height projection are unchanged. The accepted Konami and
Anfield v20 equations are unchanged. Player, face and pitch receivers still
share the same shadow; direct light retains 12% and ambient light 56% in full
shade. No shadow texture, extra light, draw pass or per-frame actor is added.

The emitted shader is compared against frozen v25 equations across 4,020,640
samples, including curved boundaries, partial panel gates and edge widths.
Visibility agrees within 0.0002. Counted square-root calls fall from 5,528,839
to 401,771 (92.7%) in that test; this is a host source-path count, not GPU time.

## Repeatable conversion

Use a separate ignored workspace. The existing v25 prepared files are read
only; neither game source inputs nor an installed runtime are overwritten.
`optimize_stadium_batch.py` needs a local config containing `blender` and
reuses the reviewed ten-addon registry in `data/stadiums/fl26_addons_v25.json`.

```powershell
python tools/optimize_stadium_batch.py --config <local-config> --source <v25-work> --work <new-work>
python tools/cook_stadium_batch.py --config <cook-config> --work <new-work> --keys <stadium-keys>
python tools/audit_stadium_optimization.py --config <cook-config> --work <new-work> --output <fresh-audit-dir>
```

Cook config requires `editor`, isolated UE4.22 `project`, `repak` and `umodel`.
Keep the same GLES feature settings documented in the v25 guide. Existing
prepared output requires `--rebuild`; the cooked audit requires a fresh output
directory to avoid accepting stale exports. The new atlas, FBX, UE project,
game textures and PAKs all remain local and ignored.

The converter removes orphan vertices when separating the crowd from the
shell: they do not render, but can incorrectly inflate the exported bounds.
The actual imported mesh bounds, material slots, triangle count, atlas tile
IDs, alpha masks and texture format are checked after cooking. `repak` output
is unpacked and compared byte-for-byte, then checked independently by UnrealPak.

## Device comparison and installation

This is a paired **NRO plus ten replacement PAKs** update. Copy the contents
of its `update/` directory over the existing `switch/pes21_nx/` installation;
the PAK filenames match v25. An NRO-only install does not reduce model loading
cost. The accepted Anfield PAK, realfaces, physique dataset and saves remain
compatible. Runtime identity is `e861c583ec78e9ae`, patch OBB size 53,248 bytes.

Use High quality and compare the same teams, camera, weather and season.
Check DAY passing under roof shade and across its boundary, then NIGHT, and
celebrations in all corners. Check loading both on first entry and when
switching stadiums. Pause after each comparison to flush presentation timings
and retain `scene-runtime.log`; the header is `FootballNX scene v26 session`.

Restore the previous NRO and v25 versions of the same ten PAKs to compare or
roll back. The source of the reported frame-time issue is not fully isolated
without a hardware capture, and this candidate does not promise 60 FPS.

## Measured asset comparison

| Stadium | Shell triangles, v25 to v26 | Materials, v25 to v26 | PAK MB, v25 to v26 |
| --- | ---: | ---: | ---: |
| ETIHAD STADIUM | 100,000 -> 35,000 | 68 -> 6 | 15.51 -> 4.82 |
| GIUSEPPE MEAZZA | 52,038 -> 35,000 | 31 -> 4 | 7.73 -> 3.27 |
| PARC DES PRINCES | 75,456 -> 35,000 | 49 -> 5 | 10.69 -> 4.37 |
| RAMON SANCHEZ PIZJUAN | 100,000 -> 35,000 | 66 -> 6 | 13.56 -> 4.85 |
| SAN SIRO | 51,858 -> 35,000 | 31 -> 4 | 7.98 -> 3.27 |
| SANTIAGO BERNABEU | 99,999 -> 35,000 | 67 -> 6 | 13.76 -> 5.05 |
| SIGNAL IDUNA PARK | 100,000 -> 35,000 | 107 -> 8 | 19.22 -> 5.23 |
| STAMFORD BRIDGE | 100,000 -> 35,000 | 68 -> 6 | 13.04 -> 4.72 |
| TOTTENHAM HOTSPUR STADIUM | 99,999 -> 34,999 | 65 -> 6 | 15.03 -> 5.25 |
| WANDA METROPOLITANO | 100,000 -> 35,000 | 26 -> 4 | 11.70 -> 3.74 |

Totals: PAK size 128,228,669 -> 44,575,425 bytes (65.2% smaller), archive
members 2,864 -> 367, shell triangles 879,350 -> 349,999, and materials
578 -> 55. All 40,581 fitted crowd rows remain. Cooked texture bulk payload
falls from 179,532,288 to 55,009,280 bytes; this is file payload, not a measured
peak GPU/RAM allocation or loading time.

## Final local verification

- 61 focused tests and 359 subtests pass, including the frozen roof-equation
  comparison, repeated/negative UVs, read-only source textures, near-threshold
  glass coverage, sparse installations and cached roof uniform uploads.
- 706 eligible native shader variants compile before/after rewriting under
  both clip-space definitions: 2,824 successful compilations.
- The 55 cooked materials contain 770 shader records. All compile under the
  two clip-space and four native HDR header configurations (160 unique source
  compilations after deduplication). ES3.1 atlas maps use gradients; ES2 maps
  use ordinary samples without unsupported gradient calls.
- All ten actual cooked meshes match their section and triangle counts. Each
  atlas triangle has a constant valid tile ID. All textures use ETC1; decoded
  base-level cutout coverage differs by at most 0.551% after compression.
- UE cooking completes with zero errors/warnings. Import retains PC geometry
  warnings about degenerate tangent/binormal bases; these unlit materials use
  vertex normals and no tangent-space normal maps. Bounds and UV audits pass.
- All 367 PAK members round-trip byte-for-byte through repak and pass the
  independent UnrealPak archive test. The NRO's ELF loadable segments, runtime
  identity and embedded icon are verified. Public-tree and whitespace checks
  pass. The wider legacy suite is not repeated; its pre-existing failures are
  recorded in the v25 report.

Delivery: `local-debug/stadium-performance-v26/release/FootballNX-Stadiums-v26.zip`.
The release contains Indonesian installation notes, checksums and per-stadium
verification/cost data. Hardware acceptance remains pending.

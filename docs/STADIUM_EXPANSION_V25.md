# Stadium expansion v25

## Scope

The selector now calls the accepted Anfield asset **Anfield Stadium**. Its PAK,
geometry, crowd and v20 roof equations are unchanged. This batch adds the ten
standalone stadium folders in the owned FL26 installation. Built-in stadiums
inside FL26 CPK archives are outside this batch.

| Runtime ID | Stadium / asset key | Shell triangles | Animated crowd rows | Materials |
| --- | --- | ---: | ---: | ---: |
| 2 | Etihad Stadium / `EtihadStadium` | 100,000 | 4,018 | 68 |
| 3 | Giuseppe Meazza / `GiuseppeMeazza` | 52,038 | 2,274 | 31 |
| 4 | Parc des Princes / `ParcdesPrinces` | 75,456 | 4,389 | 49 |
| 5 | Ramon Sanchez Pizjuan / `RamonSanchezPizjuan` | 100,000 | 3,022 | 66 |
| 6 | San Siro / `SanSiro` | 51,858 | 2,274 | 31 |
| 7 | Santiago Bernabeu / `SantiagoBernabeu` | 99,999 | 5,227 | 67 |
| 8 | Signal Iduna Park / `SignalIdunaPark` | 100,000 | 4,924 | 107 |
| 9 | Stamford Bridge / `StamfordBridge` | 100,000 | 4,045 | 68 |
| 10 | Tottenham Hotspur Stadium / `TottenhamStadium` | 99,999 | 5,384 | 65 |
| 11 | Wanda Metropolitano / `WandaMetropolitano` | 100,000 | 5,024 | 26 |

IDs 0 and 1 remain Konami and Anfield. Two triangles per audience row are
additional to the shell counts. Giuseppe Meazza and San Siro are separate
owned addon variants, so both are retained.

## Runtime integration

`stadium_catalog.h` defines stable IDs, names, PAK paths and object paths. Only
PAKs present at startup enter the installed menu. The UI resolves menu indices
to this registry: installing Etihad without Anfield cannot select the wrong
asset. Selection still uses the guarded native `LoadedCall` hook and existing
component resource/LOD lifecycle. No UObject pointers are retained between
callbacks and no shell spawning or mesh replacement runs per frame.

Every addon replaces the native shell carrier. Native pitch, goals, players,
flags, adboards, weather surfaces and cameras remain. The same v17 material
camera cutaway applies to the shell and audience. A failed replacement load
attempts to restore the native carrier if an imported shell was already active.

The audience uses the owned native sixteen-frame seated sprite atlas at 8 fps.
Rows are placed from each stadium's own
audience areas and checked against its seating surfaces. There is no manual
vertex animation or runtime CPU update of individual spectators.

`stadium_roof_profiles.h` contains offline measured roof approximations, fitted
to each opening and outer contour. The same projection affects the pitch,
bodies and faces. Different receiver heights intersect the same light ray.
The fit is a rounded ring at a representative height, not an exact shadow of
every truss, opening or sloping panel. Seasonal direction and rain attenuation
use the existing environment settings.

Four geometry vectors upload only when a GL program first receives a profile
or the selected stadium changes. The v20 fast paths and Konami/Anfield geometry
are retained. This adds no shadow texture, depth pass or per-frame fitting.
Imported stadiums still have different geometry/material costs; Signal Iduna
Park has the largest material count and needs particular attention on Switch.

## Conversion and repeatability

The reviewed part lists, triangle budgets and roof measurements are in
`data/stadiums/fl26_addons_v25.json`. Source geometry, textures, FBX/Blender
files, Unreal projects and generated PAKs stay local and ignored.

The converter selects each venue's seating tiers and roof parts, excludes
alternate/snow/demo meshes and distant city geometry, and protects the native
pitch surface. Large shells are reduced to approximately 100,000 triangles.
Materials sharing a source texture are merged. Empty slots left by reduction
are removed; Unreal-safe hashed names preserve distinct source names containing
spaces or punctuation. Alpha metadata is retained for masks and fences.

The audience reader accepts both observed header versions, multiple groups
per tier and empty tiers, with bounds/count/pointer validation. Anfield's
existing audience fixtures retain the same geometry.

Example local configuration keys for preparation:

```json
{
  "stadium_root": "D:/owned/FL26/SiderAddons/content/stadiums",
  "blender": "D:/tools/blender.exe",
  "fmdl_parser": "D:/tools/pes-fmdl",
  "texture_parser": "D:/tools/pes-file-tools/lib",
  "crowd_atlas": "D:/owned/native/s_au000_all.png"
}
```

Run `python tools/prepare_stadium_batch.py --config <local-json> --work
<ignored-output>` to prepare and audit the ten venues. Existing output requires
an explicit `--rebuild`; `--keys` can narrow a retry. Review the generated roof
and camera reports plus `render_stadium_preview.py` images before promotion.
The preview reconstructs the exported unlit hemisphere material; it is not a
Switch screenshot.

For cooking, use `cook_stadium_batch.py --config <local-json> --work
<ignored-output> --keys <keys...>`. Its separate config has `editor`, `project`
and `repak` paths. Use an isolated UE4.22 project with Python enabled,
`bBuildForES2=True`, `bBuildForES31=True`, inline shader maps and ETC1. The
bootstrap is Python 2.7 compatible and avoids spaces in the commandlet script
path. Repeated imports repair material graphs and reimport the shell.

The packer uses the FBX dependency allowlist, excluding stale imports and all
other stadium namespaces. It requires both GLES shader maps, verifies member
names, unpacks the generated PAK and compares every member byte for byte.

Four texture references are absent from their selected source texture folder:
two Etihad camera/staff props, one Parc grate and one Signal signboard. These
small materials currently use the explicit plain-concrete fallback. They are
not silently substituted with unrelated textures. Main seating/roof textures
and crowd atlases are present.

## Verification and device limits

Each venue's offline camera audit samples 30,240 camera-to-player rays across
all quadrants and multiple camera/player heights: none remain occluded after
the cutaway policy. This checks the sampled geometry and policy, not every
native cinematic on hardware. Roof fits are visually reviewed; their central
opening overlap is at least 0.89 and outer overlap at least 0.84 against the
filtered measured grid.

Host tests cover sparse installation, switching and restoring shells,
resource lifecycle, audience layouts, safe material names, protected pitch,
catalog/profile agreement, shared pitch/player lighting and bounded uniform
uploads: 56 tests and 359 subtests pass. The wider project suite reports 820
passed, 13 failed and 51 skipped (55,420 subtests passed). All 13 failures
reproduce on checkpoint `899f22f` in a separate source snapshot: legacy menu,
team catalog, gamepad, pause harness and master-registry expectations. They
are recorded separately from this batch's passing focused checks.

Native shader validation covers 706 eligible variants before/after
rewriting with both clip-space definitions: 2,824 successful compilations.
The production NRO uses runtime identity `e861c583ec78e9ae` and the existing
53,248-byte patch OBB; its icon and ELF loadable segments are verified during
packaging. The scene log header is `FootballNX scene v25 session`; stadium
numbers in frame-pacing lines use the stable IDs in the table.

This batch needs Switch testing. Check DAY and NIGHT, passing within roof
shade, crossing its edge, close replays and celebrations in all corners, then
switch stadiums between matches. Retain the installed physique CPK/manifest,
realface PAK and accepted Anfield PAK. This update supplies a new NRO and ten
additional stadium PAKs, with no dataset or save migration.

Local delivery: `local-debug/stadium-expansion-v25/release/FootballNX-Stadiums-v25.zip`.
Copy its `update/` contents into the existing `switch/pes21_nx/` installation.
The ten additional PAKs are independent; the NRO is required for their selector
entries and roof profiles. Keep the accepted Anfield PAK installed. Use High
quality for the audited native shell carrier path. The release includes
checksums, per-stadium verification metadata and Indonesian installation notes.

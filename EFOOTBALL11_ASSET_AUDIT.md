# eFootball 11.0.0 XAPK asset audit

Audited read-only on 2026-08-23 from `EFOOTBAL2024.xapk`. Despite its filename,
the embedded manifest identifies the package as eFootball 11.0.0,
`versionCode 311000001`, package `jp.konami.pesam`.
The audited file SHA-256 is
`C6C9ACE32518C63F1BA4AEF79D780DD7D91B651CC80FFEF698ADC17A5C7C98AA`.

No files from this package have been copied into the PES21 NX runtime.
Technical compatibility does not grant redistribution rights; any shipped
asset also needs an appropriate permission/license review.

## Package layout

- Base APK: 22.3 MB. Mostly Android bootstrap code/resources.
- ARM64 split: 57.1 MB compressed, containing a 160.8 MB `libUE4.so` and
  supporting Android libraries.
- `pad_it_0.apk`: 395.4 MB, containing 46 CRI CPK archives.
- `pad_it_1.apk`: 386.4 MB, containing `dt540_mobile_all.cpk` plus a newer
  Unreal IoStore payload (`pak`, `ucas`, `utoc`).
- Base Unreal payload: an outer ZIP contains
  `pakchunk0-Android_ETC2.pak` (77.3 MB), its 23.9 MB UCAS, UTOC metadata and
  the global IoStore container. PES21 NX instead mounts the older
  `PesMobile-Android_ETC1.pak`, so this payload is not a drop-in replacement.

The XAPK contains only bootstrap/initial packs. Large live-service downloads
such as a modern equivalent of PES21's 2 GB `dt510` pack are not present.

## Concrete CPK inventory

- `dt200_mobile_all.cpk` (9.9 MB, 2,993 files): 2,982 binary tables plus
  eight save-state PNGs. Its 47 PESDB tables include Player, PlayerAssignment,
  Team, TeamColor, Ball, Boots, Glove, Stadium, Coach, Tactics and formation
  data.
- `dt220_mobile_all.cpk` (3.0 MB, 295 files): cut-scene/demo animation data.
- `dt230_mobile_all.cpk` (200.5 MB, 131 files): gameplay animation tables,
  skeletons, geometry and animation archives.
- `dt240_mobile_all.cpk` (5.9 MB, 196 files): primarily goal-net geometry,
  cloth and 15 tiny net-pattern PNGs.
- `dt250`/`dt251` (2.8 MB combined): hashed flow/script resources whose names
  no longer map to the PES21 JSON flow layout.
- `dt260` and localized `dt261` packs: UI/localization string tables.
- `dt270_mobile_all.cpk` (18.0 MB, 81 files): match constants and replay/event
  tables, including `constant_match.bin`, player/team/stadium constants and
  replay `.rep`/`.trep` data.
- `dt500_mobile_all.cpk` (136.7 MB): menu BGM and system/menu ACB/AWB banks.
- `dt520` and localized `dt530` packs: sound configuration, localized XML and
  binary configuration.
- `dt540_mobile_all.cpk` (285.6 MB): match announcer, chants, cheers, player
  voice, match BGM and event-control ACB/AWB banks.

## Measured overlap with PES21

Matching paths do not imply matching binary schemas, but they show which packs
still belong to the same subsystem:

| Pack | PES21 files | New files | Shared paths | Assessment |
| --- | ---: | ---: | ---: | --- |
| dt200 | 2,435 | 2,993 | 1,059 | Useful database reference; unsafe wholesale swap |
| dt220 | 2,472 | 295 | 285 | Most new paths exist in PES21, but the new pack is heavily trimmed |
| dt230 | 416 | 131 | 71 | Some animation-table continuity; binary/layout risk is high |
| dt240 | 6,550 | 196 | 3 | Assets moved elsewhere; not a replacement for PES21 render content |
| dt250 | 423 | 1,094 | 0 | Incompatible hashed flow system |
| dt270 | 35 | 81 | 33 | Strong match-constant continuity; good research target |
| dt500 | 9 | 11 | 5 | Partial audio path continuity, cue/config changes |
| dt520 | 5 | 22 | 4 | Configuration continuity with newer locale split |
| dt540 | 41 | 25 | 16 | Partial match-audio continuity, different cue banks |

## Realistic reuse possibilities

### Best research targets

1. **Match constants and camera/replay behavior (`dt270`)**
   Compare individual fields/tables against PES21, especially match constants
   and replay camera data. This may reveal safer parameter-level improvements
   for camera tracking or transitions. Do not replace the entire CPK.
2. **Database migration (`dt200`)**
   Build an explicit field-by-field converter for selected Team, TeamColor,
   Player, PlayerAssignment, Ball, Boots and Stadium records. IDs and record
   sizes must be mapped to the PES21 schema; direct replacement would likely
   break roster construction and hooks that depend on PES21 layouts.
3. **Localization (`dt260`/`dt261`)**
   Extract text conceptually or convert selected strings into the existing
   PES21 string format. This is much safer than loading the new binary table.
4. **Standalone Android PNGs**
   Launcher branding and the 1280x720 UE4 startup graphic are normal PNGs and
   technically easy to convert for an NRO icon/title asset. The UE4 startup
   image has little in-game value, and branding still needs permission review.

### Possible with conversion, but higher risk

- Individual goal-net patterns/geometry from `dt240`, after verifying Fox
  Engine geometry/material compatibility.
- Individual menu or match audio banks from `dt500`/`dt540`, only after cue-ID,
  ACF and event-name mapping. Replacing whole banks risks missing sounds or
  crashes.
- Selected animation data from `dt220`/`dt230`, only after skeleton and binary
  version validation. The size/layout differences rule out a safe pack swap.

### Not suitable as a direct update

- The newer UE IoStore/ETC2 payload (`pak`/`ucas`/`utoc`). PES21 uses an older
  ETC1 cooked package and runtime. New cooked UAssets, materials, shaders and
  textures need extraction and recooking/conversion; copying the container
  will not mount correctly in the current port.
- The new `libUE4.so`. Its code/data addresses and ABI differ from the PES21
  library, invalidating the current hooks and runtime assumptions.
- Entire CPK replacements, especially `dt200`, `dt230`, `dt250`, `dt500` and
  `dt540`. They contain interdependent schemas, event IDs or flow formats.

## Recommended next experiment

Start with a read-only extractor/differ for `dt270` and `dt200`. Produce a
table-level schema diff first, then port one isolated value or visual record at
a time behind a runtime flag. This has a much better chance of improving PES21
without destabilizing match loading than copying a newer pack wholesale.

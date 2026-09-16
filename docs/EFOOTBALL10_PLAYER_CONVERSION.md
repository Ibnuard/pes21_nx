# eFootball 10 player conversion

The repository contains an offline converter that maps one EF10 team onto
globally-unused native PES21 player slots. Barcelona (team 108) is the default
proof of concept:

```powershell
python tools/convert_efootball10_players.py --team-id 108
python tools/generate_efootball10_rosters.py --team-id 108
```

The default output is the ignored directory
`local-debug/efootball10-player-patch/`. It contains converted
`Player.bin`, byte-identical `PlayerAssignment.bin`, the fixed-count
`TacticsFormation.bin`, `surrogate-map.json`, the persistent
`surrogate-registry.json`, `conversion-summary.json`, and a strict
`validation-report.json`.

The converter never appends a record and never changes a PES21 player ID.
`Player.bin` therefore remains exactly 43,074 records in the original order,
which keeps `PlayerAppearance.bin` and the other CommonWork parallel tables
aligned. An unused slot with the same registered position is selected from the
globally-unused pool. Every surrogate is absent from all native
`PlayerAssignment.bin` rows, all `SpecialPlayerAssignment.bin` rows, and every
stable custom runtime roster. It is also required to have the exact registered
position, so a GK cannot inherit a striker slot. Four EF10 name fields and 25
EF10 gameplay abilities are converted into the PES21 packed layout. EF10 and
PES21 use different nationality codebooks, so the converter infers a verified
code mapping from shared player IDs and writes the PES21 nationality byte too.
The validation pass decodes the result again and requires every copied name,
ability, and nationality to round-trip exactly. It also proves that the player
ID sequence and `PlayerAssignment.bin` remain unchanged.

Surrogate allocation is persistent. Once an EF10 source ID receives a safe
PES21 slot, every subsequent club or national-team conversion reuses that same
slot. The generated roster table automatically includes related national teams
that contain converted club players. For example, Lamine Yamal is PES21 ID
`8957` in both Barcelona and Spain, rather than being duplicated.

The converter also maps each available EF10 team formation onto the existing
PES21 tactics IDs. It preserves all PES21 formation row indices and applies the
EF10 positions/coordinates to each of the three native tactical phases.

For a local experiment, the repository-owned CPK repacker can replace the two
members in a copy of the user-owned `dt200_mobile_all.cpk`:

```powershell
python tools/repack_cpk_members.py `
  local-debug/efootball10-player-patch/dt200_mobile_all_pes21_working.cpk `
  dt200_mobile_all_ef10_surrogate.cpk `
  --expect-members 2435 `
  --replace common/etc/pesdb/Player.bin=local-debug/efootball10-player-patch/Player.bin `
  --replace common/etc/pesdb/TacticsFormation.bin=local-debug/efootball10-player-patch/TacticsFormation.bin
```

The source above must be the PES21 `dt200` from the last known-working OBB.
The similarly named EF10 file has 2,841 members instead of 2,435 and is not a
compatible base. `--expect-members 2435` aborts before writing an output if the
wrong generation is selected.

`PlayerAssignment.bin` deliberately remains the original PES21 file. Team
membership and shirt ordering are installed by the generated Exhibition
roster hook. That hook resolves EF10 source IDs through `surrogate-map.json`,
so no unknown player ID reaches the PES21 runtime.

## Portraits

PES21 Game Plan portraits are independent PNG files in
`dt241_mobile_all.cpk`, under `common/player/<pes21_player_id>.png`. They are
not stored in `PlayerAppearance.bin`. All 23 Barcelona surrogate slots have a
native 128x128 portrait member, which is why leaving dt241 unchanged displays
the old donor player's face.

The EF10 XAPK's `pc1000_mobile_and` IO Store container contains the original
128x128 player thumbnails under
`/Game/Assets/ui/Data/Thumbnail/Player/<ef10_player_id>_`. The repository
extractor converts those UE4.26 ETC2 textures to ordinary transparent PNGs,
so no private Android cache pull is required once the XAPK assets have been
extracted into the audit directory:

```powershell
python tools/extract_efootball10_portraits.py
python tools/import_efootball10_portraits.py `
  --portrait-dir local-debug/efootball10-portraits
```

The importer normalizes each image to a transparent 128x128 PNG and writes it
under the mapped PES21 ID. Native PES21 cards render only the first 100 pixels
of that texture and reserve the final 28 pixels as transparent padding, so the
importer center-crops the EF10 portrait into the same 100-pixel safe frame.
This prevents shoulders and background pixels from spilling outside the card.
It refuses missing images by default, validates that every target member
already exists and is stored rather than compressed, and emits an import
report. The extractor reads `pc1000_mobile_and.utoc/.ucas` plus the matching
`global.utoc/.ucas` files from
`local-debug/efootball10-audit/pad-assets/assets/`; the AES key and retoc
version defaults are the values used by the EF10 package audit.

The current runtime keeps `dt200_mobile_all.cpk` as a member of
`patch.305030001.jp.nyan2021.pesam.obb`. Despite its `.obb` suffix, that file
is a CRI CPK container. The converted `dt200_mobile_all.cpk` must therefore
replace the member inside a backed-up copy of the OBB; it must not be copied
blindly into `Download/`.

For the local test build, the original OBB is preserved under
`local-debug/efootball10-player-patch/` and the patched OBB is installed at
the normal runtime filename under `dist/pes21_nx/`. The corresponding release
NRO contains the generated EF10 roster membership table.

## Current all-team build

The ready-to-test files are the normal runtime pair in `dist/pes21_nx/`:

```text
pes21_nx.nro
patch.305030001.jp.nyan2021.pesam.obb
```

This build updates all 99 Exhibition teams that have EF10 assignment data:
2,596 unique players, 99 team formations, names, 25 gameplay abilities, and
packed nationality fields. It uses 1,201 direct shared IDs and 1,395
globally-unused PES21 surrogate slots. The original `PlayerAssignment.bin`
remains byte-identical, so native teams outside the generated Exhibition
rosters are not reassigned.

There are 2,232 original EF10 portraits. The 364 EF10 players for which the
container has no thumbnail receive a transparent no-photo image instead of
leaking the unrelated PES21 donor portrait. The ten post-v1.98 migrated clubs
(Manchester B, Everton B, Tottenham WB, Brighton WB, Benfica, Porto,
Sporting CP, Atalanta, Napoli, and Torino) are also present with complete EF10
rosters and native badge images.

PES21 does not store EF10's displayed card overall as one of these converted
fields. It recalculates the displayed overall using the PES21 formula and the
25 exact base abilities. Values around the mid/high 70s in the Game Plan are
therefore expected and do not mean the donor player's old attributes remain.
Boosting them would no longer be an exact EF10 base-stat conversion.

The runtime NRO is built from the exact v1.98 release commit (`99a0883`) with
only static team-list/badge data, the generated EF10 roster table, and the
current OBB-size check added. Diagnostic logging and performance tracing are
both disabled. This keeps the v1.98 overlay/helper and frame-pacing path
instead of compiling unrelated post-release runtime experiments.

The final files are:

- NRO: 11,116,749 bytes, SHA-256
  `f423132c9333a5e0334c96a9f60043b084eff7f9e4da110dad89470a8942b306`
- OBB: 1,391,120,384 bytes, SHA-256
  `f3583c2a590e59dc8bf8a09d0c1538bfe0fda35c8d900420bc28c67e20afac23`

The immediately previous NRO is preserved as
`local-debug/efootball10-all-teams-patch/pes21_nx.pre-all-teams.nro`. The
tested Barcelona OBB rollback remains at
`local-debug/efootball10-player-patch/patch.305030001.jp.nyan2021.pesam.barcelona-nationality-portraits-fixed.obb`.

# Inter Miami original-ID experiment

This experiment tests whether an EF10-only player can retain the EF10 player
ID in the PES21-mobile master database without using a runtime surrogate ID.
The player conversion remains reusable and data-only; the deployable runtime
integration is an explicitly compiled, detachable NRO plus OBB pair.

## Scope

- EF10 team: `5738`, displayed by the source database as `Miami BP`.
- EF10 league membership: category `603`, exposed by the custom selector as
  `N AMERICA CLUBS`.
- Shared PES21/EF10 player IDs: eight players, updated directly in place.
- Canary player: Noah Allen, EF10 player ID `153007`.
- XI mode: the eight shared players plus original IDs `153007`, `160365`, and
  `157971`.
- Full mode: all 27 Inter Miami roster members, including 19 EF10-only IDs.
- Runtime physical alias: PES21 team `2473` (`PUNTIHUERVA`), an unexposed club
  slot with native roster, tactics, uniform, and crest resources.

The manifest is `data/experimental_original_inter_miami.json`. The generator
is `tools/experimental_import_ef10_original.py`.

## Method

EF10 `Player.bin` records are 392 bytes; PES21-mobile records are 312 bytes.
The source row therefore cannot be copied directly. The experiment converts
the name fields, 25 gameplay abilities, nationality, and registered position
into the PES21 layout.

For an EF10-only ID, the converter selects a retired PES21 row that:

- appears in `PlayerDeleteList.bin`;
- is absent from `PlayerAssignment.bin`;
- is absent from `SpecialPlayerAssignment.bin` and `PlayerWeekly.bin`;
- has the same registered position; and
- is not referenced by optional `PlayerAppearance.bin` or `BootsList.bin`
  when those tables are present.

The retired record is replaced by a PES21-schema record whose ID is the EF10
ID. `Player.bin` stays at exactly 43,074 rows and is sorted again by player ID.
The matching row in `InstallVersionPlayer.bin` receives the original ID, and
the retired donor is removed from `PlayerDeleteList.bin`.

This is materially different from the old invalid direct-ID artifact, which
appended tens of thousands of records while leaving dependent tables at stock
sizes.

## Generate

```powershell
python tools/experimental_import_ef10_original.py `
  --mode canary `
  --output-dir local-debug/efootball10-original-inter-miami-canary

python tools/experimental_import_ef10_original.py `
  --mode xi `
  --output-dir local-debug/efootball10-original-inter-miami-xi

python tools/experimental_import_ef10_original.py `
  --mode full `
  --output-dir local-debug/efootball10-original-inter-miami-full
```

Each ignored output directory contains patched database members, an
`original-id-map.json`, `validation-report.json`, a standalone roster include,
`cpk-replacement-manifest.json`, and a `team-integration-pending.json` marker.
The replacement manifest lists only the three changed PES21 database members;
it is not an instruction to overwrite the normal runtime CPK.

## Current result

All three modes pass the offline invariants:

- the `Player.bin` row count remains 43,074;
- player IDs are unique and strictly increasing;
- `InstallVersionPlayer.bin` contains exactly the same player ID set;
- original EF10 IDs are present and retired donor IDs are absent;
- each donor is removed from `PlayerDeleteList.bin`; and
- native assignment tables remain byte-identical.

The canary maps retired PES21 ID `141552` to Noah Allen ID `153007`.

## Original-ID database stage

Before the detachable runtime package was added, this stage deliberately
stopped at the converted player tables:

- PES21 `Team.bin` has no Inter Miami record. Logical EF10 ID `5738` therefore
  cannot be sent directly to CommonWork. The manifest reserves PES21 physical
  team ID `2473` (`PUNTIHUERVA`) because it is a complete club slot not exposed
  by the current selector. The standalone converter still leaves Team.bin
  untouched; the release packager owns that separate patch.
- No selector, badge atlas, kit, tactics, CPK, OBB, NRO, root, or dist file is
  changed.
- Shared players still have their legacy PES21 club assignments. Before
  runtime integration, club memberships for the eight shared IDs must move to
  Inter Miami while national-team memberships are preserved.
- An original-ID portrait cannot be added to the stock `dt241_mobile_all.cpk`
  by the current stored-member replacement tool because the CPK has no
  `common/player/153007.png` member. The player can use a no-photo fallback for
  the first hardware canary; a later portrait phase needs an append-capable
  CPK or runtime aliasing.

Those limits still describe the standalone canary output. The release-base full
package below is the separate runtime integration used by the stable release.

## Isolated CPK canary

`tools/build_inter_miami_original_canary.py` packages the canary player tables
into a new `dt200_mobile_all.cpk` only when the source CPK hashes match the
experiment input. It refuses to patch the deployed custom OBB or overwrite an
existing output unless `--force` is supplied.

```powershell
python tools/build_inter_miami_original_canary.py --check
python tools/build_inter_miami_original_canary.py
```

The current canary is under
`local-debug/efootball10-original-inter-miami-canary/cpk/` and changes only
`Player.bin`, `InstallVersionPlayer.bin`, and `PlayerDeleteList.bin`. The
validation report records 2,432 unrelated CPK members as byte-identical and
marks the release OBB as untouched. Rollback is simply removing the canary
CPK and restoring the original base CPK; no selector or runtime source change
is required.

The generated report already classifies the known memberships for cleanup.
Seven of the eight shared IDs occur in PES21 assignments. For example, Messi's
Argentina membership is marked `preserve_national_membership`, while his old
Barcelona membership is marked `remove_legacy_club_membership`. Rocco Rios
Novo has no native PES21 assignment and needs no cleanup.

## Release-base full merge

The deployable experiment must preserve the existing converted team/player
database. `tools/build_inter_miami_release_experiment.py` therefore merges the
full 27-player roster onto the dt200 extracted from the current runtime instead
of copying the stock-based tables. It verifies 43,047 unrelated Player rows,
patches the physical Team.bin name/codes, imports the three EF10 uniform
definitions, and changes no other dt200 member.

The same packager rebuilds dt240 with only the three physical-slot crest PNGs
replaced. The final OBB is produced in two checked steps (`dt200`, then
`dt240`), and all other outer OBB members remain byte-identical. Compact WESYS
compression keeps dt200 inside its fixed 10,452,992-byte OBB slot.

```powershell
python tools/build_inter_miami_release_experiment.py --check
python tools/build_inter_miami_release_experiment.py --package-obb
```

The packager never overwrites the deployed NRO or OBB. Runtime exposure is
guarded by the compile-time flag `PES_EXPERIMENT_INTER_MIAMI=1`, which is
enabled by default and can be disabled with `PES_EXPERIMENT_INTER_MIAMI=0`.
Candidate builds must use their separately named NRO and OBB together; after
hardware validation, that verified pair can be promoted to the stable paths.
The reproducible pre-integration OBB base remains archived locally at
`local-debug/inter-miami-runtime-base/patch.pre-inter-miami.obb`.

## Stable release

The selector exposes logical team ID `5738` as `INTER MIAMI CF`
under `N AMERICA CLUBS`, matching its EF10 category `603`. CommonWork receives physical
PES21 team slot `2473`, while the custom runtime installs all 27 EF10 roster
members with their EF10 shirt numbers. The first eleven include a goalkeeper;
the remaining sixteen provide a complete Game Plan bench.

The release merge also rewrites native `PlayerAssignment.bin`: the 25-player
PUNTIHUERVA roster is replaced by all 27 Inter Miami members, seven stale club
memberships for shared IDs are removed, and Messi/Busquets/Suarez national-team
memberships are preserved. Generated fallback rosters consume the same external
club ownership rule, so old selectable clubs cannot retain those shared players.

All 27 EF10 portraits are installed into compatible native dt241 slots. Shared
IDs keep their own slots, while original IDs map to the retired donor slots
populated by the package. The selector atlas uses dormant slot `502`, the
native intro/pause UI reads the Inter Miami crest from the patched
`e_002473_f{,_l,_s}.png` files, and dt210 carries the stable scoreboard update.

The hardware-validated stable pair is:

- `dist/pes21_nx/pes21_nx.nro`
- `dist/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb`

The exact tested candidate remains archived at:

- `dist/pes21_nx/inter_miami_stable_candidate/pes21_nx.nro`
- `dist/pes21_nx/inter_miami_stable_candidate/patch.305030001.jp.nyan2021.pesam.obb`

Hardware validation passed before promotion. The integration remains
detachable: build with `PES_EXPERIMENT_INTER_MIAMI=0` and pair it with a
pre-integration OBB to remove the selector entry, original-ID players, renamed
physical slot, Inter Miami kits, and crest together.

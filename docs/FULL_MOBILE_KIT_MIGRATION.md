# Full Football Life 2026 kit migration

`tools/build_full_mobile_kit_migration.py` converts compatible Football Life
2026 uniforms into the PES21 Mobile layout used by the Switch wrapper. Source
game payloads and generated CPKs stay under ignored local directories; the
repository contains only the generator, policy, tests, and documentation.

## Identity and fallback policy

- `team_id` is the Football Life source identity.
- `physical_team_id` is the native PES21 destination slot.
- Home, away, and goalkeeper descriptors plus their body/back FTEX files must
  all exist before a team is changed.
- Missing or partial source sets preserve the existing mobile team byte-for-
  byte. The generator never substitutes a donor uniform.
- Hub previews are generated from the converted Uniform16 body atlas with the
  hardware-tested project mesh. `_full` native members remain unchanged.
- Only `dt120`, `dt200`, and `dt240` are rebuilt. Validation requires every
  unrelated CPK member to remain byte-identical.

## Selector branding

The local build extracts licensed competition emblems from Football Life's
`dt15_x64.cpk`, clears and replaces only the matching category slots in the
existing badge atlas, and generates a branded migration team include. Clearing
the complete slot is required because transparent margins in the new emblem
must not reveal pixels from the previous unlicensed logo. `build-wsl.ps1` accepts
these ignored local artifacts through `-BadgeAtlas` and
`-MigrationTeamInclude`, copying them only into its temporary build tree.

## Baseline full build

The first full migration against the 443-team player-migration catalog found:

- 403 teams with complete, convertible source kits;
- 40 teams preserved because the source set was absent or incomplete;
- 1,209 converted home/away/goalkeeper kit sets;
- 806 generated home/away hub preview members;
- 21 selector categories updated with licensed names and emblems.

All catalog entries in the Premier League, EFL Championship, LaLiga, LaLiga
2, Serie A, and national-team categories passed the complete-source gate.

## Commands

```powershell
python tools/build_full_mobile_kit_migration.py `
  --output local-debug/full-mobile-kit-migration-v1

.\build-wsl.ps1 `
  -OutputDirectory local-debug/full-mobile-kit-migration-v1 `
  -Jobs 8 -ExpectedPatchObbSize 53248 `
  -PlayerMigrationCanary -LooseCpkFull `
  -BadgeAtlas local-debug/full-mobile-kit-migration-v1/league-branding/badge_atlas.bin `
  -MigrationTeamInclude local-debug/full-mobile-kit-migration-v1/league-branding/exhibition_teams_migration_generated.inc

python tools/build_full_mobile_kit_migration.py `
  --output local-debug/full-mobile-kit-migration-v1 --finalize
```

The final local report is
`local-debug/full-mobile-kit-migration-v1/full-kit-migration-report.json`.
It contains team-level provenance, preserved teams and missing assets, CPK
member counts and hashes, preview sheets, selector branding provenance, and a
hardware validation checklist.

## Preserving branding and kits across roster migrations

Two regressions were identified after the Bundesliga/Indonesia stage:

- Its selector started from the generic catalog/atlas instead of reapplying
  the FL26 branding policy. The shared `brand_selector` helper now brands only
  surviving categories, preserves every team and badge slot, and never
  reintroduces retired selector categories. The Bundesliga staging tool uses
  this helper before publishing its selector.
- The pairing tool replaced all of `Team.bin` with a table generated from an
  older database. This reset unrelated kit-selection bytes even though the
  converted descriptors/textures were still present. Pairing now merges only
  the explicitly migrated Bundesliga/Indonesia team rows into the licensed
  kit base, preserving all other rows byte-for-byte.

For an already affected package, `tools/restore_fl26_presentation.py` stages
a new paired candidate. It restores only active teams whose logical/native
mapping and entire native team record (except byte 84) match the licensed
reference. All three mobile descriptors, six converted textures, and both
home/away preview sets must match the audited FL26 package and asset hashes.
Unproven teams are reported as held; they never inherit a donor kit. No player,
assignment, tactic, crest, or texture data is replaced.

```powershell
python tools/restore_fl26_presentation.py `
  --base PATH_TO_CURRENT_FULL_CANDIDATE `
  --catalog PATH_TO_CURRENT_SELECTOR_CATALOG `
  --atlas PATH_TO_CURRENT_BADGE_ATLAS `
  --reference local-debug/full-mobile-kit-migration-v1 `
  --all-verified-kits `
  --output local-debug/new-fl26-presentation-candidate
```

`--team 137` can narrow restoration to Palmeiras. The output assigns a new
paired build ID and contains a roster include whose arrays are unchanged;
only its build-ID markers differ. Build its NRO with the generated
`league-branding/badge_atlas.bin`, matching team include, and the new
`selector/exhibition_rosters_migration_canary_generated.inc`. Keep the existing
Cup/League pools and scorer data. Then use `package_loose_update.py` to deliver
only changed install files, never the build/audit directory. Runtime kits still
need a Switch check; byte-level checks do not prove on-device rendering.

For branding alone, `--refresh-branding --badge-atlas CURRENT_ATLAS
--paired-build-id CURRENT_LOOSE_ID` on `build_full_mobile_kit_migration.py`
preserves the latest team crests (including Palmeiras and Indonesia). Never
revert to the archived generic atlas after adding or updating club crests.

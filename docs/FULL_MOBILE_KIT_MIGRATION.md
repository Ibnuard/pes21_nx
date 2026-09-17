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

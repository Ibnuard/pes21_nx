# Football Life 2026 Cups in Cup Mode

Cup Type offers FA Cup, Copa del Rey, Coppa Italia, AFC Cup, UEFA Euro,
World Cup, and FootballNX Cup, in that order. The first six use competition
membership from a locally owned SP Football Life 2026 installation. The public
catalog contains only
competition IDs, display names, category mappings, and team IDs. Original
competition logos and the three user-supplied international logos are never
committed or embedded in the NRO.

## Data mapping

`tools/build_fl26_cup_catalog.py` reads `Competition.bin` from
`download/data_s2526.cpk`, current Cup participant membership from
`CompetitionEntry.bin` in `download/data_s2526c.cpk`, and emblem names from
`Data/dt15_x64.cpk`. For each Cup it keeps the intersection of its ordered PC
participant list with the playable Switch team catalog. This includes eligible
second-division teams in Cups such as the FA Cup, but avoids importing a team
that has no playable Switch roster. International Cups use their own ordered
national-team participant lists, including World Cup teams across continents.
Only 18 of the PC World Cup entrants have playable Switch rosters, so the
World Cup pool keeps those entrants first and adds the remaining playable
national teams as eligible replacements. It can therefore fill 32 unique
slots without importing unplayable teams.
Cup Mode opens its team picker directly on the selected Cup's filtered list;
random fill uses the same pool.

FA Cup and Copa del Rey offer 8, 16, or 32 teams; Coppa Italia offers 8, 16,
or 24 because only 29 Italian clubs in its pool have playable Switch rosters.
AFC Cup and UEFA Euro are fixed at 16 teams, while World Cup is fixed at 32.
The team picker retains each Cup's full eligible pool so players can replace
assigned teams before the first match.
FootballNX Cup remains the unrestricted custom 2–32-team option. Version 1/2
saves migrate to the seven-choice selector; saved Cups removed from the menu
remain playable as FootballNX Cup brackets, without changing their fixtures.

## Regenerate locally

Run from the repository root, substituting your own FL26 installation path:

```powershell
python tools/build_fl26_cup_catalog.py --fl26-root 'D:\Games\SP Football Life 2026' --logo-output local-debug/fl26-cup-build/CupLogos
python tools/build_fl26_cup_catalog.py --fl26-root 'D:\Games\SP Football Life 2026' --check
```

The generated public files are `data/fl26_cup_catalog.json` and
`source/fl26_cup_catalog_generated.h`. The three domestic emblems are copied
only to the ignored candidate `local-debug/fl26-cup-build/CupLogos` directory.
Place the user-provided `cup-afc.png`, `cup-euro.png`, and `cup-world.png` in
that same folder before running the generator. Older, unreferenced emblems may
remain in a local folder but do not appear as Cup choices.

## Build for the current full-loose runtime

The Switch install with a 53,248-byte dummy OBB and `LooseCpk/manifest.txt`
**must not** use bare `build-wsl.ps1`. A bare NRO expects a large OBB and will
fail loose-runtime validation before the Cup screen opens. Build with the
matching migration ID and branding inputs:

```powershell
.\build-wsl.ps1 `
  -OutputDirectory local-debug/fl26-cup-build `
  -PlayerMigrationCanary -LooseCpkFull -ExpectedPatchObbSize 53248 `
  -BadgeAtlas local-debug/full-mobile-kit-migration-v1/league-branding/badge_atlas.bin `
  -MigrationTeamInclude local-debug/full-mobile-kit-migration-v1/league-branding/exhibition_teams_migration_generated.inc `
  -Jobs 8
```

The compiled migration ID is `1852ec648d2ebd75`; it must equal the ID on
the first line of the installed `LooseCpk/manifest.txt`. Copy the candidate
NRO and the `CupLogos/` directory beside it to
`sdmc:/switch/pes21_nx/`, retaining the matching dummy OBB and loose CPKs.
Do not copy the unrelated bare NRO from `dist/` as the full-loose candidate.
The selected logo appears prominently in the center above the Cup Settings
rows and as a subtle
watermark behind the bracket, changing with Cup Type. FootballNX Cup uses the
project's built-in brand image. If an optional FL26 logo is absent, the Cup
remains playable and shows the built-in brand instead; copy `CupLogos/` and
restart to see that Cup's original emblem. The renderer loads each selected
emblem once, not every frame.

Do not commit the extracted PNGs, CPK files, or raw PC database records.

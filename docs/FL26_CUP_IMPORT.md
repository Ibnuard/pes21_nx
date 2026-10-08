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
The Cup news UI displays the selected competition's mapped `CupLogos/` PNG
at the right of the main header and in the Cup Settings summary. The shared
Master League trophy sprite remains at the left of the header. Changing Cup Type immediately
selects the matching cached texture; PNG aspect ratio is preserved. FootballNX
Cup and unavailable optional logos use the embedded FootballNX brand fallback.
The logo files remain outside Git and are not recreated by the UI renderer.

Do not commit the extracted PNGs, CPK files, or raw PC database records.

## Cup news UI review (October 2026)

`source/cup_overlay.inc` reuses Master League's actual white panels, navy
headers, cyan/lime focus frames, blue buttons, font atlas, header icons and
carousel pills. The Cup landing page offers New and Continue, settings show
all Cup rule rows beside a tournament summary, and Home presents a Cup-wide
news carousel with a next-match card. Page-intro captions, redundant next-page
hints and the header's right-hand branding text are omitted. There is no
managed-club identity.

Every Cup page uses the reclaimed space below the main header: content starts
at 19% of the screen height and extends to 88%, with pagination above the
controller footer. Notifications reuse the Master League toast component,
including its blue/cyan styling, foreground layer and slide animation. Normal
toasts expire after three seconds; the source/target move hint remains until
the move is confirmed or cancelled. Assignment counts stay in their containers.

Home uses two large cards over four actions. Up/Down changes rows, Left/Right
moves between cards, A opens, and B goes back. L/R changes the news story;
the four stories also rotate every six seconds and pause outside Home.
Next Match is one selectable card with two larger team tiles and crests; it has
no nested play button. The footer shows A / Play Match (or Top Menu after the
Cup finishes) while this card is selected.
News reads assignment counts, the next human fixture, the latest recorded
result (including COM results), and the champion. Browsing never resolves a
fixture or changes a save.

Teams opens an eight-entry participant page. Each row is ordered team crest,
team name, a colored opening-slot code (01A/01B, 02A/02B), then a P1–P8/COM
badge, including before a team is assigned. Both sides of a fixture share a
color with its numbered badge on the Bracket page. Codes use the actual draft
mapping, including byes, and stay with the position when teams and owners swap.
The move prompt shows source and target codes. The second text line is omitted. A uses
the existing eligible-team picker, X fills vacant slots, and Y starts a slot
move. The core opening-round player rule and kickoff roster lock are retained.
Bracket and Match Centre are separate pages: L/R browses rounds and Y (or
Down) pages through pairs of fixtures. Final and third-place results share a
readable final page. Fixture cards use a left-aligned number badge followed by
the round title, larger crests and consistent team/owner/score spacing.
The final's champion artwork renders the winner's team crest from the badge
atlas above its Champions caption; pending finals keep the trophy artwork alone.
A two-team Cup has only its Final page. Completed Cups
still expose results, bracket and save before returning to the top menu.
Save format, controller routing, eligible pools and match handoff are unchanged.

Generated originals and exact built-in image-generation prompts are under
`art/cup/`; runtime PNG bytes are `data/cup_news_v1.bin` and
`data/cup_pearl_v1.bin`. Text, badges, scores, focus and buttons are rendered
live rather than baked into the artwork.

To regenerate the 38 synthetic review captures and browsable gallery:

```sh
python3 -B tools/preview_cup.py
# Optional: use the PNGs from an existing runtime without copying them into Git.
python3 -B tools/preview_cup.py --cup-logos /path/to/runtime/CupLogos
# Open local-debug/cup-news-preview/index.html in a browser.
```

The tool compiles the production frontend/core and exact C renderer helpers
on the host, records their geometry, and rasterizes the public font and assets
with Pillow. All saves are temporary. It checks navigation, carousel timing,
match completion, slot swaps, bye codes, toast lifetime, 8-player/32-team
pagination and the native vertex budget;
these are software previews, not Switch captures. On a Mac where Pillow is
installed for x86_64, run the command with the matching x86_64 Python runtime.

Validation for this revision: six focused Cup unittest cases passed, as did
the host FL26 Cup catalog and League frontend C regressions. Switch GCC syntax
checks passed for `overlay.c`, `competition_frontend.c` and `ue4_hooks.c`.
The expanded-layout revision also passes the Cup frontend flow and all 17
Master League visual regressions after sharing its toast component.
A full local build was attempted but stopped at the missing OpenAL `AL/al.h`
dependency; no linked candidate or hardware validation is claimed.

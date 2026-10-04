# FootballNX League

Status: League season, save slots, match handoff, standings, knockout, and
Switch Hub render are implemented. The concept PNGs remain design references,
not screenshots. Top Scorer ranks individual players after goals are recorded;
it does not invent scorers for a played match when native player statistics
are unavailable.

## Flow and shared controls

`League > League Settings > League Hub`. League Settings mirrors the Cup
settings layout. It offers FL26 league presets with a local logo and a
competition-specific pool of playable clubs, plus `FootballNX League` as the
unrestricted custom type. The selector shows only presets with at least eight
playable clubs; the unvalidated 18-club Bundesliga migration is still local,
so the two-club public Bundesliga subset is not misleadingly presented as a
complete preset. The League System row chooses `By Standing` or `Knockout
Stages`.
Argentina League, Chilean League, Danish Superliga, Scottish Premiership,
and Serie B are intentionally absent from League Type. Named presets fix
Number of Teams to their full eligible pool; only FootballNX League can
change that count. Existing saves from those five retired presets continue
under the custom FootballNX label with their fixtures intact.
The League Hub uses four actions in this order: `Teams`, `General Setting`,
`Next`, `Save`. During the season, B returns to the menu rather than adding a
fifth `Top to Menu` action. `Teams` edits team assignments before the first
match and locks after kickoff. Unlike Cup, League has no Swap mode.

League Settings accepts 2–32 teams and 1–8 human owners, limited to the team
count. Home & Away OFF schedules each pair once; ON schedules a return leg
with reversed home and away sides. League fixtures allow draws and award
3/1/0 points. Each matchday's remaining COM fixtures are simulated only after
all pending human fixtures on that day are played. Standings sort by points,
goal difference, goals for, then team ID.

The League Hub has two sequential phases. During the League Phase, its left
panel is the table at five teams per page with native full-color badge-atlas
quads. The right panel shows up to four fixtures for the current matchday; its
page moves independently with up/down for matchdays with more than four
fixtures. L1/R1 pages the table; Y
toggles Match Schedule and Top Scorer. COM fixtures deterministically assign
their simulated goals to players from a compact pool generated from the
committed PESDB registry. The runtime result bridge samples native
`StatsPlayerInfo` goals for played fixtures, maps portrait IDs back to
eFootball BaseId, and skips unresolved identities instead of fabricating a
scorer. The Hub requests the top four portrait PNGs asynchronously; a team
badge remains visible when a portrait asset is missing. On-device validation
of native player-stat timing is still needed.

With `By Standing`, the highest-ranked club is champion after the last
matchday; the table and final matchday remain visible. With `Knockout Stages`,
the top 2 (for 2–3 teams), 4 (for 4–7), or 8 (for 8–32) qualify for a
single-leg knockout. Seeds are 1v8/4v5/2v7/3v6 or 1v4/2v3. The left panel
becomes the Knockout Bracket with two matches per page and a champion card at
completion. L1/R1 changes round, up/down changes the two-match page, and Y
continues to toggle the right panel. Completed League has only `Top to Menu`
and A/Confirm.

## Selector and local FL26 assets

The runtime migration selector removes Belgian League, Swiss League, Other
Europe, Brazil Serie B, Colombian League, and J2 League. Native PESDB records
and the archived base atlas remain unchanged, and surviving team badge slots
are not renumbered. Both normal and canary builds use the curated runtime
selector; the archived base catalog is retained for atlas generation.
Dortmund moves into the German category. Run
`tools/cleanse_playable_categories.py` after regenerating the migration
catalog, then regenerate the Cup and League catalogs so their category indices
and team pools match it. `tools/build_fl26_league_catalog.py` reads the user's
local FL26 Competition and CompetitionEntry tables. Its optional `--logo-output`
exports original logo bytes into an ignored local `LeagueLogos` directory;
those assets must be copied beside the prepared runtime, never committed.
The staged 18-club selector also needs this cleansing pass before building
its NRO; otherwise its old 33 categories override the curated public selector
and the six removed sections reappear. Its CPK manifest and roster ID can
remain unchanged because the new selector is a subset with stable native IDs
and badge slots. The cleanser's `--paired-build-id` records the original
manifest ID in the generated selector include for build preflight.

For the local 18-club Bundesliga/Indonesia full-loose candidate, the NRO must
be built with `-PlayerMigrationCanary -LooseCpkFull
-ExpectedPatchObbSize 53248 -DisablePesdbAuthoritativeOvr`, and with the
matching candidate badge atlas, team include, roster include, scorer include,
Cup catalog header, and League catalog header. The two catalog headers must
be generated against the same staged selector, not the smaller committed
migration selector. Pass `-LooseManifest` to `build-wsl.ps1` for a fail-fast
check of the manifest, selector, roster ID, and OBB-size flags. The resulting
NRO's embedded ID must match the first line
of the installed `LooseCpk/manifest.txt`. A bare `build-wsl.ps1` NRO cannot
boot with the dummy OBB/full-loose package. Copy only the paired NRO plus
`LeagueLogos/` for this UI update; keep the matching OBB and LooseCpk intact.

## Art and implementation boundaries

- `art/league_hub_stadium_v1.png` is an original 16:9 stadium backdrop for
  League, distinct from Cup's backdrop. Its PNG bytes are linked as
  `data/league_hub_stadium.bin` and uploaded once for the Switch Hub.
- `art/league_hub_phase_concept.png` shows the five-row table and four-match
  schedule at 1280×720. Initial badges are schematic lettermarks to reserve
  atlas space; production UI should draw actual full-color team badges at
  native size, not enlarge a low-resolution intermediary.
- `art/league_hub_scorer_concept.png` and
  `art/league_hub_knockout_concept.png` detail the two alternative panels.
  Their SVG siblings are editable vector sources.
- Save slots use two checksummed copies under `SaveData/footballnx_league_*`.
  They store rules, assignments, fixture results, table, knockout, and general
  match settings. Version 3 adds competition identity and League System and
  can read version-1 and version-2 saves as custom knockout seasons.
  No proprietary game data is committed.
- Cup and League Save/Load cards share a three-row layout below the title.
  Each valid slot shows its saved competition and current round or matchday;
  this display metadata is derived when slots are scanned and does not change
  either save format. Retired League presets keep their original name in the
  slot list even though new setup no longer offers them.

Background generated with the built-in image generation tool in
`stylized-concept` mode. Prompt: original cinematic 16:9 FootballNX League
night stadium; modern bowl, distant stands, floodlights and angular edge
graphics; quiet dark center for opaque UI panels; deep navy/electric cobalt
with restrained gold; no players, trophy, words, numbers, logos or watermarks.

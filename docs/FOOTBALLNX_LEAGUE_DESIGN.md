# FootballNX League

Status: League season, save slots, match handoff, standings, knockout, and
Switch Hub render are implemented. The concept PNGs remain design references,
not screenshots. Top Scorer ranks individual players after goals are recorded;
it does not invent scorers for a played match when native player statistics
are unavailable.

## Flow and shared controls

`League > League Settings > League Hub`. League Settings mirrors the Cup
settings layout, with FootballNX League as the initial and only League Type.
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

After the League Phase, the top 2 (for 2–3 teams), 4 (for 4–7), or 8 (for
8–32) qualify for a single-leg knockout. Seeds are 1v8/4v5/2v7/3v6 or
1v4/2v3. The left panel becomes the Knockout Bracket with two matches per
page and a champion card at completion. L1/R1 changes round, up/down changes
the two-match page, and Y continues to toggle the right panel. Completed
League has only `Top to Menu` and A/Confirm.

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
  match settings. Version 2 adds scorer totals and can read version-1 saves.
  No proprietary game data is committed.

Background generated with the built-in image generation tool in
`stylized-concept` mode. Prompt: original cinematic 16:9 FootballNX League
night stadium; modern bowl, distant stands, floodlights and angular edge
graphics; quiet dark center for opaque UI panels; deep navy/electric cobalt
with restrained gold; no players, trophy, words, numbers, logos or watermarks.

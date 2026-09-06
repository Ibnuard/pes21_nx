# Exhibition Team Catalog

This generated catalog is the source of truth for the custom team selector,
team names, compact badge slots, and native PES21 fallback rosters.

## Safety gate

- Catalog content ID: `29914839e0782650`
- EF10 Team.bin records: 931
- PES21 Team.bin records: 736
- EF10 Player.bin records: 21701
- PES21 Player.bin records: 43074
- Team IDs present in both: 480
- Safe shared teams with complete rosters/tactics/badges: 464
- Retained legacy-only selector teams: 6
- Final selector teams: 470
- Compact atlas slots, including slot 0 and category emblems: 502

Phase one deliberately uses the native PES21 roster for newly exposed teams.
An existing converted EF10 roster wins when present; legacy manual rosters are
only the final fallback. Full EF10 player conversion and duplicate-name cleanup
remain separate later phases.

## Generated runtime data

- `data/exhibition_team_catalog.json`: canonical team/category manifest
- `source/exhibition_teams_generated.inc`: selector order, names, and badge slots
- `source/exhibition_rosters_pes21_generated.inc`: native PES21 fallback rosters
- `source/badge_atlas.h`: compact atlas metadata and runtime symbol declaration
- `data/badge_atlas.bin`: raw RGBA team/category badge atlas

Team IDs are never used as atlas indexes. Compact slots are regenerated from
the manifest, so high native IDs do not allocate sparse texture space.

## Categories

| Category | Shared | Legacy | Total |
|---|---:|---:|---:|
| ENGLISH LEAGUE | 19 | 0 | 19 |
| ENGLISH 2ND DIV | 20 | 0 | 20 |
| SPANISH LEAGUE | 20 | 0 | 20 |
| SPANISH 2ND DIV | 16 | 0 | 16 |
| LIGUE 1 | 18 | 1 | 19 |
| LIGUE 2 | 13 | 0 | 13 |
| SERIE A | 19 | 0 | 19 |
| SERIE B | 10 | 0 | 10 |
| EREDIVISIE | 12 | 0 | 12 |
| LIGA PORTUGAL | 12 | 0 | 12 |
| GERMAN TEAMS | 1 | 1 | 2 |
| TURKISH LEAGUE | 15 | 0 | 15 |
| SCOTTISH LEAGUE | 9 | 0 | 9 |
| DANISH LEAGUE | 10 | 0 | 10 |
| BELGIAN LEAGUE | 12 | 0 | 12 |
| SWISS LEAGUE | 10 | 0 | 10 |
| OTHER EUROPE | 21 | 3 | 24 |
| BRAZIL SERIE A | 19 | 0 | 19 |
| BRAZIL SERIE B | 16 | 0 | 16 |
| ARGENTINA LEAGUE | 23 | 0 | 23 |
| CHILEAN LEAGUE | 15 | 0 | 15 |
| COLOMBIAN LEAGUE | 17 | 0 | 17 |
| J1 LEAGUE | 20 | 0 | 20 |
| J2 LEAGUE | 15 | 0 | 15 |
| THAI LEAGUE | 12 | 0 | 12 |
| WORLD / EDIT CLUBS | 2 | 0 | 2 |
| NATIONAL EUROPE | 41 | 1 | 42 |
| NATIONAL AFRICA | 14 | 0 | 14 |
| NATIONAL N AMERICA | 6 | 0 | 6 |
| NATIONAL S AMERICA | 10 | 0 | 10 |
| NATIONAL ASIA OCEANIA | 17 | 0 | 17 |

## Top-flight source exclusions

These EF10 league members were not admitted because the same team ID does
not pass the cross-version safety gate.

- English League: 396 (SUNDERLAND RWB)
- Serie A: 4219 (COMO A)
- Eredivisie: 253 (FC VOLENDAM), 352 (SC TELSTAR), 346 (GO AHEAD EAGLES), 344 (EXCELSIOR ROTTERDAM), 247 (N.E.C. NIJMEGEN), 246 (NAC BREDA)
- Liga Portugal: 5954 (AVS FUTEBOL), 2380 (FC AROUCA), 5845 (FC ALVERCA), 5844 (CF ESTRELA DA AMADORA), 5633 (CASA PIA AC), 2383 (GD ESTORIL PRAIA)

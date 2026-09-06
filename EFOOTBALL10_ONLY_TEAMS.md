# eFootball 10 Teams Missing From PES21 IDs

This generated audit compares raw `Team.bin` IDs. A missing raw ID does
not automatically mean a missing club: some teams were re-numbered or
renamed between versions. Alias candidates therefore remain review-only.
No runtime selector or database files are changed by this audit.

## Counts

- Audit content ID: `e23681f95366d201`
- EF10 team records: 931
- PES21 team records: 736
- EF10 player records: 21701
- PES21 player records: 43074
- EF10-only raw IDs: 451
- Configured club IDs: 221
- Configured national IDs: 109
- Unclassified IDs: 121
- Alias candidates: 35
- Alias review rows: 4
- Surrogate-required rows: 412

## Focus teams

| EF10 ID | EF10 name | Kind | Roster | Shared players | Classification | PES21 candidate |
|---:|---|---|---:|---:|---|---|
| 126 | Borussia Dortmund | club | 37 | 10 | surrogate_required | - |
| 5738 | Miami BP | club | 27 | 8 | surrogate_required | - |
| 17730 | Al Rayyan SC | club | 29 | 0 | surrogate_required | - |
| 17733 | Al-Ahli Saudi FC | club | 35 | 0 | surrogate_required | - |
| 17873 | Al Hilal SFC | club | 35 | 0 | alias_candidate | `67025` AL HILAL |
| 17877 | Buriram United F.C. | club | 29 | 0 | alias_candidate | `1493` BURIRAM UNITED |
| 17962 | Sydney FC | club | 32 | 0 | alias_candidate | `67114` SYDNEY |
| 18961 | Al Nassr FC | club | 31 | 0 | alias_candidate | `68113` AL NASSR |
| 20478 | Shanghai Port FC | club | 30 | 0 | surrogate_required | - |
| 20557 | Al Sadd SC | club | 35 | 0 | alias_candidate | `69709` AL SADD |
| 20560 | Shabab Al Ahli Dubai FC | club | 34 | 0 | alias_candidate | `69712` SHABAB AL AHLI DUBAI |
| 21557 | Shanghai Shenhua FC | club | 32 | 0 | alias_review | `5173` SHANGHAI SHENHUA, `70709` SHANGHAI SHENHUA |

## Surrogate-required clubs by source category

Counts below are category memberships; a team can appear in more than one
source category (notably `WORLD / EDIT CLUBS`).

| Category | Teams |
|---|---:|
| ARGENTINA LEAGUE | 7 |
| BELGIAN LEAGUE | 4 |
| BRAZIL SERIE A | 1 |
| BRAZIL SERIE B | 8 |
| CHILEAN LEAGUE | 1 |
| COLOMBIAN LEAGUE | 3 |
| DANISH LEAGUE | 2 |
| ENGLISH 2ND DIV | 4 |
| ENGLISH LEAGUE | 1 |
| EREDIVISIE | 6 |
| J2 LEAGUE | 5 |
| LIGA PORTUGAL | 6 |
| LIGUE 2 | 5 |
| N AMERICA CLUBS | 59 |
| OTHER ASIA CLUBS | 47 |
| OTHER EUROPE | 9 |
| SCOTTISH LEAGUE | 3 |
| SERIE A | 1 |
| SERIE B | 10 |
| SPANISH 2ND DIV | 6 |
| SWISS LEAGUE | 2 |
| THAI LEAGUE | 4 |
| TURKISH LEAGUE | 3 |
| WORLD / EDIT CLUBS | 179 |

## Interpretation

- `alias_candidate`: one PES21 team has the same normalized club name;
  confirm the mapping before using its native team slot.
- `alias_review`: multiple PES21 teams share the normalized name;
  requires an explicit mapping decision.
- `surrogate_required`: no normalized PES21 name candidate exists;
  a donor team slot and player conversion plan are required.

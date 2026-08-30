# eFootball 10 Player/Roster Compatibility Update

This report is generated from the locally supplied eFootball 10.0.0 XAPK.
No source database records are redistributed: the compiled code contains only
team membership IDs, order, and shirt numbers.
Related national teams reuse the persistent surrogate ID selected for the
same EF10 player in the converted club roster.

## Result

| Team ID | Symbol | EF10 entries | PES21-compatible | PES21 fallback | Status |
|---:|---|---:|---:|---:|---|
| 7 | `spain` | 26 | 25 | 0 | active (25) |
| 8 | `france` | 26 | 20 | 0 | active (20) |
| 10 | `netherlands` | 26 | 23 | 0 | active (23) |
| 14 | `germany` | 26 | 15 | 3 | active (18) |
| 15 | `denmark` | 26 | 23 | 0 | active (23) |
| 19 | `poland` | 26 | 16 | 2 | active (18) |
| 45 | `brazil` | 26 | 19 | 0 | active (19) |
| 49 | `uruguay` | 26 | 17 | 1 | active (18) |
| 108 | `barcelona` | 38 | 38 | 0 | active (38) |

Players marked below exist in EF10 but not in the selected PES21-schema
master database. They cannot be used safely by the current CommonWork runtime.

### 7 / `spain`

- `159586` — Dean Huijsen (shirt 11)
### 8 / `france`

- `116655` — Dayot Upamecano (shirt 3)
- `114975` — Ibrahima Konaté (shirt 14)
- `157339` — Warren Zaïre-Emery (shirt 17)
- `152928` — Désiré Doué (shirt 23)
- `147955` — Bradley Barcola (shirt 19)
- `108069` — Marcus Thuram (shirt 8)
### 10 / `netherlands`

- `142128` — Mark Flekken (shirt 22)
- `136184` — Micky van de Ven (shirt 14)
- `104805` — Nick Olij (shirt 12)
### 14 / `germany`

- `113281` — Benjamin Henrichs (shirt 25)
- `142177` — M. Mittelstädt (shirt 17)
- `142063` — Waldemar Anton (shirt 20)
- `142237` — Nico Schlotterbeck (shirt 14)
- `146017` — David Raum (shirt 21)
- `142238` — Robert Andrich (shirt 22)
- `162163` — Aleksandar Pavlović (shirt 24)
- `146006` — Deniz Undav (shirt 12)
- `142147` — Oliver Baumann (shirt 11)
- `146020` — Jamie Leweling (shirt 13)
- `142211` — Niclas Füllkrug (shirt 8)
### 15 / `denmark`

- `120461` — Rasmus Kristensen (shirt 12)
- `164926` — Patrick Dorgu (shirt 16)
- `152073` — Mika Biereth (shirt 24)
### 19 / `poland`

- `176046` — Mateusz Skrzypczak (shirt 15)
- `147706` — Jakub Kiwior (shirt 13)
- `143775` — Bartosz Slisz (shirt 16)
- `102750` — Mateusz Wieteska (shirt 3)
- `123147` — P. Frankowski (shirt 18)
- `143435` — Jakub Kamiński (shirt 12)
- `142635` — Adam Buksa (shirt 23)
- `159386` — Maximillian Oyedele (shirt 19)
- `125382` — Jakub Piotrowski (shirt 5)
- `172263` — Dominik Marczuk (shirt 24)
### 45 / `brazil`

- `141619` — Vanderson (shirt 1)
- `167167` — Estêvão (shirt 19)
- `119531` — Matheus Cunha (shirt 8)
- `143844` — Beraldo (shirt 14)
- `135038` — João Gomes (shirt 18)
- `154217` — Murillo (shirt 23)
- `157472` — Endrick (shirt 25)
### 49 / `uruguay`

- `102895` — Sergio Rochet (shirt 0)
- `147895` — Maximiliano Araújo (shirt 19)
- `130927` — Santiago Mele (shirt 22)
- `131722` — Nicolás Fonseca (shirt 25)
- `146371` — Facundo Torres (shirt 20)
- `102986` — Rodrigo Aguirre (shirt 6)
- `170862` — Luciano Rodríguez (shirt 24)
- `145746` — Sebastián Cáceres (shirt 2)
- `146559` — Joaquín Piquerez (shirt 21)

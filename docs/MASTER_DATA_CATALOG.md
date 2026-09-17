# PES21 NX master data catalog

This catalog is the stable lookup layer for player, team, competition,
formation, asset, and kit work. It is generated; do not hand-edit its CSV
registries or local SQLite database.

## Active snapshot

- Source: `eF26_v551`
- Migration build: `1852ec648d2ebd75`
- Snapshot content ID: `304796954c6ba9bf`
- Local database SHA-256: `b171a486c58221afd61892aed2926cff7620573fe8cd3d2e8a1adc1f06472dda`
- EF BaseIds indexed: **24,174**
- Materialized players: **12,653**
- Playable teams: **443**
- Selector competitions/categories: **33**
- Audit: **PASS**

## Storage contract

- `local-inputs/master-data/pes21_master.db` is the complete local source for
  joins and ad-hoc SQL. It includes full player stats and local provenance and
  therefore remains ignored.
- `data/master/player-id-registry.csv` is the stable `BaseId` to native ID map.
- `data/master/team-registry.csv` maps logical teams to physical PES21 slots.
- `data/master/competition-registry.csv` records selector groups and licensed
  display labels.
- `local-debug/master-exports/` contains disposable full CSV exports.
- The locked EF snapshot remains under `local-inputs/`; raw game payloads are
  never copied into this public catalog.

## Database tables

| Table | Rows | Purpose |
|---|---:|---|
| `metadata` | 14 | Snapshot versions, content IDs, source paths, and hashes. |
| `competitions` | 33 | Selector leagues/categories and their licensed labels. |
| `teams` | 443 | Logical EF team IDs and native PES21 physical slots. |
| `excluded_teams` | 37 | Teams deliberately excluded from the playable scope. |
| `ef_player_catalog` | 24,174 | Every EF26 BaseId in the locked 24,174-player index. |
| `players` | 12,653 | Materialized canonical players and stable native identities. |
| `player_stats` | 12,653 | Full canonical/highest-OVR EF data, one wide row per player. |
| `player_aliases` | 29 | Identity aliases retained by the resolver. |
| `team_rosters` | 13,653 | Club/national memberships, shirt numbers, and order. |
| `formation_slots` | 9,746 | Locked API formation roles and pitch coordinates. |
| `starting_lineups` | 4,873 | Final formation-aware selected eleven for each team. |
| `player_assets` | 12,653 | Portrait, face, and commentary ownership/status. |
| `team_kits` | 443 | Per-team migration or preservation state. |
| `kit_variants` | 1,209 | Converted home, away, and goalkeeper kit provenance. |
| `source_artifacts` | 7 | Input files and hashes used to build this database. |
| `field_dictionary` | 150 | Mapping from EF source field names to SQL columns. |

Convenience views `v_team_rosters` and `v_starting_eleven` provide joined,
human-readable names and positions.

## Regeneration

```powershell
python tools/pes21_master_data.py sync
python tools/pes21_master_data.py audit
python tools/pes21_master_data.py export
```

Run `sync` whenever the locked EF version, migration build, formation hints,
portrait report, or kit report changes. `audit` blocks mismatched identities,
invalid references, incomplete rosters, or incomplete final lineups. `export`
creates one CSV for every master table and view without changing committed
registries.

## Common queries

```sql
-- Find a player and every club/national assignment.
SELECT * FROM v_team_rosters WHERE canonical_name LIKE '%Messi%';

-- Inspect one team's final eleven and pitch coordinates.
SELECT * FROM v_starting_eleven WHERE team_id = 108 ORDER BY slot;

-- Find portrait fallbacks or identities without commentary.
SELECT p.canonical_name, a.*
FROM player_assets a JOIN players p USING(base_id)
WHERE a.portrait_status = 'placeholder' OR a.commentary_owner_id IS NULL;
```

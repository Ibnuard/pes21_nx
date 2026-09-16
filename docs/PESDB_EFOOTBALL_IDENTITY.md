# PESDB eFootball identity pipeline

Player values in this lane come from `https://pesdb.net/efootball` only.
PES21 is not an identity, rating, or stat fallback; it is used later only as
the fixed target binary format and physical slot inventory.

## Flow

1. `tools/resolve_pesdb_player_ids.py` compares EF10 source IDs/names with the
   current PESDB sitemap and emits a review manifest.
2. Direct ID matches with normalized names are high-confidence. Exact-name
   candidates for retired IDs are review-only by default because several
   current cards can share a name.
3. `tools/import_pesdb_identity_map.py` fetches authentic PESDB rows for an
   explicitly accepted identity map and re-keys the snapshot by EF10 source ID.
4. `tools/convert_efootball10_players.py --require-pesdb` refuses to create a
   release artifact if any selected player lacks an authentic PESDB row.

## Current audit

The local all-team source set contains 2,596 selected EF10 player IDs. The
identity audit currently accepts only high-confidence direct IDs and reports
the rest for review; this is intentionally not a release snapshot.

```powershell
python tools/resolve_pesdb_player_ids.py `
  --ids-file local-debug/efootball10-all-teams-patch/validation-report.json `
  --ids-file local-debug/efootball10-original-inter-miami-full/original-id-map.json `
  --output local-debug/pesdb-efootball-identity-map-all-active.json
```

Do not pass `--accept-exact-name` for a release without reviewing each row.
`ambiguous_name`, `unresolved`, and unapproved name mismatches are release
blockers.

# PESDB eFootball player import

`tools/import_pesdb_efootball.py` treats `https://pesdb.net/efootball` as the
authoritative player source. The default `authentic` endpoint is the offline
authentic-card view; use `--source standard` only when a Standard/Dream Team
snapshot is explicitly wanted.

The importer caches each normalized player response under `local-debug/` and
emits a content-addressed snapshot. It currently marks the following as
verified for the PES21-mobile target: names, nationality, registered position
when supplied by the EF10 conversion path, and the 25 six-bit gameplay
abilities already proven by `tools/convert_efootball10_players.py`.

Skills, playing styles, foot, form, injury resistance, height/weight, and
body-model values are retained in the snapshot but remain `unsupported` for
binary writes until their PES21-mobile offsets are independently verified.
This prevents a current PESDB value from being written into an unrelated
packed field.

Example:

```text
python tools/import_pesdb_efootball.py --player-id 7511 --player-id 4522 \
  --snapshot local-debug/pesdb-messi-ronaldo.json
```

PES21 files may be supplied to a later conversion command only as target-format
references. They are never used as a fallback source for player ratings.

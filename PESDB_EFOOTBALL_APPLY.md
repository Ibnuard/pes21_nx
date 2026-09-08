# Applying PESDB eFootball snapshots

`tools/apply_pesdb_efootball.py` consumes a snapshot produced by
`tools/import_pesdb_efootball.py` and writes an isolated `Player.bin` patch.
Use `--target-map` for EF10 IDs that are represented by PES21 surrogate slots
(the converter's `surrogate-map.json` is accepted directly).

The command fails closed when coverage is below `--min-coverage`. It writes
only fields whose PES21-mobile layout is verified: the player display name,
registered position, and 25 gameplay abilities. PESDB OVR is reported but not
written because the game calculates OVR from attributes and position. Skills,
foot, playing style, form, body model, and nationality code remain in the
snapshot/report until their target offsets are proven.

Release commands must pass `--require-authentic`. This rejects standard-card
or mixed-source snapshots; the team/original-ID converters additionally use
`--require-pesdb` to require coverage for every selected roster member. PES21
player values are never used as fallback data.

No stable `dist/` file is modified by this command.

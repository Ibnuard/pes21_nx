# PES21PLAYERMIGRATION

`tools/pes21_player_migration.py` is the deterministic bridge from the local
eFootball source in `../tools/PESDBTools` to PES21 mobile/Switch.

The source of truth is EF `BaseId`. `NativePES21Id` is a stable engine address
that may differ to preserve verified PES21 faces and commentary. Card IDs are
version-specific inputs and are never written as identity keys.

Player names also follow the EF26 canonical form. A legacy PES21 label such as
`S. MANÉ` may be used only during the initial identity/face verification; the
registry and rebuilt `Player.bin` store `Sadio Mané`, together with a normalized
audit key. Future updates match by `BaseId` first, never by display name alone.

## Workflow

```powershell
python tools/pes21_player_migration.py sync
python tools/pes21_player_migration.py audit
python tools/pes21_player_migration.py canary --package
```

`sync` copies and hashes `db_eF26_v551.json`, optionally fetches the EF
Appearance table through `pull_pesdb.py`, extracts the active release's dt200
and dt241 archives plus its native tactics tables, selects playable teams, and writes an offline source lock
under `local-inputs/pes21-player-migration/eF26_v551/`.

The current canary is deliberately rebased on
`local-checkpoints/2026-09-16-startup-brand-v4/patch.305030001.jp.nyan2021.pesam.obb`
(SHA-256 `D58B4BAACF7D0945A465E975C02C9F46D94C03D4EAFBB6A41ED4F74900FF6661`).
Only dt200 and dt241 are replaced. Every other outer CPK, including dt210
startup branding and dt240 native team assets, is verified byte-identical to
that checkpoint.

`audit` enforces the approved 443-team scope and writes the persistent compact
registry at `data/pes21_player_registry.json`. The registry contains identity
and ownership hashes, not the proprietary stats database. It also writes the
443-team selector catalog/include and an offline `change-report.json` covering
added, removed, transferred, stat-changed, name-changed,
portrait-source-changed, and unresolved BaseIds. Removed identities become tombstones; their native and
physical slots are not silently recycled.

`canary --package` patches only fields whose PES21 layout is proven, downloads
portraits through PESDBTools, uses a neutral placeholder when unavailable, and
builds a detachable OBB under `local-debug/pes21-player-migration-canary/`.
The normal release OBB is never overwritten.

The PESDatabase GUI's normal “Convert to PES 2021” export does not store an
OVR field or rescale the 25 base abilities; it maps the EF abilities into the
PES21 schema. The green OVR shown on the EF26 page is calculated by the EF26
formula. The canary therefore keeps those source abilities, copies PES21's
proven basic/familiarity fields, and embeds the authoritative EF26 `Overall`
for Game Plan display and selection. Starting XIs are solved against the
native formation roles using that same EF26 OVR. Assignment order from EF26 is
not treated as a starting-XI flag (for example, Messi is assignment 21 at
Inter Miami in v5.5.1).

Squad refresh uses the lookup key at the start of each native `SquadPlayer`,
not the PlayerId inside its normal/boosted player copies. The native loader
initializes that key from matchPlan before hydration: its unique ID at offset
4 is XOR-protected with `common::GetCryptKey()`, and its storage locator occupies
the first two bytes. This locator is not a card type: native CommonWork uses
it for indexed lookup and routes the special HOME/AWAY locators to Match.
The match-local locator must not be compared with the master database locator.
Refresh validates the unique identity against the selected
roster and CommonWork before filling both copies. Vector position is not an
identity mapping.

The earlier canary incorrectly trusted the unhydrated copies, which can hold
nonzero placeholders or donor players. This rejected valid squad entries and
left Game Plan showing `PLAYER n`/donor names without portraits even though
the hub list was correct. The executable host regression covers those cases,
reordered vectors, repeated refresh, both parameter copies, invalid/duplicate
keys, different match/master locators, native setter read-back, and preservation
of lookup key/serial/stamina fields. The next hardware report showed that the
decoded unique IDs were correct (including Messi 7511 and Ronaldo 4522), but
the incorrect locator equality guard rejected all 26 Miami and 34 Al Nassr
players. Removing that guard makes this case pass in the host regression;
the destination lookup key is preserved while both player copies are hydrated
from the validated master row. The selected copy is read back before counting
a successful refresh. Hardware confirmation of
Game Plan and match identity is still required. This correction changes only
the NRO; the rebased canary OBB remains unchanged.

The first hardware package contains seven representative teams and 202
canonical players. Its rewritten `Player.bin` remains exactly 43,074 rows;
`InstallVersionPlayer.bin` carries the identical ID set. Native assignments
are rebuilt for the canary teams, 3D-face owner IDs are protected using a
locked inventory read directly from the active PES21 PAK, and the matching NRO
embeds the same `migration_build_id` recorded by the hardware report.

Copy both files from the canary directory for a test; do not pair either file
with an older artifact:

- `pes21_nx.nro`
- `patch.305030001.jp.nyan2021.pesam.obb`

Use a clean `SaveData` directory for the migration canary. Existing Edit Data
is intentionally not migrated.

The global `build` stage fails closed until:

1. `hardware-canary-report.json` is changed to `result: hardware_pass` after
   the listed Switch checks are completed; and
2. the remaining PES21 field/table mapping blocker is removed by verified
   round-trip tests.

No PESDB scraper, surrogate player, or portrait alias is part of this flow.

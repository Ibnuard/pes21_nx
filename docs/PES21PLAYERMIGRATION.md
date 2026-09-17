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

Identity and gameplay card selection are deliberately separate. Name,
nationality, biography, assignment, portrait, appearance, face, and commentary
ownership come from the canonical base identity. Gameplay data comes from the
variant with the highest EF `Overall` for that same BaseId. This supplies OVR,
abilities, form/weak foot, player skills, and COM styles. Registered position,
position familiarity, and playing style remain base-card data because a
promotional card may deliberately reinvent a player's role. For example,
Frenkie de Jong keeps his base CMF/Orchestrator role while using the abilities
and OVR 90 from his strongest card. A direct/default card wins only an
equal-OVR tie, so a genuinely stronger Dream Team variant is not discarded.
The registry records both `source_card_id` and `stats_source_card_id`.

Starting XI selection is formation-aware. It maximizes full position
familiarity, partial/neighbor compatibility, then registered-position matches,
before lineup preferences and authoritative OVR. A stronger promotional card
must not move a natural CF onto the wing just to increase total OVR.

Optional eFootballDB tactics hints supply roles, pitch coordinates, and preferred
starting BaseIds. They never supply player stats, transfers, or new identities.
The live API is not version-locked to eF26_v551: fetch hints explicitly, inspect
the missing-player report, then build offline from that saved file:

```powershell
python tools/import_team_tactics.py --team 108 --team 5738 `
  --output local-inputs/pes21-player-migration/eF26_v551/team-tactics.json
python tools/pes21_player_migration.py canary --package `
  --tactics-hints local-inputs/pes21-player-migration/eF26_v551/team-tactics.json `
  --output local-debug/pes21-player-migration-formation-v4 `
  --loose-base-root local-debug/pes21-player-migration-role-v2
```

The converter joins assignment order to formation slot and preserves API
response hashes, URLs, and fetch time. Available API starters are pinned to
their exact slots, even when the tactical role differs from their registered
position (e.g. Fermin at CMF or Raphinha at CF). Keeper/outfield crossings are
rejected. Missing preferred BaseIds are substituted from the remaining locked
roster using position fit, registered position, then OVR. Other teams use
their native template. A wide-midfield slot promoted to RWF/LWF also moves to
depth 39 or beyond on the native 0..48 pitch. Barcelona's API 4-3-3 has no AMF,
so an API starter such as Fermin occupies the specified CMF slot.

Native TacticsFormation rows encode depth and width in the low two bytes,
slot in bits 16..19, and phase in bits 20..21. Read and patch by encoded slot,
not physical row order. Write roles and coordinates to both team tactics and
all existing phases so attacking/defensive state uses the same roster contract.
The initial imported template is shared across these phases; distinct dynamic
phase layouts are not imported yet. The formation-v4 hardware checkpoint
confirmed correct field positions and identities after opening Game Plan and
entering a match. Every future full snapshot must repeat those checks.

Runtime roster installation must reset the selected **Coach** appointment order,
not a Team field. On the supported native binary, `GetAppointmentOrder` reads
40 order bytes at Coach+0x218. Team+0x218 overlaps member IDs 33..37 and must
never receive an order array. Resolve Team's CoachId at +0x250 through
CommonWork::UpdateCoach with the native mask `0xffffffff0000ffff`, then set
Coach+0x218 to the generated roster order before SetExhibitionTeam copies it.
The executable host regression uses all 40 members, verifies independent coach
storage, preserves adjacent fields, and requires a missing coach to fail before
writing the Team. This fixes the old coach permutation moving Yamal into CMF
and Lewandowski onto the wing despite correct CPK roles and generated rosters.

## Workflow

The full migration order is a build contract, not four interchangeable jobs:

1. Recreate the canonical player catalog from the locked PESDBTools snapshot,
   keyed by `BaseId`, and assign stable `NativePES21Id` values.
2. Apply canonical identity/biography/appearance plus highest-OVR gameplay
   stats, and generate each player's portrait through PESDBTools.
3. Materialize the playable team assignments, then fetch and lock that team's
   formation, coordinates, roles, and preferred starting BaseIds.
4. Set the native formation and solve the starting XI against the recreated
   roster. An API player absent from the locked EF26 roster is replaced by the
   best remaining player for that exact slot; the API never creates identities.

This ordering prevents a live lineup response from selecting stale PES21 rows
or card IDs before the canonical roster exists. Once the source and tactics
snapshots are locked, `audit`, `canary`, and `build` remain offline and
deterministic.

```powershell
python tools/pes21_player_migration.py sync
python tools/pes21_player_migration.py audit
python tools/pes21_player_migration.py canary --package `
  --loose-base-root local-debug/loose-cpk-full-v1
python tools/pes21_player_migration.py build `
  --hardware-report local-debug/pes21-player-migration-formation-v4/hardware-canary-report.json `
  --tactics-hints local-inputs/pes21-player-migration/eF26_v551/team-tactics-full.json `
  --loose-base-root local-debug/loose-cpk-full-v1 `
  --output local-debug/pes21-player-migration-full-v1
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
portraits through PESDBTools, and uses a neutral placeholder when unavailable.
With `--loose-base-root`, it hard-links the verified full loose-CPK checkpoint,
replaces only dt200/dt241, writes the new build-bound manifest, and compiles its
matching NRO. The stable source package and normal release OBB are never
overwritten; filesystems without hard-link support fall back to safe copies.

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
a successful refresh. The hardware canary confirmed Game Plan portraits/names
and match identity after this correction. It changes only the NRO; the rebased
canary OBB remains unchanged.

The hardware canary contains seven representative teams and 202
canonical players. Its rewritten `Player.bin` remains exactly 43,074 rows;
`InstallVersionPlayer.bin` carries the identical ID set. Native assignments
are rebuilt for the canary teams, 3D-face owner IDs are protected using a
locked inventory read directly from the active PES21 PAK, and the matching NRO
embeds the same `migration_build_id` recorded by the hardware report.

When updating an installed `loose-cpk-full-v1` runtime with another canary,
close the game and copy these files from the canary directory:

- `pes21_nx.nro`
- `LooseCpk/dt200_mobile_all.cpk`
- `LooseCpk/manifest.txt` **last**

Delete `LooseCpk/verified-v2.txt` before the next boot. The dummy OBB and
dt241 are byte-identical to the stable package for this stats-only update, so
they do not need to be recopied. Never combine the new manifest with an older
NRO or dt200.

Use a clean `SaveData` directory for the migration canary. Existing Edit Data
is intentionally not migrated.

## Full migration build

The formation-v4 hardware canary is signed off. The global `build` stage now
materializes all 443 playable teams and 12,653 canonical EF26 players while
preserving the fixed 43,074-row PES21 table. It rebuilds Player,
InstallVersionPlayer, PlayerAssignment, SpecialPlayerAssignment,
PlayerAppearance, PlayerWeekly, PlayerDeleteList, Boots, and
TacticsFormation together. The same locked input is rebuilt twice and every
modified table must be byte-identical before packaging continues.

The first complete artifact has migration build ID `1852ec648d2ebd75` and is
written locally under `local-debug/pes21-player-migration-full-v1/`. Install it
as one atomic set:

- `pes21_nx.nro`
- `patch.305030001.jp.nyan2021.pesam.obb` (the loose-CPK dummy OBB)
- the complete `LooseCpk/` directory, including `manifest.txt`

Do not mix any one of those files with the canary package. Start from clean
SaveData/Edit Data for the first full-migration boot. The generated
`full-hardware-report.json` is intentionally local and remains
`awaiting_hardware_validation` until selector, Game Plan, identity assets,
club/national overlap, and repeated-match checks pass on Switch.

For this build, 5,402 portraits replace existing CPK members, 7,251 are added,
and 1,222 unavailable source portraits use the neutral silhouette. Missing
portraits never borrow another player's image. The complete source/tactics
snapshots and binary artifacts stay in ignored local directories; only the
stable registry, generator, tests, and generated runtime roster metadata are
public source.

No PESDB scraper, surrogate player, or portrait alias is part of this flow.

## Unified master-data catalog

After a migration build, run `tools/pes21_master_data.py sync`, `audit`, and
`export`. The pipeline joins the locked player snapshot, stable ID registry,
443-team catalog, roster memberships, formation hints, final starting elevens,
portrait/face/commentary ownership, and kit migration report into the ignored
`local-inputs/master-data/pes21_master.db`. Compact identity/team/competition
registries remain under `data/master/`; complete CSV exports stay under
`local-debug/master-exports/`. See `docs/MASTER_DATA_CATALOG.md` for the schema,
counts, provenance, and example queries.

# FL26 Bundesliga and Indonesia candidate

This is a local-source candidate, not a hardware-validated release. Run:

```powershell
python tools/audit_fl26_bundesliga_indonesia.py
python -m pytest tests/test_fl26_team_expansion.py -q
```

The audit reads the installed Football Life 2026 CPKs and the locked eF26
registry. Its IDs/counts-only report is written to the ignored
`local-debug/fl26-team-expansion-audit.json`; it does not extract copyrighted
assets into the public tree.

## Verified source coverage

- FL26 competition 39 lists 18 distinct Bundesliga clubs. All 18 have a
  crest and source home/away/goalkeeper kit descriptor.
- The current migration selector places only Bayer Leverkusen in its
  `german_teams` category. Borussia Dortmund is playable but is under
  `other_europe`; Eintracht Frankfurt has a complete eF26 roster but is not
  in the selector. The other 15 FL26 Bundesliga clubs have fewer than 18
  assignments (in this locked eF26 source, zero), so displaying all 18 now
  would produce invalid teams.
- FL26 team 5750 is Indonesia. Both FL26 and the locked eF26 source contain
  26 roster assignments. FL26 also has its crest and home/away/keeper kit.
  Only nine of those eF26 BaseIds are currently allocated in the public player
  registry; the rest require identity-safe native allocation. A detached
  `sync` + `audit` candidate passed with 17 new players, 19 former Israel-only
  players removed, 16 membership transfers, and zero unresolved identities;
  it has not been promoted to the public registry or runtime.
- The candidate audit also reported 268 existing-player stat hash changes.
  Comparing the same code against the original catalog reproduced all 268;
  replacing Israel with Indonesia caused **zero** additional data changes.
  This is baseline/code drift that must be reconciled independently before
  release, not an effect of the Indonesia roster.
- The current logical Israel team 1164 uses native physical slot 1164. A
  proposed Indonesia replacement may reuse that physical slot only after
  native team identity, assignments, tactics, kit and crest are all replaced
  together. Renaming alone would retain Israel's roster/assets.

## Safe local staging

`python tools/stage_indonesia_selector.py` creates a new ignored directory
`local-debug/indonesia-selector-candidate/` containing an Indonesia selector
catalog, matching generated include, and atlas badge cell. The stage reuses
Israel's logical badge slot to avoid reshuffling all other badges. It is
explicitly marked `selector_staged_not_playable`; do not copy these artifacts
to a release without the native OBB changes and an NRO/OBB hardware check.

The expanded local candidate can now be reproduced in order:

```powershell
python tools/plan_fl26_player_identities.py
python tools/plan_fl26_native_slots.py
python tools/stage_fl26_bundesliga_indonesia_selector.py --output local-debug/fl26-bundesliga-indonesia-selector-v2
python tools/stage_fl26_player_portraits.py --output local-debug/fl26-bundesliga-portraits-v2
python tools/stage_fl26_bundesliga_native_tables.py --output local-debug/fl26-bundesliga-indonesia-native-v2
python tools/stage_fl26_kit_scope.py --selector local-debug/fl26-bundesliga-indonesia-selector-v2/exhibition_team_catalog_migration.json --output local-debug/fl26-bundesliga-indonesia-selector-v2/kit-scope.json
python tools/build_full_mobile_kit_migration.py --catalog local-debug/fl26-bundesliga-indonesia-selector-v2/kit-scope.json --loose-base local-debug/full-mobile-kit-migration-v1 --output local-debug/fl26-bundesliga-indonesia-kit-candidate --preview-workers 4
python tools/stage_fl26_paired_cpks.py --native local-debug/fl26-bundesliga-indonesia-native-v2 --portraits local-debug/fl26-bundesliga-portraits-v2 --selector local-debug/fl26-bundesliga-indonesia-selector-v2 --output local-debug/fl26-bundesliga-indonesia-paired-v2
python tools/stage_fl26_migration_roster_include.py
python tools/stage_fl26_league_scorer_pool.py
.\build-wsl.ps1 -OutputDirectory local-debug/fl26-bundesliga-indonesia-paired-v2 -ExpectedPatchObbSize 53248 -DisablePesdbAuthoritativeOvr -PlayerMigrationCanary -LooseCpkFull -BadgeAtlas local-debug/fl26-bundesliga-indonesia-selector-v2/badge_atlas.bin -MigrationTeamInclude local-debug/fl26-bundesliga-indonesia-selector-v2/exhibition_teams_migration_generated.inc -MigrationRosterInclude local-debug/fl26-bundesliga-indonesia-selector-v2/exhibition_rosters_migration_canary_generated.inc -LeagueScorerInclude local-debug/fl26-bundesliga-indonesia-selector-v2/league_scorer_pool_generated.inc
python tools/verify_fl26_bundesliga_candidate.py
```

The build size argument is from this local dummy OBB, not a portable constant;
read the actual `.obb` length when reproducing on another checkout.

The current paired candidate has 459 selector teams, 18 Bundesliga clubs,
and Indonesia in logical ID 5750 mapped to native physical slot 1164. The
native Team.bin row now names Indonesia and has 26 assignments. Its old Europe
competition membership has moved to the Asia competition. The 18 club rosters
have 26–35 players each. FL26-only players use 376 clean native slots and
their 376 FL26 2D portraits; 154 verified eFootball BaseIds are reused, including
104 that already have active national-team membership. Existing club assignments
for transferred players are removed, but their national-team memberships are
preserved. Native Player.bin retains all 43,074 fixed unique IDs. All 19 teams
have FL26 home, away, and goalkeeper kit descriptors, matching texture assets,
and native 64/128/256px crest variants in the paired loose CPKs.

Thirty-one ambiguous identities were explicitly reviewed: 19 same-person
matches (name, age and position checked against the locked eFootball card)
reuse their BaseId, while 12 reused numeric IDs with different names receive
new native slots without inheriting donor faces/commentary. One Frankfurt
player has no FL26 portrait and remains held. Native tactics and starting-XI
fidelity still need review before release. The generated
`BootsList.bin` and `PlayerAppearance.bin` are absent from the mobile dt200
inventory; the packer records them as unpackageable auxiliary output rather
than adding unsupported members. The paired NRO compiles but has not been
tested on hardware. Do not publish/promote the candidate from `local-debug`
until match/gameplan, portrait, crest, uniform and save/load checks pass on a
Switch; no emulator test is required. Structural validation of the paired
candidate passed with the exact staged atlas embedded in the NRO and all
459 selector teams, 376 portraits and 19 kit/crest sets present. The NRO also
embeds the same 16-character build ID as the loose CPK manifest and a verified
Bundesliga roster sequence; without the generated migration-roster include,
the old build ID would make the runtime reject this candidate. Its League
scorer pool also covers all 459 teams; FL26-only scorers use a disjoint
high-bit tournament identity and their native portrait ID, so COM simulation
can populate Top Scorer for the new Bundesliga teams.

The MLS request is deferred by user choice. The installed FL26 competition
table does not provide a full MLS league; its current Switch North America
selector contains Inter Miami plus four Mexican clubs, so relabeling that
category as MLS would be inaccurate.

Indonesia's reused storage slot also needs a separate commentary identity
policy. See [Indonesia team commentary](TEAM_COMMENTARY.md) for the scoped
5750 name lookup and optional local English audio delta; renaming Team.bin
alone leaves the original slot's Israel recordings reachable.

## Release gates

1. Review native tactics and formation assignments for the 18 mapped physical
   slots; the detached table candidate currently preserves each slot's native
   formation rather than importing FL26 tactical rows.
2. Validate all visual and roster combinations on Switch hardware, including
   Indonesia, Bayern, Dortmund, one 4000-series club, Cup/League team select,
   match/gameplan, kit previews, portraits, and save/load.
3. Promote only a hardware-passed paired CPK/NRO candidate, never a selector or
   isolated team-table stage. Keep extracted game payloads ignored and local.

## Bundesliga default-XI correction (2026-10-05)

The earlier importer used raw FL26 membership order as the native starting
order while retaining the physical slot's formation. Membership order is not
FL26's actual selected XI: several keepers and defenders appeared first. The
runtime deliberately sets Coach appointment order to the generated roster
indices, so this data error became a real on-field role error, not just a label.
The first web-transfer candidate corrected two Bundesliga teams from valid
web tactics, but the other sixteen retained incompatible local starters. Its
outgoing-transfer refill pinned surviving starters and therefore preserved
most incompatible outfield assignments.

`native_lineup.py` now selects the entire local XI without pinning that raw
order. Primary positions and native full/partial familiarity are allowed;
keeper/outfield crossings and unfamiliar neighboring roles are forbidden.
All eleven slots must be filled or staging fails. Selection is deterministic,
the remaining bench keeps source order, and identities, memberships, shirts,
stats, portraits and assets do not change. In a mixed roster with incomplete
OVR coverage, source order breaks equal-fit ties rather than fabricated ratings.

The original FL26 staging path now uses this selector and validates every
encoded slot in both native tactics and all three phases. The paired verifier
performs the same role checks; asset/ID coverage alone is no longer sufficient.
For an existing web-transfer plan, explicitly opt into the authorized category:

```powershell
python tools/stage_efootballdb_update.py <existing-input-arguments> --repair-lineup-category german_teams --output local-debug/new-bundesliga-candidate
```

The repair leaves exact valid web XIs in place and rebalances only retained
local teams within the category. Teams outside that category retain the
existing update policy. `stage-report.json` records the scope and all per-phase
role checks. The candidate's SQLite starting orders and generated NRO roster
must agree with its native CPK. This is a default-lineup correction, not an
import of current real-world Bundesliga tactical shapes and not a migration
of old tournament saves or user presets. Validate new Exhibition/Cup/League
sessions and pre-game substitutions on Switch before release.

## Selector/kit preservation correction (2026-10-05)

The user confirmed the default-XI candidate boots, then reported generic
league branding and Palmeiras kits. An independent comparison found that
the selector had lost 18 active FL26 category logos/16 licensed names, while
the original Bundesliga pairing had reset the kit byte of 110 currently
playable teams. Palmeiras differed from its licensed native team row at only
byte 84 (15 became 0); its descriptors, six textures and two previews remained
identical. The same strict identity/asset checks passed for all 110 teams.

The scoped restoration tool and regression tests are documented in
[Full mobile kit migration](FULL_MOBILE_KIT_MIGRATION.md). The pairing tool now
uses the current kit package as the owner of unrelated native team rows, and
the selector stage reapplies the shared FL26 branding policy. Existing
transfers, repaired lineups, team pools, and the replacement Palmeiras crest
remain untouched. Rebuild and deliver a matched NRO/dt200/manifest set; do not
revert the database or restore an old full atlas as a shortcut.

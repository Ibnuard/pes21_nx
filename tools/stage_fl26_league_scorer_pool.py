#!/usr/bin/env python3
"""Stage a League scorer pool for the paired FL26 club/national rosters.

eFootball BaseIds remain unchanged. FL26-only identities use the disjoint
high-bit ``0x80000000 | PCPlayerId`` tournament scorer namespace; this is not
an eFootball BaseId or a native PES21 player-storage ID.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_fl26_cup_catalog import decoded_member, index_cpk
from generate_league_scorer_pool import ascii_name
from pesdb import parse_pes21_assignments, parse_player_records


ROOT = Path(__file__).resolve().parents[1]


def render(catalog: dict, assignments: dict, player_positions: dict[int, int],
           registry: dict, slot_plan: dict, *, expected_teams: int = 459) -> tuple[str, dict]:
    owners: dict[int, tuple[int, int, str]] = {}
    for row in registry["players"]:
        if row.get("status") != "active":
            continue
        native = int(row["native_player_id"])
        identity = (int(row["ef_base_id"]), int(row.get("portrait_asset_id") or native),
                    ascii_name(row["canonical_name"]) or "PLAYER")
        if native in owners and owners[native] != identity:
            raise ValueError(f"duplicate eFootball native player owner {native}")
        owners[native] = identity
    custom_ids = set()
    for row in slot_plan["player_slots"]:
        native = int(row["native_player_id"])
        pc_id = int(row["fl26_player_id"])
        if native in owners or pc_id >= 0x80000000:
            raise ValueError(f"FL26 scorer identity collides: {pc_id}/{native}")
        custom_ids.add(native)
        owners[native] = (0x80000000 | pc_id, native,
                          ascii_name(row["name"]) or "PLAYER")

    rows = sorted(catalog["teams"], key=lambda row: int(row["team_id"]))
    if expected_teams < 1 or len(rows) != expected_teams or len({int(row["team_id"]) for row in rows}) != expected_teams:
        raise ValueError(f"paired selector must contain {expected_teams} unique teams")
    lines = [
        "// Local paired FL26 League scorer pool; generated from native rosters.",
        "// eFootball BaseId or 0x80000000 | FL26 PC ID; never a donor ID.",
        "typedef struct { uint32_t team, first, count; } LeagueScorerPoolTeam;",
        "typedef struct { uint32_t base_id, portrait_id; const char *name; } LeagueScorerPoolPlayer;",
        "static const LeagueScorerPoolTeam league_scorer_pool_teams[] = {",
    ]
    pool = []
    active_owners: dict[int, tuple[int, int, str]] = {}
    custom_pool_teams = 0
    for team in rows:
        logical = int(team["team_id"])
        physical = int(team["physical_team_id"])
        roster = assignments.get(physical, [])
        if not 18 <= len(roster) <= 40:
            raise ValueError(f"League scorer source team {logical} is incomplete")
        native_ids = [int(row.player_id) for row in roster]
        if not set(native_ids) <= owners.keys():
            missing = sorted(set(native_ids) - owners.keys())
            raise ValueError(f"League scorer identity missing for {logical}: {missing[:5]}")
        # Use real forwards/attacking midfielders first. A simulated scorer's
        # first entry is deliberately favoured by the existing game logic.
        eligible = [value for value in native_ids if player_positions[value] != 0]
        eligible.sort(key=lambda value: (
            -int(player_positions[value] in (12, 11, 9, 10, 8, 7)),
            -player_positions[value], native_ids.index(value),
        ))
        chosen = eligible[:16]
        if len(chosen) < 8:
            raise ValueError(f"League scorer pool too small for {logical}")
        custom_pool_teams += any(value in custom_ids for value in chosen)
        lines.append(f"  {{{logical}u, {len(pool)}u, {len(chosen)}u}},")
        for native in chosen:
            scorer_id, portrait, name = owners[native]
            if not name:
                raise ValueError(f"custom scorer name missing for {native}")
            pool.append((scorer_id, portrait, name))
        for native in native_ids:
            active_owners[native] = owners[native]
    lines.extend(["};",
                  "static const LeagueScorerPoolPlayer league_scorer_pool_players[] = {"])
    for scorer_id, portrait, name in pool:
        escaped = name.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f"  {{{scorer_id}u, {portrait}u, \"{escaped}\"}},")
    lines.extend(["};",
                  "typedef struct { uint32_t portrait_id, base_id; } LeagueScorerIdentity;",
                  "static const LeagueScorerIdentity league_scorer_identities[] = {"])
    by_portrait = {}
    for scorer_id, portrait, _ in active_owners.values():
        if portrait and portrait in by_portrait and by_portrait[portrait] != scorer_id:
            raise ValueError(f"duplicate portrait identity {portrait}")
        if portrait:
            by_portrait[portrait] = scorer_id
    for portrait, scorer_id in sorted(by_portrait.items()):
        lines.append(f"  {{{portrait}u, {scorer_id}u}},")
    lines.extend(["};", ""])
    return "\n".join(lines), {
        "teams": len(rows), "pool_players": len(pool),
        "custom_identities": len(custom_ids),
        "teams_with_custom_scorers": custom_pool_teams,
        "portrait_identities": len(by_portrait),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-indonesia-paired-v2")
    parser.add_argument("--selector", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-indonesia-selector-v2")
    parser.add_argument("--registry", type=Path,
                        default=ROOT / "local-debug/indonesia-player-migration-work/player-registry-candidate.json")
    parser.add_argument("--slots", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-native-slot-plan.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-indonesia-selector-v2/league_scorer_pool_generated.inc")
    args = parser.parse_args()
    output = args.output.resolve()
    if (ROOT / "local-debug").resolve() not in output.parents:
        raise ValueError("generated scorer pool must stay in local-debug")
    catalog = json.loads((args.selector / "exhibition_team_catalog_migration.json")
                         .read_text(encoding="utf-8"))
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    slots = json.loads(args.slots.read_text(encoding="utf-8"))
    archive = args.candidate / "LooseCpk/dt200_mobile_all.cpk"
    index, base = index_cpk(archive)
    def member(name: str) -> bytes:
        return decoded_member(archive, index, base,
                              f"common/etc/pesdb/{name}")
    player_records = parse_player_records(member("Player.bin"), "pes21")
    player_positions = {value: int(row.position)
                        for value, row in player_records.items()}
    # Names live in the 312-byte native rows, so no FL26 asset is copied into
    # public source. Attach them to this local allocation plan only.
    for row in slots["player_slots"]:
        native = int(row["native_player_id"])
        row["name"] = player_records[native].name
    text, report = render(
        catalog, parse_pes21_assignments(member("PlayerAssignment.bin")),
        player_positions, registry, slots,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    (output.parent / "league-scorer-pool-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **report}, sort_keys=True))


if __name__ == "__main__":
    main()

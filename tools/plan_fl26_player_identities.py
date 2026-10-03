#!/usr/bin/env python3
"""Plan FL26 Bundesliga player identities without modifying game binaries.

Existing eFootball BaseIds remain canonical.  FL26-only players receive a
separate ``fl26:<PC ID>`` source key, never a fabricated eFootball BaseId.
Potential matches are held for review rather than duplicated by name or ID.
Only derived IDs, fingerprints, and source hashes are written to local-debug.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import unicodedata
from collections import defaultdict
from pathlib import Path

from build_fl26_cup_catalog import competition_members, decoded_member, index_cpk
from convert_efootball10_players import read_bits
from pesdb import parse_pes21_assignments, parse_player_records, split_records


ROOT = Path(__file__).resolve().parents[1]
PLAYER_SIZE = 312

# Audited against the locked eF26 and local FL26 names, ages and positions.
# A same-number/different-name card is a *collision*, never a face donor.
# These are explicit decisions, not a relaxed fuzzy-match rule.
CURATED_REUSE = {
    55165: 174180, 90093: 176826, 91392: 174196, 91589: 174051,
    114379: 114379, 120411: 120411, 126345: 126345, 128309: 128309,
    129369: 129369, 138082: 138082, 141840: 141840, 142121: 142121,
    142845: 142845, 142980: 142980, 143418: 143418, 152322: 152322,
    165664: 165664, 174352: 174352, 179125: 179125,
}
CURATED_NUMERIC_COLLISIONS = {
    116646: 116646, 118614: 118614, 127629: 127629,
    140870: 140870, 144090: 144090, 144886: 144886,
    146411: 146411, 157836: 157836, 159603: 159603,
    170390: 170390, 172345: 172345, 176104: 176104,
}
CURATED_PC_NAMES = {
    55165: "bencedardai", 90093: "charlesherrmann",
    91392: "erikahlstrand", 91589: "assanouedraogo",
    114379: "arnaudnordin", 116646: "ranikhedira",
    118614: "denisvavro", 120411: "askovolsen",
    126345: "vladimircoufal", 127629: "buduzivzivadze",
    128309: "dimitriosgiannoulis", 129369: "michaelolise",
    138082: "nathantella", 140870: "nicolasjackson",
    141840: "elyewahi", 142121: "phillippmwene",
    142845: "oladapoafolayan", 142980: "kevinparedes",
    143418: "carneychukwuemeka", 144090: "ismaelgharbi",
    144886: "isakjohannesson", 146411: "mohamedamoura",
    152322: "arthuraugusto", 157836: "victorboniface",
    159603: "giorgigocholeishvili", 165664: "danielperetz",
    170390: "kostanedeljkovic", 172345: "cyriaqueirie",
    174352: "christiankofane", 176104: "yandiomande",
    179125: "jeremiahmensah",
}


def normalized_name(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", folded.lower())


def pc_fingerprint(player_id: int, name: str, country: int,
                   height: int, foot: int) -> str:
    payload = f"{player_id}|{normalized_name(name)}|{country}|{height}|{foot}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def classify_player(pc: dict, by_base: dict[int, dict],
                    by_name: dict[str, list[dict]]) -> dict:
    """Use strict identity checks; ambiguous names or reused IDs need review."""
    player_id = int(pc["player_id"])
    name_key = normalized_name(str(pc["name"]))
    candidates = []
    direct = by_base.get(player_id)
    if direct is not None:
        candidates.append(direct)
    for candidate in by_name.get(name_key, []):
        if all(int(row["base_id"]) != int(candidate["base_id"])
               for row in candidates):
            candidates.append(candidate)

    qualified = []
    for candidate in candidates:
        if normalized_name(str(candidate["name"])) != name_key:
            continue
        if abs(int(candidate["height"]) - int(pc["height"])) > 3:
            continue
        if int(candidate["foot"]) != int(pc["foot"]):
            continue
        if int(candidate["country"]) * 2 not in (
            int(pc["country"]), int(pc["country"]) - 1,
        ):
            continue
        qualified.append(candidate)

    if len(qualified) == 1:
        chosen = qualified[0]
        return {
            "status": "reuse_ef_base_id",
            "base_id": int(chosen["base_id"]),
            "native_player_id": int(chosen["native_player_id"]),
            "existing_team_ids": chosen["team_ids"],
            "reason": "direct_fingerprint" if int(chosen["base_id"]) == player_id
                      else "unique_name_fingerprint",
        }
    if candidates:
        return {
            "status": "review_identity",
            "candidate_base_ids": sorted({int(row["base_id"]) for row in candidates}),
            "reason": "ambiguous_or_fingerprint_mismatch",
        }
    return {
        "status": "new_fl26_identity",
        "source_key": f"fl26:{player_id}",
        "fingerprint": pc_fingerprint(
            player_id, str(pc["name"]), int(pc["country"]),
            int(pc["height"]), int(pc["foot"]),
        ),
    }


def curate_review(pc: dict, decision: dict, by_base: dict[int, dict]) -> dict:
    if decision["status"] != "review_identity":
        return decision
    player_id = int(pc["player_id"])
    reuse = CURATED_REUSE.get(player_id)
    collision = CURATED_NUMERIC_COLLISIONS.get(player_id)
    if (reuse is None) == (collision is None):
        return decision
    candidate_id = reuse if reuse is not None else collision
    if normalized_name(str(pc["name"])) != CURATED_PC_NAMES[player_id]:
        raise ValueError(f"curated FL26 player name changed: {player_id}")
    if decision["candidate_base_ids"] != [candidate_id]:
        raise ValueError(f"curated FL26 identity candidates changed: {player_id}")
    candidate = by_base[candidate_id]
    if abs(int(pc["age"]) - int(candidate["age"])) > 2:
        raise ValueError(f"curated FL26 identity age changed: {player_id}")
    if reuse is not None:
        if abs(int(pc["position"]) - int(candidate["position"])) > 2:
            raise ValueError(f"curated FL26 identity position changed: {player_id}")
        return {
            "status": "reuse_ef_base_id",
            "base_id": candidate_id,
            "native_player_id": int(candidate["native_player_id"]),
            "existing_team_ids": candidate["team_ids"],
            "reason": "curated_name_age_position_match",
        }
    if normalized_name(str(pc["name"])) == normalized_name(str(candidate["name"])):
        raise ValueError(f"curated FL26 numeric collision name changed: {player_id}")
    return {
        "status": "new_fl26_identity",
        "source_key": f"fl26:{player_id}",
        "fingerprint": pc_fingerprint(
            player_id, str(pc["name"]), int(pc["country"]),
            int(pc["height"]), int(pc["foot"]),
        ),
        "reason": "curated_numeric_collision_no_donor_asset",
    }


def read_fl26(fl26_root: Path) -> tuple[list[int], dict[int, list], dict[int, dict], set[int]]:
    season = fl26_root / "download/data_s2526c.cpk"
    archive, base = index_cpk(season)
    def member(name: str) -> bytes:
        return decoded_member(season, archive, base, f"common/etc/pesdb/{name}")
    bundesliga = competition_members(member("CompetitionEntry.bin"))[39]
    if len(bundesliga) != 18 or len(set(bundesliga)) != 18:
        raise ValueError("FL26 Bundesliga membership is not 18 distinct teams")
    assignments = parse_pes21_assignments(member("PlayerAssignment.bin"))
    player_rows = split_records(member("Player.bin"), PLAYER_SIZE, "FL26 Player.bin")
    parsed = parse_player_records(b"".join(player_rows), "pes21")
    players = {}
    for row in player_rows:
        player_id = struct.unpack_from("<I", row, 8)[0]
        player = parsed[player_id]
        players[player_id] = {
            "player_id": player_id,
            "name": player.name,
            "country": player.nationality_code,
            "position": player.position,
            "height": read_bits(row, 216, 8) + 100,
            "foot": read_bits(row, 514, 1),
            "age": read_bits(row, 408, 6) + 15,
        }
    portraits = set()
    for archive_path in (
        fl26_root / "Data/dt14_all.cpk",
        *(fl26_root / f"download/data_s2526{suffix}.cpk"
          for suffix in ("a", "b", "c")),
    ):
        index, _ = index_cpk(archive_path)
        portraits.update(
            int(Path(member_name).stem)
            for member_name in index
            if member_name.startswith("common/render/symbol/player/")
            and member_name.endswith(".dds")
        )
    return bundesliga, assignments, players, portraits


def plan(fl26_root: Path, registry: dict, ef_source: dict,
         catalog: dict) -> dict:
    bundesliga, assignments, pc_players, portraits = read_fl26(fl26_root)
    source_cards = {int(row["Id"]): row for row in ef_source["players"]}
    by_base: dict[int, dict] = {}
    by_name: dict[str, list[dict]] = defaultdict(list)
    for row in registry["players"]:
        if row.get("status") != "active":
            continue
        card = source_cards.get(int(row["source_card_id"]))
        if card is None:
            raise ValueError(f"missing eFootball card for BaseId {row['ef_base_id']}")
        identity = {
            "base_id": int(row["ef_base_id"]),
            "name": row["canonical_name"],
            "country": int(card["Country"]),
            "height": int(card["Height"]),
            "foot": int(bool(card["Foot"])),
            "age": int(card["Age"]),
            "position": int(card["Position"]),
            "native_player_id": int(row["native_player_id"]),
            "team_ids": [int(value) for value in row.get("team_ids", [])],
        }
        by_base[identity["base_id"]] = identity
        by_name[normalized_name(identity["name"])].append(identity)

    roster_ids = {int(assignment.player_id) for team_id in bundesliga
                  for assignment in assignments[team_id]}
    national_ids = {int(row["team_id"]) for row in catalog["teams"]
                    if row["kind"] == "national"}
    players = []
    for player_id in sorted(roster_ids):
        if player_id not in pc_players:
            raise ValueError(f"FL26 assignment references missing player {player_id}")
        pc = pc_players[player_id]
        decision = curate_review(pc, classify_player(pc, by_base, by_name), by_base)
        if decision["status"] == "reuse_ef_base_id":
            decision["also_in_active_national_team"] = any(
                team_id in national_ids
                for team_id in decision["existing_team_ids"]
            )
        players.append({
            "fl26_player_id": player_id,
            "name": pc["name"],
            "country_code": pc["country"],
            "position": pc["position"],
            "portrait_available": player_id in portraits,
            "bundesliga_team_ids": [team_id for team_id in bundesliga
                                    if any(int(row.player_id) == player_id
                                           for row in assignments[team_id])],
            **decision,
        })
    counts = {status: sum(row["status"] == status for row in players)
              for status in ("reuse_ef_base_id", "review_identity", "new_fl26_identity")}
    counts["reused_with_national_team"] = sum(
        row.get("also_in_active_national_team", False) for row in players
    )
    return {
        "schema_version": 1,
        "source": "local FL26 PC Player.bin + locked eFootball registry",
        "bundesliga_team_ids": bundesliga,
        "counts": {**counts, "players": len(players),
                   "portraits_available": sum(row["portrait_available"] for row in players)},
        "players": players,
        "release_ready": False,
        "reason": "review identities, allocate native rows, patch linked tables and assets",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fl26-root", type=Path,
                        default=Path("D:/Games/SP Football Life 2026"))
    parser.add_argument("--registry", type=Path,
                        default=ROOT / "data/pes21_player_registry.json")
    parser.add_argument("--ef-source", type=Path,
                        default=ROOT / "local-inputs/pes21-player-migration/eF26_v551/source-db.json")
    parser.add_argument("--catalog", type=Path,
                        default=ROOT / "data/exhibition_team_catalog_migration.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-identity-plan.json")
    args = parser.parse_args()
    output = args.output.resolve()
    if (ROOT / "local-debug").resolve() not in output.parents:
        raise ValueError("identity plan output must stay in local-debug")
    result = plan(
        args.fl26_root,
        json.loads(args.registry.read_text(encoding="utf-8")),
        json.loads(args.ef_source.read_text(encoding="utf-8")),
        json.loads(args.catalog.read_text(encoding="utf-8")),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(json.dumps({"output": str(output), **result["counts"]}, sort_keys=True))


if __name__ == "__main__":
    main()

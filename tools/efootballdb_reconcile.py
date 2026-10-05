"""Offline identity and membership reconciliation for eFootballDB snapshots."""

from __future__ import annotations

import collections
import copy
import hashlib
import json
import re
import sqlite3
import struct
from pathlib import Path

from build_fl26_cup_catalog import decoded_member, index_cpk
from convert_efootball10_players import read_bits
from pes21_player_migration import identity_fingerprint, name_tokens, normalize_name
from pesdb import parse_pes21_assignments, parse_player_records, split_records
from plan_fl26_player_identities import pc_fingerprint


def native_baseline(path: Path) -> tuple[dict, dict]:
    index, offset = index_cpk(path)
    raw = decoded_member(path, index, offset, "common/etc/pesdb/Player.bin")
    parsed = parse_player_records(raw, "pes21")
    rows = {}
    for row in split_records(raw, 312, "Player.bin"):
        native_id = struct.unpack_from("<I", row, 8)[0]
        rows[native_id] = {
            "native_player_id": native_id, "name": parsed[native_id].name,
            "country": read_bits(row, 233, 9), "height": read_bits(row, 216, 8) + 100,
            "native_country_code": parsed[native_id].nationality_code,
            "foot": read_bits(row, 514, 1), "age": read_bits(row, 408, 6) + 15,
            "position": parsed[native_id].position,
            "native_sha256": hashlib.sha256(row).hexdigest(),
        }
    if len(rows) != 43074:
        raise ValueError("baseline must retain the fixed 43,074 native player rows")
    assignments = parse_pes21_assignments(decoded_member(
        path, index, offset, "common/etc/pesdb/PlayerAssignment.bin"))
    return rows, assignments


def source_identity(card: dict) -> dict:
    return {
        "base_id": int(card["BaseId"]), "name": card["Name"],
        "country": int(card["Country"]), "height": int(card["Height"]),
        "foot": int(bool(card["Foot"])), "age": int(card["Age"]),
        "position": int(card["Position"]),
    }


def fingerprint_fields_match(local: dict, web: dict, names: set[str] | None = None) -> bool:
    """BaseId is resolved separately; names alone never establish identity.

    Height may change slightly between data updates; record that difference in
    the report, while retaining the existing asset identity fingerprint.
    """
    allowed = names or {normalize_name(local["name"])}
    # Japanese/Korean listings may reverse the complete given/family names.
    # Only a complete token permutation is accepted, never a fuzzy surname.
    tokens = name_tokens(local["name"])
    reordered = len(tokens) >= 2 and sorted(tokens) == sorted(name_tokens(web["name"]))
    return (
        bool(normalize_name(web["name"]))
        and (normalize_name(web["name"]) in allowed or reordered)
        and local["country"] == web["country"]
        and local["foot"] == web["foot"]
        and abs(local["height"] - web["height"]) <= 3
    )


def canonical_biography_drift(local: dict, profile: dict | None) -> dict | None:
    """Additional evidence for an existing BaseId, not fuzzy name matching.

    A canonical profile may correct ONE biography field. The complete name,
    BaseId, plausible age progression, keeper/outfield type and the other TWO
    biography fields must still agree. Preserve the locked local record and
    asset fingerprint; record the source discrepancy rather than updating it.
    Never use this rule to match a different BaseId or a new FL26 identity.
    """
    if profile is None or local.get("base_id") != profile["base_id"]:
        return None
    tokens = name_tokens(local["name"])
    if (len(tokens) < 2 or any(len(token) < 2 for token in tokens)
            or sorted(tokens) != sorted(name_tokens(profile["name"]))):
        return None
    if (local.get("age") is None or not 0 <= profile["age"] - local["age"] <= 3
            or (local["position"] == 0) != (profile["position"] == 0)
            or abs(local["height"] - profile["height"]) > 10):
        return None
    changed = [field for field in ("country", "height", "foot")
               if (abs(local[field] - profile[field]) > 3 if field == "height"
                   else local[field] != profile[field])]
    if len(changed) != 1:
        return None
    return {"field": changed[0], "local": local[changed[0]],
            "canonical_profile": profile[changed[0]], "age_delta": profile["age"] - local["age"]}


def load_local_identities(registry: dict, source: dict, native: dict,
                          master_db: Path, fl26_slots: dict) -> tuple[dict, dict, dict]:
    cards = {int(row["Id"]): row for row in source["players"]}
    variants = collections.defaultdict(list)
    for row in source["players"]:
        variants[int(row["BaseId"])].append(row)
    db = sqlite3.connect(master_db.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("local master database integrity check failed")
        master = {base: (native_id, fingerprint) for base, native_id, fingerprint
                  in db.execute("SELECT base_id,native_player_id,fingerprint FROM players")}
    finally:
        db.close()
    known_bases = {base: source_identity(min(rows, key=lambda row: (
        int(row["Id"]) != base, int(row.get("CardType", 0)) != 0, int(row["Id"]))))
        for base, rows in variants.items()}
    if registry.get("generator") == "tools/stage_efootballdb_update.py":
        identities, owners = load_identity_state(registry, native, master)
        return identities, owners, known_bases
    identities = {}
    owners = {}
    for row in registry["players"]:
        base_id, native_id = int(row["ef_base_id"]), int(row["native_player_id"])
        card = cards[int(row["source_card_id"])]
        if int(card["BaseId"]) != base_id or identity_fingerprint(card) != row["fingerprint"]:
            raise ValueError(f"locked registry/source fingerprint mismatch: {base_id}")
        if base_id in master and master[base_id] != (native_id, row["fingerprint"]):
            raise ValueError(f"master DB and identity registry disagree: {base_id}")
        key = f"ef:{base_id}"
        if key in identities or native_id in owners:
            raise ValueError("duplicate canonical/native identity in local registry")
        local = source_identity(card)
        if native_id not in native and row["status"] == "active":
            raise ValueError(f"registered native player missing: {key}/{native_id}")
        # Tombstones remain reserved and must not be mistaken for a free slot.
        native_verified = native_id in native and fingerprint_fields_match(local, native[native_id])
        if row["status"] == "active" and not native_verified:
            raise ValueError(f"native Player.bin differs from registered identity: {key}")
        aliases = {normalize_name(local["name"])}
        aliases.update(normalize_name(item["Name"]) for item in variants[base_id]
                       if int(item["Country"]) == local["country"]
                       and int(bool(item["Foot"])) == local["foot"]
                       and abs(int(item["Height"]) - local["height"]) <= 3)
        identities[key] = {
            **local, "key": key, "native_player_id": native_id,
            "fingerprint": row["fingerprint"], "status": row["status"],
            "native_present": native_id in native,
            "native_identity_verified": native_verified,
            "aliases": sorted(aliases), "registry": row,
        }
        owners[native_id] = key
    for row in fl26_slots.get("player_slots", []):
        native_id = int(row["native_player_id"])
        key = row["source_key"]
        if not re.fullmatch(r"fl26:\d+", key) or native_id in owners or key in identities:
            raise ValueError("invalid or colliding FL26 identity allocation")
        if native_id not in native:
            raise ValueError(f"missing FL26 native player: {key}")
        local = native[native_id]
        if pc_fingerprint(int(key.split(":")[1]), local["name"],
                          local["native_country_code"], local["height"],
                          local["foot"]) != row["fingerprint"]:
            raise ValueError(f"FL26 native/registry fingerprint mismatch: {key}")
        identities[key] = {
            **local, "key": key, "base_id": None, "fingerprint": row["fingerprint"],
            "status": "active", "aliases": [normalize_name(local["name"])],
            "registry": row,
        }
        owners[native_id] = key
    return identities, owners, known_bases


def load_identity_state(state: dict, native: dict, legacy_master: dict | None = None) -> tuple[dict, dict]:
    """Resume future syncs from the staged canonical mapping, never reallocate."""
    if state.get("schema_version") != 1:
        raise ValueError("unsupported canonical identity-state version")
    identities, owners, aliases = copy.deepcopy(state["identities"]), {}, set()
    for key, person in identities.items():
        base = person["base_id"]
        if key != person["key"] or (base is not None and key != f"ef:{base}"):
            raise ValueError("canonical identity key/BaseId mismatch")
        if base is None and not re.fullmatch(r"fl26:\d+", key):
            raise ValueError("unknown custom identity namespace")
        native_id = person["native_player_id"]
        if native_id in owners:
            raise ValueError("duplicate native owner in canonical state")
        owners[native_id] = key
        current = native.get(native_id)
        if current is None:
            if person["status"] == "active" or person["native_sha256"] is not None:
                raise ValueError(f"canonical native identity missing: {key}")
        elif current["native_sha256"] != person["native_sha256"]:
            raise ValueError(f"canonical native record changed: {key}")
        if base in (legacy_master or {}) and legacy_master[base][0] != native_id:
            raise ValueError(f"legacy BaseId changed native owner: {key}")
        for alias in person.get("previous_keys", []):
            if alias in aliases or alias in identities:
                raise ValueError("canonical alias collides with another person")
            aliases.add(alias)
        person["native_present"] = current is not None
        if person["status"] != "active":
            person["native_identity_verified"] = current is not None and fingerprint_fields_match(person, current)
    return identities, owners


def resolve_identity(base_id: int, observations: list[dict], identities: dict,
                     by_name: dict, known_bases: dict | None = None,
                     profile: dict | None = None) -> dict:
    # Unlicensed national/card variants can have fictional labels. A separately
    # locked canonical BaseId profile is the identity authority when available.
    # It still has to pass the existing fingerprint checks; ID alone is not proof.
    evidence = [profile] if profile is not None else observations
    key = f"ef:{base_id}"
    direct = identities.get(key)
    if direct is not None:
        if not direct.get("native_present", True):
            return {"base_id": base_id, "status": "review_identity",
                    "reason": "tombstone_native_record_absent", "key": key,
                    "web": observations}
        if direct["status"] != "active" and not direct.get("native_identity_verified", False):
            # A retired key may still point to a legacy, abbreviated or replaced
            # native row. Require the native fingerprint too before reactivation.
            return {"base_id": base_id, "status": "review_identity",
                    "reason": "tombstone_requires_identity_review", "key": key,
                    "web": observations}
        matching = [row for row in evidence if fingerprint_fields_match(
            direct, row, set(direct["aliases"]))]
        drift = canonical_biography_drift(direct, profile) if not matching else None
        if not matching and drift is None:
            return {"base_id": base_id, "status": "review_identity",
                    "reason": "base_id_fingerprint_mismatch", "local": {
                        field: direct[field] for field in
                        ("key", "name", "country", "height", "foot", "native_player_id")},
                    "web": observations, "canonical_profile": profile}
        return {"base_id": base_id, "key": key, "status": "reuse_local",
                "name": direct["name"], "native_player_id": direct["native_player_id"],
                "fingerprint": direct["fingerprint"],
                "verification": "canonical_base_full_name_age_two_biography_fields" if drift else
                                "base_id_name_country_foot_height",
                "biography_drift": drift,
                "asset_policy": "preserve_verified_local", "stats_policy": "preserve_local"}
    possible = {}
    for row in evidence:
        for candidate in by_name.get(normalize_name(row["name"]), []):
            possible[candidate["key"]] = candidate
    qualified = [candidate for candidate in possible.values()
                 if any(fingerprint_fields_match(candidate, row) for row in evidence)]
    if len(qualified) == 1 and qualified[0]["key"].startswith("fl26:"):
        candidate = qualified[0]
        return {"base_id": base_id, "key": key, "status": "promote_fl26_identity",
                "previous_key": candidate["key"], "name": candidate["name"],
                "native_player_id": candidate["native_player_id"],
                "fingerprint": candidate["fingerprint"],
                "verification": "unique_fl26_name_country_foot_height",
                "asset_policy": "preserve_verified_local", "stats_policy": "preserve_local"}
    known = (known_bases or {}).get(base_id)
    known_matches = known is not None and any(
        fingerprint_fields_match(known, row) for row in evidence)
    known_matches = known_matches or canonical_biography_drift(known or {}, profile) is not None
    if known is not None and not known_matches:
        return {"base_id": base_id, "status": "review_identity",
                "reason": "unmaterialized_base_fingerprint_mismatch",
                "local": known, "web": observations, "canonical_profile": profile}
    if possible and (qualified or not known_matches):
        return {"base_id": base_id, "status": "review_identity",
                "reason": "possible_existing_person_do_not_duplicate",
                "candidates": sorted(possible), "web": observations}
    # A single BaseId must not merge unrelated club and national identities.
    canonical = evidence[0]
    if not all(fingerprint_fields_match(canonical, row) for row in evidence):
        return {"base_id": base_id, "status": "review_identity",
                "reason": "conflicting_web_identity_variants", "web": observations}
    if (canonical["country"] is None or not 0 < canonical["country"] < 512
            or canonical["foot"] not in (0, 1) or not 100 <= canonical["height"] <= 230):
        return {"base_id": base_id, "status": "review_identity",
                "reason": "invalid_new_player_biography", "web": observations}
    return {"base_id": base_id, "key": key, "status": "new_web_player",
            "name": canonical["name"], "native_player_id": None,
            "verification": "web_and_locked_unmaterialized_base" if known_matches
                            else "web_base_id_consistent_biography",
            "asset_policy": "neutral_portrait_no_face_no_commentary",
            "stats_policy": "web_base_card_proven_fields_only"}


def effective_teams(web: dict, profiles: dict) -> tuple[dict, list]:
    """Resolve duplicate club card assignments only with canonical evidence.

    Pruning a bench duplicate leaves the website's exact XI unchanged. A
    conflicting starter invalidates the entire roster rather than inventing XI.
    """
    teams = copy.deepcopy(web)
    clubs = collections.defaultdict(list)
    for team_id, team in teams.items():
        if team["kind"] == "club" and not team["problems"]:
            for row in team["members"]:
                clubs[row["base_id"]].append(team_id)
    corrections = []
    for base_id, team_ids in sorted(clubs.items()):
        canonical_club = profiles.get(base_id, {}).get("club_id")
        if len(team_ids) < 2 or canonical_club not in team_ids:
            continue
        for team_id in team_ids:
            if team_id == canonical_club:
                continue
            team = teams[team_id]
            member = next(row for row in team["members"] if row["base_id"] == base_id)
            if member["order"] < 11 or len(team["members"]) <= 18:
                team["problems"].append(f"canonical_club_conflict:{base_id}")
            else:
                team["members"] = [row for row in team["members"] if row is not member]
                for order, row in enumerate(team["members"]):
                    row["order"] = order
                corrections.append({"team_id": team_id, "base_id": base_id,
                                    "canonical_club": canonical_club,
                                    "reason": "stale_bench_card_assignment"})
    return teams, corrections


def reconcile(catalog: dict, web: dict, errors: dict, identities: dict,
              owners: dict, assignments: dict, keep_unavailable: bool,
              known_bases: dict | None = None, profiles: dict | None = None,
              keep_identity_teams: bool = False,
              allow_retained_outgoing: bool = False,
              import_errors: dict | None = None) -> dict:
    if allow_retained_outgoing and not keep_identity_teams:
        raise ValueError("outgoing fallback transfers require the safe-team policy")
    profiles = profiles or {}
    web, corrections = effective_teams(web, profiles)
    scope = {int(row["team_id"]): row for row in catalog["teams"]}
    attempted = set(web) | set(map(int, errors))
    if attempted != set(scope):
        raise ValueError("all playable teams must be attempted before reconciliation")
    old_rosters = {}
    for team_id, team in scope.items():
        rows = assignments.get(int(team["physical_team_id"]), [])
        if not 18 <= len(rows) <= 40:
            raise ValueError(f"current native roster is incomplete: {team_id}")
        old_rosters[team_id] = [{"key": owners[row.player_id],
                                "native_player_id": row.player_id,
                                "shirt_number": row.shirt, "order": row.order}
                               for row in rows]
    keep = {}
    source_teams = {}
    problems = []
    for team_id, team in scope.items():
        if team_id not in web:
            reason = errors[str(team_id)]
            # Timeout/auth/server failures are not evidence that a roster is absent.
            can_keep = "HTTP Error 404:" in reason
        else:
            reason = ", ".join(web[team_id]["problems"])
            can_keep = True
        if reason:
            keep[team_id] = {"team_id": team_id, "name": team["display_name"], "reason": reason}
            if not keep_unavailable or not can_keep:
                problems.append({"team_id": team_id, "reason": "source_unavailable", "detail": reason})
        else:
            source_teams[team_id] = web[team_id]
    observed = collections.defaultdict(list)
    observed_teams = collections.defaultdict(list)
    for team_id, team in sorted(source_teams.items()):
        for row in team["members"]:
            observed[row["base_id"]].append(row)
            observed_teams[row["base_id"]].append(team_id)
    by_name = collections.defaultdict(list)
    for local in identities.values():
        for alias in local["aliases"]:
            by_name[alias].append(local)
    decisions = {}
    for base_id, observations in sorted(observed.items()):
        decision = resolve_identity(base_id, observations, identities, by_name, known_bases,
                                    profiles.get(base_id))
        if decision["status"] == "new_web_player" and base_id in (import_errors or {}):
            decision.update(status="review_identity", reason="unsupported_new_player_fields",
                            detail=import_errors[base_id])
        decision["team_ids"] = observed_teams[base_id]
        clubs = [team_id for team_id in observed_teams[base_id] if scope[team_id]["kind"] == "club"]
        if len(clubs) > 1:
            decision.update(status="review_identity", reason="assigned_to_multiple_web_clubs",
                            club_ids=clubs)
        decisions[base_id] = decision
    # Two different eFootball BaseIds may not both claim one FL26 native player.
    claims = collections.defaultdict(list)
    for decision in decisions.values():
        if decision.get("native_player_id") is not None:
            claims[decision["native_player_id"]].append(decision)
    for group in claims.values():
        if len(group) > 1:
            for decision in group:
                decision.update(status="review_identity", reason="multiple_bases_claim_one_native_id")
    for team_id, team in list(source_teams.items()):
        primary = next((row for row in team["strategies"] if row["strategy"] == 0), None)
        valid = primary is not None and sum(row["role"] == 0 for row in primary["slots"]) == 1
        if valid:
            for slot, member in zip(primary["slots"], team["members"][:11]):
                decision = decisions[member["base_id"]]
                if decision["status"] == "review_identity":
                    continue
                key = decision.get("previous_key", decision["key"])
                position = identities[key]["position"] if key in identities else member["position"]
                if (slot["role"] == 0) != (position == 0):
                    valid = False
        if not valid:
            keep[team_id] = {"team_id": team_id, "name": scope[team_id]["display_name"],
                             "reason": "web_lineup_keeper_or_strategy_mismatch"}
            del source_teams[team_id]
            if not keep_unavailable:
                problems.append({"team_id": team_id, "reason": "invalid_native_lineup"})
    reviews = [row for row in decisions.values() if row["status"] == "review_identity"]
    promotions = {row["previous_key"]: row["key"] for row in decisions.values()
                  if row["status"] == "promote_fl26_identity"}
    old_clubs = collections.defaultdict(set)
    old_nations = collections.defaultdict(set)
    for team_id, roster in old_rosters.items():
        target = old_clubs if scope[team_id]["kind"] == "club" else old_nations
        for row in roster:
            target[promotions.get(row["key"], row["key"])].add(team_id)
    if keep_identity_teams:
        # Close over transfers from retained clubs. By default those clubs
        # remain exact; the separately approved outgoing mode may remove only
        # verified departures, provided enough players and a keeper remain.
        for row in reviews:
            for team_id in row["team_ids"]:
                keep.setdefault(team_id, {"team_id": team_id,
                    "name": scope[team_id]["display_name"], "reason": "identity_review"})
        while True:
            protected = collections.defaultdict(set)
            for team_id in keep:
                if scope[team_id]["kind"] == "club":
                    for row in old_rosters[team_id]:
                        protected[promotions.get(row["key"], row["key"])].add(team_id)
            added = {}
            destinations = collections.defaultdict(set)
            for team_id, team in source_teams.items():
                if team_id not in keep and team["kind"] == "club":
                    for row in team["members"]:
                        destinations[f"ef:{row['base_id']}"].add(team_id)
            blocked_retained = set(keep)
            if allow_retained_outgoing:
                blocked_retained = set()
                for retained in keep:
                    if scope[retained]["kind"] != "club":
                        continue
                    left = [row for row in old_rosters[retained]
                            if not destinations.get(promotions.get(row["key"], row["key"]))]
                    if len(left) < 18 or not any(identities[row["key"]]["position"] == 0 for row in left):
                        blocked_retained.add(retained)
            for team_id, team in source_teams.items():
                if team_id in keep or team["kind"] != "club":
                    continue
                conflicts = {f"ef:{row['base_id']}": sorted(protected[f"ef:{row['base_id']}"] & blocked_retained)
                             for row in team["members"]
                             if protected.get(f"ef:{row['base_id']}", set()) & blocked_retained}
                if conflicts:
                    added[team_id] = {"team_id": team_id, "name": scope[team_id]["display_name"],
                        "reason": "transfer_depends_on_retained_club", "blocked_players": conflicts}
            if not added:
                break
            keep.update(added)
        source_teams = {key: value for key, value in source_teams.items() if key not in keep}

    destinations = collections.defaultdict(set)
    for team_id, team in source_teams.items():
        if team["kind"] == "club":
            for row in team["members"]:
                destinations[f"ef:{row['base_id']}"].add(team_id)
    final_rosters = {}
    local_outgoing = []
    for team_id in scope:
        if team_id in source_teams:
            final_rosters[team_id] = [dict(row, key=f"ef:{row['base_id']}",
                native_player_id=decisions[row['base_id']].get('native_player_id'))
                for row in source_teams[team_id]["members"]]
        else:
            final_rosters[team_id] = [dict(row, key=promotions.get(row["key"], row["key"]))
                                      for row in old_rosters[team_id]]
            if allow_retained_outgoing and scope[team_id]["kind"] == "club":
                departing = [row["key"] for row in final_rosters[team_id]
                             if destinations.get(row["key"])]
                if departing:
                    final_rosters[team_id] = [row for row in final_rosters[team_id]
                                             if row["key"] not in departing]
                    if len(final_rosters[team_id]) < 18:
                        raise ValueError("retained outgoing policy left fewer than 18 players")
                    for order, row in enumerate(final_rosters[team_id]):
                        row["order"] = order
                    local_outgoing.append({"team_id": team_id, "departing_keys": departing,
                                           "remaining_players": len(final_rosters[team_id]),
                                           "lineup_policy": "preserve_native_shape_refill_from_survivors"})
    final_clubs = collections.defaultdict(set)
    for team_id, roster in final_rosters.items():
        if scope[team_id]["kind"] == "club":
            for row in roster:
                final_clubs[row["key"]].add(team_id)
    transfers = []
    decisions_by_key = {row.get("key", f"ef:{row['base_id']}"): row for row in decisions.values()}
    for key in sorted(set(old_clubs) | set(final_clubs)):
        clubs, previous = final_clubs.get(key, set()), old_clubs.get(key, set())
        decision = decisions_by_key.get(key, {})
        if decision.get("status") == "review_identity":
            continue
        if clubs != previous:
            local = identities.get(key, {})
            transfers.append({"key": key, "base_id": decision.get("base_id", local.get("base_id")),
                              "name": decision.get("name", local.get("name", key)),
                              "from_clubs": sorted(previous), "to_clubs": sorted(clubs),
                              "existing_national_teams": sorted(old_nations.get(key, set()))})
    if not keep_identity_teams:
        # A strict full plan must not quietly retain a transferred player too.
        for key, clubs in final_clubs.items():
            if len(clubs) > 1 and clubs != old_clubs.get(key, set()):
                problems.append({"key": key, "reason": "transfer_conflicts_with_retained_club",
                                 "team_ids": sorted(clubs)})
    else:
        for key, clubs in final_clubs.items():
            if len(clubs) > 1 and clubs != old_clubs.get(key, set()):
                raise ValueError(f"safe subset introduced duplicate club membership: {key}")
    applied_bases = {row["base_id"] for team in source_teams.values() for row in team["members"]}
    for row in decisions.values():
        row["apply"] = row["base_id"] in applied_bases
    for team_id in keep:
        keep[team_id]["remaining_players"] = len(final_rosters[team_id])
    blocked_reviews = [row for row in reviews if row["apply"]]
    return {
        "schema_version": 1, "status": "blocked_identity_review" if blocked_reviews or problems else "ready_to_stage",
        "policies": {"keep_unavailable_local_teams": keep_unavailable,
                     "keep_identity_review_teams": keep_identity_teams,
                     "allow_retained_outgoing": allow_retained_outgoing,
                     "retained_team_policy": "verified_outgoing_native_shape_preserved" if allow_retained_outgoing
                                             else "preserve_roster_and_tactics_exactly",
                     "existing_stats_assets": "preserve", "new_assets": "placeholder_no_donor",
                     "identity": "BaseId_plus_fingerprint", "active_runtime_modified": False},
        "counts": {"playable_teams": len(scope), "web_teams": len(source_teams),
                   "retained_local_teams": len(keep), "web_base_ids": len(decisions),
                   "reuse_local": sum(row["status"] == "reuse_local" for row in decisions.values()),
                   "promote_fl26": sum(row["status"] == "promote_fl26_identity" for row in decisions.values()),
                   "new_web_players": sum(row["status"] == "new_web_player" for row in decisions.values()),
                   "identity_reviews": len(reviews), "transfer_events": len(transfers),
                   "new_players_to_import": sum(row["apply"] and row["status"] == "new_web_player"
                                                for row in decisions.values()),
                   "applied_base_ids": len(applied_bases), "blocked_identity_reviews": len(blocked_reviews),
                   "local_teams_with_verified_outgoing": len(local_outgoing),
                   "problems": len(problems)},
        "updated_team_ids": sorted(source_teams),
        "final_rosters": {str(key): value for key, value in final_rosters.items()},
        "source_corrections": corrections,
        "local_outgoing": local_outgoing,
        "retained_teams": list(keep.values()), "problems": problems,
        "players": list(decisions.values()), "identity_reviews": reviews,
        "transfers": transfers,
    }

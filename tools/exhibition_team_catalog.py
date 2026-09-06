#!/usr/bin/env python3
"""Helpers shared by Exhibition generators that consume the team catalog."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_PATH = ROOT / "data" / "exhibition_team_catalog.json"


def load_catalog(path: Path = DEFAULT_CATALOG_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported team catalog schema")

    teams = payload.get("teams")
    categories = payload.get("categories")
    if not isinstance(teams, list) or not isinstance(categories, list):
        raise ValueError(f"{path}: malformed team catalog")

    team_ids = [int(team["team_id"]) for team in teams]
    if len(team_ids) != len(set(team_ids)):
        raise ValueError(f"{path}: duplicate team IDs")
    if team_ids != sorted(team_ids) or any(team_id <= 0 for team_id in team_ids):
        raise ValueError(f"{path}: team IDs must be positive and sorted")

    category_team_ids = [
        int(team_id)
        for category in categories
        for team_id in category.get("team_ids", [])
    ]
    if sorted(category_team_ids) != sorted(team_ids):
        raise ValueError(f"{path}: category membership does not match team list")

    category_keys = [str(category["key"]) for category in categories]
    if len(category_keys) != len(set(category_keys)):
        raise ValueError(f"{path}: duplicate category keys")

    team_by_id = {int(team["team_id"]): team for team in teams}
    for category_index, category in enumerate(categories):
        category_key = str(category["key"])
        for category_position, raw_team_id in enumerate(category["team_ids"]):
            team = team_by_id[int(raw_team_id)]
            if (
                str(team.get("category")) != category_key
                or int(team.get("category_index", -1)) != category_index
                or int(team.get("category_position", -1)) != category_position
            ):
                raise ValueError(
                    f"{path}: inconsistent category metadata for team {raw_team_id}"
                )

    badge_slots = [int(team["badge_slot"]) for team in teams]
    badge_slots.extend(int(category["badge_slot"]) for category in categories)
    expected_badge_slots = list(range(1, len(badge_slots) + 1))
    if sorted(badge_slots) != expected_badge_slots:
        raise ValueError(f"{path}: badge slots must be unique and contiguous")

    counts = payload.get("counts", {})
    expected_counts = {
        "selector_teams": len(teams),
        "categories": len(categories),
        "badge_slots": len(badge_slots) + 1,
    }
    for key, expected in expected_counts.items():
        if int(counts.get(key, -1)) != expected:
            raise ValueError(
                f"{path}: count {key} is {counts.get(key)!r}, expected {expected}"
            )

    canonical_payload = {
        key: value for key, value in payload.items() if key != "content_id"
    }
    canonical = json.dumps(
        canonical_payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    expected_content_id = hashlib.sha256(canonical).hexdigest()[:16]
    if payload.get("content_id") != expected_content_id:
        raise ValueError(f"{path}: catalog content ID does not match its payload")
    return payload


def catalog_team_map(catalog: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(team["team_id"]): team for team in catalog["teams"]}


def conversion_team_ids(catalog: dict[str, Any]) -> set[int]:
    return {
        int(team["team_id"])
        for team in catalog["teams"]
        if team.get("conversion_eligible", False)
    }


def parse_c_roster_arrays(
    paths: list[Path],
) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    """Read legacy roster arrays without treating ue4_hooks.c as catalog data."""
    players: dict[str, list[int]] = {}
    shirts: dict[str, list[int]] = {}
    pattern = re.compile(
        r"static\s+const\s+uint(32|8)_t\s+"
        r"exhibition_([a-z0-9_]+)_(players|shirts)\[\]\s*=\s*\{(.*?)\};",
        re.DOTALL,
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for _width, name, kind, body in pattern.findall(text):
            values = [int(value) for value in re.findall(r"\b(\d+)u?\b", body)]
            target = players if kind == "players" else shirts
            target[name] = values
    return players, shirts

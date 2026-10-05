"""Explicit public-API -> proven PES21 fields for newly allocated players only."""

from __future__ import annotations

import re

from pes21_player_migration import (
    EF_COM_STYLE_FIELDS, EF_PLAYER_SKILL_FIELDS, EF_POSITION_FIELDS,
    SOURCE_TO_PES21_STATS,
)


ABILITY_FIELDS = {
    "PlaceKicking": "place_kicking", "LowPass": "low_pass", "GKParrying": "clearing",
    "DefensiveAwareness": "defensive_prowess", "BallControl": "ball_control",
    "Header": "header", "Jump": "jump", "GKReach": "coverage", "Speed": "speed",
    "BallWinning": "ball_winning", "GKReflexes": "reflexes", "GKAwareness": "goalkeeping",
    "Curl": "swerve", "Stamina": "stamina", "Acceleration": "explosive_power",
    "Dribbling": "dribbling", "KickingPower": "kicking_power", "GKCatching": "catching",
    "OffensiveAwareness": "attacking_prowess", "Balance": "body_control",
    "Aggression": "aggression", "PhysicalContact": "physical_contact",
    "Finishing": "finishing", "LoftedPass": "lofted_pass", "TightPossession": "tight_possession",
    "DefensiveEngagement": "defensive_engagement",
}
SPECIAL_SKILL_FIELDS = {
    "SoleControl": "step_on_skill_control", "GKLowPunt": "low_punt_trajectory",
    "LongRangeShot": "long_range_shooting", "DippingShot": "dipping_shots",
    "RisingShot": "rising_shots", "ChopTurn": "cross_over_turn",
    "CutBehindAndTurn": "cut_behind_turn", "AcrobaticClearance": "acrobatic_clear",
    "LongRangeCurler": "long_range_drive", "EarlyCrosser": "early_cross",
    "GKDirectingDefence": "gk_directing_defense",
}


def snake_name(name: str) -> str:
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def number(player: dict, key: str, lower: int, upper: int) -> int:
    value = player[key]
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise ValueError(f"invalid API field {key}: {value!r}")
    return value


def web_player_to_source(player: dict) -> dict:
    """No OVR invention, donor face, movement preset, or hidden asset fields.

    The API has an additional +1 on Form/weak-foot/injury enums compared with
    the locked PESDBTools export, and exposes PlayingAttitude zero-based.
    Snapshot comparison must confirm this encoding before materialization.
    """
    assert set(SOURCE_TO_PES21_STATS.values()) <= ABILITY_FIELDS.keys()
    national = player["nationality_a"]
    country = national["country_id"] if isinstance(national, dict) else national
    if not isinstance(country, int) or not 1 <= country < 512:
        raise ValueError("new player has no valid PESDB country_id")
    result = {
        "Id": number(player, "pes_id", 1, (1 << 63) - 1),
        "BaseId": number(player, "base_pes_id", 1, (1 << 31) - 1),
        "Name": str(player["player_name"]), "Country": country, "Country2": 0,
        "Height": number(player, "height", 100, 230),
        "Weight": number(player, "weight", 30, 157),
        "Age": number(player, "age", 15, 78),
        "Foot": bool(number(player, "strong_foot", 0, 1)),
        "Hand": bool(number(player, "strong_hand", 0, 1)),
        "Position": number(player, "main_position", 0, 12),
        "PlayingStyle": number(player, "playing_style", 0, 22),
        "JapaneseName": str(player.get("japanese_name") or ""),
        "ClubShirt": str(player.get("shirt_name") or ""),
        "NationalShirt": str(player.get("national_shirt_name") or ""),
        "Form": number(player, "form", 2, 4) - 1,
        "WeakFootUsage": number(player, "weak_foot_usage", 2, 5) - 1,
        "WeakFootAccuracy": number(player, "weak_foot_accuracy", 2, 5) - 1,
        "InjuryResistance": number(player, "injury_resistance", 2, 4) - 1,
        "PlayingAttitude": number(player, "playing_attitude", 0, 2) + 1,
    }
    if not result["Name"].strip():
        raise ValueError("new player has an empty name")
    for field in EF_POSITION_FIELDS:
        result[field] = number(player, field.lower(), 0, 2)
    for field, key in ABILITY_FIELDS.items():
        result[field] = number(player, key, 40, 127)
    # Existing converter safely clamps PES21 abilities at 99. Unknown modern
    # eFootball-only skills stay in the audit payload, not guessed native bits.
    for field in (*EF_PLAYER_SKILL_FIELDS, *EF_COM_STYLE_FIELDS):
        key = SPECIAL_SKILL_FIELDS.get(field, snake_name(field))
        if key in player:
            result[field] = bool(number(player, key, 0, 1))
    result["CrossOverTurn"] = bool(number(player, "cross_over_turn", 0, 1))
    return result


def validate_api_enum_encoding(profiles: dict[int, dict], source: dict) -> dict:
    """Detect API schema drift using hundreds of frozen canonical-card anchors."""
    cards = {int(row["Id"]): row for row in source["players"]}
    fields = {"form": ("Form", 1), "weak_foot_usage": ("WeakFootUsage", 1),
              "weak_foot_accuracy": ("WeakFootAccuracy", 1),
              "injury_resistance": ("InjuryResistance", 1),
              "playing_attitude": ("PlayingAttitude", -1)}
    result = {}
    for key, (field, delta) in fields.items():
        comparisons = [int(row[key]) - int(cards[base][field])
                       for base, row in profiles.items() if base in cards and field in cards[base]]
        agreement = sum(value == delta for value in comparisons)
        if len(comparisons) < 20 or agreement / len(comparisons) < 0.9:
            raise ValueError(f"API enum encoding is unverified/changed: {key}")
        result[key] = {"samples": len(comparisons), "matching": agreement, "api_minus_source": delta}
    return result

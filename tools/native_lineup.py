"""Position-safe native starting orders; never changes a player's identity/stats."""

from __future__ import annotations

import struct

from convert_efootball10_players import read_bits
from generate_pesdb_runtime_rosters import _choose_balanced_xi_with_score
from pes21_player_migration import PES21_POSITION_BITS


def player_positions(record: bytes) -> tuple[int, tuple[int, ...]]:
    if len(record) != 312:
        raise ValueError("invalid native player record size")
    position = read_bits(record, 434, 4)
    if not 0 <= position < 13:
        raise ValueError("invalid native registered position")
    return position, tuple(read_bits(record, bit, 2) for bit in PES21_POSITION_BITS.values())


def position_fit(record: bytes, role: int) -> int:
    """2 = primary/full, 1 = partial, 0 = unfamiliar, -1 = GK crossing."""
    if not 0 <= role < 13:
        raise ValueError("invalid formation role")
    position, familiarity = player_positions(record)
    if (position == 0) != (role == 0):
        return -1
    if position == role or familiarity[role] >= 2:
        return 2
    return 1 if familiarity[role] == 1 else 0


def validate_starting_order(player_ids: list[int], roles: list[int], players: dict[int, bytes]) -> dict:
    if len(roles) != 11 or roles.count(0) != 1:
        raise ValueError("formation must have eleven slots and exactly one goalkeeper")
    if len(player_ids) != 11 or len(set(player_ids)) != 11:
        raise ValueError("starting XI must contain eleven distinct players")
    counts = {"full": 0, "partial": 0}
    for slot, (player_id, role) in enumerate(zip(player_ids, roles, strict=True)):
        if player_id not in players:
            raise ValueError(f"missing native player {player_id}")
        fit = position_fit(players[player_id], role)
        if fit < 0:
            raise ValueError(f"keeper/outfield crossing at slot {slot}: player {player_id}")
        if fit == 0:
            raise ValueError(f"unfamiliar role {role} at slot {slot}: player {player_id}")
        counts["full" if fit == 2 else "partial"] += 1
    return counts


def balanced_roster_order(player_ids: list[int], roles: list[int], players: dict[int, bytes],
                          ratings: dict[int, int] | None = None) -> list[int]:
    """Return source indices: strict role-fit XI followed by stable bench order.

    Raw assignment order is not a starting-XI hint. Do not pin it. In a mixed
    roster without ratings for every member, use stable source order as the
    tie-break instead of inventing OVRs or disadvantaging unscored FL26 players.
    """
    if not 18 <= len(player_ids) <= 40 or len(set(player_ids)) != len(player_ids):
        raise ValueError("native roster must contain 18..40 distinct players")
    if len(roles) != 11 or roles.count(0) != 1:
        raise ValueError("formation must have eleven slots and exactly one goalkeeper")
    ratings = ratings or {}
    use_ratings = all(player_id in ratings for player_id in player_ids)
    candidates = []
    for player_id in player_ids:
        if player_id not in players:
            raise ValueError(f"missing native player {player_id}")
        position, familiarity = player_positions(players[player_id])
        candidates.append((player_id, ratings[player_id] if use_ratings else 0, position, familiarity))
    first, _bench, _score = _choose_balanced_xi_with_score(
        candidates, roles, require_familiarity=True)
    validate_starting_order([player_ids[i] for i in first], roles, players)
    chosen = set(first)
    return first + [i for i in range(len(player_ids)) if i not in chosen]


def validate_formation_phases(tactics: bytes, formations: bytes, physical_id: int,
                              starting_ids: list[int], players: dict[int, bytes]) -> list[dict]:
    """Audit every tactic and all three phases by encoded slot, never row order."""
    tactic_ids = [tid for tid, team, _ in struct.iter_unpack("<III", tactics) if team == physical_id]
    if not tactic_ids or len(set(tactic_ids)) != len(tactic_ids):
        raise ValueError(f"missing/duplicate native tactics for team {physical_id}")
    layouts = {}
    for tid, role, packed in struct.iter_unpack("<III", formations):
        if tid not in tactic_ids:
            continue
        phase, slot = (packed >> 20) & 3, (packed >> 16) & 15
        if phase > 2 or slot >= 11:
            raise ValueError("invalid native formation phase/slot")
        layout = layouts.setdefault((tid, phase), {})
        if slot in layout:
            raise ValueError("duplicate native formation slot")
        layout[slot] = role
    checks = []
    for tid in tactic_ids:
        for phase in range(3):
            slots = layouts.get((tid, phase), {})
            if set(slots) != set(range(11)):
                raise ValueError(f"incomplete formation phase {tid}/{phase}")
            checks.append({"tactic_id": tid, "phase": phase,
                **validate_starting_order(starting_ids, [slots[i] for i in range(11)], players)})
    return checks

"""Read-only PC/Mobile score-movie compatibility audit; no script conversion.

Read explicit owned .bin inputs, or one bounded member from each owned CPK.
Write metadata only. A matching AP2 version never establishes runtime parity.
Generated reports reference local owned assets and should remain ignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

try:
    from .afp_score_layout import read_movies, placements, strings
    from .afp_texture_patch import lzss_decode
    from .build_fl26_cup_catalog import index_cpk, cpk_member
    from .convert_ef_referee import unpack_wesys
except ImportError:
    from afp_score_layout import read_movies, placements, strings
    from afp_texture_patch import lzss_decode
    from build_fl26_cup_catalog import index_cpk, cpk_member
    from convert_ef_referee import unpack_wesys

LIMIT = 64 * 1024 * 1024
RUNTIME_THEME_LIMIT = 2_000_000
REQUIRED_INSTANCES = frozenset((
    "teamName_home", "teamName_away", "teamScore_home", "teamScore_away",
    "time_set", "losstime_progress_set", "time_min_00", "time_min_01",
    "time_min_02", "time_sec_00", "time_sec_01", "aggregate", "losstime",
))


def named_paths(records: list[dict]) -> dict[str, dict]:
    """Resolve initial named instance paths, without conflating equal leaf names."""
    children: dict[int | None, list[dict]] = {}
    for row in records:
        if row.get("frame") == 0 and row.get("name"):
            children.setdefault(row["parent"], []).append(row)
    result = {}

    def walk(parent, prefix, ancestors):
        for row in children.get(parent, ()):
            path = ".".join((*prefix, row["name"]))
            if path in result or len(result) >= 4096:
                raise ValueError("ambiguous or excessive named AP2 instance paths")
            result[path] = row
            source = row.get("source")
            if source is not None and source in children:
                if source in ancestors:
                    raise ValueError("recursive named AP2 instance path")
                walk(source, (*prefix, row["name"]), (*ancestors, source))

    walk(None, (), ())
    return result


def movie_contract(movie) -> dict:
    rows = placements(movie.data)
    paths = named_paths(rows)
    timelines = {}
    for path, initial in paths.items():
        updates = [row for row in rows if row["parent"] == initial["parent"]
                   and row["depth"] == initial["depth"]]
        timelines[path] = {
            "source": initial.get("source"),
            "initial_translate": initial.get("translate"),
            "initial_scale": initial.get("scale", initial.get("scale16")),
            "placement_updates": len(updates),
            "frames": sorted({row["frame"] for row in updates if row["frame"] is not None}),
        }
    return {
        "bytes": len(movie.data), "sha256": hashlib.sha256(movie.data).hexdigest(),
        "ap2_signature": movie.data[:4].hex(),
        "header_word_0c": struct.unpack_from("<I", movie.data, 12)[0],
        "byteswap_descriptor_sha256": hashlib.sha256(movie.info).hexdigest(),
        "placement_count": len(rows), "string_count": len(strings(movie.data)),
        "required_paths": sorted(path for path in paths
                                 if path.rsplit(".", 1)[-1] in REQUIRED_INSTANCES),
        "named_timelines": timelines,
    }


def container_contract(data: bytes) -> dict:
    if not 108 <= len(data) <= LIMIT:
        raise ValueError("scoreboard input size exceeds audit bound")
    base = data.find(b"TXP2")
    if base < 0 or base + 108 > len(data):
        raise ValueError("missing or truncated TXP2")
    txp_size = struct.unpack_from(">I", data, base + 12)[0]
    if txp_size < 108 or base + txp_size > len(data):
        raise ValueError("TXP2 size outside input")
    flags, texture_count, texture_table = struct.unpack_from(">III", data, base + 20)
    if not 0 < texture_count <= 64 or texture_table + 12 * texture_count > txp_size:
        raise ValueError("texture table outside audit bound")
    textures = []
    for i in range(texture_count):
        name, length, offset = struct.unpack_from(">III", data, base + texture_table + 12 * i)
        if name >= txp_size or offset + length > len(data) - base or length < 8:
            raise ValueError("texture reference outside input")
        name_end = data.find(b"\0", base + name, base + txp_size)
        if name_end < 0:
            raise ValueError("unterminated texture name")
        entry = {"name": data[base + name:name_end].decode("ascii"),
                 "offset": offset, "packed_bytes": length,
                 "end": offset + length,
                 "inside_declared_txp": offset + length <= txp_size}
        if flags & 4:
            expanded, packed = struct.unpack_from(">II", data, base + offset)
            if packed != length - 8 or not 64 <= expanded <= LIMIT:
                raise ValueError("unsupported or oversized compressed texture")
            # Decode only the fixed header. PC skins can expand to 60 MB;
            # dimensions/cost do not require allocating or decoding that image.
            header = lzss_decode(memoryview(data)[base + offset + 8:base + offset + length], 64)
            if header[:4] != b"TXDT":
                raise ValueError("unsupported texture header")
            entry.update(expanded_bytes=expanded,
                         dimensions=list(struct.unpack_from(">HH", header, 16)),
                         pixel_format=header[20:24].hex())
        textures.append(entry)
    movies = read_movies(data)
    if len({m.name for m in movies}) != len(movies):
        raise ValueError("duplicate AP2 movie identity")
    score = [m for m in movies if m.name == "game2d_score"]
    return {
        "bytes": len(data), "txp_bytes": txp_size,
        "sha256": hashlib.sha256(data).hexdigest(),
        "texture_count": texture_count, "textures": textures,
        "minimum_payload_span": max(txp_size, *(t["end"] for t in textures)),
        "movies": {m.name: {"bytes": m.size,
                            "sha256": hashlib.sha256(m.data).hexdigest()}
                   for m in movies},
        "score": movie_contract(score[0]) if score else None,
    }


def compare_contracts(mobile: dict, candidate: dict) -> dict:
    blockers = []
    source, target = mobile.get("score"), candidate.get("score")
    if not source:
        raise ValueError("Mobile baseline has no score movie")
    if not target:
        blockers.append("candidate_has_no_game2d_score_movie")
    missing = sorted(set(source["required_paths"]) -
                     set(target["required_paths"] if target else ()))
    if missing:
        blockers.append("native_named_instance_paths_missing")
    if candidate.get("minimum_payload_span", candidate["txp_bytes"]) + 32 > RUNTIME_THEME_LIMIT:
        blockers.append("exceeds_existing_runtime_theme_input_limit")
    if any(not t["inside_declared_txp"] for t in candidate.get("textures", ())):
        blockers.append("referenced_textures_outside_declared_txp_envelope")
    if mobile["texture_count"] != candidate["texture_count"]:
        blockers.append("texture_table_requires_explicit_conversion")
    if source and target and source["header_word_0c"] != target["header_word_0c"]:
        blockers.append("movie_header_features_differ")
    return {
        "schema_version": 1, "scope": "read-only score movie contract comparison",
        "verdict": "incompatible_drop_in" if blockers else "compatibility_not_established",
        "drop_in_port_validated": False, "runtime_theme_input_limit": RUNTIME_THEME_LIMIT,
        "blockers": blockers, "missing_native_paths": missing,
        "extra_movies": sorted(set(candidate["movies"]) - set(mobile["movies"])),
        "missing_movies": sorted(set(mobile["movies"]) - set(candidate["movies"])),
        "mobile": mobile, "candidate": candidate,
        "limitations": [
            "Instance paths are reconstructed from initial named placements, not executed AS3.",
            "Timeline counts and the shared AP2 signature do not validate event/binding semantics.",
            "No texture/shader conversion, runtime replacement or device rendering is performed.",
        ],
    }


def load_owned(path: Path, member: str | None = None) -> bytes:
    if member:
        index, base = index_cpk(path)
        row = index.get(member)
        if row is None or not 0 < int(row["FileSize"]) <= LIMIT:
            raise ValueError("missing or oversized UI CPK member")
        data = cpk_member(path, index, base, member)
    else:
        if not 0 < path.stat().st_size <= LIMIT:
            raise ValueError("UI input exceeds audit bound")
        data = path.read_bytes()
    return unpack_wesys(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mobile", type=Path, required=True)
    parser.add_argument("--mobile-member")
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--candidate-member")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("report output must be a new path; input/output assets are never overwritten")
    report = compare_contracts(
        container_contract(load_owned(args.mobile, args.mobile_member)),
        container_contract(load_owned(args.candidate, args.candidate_member)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "blockers": report["blockers"],
                      "missing_native_paths": len(report["missing_native_paths"]),
                      "output": str(args.output)}, ensure_ascii=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Convert locally installed FL26 portraits for newly allocated players.

Converted PNGs stay under ignored local-debug; no game artwork is committed.
The output can be paired with a future native dt241 candidate after all PESDB
tables and the NRO agree on the player IDs.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

from PIL import Image

from build_fl26_cup_catalog import decoded_member, index_cpk
from import_efootball10_portraits import (
    PES21_HORIZONTAL_CROP,
    PES21_VISIBLE_WIDTH,
    PORTRAIT_SIZE,
)


ROOT = Path(__file__).resolve().parents[1]


def portrait_png(raw: bytes) -> bytes:
    with Image.open(io.BytesIO(raw)) as source:
        source.load()
        if source.size != PORTRAIT_SIZE:
            raise ValueError(f"unexpected FL26 portrait size {source.size}")
        portrait = source.convert("RGBA").crop((
            PES21_HORIZONTAL_CROP, 0,
            PES21_HORIZONTAL_CROP + PES21_VISIBLE_WIDTH, 128,
        ))
    canvas = Image.new("RGBA", PORTRAIT_SIZE, (0, 0, 0, 0))
    canvas.alpha_composite(portrait, (0, 0))
    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fl26-root", type=Path,
                        default=Path("D:/Games/SP Football Life 2026"))
    parser.add_argument("--slot-plan", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-native-slot-plan.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-portraits")
    args = parser.parse_args()
    output = args.output.resolve()
    if (ROOT / "local-debug").resolve() not in output.parents or output.exists():
        raise ValueError("output must be a new directory inside local-debug")
    allocations = json.loads(args.slot_plan.read_text(encoding="utf-8"))["player_slots"]
    if len({int(row["native_player_id"]) for row in allocations}) != len(allocations):
        raise ValueError("duplicate native portrait owner")
    archives = [
        args.fl26_root / "Data/dt14_all.cpk",
        *(args.fl26_root / f"download/data_s2526{suffix}.cpk"
          for suffix in ("a", "b", "c")),
    ]
    indexed = [(path, *index_cpk(path)) for path in archives]
    resolved = []
    for row in allocations:
        member = f"common/render/symbol/player/{int(row['portrait_source_id'])}.dds"
        winners = [(path, index, base) for path, index, base in indexed
                   if member in index]
        if not winners:
            raise FileNotFoundError(f"FL26 portrait missing: {member}")
        path, index, base = winners[-1]
        resolved.append((row, member, path, index, base))
    output.mkdir(parents=True)
    manifest = []
    for row, member, archive, index, base in resolved:
        payload = portrait_png(decoded_member(archive, index, base, member))
        native_id = int(row["native_player_id"])
        (output / f"{native_id}.png").write_bytes(payload)
        manifest.append({
            "source_key": row["source_key"],
            "fl26_player_id": int(row["fl26_player_id"]),
            "native_player_id": native_id,
            "source_archive": archive.name,
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
    report = {
        "schema_version": 1,
        "status": "portraits_staged_not_packaged",
        "count": len(manifest),
        "portraits": manifest,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n",
                                       encoding="utf-8")
    print(json.dumps({"output": str(output), "count": len(manifest),
                      "status": report["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()

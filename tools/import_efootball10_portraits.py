#!/usr/bin/env python3
"""Import EF10 player thumbnails into the PES21 dt241 portrait CPK.

PES21 resolves Game Plan portraits from ``cpk_dat/common/player/<id>.png``.
For EF10-only players the runtime roster uses a globally-unused PES21 ID, so
the EF10 image must be written under that surrogate ID. Shared player IDs are
also supported, allowing their older PES21 image to be refreshed.

The input directory must contain one PNG named ``<ef10_player_id>.png`` for
every converted player. Images are normalized to the PES21 128x128 texture
layout. Its visible portrait content occupies only the leftmost 100 pixels;
the remaining 28 pixels are transparent power-of-two padding. No member is
added and no unrelated portrait is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

from prepare_runtime import read_cpk_packet


PORTRAIT_SIZE = (128, 128)
PES21_VISIBLE_WIDTH = 100
PES21_HORIZONTAL_CROP = (PORTRAIT_SIZE[0] - PES21_VISIBLE_WIDTH) // 2


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_portraits(directory: Path) -> dict[int, Path]:
    result: dict[int, Path] = {}
    for path in directory.rglob("*.png"):
        try:
            player_id = int(path.stem)
        except ValueError:
            continue
        previous = result.get(player_id)
        if previous is not None:
            raise RuntimeError(
                f"duplicate portrait for EF10 player {player_id}: "
                f"{previous} and {path}"
            )
        result[player_id] = path
    return result


def normalize_portrait(source: Path, output: Path) -> None:
    with Image.open(source) as image:
        image.load()
        image = image.convert("RGBA")
        if image.size != PORTRAIT_SIZE:
            image.thumbnail(PORTRAIT_SIZE, Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", PORTRAIT_SIZE, (0, 0, 0, 0))
            x = (PORTRAIT_SIZE[0] - image.width) // 2
            y = (PORTRAIT_SIZE[1] - image.height) // 2
            canvas.alpha_composite(image, (x, y))
            image = canvas
        # EF10 uses the full power-of-two width, while PES21's card widget is
        # authored for a 100-pixel portrait followed by 28 transparent pixels.
        # Centre-crop instead of squeezing so faces retain their proportions.
        left = PES21_HORIZONTAL_CROP
        portrait = image.crop((left, 0, left + PES21_VISIBLE_WIDTH, 128))
        canvas = Image.new("RGBA", PORTRAIT_SIZE, (0, 0, 0, 0))
        canvas.alpha_composite(portrait, (0, 0))
        image = canvas
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output, format="PNG", optimize=True)


def cpk_members(path: Path) -> dict[str, dict[str, object]]:
    with path.open("rb") as source:
        header = read_cpk_packet(source, 0, b"CPK ")[0]
        rows = read_cpk_packet(source, int(header["TocOffset"]), b"TOC ")
    return {
        "/".join(
            part
            for part in (
                str(row.get("DirName") or ""),
                str(row["FileName"]),
            )
            if part and part != "<NULL>"
        ): row
        for row in rows
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--portrait-dir",
        type=Path,
        default=Path("local-debug/efootball10-portraits"),
        help="directory containing <ef10_player_id>.png files",
    )
    parser.add_argument(
        "--validation-report",
        type=Path,
        default=Path(
            "local-debug/efootball10-player-patch/validation-report.json"
        ),
    )
    parser.add_argument(
        "--source-cpk",
        type=Path,
        default=Path(
            "local-debug/efootball10-player-patch/dt241_mobile_all.cpk"
        ),
    )
    parser.add_argument(
        "--output-cpk",
        type=Path,
        default=Path(
            "local-debug/efootball10-player-patch/"
            "dt241_mobile_all_ef10_barcelona_portraits.cpk"
        ),
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="import available images instead of requiring the full roster",
    )
    args = parser.parse_args()

    portrait_dir = args.portrait_dir.resolve()
    report_path = args.validation_report.resolve()
    source_cpk = args.source_cpk.resolve()
    output_cpk = args.output_cpk.resolve()
    if not portrait_dir.is_dir():
        raise FileNotFoundError(f"portrait directory not found: {portrait_dir}")
    if not report_path.is_file():
        raise FileNotFoundError(report_path)
    if not source_cpk.is_file():
        raise FileNotFoundError(source_cpk)
    if source_cpk == output_cpk:
        raise RuntimeError("source and output CPK must differ")

    conversion = json.loads(report_path.read_text(encoding="utf-8"))
    players = conversion["players"]
    available = discover_portraits(portrait_dir)
    missing = sorted(
        int(player["ef10_player_id"])
        for player in players
        if int(player["ef10_player_id"]) not in available
    )
    if missing and not args.allow_partial:
        raise RuntimeError(
            "missing EF10 portraits: " + ", ".join(map(str, missing))
        )

    members = cpk_members(source_cpk)
    selected = [
        player
        for player in players
        if int(player["ef10_player_id"]) in available
    ]
    if not selected:
        raise RuntimeError("no matching EF10 portrait PNGs found")

    normalized_dir = output_cpk.parent / "normalized-portraits"
    replacements: list[tuple[str, Path, dict[str, object]]] = []
    for player in selected:
        source_id = int(player["ef10_player_id"])
        target_id = int(player["pes21_player_id"])
        member = f"common/player/{target_id}.png"
        row = members.get(member)
        if row is None:
            raise RuntimeError(f"PES21 portrait member not found: {member}")
        if int(row["FileSize"]) != int(row["ExtractSize"]):
            raise RuntimeError(f"compressed portrait member is unsupported: {member}")
        normalized = normalized_dir / f"{target_id}.png"
        normalize_portrait(available[source_id], normalized)
        replacements.append((member, normalized, player))

    repacker = Path(__file__).with_name("repack_cpk_members.py").resolve()
    replacement_manifest = output_cpk.with_suffix(".replacements.json")
    replacement_manifest.write_text(
        json.dumps(
            {member: str(normalized) for member, normalized, _player in replacements},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    command = [
        sys.executable,
        str(repacker),
        str(source_cpk),
        str(output_cpk),
        "--replace-manifest",
        str(replacement_manifest),
    ]
    subprocess.run(command, check=True)

    import_report = {
        "source_cpk": str(source_cpk),
        "output_cpk": str(output_cpk),
        "output_sha256": sha256(output_cpk),
        "portrait_size": list(PORTRAIT_SIZE),
        "visible_width": PES21_VISIBLE_WIDTH,
        "imported": [
            {
                "ef10_player_id": int(player["ef10_player_id"]),
                "pes21_player_id": int(player["pes21_player_id"]),
                "name": player["name"],
                "member": member,
                "source": str(available[int(player["ef10_player_id"])]),
            }
            for member, _normalized, player in replacements
        ],
        "missing": missing,
        "partial": bool(missing),
    }
    report_output = output_cpk.with_suffix(".json")
    report_output.write_text(
        json.dumps(import_report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"imported portraits: {len(replacements)}")
    print(f"output: {output_cpk}")
    print(f"sha256: {import_report['output_sha256']}")
    print(f"report: {report_output}")


if __name__ == "__main__":
    main()

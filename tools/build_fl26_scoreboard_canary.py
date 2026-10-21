"""Build an isolated Spain layout canary from explicit owned Mobile/FL26 UI.

Author the corrected 3-column/2-row panel using the owned FL26 league mark.
Retain Mobile scripts, bindings, frame/event labels, tag sizes and other movies.
Motion is authored in verified Mobile placement fields, not imported PC motion.
Generated UI bytes and previews must remain local and ignored. Nothing is staged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from afp_score_layout import read_movies, placements, swap_fields
from afp_texture_patch import read_atlas, replace_atlas
from audit_fl26_scoreboard_contract import load_owned, named_paths, RUNTIME_THEME_LIMIT
from build_competition_scoreboards import HEADER, txp
from build_efootball10_scoreboard_v2 import region_bounds
from fl26_scoreboard_crop import crop_rgba
from pack_runtime_assets import checksum

MOBILE_SHA256 = "ff2f2a5a9dea9541dced65eaec0601fd241b03d6233b33f81446e64e690688a4"
SPAIN_SHA256 = "3c088dbee7e4bd18bdfd9a98a3dc5b89c580e0266516e783f873a35724d0acce"
SPAIN_PLATE_CROP = (485, 1902, 725, 2028)
# This bounded owned crop supplies only the league-mark mask. Its old stepped
# panel is superseded by the human's corrected text reference.
ATLAS_DESTINATION = (570, 256)
PANEL_SIZE = (246, 132)
COLUMN_EDGES = (0, 105, 180, 246)
ROW_HEIGHT = 66
PANEL_ORIGIN = (6, 20)
NAVY = (2, 3, 16)
RED = (255, 65, 65)
DESIGN_REFERENCE_SHA256 = "640d95ebd1322aa76e3c113d4f191012b2325ce26f234ae9003d96689e4c6332"
TARGETS = {
    1: (190, 158), 7: (248, 158),      # native card states below the panel
    13: (6, 86),                      # old background made transparent
    77: (1.5, 103), 78: (1.5, 103),   # clock only in lower-left cell
    52: (140, 184), 56: (6, 158),      # aggregate and injury-time child state
    60: PANEL_ORIGIN,
    61: (114, 105.65), 63: (114, 39.65),
    65: (200, 103), 67: (200, 37),
    69: (184, 95), 75: (180, 29),      # native kit tint at right of name cells
}
EXPECTED = {1: "cardNum_home", 7: "cardNum_away", 77: "time_set",
            78: "losstime_progress_set", 52: "aggregate", 56: "losstime",
            61: "teamName_away", 63: "teamName_home", 65: "teamScore_away",
            67: "teamScore_home", 69: "teamColor_away", 75: "teamColor_home"}


def make_panel(owned_plate: Image.Image):
    """Use the owned red glyph as a white alpha mask in the corrected panel."""
    rgba = np.asarray(owned_plate.convert("RGBA"))[:64, :97].astype(np.float32)
    signal = np.maximum(0, rgba[:, :, 0] - np.maximum(rgba[:, :, 1], rgba[:, :, 2]))
    peak = float(signal.max())
    if peak < 80:
        raise ValueError("owned FL26 league-mark mask is missing")
    alpha = np.rint(signal / peak * rgba[:, :, 3]).astype(np.uint8)
    mask = Image.fromarray(alpha)
    bbox = mask.getbbox()
    if bbox is None:
        raise ValueError("owned league mark has empty alpha")
    mask = mask.crop(bbox)
    mask.thumbnail((53, 49), Image.Resampling.LANCZOS)
    panel = Image.new("RGBA", PANEL_SIZE, "white")
    draw = ImageDraw.Draw(panel)
    draw.rectangle((0, 0, COLUMN_EDGES[1] - 1, ROW_HEIGHT - 1), fill=RED)
    draw.rectangle((COLUMN_EDGES[1], 0, COLUMN_EDGES[2] - 1, PANEL_SIZE[1] - 1), fill=NAVY)
    mark = Image.new("RGBA", mask.size, "white")
    mark.putalpha(mask)
    panel.alpha_composite(mark, ((COLUMN_EDGES[1] - mask.width) // 2,
                                 (ROW_HEIGHT - mask.height) // 2))
    draw.line((COLUMN_EDGES[2] + 4, ROW_HEIGHT, PANEL_SIZE[0] - 5, ROW_HEIGHT), fill=NAVY, width=2)
    return panel, {"design": "human-corrected rectangular text layout",
                   "reference_sha256": DESIGN_REFERENCE_SHA256,
                   "panel_pixels": list(PANEL_SIZE), "column_edges": list(COLUMN_EDGES),
                   "row_height": ROW_HEIGHT, "league_mark": "owned FL26 glyph mask rendered white on red",
                   "league_mark_mask_source_bbox": list(bbox), "top_clock": False,
                   "stepped_notch": False, "team_mode": "existing native UIR team initials"}


def verify_field_geometry(rows):
    """Bound native glyph/text extents in cells, including appearance updates.

    These measured Mobile bounds are a host geometry check, not text rendering.
    Clock spans are the native 1/2/3-minute-digit states retained by the accepted
    compact scorebar. Both mutually exclusive time states share the same cell.
    """
    x, y = PANEL_ORIGIN
    cells = {"clock": (x, y + ROW_HEIGHT, x + 105, y + 132),
             63: (x + 105, y, x + 172, y + 66),
             61: (x + 105, y + 66, x + 172, y + 132),
             67: (x + 180, y, x + 246, y + 66),
             65: (x + 180, y + 66, x + 246, y + 132)}
    checks = []
    for row in rows:
        if row["parent"] != 28 or "translate" not in row:
            continue
        depth = row["depth"]
        rx, ry = row["translate"]
        if depth in (77, 78):
            bounds = [(rx + lo, ry + 4, rx + hi, ry + 28)
                      for lo, hi in ((32, 82.65), (24.65, 89.3), (18, 96))]
            cell = cells["clock"]
        elif depth in (61, 63):
            bounds, cell = [(rx, ry, rx + 60, ry + 26)], cells[depth]
        elif depth in (65, 67):
            bounds, cell = [(rx, ry, rx + 38, ry + 32)], cells[depth]
        else:
            continue
        for bound in bounds:
            if not (cell[0] <= bound[0] and cell[1] <= bound[1] and
                    bound[2] <= cell[2] and bound[3] <= cell[3]):
                raise ValueError(f"native field leaves its reference cell: depth {depth}, frame {row['frame']}")
        checks.append({"depth": depth, "frame": row["frame"], "bounds": bounds})
    if len(checks) < 60:
        raise ValueError("native field geometry coverage is incomplete")
    return {"clock_cell": list(cells["clock"]), "clock_minute_states": [1, 2, 3],
            "checked_placement_updates": len(checks), "fields_inside_separate_cells": True,
            "clock_background": "old overlapping tile transparent; white lower-left cell is in the main panel",
            "team_text_source": "main.scoreGroup.teamName_home / main.scoreGroup.teamName_away; native updates unchanged"}


def authored_transform(row: dict, initial: dict) -> tuple[float, float]:
    """Map native appearance displacement to a vertical authored reveal."""
    x, y = TARGETS[row["depth"]]
    if row["frame"] == 0:
        return x, y
    old_x, old_y = row["translate"]
    base_x, base_y = initial["translate"]
    if row["depth"] == 60:
        # Existing 1..16 scale/translation fields become a vertical unfold.
        return x, y - 14 * max(0, min(1, (old_x - base_x) / 28.8))
    if row["depth"] in (61, 63):
        return x, y + abs(old_x - base_x) * .75
    if row["depth"] in (65, 67):
        return x, y + abs(old_x - base_x) * 1.5
    return x, y + (old_y - base_y) * .4


def patch_movie(data: bytes):
    rows = placements(data)
    initial = {r["depth"]: r for r in rows if r["parent"] == 28 and r["frame"] == 0}
    if len(rows) != 534:
        raise ValueError("unsupported Mobile placement revision")
    for depth, name in EXPECTED.items():
        if initial.get(depth, {}).get("name") != name:
            raise ValueError(f"native scoreboard binding mismatch: {name}")
    if initial[60].get("source") != 6 or initial[60].get("scale") != (1, 1):
        raise ValueError("requires accepted compact Mobile main plate")
    output = bytearray(data)
    allowed = bytearray(len(data))
    edits = []

    def write(offset, fmt, values, field, row):
        replacement = struct.pack("<" + fmt, *values)
        before = data[offset:offset + len(replacement)]
        if before == replacement:
            return
        output[offset:offset + len(replacement)] = replacement
        allowed[offset:offset + len(replacement)] = b"\1" * len(replacement)
        edits.append({"depth": row["depth"], "frame": row["frame"], "field": field,
                      "offset": offset, "before": before.hex(), "after": replacement.hex()})

    for row in rows:
        depth = row["depth"]
        if row["parent"] != 28 or depth not in TARGETS:
            continue
        if "translate" in row:
            x, y = authored_transform(row, initial[depth])
            write(row["translate_offset"], "ii", (round(x * 20), round(y * 20)), "translate", row)
        if depth == 60 and "scale" in row:
            # Retain frame count and duration; change the unfolding axis.
            scale = max(0, min(1, (1 - row["scale"][0]) / .150390625))
            write(row["scale_offset"], "ii", (1024, round((1 - .18 * scale) * 1024)), "scale", row)
        if depth in (61, 63) and "scale" in row:
            sx, sy = row["scale"]
            write(row["scale_offset"], "ii", (round(sx * 60 / 78 * 1024), round(sy * 1024)), "name_bounds", row)
        if "mult8" in row:
            value = int(row["mult8"][0])
            alpha, rgb = value & 255, value >> 8
            if depth in (61, 63):
                rgb = 0xffffff
            elif depth in (65, 67):
                rgb = 0x020310
            if 35 <= row["frame"] <= 44 or 48 <= row["frame"] <= 54:
                alpha = round(255 * (alpha / 255) ** 1.5)
            write(row["mult8_offset"], "I", ((rgb << 8) | alpha,), "colour_alpha", row)
    if any(a != b and not allowed[i] for i, (a, b) in enumerate(zip(data, output))):
        raise ValueError("edit outside verified placement fields")
    after = placements(bytes(output))
    if len(after) != len(rows) or named_paths(after).keys() != named_paths(rows).keys():
        raise ValueError("native placement hierarchy changed")
    geometry = verify_field_geometry(after)
    return bytes(output), {"placement_count": len(rows), "edits": edits,
                           "all_other_movie_bytes_identical": True,
                           "frame_labels_scripts_bindings_unchanged": True,
                           "motion": "authored Mobile vertical unfold, stagger and exit fade",
                           "field_geometry": geometry,
                           "pc_animation_imported": False}


def repack_plate(mobile: bytes, plate: Image.Image):
    atlas, regions, (base, _, _, _) = read_atlas(mobile)
    width, height = struct.unpack_from(">HH", atlas, 16)
    if (width, height) != (1024, 512) or plate.size != PANEL_SIZE:
        raise ValueError("unexpected Mobile atlas or PC score plate dimensions")
    left, top = ATLAS_DESTINATION
    right, bottom = left + plate.width, top + plate.height
    plate_index = next(i for i, r in enumerate(regions) if r["name"] == "game2dPes-score-plateMain")
    for i, region in enumerate(regions):
        l, t, r, b = region_bounds(region)
        if i != plate_index and l < right and r > left and t < bottom and b > top:
            raise ValueError("score plate destination overlaps a live atlas region")
    pixels = np.frombuffer(atlas[64:], np.uint8).reshape(height, width, 4).copy()
    if pixels[top:bottom, left:right, 0].any():
        raise ValueError("score plate destination has occupied alpha pixels")
    pixels[top:bottom, left:right] = np.asarray(plate)[:, :, [3, 0, 1, 2]]
    # Clock/added-time digits keep all source alpha and native digit selection.
    for region in regions:
        if region["name"].startswith("MatchPlate-texFont-"):
            l, t, r, b = region_bounds(region)
            pixels[t:b, l:r, 1:] = NAVY
        elif region["name"] == "game2dPes-score-plateTime":
            l, t, r, b = region_bounds(region)
            # Its native 124px tile is wider than the 105px reference cell.
            # The authored main panel supplies the white background instead.
            pixels[t:b, l:r, 0] = 0
    output = bytearray(mobile)
    table = struct.unpack_from(">I", output, base + 40)[0]
    rect = (0, left * 2 + 1, top * 2 + 1, right * 2 - 1, bottom * 2 - 1)
    struct.pack_into(">5H", output, base + table + plate_index * 10, *rect)
    output = replace_atlas(bytes(output), atlas[:64] + pixels.tobytes(), candidate_limit=4)
    checked, changed_regions, _ = read_atlas(output)
    if checked != atlas[:64] + pixels.tobytes():
        raise ValueError("Mobile atlas roundtrip mismatch")
    for i, (before, after) in enumerate(zip(regions, changed_regions)):
        if i != plate_index and before != after:
            raise ValueError("unrelated region mapping changed")
    return output, {"dimensions": [width, height], "decoded_bytes": len(atlas),
                    "new_plate_region": list(rect), "unrelated_region_metadata_unchanged": True}


def build(mobile: bytes, spain: bytes):
    if hashlib.sha256(mobile).hexdigest() != MOBILE_SHA256:
        raise ValueError("Mobile input does not match pinned accepted baseline")
    if hashlib.sha256(spain).hexdigest() != SPAIN_SHA256:
        raise ValueError("FL26 Spain input does not match pinned source")
    owned_plate, crop_report = crop_rgba(spain, 1, SPAIN_PLATE_CROP)
    plate, design_report = make_panel(owned_plate)
    movies = read_movies(mobile)
    score = next(m for m in movies if m.name == "game2d_score")
    score_data, motion_report = patch_movie(score.data)
    changed = bytearray(mobile)
    changed[score.offset:score.offset + score.size] = swap_fields(score_data, score.info)
    changed, atlas_report = repack_plate(bytes(changed), plate)
    after = read_movies(changed)
    for before, candidate in zip(movies, after):
        if before.name != candidate.name or before.info != candidate.info:
            raise ValueError("native movie identity or byteswap descriptor changed")
        if before.name != "game2d_score" and before.data != candidate.data:
            raise ValueError("unrelated native movie changed")
    source_txp, target_txp = txp(mobile), txp(changed)
    packet = HEADER.pack(b"NXSB01\0\0", len(source_txp), len(target_txp),
                         checksum(source_txp), checksum(target_txp)) + target_txp
    if len(packet) > RUNTIME_THEME_LIMIT:
        raise ValueError("candidate exceeds existing 2 MB runtime limit")
    report = {"schema_version": 1, "league_key": 11, "classification": "isolated authored Mobile adaptation canary",
              "source_mobile_sha256": MOBILE_SHA256, "source_fl26_spain_sha256": SPAIN_SHA256,
              "packet_bytes": len(packet), "packet_sha256": hashlib.sha256(packet).hexdigest(),
              "expected_original_txp_bytes": len(source_txp),
              "expected_original_txp_checksum": f"{checksum(source_txp):016x}",
              "runtime_limit_unchanged": RUNTIME_THEME_LIMIT, "pc_crop": crop_report,
              "design": design_report,
              "atlas": atlas_report, "native_timeline": motion_report,
              "other_movies_unchanged": len(movies) - 1, "native_paths_preserved": True,
              "device_validated": False, "production_mutated": False,
              "remaining_proof": ["native appearance and authored motion playback",
                                  "clock 0/45/90/100+ minutes and injury time",
                                  "aggregate, cards, penalties and native goal/replay events",
                                  "next match theme restoration and frame-time/memory measurements"]}
    return changed, packet, plate, report


def preview(plate: Image.Image):
    """A labelled host composition; text samples are not a native screenshot."""
    image = Image.new("RGBA", (560, 300), (41, 77, 57, 255))
    image.alpha_composite(plate, (38, 70))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 23)
    small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14)
    draw.text((90, 169), "04:49", anchor="mm", fill=NAVY, font=font)
    for y, name, score in ((103, "RMA", "0"), (169, "VAL", "0")):
        draw.text((177, y), name, anchor="mm", fill="white", font=font)
        draw.text((251, y), score, anchor="mm", fill=NAVY, font=font)
    draw.rectangle((210, 80, 217, 127), fill=(230, 230, 230))
    draw.rectangle((210, 146, 217, 193), fill=RED)
    draw.text((24, 16), "SPAIN — CORRECTED TEXT REFERENCE / MOBILE CANARY", font=small, fill="white")
    draw.text((24, 242), "Host composition; sample text. Native appearance is unverified.", font=small, fill="white")
    draw.text((24, 266), "Authored Mobile reveal/fade; PC animation is not imported.", font=small, fill="white")
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mobile", type=Path, required=True)
    parser.add_argument("--mobile-member")
    parser.add_argument("--spain", type=Path, required=True)
    parser.add_argument("--spain-member")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output must be a new ignored local directory")
    output = args.output.resolve()
    if "local-debug" not in output.parts:
        raise ValueError("proprietary canary output must remain under local-debug")
    changed, packet, plate, report = build(load_owned(args.mobile, args.mobile_member),
                                          load_owned(args.spain, args.spain_member))
    output.mkdir(parents=True)
    (output / "game2dPes-spain-canary.bin").write_bytes(changed)
    (output / "c11-spain-canary.nxsb").write_bytes(packet)
    plate.save(output / "plate.png")
    preview(plate).save(output / "preview-host-composition.png")
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("classification", "packet_bytes", "device_validated", "production_mutated")}))


if __name__ == "__main__":
    main()

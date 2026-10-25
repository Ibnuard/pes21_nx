"""Author the shared FootballNX27 League/Cup skin over the compatible Mobile UI.

Only the atlas and exposed score-movie placement fields change. Native events,
scripts, names, frame counts and bindings stay exact. Game-derived outputs must
remain ignored. The brand artwork itself is project-authored and public.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from afp_score_layout import placements, read_movies, swap_fields
from afp_texture_patch import read_atlas, replace_atlas
from build_efootball10_scoreboard_v2 import region_bounds
from build_fl26_scoreboard_profiles import field_edit_report, patch_added_time
from pack_runtime_assets import checksum

ROOT = Path(__file__).resolve().parents[1]
MOBILE_SHA256 = "ff2f2a5a9dea9541dced65eaec0601fd241b03d6233b33f81446e64e690688a4"
HEADER = struct.Struct("<8sIIQQ")
WHITE = (255, 255, 255)
BLUE = (18, 91, 255)
RED = (236, 36, 64)
INK = (26, 32, 41)
CELLS = {63: (6, 20, 84, 68), 67: (84, 20, 124, 68),
         65: (124, 20, 164, 68), 61: (164, 20, 242, 68)}
CLOCK = (250, 20, 330, 68)
ADDED = (250, 74, 310, 106)
ADDED_SIZE = (60, 32)
DX = {7: -16, 52: -8, 61: -16, 65: -12, 67: -4, 69: -17, 75: 9, 77: -24, 78: -24}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def txp(container):
    start = container.index(b"TXP2")
    size = struct.unpack_from(">I", container, start + 12)[0]
    if not 108 <= size <= len(container) - start:
        raise ValueError("invalid TXP2 range")
    return container[start:start + size]


def panel(brand):
    """Keep the native 404x48 footprint with an 80px full-wordmark cell."""
    image = Image.new("RGBA", (404, 48), WHITE + (255,))
    draw = ImageDraw.Draw(image)
    draw.rectangle((78, 0, 157, 47), fill=BLUE)
    draw.rectangle((117, 4, 118, 43), fill=RED)
    draw.rectangle((0, 0, 403, 2), fill=RED)
    draw.rectangle((0, 46, 403, 47), fill=BLUE)
    draw.line((244, 9, 244, 38), fill=(215, 224, 239), width=1)
    draw.line((324, 9, 324, 38), fill=(215, 224, 239), width=1)
    logo = brand.convert("RGBA").copy()
    logo.thumbnail((72, 34), Image.Resampling.LANCZOS)
    image.alpha_composite(logo, (324 + (80 - logo.width) // 2, (48 - logo.height) // 2))
    return image


def patch_movie(data):
    rows = placements(data)
    initial = {r["depth"]: r for r in rows if r["parent"] == 28 and r["frame"] == 0}
    expected = {61: "teamName_away", 63: "teamName_home", 65: "teamScore_away",
                67: "teamScore_home", 69: "teamColor_away", 77: "time_set"}
    if any(initial[d].get("name") != name for d, name in expected.items()):
        raise ValueError("unsupported native score hierarchy")
    out = bytearray(data)
    allowed = bytearray(len(data))
    for r in rows:
        if r["parent"] == 27:
            # Scale the full native palette wrapper, including its rectangle,
            # so no old tall backing survives behind the two smaller tiles.
            for field, fmt, factors, size in (("translate", "ii", (.5, 7/12), 8),
                                               ("scale16", "hh", (.5, 7/12), 4)):
                if field not in r:
                    continue
                unit = 20 if field == "translate" else 32768
                off = r[field + "_offset"]
                struct.pack_into("<" + fmt, out, off,
                                 *(round(v * f * unit) for v, f in zip(r[field], factors)))
                allowed[off:off + size] = b"\1" * size
        if r["parent"] != 28:
            continue
        d = r["depth"]
        if d in DX and "translate" in r:
            x, y = r["translate"]
            off = r["translate_offset"]
            struct.pack_into("<ii", out, off, round((x + DX[d]) * 20),
                             round((y + (9.15 if d in (69, 75) else 0)) * 20))
            allowed[off:off + 8] = b"\1" * 8
        if d in CELLS and "mult8" in r:
            rgb = WHITE if d in (65, 67) else INK
            alpha = int(r["mult8"][0]) & 255
            off = r["mult8_offset"]
            struct.pack_into("<I", out, off, int.from_bytes(bytes((*rgb, alpha)), "big"))
            allowed[off:off + 4] = b"\1" * 4
    # Reuse the independently verified native conditional added-time clip.
    before_loss = bytes(out)
    patch_added_time(out, rows, {"added_time_cell": ADDED})
    for r in rows:
        if r["parent"] == 24 and r["depth"] == 3 and "translate" in r:
            # Preserve the native font/glyph size. The larger plate adds room
            # around the actual plus/number ink, which sat low in the old box.
            struct.pack_into("<ii", out, r["translate_offset"], 11 * 20,
                             round((r["translate"][1] - 2.65) * 20))
    loss_report = field_edit_report(before_loss, bytes(out))
    for e in loss_report["edits"]:
        if (e["parent"], e["depth"]) not in ((28, 13), (28, 56), (24, 3), (23, 2)):
            raise ValueError("unexpected loss-time edit")
        off = e["offset"]
        allowed[off:off + len(bytes.fromhex(e["before"]))] = b"\1" * len(bytes.fromhex(e["before"]))
    for e in loss_report["placement_flag_changes"]:
        allowed[e["offset"]:e["offset"] + 4] = b"\1" * 4
    if any(a != b and not allowed[i] for i, (a, b) in enumerate(zip(data, out))):
        raise ValueError("score movie changed outside approved score/loss-time fields")
    report = field_edit_report(data, bytes(out))
    # The native entry/exit offsets remain animated. Check the settled anchors
    # and the complete 1/2/3-digit clock, whose widest state is 100+ minutes.
    ready = {r["depth"]: r for r in placements(bytes(out)) if r["parent"] == 28 and r["frame"] == 0}
    for depth, cell in CELLS.items():
        x, y = ready[depth]["translate"]
        w, h = (78, 26) if depth in (61, 63) else (38, 32)
        if not (cell[0] <= x and x + w <= cell[2] and cell[1] <= y and y + h <= cell[3]):
            raise ValueError("native name/score leaves its cell")
        if abs(x + w / 2 - (cell[0] + cell[2]) / 2) > .05 or abs(y + h / 2 - 44) > .5:
            raise ValueError("native field is not centered")
    x, y = ready[77]["translate"]
    for lo, hi in ((32, 82.65), (24.65, 89.3), (18, 96)):
        if not (CLOCK[0] <= x + lo < x + hi <= CLOCK[2] and y + 4 >= CLOCK[1] and y + 28 <= CLOCK[3]):
            raise ValueError("native clock leaves its cell")
    child = {r["depth"]: r for r in placements(bytes(out)) if r["parent"] == 27 and r["frame"] == 0}
    kit_bounds = []
    for depth, expected in ((75, (8, 30, 12, 58)), (69, (244, 30, 248, 58))):
        x, y = ready[depth]["translate"]
        sx = ready[depth].get("scale", (1, 1))[0]
        boxes = []
        for c in (child[1], child[3]):
            cx, cy = c["translate"]
            x0, x1 = sorted((x + sx * cx, x + sx * (cx + 4)))
            boxes.append((x0, y + cy, x1, y + cy + 14))
        bound = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                 max(b[2] for b in boxes), max(b[3] for b in boxes))
        if any(abs(a-b) > .025 for a, b in zip(bound, expected)):
            raise ValueError("native kit strip is not inset and centered")
        kit_bounds.append(bound)
    report.update(native_field_cells=CELLS, clock_cell=CLOCK, added_time_cell=ADDED,
                  centered_settled_fields=True, clock_minute_states=[1, 2, 3],
                  native_entry_exit_motion_preserved=True, kit_bounds=kit_bounds,
                  kit_tile_size=[4, 14], kit_backing_scaled=True)
    return bytes(out), report


def build(original, brand):
    if digest(original) != MOBILE_SHA256:
        raise ValueError("requires the pinned accepted 404x48 Mobile UI")
    changed = bytearray(original)
    movies = read_movies(original)
    movie = next(m for m in movies if m.name == "game2d_score")
    patched, movie_report = patch_movie(movie.data)
    changed[movie.offset:movie.offset + movie.size] = swap_fields(patched, movie.info)
    atlas, regions, (base, _, _, _) = read_atlas(bytes(changed))
    width, height = struct.unpack_from(">HH", atlas, 16)
    if (width, height) != (1024, 512):
        raise ValueError("unsupported atlas dimensions")
    before = np.frombuffer(atlas[64:], np.uint8).reshape(height, width, 4)
    pixels = before.copy()
    mask = np.zeros((height, width), bool)
    plate = panel(brand)
    for r in regions:
        name = r["name"]
        l, t, right, b = region_bounds(r)
        if name == "game2dPes-score-plateMain":
            if (right - l, b - t) != plate.size:
                raise ValueError("unexpected plate dimensions")
            pixels[t:b, l:right] = np.asarray(plate)[:, :, [3, 0, 1, 2]]
        elif name.startswith("MatchPlate-texFont-"):
            pixels[t:b, l:right, 1:] = INK
        elif name == "game2dPes-score-plateTime":
            # Enlarge the native conditional plate inside its existing region.
            # This instance is separate from the hidden ordinary clock plate.
            aw, ah = ADDED_SIZE
            if aw > right-l or ah > b-t:
                raise ValueError("added-time plate exceeds its native atlas region")
            pixels[t:t + ah, l:l + aw] = (255, 255, 255, 255)
            table = struct.unpack_from(">I", changed, base + 40)[0]
            i = regions.index(r)
            struct.pack_into(">5H", changed, base + table + i * 10,
                             0, l * 2 + 1, t * 2 + 1, (l + aw) * 2 - 1, (t + ah) * 2 - 1)
        elif name.startswith("game2dPes-score-plateTeamColor-"):
            pixels[t:t + 14, l:l + 4] = (255, 255, 255, 255)
            table = struct.unpack_from(">I", changed, base + 40)[0]
            i = regions.index(r)
            struct.pack_into(">5H", changed, base + table + i * 10,
                             0, l * 2 + 1, t * 2 + 1, (l + 4) * 2 - 1, (t + 14) * 2 - 1)
        else:
            continue
        mask[t:b, l:right] = True
    if not np.array_equal(before[~mask], pixels[~mask]):
        raise ValueError("unrelated atlas pixels changed")
    changed = replace_atlas(bytes(changed), atlas[:64] + pixels.tobytes(), candidate_limit=4)
    checked, after_regions, _ = read_atlas(changed)
    if checked != atlas[:64] + pixels.tobytes():
        raise ValueError("atlas roundtrip changed")
    if any(old != new for old, new in zip(regions, after_regions)
           if old["name"] != "game2dPes-score-plateTime"
           and not old["name"].startswith("game2dPes-score-plateTeamColor-")):
        raise ValueError("unrelated atlas mapping changed")
    after = read_movies(changed)
    if len(movies) != len(after):
        raise ValueError("movie inventory changed")
    for old, new in zip(movies, after):
        if (old.name, old.info) != (new.name, new.info) or (old.name != movie.name and old.data != new.data):
            raise ValueError("unrelated native movie changed")
    source, target = txp(original), txp(changed)
    packet = HEADER.pack(b"NXSB01\0\0", len(source), len(target), checksum(source), checksum(target)) + target
    return changed, packet, plate, dict(theme="FootballNX27", keys=[1000, 1001],
        source_sha256=digest(original), packet_sha256=digest(packet), packet_bytes=len(packet),
        footprint=[404, 48], native_movie=movie_report, atlas_roundtrip=True,
        unrelated_atlas_pixels_exact=True, unrelated_atlas_mappings_exact=True,
        conditional_plate_pixels=list(ADDED_SIZE),
        unrelated_movies_exact=True, device_accepted=False)


def preview(plate, added=False, scores=("0", "0"), time="7:44"):
    """Host layout proof; native-font lifecycle still requires device evidence."""
    canvas = Image.new("RGBA", (520, 150), (53, 91, 65, 255))
    canvas.alpha_composite(plate, (38, 32))
    draw = ImageDraw.Draw(canvas)
    font_path = ROOT / "assets/fonts/efootball/eFootballSans-Bold.ttf"
    if not font_path.is_file():
        raise FileNotFoundError("optional local native font required for this preview")
    font = ImageFont.truetype(str(font_path), 24)
    for d, text in ((63, "MUN"), (61, "BAR"), (67, scores[0]), (65, scores[1])):
        l, t, r, b = CELLS[d]
        draw.text(((l + r) / 2 + 32, (t + b) / 2 + 12), text, anchor="mm", font=font,
                  fill=WHITE if d in (65, 67) else INK)
    draw.text((322, 56), time, anchor="mm", font=ImageFont.truetype(str(font_path), 20), fill=INK)
    # Native team-colour strips: 4x14 per colour, centered with 10px margins.
    for x, colors in ((40, (RED, WHITE)), (276, (BLUE, RED))):
        draw.rectangle((x, 42, x + 3, 55), fill=colors[0])
        draw.rectangle((x, 56, x + 3, 69), fill=colors[1])
    if added:
        l, t, r, b = ADDED
        draw.rectangle((l + 32, t + 12, r + 31, b + 11), fill=WHITE)
        draw.text(((l + r) / 2 + 32, (t + b) / 2 + 12), "+4", anchor="mm",
                  font=ImageFont.truetype(str(font_path), 18), fill="black")
    return canvas


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mobile", required=True, type=Path)
    p.add_argument("--brand", type=Path, default=ROOT / "art/main_menu/brand-logo-runtime.png")
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    changed, packet, plate, report = build(a.mobile.read_bytes(), Image.open(a.brand))
    (a.output / "mobile.nx27.bin").write_bytes(changed)
    for key in (1000, 1001):
        (a.output / f"c{key}.nxsb").write_bytes(packet)
    plate.save(a.output / "plate.png")
    preview(plate).save(a.output / "scoreboard.png")
    preview(plate, True, ("12", "10"), "102:08").save(a.output / "scoreboard-added.png")
    report["brand_sha256"] = digest(a.brand.read_bytes())
    (a.output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"FootballNX27 Cup/League: {len(packet)} bytes each; native script/atlas checks passed")


if __name__ == "__main__":
    main()

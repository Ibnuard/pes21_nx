"""Build compact, source-backed FL26 designs on the pinned Mobile event contract.

These are authored Mobile adaptations, not imported PC animations. Only verified
placement fields and explicitly selected atlas regions change. Local proprietary
inputs/outputs remain ignored; no runtime installation or archive merge is done.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import build_fl26_scoreboard_canary as v62
from afp_score_layout import read_movies, placements, swap_fields
from afp_texture_patch import read_atlas, replace_atlas
from audit_fl26_scoreboard_contract import load_owned, named_paths
from build_competition_scoreboards import HEADER, txp
from build_efootball10_scoreboard_v2 import region_bounds
from fl26_scoreboard_crop import crop_rgba
from pack_runtime_assets import checksum

SCALE = 2 / 3
SAFE_OFFSET = (32, 12)  # Measured from the supplied 1280x720 native screenshots.
EVENT_OLD_TOP = 94
PROFILES = {
    "spain": dict(key=11, source="Spain", sha256=v62.SPAIN_SHA256,
                  size=(164, 88), layout="stacked rectangular 70:50:44 cells",
                  names=((78, 33.1), (78, 77.1)), scores=((135.3, 31.3), (135.3, 75.3)),
                  clock=(3, 75.3), clock_cell=(6, 64, 76, 108),
                  text_y_offset=-3, added_time_cell=(6, 114, 54, 138), added_time_relation="below",
                  name_cells=((76, 20, 121, 64), (76, 64, 121, 108)),
                  score_cells=((126, 20, 170, 64), (126, 64, 170, 108)),
                  kits=((121, 26), (126, 70)), ink=(2, 3, 16)),
    "england": dict(key=9, source="England", sha256="586d0a379843b22f1500fe0276254b935a278ee9946a13db522d8fdddbdb9e09",
                    size=(306, 64), layout="horizontal names, green score cells, central lion, lower clock tab",
                    names=((26, 31.1), (240, 31.1)), scores=((108, 29.3), (189, 29.3)),
                    clock=(121, 61.3), clock_cell=(114, 60, 204, 84),
                    name_width=78, added_time_cell=(204, 60, 252, 84),
                    added_time_relation="right",
                    text_y_offset=-3,  # Optical lift requested after native font device review.
                    name_cells=((6, 20, 98, 60), (220, 20, 312, 60)),
                    score_cells=((98, 20, 138, 60), (180, 20, 220, 60)),
                    kits=((91, 25), (227, 25)), ink=(55, 0, 60)),
    "france": dict(key=12, source="France", sha256="46ffc0ddcd5602b706578e67f6d0f25450e856dccd225f745cddd8a536b08f54",
                   size=(164, 110), layout="full-height blue Ligue 1 mark, stacked rows, lower clock tab",
                   names=((78, 33.1), (78, 77.1)), scores=((135.3, 31.3), (135.3, 75.3)),
                   clock=(3, 108.3), clock_cell=(6, 108, 76, 130),
                   text_y_offset=-3, added_time_cell=(6, 136, 54, 160), added_time_relation="below",
                   name_cells=((70, 20, 121, 64), (70, 64, 121, 108)),
                   score_cells=((126, 20, 170, 64), (126, 64, 170, 108)),
                   kits=((121, 26), (126, 70)), ink=(2, 3, 16)),
    "italy": dict(key=10, source="Italy", sha256="60d42f819d44bbc24f69f7dfecc815d6302040e1111b712ff9f874a6825e612a",
                  size=(320, 70), bar_height=40,
                  layout="40px blue horizontal bar, white diagonal score center, cyan lower clock tab",
                  names=((22, 31.7), (250, 31.7)), scores=((130, 29.3), (177, 29.3)),
                  clock=(3, 62.3), clock_cell=(6, 62, 76, 90),
                  text_y_offset=-3, added_time_cell=(76, 64, 124, 88), added_time_relation="right",
                  name_cells=((6, 20, 118, 60), (214, 20, 326, 60)),
                  score_cells=((118, 20, 166, 60), (166, 20, 214, 60)),
                  kits=((101, 28), (231, 28)), ink=(0, 12, 83)),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def panel_for(profile, owned):
    """Build from inspected source crops; broadcaster/sponsor tiles are excluded."""
    spec = PROFILES[profile]
    crops = []

    def crop(rect):
        image, report = crop_rgba(owned, 1, rect)
        crops.append(report)
        return image

    if profile == "spain":
        panel, _ = v62.make_panel(crop(v62.SPAIN_PLATE_CROP))
        panel = panel.resize(spec["size"], Image.Resampling.LANCZOS)
    elif profile == "france":
        original = crop((485, 1902, 725, 2028))
        panel = Image.new("RGBA", spec["size"])
        # The inspected source has a full-height 97px blue mark, unlike Spain.
        panel.alpha_composite(original.crop((0, 0, 97, 126)).resize((64, 88), Image.Resampling.LANCZOS))
        draw = ImageDraw.Draw(panel)
        draw.rectangle((64, 0, 119, 87), fill=(39, 39, 39))
        draw.rectangle((120, 0, 163, 87), fill="white")
        draw.line((64, 44, 162, 44), fill=(198, 198, 198), width=1)
        draw.rectangle((0, 88, 69, 109), fill="white")
    elif profile == "italy":
        original = crop((475, 737, 956, 781))
        panel = Image.new("RGBA", spec["size"])
        bar_height = spec["bar_height"]
        panel.alpha_composite(original.resize((320, bar_height), Image.Resampling.LANCZOS))
        # Keep the actual source clock's diagonal edge and cyan colour.
        timer = crop((716, 458, 851, 504))
        panel.alpha_composite(timer.resize((80, 28), Image.Resampling.LANCZOS), (0, bar_height + 2))
    else:
        # The PC score tree verifies a horizontal home/score/score/away layout
        # and central emblem. The lion geometry comes from its owned header.
        logo = np.asarray(crop((712, 50, 782, 134))).copy()
        mask = ((logo[:, :, 0] < 110) & (logo[:, :, 1] < 70) &
                (logo[:, :, 2] < 130) & (logo[:, :, 3] > 128))
        if int(mask.sum()) < 300:
            raise ValueError("owned England lion mask is missing")
        logo[:, :, 3] = np.where(mask, logo[:, :, 3], 0)
        mark = Image.fromarray(logo).crop(Image.fromarray(logo).getbbox())
        mark.thumbnail((29, 34), Image.Resampling.LANCZOS)
        panel = Image.new("RGBA", spec["size"])
        draw = ImageDraw.Draw(panel)
        draw.rectangle((0, 0, 305, 39), fill=spec["ink"])
        draw.rectangle((92, 0, 131, 39), fill=(0, 255, 133))
        draw.rectangle((174, 0, 213, 39), fill=(0, 255, 133))
        draw.rectangle((132, 0, 173, 39), fill="white")
        draw.rectangle((108, 40, 197, 63), fill="white")
        panel.alpha_composite(mark, (153 - mark.width // 2, 20 - mark.height // 2))
    return panel, {"layout": spec["layout"], "main_plate_pixels": list(spec["size"]),
                   "source_crops": crops, "pc_animation_imported": False,
                   "team_text": "native selected-team UIR initials; no baked abbreviations"}


def patch_score(data, profile):
    """Keep v62 authored lifecycle, adapt all affected fields to the new cells."""
    spec = PROFILES[profile]
    authored, _ = v62.patch_movie(data)
    rows = placements(authored)
    initial = {r["depth"]: r for r in rows if r["parent"] == 28 and r["frame"] == 0}
    bottom = 20 + spec["size"][1]
    targets = {60: (6, 20), 13: (6, bottom + 6),
               63: spec["names"][0], 61: spec["names"][1],
               67: spec["scores"][0], 65: spec["scores"][1],
               77: spec["clock"], 78: spec["clock"],
               75: spec["kits"][0], 69: spec["kits"][1],
               56: (6, bottom + 6), 52: (100, bottom + 6),
               1: (202, bottom + 6), 7: (406, bottom + 6)}
    output = bytearray(authored)

    def write(row, field, fmt, values):
        if field + "_offset" in row:
            struct.pack_into("<" + fmt, output, row[field + "_offset"], *values)

    for row in rows:
        depth, parent = row["depth"], row["parent"]
        if parent == 28 and depth in targets:
            if "translate" in row:
                old = initial[depth]["translate"]
                target = targets[depth]
                delta = tuple((v - b) * SCALE for v, b in zip(row["translate"], old))
                # Clock digit selection moves internally between minute states.
                # Its outer native alpha lifecycle is enough for a short tab;
                # the tall v62 clock's vertical travel would cross that tab.
                if depth in (77, 78):
                    delta = (0, 0)
                if depth in (61, 63, 65, 67):
                    cells = spec["name_cells"] if depth in (61, 63) else spec["score_cells"]
                    cell = cells[0 if depth in (63, 67) else 1]
                    height = (26 if depth in (61, 63) else 32) * SCALE
                    delta = (delta[0], max(cell[1] - target[1], min(delta[1], cell[3] - height - target[1] - .05)))
                translated = [v + d for v, d in zip(target, delta)]
                if depth in (61, 63, 65, 67):
                    # Apply after the appearance envelope so every existing
                    # keyframe receives the same optical correction.
                    translated[1] += spec.get("text_y_offset", 0)
                write(row, "translate", "ii", [round(v * 20) for v in translated])
            if depth in (61, 63) and "scale" in row:
                # v62 narrows a 78px name field to 60px for Spain's column.
                # England has room for the full 78px field: undo that extra
                # horizontal squeeze before the common compact scale. Height
                # and the native UIR font/binding remain unchanged.
                width_ratio = spec.get("name_width", 60) / 60
                write(row, "scale", "ii", [round(row["scale"][0] * width_ratio * SCALE * 1024),
                                            round(row["scale"][1] * SCALE * 1024)])
            if depth in (65, 67) and "scale16" in row:
                write(row, "scale16", "hh", [round(v * SCALE * 32768) for v in row["scale16"]])
            if "mult8" in row and depth in (65, 67):
                alpha = int(row["mult8"][0]) & 255
                colour = int.from_bytes(bytes(spec["ink"]), "big")
                write(row, "mult8", "I", [(colour << 8) | alpha])
        # Clock uses a shared digit wrapper with no outer scale field. Scale
        # its existing text transform and all child spacing, including 100+.
        if parent in (17, 19, 20, 23, 24, 27) and "translate" in row:
            write(row, "translate", "ii", [round(v * SCALE * 20) for v in row["translate"]])
        if parent == 16 and "scale16" in row:
            write(row, "scale16", "hh", [round(v * SCALE * 32768) for v in row["scale16"]])
        if parent == 27 and "scale16" in row:
            write(row, "scale16", "hh", [round(v * SCALE * 32768) for v in row["scale16"]])
    patch_added_time(output, placements(bytes(output)), spec)
    return bytes(output), verify_geometry(placements(bytes(output)), spec)


def patch_added_time(output, rows, spec):
    """Use only the native conditional loss-time clip in the profile's cell.

    Depth 13 is the *ordinary* clock background, not an added-time on/off
    plate. It shares an image with plate_lossTime; moving its instance out of
    view preserves that image for the separately controlled loss-time clip.
    Tint the content wrapper as well as the bitmap atlas, because its dynamic
    UIR number is not an atlas glyph. Keep the white plate on a separate child.
    """
    initial = {(r["parent"], r["depth"]): r for r in rows if r["frame"] == 0}
    if (initial[(28, 56)].get("name") != "losstime" or
            initial[(24, 3)].get("name") != "losstime_contents" or
            initial[(24, 1)].get("name") != "plate_lossTime" or
            initial[(23, 2)].get("name") != "numbers"):
        raise ValueError("unsupported native loss-time hierarchy")
    for row in rows:
        parent, depth = row["parent"], row["depth"]
        if parent == 28 and depth == 13 and "translate" in row:
            struct.pack_into("<ii", output, row["translate_offset"], -256 * 20, -128 * 20)
        elif parent == 28 and depth == 56 and "translate" in row:
            # plate_lossTime's image child has the native (-2,-2) offset.
            cell=spec["added_time_cell"]
            struct.pack_into("<ii", output, row["translate_offset"], (cell[0]+2)*20, (cell[1]+2)*20)
        elif parent == 24 and depth == 3:
            if "translate" in row:
                struct.pack_into("<ii", output, row["translate_offset"], 5 * 20,
                                 round(row["translate"][1] * 20))
            if "mult8" in row:
                alpha = int(row["mult8"][0]) & 255
                # The next keyframe resets to white/full alpha without a
                # payload. Retain our black tint and finish this fade instead.
                if row["frame"] == 23:
                    alpha = 255
                struct.pack_into("<I", output, row["mult8_offset"], alpha)
            elif row["flags"] & 8:
                struct.pack_into("<I", output, row["offset"], row["flags"] & ~8)
        elif parent == 23 and depth == 2 and "translate" in row:
            struct.pack_into("<ii", output, row["translate_offset"], 14 * 20,
                             round(row["translate"][1] * 20))


def verify_geometry(rows, spec):
    cells = {63: spec["name_cells"][0], 61: spec["name_cells"][1],
             67: spec["score_cells"][0], 65: spec["score_cells"][1]}
    checks = []
    for row in rows:
        if row["parent"] != 28 or "translate" not in row:
            continue
        depth = row["depth"]
        x, y = row["translate"]
        if depth in (77, 78):
            cell = spec["clock_cell"]
            bounds = [(x + lo * SCALE, y + 4 * SCALE,
                       x + hi * SCALE, y + 28 * SCALE)
                      for lo, hi in ((32, 82.65), (24.65, 89.3), (18, 96))]
        elif depth in cells:
            cell = cells[depth]
            w, h = (spec.get("name_width", 60), 26) if depth in (61, 63) else (38, 32)
            bounds = [(x, y, x + w * SCALE, y + h * SCALE)]
        else:
            continue
        for bound in bounds:
            if not (cell[0] <= bound[0] and cell[1] <= bound[1] and
                    bound[2] <= cell[2] and bound[3] <= cell[3]):
                raise ValueError(f"native field leaves profile cell: depth={depth}, frame={row['frame']}, {bound}, {cell}")
        checks.append({"depth": depth, "frame": row["frame"], "bounds": bounds})
    if len(checks) < 60:
        raise ValueError("incomplete geometry coverage")
    if "added_time_cell" in spec:
        initial = {(r["parent"], r["depth"]): r for r in rows if r["frame"] == 0}
        root = initial[(28, 56)]["translate"]
        child = initial[(22, 1)]["translate"]
        left, top = (a + b for a, b in zip(root, child))
        cell = spec["added_time_cell"]
        clock = spec["clock_cell"]
        if (left, top, left + 48, top + 24) != cell:
            raise ValueError("added-time plate leaves its profile cell at the clock's right edge or lower band")
        if spec.get("added_time_relation")=="right":
            if cell[0]!=clock[2] or cell[1]+cell[3]!=clock[1]+clock[3]:
                raise ValueError("added-time plate does not abut the clock's right edge")
        elif cell[0]!=clock[0] or cell[1]<=clock[3]:
            raise ValueError("added-time plate does not occupy the reserved lower clock band")
        for row in rows:
            if row["parent"] == 28 and row["depth"] == 13 and "translate" in row:
                x, y = row["translate"]
                if x + SAFE_OFFSET[0] + 48 >= 0 or y + SAFE_OFFSET[1] + 24 >= 0:
                    raise ValueError("ordinary clock background would leave a visible blank plate")
    return {"checked_placement_updates": len(checks), "clock_minute_states": [1, 2, 3],
            "fields_inside_separate_cells": True, "clock_cell": list(spec["clock_cell"]), "checks": checks,
            **({"added_time_cell": list(spec["added_time_cell"]),
                "added_time_visibility": "native losstime clip; ordinary clock background instance offscreen",
                "added_time_ink": "black wrapper multiplier covers dynamic UIR and bitmap children",
                "name_field_pixels": spec.get("name_width",60) * SCALE,
                "text_optical_y_offset_pixels": spec.get("text_y_offset", 0),
                "text_optical_calibration": "user native-render direction; magnitude awaits Switch check"}
               if "added_time_cell" in spec else {})}


def patch_event(data, dy):
    """Translate complete native card/goal/substitution lifecycle as one stack."""
    rows = placements(data)
    main = next(r for r in rows if r["parent"] is None and r.get("name") == "main")
    parent = main["source"]
    top = [r for r in rows if r["parent"] == parent and r["frame"] == 0]
    if not top or any("translate" not in r for r in top):
        raise ValueError("event root has an unpositioned child; cannot safely relocate")
    output = bytearray(data)
    for row in rows:
        if row["parent"] == parent and "translate" in row:
            x, y = row["translate"]
            struct.pack_into("<ii", output, row["translate_offset"], round(x * 20), round((y + dy) * 20))
    return bytes(output)


def field_edit_report(before, after):
    """Fail closed unless every byte difference belongs to an exposed field."""
    a, b = placements(before), placements(after)
    if len(before) != len(after) or len(a) != len(b) or named_paths(a).keys() != named_paths(b).keys():
        raise ValueError("movie size/hierarchy changed")
    allowed = bytearray(len(before))
    edits = []
    flag_changes = []
    native_loss_contents = (
        any(r.get("name") == "losstime" and r.get("source") == 24 and r["parent"] == 28 for r in a)
        and any(r.get("name") == "losstime_contents" and r["parent"] == 24 and r["depth"] == 3 for r in a))
    fields = (("translate", 8), ("scale", 8), ("scale16", 4), ("mult8", 4))
    for old, new in zip(a, b):
        for key in ("parent", "depth", "source", "frame", "object_id", "name"):
            if old.get(key) != new.get(key):
                raise ValueError("native event identity/flags changed")
        if old["flags"] != new["flags"]:
            # Only the added-time content's payload-less white colour reset
            # may be disabled. No hierarchy, update/source or payload bits may
            # change, and the native white background is never tinted.
            if not native_loss_contents or (old["parent"], old["depth"], old["frame"]) != (24, 3, 24) or (
                    old["flags"] ^ new["flags"]) != 8 or new["flags"] & 8 or any(
                    field in old for field in ("mult8", "mult16", "add8", "add16")):
                raise ValueError("unapproved native placement flag change")
            offset = old["offset"]
            allowed[offset:offset + 4] = b"\1" * 4
            flag_changes.append(dict(parent=24, depth=3, frame=24, offset=offset,
                                     before=old["flags"], after=new["flags"],
                                     reason="retain readable added-time tint at opaque keyframe"))
        for field, size in fields:
            if field not in old or old[field] == new[field]:
                continue
            offset = old[field + "_offset"]
            allowed[offset:offset + size] = b"\1" * size
            edits.append(dict(parent=old["parent"], depth=old["depth"], frame=old["frame"], field=field,
                              offset=offset, before=before[offset:offset + size].hex(), after=after[offset:offset + size].hex()))
    if any(x != y and not allowed[i] for i, (x, y) in enumerate(zip(before, after))):
        raise ValueError("movie changed outside verified placement fields")
    return {"edits": edits, "scripts_labels_frames_bindings_identical": True,
            "scripts_labels_frames_bindings_flags_identical": not flag_changes,
            "placement_flag_changes": flag_changes,
            "pc_animation_imported": False}


def repack(mobile, panel, ink, profile=None):
    atlas, regions, (base, _, _, _) = read_atlas(mobile)
    w, h = struct.unpack_from(">HH", atlas, 16)
    if (w, h) != (1024, 512):
        raise ValueError("unsupported Mobile atlas")
    pixels = np.frombuffer(atlas[64:], np.uint8).reshape(h, w, 4).copy()
    output = bytearray(mobile)
    table = struct.unpack_from(">I", output, base + 40)[0]
    changed_names = []

    def mapping(index, bounds):
        l, t, r, b = bounds
        struct.pack_into(">5H", output, base + table + index * 10, 0, l * 2 + 1, t * 2 + 1, r * 2 - 1, b * 2 - 1)

    dest = (*v62.ATLAS_DESTINATION, v62.ATLAS_DESTINATION[0] + panel.width, v62.ATLAS_DESTINATION[1] + panel.height)
    for i, region in enumerate(regions):
        l, t, r, b = region_bounds(region)
        if region["name"] != "game2dPes-score-plateMain" and l < dest[2] and r > dest[0] and t < dest[3] and b > dest[1]:
            raise ValueError("profile destination overlaps a live region")
    if pixels[dest[1]:dest[3], dest[0]:dest[2], 0].any():
        raise ValueError("profile destination alpha is occupied")
    for i, region in enumerate(regions):
        name = region["name"]
        l, t, r, b = region_bounds(region)
        if name == "game2dPes-score-plateMain":
            pixels[dest[1]:dest[3], dest[0]:dest[2]] = np.asarray(panel)[:, :, [3, 0, 1, 2]]
            mapping(i, dest)
        elif name == "game2dPes-score-plateTime":
            # This image is shared by the ordinary clock and conditional
            # loss-time clip. England suppresses only the former instance.
            plate_width = 48 if profile == "england" else 70
            pixels[t:t + 24, l:l + plate_width] = (255, 255, 255, 255)
            mapping(i, (l, t, l + plate_width, t + 24))
        elif name.startswith("MatchPlate-texFont-") or name.startswith("game2dPes-score-plateTeamColor-"):
            tile = Image.fromarray(pixels[t:b, l:r][:, :, [1, 2, 3, 0]])
            tile = tile.resize((max(1, round(tile.width * SCALE)), max(1, round(tile.height * SCALE))), Image.Resampling.LANCZOS)
            rgba = np.asarray(tile).copy()
            if name.startswith("MatchPlate-"):
                rgba[:, :, :3] = ink
            pixels[t:t + tile.height, l:l + tile.width] = rgba[:, :, [3, 0, 1, 2]]
            mapping(i, (l, t, l + tile.width, t + tile.height))
        else:
            continue
        changed_names.append(name)
    expected = atlas[:64] + pixels.tobytes()
    output = replace_atlas(bytes(output), expected, candidate_limit=4)
    checked, after, _ = read_atlas(output)
    if checked != expected:
        raise ValueError("atlas roundtrip mismatch")
    for old, new in zip(regions, after):
        if old["name"] not in changed_names and old != new:
            raise ValueError("unrelated atlas mapping changed")
    return output, {"dimensions": [w, h], "decoded_bytes": len(atlas),
                    "changed_regions": changed_names, "unrelated_region_mappings_identical": True}


def build_profile(mobile, owned, profile):
    spec = PROFILES[profile]
    if digest(mobile) != v62.MOBILE_SHA256 or digest(owned) != spec["sha256"]:
        raise ValueError("profile input differs from pinned owned revision")
    panel, design = panel_for(profile, owned)
    movies = read_movies(mobile)
    changed = bytearray(mobile)
    reports = {}
    board_bottom = 32 + panel.height
    event_top = board_bottom + 40
    dy = event_top - EVENT_OLD_TOP
    for movie in movies:
        if movie.name == "game2d_score":
            new, geometry = patch_score(movie.data, profile)
        elif movie.name in ("game2d_memberChange", "game2d_goal", "game2d_card"):
            new = patch_event(movie.data, dy)
        else:
            continue
        reports[movie.name] = field_edit_report(movie.data, new)
        changed[movie.offset:movie.offset + movie.size] = swap_fields(new, movie.info)
    changed, atlas = repack(bytes(changed), panel, spec["ink"], profile)
    after = read_movies(changed)
    for old, new in zip(movies, after):
        if old.name != new.name or old.info != new.info:
            raise ValueError("movie identity/descriptor changed")
        if old.name not in reports and old.data != new.data:
            raise ValueError("unrelated movie changed")
        if old.name in reports:
            field_edit_report(old.data, new.data)
    source, target = txp(mobile), txp(changed)
    packet = HEADER.pack(b"NXSB01\0\0", len(source), len(target), checksum(source), checksum(target)) + target
    if len(packet) > 2_000_000:
        raise ValueError("profile exceeds unchanged runtime theme limit")
    report = dict(schema_version=1, profile=profile, league_key=spec["key"],
                  classification="source-backed authored Mobile adaptation; native playback unverified",
                  source_mobile_sha256=digest(mobile), source_fl26_sha256=digest(owned),
                  packet_bytes=len(packet), packet_sha256=digest(packet),
                  source_txp_bytes=len(source), source_txp_checksum=f"{checksum(source):016x}",
                  design=design, atlas=atlas, field_geometry=geometry, native_movies=reports,
                  safe_physical_anchor=[38, 32], main_plate_bottom_physical=board_bottom,
                  auxiliary_band_physical=[board_bottom + 6, board_bottom + 38],
                  event_top_physical=event_top, event_translate_delta_y=dy,
                  event_motion="native enter unfold, staged content reveal, member swap and exit alpha preserved",
                  scoreboard_motion="authored Mobile vertical reveal/stagger scaled to compact field cells",
                  pc_animation_imported=False, device_validated=False, production_mutated=False,
                  remaining_proof=["native team/font and clock digit appearance", "goal/replay/card/substitution lifecycle",
                                   "added-time/aggregate/100+ minutes/penalties", "next-match restoration and device timing"])
    return changed, packet, panel, report


def preview(panel, profile, report):
    """Static host composition at the actual 1280x720 target size."""
    spec = PROFILES[profile]
    im = Image.new("RGBA", (1280, 720), (51, 95, 65, 255))
    draw = ImageDraw.Draw(im)
    draw.line((0, 360, 1280, 360), fill=(130, 155, 130), width=2)
    draw.ellipse((510, 230, 770, 490), outline=(130, 155, 130), width=2)
    im.alpha_composite(panel, (38, 32))
    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 17)
    small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14)
    for point, text in zip(spec["names"], ("BAR", "RMA") if profile == "spain" else ("HOM", "AWY")):
        draw.text((point[0] + 32 + spec.get("name_width", 60) * SCALE / 2,
                   point[1] + 20.5 + spec.get("text_y_offset", 0)), text, anchor="mm", fill="white", font=font)
    for point in spec["scores"]:
        draw.text((point[0] + 44.5, point[1] + 22.5 + spec.get("text_y_offset", 0)),
                  "0", anchor="mm", fill=spec["ink"], font=font)
    cell = spec["clock_cell"]
    draw.text(((cell[0] + cell[2]) / 2 + 32, (cell[1] + cell[3]) / 2 + 12),
              "102:08", anchor="mm", fill=spec["ink"], font=font)
    bottom = report["main_plate_bottom_physical"]
    if "added_time_cell" in spec:
        l, t, r, b = spec["added_time_cell"]
        draw.rectangle((l + 32, t + 12, r + 31, b + 11), fill="white")
        draw.text(((l + r) / 2 + 32, (t + b) / 2 + 12), "+4", anchor="mm", fill="black", font=font)
    else:
        draw.rectangle((38, bottom + 6, 108, bottom + 30), fill="white")
        draw.text((73, bottom + 18), "+4", anchor="mm", fill=spec["ink"], font=font)
    y = report["event_top_physical"]
    draw.rectangle((38, y, 422, y + 68), fill=(25, 25, 90, 230))
    draw.text((52, y + 17), "12  Native player leaving", fill="white", font=font, anchor="lm")
    draw.text((52, y + 51), "  1  Native player entering", fill="white", font=font, anchor="lm")
    draw.polygon(((392, y + 10), (382, y + 26), (402, y + 26)), fill=(110, 255, 0))
    draw.polygon(((382, y + 44), (402, y + 44), (392, y + 60)), fill=(255, 70, 30))
    draw.text((32, 655), f"{profile.upper()} / 1280x720 HOST GEOMETRY COMPOSITION / SAMPLE TEXT", font=small, fill="white")
    draw.text((32, 679), "Authored Mobile adaptation. Native event/digit playback remains unverified.", font=small, fill="white")
    return im


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mobile", type=Path, required=True)
    parser.add_argument("--pc-source-dir", type=Path, required=True)
    parser.add_argument("--profiles", nargs="+", choices=PROFILES, default=list(PROFILES))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or "local-debug" not in args.output.resolve().parts:
        raise ValueError("output must be a new ignored local-debug directory")
    mobile = load_owned(args.mobile)
    args.output.mkdir(parents=True)
    manifest = {"schema_version": 1, "packets": [], "pc_animation_imported": False,
                "device_validated": False, "production_mutated": False}
    sheet = Image.new("RGBA", (640, 180 * len(args.profiles)), (40, 70, 50))
    for i, profile in enumerate(args.profiles):
        spec = PROFILES[profile]
        owned = load_owned(args.pc_source_dir / ("game2d" + spec["source"] + ".bin"))
        changed, packet, panel, report = build_profile(mobile, owned, profile)
        folder = args.output / profile
        folder.mkdir()
        file = folder / f"c{spec['key']}.nxsb"
        file.write_bytes(packet)
        (folder / "game2dPes-candidate.bin").write_bytes(changed)
        panel.save(folder / "plate.png")
        preview(panel, profile, report).save(folder / "preview-host-1280x720.png")
        (folder / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        draw = ImageDraw.Draw(sheet)
        draw.text((20, i * 180 + 12), profile.upper() + " / host sample geometry", fill="white")
        sheet.alpha_composite(preview(panel, profile, report).crop((26, 24, 486, 164)), (20, i * 180 + 34))
        manifest["packets"].append(dict(archive_path=f"scoreboards/c{spec['key']}.nxsb", file=str(file.resolve()),
                                        bytes=len(packet), sha256=digest(packet), profile=profile,
                                        validation=str((folder / "validation.json").resolve()),
                                        preview=str((folder / "preview-host-1280x720.png").resolve())))
        print(json.dumps({"profile": profile, "packet_bytes": len(packet), "sha256": digest(packet)}), flush=True)
    sheet.save(args.output / "profiles-host-sheet.png")
    (args.output / "SCOREBOARD-PACKETS.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

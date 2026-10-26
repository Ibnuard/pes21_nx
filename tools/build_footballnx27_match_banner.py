"""Recolour the native animated lower match banner without replacing scripts.

Input/output game-derived containers and NXSB packets must remain ignored.
All other movies (including each competition's top scorebar) stay exact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from afp_score_layout import placements, read_movies, swap_fields, strings
from afp_texture_patch import read_atlas, replace_atlas
from build_efootball10_scoreboard_v2 import region_bounds
from build_footballnx27_scoreboard import HEADER, INK, BLUE, RED, WHITE, txp
from pack_runtime_assets import checksum, read_archive, pack_entries

MOVIE = "game2d_scoreDemo"
MOVIE_SHA256 = "06b3d078226ff969c10b5cb69e941c1420d4e932b88d113a5c5f2a60917c88af"
PLATE = "game2dPes-scoreDemo-plate-half"
TEXT_DEPTHS = (16, 18, 20, 22, 24, 26, 28)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def half_plate():
    """Authored half, mirrored by the existing native two-image timeline."""
    image = Image.new("RGBA", (562, 128), WHITE + (255,))
    return image


def image_imports(data):
    """Read exact root AP2 image bindings and their exported dimensions."""
    names=strings(data)
    base=struct.unpack_from("<I",data,36)[0]
    _,_,_,count,_,_,table=struct.unpack_from("<HHIIIII",data,base)
    cursor=base+table
    result={}
    for _ in range(count):
        word=struct.unpack_from("<I",data,cursor)[0]
        code,size=word>>22,word&0x3fffff
        if code==0x83:
            flags,source,name,w,h=struct.unpack_from("<I4H",data,cursor+4)
            if flags!=40 or size!=12:raise ValueError("unsupported native image import")
            result[source]={"name":names[name].replace("_","-"),"exported_size":[w,h]}
        cursor+=4+(size+3)//4*4
    return result


def geometry(data):
    """Native UIR template bounds, after the title's 3:2 export conversion."""
    unit=200/3
    rows=placements(data)
    initial={(r["parent"],r["depth"]):r for r in rows if r["frame"]==0}
    result={}
    for name,depth in (("home_crest",12),("away_crest",14),("home_score",16),
                       ("away_score",18),("competition",20)):
        r=initial[(22,depth)];sx,sy=r.get("scale",r.get("scale16",(1,1)));x,y=r["translate"]
        result[name]=[x,y,x+sx*unit,y+sy*unit]
    for name,depth,parent in (("home_name",22,16),("away_name",24,17)):
        x,y=initial[(22,depth)]["translate"];sx,sy=initial[(parent,1)]["scale"]
        result[name]=[x,y,x+sx*unit,y+sy*unit]
    return result


def patch_movie(data):
    if digest(data) != MOVIE_SHA256:
        raise ValueError("lower banner is not the pinned native revision")
    rows = placements(data)
    initial = {r["depth"]: r for r in rows if r["parent"] == 22 and r["frame"] == 0}
    names = {12: "emblem_home", 14: "emblem_away", 16: "score_home",
             18: "score_away", 20: "competitionName", 22: "teamName_home",
             24: "teamName_away", 4: "vi"}
    if len(rows) != 709 or any(initial[d].get("name") != n for d, n in names.items()):
        raise ValueError("unexpected native lower-banner hierarchy")
    out = bytearray(data)
    mask = bytearray(len(data))
    edits = []
    selected = [r for r in rows if r["parent"] == 22 and r["depth"] in TEXT_DEPTHS]
    for r in selected:
        rgb = INK
        if any(k in r for k in ("add8", "add16", "mult16")):
            raise ValueError("unsupported banner colour transform")
        if "mult8" in r:
            off = r["mult8_offset"]
            alpha = int(r["mult8"][0]) & 255
            # Native payload-less colour resets promote the entry fade to full
            # white. Retain the authored colour through that reset; complete
            # its preceding final fade step at full alpha, as the scorebar does.
            following = [n for n in selected if n["parent"] == r["parent"] and
                         n["depth"] == r["depth"] and n["frame"] == r["frame"] + 1]
            if any(n["flags"] & 8 and "mult8" not in n for n in following):
                alpha = 255
            value = int.from_bytes(bytes((*rgb, alpha)), "big")
            struct.pack_into("<I", out, off, value)
            mask[off:off + 4] = b"\1" * 4
            edits.append(dict(parent=r["parent"], depth=r["depth"], frame=r["frame"],
                              offset=off, field="mult8", alpha=alpha))
        elif r["flags"] & 8:
            off = r["offset"]
            struct.pack_into("<I", out, off, r["flags"] & ~8)
            mask[off:off + 4] = b"\1" * 4
            edits.append(dict(parent=r["parent"], depth=r["depth"], frame=r["frame"],
                              offset=off, field="retain_colour_at_native_reset"))
    if any(a != b and not mask[i] for i, (a, b) in enumerate(zip(data, out))):
        raise ValueError("banner changed outside bounded colour fields")
    if len(placements(bytes(out))) != len(rows):
        raise ValueError("placement count changed")
    return bytes(out), {"movie": MOVIE, "placements": len(rows), "edits": edits,
                        "native_transforms_and_scripts_exact": True,
                        "native_entry_hold_exit_retained": True,
                        "external_wave_shapes_retained": True}


def build(container):
    movies = read_movies(container)
    movie = next(m for m in movies if m.name == MOVIE)
    patched, report = patch_movie(movie.data)
    changed = bytearray(container)
    changed[movie.offset:movie.offset + movie.size] = swap_fields(patched, movie.info)
    atlas, regions, _ = read_atlas(bytes(changed))
    width, height = struct.unpack_from(">HH", atlas, 16)
    pixels = np.frombuffer(atlas[64:], np.uint8).reshape(height, width, 4).copy()
    region = next(r for r in regions if r["name"] == PLATE)
    l, t, right, b = region_bounds(region)
    if (right-l, b-t) != (562, 128):
        raise ValueError("unexpected lower plate size")
    pixels[t:b, l:right] = np.asarray(half_plate())[:, :, [3, 0, 1, 2]]
    updated = atlas[:64] + pixels.tobytes()
    output = replace_atlas(bytes(changed), updated, candidate_limit=4)
    after = read_movies(output)
    for old, new in zip(movies, after):
        if (old.name, old.info, old.size) != (new.name, new.info, new.size):
            raise ValueError("movie table changed")
        if old.name != MOVIE and old.data != new.data:
            raise ValueError("unrelated movie changed")
    report.update(protected_movies={m.name: digest(m.data) for m in movies if m.name != MOVIE},
                  movie_sha256=digest(patched), atlas_region=region,
                  native_geometry=geometry(patched),native_image_imports=image_imports(patched),
                  source_sha256=digest(container), output_sha256=digest(output))
    return output, report


def patch_packet(packet):
    if len(packet) < HEADER.size:
        raise ValueError("truncated NXSB packet")
    magic, source_size, size, source_hash, target_hash = HEADER.unpack_from(packet)
    target = packet[HEADER.size:]
    if magic != b"NXSB01\0\0" or size != len(target) or checksum(target) != target_hash:
        raise ValueError("invalid NXSB target binding")
    if txp(target) != target:
        raise ValueError("NXSB target envelope mismatch")
    output, report = build(target)
    payload = txp(output)
    return HEADER.pack(magic, source_size, len(payload), source_hash, checksum(payload)) + payload, report


def default_packet(container):
    output, report = build(container)
    before, after = txp(container), txp(output)
    return HEADER.pack(b"NXSB01\0\0", len(before), len(after), checksum(before), checksum(after)) + after, report


def repack_archive(original, packets, output):
    """Bind every current theme; prove every unrelated archive member exact."""
    _,before=read_archive(original)
    old={name for name in before if name.startswith("scoreboards/")}
    supplied={"scoreboards/"+p.name.lower():p.read_bytes() for p in packets.glob("*.nxsb")}
    required=old|{"scoreboards/c0.nxsb","scoreboards/banner-textures.nxsb"}
    if set(supplied)!=required:
        raise ValueError("packet cohort must contain every current theme plus c0 and shared waves")
    members=dict(before)
    members.update(supplied)
    pack_entries(members,output)
    _,after=read_archive(output)
    changed={n for n in before if before[n]!=after[n]}
    if changed!=old or set(after)-set(before)!={"scoreboards/c0.nxsb","scoreboards/banner-textures.nxsb"}:
        raise ValueError("unexpected archive member delta")
    exact={n:digest(v) for n,v in before.items() if n not in old}
    if any(digest(after[n])!=h for n,h in exact.items()):
        raise ValueError("unrelated archive payload changed")
    return {"baseline_sha256":digest(original.read_bytes()),"bytes":output.stat().st_size,
            "sha256":digest(output.read_bytes()),"changed_members":sorted(changed),
            "added_members":sorted(set(after)-set(before)),"protected_members":exact,
            "protected_members_count":len(exact),"packet_members":len(supplied)}


def timeline_state(movie, parent, depth, frame):
    state = {"translate": (0, 0), "scale": (1, 1), "mult8": (0xFFFFFFFF,)}
    for row in placements(movie):
        if row["parent"] != parent or row["depth"] != depth or row["frame"] > frame:
            continue
        for key in ("translate", "scale", "scale16", "mult8"):
            if key in row:
                state["scale" if key == "scale16" else key] = row[key]
        if row["flags"] & 8 and "mult8" not in row:
            state["mult8"] = (0xFFFFFFFF,)
    return state


def preview(container, background, frame, label="Exhibition", home="Manchester United", away="FC Barcelona", waves=None):
    """Host layout proof using actual patched plate/timeline, sample native data.

    Native wave pixels and placement/opacity tracks are sampled directly.
    UIR font rasterization and actual crest assets are not emulated.
    """
    movie = next(m for m in read_movies(container) if m.name == MOVIE).data
    imports=image_imports(movie)
    boxes=geometry(movie)
    canvas = background.convert("RGBA").resize((1280, 720))
    panel = Image.new("RGBA", (1124, 128))
    part = half_plate()
    opacity = int(timeline_state(movie, 22, 1, frame)["mult8"][0]) & 255
    part.putalpha(opacity)
    panel.alpha_composite(part, (0, 0))
    panel.alpha_composite(part.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (562, 0))
    text_layer=Image.new("RGBA",panel.size)
    # The imported wave raster and its exact native timeline track are used.
    for depth in range(1, 7):
        state = timeline_state(movie, 15, depth, frame)
        value = int(state["mult8"][0])
        if waves is None:
            continue
        source=next(r["source"] for r in placements(movie) if r["parent"]==15 and r["depth"]==depth and r["frame"]==0)
        imported=imports[source]
        image = waves[imported["name"]].copy()
        sx,sy = state["scale"]
        image = image.resize((round(image.width*abs(sx)),round(image.height*abs(sy))),Image.Resampling.BICUBIC)
        alpha = np.asarray(image.getchannel("A"),np.uint32)*(value&255)*opacity//(255*255)
        image.putalpha(Image.fromarray(alpha.astype(np.uint8)))
        x,y = state["translate"]
        panel.alpha_composite(image,(round(x),round(y)))
    d = ImageDraw.Draw(text_layer)
    font_path = Path("C:/Windows/Fonts/arialbd.ttf")
    font = ImageFont.truetype(str(font_path), 26)
    small = ImageFont.truetype(str(font_path), 20)
    score = ImageFont.truetype(str(font_path), 43)
    for depth, text, box, face in ((22,home,boxes["home_name"],font),
            (24,away,boxes["away_name"],font), (16,"2",boxes["home_score"],score),
            (18,"1",boxes["away_score"],score), (20,label,boxes["competition"],small)):
        state = timeline_state(movie, 22, depth, frame)
        value = int(state["mult8"][0])
        colour = tuple((value >> shift) & 255 for shift in (24,16,8,0))
        position=((box[0]+box[2])/2,(box[1]+box[3])/2)
        d.text(position, text, font=face, fill=colour, anchor="mm")
    # Clearly authored crest proxies avoid pretending to render native emblems.
    for key, letter, colour in (("home_crest","H",RED),("away_crest","A",BLUE)):
        box=boxes[key];cx,cy=(box[0]+box[2])/2,(box[1]+box[3])/2
        # These are equal-bounds proxy marks, not rectangular replacements
        # for actual native transparent crest silhouettes.
        d.ellipse((cx-32,cy-32,cx+32,cy+32), fill=colour+(opacity,))
        d.text((cx,cy),letter,font=font,fill=WHITE+(opacity,),anchor="mm")
    panel.alpha_composite(text_layer)
    canvas.alpha_composite(panel, (78,548))
    return canvas.convert("RGB")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mobile", type=Path, required=True)
    p.add_argument("--packets", type=Path, help="directory of current NXSB packets")
    p.add_argument("--background", type=Path)
    p.add_argument("--wave-packet",type=Path,help="validated banner-textures.nxsb for actual wave preview")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    original = a.mobile.read_bytes()
    packet, report = default_packet(original)
    (a.output / "c0.nxsb").write_bytes(packet)
    reports = {"c0.nxsb": report}
    if a.packets:
        for path in sorted(a.packets.glob("*.nxsb")):
            if path.name.lower() == "c0.nxsb":
                raise ValueError("input already has c0; choose an explicit unmodified baseline")
            packet, report = patch_packet(path.read_bytes())
            (a.output / path.name).write_bytes(packet)
            reports[path.name] = report
    if a.background:
        from build_footballnx27_banner_textures import wave_images
        waves = wave_images(a.wave_packet.read_bytes()[HEADER.size:]) if a.wave_packet else None
        image = Image.open(a.background)
        target = (a.output / "c0.nxsb").read_bytes()[HEADER.size:]
        for frame, name in ((20,"entry"),(70,"hold"),(105,"exit")):
            preview(target, image, frame,waves=waves).save(a.output / f"preview-{name}.png")
        preview(target,image,70,"UEFA CHAMPIONS LEAGUE",waves=waves).save(a.output / "preview-cup.png")
    (a.output / "REPORT.json").write_text(json.dumps(reports,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"packets":len(reports),"output":str(a.output)}))


if __name__ == "__main__":
    main()

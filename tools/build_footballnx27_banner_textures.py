"""Recolour the six shared native wave regions; alpha/other pixels stay exact.

Requires the user's ignored Mobile licenceTexturePes.bin. Output is game-
derived and remains local. The shared waves also appear in other native UI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image

from afp_texture_patch import lzss_decode, lzss_encode
from build_efootball10_scoreboard_v2 import region_bounds
from build_footballnx27_scoreboard import HEADER, BLUE, RED, txp
from pack_runtime_assets import checksum

SOURCE_SHA256 = "2df762f75ce06da456d86eea057c0e3384619f7b78066b9b0b426476af4ccc06"
WAVE_STRENGTHS = (1.0,.55,.22,1.0,.55,.22)
# Proven import/depth order: blue0/1/2 at right, red3/4/5 at left.
WAVES = {f"hudTexPes-waves-{i}": BLUE if i < 3 else RED for i in range(6)}


def wave_rgb(name,width,height):
    """Three ribbon depths, strongest at the outside and white near text.

    Grade only RGB within the existing masks; native alpha/motion stay exact.
    No extra image, material, draw or texture lookup is added at runtime.
    """
    index=int(name.rsplit("-",1)[1])
    outer=np.linspace(0,1,width,dtype=np.float64)
    if index>=3:outer=1-outer
    # A smooth transition avoids a vertical seam in the slanted native masks.
    t=np.clip((outer-.12)/.66,0,1)
    ramp=t*t*(3-2*t)
    strength=WAVE_STRENGTHS[index]*(.25+.75*ramp)
    brand=np.asarray(WAVES[name],np.float64)
    rgb=np.rint(255+(brand-255)*strength[:,None]).astype(np.uint8)
    return np.broadcast_to(rgb[None,:,:],(height,width,3))


def read(data):
    base = data.index(b"TXP2")
    payload = data[base:base + struct.unpack_from(">I", data, base+12)[0]]
    if struct.unpack_from(">II",payload,16) != (108,0x37fdf):
        raise ValueError("unsupported wave TXP2 schema")
    count, table = struct.unpack_from(">II",payload,24)
    if count != 2 or not struct.unpack_from(">I",payload,20)[0] & 4:
        raise ValueError("expected two legacy-compressed native atlases")
    images, textures = [], []
    for index in range(count):
        name, length, offset = struct.unpack_from(">III",payload,table+12*index)
        size, packed = struct.unpack_from(">II",payload,offset)
        if packed+8 != length or offset+length > len(payload):
            raise ValueError("invalid wave atlas range")
        atlas = lzss_decode(payload[offset+8:offset+length],size)
        w,h = struct.unpack_from(">HH",atlas,16)
        if atlas[:4] != b"TXDT" or len(atlas) != 64+w*h*4:
            raise ValueError("unsupported wave atlas format")
        images.append(atlas)
        textures.append((name,length,offset))
    count, region_table, names = struct.unpack_from(">III",payload,36)
    if count != 10 or struct.unpack_from(">I",payload,names+16)[0] != count:
        raise ValueError("unsupported wave region table")
    names_table = struct.unpack_from(">I",payload,names+24)[0]
    regions = [None]*count
    for i in range(count):
        _, index, name = struct.unpack_from(">III",payload,names_table+i*12)
        raw = payload[name:payload.index(b"\0",name)]
        if raw[0] >= 0xa0:
            raw = bytes((v+128)&255 for v in raw)
        rect = struct.unpack_from(">5H",payload,region_table+index*10)
        regions[index] = {"name":raw.decode("ascii"),"rect":rect}
    if set(WAVES) - {r["name"] for r in regions}:
        raise ValueError("missing native wave region")
    return base,payload,table,images,textures,regions


def wave_images(data):
    _,_,_,atlases,_,regions = read(data)
    result = {}
    for region in regions:
        if region["name"] not in WAVES:
            continue
        atlas = atlases[region["rect"][0]]
        w,h = struct.unpack_from(">HH",atlas,16)
        pixels = np.frombuffer(atlas[64:],np.uint8).reshape(h,w,4)
        l,t,r,b = region_bounds(region)
        result[region["name"]] = Image.fromarray(pixels[t:b,l:r][:,:,[1,2,3,0]])
    return result


def build(data):
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError("requires the pinned native shared wave texture input")
    base,payload,table,atlases,textures,regions = read(data)
    updated,report = [],[]
    for index,atlas in enumerate(atlases):
        w,h = struct.unpack_from(">HH",atlas,16)
        before = np.frombuffer(atlas[64:],np.uint8).reshape(h,w,4)
        after = before.copy()
        mask = np.zeros((h,w),bool)
        for region in regions:
            if region["rect"][0] != index or region["name"] not in WAVES:
                continue
            l,t,r,b = region_bounds(region)
            after[t:b,l:r,1:] = wave_rgb(region["name"],r-l,b-t)
            mask[t:b,l:r] = True
            wave_index=int(region["name"].rsplit("-",1)[1])
            report.append(dict(region=region,brand_colour=WAVES[region["name"]],
                               maximum_brand_strength=WAVE_STRENGTHS[wave_index],
                               inner_strength=WAVE_STRENGTHS[wave_index]*.25,
                               alpha_sha256=hashlib.sha256(before[t:b,l:r,0].tobytes()).hexdigest()))
        if not np.array_equal(before[:,:,0],after[:,:,0]) or not np.array_equal(before[~mask],after[~mask]):
            raise ValueError("wave alpha or unrelated pixels changed")
        updated.append(atlas[:64]+after.tobytes())
    if {row["region"]["name"] for row in report} != set(WAVES) or len(report) != 6:
        raise ValueError("all six native wave regions must be recoloured")
    # These two compressed atlases are the terminal payloads. Keep the entire
    # preceding import/region metadata exact, except size/offset table words.
    first = min(t[2] for t in textures)
    if max(t[2]+t[1] for t in textures) > len(payload) or len(payload)-max(t[2]+t[1] for t in textures) > 3:
        raise ValueError("wave textures are not terminal")
    out = bytearray(payload[:first])
    for index,atlas in enumerate(updated):
        out.extend(b"\0"*((-len(out))%4))
        offset = len(out)
        packed = lzss_encode(atlas,candidate_limit=4)
        blob = struct.pack(">II",len(atlas),len(packed))+packed
        out.extend(blob)
        struct.pack_into(">III",out,table+index*12,textures[index][0],len(blob),offset)
    struct.pack_into(">I",out,12,len(out))
    parsed = read(bytes(out))
    if parsed[3] != updated or parsed[5] != regions:
        raise ValueError("shared wave atlas roundtrip failed")
    target = bytes(out)
    packet = HEADER.pack(b"NXSB01\0\0",len(payload),len(target),checksum(payload),checksum(target))+target
    if len(packet) > 2_000_000:
        raise ValueError("wave packet exceeds existing runtime transport bound")
    return packet,{"source_sha256":SOURCE_SHA256,"source_txp_bytes":len(payload),
                   "target_txp_bytes":len(target),"packet_sha256":hashlib.sha256(packet).hexdigest(),
                   "regions":report,"all_alpha_exact":True,"all_other_pixels_exact":True,
                   "ribbon_strengths":WAVE_STRENGTHS,
                   "rgb_gradient":"smooth outside-to-centre depth; exact native alpha",
                   "shared_native_wave_uses_rebranded":True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    packet,report=build(a.input.read_bytes())
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_bytes(packet)
    a.output.with_suffix(".json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"bytes":len(packet),"sha256":report["packet_sha256"]}))


if __name__=="__main__":
    main()

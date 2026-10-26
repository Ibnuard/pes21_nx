"""Restore native rounded banner alpha and give its smaller title breathing room.

Operates on explicit ignored, owned v89 NXSB/archive inputs. No native script,
wave animation, shared wave texture, scorebar or runtime source is replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image,ImageDraw,ImageFont

from afp_score_layout import placements,read_movies,swap_fields
from afp_texture_patch import read_atlas,replace_atlas
from build_efootball10_scoreboard_v2 import region_bounds
from build_footballnx27_scoreboard import HEADER,MOBILE_SHA256,txp,INK,WHITE,RED,BLUE
from build_footballnx27_match_banner import MOVIE,PLATE,geometry,timeline_state,image_imports
from build_footballnx27_banner_textures import wave_images
from pack_runtime_assets import read_archive,pack_entries,checksum

V89_MOVIE_SHA256="6fe17b52fddc068212d65a6c796f8862155d4cb728342161ebda92a2357d10d3"
V89_ASSETS_SHA256="3b1b0c12e80fd818f2d18caa172d173bdba38a49432daed65a4d2f0bcf47e250"
TITLE_SCALE_Y=277/1024
TITLE_DY=12


def digest(value):return hashlib.sha256(value).hexdigest()


def plate_pixels(container):
    atlas,regions,_=read_atlas(container)
    w,h=struct.unpack_from(">HH",atlas,16)
    pixels=np.frombuffer(atlas[64:],np.uint8).reshape(h,w,4)
    region=next(r for r in regions if r["name"]==PLATE)
    l,t,r,b=region_bounds(region)
    if (r-l,b-t)!=(562,128):raise ValueError("unsupported native lower-banner plate")
    return pixels[t:b,l:r].copy(),(atlas,regions,pixels,(l,t,r,b))


def native_plate(native):
    if digest(native)!=MOBILE_SHA256:raise ValueError("requires the pinned original native UI")
    pixels,_=plate_pixels(native)
    image=Image.new("RGBA",(562,128),WHITE+(255,))
    image.putalpha(Image.fromarray(pixels[:,:,0]))
    return image


def patch_movie(data):
    if digest(data)!=V89_MOVIE_SHA256:raise ValueError("requires the accepted v89 lower movie")
    rows=placements(data)
    initial=next(r for r in rows if r["parent"]==22 and r["depth"]==20 and r["frame"]==0)
    if initial.get("name")!="competitionName":raise ValueError("unsupported title binding")
    output=bytearray(data);allowed=bytearray(len(data));edits=[]
    for row in rows:
        if (row["parent"],row["depth"])!=(22,20):continue
        if "translate" in row:
            x,y=row["translate"];off=row["translate_offset"]
            struct.pack_into("<ii",output,off,round(x*20),round((y+TITLE_DY)*20))
            allowed[off:off+8]=b"\1"*8
            edits.append({"frame":row["frame"],"field":"translate","offset":off})
        if "scale" in row:
            sx,sy=row["scale"]
            if abs(sy-399/1024)>1e-9:raise ValueError("unexpected title vertical scale")
            off=row["scale_offset"]
            struct.pack_into("<ii",output,off,round(sx*1024),277)
            allowed[off:off+8]=b"\1"*8
            edits.append({"frame":row["frame"],"field":"scale","offset":off})
    if any(x!=y and not allowed[i] for i,(x,y) in enumerate(zip(data,output))):
        raise ValueError("movie changed outside title geometry")
    changed=bytes(output);after=placements(changed)
    for old,new in zip(rows,after):
        if (old["parent"],old["depth"])!=(22,20) and old!=new:
            raise ValueError("non-title native timeline changed")
    # Conservative UIR field extents, not just sample-font ink in the preview.
    gaps=[]
    for frame in range(111):
        title=timeline_state(changed,22,20,frame)
        if not (int(title["mult8"][0])&255):continue
        title_top=title["translate"][1]
        bottoms=[]
        for depth in (16,18):
            score=timeline_state(changed,22,depth,frame)
            if int(score["mult8"][0])&255:
                bottoms.append(score["translate"][1]+score["scale"][1]*200/3)
        if bottoms:gaps.append((frame,title_top-max(bottoms)))
    if not gaps or min(g for _,g in gaps)<8:raise ValueError("native score/title gap is below8px")
    bounds=geometry(changed)
    if abs((bounds["competition"][0]+bounds["competition"][2])/2-562)>.01:
        raise ValueError("competition field no longer centred")
    if bounds["competition"][3]>123:raise ValueError("title leaves the rounded panel")
    return changed,{"edits":edits,"title_scale_y":TITLE_SCALE_Y,"title_dy":TITLE_DY,
                    "minimum_visible_field_gap":min(g for _,g in gaps),
                    "settled_field_gap":bounds["competition"][1]-max(bounds[k][3] for k in ("home_score","away_score")),
                    "geometry":bounds,"source_movie_sha256":V89_MOVIE_SHA256,
                    "movie_sha256":digest(changed),"native_scripts_and_non_title_tracks_exact":True}


def patch_packet(packet,native):
    magic,source_size,size,source_hash,target_hash=HEADER.unpack_from(packet)
    target=packet[32:]
    if magic!=b"NXSB01\0\0" or size!=len(target) or checksum(target)!=target_hash or txp(target)!=target:
        raise ValueError("invalid source NXSB binding")
    movies=read_movies(target);movie=next(m for m in movies if m.name==MOVIE)
    changed,report=patch_movie(movie.data)
    edited=bytearray(target)
    edited[movie.offset:movie.offset+movie.size]=swap_fields(changed,movie.info)
    original,_=plate_pixels(native)
    before,(atlas,regions,pixels,(l,t,r,b))=plate_pixels(bytes(edited))
    pixels=pixels.copy();pixels[t:b,l:r,0]=original[:,:,0]
    # Reuse a real outer AFP header so the existing bounded atlas replacer
    # can grow a compressed TXP2 safely without confusing its endian header.
    outer=bytearray(native[:native.index(b"TXP2")])
    struct.pack_into("<I",outer,12,len(edited))
    combined=bytes(outer)+bytes(edited)
    output=replace_atlas(combined,atlas[:64]+pixels.tobytes(),candidate_limit=4)
    payload=txp(output)
    new_movies=read_movies(payload)
    for old,new in zip(movies,new_movies):
        if (old.name,old.size,old.info)!=(new.name,new.size,new.info):raise ValueError("movie inventory changed")
        if old.name!=MOVIE and old.data!=new.data:raise ValueError("non-banner movie changed")
    after,_=plate_pixels(payload)
    if not np.array_equal(after[:,:,0],original[:,:,0]):raise ValueError("native rounded alpha not restored")
    if not np.array_equal(after[:,:,1:],before[:,:,1:]):raise ValueError("plate RGB changed")
    report.update(native_plate_alpha_sha256=digest(original[:,:,0].tobytes()),
                  prior_plate_alpha_sha256=digest(before[:,:,0].tobytes()),
                  zero_alpha_pixels=int(np.count_nonzero(original[:,:,0]==0)),
                  protected_movies={m.name:digest(m.data) for m in movies if m.name!=MOVIE},
                  packet_sha256=digest(HEADER.pack(magic,source_size,len(payload),source_hash,checksum(payload))+payload),
                  native_wave_clip_and_imports_exact=True)
    return HEADER.pack(magic,source_size,len(payload),source_hash,checksum(payload))+payload,report


def preview(packet,native,background,waves,frame,label="Exhibition"):
    movie=next(m.data for m in read_movies(packet[32:]) if m.name==MOVIE)
    boxes=geometry(movie);imports=image_imports(movie)
    panel=Image.new("RGBA",(1124,128))
    half=native_plate(native)
    phase=int(timeline_state(movie,22,1,frame)["mult8"][0])&255
    original_alpha=np.asarray(half.getchannel("A"),np.uint32)
    half.putalpha(Image.fromarray((original_alpha*phase//255).astype(np.uint8)))
    panel.alpha_composite(half,(0,0));panel.alpha_composite(half.transpose(Image.Transpose.FLIP_LEFT_RIGHT),(562,0))
    coverage=np.minimum(original_alpha*255//224,255).astype(np.uint8)
    clip=np.concatenate((coverage,np.flip(coverage,axis=1)),axis=1).astype(np.uint32)
    wave_layer=Image.new("RGBA",panel.size)
    rows=placements(movie)
    for depth in range(1,7):
        state=timeline_state(movie,15,depth,frame)
        source=next(r["source"] for r in rows if r["parent"]==15 and r["depth"]==depth and r["frame"]==0)
        image=waves[imports[source]["name"]].copy();sx,sy=state["scale"]
        image=image.resize((round(image.width*abs(sx)),round(image.height*abs(sy))),Image.Resampling.BICUBIC)
        alpha=np.asarray(image.getchannel("A"),np.uint32)*(int(state["mult8"][0])&255)*phase//(255*255)
        image.putalpha(Image.fromarray(alpha.astype(np.uint8)));x,y=state["translate"]
        wave_layer.alpha_composite(image,(round(x),round(y)))
    wave_alpha=np.asarray(wave_layer.getchannel("A"),np.uint32)*clip//255
    wave_layer.putalpha(Image.fromarray(wave_alpha.astype(np.uint8)))
    panel.alpha_composite(wave_layer)
    text=Image.new("RGBA",panel.size);draw=ImageDraw.Draw(text)
    font_path="C:/Windows/Fonts/arialbd.ttf"
    font=ImageFont.truetype(font_path,26);score_font=ImageFont.truetype(font_path,43)
    label_font=ImageFont.truetype(font_path,round(20*277/399))
    for depth,value,key,face in ((22,"Manchester United","home_name",font),(24,"FC Barcelona","away_name",font),
            (16,"2","home_score",score_font),(18,"1","away_score",score_font),(20,label,"competition",label_font)):
        bounds=boxes[key];state=timeline_state(movie,22,depth,frame);colour=int(state["mult8"][0])
        rgba=tuple((colour>>shift)&255 for shift in (24,16,8,0))
        draw.text(((bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2),value,font=face,fill=rgba,anchor="mm")
    for key,value,colour in (("home_crest","H",RED),("away_crest","A",BLUE)):
        box=boxes[key];x,y=(box[0]+box[2])/2,(box[1]+box[3])/2
        draw.ellipse((x-32,y-32,x+32,y+32),fill=colour+(phase,))
        draw.text((x,y),value,font=font,fill=WHITE+(phase,),anchor="mm")
    panel.alpha_composite(text)
    result=background.convert("RGBA").resize((1280,720));result.alpha_composite(panel,(78,548))
    return result.convert("RGB")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive",type=Path,required=True);p.add_argument("--native",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True);p.add_argument("--background",type=Path)
    a=p.parse_args()
    if a.output.exists() and any(a.output.iterdir()):raise ValueError("use a new stage; sealed outputs are not overwritten")
    if digest(a.archive.read_bytes())!=V89_ASSETS_SHA256:raise ValueError("requires the verified v89 archive")
    native=a.native.read_bytes();native_plate(native)
    a.output.mkdir(parents=True,exist_ok=True)
    _,members=read_archive(a.archive);before=dict(members);reports={}
    names=sorted(n for n in members if n.startswith("scoreboards/c") and n.endswith(".nxsb"))
    if len(names)!=23:raise ValueError("requires23 current default/licensed theme packets")
    for name in names:
        value,report=patch_packet(members[name],native);members[name]=value;reports[name]=report
        (a.output/Path(name).name).write_bytes(value)
    if a.background:
        waves=wave_images(members["scoreboards/banner-textures.nxsb"][32:]);bg=Image.open(a.background)
        for frame,name in ((20,"entry"),(70,"hold"),(105,"exit")):
            image=preview(members["scoreboards/c0.nxsb"],native,bg,waves,frame)
            image.save(a.output/f"preview-{name}.png");image.crop((78,548,1202,676)).save(a.output/f"preview-{name}-strip.png")
        preview(members["scoreboards/c0.nxsb"],native,bg,waves,70,"UEFA CHAMPIONS LEAGUE").save(a.output/"preview-cup.png")
    output=a.output/"FootballNX.assets";pack_entries(members,output);_,verified=read_archive(output)
    changed={n for n in before if before[n]!=verified[n]}
    if set(before)!=set(verified) or changed!=set(names):raise ValueError("archive delta exceeds23 lower-banner packets")
    report={"baseline_sha256":V89_ASSETS_SHA256,"sha256":digest(output.read_bytes()),"bytes":output.stat().st_size,
            "changed_members":sorted(changed),"packets":reports,"protected_members":{n:digest(v) for n,v in before.items() if n not in changed},
            "native_plate_alpha_restored":True,"wave_clip_and_shared_wave_packet_exact":True,
            "preview_evidence":{"native_plate_and_rounded_alpha":True,"native_wave_pixels_and_tracks":True,"text_and_crests":"sample proxies","switch_capture":False},
            "previews":{f.name:digest(f.read_bytes()) for f in a.output.glob("preview-*.png")}}
    (a.output/"ASSET-REPORT.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k in ("bytes","sha256","native_plate_alpha_restored")}))


if __name__=="__main__":main()

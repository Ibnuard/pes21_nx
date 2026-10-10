"""Build local Mobile-compatible competition skins, preserving native AP2.

Uses only the user's compatible Mobile UI member and optional local emblems.
It does not substitute PC FL26 scripts or change native score/time bindings.
Output contains game-owned UI data and must stay in an ignored local directory.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from afp_texture_patch import read_atlas, replace_atlas
from afp_score_layout import read_movies
from build_efootball10_scoreboard_v2 import region_bounds
from build_fl26_cup_catalog import index_cpk, decoded_member
from pack_runtime_assets import checksum

HEADER = struct.Struct('<8sIIQQ')
# key, label, team-field colour, score/clock colour, optional local emblem
THEMES = (
 (9,'PL','#29083e','#35efc5','LeagueLogos/emb_0009_l.png'),
 (10,'ITA','#09234b','#72d6ff','LeagueLogos/emb_0010_w_l.png'),
 (11,'ESP','#471326','#ffe5db','LeagueLogos/emb_0011_l.png'),
 (12,'FRA','#10224a','#dbff00','LeagueLogos/emb_0012_w_l.png'),
 (13,'NED','#122440','#86e9e5','LeagueLogos/emb_0013_w_l.png'),
 (14,'POR','#11372d','#fbd148','LeagueLogos/emb_0014_w_l.png'),
 (39,'GER','#252526','#f5f5f5','LeagueLogos/emb_0039_l.png'),
 (21,'BRA','#10382c','#ffe864','LeagueLogos/emb_0021_w_l.png'),
 (41,'J1','#3a121c','#ffedef','LeagueLogos/emb_0041_w_l.png'),
 (119,'TUR','#430b19','#ffd6db','LeagueLogos/emb_0119_w_l.png'),
 (66,'EFL','#132a55','#e9e9ed','LeagueLogos/emb_0066_l.png'),
 (67,'ESP2','#24372b','#f1edd7','LeagueLogos/emb_0067_l.png'),
 (68,'FRA2','#17233a','#95f3bb','LeagueLogos/emb_0068_w_l.png'),
 (15,'FA','#431126','#efc9dc','CupLogos/emb_0015_l.png'),
 (16,'CUP','#162d55','#cde5ff','CupLogos/emb_0016_l.png'),
 (17,'REY','#461629','#fff0d0','CupLogos/emb_0017_w_l.png'),
 (35,'AFC','#113247','#fff1a5','CupLogos/cup-afc.png'),
 (33,'EURO','#0f2444','#c5e7ff','CupLogos/cup-euro.png'),
 (27,'WC','#3b1326','#edd3a2','CupLogos/cup-world.png'),
 (1000,'CUP','#283241','#e2d5a6',None),
 (1001,'NX','#14302e','#71ead4',None),
 (1002,'INT','#121946','#c7d9ff',None),
)

def txp(container):
    start=container.index(b'TXP2')
    size=struct.unpack_from('>I',container,start+12)[0]
    if size<108 or start+size>len(container):
        raise ValueError('Invalid TXP2 size')
    return container[start:start+size]

def skin(original, theme, logos):
    key,label,dark,light,logo=theme
    atlas,regions,_=read_atlas(original)
    width,height=struct.unpack_from('>HH',atlas,16)
    pixels=np.frombuffer(atlas[64:],np.uint8).reshape(height,width,4).copy()
    plate=next(r for r in regions if r['name']=='game2dPes-score-plateMain')
    l,t,r,b=region_bounds(plate)
    if (r-l,b-t)!=(404,48):
        raise ValueError('Requires the accepted 404x48 square Mobile scoreboard')
    def rgb(text): return tuple(bytes.fromhex(text[1:]))
    bar=pixels[t:b,l:r]
    # Preserve alpha, native geometry and the dark/light readability contract.
    bright=np.max(bar[:,:,1:],axis=2)>150
    bar[:,:,1:]=np.where(bright[:,:,None],rgb(light),rgb(dark))
    badge=Image.new('RGBA',(48,48),rgb(dark)+(255,))
    emblem=logos/logo if logo and logos else None
    if emblem and emblem.is_file():
        icon=Image.open(emblem).convert('RGBA')
        icon.thumbnail((38,38),Image.Resampling.LANCZOS)
        badge.alpha_composite(icon,((48-icon.width)//2,(48-icon.height)//2))
    else:
        draw=ImageDraw.Draw(badge)
        draw.text((24,24),label,anchor='mm',font=ImageFont.load_default(size=12),fill=rgb(light))
    rgba=np.asarray(badge)
    bar[:,-48:]=rgba[:,:,[3,0,1,2]]
    modified=replace_atlas(original,atlas[:64]+pixels.tobytes(),candidate_limit=4)
    before=read_movies(original); after=read_movies(modified)
    if [(m.name,m.info,m.data) for m in before] != [(m.name,m.info,m.data) for m in after]:
        raise ValueError('Native AP2 scripts changed')
    source,target=txp(original),txp(modified)
    packet=HEADER.pack(b'NXSB01\0\0',len(source),len(target),checksum(source),checksum(target))+target
    preview=Image.fromarray(pixels[t:b,l:r,:][:,:,[1,2,3,0]])
    return packet,preview

def build(cpk,logos,out):
    source=decoded_member(cpk,*index_cpk(cpk),'common/menu/licence/game2dPes.bin')
    out.mkdir(parents=True,exist_ok=True)
    previews=[]; report={'source_sha256':hashlib.sha256(source).hexdigest(),'themes':{}}
    for theme in THEMES:
        packet,preview=skin(source,theme,logos)
        path=out/('c%d.nxsb'%theme[0]); path.write_bytes(packet)
        previews.append(preview)
        report['themes'][str(theme[0])]={'bytes':len(packet),'sha256':hashlib.sha256(packet).hexdigest()}
    sheet=Image.new('RGBA',(404,48*len(previews)),(20,20,20,255))
    for i,preview in enumerate(previews): sheet.paste(preview,(0,i*48))
    sheet.save(out/'preview.png')
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mobile-cpk',type=Path,required=True)
    p.add_argument('--logos',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    report=build(a.mobile_cpk,a.logos,a.output)
    print('Validated %d competition skins; AP2 unchanged'%len(report['themes']))

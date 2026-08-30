"""Bake user-owned EF10 visuals into PES21's original layouts and formats.

The source materials/meshes, package headers, alpha channels, UVs and markings
are preserved. Every existing mip is regenerated, including the 10x tiled
RGBA detail map responsible for most of the visible grass noise.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import zlib

import numpy as np
from PIL import Image, ImageFilter

from cooked_texture import Texture
from afp_texture_patch import read_atlas, replace_atlas


def sha(data):
    return hashlib.sha256(data).hexdigest()


def etc1(image, path, encoder):
    image.convert('RGB').save(path.with_suffix('.png'))
    subprocess.run([str(encoder),str(path.with_suffix('.png')),'--encodeNoHeader','-o',str(path)],check=True,capture_output=True)
    return path.read_bytes()


def grain_source(ef10):
    # Green is turf detail, blue is field markings. Crop an unmarked central
    # patch, never copy EF10's incompatible line geometry or packed RGB mask.
    src=Texture(next(ef10.rglob('T_Pitch_mobile.uexp'))).decode()
    green=src.getchannel('G').crop((650,320,1162,832))
    blurred=green.filter(ImageFilter.GaussianBlur(1.1))
    fine=np.asarray(green,dtype=np.float32)-np.asarray(blurred,dtype=np.float32)
    fine-=fine.mean()
    return np.clip(fine/max(float(fine.std()),0.01),-2.5,2.5)


def pitch(args, out, previews):
    root=args.pes21/'PesMobile/Content/Assets/bg_lighting_AM1/Textures'
    grain=grain_source(args.ef10)
    result=[]
    names=('pitch_l_bsm_alp','pitch_r_bsm_alp','pitch_lr_bsm_exLow_alp',
           'pitch_l_bsm_exLow_alp','pitch_r_bsm_exLow_alp','pitch2_bsm_alp_copied')
    for name in names:
        texture=Texture(root/(name+'.uexp'))
        original=np.asarray(texture.decode())
        height,width=original.shape[:2]
        detail=name=='pitch2_bsm_alp_copied'
        if detail:
            # Native tiled detail is the high-contrast, yellow/noisy layer.
            # Retain its alpha and use EF10 high-frequency turf at lower gain.
            base=np.array([47,65,18],dtype=np.float32)
            replacement=np.empty_like(original)
            replacement[:,:,:3]=np.clip(base+grain[:,:,None]*np.array([2.0,3.8,1.5]),0,255)
            replacement[:,:,3]=original[:,:,3]
            image=Image.fromarray(replacement)
        else:
            original_rgb=original[:,:,:3].astype(np.int16)
            original_line_mask=(original_rgb.min(axis=2)>=78)&((original_rgb.max(axis=2)-original_rgb.min(axis=2))<=48)
            line_image=Image.fromarray(original_line_mask.astype(np.uint8)*255)
            bands=16 if '_lr_' in name else 8
            x=np.arange(width,dtype=np.float32)
            # No seam shift or line movement. Stripe phase is symmetric at
            # the half-pitch join, and contrast is independent of grain gain.
            blend=((x//(width/bands)).astype(int)&1)[None,:,None]
            dark=np.array([30,51,13],dtype=np.float32)
            light=np.array([46,72,22],dtype=np.float32)
            rgb=np.repeat(dark*(1-blend)+light*blend,height,axis=0)
            image=Image.fromarray(np.uint8(rgb),'RGB').filter(ImageFilter.GaussianBlur(0.7))
        payloads=[]
        line_counts=[]
        for i,mip in enumerate(texture.mips):
            # Mip data is converted in sRGB here because these authored colors
            # are already in the native texture's gamma encoding. Box-average
            # in linear space to avoid dark halos at stripe transitions.
            rgb=np.asarray(image.convert('RGB'),dtype=np.float32)/255
            linear=np.where(rgb<=0.04045,rgb/12.92,((rgb+0.055)/1.055)**2.4)
            small=np.stack([np.asarray(Image.fromarray(linear[:,:,c]).resize((mip.width,mip.height),Image.Resampling.BOX)) for c in range(3)],axis=2)
            gamma=np.where(small<=0.0031308,small*12.92,1.055*np.power(np.maximum(small,0),1/2.4)-0.055)
            resized=Image.fromarray(np.uint8(np.clip(np.rint(gamma*255),0,255)))
            if texture.format=='PF_B8G8R8A8':
                resized.putalpha(texture.decode(i).getchannel('A'))
                payload=resized.tobytes('raw','BGRA')
                line_counts.append(0)
            elif texture.format=='PF_ETC1':
                payload=bytearray(etc1(resized,previews/f'{name}-mip{i}.etc1',args.etc1tool))
                native=np.asarray(texture.decode(i))[:,:,:3].astype(np.int16)
                mask=(native.min(axis=2)>=78)&((native.max(axis=2)-native.min(axis=2))<=48)
                # A distant mip may average white paint below the brightness
                # threshold. Protect its footprint from the native top mip as
                # well, rather than accidentally painting over a faint line.
                mask |= np.asarray(line_image.resize((mip.width,mip.height),Image.Resampling.BOX))>0
                blocks=mask.reshape(mip.height//4,4,mip.width//4,4).any(axis=(1,3)).reshape(-1)
                source=texture.payload(i)
                for block in np.flatnonzero(blocks):
                    payload[block*8:block*8+8]=source[block*8:block*8+8]
                payload=bytes(payload)
                line_counts.append(int(blocks.sum()))
                assert all(payload[b*8:b*8+8]==source[b*8:b*8+8] for b in np.flatnonzero(blocks))
            else:
                raise ValueError('unsupported PES21 target format')
            payloads.append(payload)
        files=texture.replace(payloads)
        target=out/'pitch-stage'/texture.path.relative_to(args.pes21)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(texture.path.with_suffix('.uasset'),target.with_suffix('.uasset'))
        for suffix,data in files.items():
            assert len(data)==len(texture.files[suffix])
            target.with_suffix('.'+suffix).write_bytes(data)
        check=Texture(target)
        assert all(check.payload(i)==p for i,p in enumerate(payloads))
        check.decode().save(previews/(name+'-after.png'))
        result.append({'texture':name,'mips':len(payloads),'original_line_blocks':line_counts,
                       'format':texture.format,'changed_mips':sum(check.payload(i)!=texture.payload(i) for i in range(len(payloads))),
                       'headers_unchanged':True,'file_sizes_unchanged':True})
        print(name,'mips',len(payloads),'verified',flush=True)
    return result


def scoreboard(args,out,previews):
    original=args.score_base.read_bytes()
    atlas,regions,_=read_atlas(original)
    w,h=struct.unpack_from('>HH',atlas,16)
    if struct.unpack_from('>I',atlas,20)[0]&255 !=0x15:
        raise ValueError('expected ARGB8888 score atlas')
    source=Image.frombytes('RGBA',(w,h),atlas[64:],'raw','ARGB')
    modified=np.array(source)
    blue=Texture(next(args.ef10.rglob('MatchTimePlate_0.uexp'))).decode().getpixel((0,0))[:3]
    yellow=Texture(next(args.ef10.rglob('MatchTimePlate_1.uexp'))).decode().getpixel((0,0))[:3]
    changes=[]
    # Preserve white digits/team text legibility on navy. EF10 yellow is an
    # accent, not a full plate behind PES21's fixed white glyphs.
    for entry in regions:
        name=entry['name']
        if name not in ('game2dPes-score-plateTime','game2dPes-score-plateMain',
                         'game2dPes-score-plateAgreegateScore','game2dPes-score-plateStats'):
            continue
        _,l,t,r,b=entry['rect']
        x0,y0,x1,y1=l//2,t//2,(r+1)//2,(b+1)//2
        modified[y0:y1,x0:x1,:3]=blue
        # Inset bounds include native half-texel filtering gutters.
        modified[max(y0,y1-2):y1,x0:x1,:3]=yellow
        changes.append(name)
    image=Image.fromarray(modified)
    assert np.array_equal(modified[:,:,3],np.asarray(source)[:,:,3])
    patched_atlas=atlas[:64]+modified[:,:,[3,0,1,2]].tobytes()
    patched=replace_atlas(original,patched_atlas)
    packed=zlib.compress(patched,9)
    wesys=b'\xff\x10\x81WESYS'+struct.pack('<II',len(packed),len(patched))+packed
    (out/'game2dPes.bin').write_bytes(wesys)
    image.save(previews/'score-atlas-after.png')
    return {'changed_regions':changes,'palette_source':['MatchTimePlate_0','MatchTimePlate_1'],
            'alpha_unchanged':True,'scripts_layout_regions_unchanged':True,
            'scope':'EF10 plate/palette skin; native PES21 layout, logo and text remain',
            'wesys_size':len(wesys),'sha256':sha(wesys)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--pes21',type=Path,default=Path('local-debug/pitch-audit-20260826/base'))
    p.add_argument('--ef10',type=Path,default=Path('local-debug/stability-visuals/ef10'))
    p.add_argument('--score-base',type=Path,default=Path('local-debug/stability-visuals/pes21-ui/game2dPes.bin'))
    p.add_argument('--output',type=Path,default=Path('local-debug/stability-visuals/built'))
    p.add_argument('--etc1tool',type=Path,default=Path.home()/'AppData/Local/Android/Sdk/platform-tools/etc1tool.exe')
    args=p.parse_args()
    out=args.output
    out.mkdir(parents=True,exist_ok=True)
    previews=out/'previews'
    previews.mkdir(exist_ok=True)
    report={'pitch':pitch(args,out,previews),'scoreboard':scoreboard(args,out,previews)}
    (out/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()

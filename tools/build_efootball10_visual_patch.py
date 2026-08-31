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


def diffuse_grain_source(ef10):
    """Mid/fine EF10 turf variation for the once-mapped diffuse textures."""
    src=Texture(next(ef10.rglob('T_Pitch_mobile.uexp'))).decode()
    green=src.getchannel('G').crop((650,320,1162,832))
    # Keep only fine grass variation. A wider residual also retains EF10's
    # broad baked tiles, which showed as faint rectangles in the PES21 diffuse.
    # Repeat this line-free high-frequency crop at native diffuse resolution.
    low=np.asarray(green.filter(ImageFilter.GaussianBlur(1.1)),dtype=np.float32)
    residual=np.asarray(green,dtype=np.float32)-low
    residual-=residual.mean()
    residual=np.clip(residual/max(float(residual.std()),0.01),-2.5,2.5)
    tiled=np.tile(residual,(2,2))
    tiled-=tiled.mean()
    return tiled


def pitch_colors(style):
    if style in ('clean-v2','clean-v3','clean-v4','clean-v5','clean-v6','clean-v7'):
        # Same mean green (61.5), stronger separation (31 instead of 21).
        # Contrast is not achieved by scaling the fine-grain layer.
        return ([26,46,12], [49,77,23])
    return ([30,51,13], [46,72,22])


def mowing_blend(name, width, style):
    """Return a 1xWx1 dark/light blend anchored to the native pitch seam."""
    bands=16 if '_lr_' in name else 8
    band_width=width//bands
    x=np.arange(width,dtype=np.int32)
    if style=='clean-v7':
        # Cooked-asset audit: Low_L and Low_R share pitch_l_bsm_alp. The
        # exported mesh has seam UV0 L u=1, R u~=0, before shader transforms.
        # Six bands across the whole texture make those edges opposite. This
        # is a candidate mapping, not proof of the active runtime shader's
        # final UVs; v6's assumed active-rectangle mapping failed on Switch.
        bands=12 if '_lr_' in name else 6
        values=np.floor(x*bands/width).astype(np.int32)&1
        band_width=width/bands
    elif style=='clean-v6':
        # Historical v6 recipe, retained for reproducibility. It assumed
        # Low_R mirrored the x254..1023 painted-field rectangle via isL.
        # The device still showed light/light, so that runtime interpretation
        # was not validated. Do not treat this branch as an audited UV model.
        if '_lr_' in name:
            active_start,active_end,bands=127,897,12
        elif name.startswith('pitch_l_'):
            active_start,active_end,bands=254,1024,6
        else:
            active_start,active_end,bands=0,770,6
        sample=np.clip(x,active_start,active_end-1)
        values=np.floor((sample-active_start)*bands/(active_end-active_start)).astype(np.int32)&1
        band_width=(active_end-active_start)/bands
    elif style=='clean-v5' and '_lr_' in name:
        # The combined distant-LOD texture contains both pitch halves. Author
        # outwards from its exact middle: left-adjacent is light and
        # right-adjacent is dark, so the mowing shade changes at the line
        # instead of placing a correction band across it.
        center=width//2
        left_index=(center-1-x)//band_width
        right_index=(x-center)//band_width
        values=np.where(x<center,1-(left_index&1),right_index&1)
    else:
        phase_offset=band_width/2 if style=='clean-v4' else 0
        values=(((x+phase_offset)//band_width).astype(np.int32)&1)
        if style=='clean-v3' and name.startswith('pitch_r_'):
            values=1-values
        if style=='clean-v5' and name.startswith('pitch_l_'):
            # In the L texture the center seam is the right edge. Its left
            # edge is outside the playable geometry, so make both possible UV
            # orientations light without altering the visible outer sideline.
            values[:band_width]=1
            values[-band_width:]=1
        elif style=='clean-v5' and name.startswith('pitch_r_'):
            # R is the opposite half: center-adjacent shade is dark. Mirrored
            # and non-mirrored sampling therefore agree at the seam.
            values[:band_width]=0
            values[-band_width:]=0
    return values[None,:,None],band_width


def neutral_specular_payload(texture, index):
    if texture.format != 'PF_B8G8R8A8':
        raise ValueError('unexpected native specular mask format')
    rgba=np.array(texture.decode(index))
    # Native R/G encode crossing stripe patterns. Make them spatially neutral
    # so the diffuse remains the sole broad-band pattern. Preserve B and A
    # exactly: their shader roles are not being guessed/replaced here.
    rgba[:,:,:2]=128
    return Image.fromarray(rgba).tobytes('raw','BGRA')


def pitch(args, out, previews, selected_names=None, complement_diffuse=False):
    root=args.pes21/'PesMobile/Content/Assets/bg_lighting_AM1/Textures'
    grain=grain_source(args.ef10)
    diffuse_grain=diffuse_grain_source(args.ef10)
    result=[]
    style=getattr(args,'pitch_style','baseline')
    names=('pitch_l_bsm_alp','pitch_r_bsm_alp','pitch_lr_bsm_exLow_alp',
           'pitch_l_bsm_exLow_alp','pitch_r_bsm_exLow_alp','pitch2_bsm_alp_copied')
    if style in ('mask-only','clean-v2','clean-v3','clean-v4','clean-v5','clean-v6','clean-v7'):
        names+=('pitch_specular_mask_l','pitch_specular_mask_r')
    if selected_names is not None:
        if not set(selected_names).issubset(names):
            raise ValueError('unexpected selected pitch textures')
        names=tuple(selected_names)
    for name in names:
        texture=Texture(root/(name+'.uexp'))
        original=np.asarray(texture.decode())
        height,width=original.shape[:2]
        detail=name=='pitch2_bsm_alp_copied'
        specular=name.startswith('pitch_specular_mask_')
        if specular:
            image=texture.decode()
        elif detail:
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
            blend,band_width=mowing_blend(name,width,style)
            if complement_diffuse:
                blend=1-blend
            phase_inverted=style=='clean-v3' and name.startswith('pitch_r_')
            dark_color,light_color=pitch_colors(style)
            dark=np.array(dark_color,dtype=np.float32)
            light=np.array(light_color,dtype=np.float32)
            rgb=np.repeat(dark*(1-blend)+light*blend,height,axis=0)
            rgb=np.asarray(Image.fromarray(np.uint8(rgb),'RGB').filter(ImageFilter.GaussianBlur(0.7)),dtype=np.float32)
            if style in ('clean-v3','clean-v4','clean-v5','clean-v6','clean-v7'):
                if diffuse_grain.shape != (height,width):
                    raise ValueError('unexpected diffuse texture dimensions for EF10 grain')
                # Bake subtle grain into the diffuse itself. The separate
                # 10x detail layer is retained byte-for-byte from the accepted
                # baseline, because it was too weak/unused in the device view.
                gain_values={'clean-v3':[1.6,3.2,1.2],
                             'clean-v4':[2.0,4.0,1.5],
                             'clean-v5':[2.4,4.8,1.8],
                             'clean-v6':[2.4,4.8,1.8],
                             'clean-v7':[2.8,5.6,2.1]}
                gain=np.array(gain_values[style],dtype=np.float32)
                rgb+=diffuse_grain[:,:,None]*gain
            image=Image.fromarray(np.uint8(np.clip(np.rint(rgb),0,255)),'RGB')
        payloads=[]
        line_counts=[]
        for i,mip in enumerate(texture.mips):
            if specular:
                payloads.append(neutral_specular_payload(texture,i))
                line_counts.append(0)
                continue
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
                       'headers_unchanged':True,'file_sizes_unchanged':True,
                       'diffuse_phase_complemented':bool(complement_diffuse and not detail and not specular),
                       'diffuse_grain_gain_rgb':({'clean-v3':[1.6,3.2,1.2],
                                                  'clean-v4':[2.0,4.0,1.5],
                                                  'clean-v5':[2.4,4.8,1.8],
                                                  'clean-v6':[2.4,4.8,1.8],
                                                  'clean-v7':[2.8,5.6,2.1]}[style]) if style in ('clean-v3','clean-v4','clean-v5','clean-v6','clean-v7') and not detail and not specular else None,
                       'right_half_phase_inverted':bool(style=='clean-v3' and name.startswith('pitch_r_')),
                       'stripe_half_band_offset':bool(style=='clean-v4' and not detail and not specular),
                       'native_seam_anchored':bool(style=='clean-v5' and not detail and not specular),
                       'seam_adjacent_shade':('light-left/dark-right' if style in ('clean-v5','clean-v6','clean-v7') and not detail and not specular else None),
                       'active_pitch_rect_anchored':bool(style=='clean-v6' and not detail and not specular),
                       'global_mirror_antisymmetric_phase':bool(style=='clean-v7' and not detail and not specular),
                       'low_right_shared_left_texture_compatible':bool(style in ('clean-v6','clean-v7') and not detail and not specular)})
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
    p.add_argument('--pitch-style',choices=('baseline','mask-only','clean-v2','clean-v3','clean-v4','clean-v5','clean-v6','clean-v7'),default='baseline')
    p.add_argument('--only',choices=('pitch','scoreboard','all'),default='all')
    p.add_argument('--etc1tool',type=Path,default=Path.home()/'AppData/Local/Android/Sdk/platform-tools/etc1tool.exe')
    args=p.parse_args()
    out=args.output
    if args.pitch_style!='baseline' and (out==p.get_default('output') or out.exists()):
        raise ValueError('new pitch revisions require an explicit, new output directory')
    out.mkdir(parents=True,exist_ok=True)
    previews=out/'previews'
    previews.mkdir(exist_ok=True)
    report={'pitch_style':args.pitch_style}
    if args.only in ('pitch','all'):
        report['pitch']=pitch(args,out,previews)
    if args.only in ('scoreboard','all'):
        report['scoreboard']=scoreboard(args,out,previews)
    (out/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()

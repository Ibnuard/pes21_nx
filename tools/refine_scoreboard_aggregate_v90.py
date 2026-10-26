"""Expose the existing native leg-two aggregate on every current scorebar.

Only aggregate placement fields, its dedicated image binding and atlas region
change. Scripts, native visibility/digit labels, the live score, the clock and
the separately refined lower match banner remain exact. Local game-derived
packets, previews and archives must remain ignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from afp_score_layout import read_movies, placements, strings, swap_fields
from afp_texture_patch import read_atlas, replace_atlas
from build_efootball10_scoreboard_v2 import region_bounds
from build_footballnx27_scoreboard import HEADER, txp
from pack_runtime_assets import read_archive, pack_entries, checksum

MOVIE = 'game2d_score'
PLATE = 'game2dPes-score-plateAgreegateScore'
LOWER_SHA = 'eb96ed25e3f9fda9fb3b632dd7aefa1301d0b156f6baf49bd7f96de7caf56955'
LOWER_ALPHA_SHA = '6e74130d78cf3d83cd82716709f8b080345a8a54dab15d76824890b46ebc5ecf'
BANNER_ASSETS_SHA = '460d853efebea7aeb98abde3bc187959852acfd264eb8e7fa146917e2c092979'
REGION = (0, 464, 144, 496)
KEYS = (0, 9, 10, 11, 12, 13, 14, 15, 16, 17, 21, 27, 33, 35, 39,
        41, 66, 67, 68, 119, 1000, 1001, 1002)
# GER/INT placeholder plates use the current FootballNX27 default theme.
# Keep their selection keys so competition/fixture identity stays unchanged.
DEFAULT_THEME_ALIASES = {39: 1000, 1002: 1000}


def digest(value): return hashlib.sha256(value).hexdigest()


def aggregate_plate():
    image = Image.new('RGBA', (144, 32), (249, 250, 252, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 143, 1), fill=(18, 91, 255, 255))
    draw.rectangle((0, 31, 143, 31), fill=(215, 222, 233, 255))
    font = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 14)
    draw.text((9, 17), 'AGG', font=font, anchor='lm', fill=(26, 32, 41, 255))
    draw.line((46, 8, 46, 25), fill=(215, 222, 233, 255))
    draw.rectangle((91, 15, 98, 17), fill=(26, 32, 41, 255))
    return image


def image_binding(data):
    base = struct.unpack_from('<I', data, 36)[0]
    count, table = struct.unpack_from('<HHIIIII', data, base)[3::3]
    cursor = base + table
    found = []
    names = strings(data)
    for _ in range(count):
        word = struct.unpack_from('<I', data, cursor)[0]
        code, size = word >> 22, word & 0x3fffff
        if code == 0x83:
            flags, source, name, width, height = struct.unpack_from('<I4H', data, cursor + 4)
            if source == 8:
                if flags != 40 or size != 12 or names[name].replace('_', '-') != PLATE:
                    raise ValueError('unsupported dedicated aggregate image binding')
                found.append((cursor + 12, width, height))
        cursor += 4 + (size + 3) // 4 * 4
    if len(found) != 1 or found[0][1:] != (54, 54):
        raise ValueError('aggregate import must be the unmodified native 54x54 image')
    return found[0][0]


def patch_movie(data, key):
    if key not in KEYS: raise ValueError('unsupported scoreboard key')
    rows = placements(data)
    initial = {(r['parent'], r['depth']): r for r in rows if r['frame'] == 0}
    if len(rows) != 534 or initial[(28, 52)].get('name') != 'aggregate':
        raise ValueError('unsupported native aggregate hierarchy')
    if any(initial[(20, d)].get('name') != name for d, name in
           ((1, 'aggregate_numbers_home'), (6, 'aggregate_numbers_away'))):
        raise ValueError('aggregate digit owner mismatch')
    if {(r['parent'], r['depth']) for r in rows if r.get('source') == 8} != {(21, 1), (21, 2)}:
        raise ValueError('aggregate image is used outside its own native clip')
    output, allowed, edits = bytearray(data), bytearray(len(data)), []
    def write(off, fmt, values, field):
        value = struct.pack('<' + fmt, *values)
        output[off:off + len(value)] = value
        allowed[off:off + len(value)] = b'\1' * len(value)
        edits.append(dict(offset=off, bytes=len(value), field=field))
    # The native image dimensions are exported at 3:2 physical pixels.
    write(image_binding(data), 'HH', (216, 48), 'aggregate_image_size')
    # Keep the native entry/exit translations, shifting every outer keyframe
    # by one delta. Spain/France reserve the lower left for added time.
    target = {9: (8, 92), 10: (8, 98), 11: (64, 116), 12: (64, 138)}.get(key, (8, 76))
    anchor = initial[(28, 52)]['translate']
    digit = initial[(16, 1)].get('scale16')
    if digit is None: raise ValueError('missing native aggregate/clock glyph scale')
    glyph_w, glyph_h = (200 / 3 * x for x in digit)
    # Native oneDigit displays numbers_1 at x0; twoDigit uses -6.65,+7.3
    # (2/3 in compact profiles). Place both native states within roomy cells.
    glyph_y = (32 - glyph_h) / 2 - 2
    homes = {1: 70 - glyph_w / 2 - 2, 6: 120 - glyph_w / 2 - 2}
    for row in rows:
        if 'translate' not in row: continue
        x, y = row['translate']; pair = (row['parent'], row['depth'])
        if pair == (28, 52):
            write(row['translate_offset'], 'ii', tuple(round((v + n - old) * 20)
                  for v, n, old in zip((x, y), target, anchor)), 'aggregate_anchor')
        elif row['parent'] == 20 and row['depth'] in homes:
            write(row['translate_offset'], 'ii', (round(homes[row['depth']] * 20),
                  round(glyph_y * 20)), 'aggregate_number_cell')
        elif pair == (21, 2):
            # Native used two adjacent square tiles; the first now supplies
            # one complete plate. Retain second-child alpha/timing offscreen.
            write(row['translate_offset'], 'ii', (round((x - 2048) * 20), round(y * 20)),
                  'redundant_aggregate_background')
    if any(a != b and not allowed[i] for i, (a, b) in enumerate(zip(data, output))):
        raise ValueError('movie changed outside aggregate fields')
    if len(placements(output)) != len(rows): raise ValueError('native timeline inventory changed')
    return bytes(output), dict(edits=edits, anchor=list(target), glyph_size=[glyph_w, glyph_h],
        number_cells=[[target[0]-2+homes[d], target[1]+glyph_y] for d in (1, 6)],
        native_show_hide_labels_exact=True, native_one_two_digit_scripts_exact=True,
        current_score_clock_cards_and_lower_banner_exact=True)


def build(container, key):
    movies = read_movies(container)
    movie = next(m for m in movies if m.name == MOVIE)
    lower = next(m for m in movies if m.name == 'game2d_scoreDemo')
    if digest(lower.data) != LOWER_SHA: raise ValueError('requires the reviewed v90 lower banner')
    patched, report = patch_movie(movie.data, key)
    changed = bytearray(container)
    changed[movie.offset:movie.offset+movie.size] = swap_fields(patched, movie.info)
    atlas, regions, (base, _, _, _) = read_atlas(changed)
    width, height = struct.unpack_from('>HH', atlas, 16)
    if (width, height) != (1024, 512): raise ValueError('unsupported atlas')
    if any(region_bounds(r)[3] > REGION[1] for r in regions):
        raise ValueError('new aggregate atlas area is not unused')
    original = np.frombuffer(atlas[64:], np.uint8).reshape(height, width, 4)
    pixels = original.copy(); l, t, r, b = REGION
    pixels[t:b, l:r] = np.asarray(aggregate_plate())[:, :, [3, 0, 1, 2]]
    outside = np.ones((height, width), bool); outside[t:b,l:r] = False
    if not np.array_equal(pixels[outside], original[outside]): raise ValueError('unrelated pixels changed')
    table = struct.unpack_from('>I', changed, base+40)[0]
    index = next(i for i, region in enumerate(regions) if region['name'] == PLATE)
    struct.pack_into('>5H', changed, base+table+index*10, 0, l*2+1, t*2+1, r*2-1, b*2-1)
    expected_atlas = atlas[:64]+pixels.tobytes()
    output = replace_atlas(bytes(changed), expected_atlas, candidate_limit=4)
    actual, after_regions, _ = read_atlas(output)
    if actual != expected_atlas: raise ValueError('atlas roundtrip mismatch')
    if any(a != b for a,b in zip(regions, after_regions) if a['name'] != PLATE):
        raise ValueError('unrelated atlas mapping changed')
    for old,new in zip(movies,read_movies(output)):
        if (old.name,old.info,old.size)!=(new.name,new.info,new.size) or (old.name!=MOVIE and old.data!=new.data):
            raise ValueError('unrelated native movie changed')
    lower_plate=next(r for r in regions if r['name']=='game2dPes-scoreDemo-plate-half')
    ll,tt,rr,bb=region_bounds(lower_plate)
    if digest(pixels[tt:bb,ll:rr,0].tobytes())!=LOWER_ALPHA_SHA:
        raise ValueError('reviewed native rounded lower plate alpha changed')
    report.update(key=key, source_sha256=digest(container), output_sha256=digest(output),
        lower_movie_sha256=LOWER_SHA, lower_plate_alpha_sha256=LOWER_ALPHA_SHA,
        aggregate_atlas_region=list(REGION), aggregate_plate_size=[144,32],
        atlas_roundtrip=True, unrelated_atlas_pixels_exact=True,
        unrelated_atlas_mappings_exact=True, unrelated_movies_exact=True, device_validated=False)
    return output,report


def patch_packet(packet,key):
    if len(packet)<HEADER.size: raise ValueError('truncated NXSB packet')
    magic,source_size,size,source_hash,target_hash=HEADER.unpack_from(packet)
    target=packet[HEADER.size:]
    if magic!=b'NXSB01\0\0' or size!=len(target) or checksum(target)!=target_hash or txp(target)!=target:
        raise ValueError('invalid NXSB target binding')
    output,report=build(target,key)
    return HEADER.pack(magic,source_size,len(output),source_hash,checksum(output))+output,report


def preview(container,key,report,scores=(12,13)):
    """Actual atlas/aggregate bitmap geometry with sample native UIR text.

    This is a host layout view, not a Switch screenshot or animation proof.
    """
    atlas,regions,_=read_atlas(container)
    image=Image.fromarray(np.frombuffer(atlas[64:],np.uint8).reshape(512,1024,4)[:,:,[1,2,3,0]])
    bounds={r['name']:region_bounds(r) for r in regions}
    canvas=Image.new('RGBA',(480,224),(53,91,65,255));draw=ImageDraw.Draw(canvas)
    main=image.crop(bounds['game2dPes-score-plateMain']);canvas.alpha_composite(main,(38,32))
    movie=next(m for m in read_movies(container) if m.name==MOVIE)
    initial={(r['parent'],r['depth']):r for r in placements(movie.data) if r['frame']==0}
    font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',18 if key in (9,10,11,12) else 22)
    for depth,text in ((63,'HOM'),(61,'AWY'),(67,'2'),(65,'1')):
        x,y=initial[(28,depth)]['translate']
        # NodeRectText has a native UIR field rather than atlas glyphs.
        w=(52 if depth in (61,63) else 25.3) if key in (9,10,11,12) else (78 if depth in (61,63) else 38)
        colour=int(initial[(28,depth)].get('mult8',(0xffffffff,))[0])
        rgb=tuple((colour>>shift)&255 for shift in (24,16,8))
        if depth in (65,67) and key in (9,10,11,12):rgb=(26,32,41)
        # Production brand names are tinted inside their NodeRectText fields;
        # the outer white timeline multiplier is not that UIR text colour.
        if depth in (61,63) and key in (1000,1001):rgb=(26,32,41)
        draw.text((32+x+w/2,12+y+12),text,font=font,anchor='mm',fill=rgb)
    if key in (1000,1001):
        draw.text((322,56),'102:08',font=font,anchor='mm',fill=(26,32,41))
    ax,ay=report['anchor'];canvas.alpha_composite(image.crop(REGION),(round(ax+30),round(ay+10)))
    digit_rows=[r for r in placements(movie.data) if r['parent']==19 and r['frame']==3]
    offsets={r['depth']:r['translate'][0] for r in digit_rows if 'translate'in r}
    for score,(x,y) in zip(scores,report['number_cells']):
        chars=str(min(99,score)); xs=[0] if len(chars)==1 else [offsets[1],offsets[4]]
        for char,dx in zip(chars,xs):
            tile=image.crop(bounds['MatchPlate-texFont-digit'+char])
            canvas.alpha_composite(tile,(round(32+x+dx),round(12+y)))
    small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',12)
    draw.text((8,198),f'c{key}: native live 2-1; AGG {scores[0]}-{scores[1]}',font=small,fill='white')
    draw.text((8,212),'HOST LAYOUT / native atlas digits / sample UIR text',font=small,fill='white')
    return canvas


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--packets',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise SystemExit('output must be new')
    if digest(args.assets.read_bytes())!=BANNER_ASSETS_SHA: raise SystemExit('requires verified v90 banner-only assets')
    _,before=read_archive(args.assets);members=dict(before)
    args.output.mkdir(parents=True);reports=[];views=[]
    for key in KEYS:
        source_key=DEFAULT_THEME_ALIASES.get(key,key)
        name=f'c{key}.nxsb';member='scoreboards/'+name;source_name=f'c{source_key}.nxsb'
        packet=(args.packets/source_name).read_bytes()
        if before['scoreboards/'+source_name]!=packet:raise ValueError('packet/archive source mismatch '+source_name)
        changed,report=patch_packet(packet,source_key);(args.output/name).write_bytes(changed);members[member]=changed
        view=preview(changed[HEADER.size:],source_key,report);view.save(args.output/(name+'.png'));views.append(view)
        report.update(key=key,source_theme_key=source_key,packet_sha256=digest(changed),packet_bytes=len(changed));reports.append(report)
    board=Image.new('RGBA',(4*480,6*224),(20,30,25,255))
    for i,view in enumerate(views):board.alpha_composite(view,((i%4)*480,(i//4)*224))
    board.save(args.output/'ALL-THEMES.png')
    packed=args.output/'FootballNX.assets';pack_entries(members,packed);_,after=read_archive(packed)
    expected={'scoreboards/c'+str(k)+'.nxsb' for k in KEYS}
    if set(before)!=set(after) or {n for n in before if before[n]!=after[n]}!=expected:
        raise ValueError('unexpected archive member delta')
    report=dict(state='verified_host_aggregate_candidate',bytes=packed.stat().st_size,
        sha256=digest(packed.read_bytes()),baseline_sha256=BANNER_ASSETS_SHA,
        changed_members=sorted(expected),protected_member_count=len(before)-len(expected),
        protected_members={n:digest(v) for n,v in before.items() if n not in expected},
        all_23_themes=True,lower_movie_sha256=LOWER_SHA,lower_plate_alpha_sha256=LOWER_ALPHA_SHA,
        shared_wave_exact=True,default_theme_aliases=DEFAULT_THEME_ALIASES,
        device_validated=False,themes=reports)
    (args.output/'ASSET-REPORT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:report[k] for k in ('state','bytes','sha256','protected_member_count')}))


if __name__=='__main__':main()

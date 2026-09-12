"""Read original menu atlases from the local PES archive for asset selection."""
from pathlib import Path
import struct
import json
import zlib
from PIL import Image
from prepare_runtime import read_cpk_packet
from afp_texture_patch import read_atlas, lzss_decode

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'local-debug/main-menu-art'
out.mkdir(parents=True, exist_ok=True)
with (ROOT / 'local-inputs/patch.305030001.jp.nyan2021.pesam.obb').open('rb') as f:
    h = read_cpk_packet(f, 0, b'CPK ')[0]
    rows = read_cpk_packet(f, h['TocOffset'], b'TOC ')
    r = next(r for r in rows if r['FileName'] == 'dt210_mobile_android.cpk')
    offset = min(h['TocOffset'], h['ContentOffset']) + r['FileOffset']
    h = read_cpk_packet(f, offset, b'CPK ')[0]
    rows = read_cpk_packet(f, offset+h['TocOffset'], b'TOC ')
    base = offset+min(h['TocOffset'], h['ContentOffset'])
    for r in rows:
        name = r['FileName']
        if not (name in {'titlePressStart.bin', 'localMainMenu.bin',
                         'cmnIconMainMenu.bin', 'titleCorporate.bin'} or
                name.startswith('myClubMainMenu_') or
                name.startswith('myClubShopAmbassador_item')):
            continue
        f.seek(base+r['FileOffset'])
        raw = f.read(r['FileSize'])
        if raw[3:8] == b'WESYS':
            raw = zlib.decompress(raw[16:])
        try:
            atlas, regions, _ = read_atlas(raw)
            w,h = struct.unpack_from('>HH',atlas,16)
            if len(atlas) != 64+w*h*4:
                print(name, 'unsupported',len(atlas),atlas[:32].hex()); continue
            im = Image.frombytes('RGBA',(w,h),atlas[64:],'raw','ARGB')
            im.save(out/(name+'.png'))
            (out/(name+'.json')).write_text(json.dumps(regions,indent=2))
            print(name,w,h,[(x['name'],x['rect']) for x in regions])
        except Exception as e:
            base_tx = raw.find(b'TXP2')
            if base_tx < 0:
                print(name, str(e)); continue
            tx = raw[base_tx:]
            flags,count,table = struct.unpack_from('>III',tx,20)
            print(name, 'atlases', count, 'flags',hex(flags))
            region_count, region_table, region_names = struct.unpack_from(
                '>III', tx, 36)
            named_count = struct.unpack_from('>I', tx, region_names + 16)[0]
            names_table = struct.unpack_from('>I', tx, region_names + 24)[0]
            region_labels = [None] * region_count
            if named_count == region_count:
                for region_index in range(named_count):
                    _, mapped_index, name_offset = struct.unpack_from(
                        '>III', tx, names_table + region_index * 12)
                    end = tx.index(b'\0', name_offset)
                    label = tx[name_offset:end]
                    if label and label[0] >= 0xa0:
                        label = bytes((value + 128) & 255 for value in label)
                    rect = struct.unpack_from(
                        '>5H', tx, region_table + mapped_index * 10)
                    region_labels[mapped_index] = (label.decode('ascii'), rect)
                print(' regions', region_labels)
            for i in range(count):
                _,length,pos = struct.unpack_from('>III',tx,table+i*12)
                size,packed = struct.unpack_from('>II',tx,pos)
                atlas = lzss_decode(tx[pos+8:pos+length],size)
                w,h = struct.unpack_from('>HH',atlas,16)
                if len(atlas) == 64+w*h*4:
                    Image.frombytes('RGBA',(w,h),atlas[64:],'raw','ARGB').save(out/(name+f'.{i}.png'))
                    print(' ',i,w,h)

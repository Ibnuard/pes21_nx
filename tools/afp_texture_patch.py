"""Narrow PES21 TXP2 atlas reader (format research: DragonMinded/bemaniutils).

Only the atlas payload is replaced. AFP scripts, region mappings and geometry
remain game-owned. Unsupported formats fail closed.
"""
from pathlib import Path
import struct


def lzss_decode(data: bytes, expected: int) -> bytes:
    window = bytearray(4096)
    output = bytearray()
    head, cursor = 4078, 0
    while cursor < len(data) and len(output) < expected:
        control = data[cursor]
        cursor += 1
        for bit in range(8):
            if len(output) >= expected:
                break
            if control & (1 << bit):
                if cursor >= len(data):
                    raise ValueError('truncated LZSS literal')
                sequence = bytes([data[cursor]])
                cursor += 1
                for value in sequence:
                    output.append(value)
                    window[head] = value
                    head = (head + 1) & 4095
            else:
                if cursor + 2 > len(data):
                    raise ValueError('truncated LZSS match')
                source = data[cursor] | ((data[cursor+1] & 0xf0) << 4)
                length = (data[cursor+1] & 15) + 3
                cursor += 2
                for _ in range(min(length, expected-len(output))):
                    value = window[source]
                    source = (source + 1) & 4095
                    output.append(value)
                    window[head] = value
                    head = (head + 1) & 4095
    if len(output) != expected:
        raise ValueError(f'LZSS size mismatch {len(output)} != {expected}')
    return bytes(output)


def read_atlas(container: bytes):
    base = container.find(b'TXP2')
    if base < 0:
        raise ValueError('missing TXP2')
    txp = container[base:base+struct.unpack_from('>I',container,base+12)[0]]
    flags, count, table = struct.unpack_from('>III',txp,20)
    if count != 1 or not flags & 4:
        raise ValueError('expected a single legacy-compressed atlas')
    name, length, offset = struct.unpack_from('>III',txp,table)
    size, compressed_size = struct.unpack_from('>II',txp,offset)
    if compressed_size != length - 8:
        raise ValueError('atlas compression size mismatch')
    atlas = lzss_decode(txp[offset+8:offset+length],size)
    # PES21 header has texture mapping, then regions and region mapping.
    region_count, region_table, region_names = struct.unpack_from('>III',txp,36)
    n = struct.unpack_from('>I',txp,region_names+16)[0]
    names_table = struct.unpack_from('>I',txp,region_names+24)[0]
    if n != region_count:
        raise ValueError('region count mismatch')
    regions = [None]*n
    for i in range(n):
        _crc, index, name_off = struct.unpack_from('>III',txp,names_table+i*12)
        name = txp[name_off:txp.index(b'\0',name_off)]
        if name and name[0] >= 0xa0:
            name=bytes((c+128)&255 for c in name)
        rect=struct.unpack_from('>5H',txp,region_table+index*10)
        regions[index]={'name':name.decode('ascii'),'rect':rect}
    return atlas, regions, (base, table, offset, length)


def lzss_encode(data: bytes) -> bytes:
    from collections import defaultdict, deque
    candidates = defaultdict(lambda: deque(maxlen=48))
    output=bytearray()
    pos=0
    while pos < len(data):
        flag_index=len(output)
        output.append(0)
        for bit in range(8):
            if pos>=len(data):
                break
            matches=candidates[data[pos:pos+3]]
            best_length,best_pos=0,0
            for candidate in reversed(matches):
                if pos-candidate>4096:
                    break
                length=3
                while length<18 and pos+length<len(data) and data[candidate+length]==data[pos+length]:
                    length+=1
                if length>best_length:
                    best_length,best_pos=length,candidate
                if length==18:
                    break
            if best_length>=3:
                pointer=(4078+best_pos)&4095
                output.extend((pointer&255,((pointer>>4)&0xf0)|(best_length-3)))
                step=best_length
            else:
                output[flag_index]|=1<<bit
                output.append(data[pos])
                step=1
            for k in range(step):
                if pos+k+3<=len(data):
                    candidates[data[pos+k:pos+k+3]].append(pos+k)
            pos+=step
    return bytes(output)


def replace_atlas(container: bytes, atlas: bytes) -> bytes:
    original,regions,(base,table,offset,length)=read_atlas(container)
    if len(atlas)!=len(original) or atlas[:64]!=original[:64]:
        raise ValueError('atlas dimensions/header must remain unchanged')
    compressed=lzss_encode(atlas)
    if lzss_decode(compressed,len(atlas))!=atlas:
        raise ValueError('atlas compression roundtrip failed')
    packed=struct.pack('>II',len(atlas),len(compressed))+compressed
    output=bytearray(container)
    txp_length=struct.unpack_from('>I',container,base+12)[0]
    if len(packed)>length:
        # The atlas is the last payload in this verified container. Resize it,
        # keeping every preceding script/name/region offset byte-identical.
        if offset+length>txp_length or txp_length-offset-length>16:
            raise ValueError('cannot resize a non-terminal atlas')
        end=base+offset
        output=output[:end]+packed
        new_length=len(output)-base
        struct.pack_into('>I',output,base+12,new_length)
        struct.pack_into('<I',output,12,new_length)
        output.extend(b'\0'*((-len(output))%16))
    else:
        output[base+offset:base+offset+length]=packed+b'\0'*(length-len(packed))
    struct.pack_into('>I',output,base+table+4,len(packed))
    verified,verified_regions,_=read_atlas(bytes(output))
    if verified!=atlas or verified_regions!=regions:
        raise ValueError('TXP2 replacement roundtrip failed')
    return bytes(output)


if __name__ == '__main__':
    import json
    root=Path('local-debug/stability-visuals/pes21-ui')
    for name in ('game2dPes','game2d'):
        atlas,regions,layout=read_atlas((root/(name+'.bin')).read_bytes())
        (root/(name+'.atlas')).write_bytes(atlas)
        (root/(name+'.regions.json')).write_text(json.dumps(regions,indent=2))
        print(name,len(atlas),atlas[:64].hex(),layout)
        print(regions)

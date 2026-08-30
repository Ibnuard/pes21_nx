"""Strict reader for the inline/separate cooked Texture2D mip layouts used here.

No package metadata is rewritten: callers replace same-sized payloads only.
"""
from dataclasses import dataclass
from pathlib import Path
import struct
import texture2ddecoder
from PIL import Image


@dataclass
class Mip:
    width: int
    height: int
    file: str
    offset: int
    size: int


class Texture:
    def __init__(self, path: Path):
        self.path = path
        self.files = {'uexp': path.read_bytes()}
        if path.with_suffix('.ubulk').exists():
            self.files['ubulk'] = path.with_suffix('.ubulk').read_bytes()
        data = self.files['uexp']
        begin = data.find(b'PF_')
        if begin < 16:
            raise ValueError(f'{path}: no pixel format')
        end = data.index(b'\0',begin)+1
        self.format = data[begin:end-1].decode()
        self.width,self.height,slices,length = struct.unpack_from('<4I',data,begin-16)
        if length != end-begin or slices != 1:
            raise ValueError('unsupported texture array/layout')
        self.first_mip,count = struct.unpack_from('<2I',data,end)
        if not 1 <= count <= 16:
            raise ValueError('invalid mip count')
        cursor = end+8
        self.mips=[]
        for i in range(count):
            cooked,flags,elements,size,offset=struct.unpack_from('<4Iq',data,cursor)
            cursor+=24
            if cooked != 1 or elements != size:
                raise ValueError(f'unsupported bulk layout {flags:x}')
            if flags & 0x40:
                file, payload = 'uexp', cursor
                cursor += size
            elif flags & 0x100:
                file, payload = 'ubulk', offset
                # Older PES21 packages store offsets relative to BulkDataStart,
                # effectively negative by the end of .uasset + .uexp.
                if not flags & 0x10000:
                    payload += path.with_suffix('.uasset').stat().st_size + len(data) - 4
            else:
                raise ValueError(f'unsupported bulk flags {flags:x}')
            w,h,depth=struct.unpack_from('<3I',data,cursor)
            cursor+=12
            expected = self.payload_size(w,h)
            minimum = 4 if 'ETC' in self.format else 1
            if depth != 1 or size != expected or w != max(minimum,self.width>>i) or h != max(minimum,self.height>>i):
                raise ValueError(f'{path.name}: mip {i} {w}x{h} bytes={size}, expected={expected}')
            if file not in self.files or payload < 0 or payload+size > len(self.files[file]):
                raise ValueError(f'{path.name}: bulk range {file} {payload}+{size}')
            self.mips.append(Mip(w,h,file,payload,size))

    def payload_size(self,w,h):
        if self.format in ('PF_ETC1','PF_ETC2_RGB'):
            return ((w+3)//4)*((h+3)//4)*8
        if self.format == 'PF_ETC2_RGBA':
            return ((w+3)//4)*((h+3)//4)*16
        if self.format == 'PF_B8G8R8A8':
            return w*h*4
        if self.format == 'PF_G8':
            return w*h
        raise ValueError(f'unsupported pixel format {self.format}')

    def payload(self,index=0):
        mip=self.mips[index]
        return self.files[mip.file][mip.offset:mip.offset+mip.size]

    def decode(self,index=0):
        mip=self.mips[index]
        raw=self.payload(index)
        decoders={'PF_ETC1':texture2ddecoder.decode_etc1,'PF_ETC2_RGB':texture2ddecoder.decode_etc2,
                  'PF_ETC2_RGBA':texture2ddecoder.decode_etc2a8}
        if self.format in decoders:
            raw=decoders[self.format](raw,mip.width,mip.height)
        if self.format == 'PF_G8':
            return Image.frombytes('L',(mip.width,mip.height),raw).convert('RGBA')
        return Image.frombytes('RGBA',(mip.width,mip.height),raw,'raw','BGRA')

    def replace(self,payloads):
        if len(payloads)!=len(self.mips):
            raise ValueError('must supply every mip, not just mip zero')
        output={name:bytearray(data) for name,data in self.files.items()}
        for mip,data in zip(self.mips,payloads):
            if len(data)!=mip.size:
                raise ValueError('replacement changes bulk payload size')
            output[mip.file][mip.offset:mip.offset+mip.size]=data
        return {name:bytes(data) for name,data in output.items()}


if __name__=='__main__':
    import sys
    for root in sys.argv[1:]:
        for path in Path(root).rglob('*.uexp'):
            if not ('pitch' in path.stem.lower() or 'MatchTime' in path.stem):
                continue
            try:
                texture=Texture(path)
                print(path.name,texture.format,[(m.width,m.height,m.file,m.offset) for m in texture.mips])
            except ValueError as e:
                print(path.name,str(e))

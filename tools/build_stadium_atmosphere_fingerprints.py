"""Emit body hashes for explicitly selected local stadium colour materials.

No shader source or game payload is written to the public tree. Shader maps
without the audited world-position varying (including depth passes) are refused.
"""
import argparse
from pathlib import Path
import re
import zlib

MATERIALS=('bf','M_Audience_2','M_Audience_Low','M_cover_black','M_flag',
           'M_frame','M_roofFrame','M_vari001',
           *('M_bsm%02d'%i for i in range(1,12)),'M_bsm05_Inst')

def shader_sources(path):
    data=path.read_bytes()
    for match in re.finditer(b'\x78[\x01\x5e\x9c\xda]',data):
        try:raw=zlib.decompress(data[match.start():])
        except zlib.error:continue
        if not raw.startswith(b'LSLGSP'):continue
        start=raw.find(b'#version');end=raw.find(b'\0',start)
        if start>=0 and end>start:yield raw[start:end].replace(b'\r\n',b'\n')

def body_hash(body):
    value=14695981039346656037
    for byte in body:
        if byte not in b' \r\n\t':value=((value^byte)*1099511628211)&((1<<64)-1)
    return value

def collect(root):
    hashes=set();accepted=refused=0
    for name in MATERIALS:
        path=root/(name+'.uexp')
        if not path.is_file():raise ValueError('Owned fixture unavailable: '+str(path))
        for source in shader_sources(path):
            if not all(token in source for token in (b'#version 310 es',
                b'in highp vec4 in_TEXCOORD8;',b'View_PreViewTranslation',
                b'View_WorldCameraOrigin',b'out_Target0.xyzw = ')):
                refused+=1;continue
            body=source.split(b'void main()',1)[1]
            hashes.add(body_hash(b'void main()'+body));accepted+=1
    return hashes,accepted,refused

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--materials',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();hashes,accepted,refused=collect(a.materials)
    a.output.write_text('/* Audited native stadium/crowd colour bodies only. */\n'+
        ''.join('UINT64_C(0x%016x),\n'%v for v in sorted(hashes)),encoding='utf-8')
    print(dict(materials=len(MATERIALS),accepted_records=accepted,unique_bodies=len(hashes),refused_records=refused))

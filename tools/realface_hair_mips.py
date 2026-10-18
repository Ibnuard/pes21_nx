"""Bounded alpha-test survival for nonempty 1–2 pixel cooked hair mips.

Only a fully discarded tiny mip may be scaled. RGB, dimensions, payload
lengths, mip zero and all already-visible mips remain exact. Empty source
hair placeholders are deliberately preserved. Device testing is separate.
"""
import math

from cooked_texture import Texture


def protect_payloads(payloads, dimensions):
    if not payloads or len(payloads) != len(dimensions):
        raise ValueError('Complete mip chain required')
    for raw,(w,h) in zip(payloads,dimensions):
        if w<1 or h<1 or len(raw)!=w*h*4:
            raise ValueError('Expected same-sized BGRA hair payload')
    if max(payloads[0][3::4]) < 85:
        return payloads,dict(source_has_visible_hair=False,changed_mips=[])
    result=list(payloads);changed=[]
    for index,(raw,(w,h)) in enumerate(zip(payloads,dimensions)):
        maximum=max(raw[3::4])
        if maximum>=85:
            continue
        if index==0 or w>2 or h>2 or maximum==0:
            raise ValueError('Discarded hair mip exceeds the bounded tiny-mip policy')
        data=bytearray(raw)
        # 86 clears the native approximately one-third threshold with a byte
        # of margin. Preserve alpha ratios and leave zero-alpha texels zero.
        for offset in range(3,len(data),4):
            data[offset]=min(255,math.ceil(data[offset]*86/maximum))
        result[index]=bytes(data)
        changed.append(dict(index=index,width=w,height=h,old_alpha_max=maximum,
                            new_alpha_max=max(data[3::4]),rgb_unchanged=True))
    return result,dict(source_has_visible_hair=True,changed_mips=changed)


def protect_texture(path):
    texture=Texture(path)
    if texture.format!='PF_B8G8R8A8':
        raise ValueError('Only native uncompressed BGRA hair is supported')
    payloads,proof=protect_payloads([texture.payload(i) for i in range(len(texture.mips))],
                                    [(m.width,m.height) for m in texture.mips])
    if proof['changed_mips']:
        for suffix,data in texture.replace(payloads).items():
            path.with_suffix('.'+suffix).write_bytes(data)
        checked=Texture(path)
        if any(checked.payload(i)!=raw for i,raw in enumerate(payloads)):
            raise ValueError('Hair mip payload roundtrip changed')
    return proof

"""Verify the cooked mesh's embedded reference rig against an explicit contract."""
import base64
import math
import struct


def audit_rig(document,reference,include_bones=False):
    raw=base64.b64decode(document['Exports'][0]['Extras']);names=document['NameMap']
    count=len(reference);matches=[]
    for off in range(len(raw)-4):
        if struct.unpack_from('<I',raw,off)[0]!=count:continue
        try:
            info=[struct.unpack_from('<iii',raw,off+4+i*12) for i in range(count)]
            if not all(0<=a<len(names) and b==0 and -1<=c<i for i,(a,b,c) in enumerate(info)):continue
            if names[info[0][0]]!='root_main':continue
            pos=off+4+count*12
            if struct.unpack_from('<I',raw,pos)[0]!=count:continue
            bones=[dict(name=names[a],parent=c,trs=struct.unpack_from('<10f',raw,pos+4+i*40)) for i,(a,b,c) in enumerate(info)]
            if [(b['name'],b['parent']) for b in bones]!=[(b['name'],b['parent']) for b in reference]:continue
            errors=[]
            for a,b in zip(bones,reference):
                x,y=a['trs'],b['trs']
                if not all(math.isfinite(v) for v in x):raise ValueError('Non-finite cooked rig')
                errors.append(min(max(abs(v-z) for v,z in zip(x[:4],y[:4])),max(abs(v+z) for v,z in zip(x[:4],y[:4]))))
                errors.extend(abs(v-z) for v,z in zip(x[4:],y[4:]))
            matches.append((max(errors),bones))
        except (struct.error,IndexError):continue
    if len(matches)!=1 or matches[0][0]>=.002:
        raise ValueError('Cooked rig differs from native import contract: '+str(matches))
    result=dict(bones=count,max_component_drift=matches[0][0],imports=sorted({v['ObjectName'] for v in document['Imports']}))
    if include_bones:result['embedded_rig']=matches[0][1]
    return result

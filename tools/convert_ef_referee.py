"""Bake locally owned EF10 locomotion onto the PES21 Mobile referee skeleton.

The owned PES21 decoder evaluates EF's GANI/FRIG tracks, including limb IK.
World rotations are mapped by bone name; positions are rebuilt using PES21
bone lengths, then render-skeleton conversion rotations are applied. Extra
spine/neck rotations survive in the mapped world orientations. No EF executable
function or native player skeleton is replaced.
Generated clips contain proprietary motion data: keep them local/ignored.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import zipfile
import zlib

try:
    from .pack_runtime_assets import checksum
except ImportError:
    from pack_runtime_assets import checksum

CLIPS = ('referee_stand_0', 'walk_1_1', 'run_2_2', 'run_3_3',
         'referee_stand_0_whistle', 'referee_hand_up_0',
         'referee_1_0_000_hand_middle_point_000', 'referee_hand_up_0_hand_down')
# Playback knots, metres/second; blend continuously instead of toggling states.
SPEEDS = (0.0, 1.4, 3.2, 5.8, 0.0, 0.0, 0.0, 0.0)
ALIASES = {'sk_belly': 'sk_spine_01', 'sk_chest': 'sk_spine_03',
           'sk_neck': 'sk_cervicalspine_02'}
MAGIC = b'NXREF01\0'
HEADER = struct.Struct('<8sIIIIQ')
ENTRY = struct.Struct('<IIffIIII')
POSE = struct.Struct('<8f')

def unpack_wesys(data: bytes) -> bytes:
    if data[3:8] != b'WESYS':
        return data
    if len(data) < 16:
        raise ValueError('truncated WESYS header')
    packed, size = struct.unpack_from('<II', data, 8)
    if packed != len(data)-16 or not 0 < size <= 64*1024*1024:
        raise ValueError('invalid WESYS bounds')
    decoder = zlib.decompressobj()
    result = decoder.decompress(data[16:], size+1)
    if len(result) != size or not decoder.eof or decoder.unused_data:
        raise ValueError('WESYS size mismatch')
    return result

def read_skeleton(data: bytes) -> list[dict]:
    data = unpack_wesys(data)
    if len(data) < 8:
        raise ValueError('truncated skeleton header')
    version, count = struct.unpack_from('<II', data)
    if version not in (1, 2) or not 1 <= count <= 96:
        raise ValueError('unsupported skeleton')
    start, stride = (8, 44) if version == 1 else (16, 28)
    if start+stride*count > len(data):
        raise ValueError('truncated skeleton')
    bones=[]
    for i in range(count):
        at=start+i*stride
        ns=at+4+struct.unpack_from('<I',data,at+4)[0]
        if not start+stride*count <= ns < len(data):
            raise ValueError('invalid skeleton name')
        name=data[ns:data.index(0,ns)].decode('ascii')
        if not name:
            raise ValueError('empty skeleton name')
        parent=struct.unpack_from('<i',data,at+8)[0]
        pos=struct.unpack_from('<3f',data,at+12)
        if parent < -1 or parent >= i or (i > 0 and parent == -1) or not all(math.isfinite(v) and abs(v)<5 for v in pos):
            raise ValueError('invalid bone hierarchy/translation')
        bones.append(dict(name=name,parent=parent,pos=pos))
    if len({b['name'] for b in bones}) != count:
        raise ValueError('duplicate skeleton bone')
    return bones

def normalized(q):
    n=math.sqrt(sum(v*v for v in q))
    if not math.isfinite(n) or not 0.95<n<1.05:
        raise ValueError('decoder produced an invalid rotation')
    return tuple(v/n for v in q)


def render_rotations(data: bytes, target: list[dict]) -> list[tuple]:
    """Read SkelFile::GetConvRotations from the RENDER (not animation) ASK."""
    data = unpack_wesys(data)
    bones = read_skeleton(data)
    if [(b['name'], b['parent']) for b in bones] != [(b['name'], b['parent']) for b in target]:
        raise ValueError('render/animation skeleton mapping mismatch')
    version, count = struct.unpack_from('<II', data)
    start = 8+28 if version == 1 else (16+28*count+15)&~15
    stride = 44 if version == 1 else 16
    end = start + (count-1)*stride + 16
    name_start = min((8 if version == 1 else 16)+i*(44 if version == 1 else 28)+4+
                     struct.unpack_from('<I', data, (8 if version == 1 else 16)+i*(44 if version == 1 else 28)+4)[0]
                     for i in range(count))
    if end > len(data) or end > name_start:
        raise ValueError('truncated render conversion rotations')
    return [normalized(struct.unpack_from('<4f', data, start+i*stride)) for i in range(count)]


def render_rotation(world, conversion):
    # Matches AnimConvertBoneSpacePlugin (forward conversion): world * bind.
    # Positions stay in model space. Applying these before FK bends the limbs.
    x,y,z,w=world; X,Y,Z,W=conversion
    return normalized((w*X+x*W+y*Z-z*Y, w*Y-x*Z+y*W+z*X,
                       w*Z+x*Y-y*X+z*W, w*W-x*X-y*Y-z*Z))

def rotate(q,v):
    x,y,z,w=q; a,b,c=v
    tx,ty,tz=2*(y*c-z*b),2*(z*a-x*c),2*(x*b-y*a)
    return (a+w*tx+y*tz-z*ty,b+w*ty+z*tx-x*tz,c+w*tz+x*ty-y*tx)

def retarget(source: list[dict], target: list[dict], q, p) -> tuple[list,list]:
    lookup={b['name']:i for i,b in enumerate(source)}
    rotations=[]; positions=[]
    for b in target:
        name=ALIASES.get(b['name'],b['name'])
        if name not in lookup:
            raise ValueError('missing source bone '+name)
        index=lookup[name];rotations.append(normalized(q[index]))
        if b['parent'] < 0:
            # Root locomotion is applied by the wrapper; retain vertical motion.
            if abs(source[index]['pos'][1]) < 0.001:
                raise ValueError('source root has no rest height')
            ratio=b['pos'][1]/source[index]['pos'][1]
            positions.append((0.0,p[index][1]*ratio,0.0))
        else:
            parent=b['parent'];offset=rotate(rotations[parent],b['pos'])
            positions.append(tuple(a+b for a,b in zip(positions[parent],offset)))
    if any(not math.isfinite(v) or abs(v)>4 for pos in positions for v in pos):
        raise ValueError('retargeted pose out of bounds')
    return rotations,positions

def extract_ef(xapk: Path, vm) -> tuple[bytes,bytes,dict]:
    # Existing preparation helpers use sibling CLI imports. Load them only for
    # extraction, so pure format/retargeting users do not need the CLI path.
    tool_dir = str(Path(__file__).resolve().parent)
    if tool_dir not in sys.path:
        sys.path.insert(0, tool_dir)
    from prepare_runtime import read_cpk_packet
    hashes={}
    for name in CLIPS:
        encoded=name.encode();ptr=vm.alloc(len(encoded)+1,encoded+b'\0')
        hashes[vm.call('_ZN3fox10FoxStrHashEPKcm',ptr,len(encoded))]=name
    found={};skel=rig=None
    with ExitStack() as stack:
        outer=stack.enter_context(zipfile.ZipFile(xapk))
        pads=[n for n in outer.namelist() if n.endswith('pad_it_0.apk')]
        if len(pads)!=1:raise ValueError('expected one EF asset pack')
        stream=stack.enter_context(outer.open(pads[0]))
        inner=stack.enter_context(zipfile.ZipFile(stream))
        cpk=stack.enter_context(inner.open('assets/dt230_mobile_all.cpk'))
        head=read_cpk_packet(cpk,0,b'CPK ')[0]
        rows=read_cpk_packet(cpk,head['TocOffset'],b'TOC ')
        base=min(head['TocOffset'],head['ContentOffset'])
        for row in sorted(rows,key=lambda r:r['FileOffset']):
            name=row['FileName']
            if name not in ('body_anim_skel.ask','body_skel.frig') and not (
                    name.startswith('body_anime_file') and name.endswith('.mtar')):continue
            size=int(row['FileSize'])
            if not 0<size<=64*1024*1024:raise ValueError('invalid CPK member size')
            cpk.seek(base+row['FileOffset']);data=unpack_wesys(cpk.read(size))
            if name=='body_anim_skel.ask':skel=data;continue
            if name=='body_skel.frig':rig=data;continue
            magic,count=struct.unpack_from('<II',data)
            if magic!=0x0bffa89c or not 0<count<100000 or 32+16*count>len(data):
                raise ValueError('unsupported MTAR index')
            for i in range(count):
                key,offset,length=struct.unpack_from('<QII',data,32+i*16)
                if key not in hashes:continue # Full identity, not just low hash bits.
                if offset<32+16*count or offset+length>len(data):raise ValueError('invalid clip bounds')
                if hashes[key] in found:raise ValueError('duplicate motion identity')
                found[hashes[key]]=data[offset:offset+length]
    if set(found)!=set(CLIPS) or skel is None or rig is None:
        raise ValueError('EF input is missing required motions/skeleton')
    return skel,rig,found

class Sampler:
    def __init__(self,vm,skeleton,rig):
        self.vm=vm;self.bones=read_skeleton(skeleton);n=len(self.bones);self.n=n
        if len(rig)<32 or struct.unpack_from('<I',rig,8)[0]!=102:
            raise ValueError('unsupported rig version')
        units=struct.unpack_from('<I',rig,12)[0]
        if not 1<=units<=32:raise ValueError('invalid rig unit count')
        for off in struct.unpack_from('<'+str(units)+'I',rig,32):
            if not 0<off<len(rig)-20 or struct.unpack_from('<I',rig,off)[0] not in (1,2,3,4,5,7,8):
                raise ValueError('unsupported rig unit')
        data=bytearray(n*32);positions=bytearray(n*16)
        for i,b in enumerate(self.bones):
            struct.pack_into('<i',data,i*32,b['parent'])
            struct.pack_into('<4f',data,i*32+16,*b['pos'],0)
            struct.pack_into('<4f',positions,i*16,*b['pos'],0)
        bp=vm.alloc(len(data),data)
        self.default_positions=bytes(positions);self.default_rotations=struct.pack('<4f',0,0,0,1)*n
        self.p=vm.alloc(n*16,positions);self.q=vm.alloc(n*16,self.default_rotations)
        self.rs=vm.alloc(128)
        vm.call('_ZN3fox4anim17RigPoseToSkeletonC2EPKNS_4BoneEPN10Vectormath3Aos4QuatEPNS6_7Vector3EiPKs',self.rs,bp,self.q,self.p,n,0)
        self.rig=vm.alloc(len(rig),rig)
        self.pose=vm.call('_ZN3fox4anim7RigPose6CreateEPKNS0_6RigDefE',self.rig)
        self.mask=vm.alloc(16)
        vm.call('_ZNK3fox4anim6RigDef11GetFullMaskERNS0_8BoneMaskE',self.rig,self.mask)

    def sample(self,gani):
        vm=self.vm
        if len(gani)<164 or struct.unpack_from('<III',gani) != (201106130,32,len(gani)):
            raise ValueError('unsupported GANI header')
        # This EF body format has a MOTION parent and UNIT track node at 0x60.
        if struct.unpack_from('<IIII',gani,0x60)!=(3337172921,0,1,48):
            raise ValueError('unsupported GANI track layout')
        frames,scale=struct.unpack_from('<Ib',gani,156)
        if not 2<=frames<=600 or scale!=10:raise ValueError('unsupported motion timing')
        th=vm.alloc(len(gani),gani)+144
        size=vm.call('_ZN3fox4anim12TrackControl19GetTrackControlSizeEPKNS0_11TrackHeaderE',th)
        tc=vm.alloc(size);vm.call('_ZN3fox4anim12TrackControlC2EPKNS0_11TrackHeaderEi',tc,th,0)
        result=[]
        for frame in range(frames):
            vm.uc.mem_write(self.p,self.default_positions);vm.uc.mem_write(self.q,self.default_rotations)
            vm.call('_ZN3fox4anim12TrackControl7SetDataEPKNS0_11TrackHeaderEff',tc,th,floats=(frame*scale,0.0))
            vm.call('_ZN3fox4anim7RigPose10UpdatePoseERKNS0_8BoneMaskEPKNS0_12TrackControlEPKNS0_6RigDefEPNS0_11RigSkeletonEj',self.pose,self.mask,tc,self.rig,self.rs,0)
            vm.call('_ZNK3fox4anim7RigPose14PoseToSkeletonEPNS0_11RigSkeletonEPKNS0_6RigDefE',self.pose,self.rs,self.rig)
            q=[normalized(struct.unpack('<4f',vm.read(self.q+i*16,16))) for i in range(self.n)]
            p=[struct.unpack('<4f',vm.read(self.p+i*16,16)) for i in range(self.n)]
            result.append((q,p))
        return result

def write_bank(clips,output: Path):
    if len(clips) not in (4,8):
        raise ValueError('expected four locomotion clips, optionally four ordered gestures')
    count=len(clips)
    index=bytearray();payload=bytearray();offset=HEADER.size+ENTRY.size*count
    for clip,speed in zip(clips,SPEEDS):
        frames=len(clip)
        if not 2 <= frames <= 600:
            raise ValueError('invalid clip frame count')
        index+=ENTRY.pack(frames,offset,30.0,speed,0,0,0,0)
        for frame in clip:
            if len(frame)!=19:raise ValueError('expected 19 renderer slots')
            for q,p in frame:
                if len(q) != 4 or len(p) != 3 or not all(math.isfinite(v) and abs(v)<=4 for v in p):
                    raise ValueError('invalid bone pose')
                payload+=POSE.pack(*normalized(q),*p,1.0)
        offset+=frames*19*POSE.size
    content=index+payload
    data=HEADER.pack(MAGIC,3 if count==8 else 2,count,19,ENTRY.size,checksum(content))+content
    if len(data) > 512*1024:
        raise ValueError('clip bank exceeds runtime limit')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(data)
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def convert(xapk: Path,native_lib: Path,target_path: Path,output: Path,render_path: Path):
    try:from .native_animation_bake import NativeAnimationVM
    except ImportError:from native_animation_bake import NativeAnimationVM
    vm=NativeAnimationVM(native_lib)
    target=read_skeleton(target_path.read_bytes())
    if len(target)!=20:raise ValueError('expected PES21 20-bone skeleton')
    conversions=render_rotations(render_path.read_bytes(),target)
    slot_names=[];ptr=vm.alloc(4)
    for i in range(19):
        vm.uc.mem_write(ptr,struct.pack('<I',i))
        nameptr=vm.call('_ZN4draw8GetBonesERKi',ptr)
        address=struct.unpack('<Q',vm.read(nameptr,8))[0]
        slot_names.append(vm.read(address,64).split(b'\0')[0].decode('ascii'))
    byname={b['name']:i for i,b in enumerate(target)}
    if len(set(slot_names))!=19 or not set(slot_names)<=byname.keys():raise ValueError('native renderer bone map mismatch')
    skel,rig,ganis=extract_ef(xapk,vm);sampler=Sampler(vm,skel,rig)
    baked=[];report=[]
    for name in CLIPS:
        samples=sampler.sample(ganis[name]);poses=[]
        for q,p in samples:
            rq,rp=retarget(sampler.bones,target,q,p)
            poses.append([(render_rotation(rq[byname[n]],conversions[byname[n]]),
                           rp[byname[n]]) for n in slot_names])
        # Align locomotion phases at the left foot's furthest forward position.
        phase=0
        if name in CLIPS[1:4]:
            left,right=slot_names.index('sk_foot_l'),slot_names.index('sk_foot_r')
            phase=max(range(len(poses)),key=lambda i:poses[i][left][1][2]-poses[i][right][1][2])
            poses=poses[phase:]+poses[:phase]
        baked.append(poses)
        report.append(dict(source=name,frames=len(poses),phase_shift=phase,
                           source_sha256=hashlib.sha256(ganis[name]).hexdigest()))
        print(f'{name}: {len(poses)} frames retargeted',flush=True)
    info=write_bank(baked,output)
    info.update(clips=report,renderer_slots=slot_names,source_bones=len(sampler.bones),
                target_bones=len(target),native_lib_sha256=hashlib.sha256(native_lib.read_bytes()).hexdigest(),
                native_skeleton_sha256=hashlib.sha256(target_path.read_bytes()).hexdigest(),hardware_tested=False)
    info.update(render_skeleton_sha256=hashlib.sha256(render_path.read_bytes()).hexdigest(),
                bank_version=3, rotation_space='PES21 render bone space')
    output.with_suffix('.local.json').write_text(json.dumps(info,indent=2)+'\n')
    return info

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--xapk',type=Path,required=True)
    p.add_argument('--native-lib',type=Path,required=True)
    p.add_argument('--pes21-skeleton',type=Path,required=True)
    p.add_argument('--pes21-render-skeleton',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(convert(a.xapk,a.native_lib,a.pes21_skeleton,a.output,a.pes21_render_skeleton),indent=2))
if __name__=='__main__':main()

"""Package paired runtime probes and a verified entrance-only rollback locally.

No active runtime mutation, face recook or duplicate OBB. Proprietary cinematic
payloads are copied only into ignored local-debug output. Unknown installed
cinematic archives are rejected by the included installer.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import zipfile

from elftools.elf.elffile import ELFFile
from entrance_scene_canary import Cpk
from fixdemo_scene_table import parse_scene_table
from prepare_loose_cpk import read_manifest

ROOT=Path(__file__).resolve().parents[1]
TABLE='common/demo/fixdemo/ent/table_ent.bin'
CPK='dt220_mobile_all.cpk'


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def inspect_build(folder,diagnostic,pair):
    folder=Path(folder)
    nro=folder/'pes21_nx.nro'
    data=nro.read_bytes()
    if data[16:20]!=b'NRO0' or pair.encode() not in data:raise ValueError('Wrong NRO/pair')
    if b'camera policy: STADIUM-V2 suspended' not in data:raise ValueError('Camera suspension absent')
    for text in (b'Unexpected Stadium V2 native motion boundary',b'PESNX_CINEMATIC_TRACE_V1'):
        if text in data:raise ValueError('Suspended native installer still present')
    for text in (b'gpu_samples=',b'face_component='):
        if (text in data)!=diagnostic:raise ValueError('Wrong diagnostic/production variant')
    with (folder/'pes21_nx.elf').open('rb') as f:
        elf=ELFFile(f)
        loads=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
        if len(loads)!=3:raise ValueError('Unexpected ELF segment count')
        for i,load in enumerate(loads):
            start,size=struct.unpack_from('<II',data,0x20+i*8)
            if start!=load['p_vaddr'] or load['p_filesz']>size:raise ValueError('NRO segment layout differs')
            skip=0x80 if i==0 else 0
            expected=load.data()[skip:]
            if data[start+skip:start+skip+len(expected)]!=expected:raise ValueError('NRO differs from built ELF')
    return dict(bytes=nro.stat().st_size,sha256=sha(nro),elf_load_segments_match=True,
                near_camera_trace=diagnostic,gpu_timestamp_sampling=diagnostic,
                realface_load_snapshots=diagnostic,hardware_accepted=False)


def entrance_only_canary(baseline,candidate):
    """Never whitelist an archive that also changed another native scene."""
    original,other=Cpk(Path(baseline)),Cpk(Path(candidate))
    if not set(original.index)<=set(other.index):raise ValueError('Canary omitted native members')
    table=parse_scene_table(other.read(TABLE),1)
    if [s['name'] for s in table['scenes']]!=['NX_WALKOUT_CANARY_V1']:
        raise ValueError('Not the reviewed single-entrance canary')
    for name in original.index:
        if name!=TABLE and original.read(name)!=other.read(name):
            raise ValueError('Canary also changed an unrelated native member: '+name)
    for name in set(other.index)-set(original.index):
        if not (name.startswith('common/demo/fixdemo/ent/cut_data/ent_012_') or
                name.startswith('common/demo/anime/FoxAnim/FixDemo/Animations/dml_ent_')):
            raise ValueError('Canary appended an unrelated resource: '+name)
    return sha(candidate)


def package(build_root,baseline_root,output,walkouts=()):
    build_root,baseline_root,output=map(lambda p:Path(p).resolve(),(build_root,baseline_root,output))
    if not output.is_relative_to(ROOT/'local-debug') or output.exists():
        raise ValueError('Use a fresh ignored local-debug output')
    manifest=read_manifest(baseline_root)
    if manifest['version']!=2:raise ValueError('Full-loose V2 baseline required')
    row=next(r for r in manifest['files'] if r['name']==CPK)
    cpk=baseline_root/'LooseCpk'/CPK
    if cpk.stat().st_size!=row['size'] or sha(cpk)!=row['sha256']:
        raise ValueError('Baseline cinematic CPK differs from manifest')
    native_table=parse_scene_table(Cpk(cpk).read(TABLE),1)
    if [s['name'] for s in native_table['scenes']]!=['ENT_MOBILE_CMN']:
        raise ValueError('Baseline contains an experimental entrance')
    allowed=[row['sha256']]+[entrance_only_canary(cpk,p) for p in walkouts]
    builds={k:inspect_build(build_root/k,k=='diagnostic',manifest['build_id'])
            for k in ('production','diagnostic')}
    proof=dict(candidate='Face runtime isolation v42',runtime_pair=manifest['build_id'],
               expected_patch_obb_bytes=manifest['parent_obb_bytes'],builds=builds,
               baseline_cinematics=dict(dt220_sha256=row['sha256'],
                 manifest_sha256=sha(baseline_root/'LooseCpk/manifest.txt'),
                 allowed_installed_dt220_sha256=sorted(set(allowed))),
               hardware_accepted=False,face_payload_included=False,
               missing_heads_fixed=False,stable_60_fps_verified=False,
               active_runtime_modified=False)
    output.mkdir(parents=True)
    for kind,dest in (('production','update'),('diagnostic','diagnostic')):
        (output/dest).mkdir()
        shutil.copy2(build_root/kind/'pes21_nx.nro',output/dest/'pes21_nx.nro')
    target=output/'entrance-baseline/LooseCpk';target.mkdir(parents=True)
    for p in (cpk,baseline_root/'LooseCpk/manifest.txt'):shutil.copy2(p,target/p.name)
    shutil.copy2(ROOT/'tools/install_realface_runtime_probe.ps1',output/'Apply-Update.ps1')
    (output/'VERIFICATION.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    return proof


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-root',type=Path,required=True)
    p.add_argument('--baseline-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--walkout-cpk',type=Path,action='append',default=[])
    p.add_argument('--instructions',type=Path,required=True)
    args=p.parse_args()
    if args.output.with_suffix('.zip').exists():raise ValueError('Archive exists; preserve the earlier candidate')
    result=package(args.build_root,args.baseline_root,args.output,args.walkout_cpk)
    shutil.copy2(args.instructions,args.output/'INSTALL.txt')
    archive=args.output.with_suffix('.zip')
    if archive.exists():raise ValueError('Archive exists; preserve the earlier candidate')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(args.output.rglob('*')):
            if f.is_file():z.write(f,f.relative_to(args.output))
    print(json.dumps(dict(zip=str(archive.resolve()),bytes=archive.stat().st_size,sha256=sha(archive),
                          verification=result),indent=2))


if __name__=='__main__':main()

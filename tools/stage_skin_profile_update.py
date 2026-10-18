"""Stage a reviewed skin policy with byte-level identity/CPK verification.

Does not touch the active runtime. Only PlayerAppearance skin selector bits
may change; height, weight, face ownership and every other CPK member must
remain byte-identical. Both the archive and its paired manifest are emitted.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from patch_player_skin import patch_profiles
from pes21_player_migration import member_payload, cpk_index
from prepare_loose_cpk import read_manifest, write_manifest
from realface_pipeline import sha


def stage(source, output, registry, policy):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or output.exists():
        raise ValueError('Use a new candidate directory')
    manifest = read_manifest(source)
    cpk = source/'LooseCpk/dt200_mobile_all.cpk'
    entry = next(r for r in manifest['files'] if r['name']==cpk.name)
    if cpk.stat().st_size != entry['size'] or sha(cpk) != entry['sha256']:
        raise ValueError('Source CPK and paired manifest differ')
    if policy.get('build_id') != manifest['build_id']:
        raise ValueError('Skin policy targets another roster build')
    member = 'common/etc/appearance/PlayerAppearance.bin'
    raw = member_payload(cpk,member)
    patched, report = patch_profiles(raw,registry,policy)
    changed = [i for i,(a,b) in enumerate(zip(raw,patched)) if a!=b]
    if len(raw)!=len(patched) or any(i%60!=37 or (raw[i]^patched[i])&0xf8 for i in changed):
        raise ValueError('Change escaped player-local skin selector bits')
    if patch_profiles(patched,registry,policy)[0] != patched:
        raise ValueError('Skin update is not idempotent')
    output.mkdir(parents=True)
    table=output/'PlayerAppearance.bin';table.write_bytes(patched)
    destination=output/'update/LooseCpk/dt200_mobile_all.cpk';destination.parent.mkdir(parents=True)
    _,old_rows,old_base=cpk_index(cpk)
    subprocess.run([sys.executable,str(Path(__file__).with_name('repack_cpk_members.py')),
                    str(cpk),str(destination),'--replace',member+'='+str(table),
                    '--expect-members',str(len(old_rows))],check=True)
    _,new_rows,new_base=cpk_index(destination)
    if list(old_rows)!=list(new_rows):raise ValueError('CPK member inventory changed')
    changed_members=[]
    with cpk.open('rb') as a,destination.open('rb') as b:
        for name,old in old_rows.items():
            new=new_rows[name]
            a.seek(old_base+int(old['FileOffset']));b.seek(new_base+int(new['FileOffset']))
            if a.read(int(old['FileSize']))!=b.read(int(new['FileSize'])):changed_members.append(name)
            ignored={'FileOffset','FileSize','ExtractSize'}
            if {k:v for k,v in old.items() if k not in ignored}!={k:v for k,v in new.items() if k not in ignored}:
                raise ValueError('CPK metadata changed')
    if changed_members != ([member] if changed else []):
        raise ValueError('Unexpected changed CPK members')
    entry.update(size=destination.stat().st_size,sha256=sha(destination))
    write_manifest(output/'update',manifest)
    report.update(source_build=manifest['build_id'],source_cpk_sha256=sha(cpk),
                  cpk_sha256=sha(destination),cpk_members_compared=len(old_rows),
                  changed_members=changed_members,changed_bytes=changed,
                  physique_and_identity_unchanged=True,hardware_tested=False)
    (output/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','output','registry','policy'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(stage(a.source,a.output,json.loads(a.registry.read_text(encoding='utf-8')),
                           json.loads(a.policy.read_text(encoding='utf-8'))),indent=2))

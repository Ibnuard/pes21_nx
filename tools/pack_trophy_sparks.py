"""Pack only the authored podium spark mesh and its embedded mobile material."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from pack_stadium_shell import material_shader_versions

NAMESPACE=Path('PesMobile/Content/FootballNX/TrophySparks')


def pack(cooked,repak,output):
    cooked,repak,output=Path(cooked),Path(repak),Path(output)
    if output.exists():raise ValueError('Refuse to replace an existing spark PAK')
    source=cooked/NAMESPACE
    names=[name+suffix for name in ('PodiumSparks','M_PodiumSparks')
           for suffix in ('.uasset','.uexp')]
    if (source/'PodiumSparks.ubulk').is_file():names.append('PodiumSparks.ubulk')
    if any(not (source/name).is_file() for name in names):
        raise ValueError('Cooked podium spark mesh/material missing')
    versions=material_shader_versions(source/'M_PodiumSparks.uexp')
    if versions!={'100','310 es'}:raise ValueError('Embedded ES2 and ES3.1 shaders required')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='trophy-sparks-') as tmp:
        stage=Path(tmp)/'stage'
        target=stage/NAMESPACE
        target.mkdir(parents=True)
        for name in names:shutil.copyfile(source/name,target/name)
        subprocess.run([str(repak),'pack','--version','V8A','--compression','Zlib',str(stage),str(output)],check=True)
        listed=subprocess.check_output([str(repak),'list',str(output)],text=True).splitlines()
        expected=sorted((NAMESPACE/name).as_posix() for name in names)
        if sorted(listed)!=expected:raise ValueError('Unexpected spark PAK members')
        check=Path(tmp)/'verify'
        subprocess.run([str(repak),'unpack',str(output),'--output',str(check)],check=True)
        for name in names:
            if (check/NAMESPACE/name).read_bytes()!=(source/name).read_bytes():
                raise ValueError('Spark PAK roundtrip mismatch')
    report={'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'members':expected,'shader_versions':sorted(versions),'spark_count':128,
            'authored_triangles':512,'active_primitives':1,'new_texture_payloads':0,
            'authored_approximation':True,'faithful_pc_fx_port':False,'device_tested':False}
    output.with_suffix('.local.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('cooked','repak','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(pack(a.cooked,a.repak,a.output),indent=2))

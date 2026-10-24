"""Pack authored UE4.22 precipitation meshes and their mobile WPO materials."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from pack_stadium_shell import material_shader_versions

def pack(cooked,repak,output,light=False,snow=False,world=False):
    if snow and not light:raise ValueError('Scoped snow packing requires light policy')
    if world and (not light or snow):raise ValueError('World field requires both bounded seasonal assets')
    namespace=Path('PesMobile/Content/FootballNX/WeatherWorld' if world else 'PesMobile/Content/FootballNX/WeatherLight' if light else 'PesMobile/Content/FootballNX/Weather')
    source=cooked/namespace
    objects=('RainField','SnowField','M_RainField','M_SnowField') if world else ('SnowField','M_SnowField') if snow else ('RainField','M_RainField') if light else ('RainField','SnowField','M_RainField','M_SnowField')
    meshes=('RainField','SnowField') if world else ('SnowField',) if snow else ('RainField',) if light else ('RainField','SnowField')
    materials=('M_RainField.uexp','M_SnowField.uexp') if world else ('M_SnowField.uexp',) if snow else ('M_RainField.uexp',) if light else ('M_RainField.uexp','M_SnowField.uexp')
    names=[name+suffix for name in objects for suffix in ('.uasset','.uexp')]
    names += [name+'.ubulk' for name in meshes if (source/(name+'.ubulk')).is_file()]
    if any(not (source/n).is_file() for n in names):
        raise ValueError('Cooked rain/snow or materials missing')
    for name in materials:
        if material_shader_versions(source/name)!={'100','310 es'}:
            raise ValueError('Weather requires embedded ES2 and ES3.1 shaders')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='weather-pak-') as tmp:
        stage=Path(tmp)/'stage';target=stage/namespace;target.mkdir(parents=True)
        for name in names: shutil.copyfile(source/name,target/name)
        subprocess.run([str(repak),'pack','--version','V8A','--compression','Zlib',str(stage),str(output)],check=True)
        members=subprocess.check_output([str(repak),'list',str(output)],text=True).splitlines()
        expected=sorted((namespace/n).as_posix() for n in names)
        if sorted(members)!=expected: raise ValueError('Unexpected weather PAK members')
        # Roundtrip each cooked member; refuse a damaged package before staging.
        check=Path(tmp)/'verify'
        subprocess.run([str(repak),'unpack',str(output),'--output',str(check)],check=True)
        for name in names:
            if (check/namespace/name).read_bytes()!=(source/name).read_bytes():
                raise ValueError('Weather PAK roundtrip mismatch')
    report={'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'members':expected,'shader_versions':['100','310 es'],'hardware_tested':False}
    output.with_suffix('.local.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('cooked','repak','output'):p.add_argument('--'+arg,type=Path,required=True)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--light-rain',action='store_true')
    mode.add_argument('--light-snow',action='store_true')
    mode.add_argument('--world-field',action='store_true')
    a=p.parse_args();print(json.dumps(pack(a.cooked,a.repak,a.output,a.light_rain or a.light_snow or a.world_field,a.light_snow,a.world_field),indent=2))

"""Cloud shade must survive native pitch detail, sheen and additive radiance."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

from test_night_lighting_policy import shader_sources
from test_result_flow import build_and_run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from stadium_lite_preview import host_math


def test_final_receiver_preserves_contrast_after_additive_native_light():
    cc = shutil.which('g++')
    if not cc:
        pytest.skip('Host C++ compiler required')
    build_and_run(cc, host_math() + r'''
int main() {
 nxStadiumProfile=12;nxStadiumClimate=vec4(1,0,0,0);nxCloudMotion=vec2(0,1);
 const vec3 grass(.03,.09,.01),added(.5,.6,.4);
 float strongest=1,changed=0;
 for(int y=-3300;y<3300;y+=200)for(int x=-5100;x<5100;x+=200) {
  vec3 world(x,y,0);
  nxCloudMotion.y=0;vec3 base=nxPitchMowing(grass,world);
  nxCloudMotion.y=1;vec3 unchanged=nxPitchMowing(grass,world);
  assert(base.x==unchanged.x && base.y==unchanged.y && base.z==unchanged.z);
  vec3 complete=base+added,shaded=nxPitchCloud(complete,world);
  float factor=shaded.y/complete.y;strongest=min(strongest,factor);
  assert(factor>=.57999 && factor<=1);
  assert(fabs(shaded.x/complete.x-factor)<.00001);
  nxCloudMotion.x=.0666667;changed+=fabs(nxPitchCloud(complete,world).y-shaded.y);
  nxCloudMotion.x=0;
 }
 assert(strongest<.70 && changed>5);
 // Same completed radiance is exact outside Cloudy/Day/pitch gates.
 for(int weather=0;weather<3;weather+=2) {
  nxStadiumClimate.x=weather;vec3 value=nxPitchCloud(added,vec3(0));
  assert(value.x==added.x&&value.y==added.y&&value.z==added.z);
 }
}
''')


def test_actual_native_pitch_variants_receive_cloud_once_after_final_colour():
    cc = shutil.which('gcc')
    if not cc:
        pytest.skip('Host compiler required')
    native = ROOT / 'local-debug/pitch-recreate/native/PesMobile/Content/Assets/bg_lighting_AM1/Materials'
    paths = [native / (n + '.uexp') for n in
             ('M_Pitch_Default', 'M_Pitch_Default_night', 'M_Pitch_Default_night_Low')]
    if not all(p.is_file() for p in paths):
        pytest.skip('Optional legally supplied native pitch shader fixtures unavailable')
    with tempfile.TemporaryDirectory(prefix='cloud-receiver-v79-') as temp:
        source=Path(temp)/'transform.c';exe=source.with_suffix('.exe')
        source.write_text('#include "stadium_lighting_policy.h"\n'
                         'int main(void){char b[262144];size_t n=fread(b,1,sizeof(b)-1,stdin);b[n]=0;'
                         'char*p=stadium_lighting_source(b);if(!p)return 2;fputs(p,stdout);free(p);return 0;}')
        subprocess.run([cc,'-std=c11','-I',str(ROOT/'source'),str(source),'-o',str(exe)],check=True)
        counts=[]
        for path in paths:
            changed=0
            for original in shader_sources(path):
                result=subprocess.run([str(exe)],input=original,capture_output=True)
                assert result.returncode in (0,2)
                if result.returncode==2:
                    assert b'View_BufferSizeAndInvSize' not in original
                    continue
                body=result.stdout.replace(b'\r\n',b'\n').split(b'void main()',1)[1]
                assert body.count(b'nxPitchCloud(')==1
                assert body.index(b'out_Target0.xyzw = ') < body.index(b'out_Target0.xyz=nxPitchCloud(')
                assert body.index(b'nxPitchMowing(') < body.index(b'out_Target0.xyzw = ')
                reads=lambda s:re.findall(rb'texture(?:Lod)?\([^;\n]*?\)',s)
                assert reads(body)==reads(original.split(b'void main()',1)[1])
                assert b'out_Target0.w=' not in body
                changed+=1
            counts.append(changed)
        assert counts==[20,20,18]

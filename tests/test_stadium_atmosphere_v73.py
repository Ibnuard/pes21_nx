"""Execute scoped scene fog edits; native samplers/depth/alpha must stay exact."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_stadium_atmosphere_fingerprints import collect,shader_sources

@pytest.fixture(scope='module')
def driver(tmp_path_factory):
    cc=shutil.which('gcc')
    if not cc:pytest.skip('Host C compiler unavailable')
    source=tmp_path_factory.mktemp('scene-fog')/'fog.c';exe=source.with_suffix('.exe')
    source.write_text('#include <stdio.h>\n#include "stadium_atmosphere.h"\n'
      'int main(void){char s[262144];size_t n=fread(s,1,sizeof(s)-1,stdin);s[n]=0;'
      'int allowed=stadium_atmosphere_scope(s);char *p=stadium_atmosphere_source(s,allowed);'
      'if(!p)return 2;fputs(p,stdout);free(p);return 0;}\n')
    r=subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'source'),str(source),'-o',str(exe)],capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    return exe

def transform(driver,source):
    p=subprocess.run([str(driver)],input=source,capture_output=True)
    assert p.returncode in (0,2),p.stderr
    return p.stdout.replace(b'\r\n',b'\n') if not p.returncode else None

def test_native_audience_and_stand_allowlist_reproduces():
    root=ROOT/'local-debug/pitch-recreate/native/PesMobile/Content/Assets/bg_lighting_AM1/Materials'
    if not root.is_dir():pytest.skip('Ignored owned stadium shader fixtures unavailable')
    actual,accepted,refused=collect(root)
    header=(ROOT/'source/stadium_atmosphere_fingerprints.inc').read_text()
    expected={int(x,16) for x in re.findall(r'0x([0-9a-f]+)',header)}
    assert actual==expected and accepted==400 and refused>0

@pytest.mark.parametrize('name',['M_Audience_2','M_Audience_Low','M_bsm01','M_bsm09','M_roofFrame'])
def test_actual_native_fragments_only_gain_rgb_fog(driver,name):
    p=ROOT/'local-debug/pitch-recreate/native/PesMobile/Content/Assets/bg_lighting_AM1/Materials'/(name+'.uexp')
    if not p.is_file():pytest.skip('Ignored owned material unavailable')
    count=0
    for s in shader_sources(p):
        changed=transform(driver,s)
        if not changed:continue
        count+=1
        old=s.split(b'void main()',1)[1]
        new=changed.split(b'void main()',1)[1]
        edit=b'\n\tout_Target0.xyz=nxRainMist(out_Target0.xyz,in_TEXCOORD8.xyz-View_PreViewTranslation,View_WorldCameraOrigin);\n'
        assert new.count(edit)==1 and new.replace(edit,b'')==old
        assert transform(driver,changed) is None
        assert transform(driver,s+b'// unrecognized body') is None
    assert count==20

@pytest.mark.parametrize('name',['M_atlas_solid_one_0','M_atlas_cutout_one_0','M_crowd_seated'])
def test_authored_stadium_crowd_and_shells_receive_the_same_air(driver,name):
    p=ROOT/'local-debug/stadium-near-camera-v31'/(name+'.frag')
    if not p.is_file():pytest.skip('Ignored owned shell shader unavailable')
    s=p.read_bytes().replace(b'\r\n',b'\n');new=transform(driver,s)
    assert new and b'nxRainMist(out_Target0.xyz' in new
    assert s.count(b'texture')==new.count(b'texture')
    assert re.findall(rb'[^\n]*discard;',s)==re.findall(rb'[^\n]*discard;',new)

def test_unknown_and_screen_space_sources_refused(driver):
    for source in (b'',b'void main(){}',b'#version 310 es\nvoid main(){out_Target0.xyzw=vec4(1.0);}'):
        assert transform(driver,source) is None

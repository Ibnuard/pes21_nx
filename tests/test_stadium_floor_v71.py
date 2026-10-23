"""Known authored shell floor recovery keeps native cutout alpha and walls."""
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def driver(tmp_path_factory):
    cc=shutil.which('gcc')
    if not cc: pytest.skip('Host C compiler unavailable')
    folder=tmp_path_factory.mktemp('stadium-floor')
    source=folder/'floor.c';exe=source.with_suffix('.exe')
    source.write_text('#include "stadium_shell_clip.h"\nint main(void){char s[262144];size_t n=fread(s,1,sizeof(s)-1,stdin);s[n]=0;char*p=stadium_shell_review_source(s);if(!p)return 2;fputs(p,stdout);free(p);return 0;}\n')
    subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-I',(ROOT/'source').as_posix(),source.as_posix(),'-o',exe.as_posix()],check=True)
    return exe


def transform(driver,source):
    result=subprocess.run([str(driver)],input=source,capture_output=True)
    assert result.returncode in (0,2),result.stderr
    return result.stdout.replace(b'\r\n',b'\n') if not result.returncode else None


@pytest.mark.parametrize('name',['M_atlas_solid_one_0','M_atlas_cutout_one_0','M_crowd_seated'])
def test_actual_owned_alpha_discard_is_preserved(driver,name):
    path=ROOT/'local-debug/stadium-near-camera-v31'/(name+'.frag')
    if not path.is_file():pytest.skip('Ignored owned v31 shader fixture unavailable')
    source=path.read_bytes().replace(b'\r\n',b'\n')
    changed=transform(driver,source)
    assert changed and b'nxShellFloorPreserve v71' in changed
    assert re.findall(rb'[^\n]*discard;',source)==re.findall(rb'[^\n]*discard;',changed)
    assert source.count(b'texture')==changed.count(b'texture')
    assert source[source.rindex(b'out_Target0'):]==changed[changed.rindex(b'out_Target0'):]
    assert transform(driver,source+b'// changed unrecognized body') is None
    assert transform(driver,changed) is None


def test_unknown_and_es2_shaders_are_not_modified(driver):
    assert transform(driver,b'void main(){}') is None
    assert transform(driver,b'#version 100\nvoid main(){discard;}') is None


def test_execute_actual_emitted_floor_gate(driver,tmp_path):
    path=ROOT/'local-debug/stadium-near-camera-v31/M_atlas_cutout_one_0.frag'
    if not path.is_file():pytest.skip('Ignored owned v31 shader fixture unavailable')
    changed=transform(driver,path.read_bytes())
    condition=re.search(rb'if\(nxShellFloorWorld[^\n]+',changed).group().decode()
    variable=re.search(r'\) (h\d+)=1.0;',condition).group(1)
    cpp=shutil.which('g++')
    if not cpp:pytest.skip('Host C++ compiler unavailable')
    source=tmp_path/'gate.cpp';exe=source.with_suffix('.exe')
    source.write_text('#include <cmath>\n#include <cassert>\nusing std::abs;\nstruct V{float x,y,z;};\n'
        'float mask(V nxShellFloorWorld,float '+variable+'){'+condition+'return '+variable+';}\n'+r'''
int main(){
 assert(mask({6000,4200,0},0)==1);
 assert(mask({-6000,-4200,-25},0)==1);
 assert(mask({6000,4200,11},0)==0);
 assert(mask({6000,4200,-31},0)==0);
 assert(mask({0,0,0},0)==0);
 assert(mask({5300,3450,0},0)==0);
 assert(mask({6000,4200,300},1)==1);
 for(float alpha:{0.f,.1f,.39f}) assert(mask({6000,4200,0},0)*alpha<.4f);
}
'''.replace('for(float alpha:{0.f,.1f,.39f})','for(float alpha=0;alpha<.4f;alpha+=.1f)'))
    subprocess.run([cpp,'-std=c++17',source.as_posix(),'-o',exe.as_posix()],check=True)
    subprocess.run([str(exe)],check=True)

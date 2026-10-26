"""Bounded podium effects, original-native transform ABI and authored geometry."""
from pathlib import Path
import hashlib
import importlib.util
import math
import os
import re
import shutil
import struct
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import trophy_spark_mesh as spark


def test_spark_runtime_owns_only_its_weak_actor_and_ceremony(tmp_path):
    compiler=shutil.which('gcc') or shutil.which('clang')
    if not compiler:pytest.skip('host C compiler required')
    exe=tmp_path/'sparks.exe'
    built=subprocess.run([compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror',
        (ROOT/'tests/test_trophy_sparks_v89.c').as_posix(),'-o',exe.as_posix(),'-lm'],
        capture_output=True,text=True,timeout=60)
    assert built.returncode==0,built.stdout+built.stderr
    ran=subprocess.run([str(exe)],capture_output=True,text=True,timeout=20)
    assert ran.returncode==0,ran.stdout+ran.stderr
    assert ran.stdout.strip()=='podium sparks: bounded native lifecycle, fixed pose and optional rollback passed'


def test_128_sparks_have_rigid_phase_encoding_and_conservative_culling(tmp_path):
    vertices,uvs,faces=spark.field()
    assert len(vertices)==1024 and len(uvs)==1024 and len(faces)==512
    assert spark.field()==(vertices,uvs,faces)
    minimum=[min(p[i] for p in vertices) for i in range(3)]
    maximum=[max(p[i] for p in vertices) for i in range(3)]
    # These are the cooked bounds extensions, independently checked against
    # each animated corner rather than only the emitter/mesh static centre.
    lower=[minimum[0]-82,minimum[1]-62,minimum[2]-2]
    upper=[maximum[0]+82,maximum[1]+62,maximum[2]+422]
    for particle in range(spark.SPARKS):
        rows=vertices[particle*8:particle*8+8]
        encoded=[struct.unpack('e',struct.pack('e',row[0]))[0]
                 for row in uvs[particle*8:particle*8+8]]
        assert {math.floor(value) for value in encoded}=={particle}
        for frame in range(241):
            delta=spark.trajectory(particle,frame/60)
            for row in rows:
                assert all(lower[i]<=row[i]+delta[i]<=upper[i] for i in range(3))
            assert spark.trajectory(particle,frame/60)==pytest.approx(spark.trajectory(particle,frame/60+4))
    for face in faces:
        assert len(set(face))==3 and all(0<=index<len(vertices) for index in face)
    a,b=tmp_path/'a.obj',tmp_path/'b.obj'
    assert spark.write(a)['sha256']==spark.write(b)['sha256']
    assert a.read_bytes()==b.read_bytes() and b'mtllib' not in a.read_bytes()


def test_optional_original_native_transform_getter_copies_the_40_byte_android_pose():
    if not (ROOT/'dist/pes21_nx/libUE4.so').is_file():
        pytest.skip('compatible ignored libUE4.so required')
    for module in ('elftools','unicorn'):
        if importlib.util.find_spec(module) is None:pytest.skip(module+' required')
    environment=os.environ.copy()
    environment.pop('PYTHONFAULTHANDLER',None)
    ran=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--native-transform-probe'],
        cwd=ROOT,env=environment,capture_output=True,text=True,timeout=45)
    assert ran.returncode==0,ran.stdout+ran.stderr
    assert ran.stdout.strip()=='original Android component transform: pass'


def native_transform_probe():
    library=ROOT/'dist/pes21_nx/libUE4.so'
    if not library.is_file():pytest.skip('compatible ignored libUE4.so required')
    elf_module=pytest.importorskip('elftools.elf.elffile')
    unicorn=pytest.importorskip('unicorn')
    registers=pytest.importorskip('unicorn.arm64_const')
    with library.open('rb') as stream:
        assert hashlib.file_digest(stream,'sha256').hexdigest()=='a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187'
        stream.seek(0);elf=elf_module.ELFFile(stream)
        address,length=0x545FCF8,0x30
        stream.seek(next(elf.address_offsets(address,length)))
        code=stream.read(length)
        assert hashlib.sha256(code).hexdigest()=='cf77ce8a306220c1a64b5f1847a5a959e76c46b7b34c5ec8b8aeb314f048630d'
    source=(ROOT/'source/fixdemo_trophy_sparks.inc').read_text()
    words=re.search(r'getter\[\] = \{([^}]+)\}',source)[1]
    assert struct.pack('<12I',*[int(word,16) for word in re.findall(r'0x[0-9a-f]+',words)])==code
    vm=unicorn.Uc(unicorn.UC_ARCH_ARM64,unicorn.UC_MODE_ARM)
    vm.mem_map(address&~0xFFF,0x1000)
    vm.mem_write(address,code)
    base=0x1000000;vm.mem_map(base,0x4000)
    component,result,stop=base,base+0x1000,base+0x3000
    # Real instructions perform the copy; only fake owned component/output
    # storage is supplied. No native allocation, renderer or target runs here.
    expected=struct.pack('<10f',0,.70710678,0,.70710678,125,-456,72,1,2,3)
    vm.mem_write(component+0x190,expected)
    vm.reg_write(registers.UC_ARM64_REG_X0,component)
    vm.reg_write(registers.UC_ARM64_REG_X8,result)
    vm.reg_write(registers.UC_ARM64_REG_X30,stop)
    vm.emu_start(address,stop,count=50)
    assert bytes(vm.mem_read(result,40))==expected
    print('original Android component transform: pass')


def test_material_is_masked_depth_tested_and_rotates_trajectories_to_world():
    source=(ROOT/'tools/ue_create_trophy_sparks.py').read_text()
    assert "('disable_depth_test',False)" in source
    assert 'BLEND_MASKED' in source and 'MSM_UNLIT' in source
    assert 'TRANSFORMSOURCE_LOCAL' in source and 'TRANSFORM_WORLD' in source
    assert 'MaterialExpressionTextureSample' not in source
    runtime=(ROOT/'source/fixdemo_trophy_sparks.inc').read_text()
    assert 'SetWorld' not in runtime and 'Camera' not in runtime
    assert 'trophy_spark_ops.shadow(component, 0)' in runtime
    assert 'trophy_spark_ops.collision(component, 0)' in runtime


if __name__=='__main__' and sys.argv[1:]==['--native-transform-probe']:
    native_transform_probe()
